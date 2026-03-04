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
    days_since_rebal_v4 = 0
    days_since_rebal_v4_3 = 0

    for i in range(1, len(df)):
        today, yesterday = df.index[i], df.index[i-1]
        days_since_rebal_v4 += 1
        days_since_rebal_v4_3 += 1
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
        rebal_v4 = False; rebal_v4_3 = False
        
        if today_reg_v4 != df['Signal_Regime_v4'].iloc[i-1] or i == 1: rebal_v4 = True
        else:
            if rebal_freq == "월 1회":
                if today.month != yesterday.month: rebal_v4 = True
            elif rebal_freq == "주 1회 (5거래일)":
                if days_since_rebal_v4 >= 5: rebal_v4 = True
            elif rebal_freq == "2주 1회 (10거래일)":
                if days_since_rebal_v4 >= 10: rebal_v4 = True
            elif rebal_freq == "3주 1회 (15거래일)":
                if days_since_rebal_v4 >= 15: rebal_v4 = True
                
        if today_reg_v4_3 != df['Signal_Regime_v4_3'].iloc[i-1] or i == 1: rebal_v4_3 = True
        else:
            if rebal_freq == "월 1회":
                if today.month != yesterday.month: rebal_v4_3 = True
            elif rebal_freq == "주 1회 (5거래일)":
                if days_since_rebal_v4_3 >= 5: rebal_v4_3 = True
            elif rebal_freq == "2주 1회 (10거래일)":
                if days_since_rebal_v4_3 >= 10: rebal_v4_3 = True
            elif rebal_freq == "3주 1회 (15거래일)":
                if days_since_rebal_v4_3 >= 15: rebal_v4_3 = True
                
        if rebal_v4:
            weights_v4 = get_v4_weights(today_reg_v4, use_soxl)
            days_since_rebal_v4 = 0
            
        if rebal_v4_3:
            weights_v4_3 = get_v4_3_weights(today_reg_v4_3, use_soxl)
            log_type = "🚨 레짐 전환" if today_reg_v4_3 != df['Signal_Regime_v4_3'].iloc[i-1] else f"🔄 정기 ({rebal_freq.split(' ')[0]})"
            semi_target = "SOXL (3x)" if use_soxl and today_reg_v4_3 == 1 else ("USD (2x)" if today_reg_v4_3 in [1, 2] else "-")
            logs.append({"날짜": today.strftime('%Y-%m-%d'), "유형": log_type, "국면": f"Regime {int(today_reg_v4_3)}", "반도체 스위칭": semi_target, "평가액": ports['AMLS v4.3']})
            days_since_rebal_v4_3 = 0

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
# [2] 페이지 렌더링 함수 정의
# =====================================================================

# --- 📜 전략 명세서 (v4.3) ---
def page_strategy_specification():
    st.title("📜 AMLS 적응형 다중 레버리지 전략 명세서")
    st.caption("DEPARTMENT OF QUANTITATIVE STRATEGY | 정량전략부 공식 문서")
    st.markdown("""---""")

    with st.container():
        st.markdown("""
        ### 🏷️ 버전: v4.3 (단계적 진입 로직)
        **v4.2 배분표를 계승하되, 상향 전환 확인 대기 중의 행동을 개선한 명세서** *작성일: 서기 2026년 3월 3일*
        """)
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.info("""
            **문서 요약**
            - **기준 자산:** QQQ (나스닥100 ETF)
            - **레짐 판단:** QQQ vs 200일 MA + VIX + MA50/MA200 골든크로스
            - **전환 규칙:** 하향 즉시 / 상향 5일 확인 (확인 중 한 단계 위 배분 적용)
            - **핵심 ETF:** TQQQ, SOXL, USD, QLD, SSO, QQQ, SPY, GLD
            """)
        with col_s2:
            st.success("""
            **목표 지표**
            - **목표 MDD:** -35% 이내
            - **진화 단계:** v4 → v4.2 → v4.3
            - **핵심 가치:** 하락장 생존 및 상승장 초입 수익 극대화
            """)

    st.markdown("### I. 진화 경로: v4 → v4.2 → v4.3")
    st.markdown("""
    - **v4 (기본):** 4단계 레짐(R1~R4)과 비대칭 전환 규칙(하향 즉시, 상향 5일 확인) 확립.
    - **v4.2 (R2/R3 개선):** R2 레버리지를 1.45x에서 1.75x로 상향하여 완만한 상승장 방어. R3의 GLD 비중을 50%로 높여 폭락장 방어 강화.
    - **v4.3 (단계적 진입):** 상향 전환 5일 확인 대기 기간 동안 기존 레짐이 아닌 **한 단계 위 레짐 배분**을 적용하여 수익 누락 방지.
    """)

    st.markdown("### II. 레짐 판단 기준")
    st.table(pd.DataFrame({
        "우선순위": ["1", "2", "3", "4"],
        "조건": ["VIX > 40", "QQQ < 200일 MA", "QQQ > MA200 & MA50 > MA200 & VIX < 25", "위 조건 모두 불충족"],
        "목표 레짐": ["R4 (위기)", "R3 (약세)", "R1 (강세)", "R2 (보통)"],
        "의미": ["시장 패닉 상태", "장기 추세 이탈", "추세 강세 (골든크로스)", "전환 구간 또는 약한 강세"]
    }))

    st.markdown("### III. 레짐별 자산 배분표 (v4.3)")
    tabs = st.tabs(["Regime 1 (강세)", "Regime 2 (보통)", "Regime 3 (약세)", "Regime 4 (위기)"])
    
    with tabs[0]:
        st.write("**실효 레버리지: 약 2.25배**")
        st.table(pd.DataFrame({"종목": ["TQQQ", "SOXL/USD", "QLD", "SSO", "GLD", "현금"], "비중": ["30%", "20%", "20%", "15%", "10%", "5%"]}))
    with tabs[1]:
        st.write("**실효 레버리지: 약 1.75배**")
        st.table(pd.DataFrame({"종목": ["QLD", "SSO", "GLD", "USD", "QQQ", "현금"], "비중": ["30%", "25%", "20%", "10%", "5%", "10%"]}))
    with tabs[2]:
        st.write("**실효 레버리지: 약 0.15배**")
        st.table(pd.DataFrame({"종목": ["QQQ", "GLD", "현금"], "비중": ["15%", "50%", "35%"]}))
    with tabs[3]:
        st.write("**실효 레버리지: 약 0.10배**")
        st.table(pd.DataFrame({"종목": ["GLD", "QQQ", "현금"], "비중": ["50%", "10%", "40%"]}))

    st.markdown("### IV. v4.3 핵심 변경: 단계적 진입 로직")
    st.markdown("""
    | 상황 | v4.2 (기존) | v4.3 (변경) |
    | :--- | :--- | :--- |
    | **R3→R1 감지 시 (5일 대기)** | R3 유지 (0.15x) | **R2 적용 (1.75x)** |
    | **R3→R2 감지 시 (5일 대기)** | R3 유지 (0.15x) | **R2 적용 (1.75x)** |
    | **R2→R1 감지 시 (5일 대기)** | R2 유지 (1.75x) | **R1 적용 (2.25x)** |
    | **R4→R3 감지 시 (5일 대기)** | R4 유지 (0.10x) | **R3 적용 (0.15x)** |
    """)

    st.markdown("### V. 반도체 동적 스위칭 (SOXL/USD)")
    st.write("R1 반도체 슬롯(20%)은 아래 세 조건을 모두 충족할 때만 **SOXL(3x)**을 사용합니다.")
    st.markdown("- SMH > SMH 50일 MA (추세 상승)\n- SMH 3개월 수익률 > 5% (중기 모멘텀)\n- SMH RSI(14) > 50 (과매도 탈출)")

    st.markdown("### 📎 부록")
    with st.expander("부록 A. 무한매수법 진입 타이밍에 대한 고찰"):
        st.write("""
        무한매수법의 핵심은 연간 회전수입니다. 고점에서 진입 시 사이클 종료까지 시간이 오래 걸려 수익률이 저하됩니다.
        **AMLS R3(약세)에서 R2(보통)로 전환되는 시점**이 가장 이상적인 무한매수법 진입 타이밍으로 간주됩니다.
        """)
    with st.expander("부록 B. 와인스타인 30주 MA 방법론"):
        st.write("""
        AMLS의 200일 MA(약 40주) 판단은 고전적인 와인스타인 30주 MA 방법론의 현대적 보완판입니다.
        Stage 4(하락)에서 Stage 1(축적)로 넘어가는 구간의 변동성을 VIX와 단계적 진입 로직으로 제어합니다.
        """)

# --- 🌐 글로벌 마켓 대시보드 ---
def page_market_dashboard():
    st.title("🌐 글로벌 매크로 & 마켓 터미널")
    
    # 1. Ticker Tape
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
              "exchanges": [], "dataSource": "SPX500", "grouping": "sector", "blockSize": "market_cap_basic", "blockColor": "change", "locale": "kr", "symbolUrl": "", "colorTheme": "dark", "hasTopBar": true, "isDataSetEnabled": true, "isZoomEnabled": true, "hasSymbolTooltip": true, "width": "100%", "height": "460"
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


# --- 📊 백테스트: AMLS ---
def page_amls_backtest():
    st.title("🦅 AMLS 퀀트 듀얼 백테스트 엔진")
    st.markdown("**AMLS v4 (기본형)**과 최신 알고리즘이 적용된 **AMLS v4.3 (R2/R3 개선 및 단계적 진입)**의 퍼포먼스를 비교합니다.")

    st.sidebar.header("⚙️ 백테스트 설정")
    BACKTEST_START = st.sidebar.date_input("시작일", datetime(2018, 1, 1))
    BACKTEST_END = st.sidebar.date_input("종료일", datetime.today())
    INITIAL_CAPITAL = st.sidebar.number_input("초기 자본금 ($)", value=10000, step=1000)
    MONTHLY_CONTRIBUTION = st.sidebar.number_input("매월 추가 적립금 ($)", value=2000, step=500)
    REBAL_FREQ = st.sidebar.selectbox("🔄 정기 리밸런싱 주기 (v4.3 적용)", ["월 1회", "주 1회 (5거래일)", "2주 1회 (10거래일)", "3주 1회 (15거래일)"], index=0)

    with st.spinner('듀얼 퀀트 엔진을 가동하여 시장 데이터를 연산 중입니다...'):
        df, full_logs, tickers = load_amls_backtest_data(BACKTEST_START, BACKTEST_END, INITIAL_CAPITAL, MONTHLY_CONTRIBUTION, REBAL_FREQ)
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
        st.markdown(f"**[ 전체 리밸런싱 매매 이력 ({REBAL_FREQ}) ]**")
        logs_df = pd.DataFrame(full_logs)[::-1]
        if not logs_df.empty: 
            logs_df['평가액'] = logs_df['평가액'].apply(lambda x: f"${x:,.0f}")
            st.dataframe(logs_df, hide_index=True, use_container_width=True, height=200)

# --- 📊 백테스트: 도깨비 ---
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


# --- 💼 포트폴리오 관리 (AI 분석관 & 지표 UI 통일 & 시드 곡선) ---
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
                if tr > current_v4_3: 
                    current_v4_3 = tr; pend_v4_3 = None; cnt_v4_3 = 0; actual_regime_v4_3.append(current_v4_3)
                elif tr < current_v4_3:
                    if tr == pend_v4_3:
                        cnt_v4_3 += 1
                        if cnt_v4_3 >= 5: current_v4_3 = tr; pend_v4_3 = None; cnt_v4_3 = 0; actual_regime_v4_3.append(current_v4_3)
                        else: actual_regime_v4_3.append(current_v4_3 - 1)
                    else: 
                        pend_v4_3 = tr; cnt_v4_3 = 1; actual_regime_v4_3.append(current_v4_3 - 1)
                else: 
                    pend_v4_3 = None; cnt_v4_3 = 0; actual_regime_v4_3.append(current_v4_3)
                    
            df['Signal_Regime_v4_3'] = pd.Series(actual_regime_v4_3, index=df.index).shift(1).bfill()
            today = df.iloc[-1]; yesterday = df.iloc[-2]; ts = df['Signal_Regime_v4_3'].iloc[-1]
            cond1, cond2, cond3 = today['SMH'] > today['SMH_MA50'], today['SMH_3M_Ret'] > 0.05, today['SMH_RSI'] > 50
            use_soxl = cond1 and cond2 and cond3

            def get_w(reg, usx):
                w = {t: 0.0 for t in TICKERS}
                semi = 'SOXL' if usx else 'USD'
                if reg == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'], w['CASH'] = 0.30, 0.20, 0.20, 0.15, 0.10, 0.05
                elif reg == 2: w['QLD'], w['SSO'], w['GLD'], w['USD'], w['QQQ'], w['CASH'] = 0.30, 0.25, 0.20, 0.10, 0.05, 0.10
                elif reg == 3: w['GLD'], w['CASH'], w['QQQ'] = 0.50, 0.35, 0.15
                elif reg == 4: w['GLD'], w['CASH'], w['QQQ'] = 0.50, 0.40, 0.10
                return {k: v for k, v in w.items() if v > 0}
                
            return {
                'target_regime': today['Target_Regime'], 'applied_regime': ts, 
                'is_waiting': (today['Target_Regime'] < current_v4_3) and pend_v4_3 is not None, 
                'wait_days': cnt_v4_3, 'vix': today['^VIX'], 'qqq': today['QQQ'], 
                'ma200': today['QQQ_MA200'], 'ma50': today['QQQ_MA50'], 
                'smh_rsi': today['SMH_RSI'], 'smh_3m_ret': today['SMH_3M_Ret'], 
                'cond1': cond1, 'cond2': cond2, 'cond3': cond3, 
                'semi_target': "SOXL (3배)" if use_soxl else "USD (2배)", 
                'date': today.name, 'target_weights': get_w(ts, use_soxl), 
                'latest_prices': {t: today[t] for t in TICKERS if t != '^VIX'}, 
                'prev_prices': {t: yesterday[t] for t in TICKERS if t != '^VIX'}
            }

        with st.spinner("시장 국면 판독 중..."): 
            mr = get_market_regime_v4_3()
            
        live_prices = mr['latest_prices'].copy(); live_prices['CASH'] = 1.0
        custom_tkrs = [str(t).upper().strip() for t in pf_df["티커 (Ticker)"] if str(t).upper().strip() not in live_prices and str(t).upper().strip() != '']
        if custom_tkrs:
            try:
                c_data = yf.download(custom_tkrs, period="5d", progress=False)['Close'].ffill()
                for t in custom_tkrs:
                    if t in c_data.columns: live_prices[t] = c_data[t].iloc[-1]
                    elif isinstance(c_data, pd.Series): live_prices[t] = c_data.iloc[-1]
            except: pass
            
        asset_vals, prev_vals, total_prin = {}, {}, 0.0
        for _, row in pf_df.iterrows():
            tkr = str(row.iloc[0]).upper().strip()
            try: shares, avg_p = float(row.iloc[1]), float(row.iloc[2])
            except: shares, avg_p = 0.0, 0.0
            if shares > 0:
                if tkr == "CASH": 
                    asset_vals[tkr] = asset_vals.get(tkr, 0) + shares
                    prev_vals[tkr] = prev_vals.get(tkr, 0) + shares
                    total_prin += shares
                else:
                    curr_p = live_prices.get(tkr, 0.0)
                    prev_p = mr['prev_prices'].get(tkr, curr_p)
                    if curr_p > 0: asset_vals[tkr] = asset_vals.get(tkr, 0) + (shares * curr_p)
                    if prev_p > 0: prev_vals[tkr] = prev_vals.get(tkr, 0) + (shares * prev_p)
                    if avg_p > 0: total_prin += (shares * avg_p)
                    
        total_val = sum(asset_vals.values()) if asset_vals else 0.0
        prev_total = sum(prev_vals.values()) if prev_vals else 0.0
        pnl_amt = total_val - prev_total
        pnl_pct = (pnl_amt / prev_total * 100) if prev_total > 0 else 0.0

        # --- 상단 레이더: AI 분석관 & 지표 UI 통합 ---
        with st.container(border=True):
            st.markdown(f"**[ 실시간 시장 인텔리전스 ]** &nbsp; | &nbsp; 기준: {mr['date'].strftime('%Y-%m-%d')}")
            col_l, col_r = st.columns(2)
            
            with col_l:
                st.markdown("##### 🎯 레짐 판단 3대 지표")
                if mr['vix'] > 40: st.error(f"**VIX:** {mr['vix']:.2f} (>40 위험)", icon="🚨")
                elif mr['vix'] >= 25: st.warning(f"**VIX:** {mr['vix']:.2f} (>25 경계)", icon="⚠️")
                else: st.success(f"**VIX:** {mr['vix']:.2f} (<25 안정)", icon="✅")
                
                if mr['qqq'] >= mr['ma200']: st.success(f"**장기추세:** 200일선 위 (안전)", icon="✅")
                else: st.error(f"**장기추세:** 200일선 아래 (위험)", icon="🚨")
                
                if mr['ma50'] >= mr['ma200']: st.success(f"**배열:** 정배열 (상승 추세)", icon="✅")
                else: st.error(f"**배열:** 역배열 (하락 추세)", icon="🚨")

            with col_r:
                st.markdown("##### ⚡ 반도체 진입 지표 (SOXL 판단)")
                if mr['cond1']: st.success("**추세:** SMH > 50일선", icon="✅")
                else: st.error("**추세:** SMH < 50일선", icon="❌")
                
                if mr['cond2']: st.success(f"**수익률:** {mr['smh_3m_ret']*100:.1f}% (>5% 우수)", icon="✅")
                else: st.error(f"**수익률:** {mr['smh_3m_ret']*100:.1f}% (<5% 부진)", icon="❌")
                
                if mr['cond3']: st.success(f"**모멘텀:** RSI {mr['smh_rsi']:.1f} (>50 강세)", icon="✅")
                else: st.error(f"**모멘텀:** RSI {mr['smh_rsi']:.1f} (<50 약세)", icon="❌")

            st.divider()
            
            # 🔥 AI 레짐 판단 알고리즘 분석관
            st.markdown("##### 🦅 AMLS 전략 분석 보고서")
            target_reg = mr['target_regime']
            app_reg = mr['applied_regime']

            if target_reg == 4: reason = "시장 공포지수(VIX)가 40을 초과하여 **[극심한 공포 및 폭락장 - Regime 4]** 조건이 발동되었습니다. 즉각적인 대피(GLD 및 현금 100%)가 필요합니다."
            elif target_reg == 3: reason = "나스닥(QQQ)이 생명선인 200일 장기 이평선을 하향 이탈하여 **[대세 하락장 - Regime 3]**으로 판단되었습니다. 3배 레버리지를 모두 청산하고 방어 태세를 갖춥니다."
            elif target_reg == 1: reason = "VIX가 25 미만으로 안정적이며, 나스닥이 장기(200일) 및 단기(50일) 이평선 위에서 완벽한 정배열을 유지하는 **[안정적 상승장 - Regime 1]**입니다. 공격적인 레버리지 운용 구간입니다."
            else: reason = "나스닥이 200일선 위에는 있지만, VIX가 25 이상으로 튀었거나 단기 이평선(50일선)이 꺾인 **[불안정한 조정장 - Regime 2]**입니다. 레버리지 비중을 낮춰 안전 마진을 확보해야 합니다."

            if mr['is_waiting']:
                st.warning(f"**[AI 판독 결과]** {reason} \n\n⏳ **단계적 진입 대기 중:** 현재 시장은 상향 돌파(R{target_reg}) 조건을 충족했으나, 속임수(휩쏘)를 피하기 위해 5일간의 확인 기간을 거치고 있습니다. (현재 {mr['wait_days']}일차 대기 중이며, 보수적으로 R{app_reg} 비중을 적용합니다.)")
            elif target_reg != app_reg:
                 st.info(f"**[AI 판독 결과]** {reason} \n\n✅ **현재 포트폴리오 적용 상태:** 안전 확인이 완료되어 R{app_reg} 비중 모델이 적용 중입니다.")
            else:
                st.success(f"**[AI 판독 결과]** {reason} 시스템 지표가 일치하여 현재 포트폴리오에 **Regime {app_reg} 배분율**이 완벽히 적용되고 있습니다. 반도체 타겟은 **{mr['semi_target']}** 입니다.")

        # --- 자산 기입표 & 도넛 차트 ---
        st.write("")
        c_h1, c_h2 = st.columns([5, 1])
        with c_h1: st.markdown(f"**[ 자산 기입표 및 실시간 수익률 ]**")
        with c_h2:
            if st.button("🔄 리셋", use_container_width=True):
                st.session_state['accounts'][acc_name]["portfolio"] = [{"티커 (Ticker)": t, "수량 (주/달러)": 0.0, "평균 단가 ($)": 0.0} for t in REQUIRED_TICKERS]
                st.session_state['accounts'][acc_name]["history"].append({"Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Log": "🔄 시스템: 초기화됨"})
                st.session_state[last_pf_key] = pd.DataFrame(st.session_state['accounts'][acc_name]["portfolio"])
                save_accounts_data(st.session_state['accounts']); st.rerun()

        disp_df = pf_df.copy()
        disp_df["현재가 ($)"] = disp_df["티커 (Ticker)"].apply(lambda x: live_prices.get(str(x).upper().strip(), 0.0))
        def cy(row):
            if row["수량 (주/달러)"] == 0 or row["평균 단가 ($)"] == 0 or str(row["티커 (Ticker)"]).upper().strip() == "CASH": return 0.0
            return (row["현재가 ($)"] - row["평균 단가 ($)"]) / row["평균 단가 ($)"] * 100
        disp_df["수익률 (%)"] = disp_df.apply(cy, axis=1)
        
        def c_y_n(val):
            if isinstance(val, (int, float)):
                if val > 0: return 'color: #ff4b4b; font-weight: bold;'
                elif val < 0: return 'color: #3498db; font-weight: bold;'
            return ''

        c_t, c_c = st.columns([1.2, 1])
        with c_t:
            st.caption("💡 보유 수량과 평단가를 더블 클릭하여 입력하세요. (현재가, 수익률은 자동 계산됩니다)")
            ed_disp = st.data_editor(
                disp_df.style.map(c_y_n, subset=["수익률 (%)"]), 
                num_rows="dynamic", key=f"editor_{acc_name}", use_container_width=True, height=350, 
                column_config={"현재가 ($)": st.column_config.NumberColumn(disabled=True, format="$ %.2f"), "수익률 (%)": st.column_config.NumberColumn(disabled=True, format="%.2f %%")}
            )
            base_ed = ed_disp[["티커 (Ticker)", "수량 (주/달러)", "평균 단가 ($)"]]
            if not base_ed.equals(st.session_state[last_pf_key]):
                now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                old_state = {str(r["티커 (Ticker)"]).upper().strip(): {'qty': float(r["수량 (주/달러)"] if pd.notna(r["수량 (주/달러)"]) else 0), 'avg_p': float(r["평균 단가 ($)"] if pd.notna(r["평균 단가 ($)"]) else 0)} for _, r in st.session_state[last_pf_key].iterrows() if str(r["티커 (Ticker)"]).upper().strip()}
                new_state = {str(r["티커 (Ticker)"]).upper().strip(): {'qty': float(r["수량 (주/달러)"] if pd.notna(r["수량 (주/달러)"]) else 0), 'avg_p': float(r["평균 단가 ($)"] if pd.notna(r["평균 단가 ($)"]) else 0)} for _, r in base_ed.iterrows() if str(r["티커 (Ticker)"]).upper().strip()}
                for tkr, new_val in new_state.items():
                    if tkr in old_state:
                        if old_state[tkr]['qty'] != new_val['qty']: st.session_state['accounts'][acc_name]["history"].append({"Date": now_s, "Log": f"[{tkr}] 수량 변경: {old_state[tkr]['qty']} ➔ {new_val['qty']}"})
                        if old_state[tkr]['avg_p'] != new_val['avg_p']: st.session_state['accounts'][acc_name]["history"].append({"Date": now_s, "Log": f"[{tkr}] 평단가 변경: ${old_state[tkr]['avg_p']} ➔ ${new_val['avg_p']}"})
                    else: st.session_state['accounts'][acc_name]["history"].append({"Date": now_s, "Log": f"[{tkr}] 신규 종목 추가: {new_val['qty']}주"})
                for tkr in old_state.keys():
                    if tkr not in new_state: st.session_state['accounts'][acc_name]["history"].append({"Date": now_s, "Log": f"[{tkr}] 종목 삭제됨"})
                st.session_state['accounts'][acc_name]["portfolio"] = base_ed.to_dict(orient="records")
                st.session_state[last_pf_key] = base_ed.copy(); save_accounts_data(st.session_state['accounts']); st.rerun()

        with c_c:
            st.markdown("<br>", unsafe_allow_html=True)
            if total_val > 0:
                s_a = sorted(asset_vals.items(), key=lambda x: x[1], reverse=True)
                fig_d = go.Figure(go.Pie(labels=[x[0] for x in s_a], values=[x[1] for x in s_a], hole=0.6, textinfo='label+percent', textposition='inside', marker=dict(colors=['#18bc9c', '#3498db', '#9b59b6', '#e74c3c', '#f39c12', '#f1c40f', '#34495e', '#95a5a6'], line=dict(color='#0e1117', width=2))))
                fig_d.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), showlegend=False, annotations=[dict(text=f"총 평가액<br><b><span style='font-size:24px; color:#3498db;'>${total_val:,.0f}</span></b>", x=0.5, y=0.5, font_size=14, showarrow=False)])
                st.plotly_chart(fig_d, use_container_width=True)

        st.write("")
        st.markdown("**[ 리밸런싱 액션 지침 ]**")
        target_seed = st.number_input("🎯 총 운용 시드 입력 ($)", value=float(curr_acc_data.get("target_seed", 10000.0)), step=1000.0, key=f"seed_{acc_name}")
        if target_seed != curr_acc_data.get("target_seed"):
            st.session_state['accounts'][acc_name]["target_seed"] = target_seed; save_accounts_data(st.session_state['accounts'])

        status_d = []
        all_tkrs = set([t for t in asset_vals.keys()] + list(mr['target_weights'].keys()))
        for tkr in all_tkrs:
            tkr = tkr.upper(); my_v = asset_vals.get(tkr, 0.0); my_w = (my_v / total_val * 100) if total_val > 0 else 0.0
            tw = mr['target_weights'].get(tkr, 0.0); tv = target_seed * tw; diff = tv - my_v; cp = live_prices.get(tkr, 0.0)
            act = "적정" if abs(diff) < 50 else (f"🟢 ${diff:,.0f} 매수" if diff > 0 else f"🔴 ${abs(diff):,.0f} 매도")
            
            shares, avg_price = 0.0, 0.0
            for _, row in pf_df.iterrows():
                if str(row.iloc[0]).upper().strip() == tkr:
                    try: shares += float(row.iloc[1]); avg_price = float(row.iloc[2])
                    except: pass
            
            ret_pct, ret_amt = 0.0, 0.0
            if shares > 0 and tkr != "CASH":
                if avg_price > 0: ret_pct = ((cp - avg_price) / avg_price) * 100; ret_amt = (cp - avg_price) * shares
            if my_v > 0 or tw > 0: status_d.append({"종목": tkr, "목표비중": f"{tw*100:.1f}%", "현재비중": f"{my_w:.1f}%", "목표액": f"${tv:,.0f}", "현재액": f"${my_v:,.0f}", "수익률 (%)": f"{ret_pct:+.2f}%" if shares > 0 and tkr != "CASH" else "-", "수익금 ($)": f"${ret_amt:+,.0f}" if shares > 0 and tkr != "CASH" else "-", "액션": act})
                
        if status_d:
            status_df = pd.DataFrame(status_d).sort_values("목표비중", ascending=False)
            fig_comp = go.Figure(data=[
                go.Bar(name='현재 비중 (Actual)', x=list(status_df['종목']), y=[float(str(x).replace('%','')) for x in status_df['현재비중']], marker_color='#3498db'),
                go.Bar(name='목표 비중 (Target)', x=list(status_df['종목']), y=[float(str(x).replace('%','')) for x in status_df['목표비중']], marker_color='#18bc9c')
            ])
            fig_comp.update_layout(barmode='group', height=250, margin=dict(t=30, b=0, l=0, r=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_comp, use_container_width=True)

            def color_act(val):
                val_s = str(val)
                if '매수' in val_s or ('+' in val_s and val_s != '-'): return 'color: #ff4b4b; font-weight: bold;'
                elif '매도' in val_s or ('-' in val_s and val_s != '-'): return 'color: #3498db; font-weight: bold;'
                return ''
            st.dataframe(status_df.style.map(color_act, subset=['액션', '수익률 (%)', '수익금 ($)']), use_container_width=True, hide_index=True)

        # 🔥 자산 가치 추이: 00시 기준 운용 시드 꺾은선 그래프
        st.write("")
        st.markdown("**[ 📈 00시 종가 기준 운용 시드(Target Seed) 성장 곡선 ]**")
        if target_seed > 0:
            with st.container(border=True):
                fed_str = curr_acc_data.get("first_entry_date")
                default_date = pd.to_datetime(fed_str).date() if fed_str else (datetime.today() - timedelta(days=90)).date()
                col_date, _ = st.columns([1, 3])
                with col_date:
                    u_date = st.date_input("투자 시작일 (벤치마크 기점)", value=default_date, key=f"date_{acc_name}")
                    if str(u_date) != str(fed_str)[:10]: 
                        st.session_state['accounts'][acc_name]["first_entry_date"] = str(u_date)
                        save_accounts_data(st.session_state['accounts'])
                
                try:
                    # QQQ를 벤치마크로 삼아, 사용자의 현재 타겟 시드가 과거에 어떻게 변해왔는지 궤적을 그림
                    chart_start_ts = pd.Timestamp(u_date)
                    fetch_start = (chart_start_ts - timedelta(days=5)).strftime('%Y-%m-%d')
                    bench_data = yf.download("QQQ", start=fetch_start, progress=False)['Close'].ffill()
                    
                    if not bench_data.empty:
                        if isinstance(bench_data, pd.DataFrame): bench_series = bench_data.iloc[:, 0]
                        else: bench_series = bench_data
                        
                        bench_series = bench_series[bench_series.index >= chart_start_ts]
                        # 투자 시작일의 QQQ 가격을 기준(1.0)으로 삼고, 현재 타겟 시드를 곱해 성장 곡선 생성
                        seed_curve = (bench_series / bench_series.iloc[0]) * target_seed
                        
                        fig_seed = go.Figure()
                        fig_seed.add_trace(go.Scatter(x=seed_curve.index, y=seed_curve.values, name='운용 시드 추이', line=dict(color='#00d1ff', width=3), fill='tozeroy', fillcolor='rgba(0, 209, 255, 0.1)'))
                        fig_seed.add_trace(go.Scatter(x=seed_curve.index, y=[target_seed]*len(seed_curve), name='현재 시드 기준선', line=dict(color='#e74c3c', width=2, dash='dot')))
                        fig_seed.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="운용 시드 ($)", template="plotly_dark", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                        st.plotly_chart(fig_seed, use_container_width=True)
                    else: st.info("선택한 날짜의 주가 데이터가 없습니다.")
                except Exception as e: pass

        col_j, col_h = st.columns([1.5, 1])
        with col_j:
            st.markdown("**[ 매매 복기 일지 ]**")
            def sj(): st.session_state['accounts'][acc_name]["journal_text"] = st.session_state[f'jnl_{acc_name}']; save_accounts_data(st.session_state['accounts'])
            st.text_area("상황 기록", value=curr_acc_data.get('journal_text', ''), height=200, key=f'jnl_{acc_name}', on_change=sj, label_visibility="collapsed")
        with col_h:
            st.markdown("**[ 시스템 로그 ]**")
            if curr_acc_data.get('history'): st.dataframe(pd.DataFrame(curr_acc_data['history'])[::-1], hide_index=True, use_container_width=True, height=200)

    page_func.__name__ = f"page_pf_{abs(hash(acc_name))}"
    return page_func


# --- 페이지 3: 계좌 관리 ---
def page_manage_accounts():
    st.title("⚙️ 포트폴리오 계좌 관리")
    st.subheader("➕ 새 계좌 만들기")
    new_acc = st.text_input("계좌 이름")
    if st.button("🚀 생성", type="primary"):
        if new_acc and new_acc not in st.session_state['accounts']:
            st.session_state['accounts'][new_acc] = {"portfolio": [{"티커 (Ticker)": t, "수량 (주/달러)": 0.0, "평균 단가 ($)": 0.0} for t in REQUIRED_TICKERS], "history": [{"Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Log": "✨ 계좌 개설"}], "first_entry_date": None, "journal_text": "", "target_seed": 10000.0}
            save_accounts_data(st.session_state['accounts']); st.success("생성 완료!"); st.rerun()
    st.divider(); st.subheader("🗑️ 기존 계좌 삭제")
    for acc in list(st.session_state['accounts'].keys()):
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"💼 **{acc}**")
        if c2.button("삭제", key=f"del_{acc}", disabled=len(st.session_state['accounts']) <= 1):
            del st.session_state['accounts'][acc]; save_accounts_data(st.session_state['accounts']); st.rerun()

# =====================================================================
# [3] 네비게이션 라우팅 및 사이드바 백업 기능
# =====================================================================
st.sidebar.divider()
with st.sidebar.expander("💾 데이터 백업 및 복구", expanded=False):
    st.download_button(label="📥 백업 받기", data=json.dumps(st.session_state['accounts'], ensure_ascii=False, indent=4), file_name=f"amls_backup.json", mime="application/json", use_container_width=True)
    up_f = st.file_uploader("📤 복구하기", type=['json'])
    if up_f and st.button("⚠️ 복구 실행"):
        st.session_state['accounts'] = json.load(up_f); save_accounts_data(st.session_state['accounts']); st.rerun()

pages_dict = {
    "🌐 글로벌 마켓 터미널": [st.Page(page_market_dashboard, title="매크로 & 시장 지표", icon="🗺️")],
    "📊 백테스팅 시뮬레이터": [
        st.Page(page_amls_backtest, title="AMLS 듀얼 엔진", icon="🦅"),
        st.Page(page_dokkaebi_backtest, title="세윤도깨비 시뮬레이터", icon="👹")
    ],
    "📜 공식 가이드": [st.Page(page_strategy_specification, title="전략 공식 명세서 (v4.3)", icon="📄")],
    "🏦 내 포트폴리오": []
}

for name in st.session_state['accounts'].keys():
    pages_dict["🏦 내 포트폴리오"].append(st.Page(make_portfolio_page(name), title=name, icon="💼"))
pages_dict["🏦 내 포트폴리오"].append(st.Page(page_manage_accounts, title="⚙️ 계좌 관리", icon="⚙️"))

pg = st.navigation(pages_dict)
pg.run()
