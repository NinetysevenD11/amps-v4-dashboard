import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')

st.title("🦅 AMLS 퀀트 듀얼 백테스트 엔진")
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
    actual_regime_v4 = []; actual_regime_v4_3 = []
    current_v4 = 3; current_v4_3 = 3
    pend_v4 = None; pend_v4_3 = None
    cnt_v4 = 0; cnt_v4_3 = 0

    for i in range(len(df)):
        tr = df['Target_Regime'].iloc[i]
        # v4 Logic
        if tr > current_v4:
            current_v4 = tr; pend_v4 = None; cnt_v4 = 0
            actual_regime_v4.append(current_v4)
        elif tr < current_v4:
            if tr == pend_v4:
                cnt_v4 += 1
                if cnt_v4 >= 5: current_v4 = tr; pend_v4 = None; cnt_v4 = 0; actual_regime_v4.append(current_v4)
                else: actual_regime_v4.append(current_v4)
            else: pend_v4 = tr; cnt_v4 = 1; actual_regime_v4.append(current_v4)
        else: pend_v4 = None; cnt_v4 = 0; actual_regime_v4.append(current_v4)
        # v4.3 Logic
        if tr > current_v4_3: 
            current_v4_3 = tr; pend_v4_3 = None; cnt_v4_3 = 0; actual_regime_v4_3.append(current_v4_3)
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

    strategies = ['AMLS v4.3', 'AMLS v4', 'QQQ', 'QLD', 'TQQQ', 'SPY']
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
        for s in ['QQQ', 'QLD', 'TQQQ', 'SPY']: ports[s] *= (1 + daily_returns[s].iloc[i])

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
    with tab_ret: st.dataframe(yearly_ret, use_container_width=True)
    with tab_val: st.dataframe(yearly_val, use_container_width=True)

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
