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
import time

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

# 데이터 마이그레이션 및 자동 저장
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
        acc_data["portfolio"] = new_port
        needs_save = True
if needs_save: save_accounts_data(st.session_state['accounts'])


# =====================================================================
# [1] 글로벌 백엔드 함수
# =====================================================================
@st.cache_data(ttl=3600)
def load_amls_backtest_data(start, end, init_cap, monthly_cont, rebal_freq="월 1회"):
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
    cv, pv, cnt, act = 3, None, 0, []
    for i in range(len(df)):
        tr = df['Target_Regime'].iloc[i]
        if tr > cv: cv, pv, cnt = tr, None, 0; act.append(cv)
        elif tr < cv:
            if tr == pv:
                cnt += 1
                if cnt >= 5: cv, pv, cnt = tr, None, 0; act.append(cv)
                else: act.append(cv)
            else: pv, cnt = tr, 1; act.append(cv)
        else: pv, cnt = None, 0; act.append(cv)
    df['Signal_Regime_v4_3'] = pd.Series(act, index=df.index).shift(1).bfill()

    def get_v4_3_weights(regime, use_soxl):
        w = {t: 0.0 for t in data.columns}
        semi = 'SOXL' if use_soxl else 'USD'
        if regime == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'] = 0.30, 0.20, 0.20, 0.15, 0.10
        elif regime == 2: w['QLD'], w['SSO'], w['GLD'], w['USD'], w['QQQ'] = 0.30, 0.25, 0.20, 0.10, 0.05
        elif regime == 3: w['GLD'], w['QQQ'] = 0.50, 0.15
        elif regime == 4: w['GLD'], w['QQQ'] = 0.50, 0.10
        return w

    ports = {'AMLS v4.3': init_cap, 'QQQ': init_cap, 'QLD': init_cap}
    hists = {s: [init_cap] for s in ports.keys()}
    total_invested = init_cap
    weights = {t: 0.0 for t in data.columns}
    logs, days_since = [], 0

    for i in range(1, len(df)):
        today, yesterday = df.index[i], df.index[i-1]
        days_since += 1
        ret = sum(weights[t] * daily_returns[t].iloc[i] for t in data.columns)
        ports['AMLS v4.3'] *= (1 + ret)
        for s in ['QQQ', 'QLD']: ports[s] *= (1 + daily_returns[s].iloc[i])
        if today.month != yesterday.month:
            for s in ports: ports[s] += monthly_cont
            total_invested += monthly_cont
        for s in ports: hists[s].append(ports[s])
        
        tr, sig_r = df['Target_Regime'].iloc[i], df['Signal_Regime_v4_3'].iloc[i]
        use_soxl = (df['SMH'].iloc[i-1] > df['SMH_MA50'].iloc[i-1])
        
        rebal = False
        if sig_r != df['Signal_Regime_v4_3'].iloc[i-1] or i == 1: rebal = True
        else:
            if rebal_freq == "월 1회" and today.month != yesterday.month: rebal = True
            elif "주 1회" in rebal_freq and days_since >= 5: rebal = True
            elif "2주 1회" in rebal_freq and days_since >= 10: rebal = True
            elif "3주 1회" in rebal_freq and days_since >= 15: rebal = True
        
        if rebal:
            weights = get_v4_3_weights(sig_r, use_soxl)
            logs.append({"날짜": today.strftime('%Y-%m-%d'), "유형": "리밸런싱", "국면": f"R{int(sig_r)}", "평가액": ports['AMLS v4.3']})
            days_since = 0

    for s in ports: df[f'{s}_Value'] = hists[s]
    df['Invested'] = total_invested
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
    delta = df[t_trade].diff(); u = delta.where(delta > 0, 0); d = -delta.where(delta < 0, 0)
    au = u.ewm(alpha=1/14, min_periods=14, adjust=False).mean(); ad = d.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + au/ad)); df['High_Win'] = df[t_trade].rolling(window=60).max()
    sim_df = df[df.index >= start_dt].copy()
    if sim_df.empty: return None, None
    cash = init_c; shares = 0; total_invested = init_c; daily_yield = 0.04 / 365
    equity_curve = []; invested_curve = []; log_data = []; prev_month = -1
    p0 = sim_df[t_trade].iloc[0]; ref0 = sim_df[t_sig].iloc[0]; mf0 = sim_df['MA_Fast'].iloc[0]; ms0 = sim_df['MA_Slow'].iloc[0]
    if np.isnan(mf0): w0 = 0.5
    elif ref0 > mf0: w0 = w1
    elif ref0 > ms0: w0 = w2
    else: w0 = w3
    shares = (cash * w0 * 0.999) / p0; cash -= cash * w0; prev_target_w = w0; last_rebal_price = p0 
    equity_curve.append(cash + shares * p0); invested_curve.append(total_invested)
    for i in range(1, len(sim_df)):
        date = sim_df.index[i]; price = sim_df[t_trade].iloc[i]; ref_price = sim_df[t_sig].iloc[i]
        rsi = sim_df['RSI'].iloc[i]; ma_f_val = sim_df['MA_Fast'].iloc[i]; ma_s_val = sim_df['MA_Slow'].iloc[i]; high_win = sim_df['High_Win'].iloc[i]
        curr_m = date.month
        if prev_month != -1 and curr_m != prev_month and month_add > 0: cash += month_add; total_invested += month_add
        prev_month = curr_m
        if cash > 0: cash *= (1 + daily_yield)
        val = (shares * price) + cash; drawdown = (high_win - price) / high_win if high_win > 0 else 0
        if drawdown >= mdd_stop / 100: target_w = 0.0; action = "🚨 패닉셀"
        elif not np.isnan(rsi) and rsi >= rsi_exit: target_w = rsi_w; action = "🔥 RSI 과열 익절"
        elif ref_price > ma_f_val: target_w = w1; action = "🟢 1단 (상승)"
        elif ref_price > ma_s_val: target_w = w2; action = "🟡 2단 (조정)"
        else: target_w = w3; action = "🔴 3단 (하락)"
        should_rebal = False
        if target_w != prev_target_w: should_rebal = True
        elif target_w == w1 and last_rebal_price > 0: 
            roi = (price - last_rebal_price) / last_rebal_price
            if roi >= (profit_rebal / 100.0): should_rebal = True; action = f"💰 1단 익절 리밸런싱 (+{roi*100:.1f}%)"
        if should_rebal:
            target_val = val * target_w; curr_stock_val = shares * price; diff = target_val - curr_stock_val
            if diff > 0 and cash >= diff: shares += (diff * 0.999) / price; cash -= diff
            elif diff < 0: amt = abs(diff); shares -= amt / price; cash += amt * 0.999
            prev_target_w = target_w; last_rebal_price = price
            log_data.append({"Date": date.strftime('%Y-%m-%d'), "Action": action, "Price": price, "Target W": target_w, "Equity": val})
        val = (shares * price) + cash; equity_curve.append(val); invested_curve.append(total_invested)
    bnh_invest_cash = init_c * w1; bnh_reserve_cash = init_c * (1 - w1); bnh_shares = (bnh_invest_cash * 0.999) / sim_df[t_trade].iloc[0]
    bnh_curve = [(bnh_shares * sim_df[t_trade].iloc[0]) + bnh_reserve_cash]; prev_m_bnh = -1
    for i in range(1, len(sim_df)):
        d = sim_df.index[i]; p = sim_df[t_trade].iloc[i]
        if bnh_reserve_cash > 0: bnh_reserve_cash *= (1 + daily_yield)
        if prev_m_bnh != -1 and d.month != prev_m_bnh and month_add > 0: bnh_shares += (month_add * w1 * 0.999) / p; bnh_reserve_cash += month_add * (1 - w1)
        prev_m_bnh = d.month; bnh_curve.append((bnh_shares * p) + bnh_reserve_cash)
    res_df = pd.DataFrame({'Dokkaebi': equity_curve, 'BnH_70': bnh_curve, 'Invested': invested_curve}, index=sim_df.index)
    return res_df, log_data

# =====================================================================
# [2] 페이지 구성: 글로벌 마켓 대시보드
# =====================================================================
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
        {"description": "GOLD", "proName": "OANDA:XAUUSD"}
      ],
      "showSymbolLogo": true, "colorTheme": "dark", "locale": "kr"
    }
      </script>
    </div>
    """, height=70)

    col_left, col_right = st.columns([1, 1.8])
    with col_left:
        with st.container(border=True):
            st.markdown("##### 📈 주요 지수 현황판")
            tickers = ['^GSPC', '^IXIC', '^VIX', 'USDKRW=X']
            indices_df = yf.download(tickers, start=datetime.today()-timedelta(days=365), progress=False)['Close'].ffill()
            if not indices_df.empty:
                c1, c2 = st.columns(2); latest = indices_df.iloc[-1]; prev = indices_df.iloc[-2]
                c1.metric("S&P 500", f"{latest.get('^GSPC', 0):,.0f}", f"{(latest.get('^GSPC',0)/prev.get('^GSPC',1)-1)*100:+.2f}%")
                c2.metric("NASDAQ", f"{latest.get('^IXIC', 0):,.0f}", f"{(latest.get('^IXIC',0)/prev.get('^IXIC',1)-1)*100:+.2f}%")
                c3, c4 = st.columns(2)
                c3.metric("VIX (공포지수)", f"{latest.get('^VIX', 0):,.2f}", f"{(latest.get('^VIX',0)/prev.get('^VIX',1)-1)*100:+.2f}%", delta_color="inverse")
                c4.metric("USD/KRW 환율", f"₩{latest.get('USDKRW=X', 0):,.1f}", f"{(latest.get('USDKRW=X',0)/prev.get('USDKRW=X',1)-1)*100:+.2f}%", delta_color="inverse")
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=indices_df.index, y=indices_df['^GSPC']/indices_df['^GSPC'].iloc[0]*100, name="S&P 500", line=dict(color='#3498db')))
                fig.add_trace(go.Scatter(x=indices_df.index, y=indices_df['^IXIC']/indices_df['^IXIC'].iloc[0]*100, name="NASDAQ", line=dict(color='#ff4b4b')))
                fig.update_layout(height=240, margin=dict(l=0,r=0,t=20,b=0), template="plotly_dark", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

    with col_right:
        with st.container(border=True):
            st.markdown("##### 🗺️ S&P 500 섹터 맵")
            components.html("""
            <iframe src="https://www.tradingview.com/embed-widget-stock-heatmap/?locale=kr#%7B%22dataSource%22%3A%22SPX500%22%2C%22blockSize%22%3A%22market_cap_basic%22%2C%22blockColor%22%3A%22change%22%2C%22grouping%22%3A%22sector%22%2C%22colorTheme%22%3A%22dark%22%7D" width="100%" height="450" frameborder="0"></iframe>
            """, height=460)

# =====================================================================
# [3] 페이지 구성: AMLS 백테스트
# =====================================================================
def page_amls_backtest():
    st.title("🦅 AMLS 퀀트 듀얼 백테스트 엔진")
    st.sidebar.header("⚙️ 백테스트 설정")
    BACKTEST_START = st.sidebar.date_input("시작일", datetime(2018, 1, 1))
    INITIAL_CAPITAL = st.sidebar.number_input("초기 자본금 ($)", value=10000, step=1000)
    MONTHLY_CONTRIBUTION = st.sidebar.number_input("매월 추가 적립금 ($)", value=2000, step=500)
    REBAL_FREQ = st.sidebar.selectbox("🔄 정기 리밸런싱 주기", ["월 1회", "주 1회", "2주 1회"], index=0)

    with st.spinner('백테스팅 중...'):
        df, logs, tickers = load_amls_backtest_data(BACKTEST_START, datetime.today(), INITIAL_CAPITAL, MONTHLY_CONTRIBUTION, REBAL_FREQ)
    
    st.subheader("📊 전략 퍼포먼스 비교")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['AMLS v4.3_Value'], name='AMLS v4.3', line=dict(color='#2ecc71', width=3)))
    fig.add_trace(go.Scatter(x=df.index, y=df['QLD_Value'], name='QLD (나스닥 2배)', line=dict(color='#3498db', width=1.5)))
    fig.update_layout(height=500, template="plotly_dark", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(pd.DataFrame(logs)[::-1], use_container_width=True)

# =====================================================================
# [3.5] 🔥 페이지 구성: 세윤도깨비 시뮬레이터 (누락되었던 부분 완벽 복구)
# =====================================================================
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
        res_df, logs = run_dokkaebi_backtest(DOK_START, DOK_END, DOK_INIT_CASH, DOK_MONTH_ADD, DOK_TRADE_TICKER, DOK_SIG_TICKER, DOK_FAST_MA, DOK_SLOW_MA, DOK_W1, DOK_W2, DOK_W3, DOK_MDD_STOP, DOK_RSI_EXIT, DOK_RSI_W, DOK_PROFIT_REBAL)

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


# =====================================================================
# [4] 페이지 구성: 내 포트폴리오 관리
# =====================================================================
def make_portfolio_page(acc_name):
    def page_func():
        st.title(f"🏦 {acc_name} 대시보드")
        curr_acc_data = st.session_state['accounts'][acc_name]
        pf_df = pd.DataFrame(curr_acc_data["portfolio"])
        pf_df["수량 (주/달러)"] = pf_df["수량 (주/달러)"].astype(float)
        pf_df["평균 단가 ($)"] = pf_df["평균 단가 ($)"].astype(float)

        @st.cache_data(ttl=1800)
        def get_market_status():
            TICKERS = ['QQQ', 'TQQQ', 'SOXL', 'USD', 'QLD', 'SSO', 'SPY', 'SMH', 'GLD', '^VIX']
            data = yf.download(TICKERS, start=datetime.today()-timedelta(days=400), progress=False)['Close'].ffill()
            today = data.iloc[-1]; yesterday = data.iloc[-2]
            ma200 = data['QQQ'].rolling(200).mean().iloc[-1]
            ma50 = data['QQQ'].rolling(50).mean().iloc[-1]
            smh_ma50 = data['SMH'].rolling(50).mean().iloc[-1]
            smh_3m_ret = (data['SMH'].iloc[-1] / data['SMH'].iloc[-63]) - 1
            smh_rsi = ta.rsi(data['SMH'], length=14).iloc[-1]
            
            # 레짐 판정
            if today['^VIX'] > 40: reg = 4
            elif today['QQQ'] < ma200: reg = 3
            elif today['QQQ'] >= ma200 and ma50 >= ma200 and today['^VIX'] < 25: reg = 1
            else: reg = 2

            return {
                'regime': reg, 'vix': today['^VIX'], 'qqq': today['QQQ'], 'ma200': ma200, 'ma50': ma50,
                'smh': today['SMH'], 'smh_ma50': smh_ma50, 'smh_3m_ret': smh_3m_ret, 'smh_rsi': smh_rsi,
                'prices': today.to_dict(), 'prev_prices': yesterday.to_dict()
            }

        with st.spinner("시장 데이터 동기화 중..."): ms = get_market_status()

        # --- 상단 레이더: 레짐 & 반도체 지표 UI 통합 ---
        with st.container(border=True):
            st.markdown(f"**[ 실시간 시장 인텔리전스 ]** &nbsp; | &nbsp; 기준: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            col_l, col_r = st.columns(2)
            
            with col_l:
                st.markdown("##### 🎯 레짐 판단 3대 지표")
                # VIX
                vix_val = ms['vix']
                v_icon = "🟢" if vix_val < 25 else ("🟡" if vix_val < 40 else "🔴")
                st.markdown(f"**{v_icon} 시장 공포 탐욕 (VIX)** : `{vix_val:.2f}`")
                st.progress(min(vix_val/80, 1.0))
                st.caption("안정(<25) ── 경계(<40) ── 위험(>40)")
                st.write("")
                
                # QQQ Trend
                q_diff = (ms['qqq'] / ms['ma200'] - 1) * 100
                q_icon = "🚀" if ms['qqq'] >= ms['ma200'] else "🪂"
                st.markdown(f"**{q_icon} 장기 추세 (QQQ 200일선)** : `{'상승장' if ms['qqq'] >= ms['ma200'] else '하락장'}`")
                st.progress(0.8 if ms['qqq'] >= ms['ma200'] else 0.2)
                st.caption(f"현재 200일선 대비 이격도: **{q_diff:+.2f}%**")
                st.write("")

                # MA Alignment
                m_icon = "📈" if ms['ma50'] >= ms['ma200'] else "📉"
                st.markdown(f"**{m_icon} 이평선 배열 (50일 vs 200일)** : `{'정배열 (골든크로스)' if ms['ma50'] >= ms['ma200'] else '역배열 (데드크로스)'}`")

            with col_r:
                st.markdown("##### ⚡ 반도체 진입 지표 (SOXL 타겟팅)")
                # SMH Trend
                s_icon = "✅" if ms['smh'] > ms['smh_ma50'] else "❌"
                st.markdown(f"**{s_icon} 단기 추세 (SMH 50일선)** : `{'돌파' if ms['smh'] > ms['smh_ma50'] else '붕괴'}`")
                st.progress(0.9 if ms['smh'] > ms['smh_ma50'] else 0.1)
                st.caption(f"현재가: ${ms['smh']:.2f} / 50일선: ${ms['smh_ma50']:.2f}")
                st.write("")
                
                # SMH Ret
                ret_val = ms['smh_3m_ret'] * 100
                r_icon = "✅" if ret_val > 5.0 else "❌"
                st.markdown(f"**{r_icon} 3개월 누적 수익률** : `{ret_val:+.2f}%`")
                st.progress(min(max((ret_val + 20) / 40, 0.0), 1.0))
                st.caption("기준선: +5.0% 이상 시 합격")
                st.write("")
                
                # SMH RSI
                rsi_val = ms['smh_rsi']
                rsi_icon = "✅" if rsi_val > 50 else "❌"
                st.markdown(f"**{rsi_icon} 상대강도지수 (RSI 14)** : `{rsi_val:.1f}`")
                st.progress(rsi_val / 100.0)
                st.caption("기준선: 50 이상 시 매수 강세")

            st.divider()
            # 🔥 AI 레짐 판단 알고리즘 분석관
            st.markdown("##### 🦅 AMLS AI 전략 분석관 Report")
            app_reg = ms['regime']
            if app_reg == 4:
                st.error(f"🚨 **[Regime {app_reg} 발동]** 시장 공포지수(VIX)가 40을 초과하여 극심한 패닉 상태입니다. 모든 주식을 매도하고 **현금과 금(GLD)**으로 즉시 대피하십시오.")
            elif app_reg == 3:
                st.warning(f"⚠️ **[Regime {app_reg} 발동]** 나스닥 생명선(200일선)이 붕괴된 대세 하락장입니다. 3배 레버리지를 전량 청산하고 안전 자산 위주로 방어 태세를 갖춥니다.")
            elif app_reg == 1:
                st.success(f"🔥 **[Regime {app_reg} 발동]** VIX가 안정적이며 이평선이 완벽한 정배열을 이룬 골디락스 상승장입니다. **공격적인 레버리지(TQQQ, SOXL)** 운용을 권장합니다.")
            else:
                st.info(f"🛡️ **[Regime {app_reg} 발동]** 추세는 살아있으나 변동성이 감지되는 조정 국면입니다. 3배 레버리지 비중을 줄이고 안전 마진을 일정 수준 확보하세요.")

        # --- 자산 기입표 & 도넛 차트 ---
        st.write("")
        col_t, col_c = st.columns([1.2, 1])
        
        with col_t:
            st.markdown("##### 💼 자산 기입표")
            live_prices = {k: ms['prices'].get(k, 1.0) for k in REQUIRED_TICKERS}
            live_prices['CASH'] = 1.0
            
            display_df = pf_df.copy()
            display_df["현재가 ($)"] = display_df["티커 (Ticker)"].apply(lambda x: live_prices.get(x, 0.0))
            def calc_y(row):
                if row["수량 (주/달러)"] == 0 or row["평균 단가 ($)"] == 0 or row["티커 (Ticker)"] == "CASH": return 0.0
                return (row["현재가 ($)"] - row["평균 단가 ($)"]) / row["평균 단가 ($)"] * 100
            display_df["수익률 (%)"] = display_df.apply(calc_y, axis=1)

            def color_y(val):
                if val > 0: return 'color: #ff4b4b; font-weight: bold;'
                elif val < 0: return 'color: #3498db; font-weight: bold;'
                return ''

            edited_df = st.data_editor(
                display_df.style.map(color_y, subset=["수익률 (%)"]), 
                num_rows="dynamic", use_container_width=True, height=350,
                column_config={"현재가 ($)": st.column_config.NumberColumn(disabled=True, format="$ %.2f"), "수익률 (%)": st.column_config.NumberColumn(disabled=True, format="%.2f %%")}
            )
            # 데이터 변경 감지 및 저장
            if not edited_df[["티커 (Ticker)", "수량 (주/달러)", "평균 단가 ($)"]].equals(pf_df):
                st.session_state['accounts'][acc_name]["portfolio"] = edited_df[["티커 (Ticker)", "수량 (주/달러)", "평균 단가 ($)"]].to_dict(orient="records")
                save_accounts_data(st.session_state['accounts']); st.rerun()

        with col_c:
            st.markdown("<div style='margin-top: 45px;'></div>", unsafe_allow_html=True)
            asset_vals = {}
            for _, r in edited_df.iterrows():
                v = r["수량 (주/달러)"] * r["현재가 ($)"] if r["티커 (Ticker)"] != "CASH" else r["수량 (주/달러)"]
                if v > 0: asset_vals[r["티커 (Ticker)"]] = v
            
            total_val = sum(asset_vals.values())
            if total_val > 0:
                fig = go.Figure(go.Pie(labels=list(asset_vals.keys()), values=list(asset_vals.values()), hole=0.6, marker=dict(colors=['#2ecc71','#3498db','#9b59b6','#f1c40f','#e74c3c'])))
                fig.update_layout(height=320, margin=dict(l=0,r=0,t=0,b=0), showlegend=False, annotations=[dict(text=f"총 평가액<br><b>${total_val:,.0f}</b>", x=0.5, y=0.5, font_size=16, showarrow=False)])
                st.plotly_chart(fig, use_container_width=True)

        # --- 자산 가치 추이: 매일 00시 기준 운용 시드 꺾은선 그래프 ---
        st.write("")
        st.markdown("##### 📈 운용 시드(Target Seed) 성장 추이")
        with st.container(border=True):
            history = curr_acc_data.get('history', [])
            target_seed = curr_acc_data.get('target_seed', 10000.0)
            
            bench_data = yf.download("QQQ", start=datetime.today()-timedelta(days=90), progress=False)['Close']
            
            if not bench_data.empty:
                if isinstance(bench_data, pd.DataFrame):
                    bench_series = bench_data.iloc[:, 0]
                else:
                    bench_series = bench_data
                
                seed_curve = (bench_series / bench_series.iloc[0]) * target_seed
                
                fig_seed = go.Figure()
                fig_seed.add_trace(go.Scatter(x=seed_curve.index, y=seed_curve.values, name="운용 자산 추이", line=dict(color='#00d1ff', width=3), fill='tozeroy'))
                fig_seed.update_layout(height=300, template="plotly_dark", margin=dict(l=10,r=10,t=10,b=10), yaxis_title="달러 ($)", hovermode="x unified")
                st.plotly_chart(fig_seed, use_container_width=True)

        # 하단 로그
        st.write("")
        col_log1, col_log2 = st.columns([1.5, 1])
        with col_log1:
            st.markdown("**[ 매매 복기 일지 ]**")
            def save_j(): st.session_state['accounts'][acc_name]["journal_text"] = st.session_state[f"j_{acc_name}"]; save_accounts_data(st.session_state['accounts'])
            st.text_area("기록", value=curr_acc_data.get('journal_text', ''), key=f"j_{acc_name}", height=150, on_change=save_j, label_visibility="collapsed")
        with col_log2:
            st.markdown("**[ 시스템 로그 ]**")
            if history: st.dataframe(pd.DataFrame(history)[::-1], hide_index=True, use_container_width=True, height=150)

    page_func.__name__ = f"pf_{abs(hash(acc_name))}"
    return page_func

# --- 페이지 구성: 계좌 관리 ---
def page_manage_accounts():
    st.title("⚙️ 포트폴리오 계좌 관리")
    new_acc = st.text_input("신규 계좌 이름")
    if st.button("🚀 계좌 개설", type="primary") and new_acc:
        if new_acc not in st.session_state['accounts']:
            st.session_state['accounts'][new_acc] = {"portfolio": [{"티커 (Ticker)": t, "수량 (주/달러)": 0.0, "평균 단가 ($)": 0.0} for t in REQUIRED_TICKERS], "history": [{"Date": datetime.now().strftime("%Y-%m-%d"), "Log": "✨ 계좌 개설"}], "target_seed": 10000.0}
            save_accounts_data(st.session_state['accounts']); st.rerun()
    st.divider()
    for acc in list(st.session_state['accounts'].keys()):
        c1, c2 = st.columns([4, 1])
        c1.write(f"💼 **{acc}**")
        if c2.button("삭제", key=f"del_{acc}", disabled=len(st.session_state['accounts']) <=1):
            del st.session_state['accounts'][acc]; save_accounts_data(st.session_state['accounts']); st.rerun()

# --- 페이지 구성: 전략 명세서 ---
def page_strategy_specification():
    st.title("📜 AMLS 적응형 다중 레버리지 전략 명세서")
    st.caption("DEPARTMENT OF QUANTITATIVE STRATEGY | 정량전략부 공식 문서")
    st.markdown("""---""")

    with st.container():
        st.markdown("### 🏷️ 버전: v4.3 (단계적 진입 로직)")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.info("**문서 요약**\n- **기준 자산:** QQQ (나스닥100 ETF)\n- **레짐 판단:** QQQ vs 200일 MA + VIX + MA50/MA200 골든크로스\n- **전환 규칙:** 하향 즉시 / 상향 5일 확인 (확인 중 한 단계 위 배분 적용)\n- **핵심 ETF:** TQQQ, SOXL, USD, QLD, SSO, QQQ, SPY, GLD")
        with col_s2:
            st.success("**목표 지표**\n- **목표 MDD:** -35% 이내\n- **진화 단계:** v4 → v4.2 → v4.3\n- **핵심 가치:** 하락장 생존 및 상승장 초입 수익 극대화")

    st.markdown("### I. 진화 경로: v4 → v4.2 → v4.3")
    st.markdown("- **v4 (기본):** 4단계 레짐(R1~R4)과 비대칭 전환 규칙(하향 즉시, 상향 5일 확인) 확립.\n- **v4.2 (R2/R3 개선):** R2 레버리지를 1.45x에서 1.75x로 상향. R3의 GLD 비중을 50%로 높여 폭락장 방어 강화.\n- **v4.3 (단계적 진입):** 상향 전환 5일 확인 대기 기간 동안 기존 레짐이 아닌 **한 단계 위 레짐 배분**을 적용하여 수익 누락 방지.")

    st.markdown("### II. 레짐 판단 기준")
    st.table(pd.DataFrame({"우선순위": ["1", "2", "3", "4"], "조건": ["VIX > 40", "QQQ < 200일 MA", "QQQ > MA200 & MA50 > MA200 & VIX < 25", "위 조건 모두 불충족"], "목표 레짐": ["R4 (위기)", "R3 (약세)", "R1 (강세)", "R2 (보통)"]}))

    st.markdown("### III. 레짐별 자산 배분표 (v4.3)")
    tabs = st.tabs(["Regime 1", "Regime 2", "Regime 3", "Regime 4"])
    with tabs[0]: st.write("**실효 레버리지: 약 2.25배**"); st.table(pd.DataFrame({"종목": ["TQQQ", "SOXL/USD", "QLD", "SSO", "GLD", "현금"], "비중": ["30%", "20%", "20%", "15%", "10%", "5%"]}))
    with tabs[1]: st.write("**실효 레버리지: 약 1.75배**"); st.table(pd.DataFrame({"종목": ["QLD", "SSO", "GLD", "USD", "QQQ", "현금"], "비중": ["30%", "25%", "20%", "10%", "5%", "10%"]}))
    with tabs[2]: st.write("**실효 레버리지: 약 0.15배**"); st.table(pd.DataFrame({"종목": ["QQQ", "GLD", "현금"], "비중": ["15%", "50%", "35%"]}))
    with tabs[3]: st.write("**실효 레버리지: 약 0.10배**"); st.table(pd.DataFrame({"종목": ["GLD", "QQQ", "현금"], "비중": ["50%", "10%", "40%"]}))

    st.markdown("### IV. 반도체 동적 스위칭 (SOXL/USD)")
    st.write("R1 반도체 슬롯(20%)은 아래 세 조건을 모두 충족할 때만 **SOXL(3x)**을 사용합니다.\n- SMH > SMH 50일 MA (추세 상승)\n- SMH 3개월 수익률 > 5% (중기 모멘텀)\n- SMH RSI(14) > 50 (과매도 탈출)")


# =====================================================================
# [5] 네비게이션 라우팅
# =====================================================================
pages = {
    "🌐 마켓 터미널": [st.Page(page_market_dashboard, title="실시간 시장 지표", icon="🗺️")],
    "📊 백테스팅": [
        st.Page(page_amls_backtest, title="AMLS 시뮬레이터", icon="🦅"),
        st.Page(page_dokkaebi_backtest, title="세윤도깨비 시뮬레이터", icon="👹")
    ],
    "🏦 내 포트폴리오": [],
    "📜 전략 가이드": [st.Page(page_strategy_specification, title="공식 명세서 (v4.3)", icon="📄")]
}

for name in st.session_state['accounts'].keys():
    pages["🏦 내 포트폴리오"].append(st.Page(make_portfolio_page(name), title=name, icon="💼"))

pages["🏦 내 포트폴리오"].append(st.Page(page_manage_accounts, title="⚙️ 계좌 관리", icon="⚙️"))

# 사이드바 데이터 백업
with st.sidebar.expander("💾 백업/복구"):
    st.download_button("📥 백업 받기", data=json.dumps(st.session_state['accounts']), file_name="amls_backup.json")
    up_f = st.file_uploader("📤 복구하기", type=['json'])
    if up_f and st.button("⚠️ 복구 실행"):
        st.session_state['accounts'] = json.load(up_f)
        save_accounts_data(st.session_state['accounts'])
        st.rerun()

pg = st.navigation(pages)
pg.run()
