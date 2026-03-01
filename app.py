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

# --- 페이지 기본 설정 ---
st.set_page_config(page_title="AMLS v4 통합 대시보드", layout="wide", initial_sidebar_state="expanded")
st.title("🛡️ AMLS v4 실전 퀀트 대시보드 (Final Edition)")

# --- 사이드바 설정 (사용자 입력) ---
st.sidebar.header("⚙️ 백테스트 설정")
st.sidebar.markdown("이곳에서 설정값을 바꾸면 대시보드가 실시간으로 다시 계산됩니다.")
BACKTEST_START = st.sidebar.date_input("시작일", datetime(2018, 1, 1))
BACKTEST_END = st.sidebar.date_input("종료일", datetime.today())
INITIAL_CAPITAL = st.sidebar.number_input("초기 자본금 ($)", value=10000, step=1000)
MONTHLY_CONTRIBUTION = st.sidebar.number_input("매월 추가 적립금 ($)", value=2000, step=500)

# --- 데이터 수집 및 연산 (캐싱) ---
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

    def get_v4_weights(regime, use_soxl):
        w = {t: 0.0 for t in data.columns}; semi = 'SOXL' if use_soxl else 'USD'
        if regime == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'] = 0.30, 0.20, 0.20, 0.15, 0.10
        elif regime == 2: w['QLD'], w['SSO'], w['GLD'], w['QQQ'], w['USD'] = 0.25, 0.20, 0.20, 0.15, 0.10
        elif regime == 3: w['GLD'], w['QQQ'], w['SPY'] = 0.35, 0.20, 0.10
        elif regime == 4: w['GLD'], w['QQQ'] = 0.50, 0.10
        return w

    strategies = ['AMLS v4', 'QQQ', 'QLD', 'TQQQ', 'SPY']
    ports = {s: init_cap for s in strategies}
    hists = {s: [init_cap] for s in strategies}
    invested_hist = [init_cap]
    total_invested = init_cap
    weights_v4 = {t: 0.0 for t in data.columns}
    logs = []

    for i in range(1, len(df)):
        today, yesterday = df.index[i], df.index[i-1]
        
        ret_v4 = sum(weights_v4[t] * daily_returns[t].iloc[i] for t in data.columns)
        ports['AMLS v4'] *= (1 + ret_v4)
        for s in ['QQQ', 'QLD', 'TQQQ', 'SPY']: ports[s] *= (1 + daily_returns[s].iloc[i])
        
        for t in data.columns: 
            if ports['AMLS v4'] > 0: weights_v4[t] = (weights_v4[t] * (1 + daily_returns[t].iloc[i])) / (1 + ret_v4)
            
        if today.month != yesterday.month:
            for s in strategies: ports[s] += monthly_cont
            total_invested += monthly_cont
            
        invested_hist.append(total_invested)
        for s in strategies: hists[s].append(ports[s])
        
        today_reg = df['Signal_Regime'].iloc[i]
        if today.month != yesterday.month or today_reg != df['Signal_Regime'].iloc[i-1] or i == 1:
            use_soxl = (df['SMH'].iloc[i-1] > df['SMH_MA50'].iloc[i-1]) and (df['SMH_3M_Ret'].iloc[i-1] > 0.05) and (df['SMH_RSI'].iloc[i-1] > 50)
            weights_v4 = get_v4_weights(today_reg, use_soxl)
            
            log_type = "레짐 전환" if today_reg != df['Signal_Regime'].iloc[i-1] else "월간 정기"
            logs.append({
                "날짜": today.strftime('%Y-%m-%d'),
                "유형": log_type,
                "국면": f"Regime {int(today_reg)}",
                "반도체 스위칭": "SOXL (3x)" if use_soxl and today_reg == 1 else ("USD (2x)" if today_reg in [1, 2] else "-"),
                "평가액": ports['AMLS v4']
            })

    for s in strategies: df[f'{s}_Value'] = hists[s]
    df['Invested'] = invested_hist
    
    return df, logs, data.columns, get_v4_weights

with st.spinner('🚀 퀀트 엔진을 가동하여 시장 데이터를 연산 중입니다...'):
    df, full_logs, tickers, get_v4_weights_func = load_and_calculate_data(BACKTEST_START, BACKTEST_END, INITIAL_CAPITAL, MONTHLY_CONTRIBUTION)
    strategies = ['AMLS v4', 'QQQ', 'QLD', 'TQQQ', 'SPY']

# --- 실시간 시장 레이더 ---
today_status = df.iloc[-1]
date_str = df.index[-1].strftime('%Y년 %m월 %d일')
current_regime_int = int(today_status['Signal_Regime'])

st.subheader(f"📡 실시간 시장 레이더 ({date_str} 종가 기준)")
m1, m2, m3, m4 = st.columns(4)
m1.metric("현재 적용 국면", f"Regime {current_regime_int}")
m2.metric("공포 지수 (VIX)", f"{today_status['^VIX']:.2f}")
m3.metric("50일선 이격도 (QQQ)", f"{(today_status['QQQ'] / today_status['QQQ_MA50'] - 1) * 100:.2f}%")
m4.metric("200일선 이격도 (QQQ)", f"{(today_status['QQQ'] / today_status['QQQ_MA200'] - 1) * 100:.2f}%")

st.divider()

# --- ⭐ 신규: 내 포트폴리오 관리 및 리밸런싱 계산기 ---
st.subheader("💼 내 포트폴리오 관리 & 리밸런싱 계산기")
st.markdown("현재 보유 중인 종목의 **평가 금액($)**을 입력하면, 오늘 국면(Regime)에 맞게 **얼마를 사고팔아야 하는지** 자동으로 계산합니다.")

# 입력 폼 (3줄로 깔끔하게 배치)
my_assets = ['TQQQ', 'SOXL', 'USD', 'QLD', 'SSO', 'QQQ', 'SPY', 'GLD', '현금']
my_portfolio = {}

col_in1, col_in2, col_in3, col_in4, col_in5 = st.columns(5)
input_cols = [col_in1, col_in2, col_in3, col_in4, col_in5]

for i, asset in enumerate(my_assets):
    with input_cols[i % 5]:
        my_portfolio[asset] = st.number_input(f"{asset} ($)", value=0.0, step=100.0, format="%.2f")

total_my_value = sum(my_portfolio.values())

if total_my_value > 0:
    # 1. 시각화: 내 포트폴리오 원그래프
    st.markdown(f"**총 자산:** `${total_my_value:,.2f}`")
    
    col_pie, col_table = st.columns([1, 2])
    
    with col_pie:
        # 0이 아닌 자산만 필터링
        active_portfolio = {k: v for k, v in my_portfolio.items() if v > 0}
        p_colors = {'TQQQ': '#e74c3c', 'SOXL': '#8e44ad', 'USD': '#9b59b6', 'QLD': '#e67e22', 'SSO': '#f39c12', 'QQQ': '#3498db', 'SPY': '#2980b9', 'GLD': '#f1c40f', '현금': '#2ecc71'}
        
        fig_my_pie = go.Figure(data=[go.Pie(
            labels=list(active_portfolio.keys()), 
            values=list(active_portfolio.values()), 
            hole=.4,
            marker=dict(colors=[p_colors.get(k, '#95a5a6') for k in active_portfolio.keys()])
        )])
        fig_my_pie.update_layout(title_text="현재 내 포트폴리오 구성", margin=dict(t=40, b=0, l=0, r=0), height=300)
        st.plotly_chart(fig_my_pie, use_container_width=True)

    with col_table:
        # 2. 리밸런싱 계산 로직
        use_soxl_today = (today_status['SMH'] > today_status['SMH_MA50']) and (today_status['SMH_3M_Ret'] > 0.05) and (today_status['SMH_RSI'] > 50)
        target_weights = get_v4_weights_func(current_regime_int, use_soxl_today)
        
        # 현금 비중 세팅
        if current_regime_int == 1: target_weights['현금'] = 0.05
        elif current_regime_int == 2: target_weights['현금'] = 0.10
        elif current_regime_int == 3: target_weights['현금'] = 0.35
        elif current_regime_int == 4: target_weights['현금'] = 0.40
        else: target_weights['현금'] = 0.0
            
        rebalance_data = []
        for asset in my_assets:
            curr_val = my_portfolio[asset]
            target_weight = target_weights.get(asset, 0.0)
            target_val = total_my_value * target_weight
            diff = target_val - curr_val
            
            # Action 판별
            if abs(diff) < 10: action = "-"
            elif diff > 0: action = "🟢 매수 (Buy)"
            else: action = "🔴 매도 (Sell)"
                
            rebalance_data.append({
                "종목": asset,
                "현재 비중": f"{(curr_val/total_my_value)*100:.1f}%",
                "목표 비중": f"{target_weight*100:.1f}%",
                "현재 금액": f"${curr_val:,.0f}",
                "목표 금액": f"${target_val:,.0f}",
                "주문 금액 (차액)": f"${diff:+,.0f}",
                "액션": action
            })
            
        rebalance_df = pd.DataFrame(rebalance_data)
        # 차액이 0인 것은 숨기거나 유지 (여기선 전부 보여줌)
        st.dataframe(rebalance_df.style.applymap(lambda x: 'color: green' if '매수' in str(x) else ('color: red' if '매도' in str(x) else ''), subset=['액션']), hide_index=True, use_container_width=True)

st.divider()

# --- 0. 포트폴리오 비율 시각화 (도넛 차트) ---
st.subheader("0. 국면별 포트폴리오 타겟 비율 (Regime Allocation)")

def get_v4_weights_for_plot(regime):
    w = {t: 0.0 for t in tickers}
    if regime == 1: w['TQQQ'], w['SOXL/USD'], w['QLD'], w['SSO'], w['GLD'], w['현금'] = 30, 20, 20, 15, 10, 5
    elif regime == 2: w['QLD'], w['SSO'], w['GLD'], w['QQQ'], w['USD'], w['현금'] = 25, 20, 20, 15, 10, 10
    elif regime == 3: w['GLD'], w['현금'], w['QQQ'], w['SPY'] = 35, 35, 20, 10
    elif regime == 4: w['GLD'], w['현금'], w['QQQ'] = 50, 40, 10
    return {k: v for k, v in w.items() if v > 0}

col0_1, col0_2, col0_3, col0_4 = st.columns(4)
colors = {'TQQQ': '#e74c3c', 'SOXL/USD': '#8e44ad', 'USD': '#9b59b6', 'QLD': '#e67e22', 'SSO': '#f39c12', 'QQQ': '#3498db', 'SPY': '#2980b9', 'GLD': '#f1c40f', '현금': '#2ecc71'}

for idx, col in enumerate([col0_1, col0_2, col0_3, col0_4]):
    reg = idx + 1
    w = get_v4_weights_for_plot(reg)
    fig_pie = go.Figure(data=[go.Pie(labels=list(w.keys()), values=list(w.values()), hole=.5, marker=dict(colors=[colors.get(k, '#95a5a6') for k in w.keys()]))])
    fig_pie.update_layout(title_text=f"Regime {reg}", title_x=0.5, margin=dict(t=30, b=0, l=0, r=0), height=250, showlegend=False)
    fig_pie.update_traces(textinfo='label+percent', textposition='inside')
    col.plotly_chart(fig_pie, use_container_width=True)

st.divider()

# --- 1. 핵심 지표 비교 ---
st.subheader("1. 핵심 지표 비교 (Key Metrics)")
def calc_metrics(series, invested):
    final = series.iloc[-1]; total_ret = (final / invested.iloc[-1]) - 1
    days = (series.index[-1] - series.index[0]).days
    cagr = (final / invested.iloc[-1]) ** (365.25 / days) - 1 if days > 0 else 0
    mdd = ((series / series.cummax()) - 1).min()
    sharpe = (series.pct_change().mean() * 252) / (series.pct_change().std() * np.sqrt(252))
    return [f"{total_ret*100:.1f}%", f"{cagr*100:.1f}%", f"{mdd*100:.1f}%", f"{sharpe:.2f}", f"${final:,.0f}"]

metrics_rows = [calc_metrics(df[f'{s}_Value'], df['Invested']) for s in strategies]
metrics_df = pd.DataFrame(metrics_rows, index=strategies, columns=['총 수익률', '연평균 수익률(CAGR)', '최대 낙폭(MDD)', '샤프 지수', '최종 자산($)'])
st.dataframe(metrics_df.style.highlight_max(subset=['연평균 수익률(CAGR)', '최종 자산($)'], color='lightgreen').highlight_min(subset=['최대 낙폭(MDD)'], color='lightcoral'), use_container_width=True)

st.divider()

# --- 2. 연도별 성과 ---
st.subheader("2. 연도별 수익률 (Yearly Returns)")
years = df.index.year.unique()
yearly_ret = pd.DataFrame(index=strategies, columns=[str(y) for y in years])
for y in years:
    for s in strategies:
        y_data = df[df.index.year == y][f'{s}_Value']
        yearly_ret.loc[s, str(y)] = f"{(y_data.iloc[-1] / y_data.iloc[0] - 1)*100:.1f}%"
st.dataframe(yearly_ret, use_container_width=True)

st.divider()

# --- 3. 전체 리밸런싱 로그 ---
st.subheader("3. 전체 리밸런싱 이력 (Rebalance Logs)")
st.markdown("최근 발생한 리밸런싱 내역부터 역순으로 보여줍니다.")
logs_df = pd.DataFrame(full_logs)[::-1] # 역순 정렬
logs_df['평가액'] = logs_df['평가액'].apply(lambda x: f"${x:,.0f}")
st.dataframe(logs_df, hide_index=True, use_container_width=True, height=250)

st.divider()

# --- 4. 시각화: 자산 성장 및 계좌 Drawdown 비교 ---
st.subheader("4. 자산 성장 및 계좌 낙폭 (Drawdown) 비교")
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)

line_colors = ['#8e44ad', '#3498db', '#f39c12', '#e74c3c', '#2c3e50']
for s, c in zip(strategies, line_colors):
    # 자산 성장 곡선
    fig.add_trace(go.Scatter(x=df.index, y=df[f'{s}_Value'], name=s, line=dict(color=c, width=3 if s=='AMLS v4' else 1.5)), row=1, col=1)
    # Drawdown 곡선
    dd = (df[f'{s}_Value'] / df[f'{s}_Value'].cummax()) - 1
    fig.add_trace(go.Scatter(x=df.index, y=dd*100, name=f'{s} DD', line=dict(color=c, width=1.5 if s=='AMLS v4' else 1, dash='solid' if s=='AMLS v4' else 'dot')), row=2, col=1)

fig.add_trace(go.Scatter(x=df.index, y=df['Invested'], name='누적 원금', line=dict(color='black', width=2, dash='dash')), row=1, col=1)
fig.update_yaxes(type="log", row=1, col=1)
fig.add_hline(y=-20, line_dash="dash", line_color="red", row=2, col=1, annotation_text="-20% 방어선")
fig.update_layout(height=700, margin=dict(l=0, r=0, t=30, b=0), hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- 5. 레짐 분포 ---
st.subheader("5. 레짐 체류 일자 (Regime Days)")
regime_counts = df['Signal_Regime'].value_counts().sort_index()
reg_df = pd.DataFrame({
    "국면": [f"Regime {int(r)}" for r in [1, 2, 3, 4]],
    "체류 일수": [f"{regime_counts.get(r, 0)}일" for r in [1, 2, 3, 4]],
    "비율(%)": [f"{regime_counts.get(r, 0)/len(df)*100:.1f}%" for r in [1, 2, 3, 4]]
})
st.dataframe(reg_df, hide_index=True, use_container_width=True)
