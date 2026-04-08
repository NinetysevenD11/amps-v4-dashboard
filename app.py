#!/usr/bin/env python3
"""
app.py 실시간 데이터 반영 속도 개선 패치
사용법: app.py와 같은 폴더에서  python patch_realtime.py
"""
import re, shutil

FILE = "app.py"
shutil.copy(FILE, FILE + ".bak_rt")

with open(FILE, "r", encoding="utf-8") as f:
    code = f.read()

changes = 0

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. load_data() 캐시: 3600초 → 300초 (5분)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
old = "@st.cache_data(ttl=3600, show_spinner=False)\ndef load_data():"
new = "@st.cache_data(ttl=300, show_spinner=False)\ndef load_data():"
if old in code:
    code = code.replace(old, new); changes += 1
    print("✅ [1] load_data() TTL: 3600 → 300초")
else:
    print("⚠  [1] load_data TTL 패턴 미발견 (이미 적용?)")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. fetch_realtime_prices() 캐시: 60초 → 20초
#    + 더 안정적인 방식으로 교체
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
old_rt = """@st.cache_data(ttl=60)
def fetch_realtime_prices():
    prices = {}
    for ticker in REALTIME_TICKERS:
        try:
            info  = yf.Ticker(ticker).fast_info
            price = info.get('last_price') or info.get('lastPrice')
            if price and price > 0: prices[ticker] = float(price)
        except: pass
    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc + timedelta(hours=9)
    fetch_time = now_kst.strftime("%Y-%m-%d %H:%M:%S")
    return prices, fetch_time"""

new_rt = """@st.cache_data(ttl=20)
def fetch_realtime_prices():
    prices = {}
    # 방법 1: fast_info (빠름)
    for ticker in REALTIME_TICKERS:
        try:
            info  = yf.Ticker(ticker).fast_info
            price = info.get('last_price') or info.get('lastPrice')
            if price and price > 0: prices[ticker] = float(price)
        except: pass
    # 방법 2: 누락 티커는 1d 다운로드로 보완
    missing = [t for t in REALTIME_TICKERS if t not in prices]
    if missing:
        try:
            _end = datetime.now()
            _start = _end - timedelta(days=2)
            _raw = yf.download(missing, start=_start.strftime('%Y-%m-%d'),
                               end=_end.strftime('%Y-%m-%d'),
                               progress=False, auto_adjust=True)['Close']
            if isinstance(_raw, pd.Series):
                _raw = _raw.to_frame(name=missing[0])
            for t in missing:
                if t in _raw.columns:
                    s = _raw[t].dropna()
                    if len(s) > 0:
                        prices[t] = float(s.iloc[-1])
        except: pass
    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc + timedelta(hours=9)
    fetch_time = now_kst.strftime("%Y-%m-%d %H:%M:%S")
    return prices, fetch_time"""

if old_rt in code:
    code = code.replace(old_rt, new_rt); changes += 1
    print("✅ [2] fetch_realtime_prices() TTL: 60→20초 + fallback 추가")
else:
    print("⚠  [2] fetch_realtime_prices 패턴 미발견")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. RT 주입 후 MA/지표 재계산 코드 추가
#    기존: QQQ_DD, HYG_IEF_Ratio, IWM_SPY_Ratio만 갱신
#    추가: QQQ_MA200, QQQ_MA50 등 레짐 판단에 쓰이는 모든 지표 재계산
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
old_inject = """if 'QQQ' in rt_injected:
    df.at[last_index, 'QQQ_DD'] = (df.at[last_index, 'QQQ'] / df['QQQ_High52'].iloc[-1]) - 1
if 'HYG' in rt_injected and 'IEF' in rt_injected:
    df.at[last_index, 'HYG_IEF_Ratio'] = df.at[last_index, 'HYG'] / df.at[last_index, 'IEF']
if 'IWM' in rt_injected and 'SPY' in rt_injected:
    df.at[last_index, 'IWM_SPY_Ratio'] = df.at[last_index, 'IWM'] / df.at[last_index, 'SPY']"""

new_inject = """# ── RT 주입 후 레짐 판단 지표 전체 재계산 ──
if 'QQQ' in rt_injected:
    df['QQQ_MA20']   = df['QQQ'].rolling(20).mean()
    df['QQQ_MA50']   = df['QQQ'].rolling(50).mean()
    df['QQQ_MA200']  = df['QQQ'].rolling(200).mean()
    df['QQQ_High52'] = df['QQQ'].rolling(252).max()
    df['QQQ_DD']     = (df['QQQ'] / df['QQQ_High52']) - 1
    df['QQQ_RSI']    = ta.rsi(df['QQQ'], length=14)
    df['QQQ_20d_Ret']  = df['QQQ'].pct_change(20)
if 'TQQQ' in rt_injected:
    df['TQQQ_MA200'] = df['TQQQ'].rolling(200).mean()
if '^VIX' in rt_injected:
    df['VIX_MA5']  = df['^VIX'].rolling(5).mean()
    df['VIX_MA20'] = df['^VIX'].rolling(20).mean()
    df['VIX_MA50'] = df['^VIX'].rolling(50).mean()
if 'SMH' in rt_injected:
    df['SMH_MA50']  = df['SMH'].rolling(50).mean()
    df['SMH_3M_Ret'] = df['SMH'].pct_change(63)
    df['SMH_1M_Ret'] = df['SMH'].pct_change(21)
    df['SMH_RSI']    = ta.rsi(df['SMH'], length=14)
if 'HYG' in rt_injected or 'IEF' in rt_injected:
    df['HYG_IEF_Ratio'] = df['HYG'] / df['IEF']
    df['HYG_IEF_MA20']  = df['HYG_IEF_Ratio'].rolling(20).mean()
    df['HYG_IEF_MA50']  = df['HYG_IEF_Ratio'].rolling(50).mean()
if 'GLD' in rt_injected or 'SPY' in rt_injected:
    df['GLD_SPY_Ratio'] = df['GLD'] / df['SPY']
    df['GLD_SPY_MA50']  = df['GLD_SPY_Ratio'].rolling(50).mean()
if 'UUP' in rt_injected:
    df['UUP_MA50'] = df['UUP'].rolling(50).mean()
if '^TNX' in rt_injected:
    df['TNX_MA50'] = df['^TNX'].rolling(50).mean()
if 'BTC-USD' in rt_injected:
    df['BTC_MA50'] = df['BTC-USD'].rolling(50).mean()
if 'IWM' in rt_injected or 'SPY' in rt_injected:
    df['IWM_SPY_Ratio'] = df['IWM'] / df['SPY']
    df['IWM_SPY_MA50']  = df['IWM_SPY_Ratio'].rolling(50).mean()
if 'QQQE' in rt_injected:
    df['QQQE_20d_Ret'] = df['QQQE'].pct_change(20)
for sec in SECTOR_TICKERS:
    if sec in rt_injected:
        df[f'{sec}_1M'] = df[sec].pct_change(21)"""

if old_inject in code:
    code = code.replace(old_inject, new_inject); changes += 1
    print("✅ [3] RT 주입 후 전체 지표 재계산 추가")
else:
    print("⚠  [3] RT 주입 블록 패턴 미발견")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. REALTIME_TICKERS에 QQQE 추가 (레짐 판단에 필요)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
old_rt_tickers = "REALTIME_TICKERS = ['QQQ','TQQQ','SMH','^VIX','HYG','IEF','UUP','GLD','SPY','SOXL','USD','QLD','SSO','USDKRW=X', '^TNX', 'BTC-USD', 'IWM']"
new_rt_tickers = "REALTIME_TICKERS = ['QQQ','TQQQ','SMH','^VIX','HYG','IEF','UUP','GLD','SPY','SOXL','USD','QLD','SSO','USDKRW=X','^TNX','BTC-USD','IWM','QQQE']"

if old_rt_tickers in code:
    code = code.replace(old_rt_tickers, new_rt_tickers); changes += 1
    print("✅ [4] REALTIME_TICKERS에 QQQE 추가")
else:
    print("⚠  [4] REALTIME_TICKERS 패턴 미발견")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 저장
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with open(FILE, "w", encoding="utf-8") as f:
    f.write(code)

print(f"\n{'='*50}")
print(f"✅ 총 {changes}곳 수정 완료")
print(f"📦 백업: {FILE}.bak_rt")
print(f"{'='*50}")

if changes < 4:
    print("\n⚠  일부 패턴이 매칭되지 않았습니다.")
    print("   이전 패치가 이미 적용되었거나 코드가 수정된 경우입니다.")
    print("   수동으로 확인해주세요.")
