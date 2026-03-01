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

# 1. 페이지 기본 설정
st.set_page_config(page_title="AMLS v4 Dashboard", layout="wide")
st.title("🛡️ AMLS v4 퀀트 투자 대시보드")

# 2. 사이드바 설정 (사용자 입력)
st.sidebar.header("⚙️ 백테스트 설정")
BACKTEST_START = st.sidebar.date_input("시작일", datetime(2018, 1, 1))
BACKTEST_END = st.sidebar.date_input("종료일", datetime.today())
INITIAL_CAPITAL = st.sidebar.number_input("초기 자본금 ($)", value=10000, step=1000)
MONTHLY_CONTRIBUTION = st.sidebar.number_input("월 적립금 ($)", value=2000, step=500)

# 3. 데이터 수집 (캐싱을 통해 속도 향상)
@st.cache_data(ttl=3600) # 1시간마다 데이터 갱신
def load_data(start, end):
    tickers = ['QQQ', 'TQQQ', 'SOXL', 'USD', 'QLD', 'SSO', 'SPY', 'SMH', 'GLD', '^VIX']
    start_str = (start - timedelta(days=400)).strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")
    try:
        data = yf.download(tickers, start=start_str, end=end_str, progress=False, auto_adjust=True)['Close']
    except:
        data = yf.download(tickers, start=start_str, end=end_str, progress=False)['Close']
    return data.ffill().dropna(subset=['QQQ', '^VIX'])

with st.spinner('시장 데이터를 불러오고 분석 중입니다...'):
    data = load_data(BACKTEST_START, BACKTEST_END)
    
    # 지표 계산
    df = pd.DataFrame(index=data.index)
    for t in data.columns: df[t] = data[t]
    df['QQQ_MA50'] = df['QQQ'].rolling(window=50).mean()
    df['QQQ_MA200'] = df['QQQ'].rolling(window=200).mean()
    df['SMH_MA50'] = df['SMH'].rolling(window=50).mean()
    df['SMH_3M_Ret'] = df['SMH'].pct_change(periods=63)
    df['SMH_RSI'] = ta.rsi(df['SMH'], length=14)
    df = df.dropna(subset=['QQQ_MA200', 'SMH_RSI'])
    df = df.loc[pd.to_datetime(BACKTEST_START):]
    daily_returns = df[data.columns].pct_change().fillna(0)

    # 레짐 판단
    def get_target_regime(row):
        vix, qqq, ma200, ma50 = row['^VIX'], row['QQQ'], row['QQQ_MA200'], row['QQQ_MA50']
        if vix > 40: return 4
        if qqq < ma200: return 3
        if qqq >= ma200 and ma50 >= ma200 and vix < 25: return 1
        return 2

    df['Target_Regime'] = df.apply(get_target_regime, axis=1)

    # 비대칭 전환 상태 추적
    current_regime = 3 
    pending_regime = None
    confirm_count = 0
    actual_regime_list = []
    
    for i in range(len(df)):
        new_regime = df['Target_Regime'].iloc[i]
        if new_regime > current_regime: 
            current_regime = new_regime; pending_regime = None; confirm_count = 0
        elif new_regime < current_regime: 
            if new_regime == pending_regime:
                confirm_count += 1
                if confirm_count >= 5: current_regime = new_regime; pending_regime = None; confirm_count = 0
            else: pending_regime = new_regime; confirm_count = 1
        else: pending_regime = None; confirm_count = 0
        actual_regime_list.append(current_regime)

    df['Signal_Regime'] = pd.Series(actual_regime_list, index=df.index).shift(1).bfill()

    # 가중치 함수
    def get_v4_weights(regime, use_soxl):
        w = {t: 0.0 for t in data.columns}; semi = 'SOXL' if use_soxl else 'USD'
        if regime == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'] = 0.30, 0.20, 0.20, 0.15, 0.10
        elif regime == 2: w['QLD'], w['SSO'], w['GLD'], w['QQQ'], w['USD'] = 0.25, 0.20, 0.20, 0.15, 0.10
        elif regime == 3: w['GLD'], w['QQQ'], w['SPY'] = 0.35, 0.20, 0.10
        elif regime == 4: w['GLD'], w['QQQ'] = 0.50, 0.10
        return w

    # 백테스트 루프
    strategies = ['AMLS v4', 'QQQ', 'QLD', 'TQQQ']
    ports = {s: INITIAL_CAPITAL for s in strategies}
    hists = {s: [INITIAL_CAPITAL] for s in strategies}
    invested_hist = [INITIAL_CAPITAL]
    total_invested = INITIAL_CAPITAL
    weights_v4 = {t: 0.0 for t in data.columns}

    for i in range(1, len(df)):
        today, yesterday = df.index[i], df.index[i-1]
        
        ret_v4 = sum(weights_v4[t] * daily_returns[t].iloc[i] for t in data.columns)
        ports['AMLS v4'] *= (1 + ret_v4)
        for s in ['QQQ', 'QLD', 'TQQQ']: ports[s] *= (1 + daily_returns[s].iloc[i])
        
        for t in data.columns: 
            if ports['AMLS v4'] > 0: weights_v4[t] = (weights_v4[t] * (1 + daily_returns[t].iloc[i])) / (1 + ret_v4)
            
        if today.month != yesterday.month:
            for s in strategies: ports[s] += MONTHLY_CONTRIBUTION
            total_invested += MONTHLY_CONTRIBUTION
            
        invested_hist.append(total_invested)
        for s in strategies: hists[s].append(ports[s])
        
        today_reg = df['Signal_Regime'].iloc[i]
        if today.month != yesterday.month or today_reg != df['Signal_Regime'].iloc[i-1] or i == 1:
            use_soxl = (df['SMH'].iloc[i-1] > df['SMH_MA50'].iloc[i-1]) and (df['SMH_3M_Ret'].iloc[i-1] > 0.05) and (df['SMH_RSI'].iloc[i-1] > 50)
            weights_v4 = get_v4_weights(today_reg, use_soxl)

    for s in strategies: df[f'{s}_Value'] = hists[s]
    df['Invested'] = invested_hist

    # 오늘 상태 브리핑
    today_status = df.iloc[-1]
    st.subheader(f"📅 오늘 시장 상태 요약 ({df.index[-1].strftime('%Y-%m-%d')} 기준)")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("현재 국면 (Regime)", f"Regime {int(today_status['Signal_Regime'])}")
    col2.metric("나스닥 (QQQ)", f"${today_status['QQQ']:.2f}")
    col3.metric("공포 지수 (VIX)", f"{today_status['^VIX']:.2f}")
    col4.metric("최종 자산 (AMLS)", f"${df['AMLS v4_Value'].iloc[-1]:,.0f}")

    # 성과 지표 계산
    def calc_metrics(series, invested):
        final = series.iloc[-1]; total_ret = (final / invested.iloc[-1]) - 1
        days = (series.index[-1] - series.index[0]).days
        cagr = (final / invested.iloc[-1]) ** (365.25 / days) - 1 if days > 0 else 0
        mdd = ((series / series.cummax()) - 1).min()
        return [f"{total_ret*100:.1f}%", f"{cagr*100:.1f}%", f"{mdd*100:.1f}%", f"${final:,.0f}"]

    metrics_rows = [calc_metrics(df[f'{s}_Value'], df['Invested']) for s in strategies]
    metrics_df = pd.DataFrame(metrics_rows, index=strategies, columns=['총수익률', 'CAGR', '최대낙폭(MDD)', '최종자산($)'])
    
    st.divider()
    st.subheader("📊 전략 성과 비교")
    st.dataframe(metrics_df, use_container_width=True)

    # Plotly 시각화
    st.divider()
    st.subheader("📈 자산 성장 및 계좌 낙폭 (Drawdown)")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    
    colors = ['#8e44ad', '#7f8c8d', '#f39c12', '#c0392b']
    for s, c in zip(strategies, colors):
        fig.add_trace(go.Scatter(x=df.index, y=df[f'{s}_Value'], name=s, line=dict(color=c, width=2.5 if s=='AMLS v4' else 1.5)), row=1, col=1)
        dd = (df[f'{s}_Value'] / df[f'{s}_Value'].cummax()) - 1
        fig.add_trace(go.Scatter(x=df.index, y=dd*100, name=f'{s} DD', line=dict(color=c, width=1, dash='dot' if s!='AMLS v4' else 'solid')), row=2, col=1)
    
    fig.add_trace(go.Scatter(x=df.index, y=df['Invested'], name='누적 투입 원금', line=dict(color='black', width=2, dash='dash')), row=1, col=1)
    fig.update_yaxes(type="log", row=1, col=1)
    fig.add_hline(y=-20, line_dash="dash", line_color="red", row=2, col=1)
    fig.update_layout(height=700, margin=dict(l=0, r=0, t=30, b=0), hovermode="x unified")
    
    st.plotly_chart(fig, use_container_width=True)
