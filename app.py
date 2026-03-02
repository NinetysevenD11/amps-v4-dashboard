import streamlit as st
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

warnings.filterwarnings('ignore')

# --- 페이지 기본 설정 ---
st.set_page_config(page_title="AMLS & 도깨비 퀀트 관제탑", layout="wide", initial_sidebar_state="expanded")

# --- 💾 데이터 영구 보존 및 세션 유지 로직 ---
DATA_FILE = "amls_portfolio_data.json"

def load_portfolio_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    return None

def save_portfolio_data(df, history, first_date, journal_text):
    data = {
        "portfolio": df.to_dict(orient="records"),
        "history": history,
        "first_entry_date": first_date.isoformat() if first_date else None,
        "journal_text": journal_text
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if 'portfolio_loaded' not in st.session_state:
    saved_data = load_portfolio_data()
    if saved_data and len(saved_data.get("portfolio", [])) > 0:
        pf_df = pd.DataFrame(saved_data["portfolio"])
        pf_df["수량 (주/달러)"] = pf_df["수량 (주/달러)"].astype(float)
        pf_df["평균 단가 ($)"] = pf_df["평균 단가 ($)"].astype(float)
        st.session_state['portfolio_df'] = pf_df
        st.session_state['portfolio_history'] = saved_data.get("history", [])
        
        fd = saved_data.get("first_entry_date")
        st.session_state['first_entry_date'] = datetime.fromisoformat(fd) if fd else None
        st.session_state['journal_text'] = saved_data.get("journal_text", "")
    else:
        st.session_state['portfolio_df'] = pd.DataFrame({
            "티커 (Ticker)": ["TQQQ", "QLD", "QQQ", "SOXL", "USD", "GLD", "CASH"],
            "수량 (주/달러)": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "평균 단가 ($)": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        })
        st.session_state['portfolio_history'] = []
        st.session_state['first_entry_date'] = None
        st.session_state['journal_text'] = ""
        
    st.session_state['portfolio_loaded'] = True

if 'target_seed' not in st.session_state:
    st.session_state['target_seed'] = 10000.0
if 'last_portfolio_df' not in st.session_state:
    if 'portfolio_df' in st.session_state:
        st.session_state['last_portfolio_df'] = st.session_state['portfolio_df'].copy()


# --- 메인 네비게이션 사이드바 ---
st.sidebar.markdown("### 🦅 퀀트 통합 관제탑")
app_mode = st.sidebar.radio("모드 선택", [
    "[1] AMLS 백테스트 (v4 vs v4.3)", 
    "[2] 실전 포트폴리오 관리 (AMLS)",
    "[3] 세윤도깨비 시뮬레이터 (신규)"
])
st.sidebar.markdown("---")

# =====================================================================
# 1. AMLS 백테스트 대시보드 모드
# =====================================================================
if app_mode == "[1] AMLS 백테스트 (v4 vs v4.3)":
    st.title("AMLS 퀀트 듀얼 백테스트 엔진")
    st.markdown("**AMLS v4 (기본형)**과 최신 알고리즘이 적용된 **AMLS v4.3 (R2/R3 개선 및 단계적 진입)**의 퍼포먼스를 비교합니다.")

    st.sidebar.header("⚙️ 백테스트 설정")
    BACKTEST_START = st.sidebar.date_input("시작일", datetime(2018, 1, 1))
    BACKTEST_END = st.sidebar.date_input("종료일", datetime.today())
    INITIAL_CAPITAL = st.sidebar.number_input("초기 자본금 ($)", value=10000, step=1000)
    MONTHLY_CONTRIBUTION = st.sidebar.number_input("매월 추가 적립금 ($)", value=2000, step=500)

    @st.cache_data(ttl=3600)
    def load_and_calculate_data(start, end, init_cap, monthly_cont):
        tickers = ['QQQ', 'TQQQ', 'SOXL', 'USD', 'QLD', 'SSO', 'SPY', 'SMH', 'GLD', '^VIX']
        start_str = (start - timedelta(days=400)).strftime("%Y-%m-%d")
        end_str = end.strftime("%Y-%m-%d")

        try:
            data = yf.download(tickers, start=start_str, end=end_str, progress=False, auto_adjust=True)['Close']
        except:
            data = yf.download(tickers, start=start_str, end=end_str, progress=False)['Close']

        data = data.ffill().dropna(subset=['QQQ', '^VIX'])

        df = pd.DataFrame(index=data.index)
        for t in data.columns:
            df[t] = data[t]

        df['QQQ_MA50'] = df['QQQ'].rolling(window=50).mean()
        df['QQQ_MA200'] = df['QQQ'].rolling(window=200).mean()
        df['QQQ_RSI'] = ta.rsi(df['QQQ'], length=14)
        df['SMH_MA50'] = df['SMH'].rolling(window=50).mean()
        df['SMH_3M_Ret'] = df['SMH'].pct_change(periods=63)
        df['SMH_RSI'] = ta.rsi(df['SMH'], length=14)

        df = df.dropna(subset=['QQQ_MA200', 'SMH_RSI'])
        df = df.loc[pd.to_datetime(start):]
        daily_returns = df[data.columns].pct_change().fillna(0)

        def get_target_regime(row):
            vix, qqq, ma200, ma50 = row['^VIX'], row['QQQ'], row['QQQ_MA200'], row['QQQ_MA50']
            if vix > 40: return 4
            if qqq < ma200: return 3
            if qqq >= ma200 and ma50 >= ma200 and vix < 25: return 1
            return 2

        df['Target_Regime'] = df.apply(get_target_regime, axis=1)

        actual_regime_v4 = []
        actual_regime_v4_3 = []
        current_v4 = 3
        current_v4_3 = 3
        pend_v4 = None
        pend_v4_3 = None
        cnt_v4 = 0
        cnt_v4_3 = 0

        for i in range(len(df)):
            tr = df['Target_Regime'].iloc[i]
            
            if tr > current_v4:
                current_v4 = tr; pend_v4 = None; cnt_v4 = 0
                actual_regime_v4.append(current_v4)
            elif tr < current_v4:
                if tr == pend_v4:
                    cnt_v4 += 1
                    if cnt_v4 >= 5:
                        current_v4 = tr; pend_v4 = None; cnt_v4 = 0
                        actual_regime_v4.append(current_v4)
                    else:
                        actual_regime_v4.append(current_v4)
                else:
                    pend_v4 = tr; cnt_v4 = 1
                    actual_regime_v4.append(current_v4)
            else:
                pend_v4 = None; cnt_v4 = 0
                actual_regime_v4.append(current_v4)

            if tr > current_v4_3: 
                current_v4_3 = tr; pend_v4_3 = None; cnt_v4_3 = 0
                actual_regime_v4_3.append(current_v4_3)
            elif tr < current_v4_3: 
                if tr == pend_v4_3:
                    cnt_v4_3 += 1
                    if cnt_v4_3 >= 5: 
                        current_v4_3 = tr; pend_v4_3 = None; cnt_v4_3 = 0
                        actual_regime_v4_3.append(current_v4_3)
                    else: 
                        actual_regime_v4_3.append(current_v4_3 - 1)
                else: 
                    pend_v4_3 = tr; cnt_v4_3 = 1
                    actual_regime_v4_3.append(current_v4_3 - 1)
            else:
                pend_v4_3 = None; cnt_v4_3 = 0
                actual_regime_v4_3.append(current_v4_3)

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

        strategies = ['AMLS v4.3', 'AMLS v4', 'QQQ', 'QLD', 'TQQQ', 'SPY']
        ports = {s: init_cap for s in strategies}
        hists = {s: [init_cap] for s in strategies}
        invested_hist = [init_cap]
        total_invested = init_cap
        
        weights_v4 = {t: 0.0 for t in data.columns}
        weights_v4_3 = {t: 0.0 for t in data.columns}
        logs = []

        for i in range(1, len(df)):
            today, yesterday = df.index[i], df.index[i-1]

            ret_v4 = sum(weights_v4[t] * daily_returns[t].iloc[i] for t in data.columns)
            ret_v4_3 = sum(weights_v4_3[t] * daily_returns[t].iloc[i] for t in data.columns)
            
            ports['AMLS v4'] *= (1 + ret_v4)
            ports['AMLS v4.3'] *= (1 + ret_v4_3)
            for s in ['QQQ', 'QLD', 'TQQQ', 'SPY']: ports[s] *= (1 + daily_returns[s].iloc[i])

            for t in data.columns:
                if ports['AMLS v4'] > 0: weights_v4[t] = (weights_v4[t] * (1 + daily_returns[t].iloc[i])) / (1 + ret_v4)
                if ports['AMLS v4.3'] > 0: weights_v4_3[t] = (weights_v4_3[t] * (1 + daily_returns[t].iloc[i])) / (1 + ret_v4_3)

            if today.month != yesterday.month:
                for s in strategies: ports[s] += monthly_cont
                total_invested += monthly_cont

            invested_hist.append(total_invested)
            for s in strategies: hists[s].append(ports[s])

            today_reg_v4 = df['Signal_Regime_v4'].iloc[i]
            today_reg_v4_3 = df['Signal_Regime_v4_3'].iloc[i]
            use_soxl = (df['SMH'].iloc[i-1] > df['SMH_MA50'].iloc[i-1]) and (df['SMH_3M_Ret'].iloc[i-1] > 0.05) and (df['SMH_RSI'].iloc[i-1] > 50)

            if today.month != yesterday.month or today_reg_v4 != df['Signal_Regime_v4'].iloc[i-1] or i == 1:
                weights_v4 = get_v4_weights(today_reg_v4, use_soxl)
                
            if today.month != yesterday.month or today_reg_v4_3 != df['Signal_Regime_v4_3'].iloc[i-1] or i == 1:
                weights_v4_3 = get_v4_3_weights(today_reg_v4_3, use_soxl)

                log_type = "레짐 전환 (v4.3)" if today_reg_v4_3 != df['Signal_Regime_v4_3'].iloc[i-1] else "월간 정기 (v4.3)"
                semi_target = "SOXL (3x)" if use_soxl and today_reg_v4_3 == 1 else ("USD (2x)" if today_reg_v4_3 in [1, 2] else "-")
                
                logs.append({
                    "날짜": today.strftime('%Y-%m-%d'), "유형": log_type, "국면": f"Regime {int(today_reg_v4_3)}",
                    "반도체 스위칭": semi_target, "평가액": ports['AMLS v4.3']
                })

        for s in strategies: df[f'{s}_Value'] = hists[s]
        df['Invested'] = invested_hist
        return df, logs, data.columns

    with st.spinner('듀얼 퀀트 엔진을 가동하여 시장 데이터를 연산 중입니다...'):
        df, full_logs, tickers = load_and_calculate_data(BACKTEST_START, BACKTEST_END, INITIAL_CAPITAL, MONTHLY_CONTRIBUTION)
        strategies = ['AMLS v4.3', 'AMLS v4', 'QQQ', 'QLD', 'TQQQ', 'SPY']

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
        with tab_ret:
            st.dataframe(yearly_ret, use_container_width=True)
        with tab_val:
            st.dataframe(yearly_val, use_container_width=True)

    st.write("")
    st.markdown("**[ 자산 성장 및 계좌 낙폭 (Drawdown) ]**")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    
    line_colors = ['#1abc9c', '#8e44ad', '#3498db', '#f39c12', '#e74c3c', '#2c3e50']
    
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


# =====================================================================
# 2. 내 실전 포트폴리오 관리 모드 (AMLS v4.3)
# =====================================================================
elif app_mode == "[2] 실전 포트폴리오 관리 (AMLS)":
    st.title("AMLS v4.3 실전 포트폴리오 관제탑")
    st.markdown("가장 진보된 **단계적 진입 로직(v4.3)**을 바탕으로 현재 시장 상태를 파악하고 리밸런싱 지침을 확인합니다.")

    TICKERS = ['QQQ', 'TQQQ', 'SOXL', 'USD', 'QLD', 'SSO', 'SPY', 'SMH', 'GLD', '^VIX']

    def get_target_weights_v4_3(regime, use_soxl):
        w = {t: 0.0 for t in TICKERS}
        semi = 'SOXL' if use_soxl else 'USD'
        if regime == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'], w['CASH'] = 0.30, 0.20, 0.20, 0.15, 0.10, 0.05
        elif regime == 2: w['QLD'], w['SSO'], w['GLD'], w['USD'], w['QQQ'], w['CASH'] = 0.30, 0.25, 0.20, 0.10, 0.05, 0.10
        elif regime == 3: w['GLD'], w['CASH'], w['QQQ'] = 0.50, 0.35, 0.15
        elif regime == 4: w['GLD'], w['CASH'], w['QQQ'] = 0.50, 0.40, 0.10
        return {k: v for k, v in w.items() if v > 0}

    @st.cache_data(ttl=1800)
    def get_market_regime_v4_3():
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

        current_v4_3 = 3
        pend_v4_3 = None
        cnt_v4_3 = 0
        actual_regime_v4_3 = []
        for i in range(len(df)):
            tr = df['Target_Regime'].iloc[i]
            if tr > current_v4_3:
                current_v4_3 = tr; pend_v4_3 = None; cnt_v4_3 = 0
                actual_regime_v4_3.append(current_v4_3)
            elif tr < current_v4_3:
                if tr == pend_v4_3:
                    cnt_v4_3 += 1
                    if cnt_v4_3 >= 5:
                        current_v4_3 = tr; pend_v4_3 = None; cnt_v4_3 = 0
                        actual_regime_v4_3.append(current_v4_3)
                    else:
                        actual_regime_v4_3.append(current_v4_3 - 1)
                else:
                    pend_v4_3 = tr; cnt_v4_3 = 1
                    actual_regime_v4_3.append(current_v4_3 - 1)
            else:
                pend_v4_3 = None; cnt_v4_3 = 0
                actual_regime_v4_3.append(current_v4_3)
                
        df['Signal_Regime_v4_3'] = pd.Series(actual_regime_v4_3, index=df.index).shift(1).bfill()

        today = df.iloc[-1]
        today_target = today['Target_Regime']
        today_signal = df['Signal_Regime_v4_3'].iloc[-1]
        
        vix, qqq, ma200, ma50 = today['^VIX'], today['QQQ'], today['QQQ_MA200'], today['QQQ_MA50']
        smh, smh_ma50, smh_3m_ret, smh_rsi = today['SMH'], today['SMH_MA50'], today['SMH_3M_Ret'], today['SMH_RSI']

        cond1, cond2, cond3 = smh > smh_ma50, smh_3m_ret > 0.05, smh_rsi > 50
        use_soxl = cond1 and cond2 and cond3
        target_w = get_target_weights_v4_3(today_signal, use_soxl)
        
        semi_target = "SOXL (3배)" if use_soxl else "USD (2배)"
        if today_signal in [3, 4]: semi_target = "미보유 (대피)"

        return {
            'target_regime': today_target, 'applied_regime': today_signal, 
            'is_waiting': (today_target < current_v4_3) and pend_v4_3 is not None,
            'wait_days': cnt_v4_3, 'vix': vix, 'qqq': qqq, 'ma200': ma200, 'ma50': ma50,
            'smh': smh, 'smh_ma50': smh_ma50, 'smh_3m_ret': smh_3m_ret, 'smh_rsi': smh_rsi,
            'cond1': cond1, 'cond2': cond2, 'cond3': cond3,
            'semi_target': semi_target, 'date': today.name, 'target_weights': target_w,
            'latest_prices': {t: today[t] for t in TICKERS if t != '^VIX'}
        }

    with st.spinner("시장 국면 판독 중..."):
        mr = get_market_regime_v4_3()

    with st.container(border=True):
        st.markdown(f"**[ 시장 레이더 요약 ]** &nbsp; | &nbsp; 기준일: {mr['date'].strftime('%Y-%m-%d')}")
        r_col1, r_col2, r_col3, r_col4 = st.columns(4)
        
        regime_color = "#e74c3c" if mr['applied_regime'] >= 3 else "#2ecc71"
        regime_display = f"Regime {int(mr['applied_regime'])}"
        if mr['is_waiting']: regime_display += f"<br><span style='font-size: 14px; color: #f39c12;'>상향 전환 대기중 ({mr['wait_days']}일차 임시적용)</span>"
            
        r_col1.markdown(f"v4.3 실시간 국면<br><span style='font-size: 24px; font-weight: bold; color: {regime_color};'>{regime_display}</span>", unsafe_allow_html=True)
        r_col2.metric("공포 지수 (VIX)", f"{mr['vix']:.2f}")
        r_col3.metric("QQQ 200일선 이격도", f"{(mr['qqq'] / mr['ma200'] - 1) * 100:+.2f}%")
        r_col4.markdown(f"반도체 스위칭 타겟<br><span style='font-size: 20px; font-weight: bold; color: #3498db;'>{mr['semi_target']}</span>", unsafe_allow_html=True)

    st.write("")
    col_header1, col_header2 = st.columns([5, 1])
    with col_header1: st.markdown("**[ 내 포트폴리오 자산 비중 ]**")
    with col_header2:
        if st.button("🔄 초기화", type="primary", use_container_width=True):
            reset_df = pd.DataFrame({"티커 (Ticker)": ["TQQQ", "QLD", "QQQ", "SOXL", "USD", "GLD", "CASH"], "수량 (주/달러)": [0.0]*7, "평균 단가 ($)": [0.0]*7})
            st.session_state['portfolio_df'] = reset_df
            st.session_state['last_portfolio_df'] = reset_df.copy()
            st.session_state['portfolio_history'] = [{"Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Log": "🔄 시스템: 포트폴리오 전체 초기화됨"}]
            st.session_state['first_entry_date'] = None
            st.session_state['target_seed'] = 10000.0
            save_portfolio_data(st.session_state['portfolio_df'], st.session_state['portfolio_history'], st.session_state['first_entry_date'], st.session_state['journal_text'])
            st.rerun()
    
    col_table, col_chart = st.columns([1, 1.2])

    with col_table:
        edited_df = st.data_editor(
            st.session_state['portfolio_df'], num_rows="dynamic", key="portfolio_editor", use_container_width=True,
            column_config={
                "티커 (Ticker)": st.column_config.TextColumn("종목 (TICKER)"),
                "수량 (주/달러)": st.column_config.NumberColumn("보유 수량", min_value=0.0, format="%.2f", step=0.01),
                "평균 단가 ($)": st.column_config.NumberColumn("평균 단가 ($)", min_value=0.0, format="%.2f", step=0.01)
            }
        )

        def get_portfolio_dict(df):
            state = {}
            for _, row in df.iterrows():
                tkr = str(row.iloc[0]).upper().strip()
                if tkr and tkr.lower() not in ['nan', 'none', '']:
                    try: qty = float(row.iloc[1])
                    except: qty = 0.0
                    try: avg_p = float(row.iloc[2])
                    except: avg_p = 0.0
                    state[tkr] = {'qty': qty, 'avg_p': avg_p}
            return state

        old_state = get_portfolio_dict(st.session_state['last_portfolio_df'])
        new_state = get_portfolio_dict(edited_df)
        changes_detected = False
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not edited_df.equals(st.session_state['last_portfolio_df']):
            for tkr, new_val in new_state.items():
                if tkr in old_state:
                    old_val = old_state[tkr]
                    if old_val['qty'] != new_val['qty']:
                        st.session_state['portfolio_history'].append({"Date": now_str, "Log": f"[{tkr}] 수량 변경: {old_val['qty']} ➔ {new_val['qty']}"})
                        changes_detected = True
                    if old_val['avg_p'] != new_val['avg_p']:
                        st.session_state['portfolio_history'].append({"Date": now_str, "Log": f"[{tkr}] 평단가 변경: ${old_val['avg_p']} ➔ ${new_val['avg_p']}"})
                        changes_detected = True
                else:
                    st.session_state['portfolio_history'].append({"Date": now_str, "Log": f"[{tkr}] 신규 종목 추가: {new_val['qty']}주"})
                    changes_detected = True
                    if st.session_state['first_entry_date'] is None and new_val['qty'] > 0: st.session_state['first_entry_date'] = datetime.now()
            
            for tkr in old_state.keys():
                if tkr not in new_state:
                    st.session_state['portfolio_history'].append({"Date": now_str, "Log": f"[{tkr}] 종목 삭제됨"})
                    changes_detected = True

            if changes_detected:
                st.session_state['portfolio_df'] = edited_df.copy()
                st.session_state['last_portfolio_df'] = edited_df.copy()
                save_portfolio_data(st.session_state['portfolio_df'], st.session_state['portfolio_history'], st.session_state['first_entry_date'], st.session_state['journal_text'])

    with col_chart:
        asset_values = {}
        total_invested_principal = 0.0 
        
        for _, row in st.session_state['portfolio_df'].iterrows():
            tkr = str(row.iloc[0]).upper().strip()
            try: shares = float(row.iloc[1])
            except: shares = 0.0
            try: avg_price = float(row.iloc[2])
            except: avg_price = 0.0
                
            if shares > 0:
                if tkr == "CASH":
                    asset_values[tkr] = asset_values.get(tkr, 0) + shares
                    total_invested_principal += shares
                else:
                    curr_price = mr['latest_prices'].get(tkr, 0.0)
                    if curr_price > 0: asset_values[tkr] = asset_values.get(tkr, 0) + (shares * curr_price)
                    if avg_price > 0: total_invested_principal += (shares * avg_price)
                    
        total_value = sum(asset_values.values()) if asset_values else 0.0

        if total_value > 0:
            fig_bar = go.Figure()
            palette = ['#2c3e50', '#18bc9c', '#3498db', '#e74c3c', '#f39c12', '#9b59b6', '#34495e', '#bdc3c7']
            sorted_assets = sorted(asset_values.items(), key=lambda x: x[1], reverse=True)
            
            for idx, (tkr, val) in enumerate(sorted_assets):
                weight = (val / total_value) * 100
                fig_bar.add_trace(go.Bar(
                    y=['내 비중'], x=[weight], name=tkr, orientation='h',
                    text=f"<b>{tkr}</b><br>{weight:.1f}%", textposition='inside', insidetextanchor='middle',
                    marker=dict(color=palette[idx % len(palette)], line=dict(color='white', width=1.0)),
                    hoverinfo='text', hovertext=f"{tkr}: ${val:,.0f} ({weight:.1f}%)"
                ))

            fig_bar.update_layout(barmode='stack', height=180, margin=dict(l=0, r=0, t=30, b=0), xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, 100]), yaxis=dict(showgrid=False, zeroline=False, showticklabels=False), showlegend=False, title=dict(text=f"현재 내 총 평가액: <b>${total_value:,.2f}</b>", font=dict(size=16), x=0.5, xanchor='center'))
            st.plotly_chart(fig_bar, use_container_width=True)


    st.write("")
    st.markdown("**[ 종목별 수익률 & 리밸런싱 액션 지침 ]**")
    col_seed_txt, col_seed_input = st.columns([1.5, 1])
    with col_seed_txt: st.markdown("원하시는 **총 운용 시드(목표 자산)**를 입력하면, 현재 국면 목표 비중에 맞춰 종목별 매수/매도 수량을 정확히 계산해 드립니다.")
    with col_seed_input:
        target_seed = st.number_input("🎯 총 운용 시드 입력 ($)", value=st.session_state['target_seed'], step=1000.0, format="%.2f", label_visibility="collapsed")
        st.session_state['target_seed'] = target_seed

    status_data = []
    all_tickers = set([t for t in asset_values.keys()] + list(mr['target_weights'].keys()))

    for tkr in all_tickers:
        tkr = tkr.upper()
        my_val = asset_values.get(tkr, 0.0)
        my_weight = (my_val / total_value) * 100 if total_value > 0 else 0.0
        
        shares, avg_price = 0.0, 0.0
        for _, row in st.session_state['portfolio_df'].iterrows():
            if str(row.iloc[0]).upper().strip() == tkr:
                try: shares += float(row.iloc[1])
                except: pass
                try: avg_price = float(row.iloc[2])
                except: pass
                
        target_w_dec = mr['target_weights'].get(tkr, 0.0)
        target_val = target_seed * target_w_dec 
        
        diff_val = target_val - my_val
        curr_price = mr['latest_prices'].get(tkr, 0.0) if tkr != "CASH" else 1.0
        
        action_shares_str = ""
        if tkr != "CASH" and curr_price > 0:
            action_shares = abs(diff_val) / curr_price
            action_shares_str = f" (약 {action_shares:.1f}주)"

        if abs(diff_val) < 50: action = "적정 (유지)"
        elif diff_val > 0: action = f"🟢 약 ${diff_val:,.0f} 매수{action_shares_str}"
        else: action = f"🔴 약 ${abs(diff_val):,.0f} 매도{action_shares_str}"

        if shares > 0:
            if tkr == "CASH": ret_pct, ret_amt = 0.0, 0.0
            else:
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
        def color_status(val):
            if type(val) == str:
                if '매수' in val or ('+' in val and val != '-'): return 'color: #18bc9c; font-weight: bold;'
                elif '매도' in val or ('-' in val and val != '-'): return 'color: #e74c3c; font-weight: bold;'
                elif '유지' in val: return 'color: #95a5a6;'
            return ''
        st.dataframe(status_df.style.map(color_status, subset=['리밸런싱 액션', '수익률 (%)', '수익금 ($)']), hide_index=True, use_container_width=True)

# =====================================================================
# 3. 세윤도깨비 시뮬레이터 (신규 추가 탭)
# =====================================================================
elif app_mode == "[3] 세윤도깨비 시뮬레이터 (신규)":
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
    
    # 🔥 1단 수익 리밸런싱 설정 추가
    DOK_PROFIT_REBAL = st.sidebar.number_input("1단 수익 리밸런싱 기준 (%)", value=15, step=1)

    @st.cache_data(ttl=3600)
    def run_dokkaebi_backtest(start_d, end_d, init_c, month_add, t_trade, t_sig, ma_f, ma_s, w1, w2, w3, mdd_stop, rsi_exit, rsi_w, profit_rebal):
        start_dt = pd.to_datetime(start_d)
        end_dt = pd.to_datetime(end_d) + pd.Timedelta(days=1)
        warmup_dt = start_dt - pd.DateOffset(months=12)

        tickers = list(set([t_trade, t_sig]))
        data = yf.download(tickers, start=warmup_dt.strftime("%Y-%m-%d"), end=end_dt.strftime("%Y-%m-%d"), progress=False)
        
        if 'Close' in data.columns: df = data['Close'].copy()
        else: df = data.copy()
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if len(tickers) == 1:
            df = pd.DataFrame(df)
            df.columns = tickers

        df = df.dropna()
        if df.empty: return None, None

        df['MA_Fast'] = df[t_sig].rolling(window=ma_f).mean()
        df['MA_Slow'] = df[t_sig].rolling(window=ma_s).mean()

        delta = df[t_trade].diff()
        u = delta.where(delta > 0, 0)
        d = -delta.where(delta < 0, 0)
        au = u.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        ad = d.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        df['RSI'] = 100 - (100 / (1 + au/ad))
        df['High_Win'] = df[t_trade].rolling(window=60).max()

        sim_df = df[df.index >= start_dt].copy()
        if sim_df.empty: return None, None

        cash = init_c
        shares = 0
        total_invested = init_c
        daily_yield = 0.04 / 365

        equity_curve = []
        invested_curve = []
        log_data = []
        
        prev_month = -1
        
        p0 = sim_df[t_trade].iloc[0]
        ref0 = sim_df[t_sig].iloc[0]
        mf0 = sim_df['MA_Fast'].iloc[0]
        ms0 = sim_df['MA_Slow'].iloc[0]

        if np.isnan(mf0): w0 = 0.5
        elif ref0 > mf0: w0 = w1
        elif ref0 > ms0: w0 = w2
        else: w0 = w3

        shares = (cash * w0 * 0.999) / p0
        cash -= cash * w0
        prev_target_w = w0
        last_rebal_price = p0 # 🔥 마지막 리밸런싱 단가 저장

        equity_curve.append(cash + shares * p0)
        invested_curve.append(total_invested)

        for i in range(1, len(sim_df)):
            date = sim_df.index[i]
            price = sim_df[t_trade].iloc[i]
            ref_price = sim_df[t_sig].iloc[i]
            
            rsi = sim_df['RSI'].iloc[i]
            ma_f_val = sim_df['MA_Fast'].iloc[i]
            ma_s_val = sim_df['MA_Slow'].iloc[i]
            high_win = sim_df['High_Win'].iloc[i]

            curr_m = date.month
            if prev_month != -1 and curr_m != prev_month and month_add > 0:
                cash += month_add
                total_invested += month_add
            prev_month = curr_m

            if cash > 0: cash *= (1 + daily_yield)
            val = (shares * price) + cash

            drawdown = (high_win - price) / high_win if high_win > 0 else 0
            
            # 1차 상태 감지
            if drawdown >= mdd_stop / 100: target_w = 0.0; action = "🚨 패닉셀"
            elif not np.isnan(rsi) and rsi >= rsi_exit: target_w = rsi_w; action = "🔥 RSI 과열 익절"
            elif ref_price > ma_f_val: target_w = w1; action = "🟢 1단 (상승)"
            elif ref_price > ma_s_val: target_w = w2; action = "🟡 2단 (조정)"
            else: target_w = w3; action = "🔴 3단 (하락)"

            should_rebal = False
            
            # 🔥 리밸런싱 판별 로직 추가 (수익 리밸런싱 포함)
            if target_w != prev_target_w:
                should_rebal = True
            elif target_w == w1 and last_rebal_price > 0: # 1단 기어 유지 중일 때 수익 확인
                roi = (price - last_rebal_price) / last_rebal_price
                if roi >= (profit_rebal / 100.0):
                    should_rebal = True
                    action = f"💰 1단 익절 리밸런싱 (+{roi*100:.1f}%)"

            if should_rebal:
                target_val = val * target_w
                curr_stock_val = shares * price
                diff = target_val - curr_stock_val

                if diff > 0 and cash >= diff:
                    shares += (diff * 0.999) / price
                    cash -= diff
                elif diff < 0:
                    amt = abs(diff)
                    shares -= amt / price
                    cash += amt * 0.999
                
                prev_target_w = target_w
                last_rebal_price = price # 🔥 리밸런싱 했으므로 단가 갱신
                
                log_data.append({"Date": date.strftime('%Y-%m-%d'), "Action": action, "Price": price, "Target W": target_w, "Equity": val})

            val = (shares * price) + cash
            equity_curve.append(val)
            invested_curve.append(total_invested)
            
        # BnH 70% 
        bnh_invest_cash = init_c * w1
        bnh_reserve_cash = init_c * (1 - w1)
        bnh_shares = (bnh_invest_cash * 0.999) / sim_df[t_trade].iloc[0]
        bnh_curve = [(bnh_shares * sim_df[t_trade].iloc[0]) + bnh_reserve_cash]
        
        prev_m_bnh = -1
        for i in range(1, len(sim_df)):
            d = sim_df.index[i]
            p = sim_df[t_trade].iloc[i]
            if bnh_reserve_cash > 0: bnh_reserve_cash *= (1 + daily_yield)
            if prev_m_bnh != -1 and d.month != prev_m_bnh and month_add > 0:
                bnh_shares += (month_add * w1 * 0.999) / p
                bnh_reserve_cash += month_add * (1 - w1)
            prev_m_bnh = d.month
            bnh_curve.append((bnh_shares * p) + bnh_reserve_cash)

        res_df = pd.DataFrame({'Dokkaebi': equity_curve, 'BnH_70': bnh_curve, 'Invested': invested_curve}, index=sim_df.index)
        return res_df, log_data

    with st.spinner("도깨비 엔진 구동 중..."):
        res_df, logs = run_dokkaebi_backtest(
            DOK_START, DOK_END, DOK_INIT_CASH, DOK_MONTH_ADD, DOK_TRADE_TICKER, 
            DOK_SIG_TICKER, DOK_FAST_MA, DOK_SLOW_MA, DOK_W1, DOK_W2, DOK_W3, 
            DOK_MDD_STOP, DOK_RSI_EXIT, DOK_RSI_W, DOK_PROFIT_REBAL # 변수 추가
        )

    if res_df is not None:
        final_dok = res_df['Dokkaebi'].iloc[-1]
        final_bnh = res_df['BnH_70'].iloc[-1]
        total_inv = res_df['Invested'].iloc[-1]
        
        dok_ret = (final_dok / total_inv - 1) * 100
        bnh_ret = (final_bnh / total_inv - 1) * 100
        
        dok_mdd = (res_df['Dokkaebi'] / res_df['Dokkaebi'].cummax() - 1).min() * 100
        bnh_mdd = (res_df['BnH_70'] / res_df['BnH_70'].cummax() - 1).min() * 100

        st.subheader("📊 도깨비 백테스트 결과 요약")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 투입 원금", f"${total_inv:,.0f}")
        c2.metric("도깨비 최종 자산", f"${final_dok:,.0f}", f"{dok_ret:+.1f}%")
        c3.metric("BnH(70%) 최종 자산", f"${final_bnh:,.0f}", f"{bnh_ret:+.1f}%")
        c4.metric("도깨비 계좌 MDD", f"{dok_mdd:.1f}%", f"BnH MDD: {bnh_mdd:.1f}%", delta_color="inverse")

        if dok_ret < bnh_ret:
            st.warning("⚠️ **진단 리포트:** 잦은 가짜 신호(휩쏘) 또는 과도한 익절/손절 장치 발동으로 인해 도깨비 전략이 단순 거치식(BnH)보다 성과가 낮습니다. 우측 메뉴에서 필터 값을 완화해 보세요.")

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
