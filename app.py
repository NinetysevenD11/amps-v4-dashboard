import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings
import json
import os
import requests
from io import StringIO
import copy

warnings.filterwarnings('ignore')

# =====================================================================
# [0] 시스템 기본 설정 및 데이터 관리
# =====================================================================
st.set_page_config(page_title="AMLS 퀀트 관제탑", layout="wide", initial_sidebar_state="expanded")

ACCOUNTS_FILE = "amls_multi_accounts.json"
REQUIRED_TICKERS = ["TQQQ", "QLD", "QQQ", "SOXL", "USD", "SSO", "GLD", "CASH"]

def load_accounts_data():
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return None
    return None

def save_accounts_data(data_dict):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=4)

if 'accounts' not in st.session_state:
    loaded = load_accounts_data()
    if not loaded:
        loaded = {
            "기본 계좌 (AMLS)": {
                "portfolio": [{"티커 (Ticker)": t, "수량 (주/달러)": 0.0, "평균 단가 ($)": 0.0} for t in REQUIRED_TICKERS],
                "history": [], "first_entry_date": None, "journal_text": "", "target_seed": 10000.0
            }
        }
    st.session_state['accounts'] = loaded

needs_save = False
for acc_name, acc_data in st.session_state['accounts'].items():
    existing_tickers = [item["티커 (Ticker)"] for item in acc_data["portfolio"]]
    missing_tickers = [t for t in REQUIRED_TICKERS if t not in existing_tickers]
    if missing_tickers:
        port_dict = {item["티커 (Ticker)"]: item for item in acc_data["portfolio"]}
        new_port = []
        for req_t in REQUIRED_TICKERS:
            if req_t in port_dict: new_port.append(port_dict[req_t])
            else: new_port.append({"티커 (Ticker)": req_t, "수량 (주/달러)": 0.0, "평균 단가 ($)": 0.0})
        for item in acc_data["portfolio"]:
            if item["티커 (Ticker)"] not in REQUIRED_TICKERS: new_port.append(item)
        acc_data["portfolio"] = new_port
        needs_save = True

if needs_save: save_accounts_data(st.session_state['accounts'])


# =====================================================================
# [1] 글로벌 백엔드 함수
# =====================================================================
@st.cache_data(ttl=3600)
def load_amls_backtest_data(start, end, init_cap, monthly_cont):
    tickers = ['QQQ', 'TQQQ', 'SOXL', 'USD', 'QLD', 'SSO', 'SPY', 'SMH', 'GLD', '^VIX']
    start_str = (start - timedelta(days=400)).strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")
    try: data = yf.download(tickers, start=start_str, end=end_str, progress=False, auto_adjust=True)['Close']
    except: data = yf.download(tickers, start=start_str, end=end_str, progress=False)['Close']
    data = data.ffill().dropna(subset=['QQQ', '^VIX'])

    df = pd.DataFrame(index=data.index)
    for t in data.columns: df[t] = data[t]

    df['QQQ_MA50'] = df['QQQ'].rolling(window=50).mean()
    df['QQQ_MA200'] = df['QQQ'].rolling(window=200).mean()
    df['QQQ_RSI'] = ta.rsi(df['QQQ'], length=14)
    df['SMH_MA50'] = df['SMH'].rolling(window=50).mean()
    df['SMH_3M_Ret'] = df['SMH'].pct_change(periods=63)
    df['SMH_RSI'] = ta.rsi(df['SMH'], length=14)

    df = df.dropna(subset=['QQQ_MA200', 'SMH_RSI']).loc[pd.to_datetime(start):]
    daily_returns = df[data.columns].pct_change().fillna(0)

    def get_target_regime(row):
        vix, qqq, ma200, ma50 = row['^VIX'], row['QQQ'], row['QQQ_MA200'], row['QQQ_MA50']
        if vix > 40: return 4
        if qqq < ma200: return 3
        if qqq >= ma200 and ma50 >= ma200 and vix < 25: return 1
        return 2

    df['Target_Regime'] = df.apply(get_target_regime, axis=1)
    actual_regime_v4 = []; actual_regime_v4_3 = []
    current_v4 = 3; current_v4_3 = 3
    pend_v4 = None; pend_v4_3 = None
    cnt_v4 = 0; cnt_v4_3 = 0

    for i in range(len(df)):
        tr = df['Target_Regime'].iloc[i]
        if tr > current_v4: current_v4 = tr; pend_v4 = None; cnt_v4 = 0; actual_regime_v4.append(current_v4)
        elif tr < current_v4:
            if tr == pend_v4:
                cnt_v4 += 1
                if cnt_v4 >= 5: current_v4 = tr; pend_v4 = None; cnt_v4 = 0; actual_regime_v4.append(current_v4)
                else: actual_regime_v4.append(current_v4)
            else: pend_v4 = tr; cnt_v4 = 1; actual_regime_v4.append(current_v4)
        else: pend_v4 = None; cnt_v4 = 0; actual_regime_v4.append(current_v4)
        
        if tr > current_v4_3: current_v4_3 = tr; pend_v4_3 = None; cnt_v4_3 = 0; actual_regime_v4_3.append(current_v4_3)
        elif tr < current_v4_3: 
            if tr == pend_v4_3:
                cnt_v4_3 += 1
                if cnt_v4_3 >= 5: current_v4_3 = tr; pend_v4_3 = None; cnt_v4_3 = 0; actual_regime_v4_3.append(current_v4_3)
                else: actual_regime_v4_3.append(current_v4_3 - 1)
            else: pend_v4_3 = tr; cnt_v4_3 = 1; actual_regime_v4_3.append(current_v4_3 - 1)
        else: pend_v4_3 = None; cnt_v4_3 = 0; actual_regime_v4_3.append(current_v4_3)

    df['Signal_Regime_v4'] = pd.Series(actual_regime_v4, index=df.index).shift(1).bfill()
    df['Signal_Regime_v4_3'] = pd.Series(actual_regime_v4_3, index=df.index).shift(1).bfill()

    def get_v4_weights(regime, use_soxl):
        w = {t: 0.0 for t in data.columns}
        semi = 'SOXL' if use_soxl else 'USD'
        if regime == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'] = 0.30, 0.20, 0.20, 0.15, 0.10
        elif regime == 2: w['QLD'], w['SSO'], w['GLD'], w['QQQ'], w['USD'] = 0.25, 0.20, 0.20, 0.15, 0.10
        elif regime == 3: w['GLD'], w['QQQ'], w['SPY'] = 0.35, 0.20, 0.10
        elif regime == 4: w['GLD'], w['QQQ'] = 0.50, 0.10
        return w

    def get_v4_3_weights(regime, use_soxl):
        w = {t: 0.0 for t in data.columns}
        semi = 'SOXL' if use_soxl else 'USD'
        if regime == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'] = 0.30, 0.20, 0.20, 0.15, 0.10
        elif regime == 2: w['QLD'], w['SSO'], w['GLD'], w['USD'], w['QQQ'] = 0.30, 0.25, 0.20, 0.10, 0.05
        elif regime == 3: w['GLD'], w['QQQ'] = 0.50, 0.15
        elif regime == 4: w['GLD'], w['QQQ'] = 0.50, 0.10
        return w

    strategies = ['AMLS v4.3', 'AMLS v4', 'QQQ', 'QLD', 'TQQQ']
    ports = {s: init_cap for s in strategies}
    hists = {s: [init_cap] for s in strategies}
    invested_hist = [init_cap]; total_invested = init_cap
    weights_v4 = {t: 0.0 for t in data.columns}; weights_v4_3 = {t: 0.0 for t in data.columns}
    
    logs = []

    for i in range(1, len(df)):
        today, yesterday = df.index[i], df.index[i-1]
        ret_v4 = sum(weights_v4[t] * daily_returns[t].iloc[i] for t in data.columns)
        ret_v4_3 = sum(weights_v4_3[t] * daily_returns[t].iloc[i] for t in data.columns)
        
        ports['AMLS v4'] *= (1 + ret_v4); ports['AMLS v4.3'] *= (1 + ret_v4_3)
        for s in ['QQQ', 'QLD', 'TQQQ']: ports[s] *= (1 + daily_returns[s].iloc[i])

        for t in data.columns:
            if ports['AMLS v4'] > 0: weights_v4[t] = (weights_v4[t] * (1 + daily_returns[t].iloc[i])) / (1 + ret_v4)
            if ports['AMLS v4.3'] > 0: weights_v4_3[t] = (weights_v4_3[t] * (1 + daily_returns[t].iloc[i])) / (1 + ret_v4_3)

        if today.month != yesterday.month:
            for s in strategies: ports[s] += monthly_cont
            total_invested += monthly_cont

        invested_hist.append(total_invested)
        for s in strategies: hists[s].append(ports[s])

        today_reg_v4 = df['Signal_Regime_v4'].iloc[i]; today_reg_v4_3 = df['Signal_Regime_v4_3'].iloc[i]
        use_soxl = (df['SMH'].iloc[i-1] > df['SMH_MA50'].iloc[i-1]) and (df['SMH_3M_Ret'].iloc[i-1] > 0.05) and (df['SMH_RSI'].iloc[i-1] > 50)

        if today.month != yesterday.month or today_reg_v4 != df['Signal_Regime_v4'].iloc[i-1] or i == 1:
            weights_v4 = get_v4_weights(today_reg_v4, use_soxl)
            
        if today.month != yesterday.month or today_reg_v4_3 != df['Signal_Regime_v4_3'].iloc[i-1] or i == 1:
            weights_v4_3 = get_v4_3_weights(today_reg_v4_3, use_soxl)
            log_type = "레짐 전환 (v4.3)" if today_reg_v4_3 != df['Signal_Regime_v4_3'].iloc[i-1] else "월간 정기 (v4.3)"
            semi_target = "SOXL (3x)" if use_soxl and today_reg_v4_3 == 1 else ("USD (2x)" if today_reg_v4_3 in [1, 2] else "-")
            logs.append({"날짜": today.strftime('%Y-%m-%d'), "유형": log_type, "국면": f"Regime {int(today_reg_v4_3)}", "반도체 스위칭": semi_target, "평가액": ports['AMLS v4.3']})

    for s in strategies: df[f'{s}_Value'] = hists[s]
    df['Invested'] = invested_hist
    return df, logs, data.columns

@st.cache_data(ttl=3600)
def run_dokkaebi_backtest(start_d, end_d, init_c, month_add, t_trade, t_sig, ma_f, ma_s, w1, w2, w3, mdd_stop, rsi_exit, rsi_w, profit_rebal):
    start_dt = pd.to_datetime(start_d)
    end_dt = pd.to_datetime(end_d) + pd.Timedelta(days=1)
    warmup_dt = start_dt - pd.DateOffset(months=12)

    tickers = list(set([t_trade, t_sig]))
    data = yf.download(tickers, start=warmup_dt.strftime("%Y-%m-%d"), end=end_dt.strftime("%Y-%m-%d"), progress=False)
    
    if 'Close' in data.columns: df = data['Close'].copy()
    else: df = data.copy()
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    if len(tickers) == 1: df = pd.DataFrame(df); df.columns = tickers

    df = df.dropna()
    if df.empty: return None, None

    df['MA_Fast'] = df[t_sig].rolling(window=ma_f).mean()
    df['MA_Slow'] = df[t_sig].rolling(window=ma_s).mean()

    delta = df[t_trade].diff()
    u = delta.where(delta > 0, 0); d = -delta.where(delta < 0, 0)
    au = u.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    ad = d.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + au/ad))
    df['High_Win'] = df[t_trade].rolling(window=60).max()

    sim_df = df[df.index >= start_dt].copy()
    if sim_df.empty: return None, None

    cash = init_c; shares = 0; total_invested = init_c
    daily_yield = 0.04 / 365
    equity_curve = []; invested_curve = []; log_data = []
    prev_month = -1
    
    p0 = sim_df[t_trade].iloc[0]; ref0 = sim_df[t_sig].iloc[0]
    mf0 = sim_df['MA_Fast'].iloc[0]; ms0 = sim_df['MA_Slow'].iloc[0]

    if np.isnan(mf0): w0 = 0.5
    elif ref0 > mf0: w0 = w1
    elif ref0 > ms0: w0 = w2
    else: w0 = w3

    shares = (cash * w0 * 0.999) / p0
    cash -= cash * w0
    prev_target_w = w0
    last_rebal_price = p0 

    equity_curve.append(cash + shares * p0)
    invested_curve.append(total_invested)

    for i in range(1, len(sim_df)):
        date = sim_df.index[i]; price = sim_df[t_trade].iloc[i]; ref_price = sim_df[t_sig].iloc[i]
        rsi = sim_df['RSI'].iloc[i]; ma_f_val = sim_df['MA_Fast'].iloc[i]; ma_s_val = sim_df['MA_Slow'].iloc[i]
        high_win = sim_df['High_Win'].iloc[i]

        curr_m = date.month
        if prev_month != -1 and curr_m != prev_month and month_add > 0:
            cash += month_add; total_invested += month_add
        prev_month = curr_m

        if cash > 0: cash *= (1 + daily_yield)
        val = (shares * price) + cash
        drawdown = (high_win - price) / high_win if high_win > 0 else 0
        
        if drawdown >= mdd_stop / 100: target_w = 0.0; action = "🚨 패닉셀"
        elif not np.isnan(rsi) and rsi >= rsi_exit: target_w = rsi_w; action = "🔥 RSI 과열 익절"
        elif ref_price > ma_f_val: target_w = w1; action = "🟢 1단 (상승)"
        elif ref_price > ma_s_val: target_w = w2; action = "🟡 2단 (조정)"
        else: target_w = w3; action = "🔴 3단 (하락)"

        should_rebal = False
        if target_w != prev_target_w: should_rebal = True
        elif target_w == w1 and last_rebal_price > 0: 
            roi = (price - last_rebal_price) / last_rebal_price
            if roi >= (profit_rebal / 100.0):
                should_rebal = True; action = f"💰 1단 익절 리밸런싱 (+{roi*100:.1f}%)"

        if should_rebal:
            target_val = val * target_w
            curr_stock_val = shares * price
            diff = target_val - curr_stock_val

            if diff > 0 and cash >= diff: shares += (diff * 0.999) / price; cash -= diff
            elif diff < 0: amt = abs(diff); shares -= amt / price; cash += amt * 0.999
            
            prev_target_w = target_w; last_rebal_price = price
            log_data.append({"Date": date.strftime('%Y-%m-%d'), "Action": action, "Price": price, "Target W": target_w, "Equity": val})

        val = (shares * price) + cash
        equity_curve.append(val)
        invested_curve.append(total_invested)
        
    bnh_invest_cash = init_c * w1; bnh_reserve_cash = init_c * (1 - w1)
    bnh_shares = (bnh_invest_cash * 0.999) / sim_df[t_trade].iloc[0]
    bnh_curve = [(bnh_shares * sim_df[t_trade].iloc[0]) + bnh_reserve_cash]
    
    prev_m_bnh = -1
    for i in range(1, len(sim_df)):
        d = sim_df.index[i]; p = sim_df[t_trade].iloc[i]
        if bnh_reserve_cash > 0: bnh_reserve_cash *= (1 + daily_yield)
        if prev_m_bnh != -1 and d.month != prev_m_bnh and month_add > 0:
            bnh_shares += (month_add * w1 * 0.999) / p; bnh_reserve_cash += month_add * (1 - w1)
        prev_m_bnh = d.month
        bnh_curve.append((bnh_shares * p) + bnh_reserve_cash)

    res_df = pd.DataFrame({'Dokkaebi': equity_curve, 'BnH_70': bnh_curve, 'Invested': invested_curve}, index=sim_df.index)
    return res_df, log_data


# =====================================================================
# [2] 페이지 렌더링 함수 정의
# =====================================================================

# --- 🌐 글로벌 마켓 대시보드 ---
def page_market_dashboard():
    st.title("🌐 글로벌 매크로 & 마켓 터미널")
    
    components.html("""
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>
      {
      "symbols": [
        {"proName": "FOREXCOM:SPXUSD", "title": "S&P 500"},
        {"proName": "FOREXCOM:NSXUSD", "title": "NASDAQ 100"},
        {"description": "TQQQ", "proName": "NASDAQ:TQQQ"},
        {"description": "SOXL", "proName": "ARCA:SOXL"},
        {"description": "USD/KRW", "proName": "FX_IDC:USDKRW"},
        {"description": "GOLD", "proName": "OANDA:XAUUSD"},
        {"description": "BITCOIN", "proName": "BITSTAMP:BTCUSD"}
      ],
      "showSymbolLogo": true,
      "isTransparent": true,
      "displayMode": "adaptive",
      "colorTheme": "dark",
      "locale": "kr"
    }
      </script>
    </div>
    """, height=70)

    col_left, col_right = st.columns([1, 1.8])

    with col_left:
        with st.container(border=True):
            st.markdown("##### 📈 주요 지수 현황판")
            @st.cache_data(ttl=1800)
            def get_market_indices():
                tickers = ['^GSPC', '^IXIC', '^VIX', 'USDKRW=X']
                end_dt = datetime.today()
                start_dt = end_dt - timedelta(days=365)
                return yf.download(tickers, start=start_dt, end=end_dt, progress=False)['Close'].ffill()

            indices_df = get_market_indices()
            if not indices_df.empty:
                c1, c2 = st.columns(2)
                latest = indices_df.iloc[-1]; prev = indices_df.iloc[-2]
                
                c1.metric("S&P 500", f"{latest.get('^GSPC', 0):,.0f}", f"{(latest.get('^GSPC',0)/prev.get('^GSPC',1)-1)*100:+.2f}%")
                c2.metric("NASDAQ", f"{latest.get('^IXIC', 0):,.0f}", f"{(latest.get('^IXIC',0)/prev.get('^IXIC',1)-1)*100:+.2f}%")
                
                c3, c4 = st.columns(2)
                c3.metric("VIX (공포지수)", f"{latest.get('^VIX', 0):,.2f}", f"{(latest.get('^VIX',0)/prev.get('^VIX',1)-1)*100:+.2f}%", delta_color="inverse")
                c4.metric("USD/KRW 환율", f"₩{latest.get('USDKRW=X', 0):,.1f}", f"{(latest.get('USDKRW=X',0)/prev.get('USDKRW=X',1)-1)*100:+.2f}%", delta_color="inverse")

                fig_idx = go.Figure()
                fig_idx.add_trace(go.Scatter(x=indices_df.index, y=indices_df['^GSPC']/indices_df['^GSPC'].iloc[0]*100, name="S&P 500", line=dict(color='#3498db', width=2)))
                fig_idx.add_trace(go.Scatter(x=indices_df.index, y=indices_df['^IXIC']/indices_df['^IXIC'].iloc[0]*100, name="NASDAQ", line=dict(color='#ff4b4b', width=2)))
                fig_idx.update_layout(title="미국 주요 지수 1년 비교 (%)", height=240, margin=dict(l=0, r=0, t=30, b=0), template="plotly_dark", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig_idx, use_container_width=True)

    with col_right:
        with st.container(border=True):
            st.markdown("##### 🗺️ S&P 500 섹터 맵 (Market Heatmap)")
            components.html("""
            <div class="tradingview-widget-container">
              <div class="tradingview-widget-container__widget"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js" async>
              {
              "exchanges": [],
              "dataSource": "SPX500",
              "grouping": "sector",
              "blockSize": "market_cap_basic",
              "blockColor": "change",
              "locale": "kr",
              "symbolUrl": "",
              "colorTheme": "dark",
              "hasTopBar": true,
              "isDataSetEnabled": true,
              "isZoomEnabled": true,
              "hasSymbolTooltip": true,
              "width": "100%",
              "height": "460"
            }
              </script>
            </div>
            """, height=460)

    with st.container(border=True):
        st.markdown("##### 💸 매크로 유동성 분석 (FRED API)")
        @st.cache_data(ttl=86400)
        def fetch_fred_data_with_bypass():
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36', 'Accept': 'text/csv'}
                def get_series(series_id):
                    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
                    res = requests.get(url, headers=headers, timeout=10)
                    if "<html" in res.text[:100].lower():
                        res = requests.get(f"https://api.allorigins.win/raw?url={url}", headers=headers, timeout=15)
                        if "<html" in res.text[:100].lower(): raise ValueError("Cloudflare blocked")
                    return pd.read_csv(StringIO(res.text), parse_dates=['DATE'], index_col='DATE').replace('.', np.nan).astype(float).dropna()

                m2_df = get_series('M2SL')
                fed_df = get_series('WALCL')
                cutoff = datetime.today() - timedelta(days=365 * 5)
                return m2_df[m2_df.index >= cutoff], fed_df[fed_df.index >= cutoff]
            except Exception as e: return None, None

        m2_data, fed_data = fetch_fred_data_with_bypass()
        
        if m2_data is not None and fed_data is not None:
            c_m2, c_fed = st.columns(2)
            with c_m2:
                fig_m2 = go.Figure()
                fig_m2.add_trace(go.Scatter(x=m2_data.index, y=m2_data['M2SL'], fill='tozeroy', line_color='#f1c40f'))
                fig_m2.update_layout(title="M2 통화량 (시중 유동성)", height=220, margin=dict(l=0, r=0, t=30, b=0), template="plotly_dark")
                st.plotly_chart(fig_m2, use_container_width=True)
                
                m2_6m_ago = m2_data['M2SL'].iloc[-7] if len(m2_data) > 6 else m2_data['M2SL'].iloc[0]
                if m2_data['M2SL'].iloc[-1] > m2_6m_ago: st.success("🟢 **최근 6개월 M2 증가 중:** 자산 시장에 돈이 풀리고 있는 긍정적 시그널입니다.")
                else: st.error("🔴 **최근 6개월 M2 감소 중:** 유동성이 축소되어 자산 시장이 압박받을 수 있습니다.")

            with c_fed:
                fig_fed = go.Figure()
                fig_fed.add_trace(go.Scatter(x=fed_data.index, y=fed_data['WALCL'], fill='tozeroy', line_color='#9b59b6'))
                fig_fed.update_layout(title="연준 총 자산 (QE vs QT)", height=220, margin=dict(l=0, r=0, t=30, b=0), template="plotly_dark")
                st.plotly_chart(fig_fed, use_container_width=True)
                
                fed_3m_ago = fed_data['WALCL'].iloc[-13] if len(fed_data) > 13 else fed_data['WALCL'].iloc[0]
                if fed_data['WALCL'].iloc[-1] > fed_3m_ago: st.success("🟢 **대차대조표 확대 (QE):** 연준이 자산을 매입하며 시장을 부양하고 있습니다.")
                else: st.warning("⚠️ **대차대조표 축소 (QT):** 연준이 달러를 흡수하고 있어 변동성 확대 리스크가 있습니다.")
        else:
            st.warning("⚠️ 서버 환경 제약으로 FRED 차트를 아이프레임 우회 모드로 띄웁니다.")
            c_m2, c_fed = st.columns(2)
            with c_m2: components.html('<iframe src="https://fred.stlouisfed.org/graph/graph-landing.php?id=M2SL&width=100%&height=280" width="100%" height="280" frameborder="0" scrolling="no"></iframe>', height=280)
            with c_fed: components.html('<iframe src="https://fred.stlouisfed.org/graph/graph-landing.php?id=WALCL&width=100%&height=280" width="100%" height="280" frameborder="0" scrolling="no"></iframe>', height=280)


# --- 페이지 1: AMLS 백테스트 ---
def page_amls_backtest():
    st.title("🦅 AMLS 퀀트 듀얼 백테스트 엔진")
    st.markdown("**AMLS v4 (기본형)**과 최신 알고리즘이 적용된 **AMLS v4.3 (R2/R3 개선 및 단계적 진입)**의 퍼포먼스를 비교합니다.")

    st.sidebar.header("⚙️ 백테스트 설정")
    BACKTEST_START = st.sidebar.date_input("시작일", datetime(2018, 1, 1))
    BACKTEST_END = st.sidebar.date_input("종료일", datetime.today())
    INITIAL_CAPITAL = st.sidebar.number_input("초기 자본금 ($)", value=10000, step=1000)
    MONTHLY_CONTRIBUTION = st.sidebar.number_input("매월 추가 적립금 ($)", value=2000, step=500)

    with st.spinner('듀얼 퀀트 엔진을 가동하여 시장 데이터를 연산 중입니다...'):
        df, full_logs, tickers = load_amls_backtest_data(BACKTEST_START, BACKTEST_END, INITIAL_CAPITAL, MONTHLY_CONTRIBUTION)
        strategies = ['AMLS v4.3', 'AMLS v4', 'QQQ', 'QLD', 'TQQQ']

    today_status = df.iloc[-1]
    date_str = df.index[-1].strftime('%Y년 %m월 %d일')

    with st.container(border=True):
        st.markdown(f"**[ 실시간 시장 레이더 ]** &nbsp; | &nbsp; 기준일: {date_str} 종가")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("v4.3 적용 국면", f"Regime {int(today_status['Signal_Regime_v4_3'])}")
        m2.metric("v4 (구형) 국면", f"Regime {int(today_status['Signal_Regime_v4'])}")
        m3.metric("공포 지수 (VIX)", f"{today_status['^VIX']:.2f}")
        m4.metric("누적 투입 원금", f"${df['Invested'].iloc[-1]:,.0f}")
        m5.metric("v4.3 최종 자산", f"${df['AMLS v4.3_Value'].iloc[-1]:,.0f}")
        
        st.divider()
        st.markdown("**🔍 나스닥 (QQQ) 기술적 지표**")
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("QQQ 종가", f"${today_status['QQQ']:.2f}")
        q2.metric("50일 이평선 (추세선)", f"${today_status['QQQ_MA50']:.2f}", f"{(today_status['QQQ'] / today_status['QQQ_MA50'] - 1) * 100:.2f}% (이격도)")
        q3.metric("200일 이평선 (생명선)", f"${today_status['QQQ_MA200']:.2f}", f"{(today_status['QQQ'] / today_status['QQQ_MA200'] - 1) * 100:.2f}% (이격도)")
        q4.metric("RSI 14 (과열/침체)", f"{today_status['QQQ_RSI']:.2f}", "70 이상 과열 / 30 이하 침체", delta_color="off")

    st.write("")
    
    st.markdown("**[ 국면별 포트폴리오 목표 비중 (AMLS v4.3 기준) ]**")
    def get_v4_3_weights_for_plot(regime):
        w = {t: 0.0 for t in tickers}
        if regime == 1: w['TQQQ'], w['SOXL/USD'], w['QLD'], w['SSO'], w['GLD'], w['현금'] = 30, 20, 20, 15, 10, 5
        elif regime == 2: w['QLD'], w['SSO'], w['GLD'], w['USD'], w['QQQ'], w['현금'] = 30, 25, 20, 10, 5, 10
        elif regime == 3: w['GLD'], w['현금'], w['QQQ'] = 50, 35, 15
        elif regime == 4: w['GLD'], w['현금'], w['QQQ'] = 50, 40, 10
        return {k: v for k, v in w.items() if v > 0}

    col1, col2, col3, col4 = st.columns(4)
    colors = {'TQQQ': '#e74c3c', 'SOXL/USD': '#8e44ad', 'USD': '#9b59b6', 'QLD': '#e67e22', 'SSO': '#f39c12', 'QQQ': '#3498db', 'SPY': '#2980b9', 'GLD': '#f1c40f', '현금': '#2ecc71'}

    for idx, col in enumerate([col1, col2, col3, col4]):
        reg = idx + 1
        w = get_v4_3_weights_for_plot(reg)
        fig_pie = go.Figure(data=[go.Pie(labels=list(w.keys()), values=list(w.values()), hole=.5, marker=dict(colors=[colors.get(k, '#95a5a6') for k in w.keys()]))])
        fig_pie.update_layout(title_text=f"Regime {reg}", title_x=0.5, margin=dict(t=30, b=0, l=0, r=0), height=250, showlegend=False)
        fig_pie.update_traces(textinfo='label+percent', textposition='inside')
        col.plotly_chart(fig_pie, use_container_width=True)

    st.write("")

    col_met, col_year = st.columns([1, 1])
    with col_met:
        st.markdown("**[ 핵심 지표 비교 ]**")
        def calc_metrics(series, invested):
            final = series.iloc[-1]
            total_ret = (final / invested.iloc[-1]) - 1
            days = (series.index[-1] - series.index[0]).days
            cagr = (final / invested.iloc[-1]) ** (365.25 / days) - 1 if days > 0 else 0
            mdd = ((series / series.cummax()) - 1).min()
            sharpe = (series.pct_change().mean() * 252) / (series.pct_change().std() * np.sqrt(252))
            return [f"{total_ret * 100:.1f}%", f"{cagr * 100:.1f}%", f"{mdd * 100:.1f}%", f"{sharpe:.2f}", f"${final:,.0f}"]

        metrics_rows = [calc_metrics(df[f'{s}_Value'], df['Invested']) for s in strategies]
        metrics_df = pd.DataFrame(metrics_rows, index=strategies, columns=['총 수익률', 'CAGR', 'MDD', '샤프 지수', '최종 자산'])
        st.dataframe(metrics_df.style.highlight_max(subset=['CAGR', '최종 자산'], color='lightgreen').highlight_min(subset=['MDD'], color='lightcoral'), use_container_width=True)

    with col_year:
        st.markdown("**[ 연도별 성과 (수익률 / 기말 자산) ]**")
        years = df.index.year.unique()
        yearly_ret = pd.DataFrame(index=strategies, columns=[str(y) for y in years])
        yearly_val = pd.DataFrame(index=strategies, columns=[str(y) for y in years])
        for y in years:
            for s in strategies:
                y_data = df[df.index.year == y][f'{s}_Value']
                yearly_ret.loc[s, str(y)] = f"{(y_data.iloc[-1] / y_data.iloc[0] - 1) * 100:+.1f}%"
                yearly_val.loc[s, str(y)] = f"${y_data.iloc[-1]:,.0f}"
        tab_ret, tab_val = st.tabs(["📈 수익률 (%)", "💰 기말 자산 ($)"])
        with tab_ret: st.dataframe(yearly_ret, use_container_width=True)
        with tab_val: st.dataframe(yearly_val, use_container_width=True)

    st.write("")
    st.markdown("**[ 자산 성장 및 계좌 낙폭 (Drawdown) ]**")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    line_colors = ['#1abc9c', '#8e44ad', '#3498db', '#f39c12', '#e74c3c']
    for s, c in zip(strategies, line_colors):
        lw = 3 if 'AMLS' in s else 1.5
        fig.add_trace(go.Scatter(x=df.index, y=df[f'{s}_Value'], name=s, line=dict(color=c, width=lw)), row=1, col=1)
        dd = (df[f'{s}_Value'] / df[f'{s}_Value'].cummax()) - 1
        fig.add_trace(go.Scatter(x=df.index, y=dd * 100, name=f'{s} DD', line=dict(color=c, width=1.5 if 'AMLS' in s else 1, dash='solid' if 'AMLS' in s else 'dot')), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Invested'], name='누적 투입 원금', line=dict(color='black', width=2, dash='dash')), row=1, col=1)
    fig.update_yaxes(type="log", row=1, col=1)
    fig.add_hline(y=-20, line_dash="dash", line_color="red", row=2, col=1, annotation_text="-20% 방어선")
    fig.update_layout(height=600, margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)

    col_dist, col_log = st.columns([1, 2])
    with col_dist:
        st.markdown("**[ 레짐 체류 일자 분포 (v4.3 기준) ]**")
        regime_counts = df['Signal_Regime_v4_3'].value_counts().sort_index()
        reg_df = pd.DataFrame({
            "국면": [f"Regime {int(r)}" for r in [1, 2, 3, 4]],
            "일수": [f"{regime_counts.get(r, 0)}일" for r in [1, 2, 3, 4]],
            "비율": [f"{regime_counts.get(r, 0) / len(df) * 100:.1f}%" for r in [1, 2, 3, 4]]
        })
        st.dataframe(reg_df, hide_index=True, use_container_width=True)
        
    with col_log:
        st.markdown("**[ 전체 리밸런싱 매매 이력 (최근순) ]**")
        logs_df = pd.DataFrame(full_logs)[::-1]
        logs_df['평가액'] = logs_df['평가액'].apply(lambda x: f"${x:,.0f}")
        st.dataframe(logs_df, hide_index=True, use_container_width=True, height=200)

# --- 페이지 2: 도깨비 백테스트 ---
def page_dokkaebi_backtest():
    st.title("👹 세윤도깨비 백테스트 시뮬레이터")
    st.markdown("단기/중기 이평선을 활용한 TQQQ 비중 조절(기어 변속) 및 **수익 익절 리밸런싱** 전략입니다.")

    st.sidebar.header("⚙️ 도깨비 기본 설정")
    DOK_START = st.sidebar.date_input("시작일", datetime(2018, 1, 1), key="d_start")
    DOK_END = st.sidebar.date_input("종료일", datetime.today(), key="d_end")
    DOK_INIT_CASH = st.sidebar.number_input("초기 투자금 ($)", value=10000, step=1000, key="d_init")
    DOK_MONTH_ADD = st.sidebar.number_input("월 적립금 ($)", value=0, step=500, key="d_add")
    
    st.sidebar.header("⚙️ 도깨비 기어 변속(Signal)")
    DOK_TRADE_TICKER = st.sidebar.text_input("매매 티커", value="TQQQ").upper()
    DOK_SIG_TICKER = st.sidebar.text_input("신호 티커 (지휘관)", value="QQQ").upper()
    DOK_FAST_MA = st.sidebar.number_input("단기 MA", value=20, step=5)
    DOK_SLOW_MA = st.sidebar.number_input("중기 MA", value=50, step=10)
    
    st.sidebar.markdown("**기어별 매수 비중**")
    DOK_W1 = st.sidebar.slider("1단 (상승장)", 0.0, 1.0, 0.7, 0.1)
    DOK_W2 = st.sidebar.slider("2단 (조정장)", 0.0, 1.0, 0.5, 0.1)
    DOK_W3 = st.sidebar.slider("3단 (하락장)", 0.0, 1.0, 0.0, 0.1)

    st.sidebar.header("🛡️ 안전장치 (Action)")
    DOK_MDD_STOP = st.sidebar.number_input("전고점 대비 손절 (%)", value=20, step=5)
    DOK_RSI_EXIT = st.sidebar.number_input("RSI 익절 기준", value=70, step=5)
    DOK_RSI_W = st.sidebar.slider("RSI 익절 시 남길 비중", 0.0, 1.0, 0.5, 0.1)
    DOK_PROFIT_REBAL = st.sidebar.number_input("1단 수익 리밸런싱 기준 (%)", value=15, step=1)

    with st.spinner("도깨비 엔진 구동 중..."):
        res_df, logs = run_dokkaebi_backtest(
            DOK_START, DOK_END, DOK_INIT_CASH, DOK_MONTH_ADD, DOK_TRADE_TICKER, 
            DOK_SIG_TICKER, DOK_FAST_MA, DOK_SLOW_MA, DOK_W1, DOK_W2, DOK_W3, 
            DOK_MDD_STOP, DOK_RSI_EXIT, DOK_RSI_W, DOK_PROFIT_REBAL
        )

    if res_df is not None:
        final_dok = res_df['Dokkaebi'].iloc[-1]; final_bnh = res_df['BnH_70'].iloc[-1]; total_inv = res_df['Invested'].iloc[-1]
        dok_ret = (final_dok / total_inv - 1) * 100; bnh_ret = (final_bnh / total_inv - 1) * 100
        dok_mdd = (res_df['Dokkaebi'] / res_df['Dokkaebi'].cummax() - 1).min() * 100
        bnh_mdd = (res_df['BnH_70'] / res_df['BnH_70'].cummax() - 1).min() * 100

        st.subheader("📊 도깨비 백테스트 결과 요약")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 투입 원금", f"${total_inv:,.0f}")
        c2.metric("도깨비 최종 자산", f"${final_dok:,.0f}", f"{dok_ret:+.1f}%")
        c3.metric("BnH(70%) 최종 자산", f"${final_bnh:,.0f}", f"{bnh_ret:+.1f}%")
        c4.metric("도깨비 계좌 MDD", f"{dok_mdd:.1f}%", f"BnH MDD: {bnh_mdd:.1f}%", delta_color="inverse")

        if dok_ret < bnh_ret:
            st.warning("⚠️ **진단 리포트:** 잦은 가짜 신호(휩쏘) 또는 과도한 익절/손절 장치 발동으로 인해 도깨비 전략이 단순 거치식(BnH)보다 성과가 낮습니다.")

        st.markdown("**[ 자산 성장 및 계좌 낙폭 (Drawdown) ]**")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
        fig.add_trace(go.Scatter(x=res_df.index, y=res_df['Dokkaebi'], name='Seyun Dokkaebi', line=dict(color='#e74c3c', width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=res_df.index, y=res_df['BnH_70'], name='BnH (70%)', line=dict(color='#3498db', width=1.5, dash='dash')), row=1, col=1)
        fig.add_trace(go.Scatter(x=res_df.index, y=res_df['Invested'], name='원금', line=dict(color='gray', width=1, dash='dot')), row=1, col=1)

        dd_dok = (res_df['Dokkaebi'] / res_df['Dokkaebi'].cummax()) - 1
        dd_bnh = (res_df['BnH_70'] / res_df['BnH_70'].cummax()) - 1
        fig.add_trace(go.Scatter(x=res_df.index, y=dd_dok * 100, name='Dokkaebi DD', line=dict(color='#e74c3c', width=1.5)), row=2, col=1)
        fig.add_trace(go.Scatter(x=res_df.index, y=dd_bnh * 100, name='BnH DD', line=dict(color='#3498db', width=1, dash='dot')), row=2, col=1)

        fig.update_yaxes(type="log", row=1, col=1)
        fig.update_layout(height=600, margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        if logs:
            st.markdown("**[ 기어 변속(리밸런싱) 매매 일지 ]**")
            log_df = pd.DataFrame(logs)[::-1]
            st.dataframe(log_df, hide_index=True, use_container_width=True)

# --- 페이지 3: 계좌 관리 (추가/삭제) ---
def page_manage_accounts():
    st.title("⚙️ 포트폴리오 계좌 관리")
    st.markdown("새로운 계좌를 생성하거나 기존 계좌를 삭제할 수 있습니다.")
    
    st.divider()
    st.subheader("➕ 새 계좌 만들기")
    new_acc_name = st.text_input("새 계좌 이름", placeholder="예: 연금저축펀드, 도깨비 테스트용, 자녀 계좌 등")
    
    if st.button("🚀 계좌 생성하기", type="primary"):
        if new_acc_name and new_acc_name not in st.session_state['accounts']:
            st.session_state['accounts'][new_acc_name] = {
                "portfolio": [{"티커 (Ticker)": t, "수량 (주/달러)": 0.0, "평균 단가 ($)": 0.0} for t in REQUIRED_TICKERS],
                "history": [{"Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Log": "✨ 신규 계좌가 개설되었습니다."}], 
                "first_entry_date": None, "journal_text": "", "target_seed": 10000.0
            }
            save_accounts_data(st.session_state['accounts'])
            st.success(f"'{new_acc_name}' 계좌가 성공적으로 생성되었습니다! 좌측 메뉴에서 확인하세요.")
            st.rerun()
        elif new_acc_name in st.session_state['accounts']:
            st.error("이미 같은 이름의 계좌가 존재합니다. 다른 이름을 입력해주세요.")
            
    st.divider()
    st.subheader("🗑️ 기존 계좌 삭제하기")
    st.warning("계좌를 삭제하면 모든 매매 내역과 일지가 날아갑니다. (앱 보호를 위해 최소 1개의 계좌는 유지해야 합니다.)")
    
    for acc in list(st.session_state['accounts'].keys()):
        col1, col2 = st.columns([4, 1])
        col1.markdown(f"💼 **{acc}**")
        disable_del = len(st.session_state['accounts']) <= 1
        if col2.button("삭제", key=f"del_mgr_{acc}", disabled=disable_del, use_container_width=True):
            del st.session_state['accounts'][acc]
            save_accounts_data(st.session_state['accounts'])
            st.rerun()

# --- 페이지 4: 개별 포트폴리오 관리 (함수 팩토리) ---
def make_portfolio_page(acc_name):
    def page_func():
        st.title(f"🏦 {acc_name} 대시보드")

        curr_acc_data = st.session_state['accounts'][acc_name]
        pf_df = pd.DataFrame(curr_acc_data["portfolio"])
        pf_df["수량 (주/달러)"] = pf_df["수량 (주/달러)"].astype(float)
        pf_df["평균 단가 ($)"] = pf_df["평균 단가 ($)"].astype(float)

        last_pf_key = f'last_pf_{acc_name}'
        if last_pf_key not in st.session_state:
            st.session_state[last_pf_key] = pf_df.copy()

        @st.cache_data(ttl=1800)
        def get_market_regime_v4_3():
            TICKERS = ['QQQ', 'TQQQ', 'SOXL', 'USD', 'QLD', 'SSO', 'SPY', 'SMH', 'GLD', '^VIX']
            end_date = datetime.today()
            start_date = end_date - timedelta(days=400)
            data = yf.download(TICKERS, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)['Close'].ffill()
            df = pd.DataFrame(index=data.index)
            for t in TICKERS: df[t] = data[t]
            
            df['QQQ_MA50'] = df['QQQ'].rolling(50).mean()
            df['QQQ_MA200'] = df['QQQ'].rolling(200).mean()
            df['SMH_MA50'] = df['SMH'].rolling(50).mean()
            df['SMH_3M_Ret'] = df['SMH'].pct_change(63)
            df['SMH_RSI'] = ta.rsi(df['SMH'], length=14)
            df = df.dropna()

            def get_target_regime(row):
                vix, qqq, ma200, ma50 = row['^VIX'], row['QQQ'], row['QQQ_MA200'], row['QQQ_MA50']
                if vix > 40: return 4
                if qqq < ma200: return 3
                if qqq >= ma200 and ma50 >= ma200 and vix < 25: return 1
                return 2
                
            df['Target_Regime'] = df.apply(get_target_regime, axis=1)

            current_v4_3 = 3; pend_v4_3 = None; cnt_v4_3 = 0; actual_regime_v4_3 = []
            for i in range(len(df)):
                tr = df['Target_Regime'].iloc[i]
                if tr > current_v4_3: current_v4_3 = tr; pend_v4_3 = None; cnt_v4_3 = 0; actual_regime_v4_3.append(current_v4_3)
                elif tr < current_v4_3:
                    if tr == pend_v4_3:
                        cnt_v4_3 += 1
                        if cnt_v4_3 >= 5: current_v4_3 = tr; pend_v4_3 = None; cnt_v4_3 = 0; actual_regime_v4_3.append(current_v4_3)
                        else: actual_regime_v4_3.append(current_v4_3 - 1)
                    else: pend_v4_3 = tr; cnt_v4_3 = 1; actual_regime_v4_3.append(current_v4_3 - 1)
                else: pend_v4_3 = None; cnt_v4_3 = 0; actual_regime_v4_3.append(current_v4_3)
                    
            df['Signal_Regime_v4_3'] = pd.Series(actual_regime_v4_3, index=df.index).shift(1).bfill()

            today = df.iloc[-1]; yesterday = df.iloc[-2] 
            today_target = today['Target_Regime']; today_signal = df['Signal_Regime_v4_3'].iloc[-1]
            
            vix, qqq, ma200, ma50 = today['^VIX'], today['QQQ'], today['QQQ_MA200'], today['QQQ_MA50']
            smh, smh_ma50, smh_3m_ret, smh_rsi = today['SMH'], today['SMH_MA50'], today['SMH_3M_Ret'], today['SMH_RSI']

            cond1, cond2, cond3 = smh > smh_ma50, smh_3m_ret > 0.05, smh_rsi > 50
            use_soxl = cond1 and cond2 and cond3

            def get_target_weights_v4_3(regime, use_soxl):
                w = {t: 0.0 for t in TICKERS}
                semi = 'SOXL' if use_soxl else 'USD'
                if regime == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'], w['CASH'] = 0.30, 0.20, 0.20, 0.15, 0.10, 0.05
                elif regime == 2: w['QLD'], w['SSO'], w['GLD'], w['USD'], w['QQQ'], w['CASH'] = 0.30, 0.25, 0.20, 0.10, 0.05, 0.10
                elif regime == 3: w['GLD'], w['CASH'], w['QQQ'] = 0.50, 0.35, 0.15
                elif regime == 4: w['GLD'], w['CASH'], w['QQQ'] = 0.50, 0.40, 0.10
                return {k: v for k, v in w.items() if v > 0}

            target_w = get_target_weights_v4_3(today_signal, use_soxl)
            semi_target = "SOXL (3배)" if use_soxl else "USD (2배)"
            if today_signal in [3, 4]: semi_target = "미보유 (대피)"

            return {
                'target_regime': today_target, 'applied_regime': today_signal, 
                'is_waiting': (today_target < current_v4_3) and pend_v4_3 is not None, 'wait_days': cnt_v4_3, 
                'vix': vix, 'qqq': qqq, 'ma200': ma200, 'ma50': ma50,
                'smh': smh, 'smh_ma50': smh_ma50, 'smh_3m_ret': smh_3m_ret, 'smh_rsi': smh_rsi,
                'cond1': cond1, 'cond2': cond2, 'cond3': cond3,
                'semi_target': semi_target, 'date': today.name, 'target_weights': target_w,
                'latest_prices': {t: today[t] for t in TICKERS if t != '^VIX'},
                'prev_prices': {t: yesterday[t] for t in TICKERS if t != '^VIX'}
            }

        with st.spinner("시장 국면 판독 중..."):
            mr = get_market_regime_v4_3()

        live_prices = mr['latest_prices'].copy()
        live_prices['CASH'] = 1.0
        
        custom_tickers = [str(t).upper().strip() for t in pf_df["티커 (Ticker)"] if str(t).upper().strip() not in live_prices and str(t).upper().strip() != '']
        if custom_tickers:
            try:
                custom_data = yf.download(custom_tickers, period="5d", progress=False)['Close'].ffill()
                for t in custom_tickers:
                    if t in custom_data.columns: live_prices[t] = custom_data[t].iloc[-1]
                    elif isinstance(custom_data, pd.Series): live_prices[t] = custom_data.iloc[-1]
            except: pass

        asset_values = {}; prev_asset_values = {}; total_invested_principal = 0.0 
        for _, row in pf_df.iterrows():
            tkr = str(row.iloc[0]).upper().strip()
            try: shares = float(row.iloc[1]); avg_price = float(row.iloc[2])
            except: shares = 0.0; avg_price = 0.0
                
            if shares > 0:
                if tkr == "CASH":
                    asset_values[tkr] = asset_values.get(tkr, 0) + shares
                    prev_asset_values[tkr] = prev_asset_values.get(tkr, 0) + shares
                    total_invested_principal += shares
                else:
                    curr_price = live_prices.get(tkr, 0.0)
                    prev_price = mr['prev_prices'].get(tkr, curr_price) 
                    if curr_price > 0: asset_values[tkr] = asset_values.get(tkr, 0) + (shares * curr_price)
                    if prev_price > 0: prev_asset_values[tkr] = prev_asset_values.get(tkr, 0) + (shares * prev_price)
                    if avg_price > 0: total_invested_principal += (shares * avg_price)
                    
        total_value = sum(asset_values.values()) if asset_values else 0.0
        prev_total_value = sum(prev_asset_values.values()) if prev_asset_values else 0.0
        today_pnl_amt = total_value - prev_total_value
        today_pnl_pct = (today_pnl_amt / prev_total_value * 100) if prev_total_value > 0 else 0.0

        with st.container(border=True):
            st.markdown(f"**[ 시장 레이더 요약 ]** &nbsp; | &nbsp; 기준일: {mr['date'].strftime('%Y-%m-%d')}")
            r_col1, r_col2, r_col3, r_col4, r_col5 = st.columns(5)
            
            regime_color = "#e74c3c" if mr['applied_regime'] >= 3 else "#2ecc71"
            regime_display = f"Regime {int(mr['applied_regime'])}"
                
            r_col1.markdown(f"현재 국면<br><span style='font-size: 24px; font-weight: bold; color: {regime_color};'>{regime_display}</span>", unsafe_allow_html=True)
            r_col2.metric("공포 지수 (VIX)", f"{mr['vix']:.2f}")
            r_col3.metric("QQQ 200일선 이격도", f"{(mr['qqq'] / mr['ma200'] - 1) * 100:+.2f}%")
            r_col4.markdown(f"반도체 타겟<br><span style='font-size: 20px; font-weight: bold; color: #3498db;'>{mr['semi_target']}</span>", unsafe_allow_html=True)
            r_col5.metric(f"오늘의 계좌 손익", f"${today_pnl_amt:,.0f}", f"{today_pnl_pct:+.2f}%")

            st.divider()
            col_ind1, col_ind2, col_ind3 = st.columns([1, 1, 1])
            with col_ind1:
                fig_vix = go.Figure(go.Indicator(
                    mode = "gauge+number", value = mr['vix'],
                    title = {'text': "시장 공포 탐욕 (VIX)", 'font': {'size': 14}},
                    gauge = {
                        'axis': {'range': [0, 80], 'tickwidth': 1, 'tickcolor': "white"},
                        'bar': {'color': "white", 'thickness': 0.2},
                        'steps': [{'range': [0, 25], 'color': "#2ecc71"}, {'range': [25, 40], 'color': "#f39c12"}, {'range': [40, 80], 'color': "#e74c3c"}],
                    }
                ))
                fig_vix.update_layout(height=180, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_vix, use_container_width=True)

            with col_ind2:
                st.markdown("##### 🎯 레짐 3대 지표")
                if mr['vix'] > 40: st.error(f"**1. VIX:** {mr['vix']:.2f} (>40 위험)", icon="🚨")
                elif mr['vix'] >= 25: st.warning(f"**1. VIX:** {mr['vix']:.2f} (>25 경계)", icon="⚠️")
                else: st.success(f"**1. VIX:** {mr['vix']:.2f} (<25 안정)", icon="✅")
                if mr['qqq'] >= mr['ma200']: st.success(f"**2. 장기추세:** 200일선 위", icon="✅")
                else: st.error(f"**2. 장기추세:** 200일선 아래", icon="🚨")
                if mr['ma50'] >= mr['ma200']: st.success(f"**3. 배열:** 정배열", icon="✅")
                else: st.error(f"**3. 배열:** 역배열", icon="🚨")

            with col_ind3:
                st.markdown("##### ⚡ 반도체 진입 지표")
                if mr['cond1']: st.success("**1. 추세:** SMH > 50일선", icon="✅")
                else: st.error("**1. 추세:** SMH < 50일선", icon="❌")
                if mr['cond2']: st.success(f"**2. 3M수익률:** {mr['smh_3m_ret']*100:.1f}% (>5%)", icon="✅")
                else: st.error(f"**2. 3M수익률:** {mr['smh_3m_ret']*100:.1f}% (<5%)", icon="❌")
                if mr['cond3']: st.success(f"**3. 모멘텀:** RSI {mr['smh_rsi']:.1f} (>50)", icon="✅")
                else: st.error(f"**3. 모멘텀:** RSI {mr['smh_rsi']:.1f} (<50)", icon="❌")

            st.divider()
            st.markdown("##### 🧠 AMLS 레짐 판단 알고리즘 해석")
            target_reg = mr['target_regime']
            app_reg = mr['applied_regime']

            reason = ""
            if target_reg == 4: reason = "시장 공포지수(VIX)가 40을 초과하여 **[극심한 공포 및 폭락장 - Regime 4]** 조건이 발동되었습니다. 즉각적인 대피(GLD 및 현금 100%)가 필요합니다."
            elif target_reg == 3: reason = "나스닥(QQQ)이 생명선인 200일 장기 이평선을 하향 이탈하여 **[대세 하락장 - Regime 3]**으로 판단되었습니다."
            elif target_reg == 1: reason = "VIX가 25 미만으로 안정적이며, 나스닥이 장기(200일) 및 단기(50일) 이평선 위에서 완벽한 정배열을 유지하는 **[안정적 상승장 - Regime 1]**입니다."
            else: reason = "나스닥이 200일선 위에는 있지만, VIX가 25 이상으로 튀었거나 단기 이평선(50일선)이 꺾인 **[불안정한 조정장 - Regime 2]**입니다."

            if mr['is_waiting']:
                st.info(f"{reason} \n\n⏳ **단계적 진입 대기 중:** 현재 시장은 상향 돌파(R{target_reg}) 조건을 충족했으나, 속임수(휩쏘)를 피하기 위해 5일간의 확인 기간을 거치고 있습니다. (현재 {mr['wait_days']}일차 대기 중이며, 임시로 한 단계 아래인 R{app_reg} 비중을 적용합니다.)")
            elif target_reg != app_reg:
                 st.info(f"{reason} \n\n✅ **적용 상태:** 현재 R{app_reg} 비중 모델이 적용 중입니다.")
            else:
                st.info(f"{reason} 현재 포트폴리오에 **R{app_reg} 배분율**이 완벽히 적용되고 있습니다.")

        st.write("")
        col_header1, col_header2 = st.columns([5, 1])
        with col_header1: st.markdown(f"**[ 자산 기입표 및 실시간 수익률 ]**")
        with col_header2:
            if st.button("🔄 숫자 모두 0으로 비우기", use_container_width=True):
                st.session_state['accounts'][acc_name]["portfolio"] = [{"티커 (Ticker)": t, "수량 (주/달러)": 0.0, "평균 단가 ($)": 0.0} for t in REQUIRED_TICKERS]
                st.session_state['accounts'][acc_name]["history"].append({"Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Log": "🔄 시스템: 포트폴리오 전체 초기화됨"})
                st.session_state['accounts'][acc_name]["first_entry_date"] = None
                st.session_state[last_pf_key] = pd.DataFrame(st.session_state['accounts'][acc_name]["portfolio"])
                save_accounts_data(st.session_state['accounts'])
                st.rerun()

        display_df = pf_df.copy()
        display_df["현재가 ($)"] = display_df["티커 (Ticker)"].apply(lambda x: live_prices.get(str(x).upper().strip(), 0.0))
        
        def calc_yield(row):
            if row["수량 (주/달러)"] == 0 or row["평균 단가 ($)"] == 0 or str(row["티커 (Ticker)"]).upper().strip() == "CASH": return 0.0
            return (row["현재가 ($)"] - row["평균 단가 ($)"]) / row["평균 단가 ($)"] * 100
            
        display_df["수익률 (%)"] = display_df.apply(calc_yield, axis=1)

        def color_yield_num(val):
            if isinstance(val, (int, float)):
                if val > 0: return 'color: #ff4b4b; font-weight: bold;'
                elif val < 0: return 'color: #3498db; font-weight: bold;'
            return ''
            
        styled_display_df = display_df.style.map(color_yield_num, subset=["수익률 (%)"])

        col_table, col_chart = st.columns([1.2, 1])
        with col_table:
            st.caption("💡 표 안의 [보유 수량]과 [평균 단가] 셀을 더블 클릭하여 입력하세요. (현재가 및 수익률은 자동 계산됩니다.)")
            edited_display_df = st.data_editor(
                styled_display_df, num_rows="dynamic", key=f"editor_{acc_name}", use_container_width=True, height=350,
                column_config={
                    "티커 (Ticker)": st.column_config.TextColumn("종목 (TICKER)"),
                    "수량 (주/달러)": st.column_config.NumberColumn("보유 수량", min_value=0.0, format="%.2f", step=0.01),
                    "평균 단가 ($)": st.column_config.NumberColumn("평균 단가 ($)", min_value=0.0, format="%.2f", step=0.01),
                    "현재가 ($)": st.column_config.NumberColumn("현재 시장가", disabled=True, format="$ %.2f"),
                    "수익률 (%)": st.column_config.NumberColumn("수익률", disabled=True, format="%.2f %%")
                }
            )

            base_edited_df = edited_display_df[["티커 (Ticker)", "수량 (주/달러)", "평균 단가 ($)"]]

            def get_portfolio_dict(df):
                state = {}
                for _, row in df.iterrows():
                    tkr = str(row["티커 (Ticker)"]).upper().strip()
                    if tkr and tkr.lower() not in ['nan', 'none', '']:
                        try: qty = float(row["수량 (주/달러)"]); avg_p = float(row["평균 단가 ($)"])
                        except: qty = 0.0; avg_p = 0.0
                        state[tkr] = {'qty': qty, 'avg_p': avg_p}
                return state

            old_state = get_portfolio_dict(st.session_state[last_pf_key])
            new_state = get_portfolio_dict(base_edited_df)
            changes_detected = False
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if not base_edited_df.equals(st.session_state[last_pf_key]):
                for tkr, new_val in new_state.items():
                    if tkr in old_state:
                        old_val = old_state[tkr]
                        if old_val['qty'] != new_val['qty']:
                            st.session_state['accounts'][acc_name]["history"].append({"Date": now_str, "Log": f"[{tkr}] 수량 변경: {old_val['qty']} ➔ {new_val['qty']}"})
                            changes_detected = True
                        if old_val['avg_p'] != new_val['avg_p']:
                            st.session_state['accounts'][acc_name]["history"].append({"Date": now_str, "Log": f"[{tkr}] 평단가 변경: ${old_val['avg_p']} ➔ ${new_val['avg_p']}"})
                            changes_detected = True
                    else:
                        st.session_state['accounts'][acc_name]["history"].append({"Date": now_str, "Log": f"[{tkr}] 신규 종목 추가: {new_val['qty']}주"})
                        changes_detected = True
                        if st.session_state['accounts'][acc_name]["first_entry_date"] is None and new_val['qty'] > 0: 
                            st.session_state['accounts'][acc_name]["first_entry_date"] = datetime.now().strftime('%Y-%m-%d')
                
                for tkr in old_state.keys():
                    if tkr not in new_state:
                        st.session_state['accounts'][acc_name]["history"].append({"Date": now_str, "Log": f"[{tkr}] 종목 삭제됨"})
                        changes_detected = True

                if changes_detected:
                    st.session_state['accounts'][acc_name]["portfolio"] = base_edited_df.to_dict(orient="records")
                    st.session_state[last_pf_key] = base_edited_df.copy()
                    save_accounts_data(st.session_state['accounts'])
                    st.rerun()

        with col_chart:
            st.markdown("<br>", unsafe_allow_html=True)
            if total_value > 0:
                fig_donut = go.Figure()
                palette = ['#18bc9c', '#3498db', '#9b59b6', '#e74c3c', '#f39c12', '#f1c40f', '#34495e', '#95a5a6']
                sorted_assets = sorted(asset_values.items(), key=lambda x: x[1], reverse=True)
                
                labels = [tkr for tkr, val in sorted_assets]
                values = [val for tkr, val in sorted_assets]
                
                fig_donut.add_trace(go.Pie(
                    labels=labels, values=values, hole=0.6,
                    textinfo='label+percent', textposition='inside',
                    marker=dict(colors=palette, line=dict(color='#0e1117', width=2)),
                    hovertemplate="<b>%{label}</b><br>$%{value:,.0f} (%{percent})<extra></extra>"
                ))
                
                fig_donut.update_layout(
                    height=300, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
                    annotations=[dict(text=f"총 평가액<br><b><span style='font-size:24px; color:#3498db;'>${total_value:,.0f}</span></b>", x=0.5, y=0.5, font_size=14, showarrow=False)]
                )
                st.plotly_chart(fig_donut, use_container_width=True)

        st.write("")
        st.markdown("**[ 종목별 수익률 & 리밸런싱 액션 지침 ]**")
        col_seed_txt, col_seed_input = st.columns([1.5, 1])
        with col_seed_txt: st.markdown("원하시는 **총 운용 시드(목표 자산)**를 입력하면, 현재 국면 목표 비중에 맞춰 종목별 매수/매도 수량을 정확히 계산해 드립니다.")
        with col_seed_input:
            target_seed = st.number_input("🎯 총 운용 시드 입력 ($)", value=float(curr_acc_data.get("target_seed", 10000.0)), step=1000.0, format="%.2f", label_visibility="collapsed", key=f"seed_{acc_name}")
            if target_seed != curr_acc_data.get("target_seed"):
                st.session_state['accounts'][acc_name]["target_seed"] = target_seed
                save_accounts_data(st.session_state['accounts'])

        status_data = []
        all_tickers = set([t for t in asset_values.keys()] + list(mr['target_weights'].keys()))

        for tkr in all_tickers:
            tkr = tkr.upper()
            my_val = asset_values.get(tkr, 0.0)
            my_weight = (my_val / total_value) * 100 if total_value > 0 else 0.0
            
            shares, avg_price = 0.0, 0.0
            for _, row in pf_df.iterrows():
                if str(row.iloc[0]).upper().strip() == tkr:
                    try: shares += float(row.iloc[1]); avg_price = float(row.iloc[2])
                    except: pass
                    
            target_w_dec = mr['target_weights'].get(tkr, 0.0)
            target_val = target_seed * target_w_dec 
            
            diff_val = target_val - my_val
            curr_price = live_prices.get(tkr, 0.0) if tkr != "CASH" else 1.0
            action_shares_str = f" (약 {abs(diff_val) / curr_price:.1f}주)" if tkr != "CASH" and curr_price > 0 else ""

            if abs(diff_val) < 50: action = "적정 (유지)"
            elif diff_val > 0: action = f"🟢 약 ${diff_val:,.0f} 매수{action_shares_str}"
            else: action = f"🔴 약 ${abs(diff_val):,.0f} 매도{action_shares_str}"

            if shares > 0 and tkr != "CASH":
                if avg_price > 0:
                    ret_pct = ((curr_price - avg_price) / avg_price) * 100
                    ret_amt = (curr_price - avg_price) * shares
                else: ret_pct, ret_amt = 0.0, 0.0
            else: ret_pct, ret_amt = 0.0, 0.0

            if my_val > 0 or target_w_dec > 0:
                status_data.append({
                    "종목": tkr, "목표 비중": f"{target_w_dec*100:.1f}%", "현재 비중": f"{my_weight:.1f}%", 
                    "목표 금액": f"${target_val:,.0f}", "현재 금액": f"${my_val:,.0f}", 
                    "수익률 (%)": f"{ret_pct:+.2f}%" if shares > 0 and tkr != "CASH" else "-",
                    "수익금 ($)": f"${ret_amt:+,.0f}" if shares > 0 and tkr != "CASH" else "-", "리밸런싱 액션": action
                })

        if status_data:
            status_df = pd.DataFrame(status_data).sort_values(by="목표 비중", ascending=False)
            fig_comp = go.Figure(data=[
                go.Bar(name='현재 비중 (Actual)', x=list(status_df['종목']), y=[float(str(x).replace('%','')) for x in status_df['현재 비중']], marker_color='#3498db'),
                go.Bar(name='목표 비중 (Target)', x=list(status_df['종목']), y=[float(str(x).replace('%','')) for x in status_df['목표 비중']], marker_color='#18bc9c')
            ])
            fig_comp.update_layout(barmode='group', height=250, margin=dict(t=30, b=0, l=0, r=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_comp, use_container_width=True)

            def color_status(val):
                val_str = str(val)
                if '매수' in val_str or ('+' in val_str and val_str != '-'): 
                    return 'color: #ff4b4b; font-weight: bold;'
                elif '매도' in val_str or ('-' in val_str and val_str != '-'): 
                    return 'color: #3498db; font-weight: bold;'
                elif '유지' in val_str: 
                    return 'color: #95a5a6;'
                return ''
            
            st.dataframe(status_df.style.map(color_status, subset=['리밸런싱 액션', '수익률 (%)', '수익금 ($)']), hide_index=True, use_container_width=True)

        st.write("")
        st.markdown("**[ 자산 가치 추이 및 성과 추적 (로그 기반) ]**")
        
        if total_value > 0:
            with st.container(border=True):
                fed_str = curr_acc_data.get("first_entry_date")
                # 🔥 에러 픽스: ISO 포맷(T 시간 포함)이든 텍스트 포맷이든 모두 안전하게 처리하는 pd.to_datetime 적용
                if fed_str:
                    default_date = pd.to_datetime(fed_str).date()
                else:
                    default_date = (datetime.today() - timedelta(days=90)).date()
                    
                col_date, _ = st.columns([1, 3])
                with col_date:
                    user_start_date = st.date_input("계좌 매수 시작일", value=default_date, key=f"date_{acc_name}")
                    if str(user_start_date) != str(fed_str)[:10]:
                        st.session_state['accounts'][acc_name]["first_entry_date"] = str(user_start_date)
                        save_accounts_data(st.session_state['accounts'])

                pure_profit = total_value - total_invested_principal
                profit_pct = (pure_profit / total_invested_principal * 100) if total_invested_principal > 0 else 0.0
                
                p_col1, p_col2, p_col3 = st.columns(3)
                p_col1.metric("총 평가액", f"${total_value:,.2f}")
                p_col2.metric("투입 원금 총합", f"${total_invested_principal:,.2f}")
                p_col3.metric("누적 순수익금", f"${pure_profit:+,.2f}", f"{profit_pct:+.2f}%")

                try:
                    history = curr_acc_data.get('history', [])
                    ledger_states = {}
                    current_state = {t: {'qty': 0.0, 'avg_p': 0.0} for t in REQUIRED_TICKERS}
                    ledger_dates = []

                    for record in sorted(history, key=lambda x: x['Date']):
                        date_str = record['Date'].split(' ')[0]
                        log = record['Log']
                        
                        if "초기화됨" in log or "비우기" in log:
                            current_state = {t: {'qty': 0.0, 'avg_p': 0.0} for t in REQUIRED_TICKERS}
                        elif "[" in log and "]" in log:
                            try:
                                tkr = log.split("[")[1].split("]")[0]
                                if tkr not in current_state: current_state[tkr] = {'qty': 0.0, 'avg_p': 0.0}
                                
                                if "수량 변경" in log:
                                    current_state[tkr]['qty'] = float(log.split("➔")[1].strip())
                                elif "평단가 변경" in log:
                                    current_state[tkr]['avg_p'] = float(log.split("➔")[1].replace("$", "").replace(",", "").strip())
                                elif "신규 종목 추가" in log:
                                    current_state[tkr]['qty'] = float(log.split(":")[1].replace("주", "").strip())
                                elif "종목 삭제됨" in log:
                                    current_state[tkr] = {'qty': 0.0, 'avg_p': 0.0}
                            except: pass
                            
                        ledger_states[date_str] = copy.deepcopy(current_state)
                        if date_str not in ledger_dates: ledger_dates.append(date_str)

                    today_str = datetime.today().strftime('%Y-%m-%d')
                    current_pf_state = {}
                    for _, row in pf_df.iterrows():
                        t = str(row.iloc[0]).upper().strip()
                        if t: current_pf_state[t] = {'qty': float(row.iloc[1] if pd.notna(row.iloc[1]) else 0), 'avg_p': float(row.iloc[2] if pd.notna(row.iloc[2]) else 0)}
                    
                    ledger_keys = sorted(ledger_states.keys())
                    if not ledger_keys or current_pf_state != ledger_states[ledger_keys[-1]]:
                        ledger_states[today_str] = current_pf_state
                        if today_str not in ledger_keys: 
                            ledger_keys.append(today_str)
                            ledger_keys.sort()

                    chart_start_ts = pd.Timestamp(user_start_date)
                    fetch_start = (chart_start_ts - timedelta(days=10)).strftime('%Y-%m-%d') 
                    
                    all_tkrs = set()
                    for state in ledger_states.values(): all_tkrs.update(state.keys())
                    all_tkrs.discard('CASH'); all_tkrs.discard('')
                    
                    if all_tkrs:
                        price_df = yf.download(list(all_tkrs), start=fetch_start, progress=False)['Close'].ffill()
                        if isinstance(price_df, pd.Series): price_df = pd.DataFrame({list(all_tkrs)[0]: price_df})
                    else: price_df = pd.DataFrame()

                    benchmark_index = yf.download("QQQ", start=fetch_start, progress=False)['Close'].index
                    portfolio_values = []
                    principal_values = []

                    for dt in benchmark_index:
                        dt_str = dt.strftime('%Y-%m-%d')
                        applicable_state = None
                        for k in ledger_keys:
                            if k <= dt_str: applicable_state = ledger_states[k]
                            else: break
                                
                        if applicable_state is None:
                            portfolio_values.append(0.0)
                            principal_values.append(0.0)
                            continue
                            
                        val = 0.0; prin = 0.0
                        for tkr, data in applicable_state.items():
                            qty = data['qty']; avg_p = data['avg_p']
                            if qty > 0:
                                if tkr == 'CASH': val += qty; prin += qty
                                else:
                                    price = np.nan
                                    if tkr in price_df.columns and dt in price_df.index: price = price_df.at[dt, tkr]
                                    if np.isnan(price): price = avg_p 
                                    val += qty * price
                                    prin += qty * avg_p
                        
                        portfolio_values.append(val)
                        principal_values.append(prin)

                    pf_series = pd.Series(portfolio_values, index=benchmark_index)
                    pr_series = pd.Series(principal_values, index=benchmark_index)

                    pf_series = pf_series[pf_series.index >= chart_start_ts]
                    pr_series = pr_series[pr_series.index >= chart_start_ts]

                    if len(pf_series) > 0 and pf_series.max() > 0:
                        fig_perf = go.Figure()
                        fig_perf.add_trace(go.Scatter(x=pf_series.index, y=pf_series.values, mode='lines', name='총 평가액', line=dict(color='#3498db', width=2), fill='tozeroy', fillcolor='rgba(52, 152, 219, 0.1)'))
                        fig_perf.add_trace(go.Scatter(x=pr_series.index, y=pr_series.values, mode='lines', name='투입 원금', line=dict(color='#e74c3c', width=2, dash='dash')))
                        fig_perf.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="달러 ($)", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                        st.plotly_chart(fig_perf, use_container_width=True)
                    else: st.info("차트를 그릴 수 있는 유효한 자산 내역이 없습니다.")
                except Exception as e: pass

        st.write("")
        col_jnl, col_hist = st.columns([1.5, 1])
        with col_jnl:
            st.markdown("**[ 매매 복기 일지 ]**")
            def save_journal():
                st.session_state['accounts'][acc_name]["journal_text"] = st.session_state[f'jnl_{acc_name}']
                save_accounts_data(st.session_state['accounts'])
            st.text_area("시장 상황 등을 기록하세요.", value=curr_acc_data.get('journal_text', ''), height=200, key=f'jnl_{acc_name}', on_change=save_journal, label_visibility="collapsed")

        with col_hist:
            st.markdown("**[ 시스템 변경 로그 ]**")
            if curr_acc_data.get('history'):
                history_df = pd.DataFrame(curr_acc_data['history'])[::-1]
                st.dataframe(history_df, hide_index=True, use_container_width=True, height=200)
            else: st.info("로그 내역이 없습니다.")

    page_func.__name__ = f"page_pf_{abs(hash(acc_name))}"
    return page_func


# =====================================================================
# [3] 네비게이션 라우팅 (블로그형 카테고리 구성)
# =====================================================================
pages_dict = {
    "🌐 글로벌 마켓 대시보드": [
        st.Page(page_market_dashboard, title="매크로 & 시장 지표", icon="🗺️")
    ]
}

pages_dict["📊 백테스팅 시뮬레이터"] = [
    st.Page(page_amls_backtest, title="AMLS 듀얼 엔진", icon="🦅"),
    st.Page(page_dokkaebi_backtest, title="세윤도깨비 시뮬레이터", icon="👹")
]

pf_pages = []
for acc_name in st.session_state['accounts'].keys():
    pf_pages.append(st.Page(make_portfolio_page(acc_name), title=acc_name, icon="💼"))

pf_pages.append(st.Page(page_manage_accounts, title="⚙️ 계좌 관리 (추가/삭제)", icon="⚙️"))
pages_dict["🏦 내 포트폴리오"] = pf_pages

pg = st.navigation(pages_dict)
pg.run()
