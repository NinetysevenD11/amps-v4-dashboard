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
st.title("🛡️ AMLS v4 퀀트 투자 대시보드 (Final Edition)")

# --- 사이드바 설정 ---
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

    current_regime = 3
    pending_regime = None
    confirm_count = 0
    actual_regime_list = []

    for i in range(len(df)):
        new_regime = df['Target_Regime'].iloc[i]
        if new_regime > current_regime:
            current_regime = new_regime
            pending_regime = None
            confirm_count = 0
        elif new_regime < current_regime:
            if new_regime == pending_regime:
                confirm_count += 1
                if confirm_count >= 5:
                    current_regime = new_regime
                    pending_regime = None
                    confirm_count = 0
            else:
                pending_regime = new_regime
                confirm_count = 1
        else:
            pending_regime = None
            confirm_count = 0
        actual_regime_list.append(current_regime)

    df['Signal_Regime'] = pd.Series(actual_regime_list, index=df.index).shift(1).bfill()

    def get_v4_weights(regime, use_soxl):
        w = {t: 0.0 for t in data.columns}
        semi = 'SOXL' if use_soxl else 'USD'
        if regime == 1:
            w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'] = 0.30, 0.20, 0.20, 0.15, 0.10
        elif regime == 2:
            w['QLD'], w['SSO'], w['GLD'], w['QQQ'], w['USD'] = 0.25, 0.20, 0.20, 0.15, 0.10
        elif regime == 3:
            w['GLD'], w['QQQ'], w['SPY'] = 0.35, 0.20, 0.10
        elif regime == 4:
            w['GLD'], w['QQQ'] = 0.50, 0.10
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
        for s in ['QQQ', 'QLD', 'TQQQ', 'SPY']:
            ports[s] *= (1 + daily_returns[s].iloc[i])

        for t in data.columns:
            if ports['AMLS v4'] > 0:
                weights_v4[t] = (weights_v4[t] * (1 + daily_returns[t].iloc[i])) / (1 + ret_v4)

        if today.month != yesterday.month:
            for s in strategies:
                ports[s] += monthly_cont
            total_invested += monthly_cont

        invested_hist.append(total_invested)
        for s in strategies:
            hists[s].append(ports[s])

        today_reg = df['Signal_Regime'].iloc[i]
        if today.month != yesterday.month or today_reg != df['Signal_Regime'].iloc[i-1] or i == 1:
            use_soxl = (df['SMH'].iloc[i-1] > df['SMH_MA50'].iloc[i-1]) and \
                       (df['SMH_3M_Ret'].iloc[i-1] > 0.05) and \
                       (df['SMH_RSI'].iloc[i-1] > 50)
            weights_v4 = get_v4_weights(today_reg, use_soxl)

            log_type = "레짐 전환" if today_reg != df['Signal_Regime'].iloc[i-1] else "월간 정기"
            logs.append({
                "날짜": today.strftime('%Y-%m-%d'),
                "유형": log_type,
                "국면": "Regime {}".format(int(today_reg)),
                "반도체 스위칭": "SOXL (3x)" if use_soxl and today_reg == 1 else ("USD (2x)" if today_reg in [1, 2] else "-"),
                "평가액": ports['AMLS v4']
            })

    for s in strategies:
        df['{}_Value'.format(s)] = hists[s]
    df['Invested'] = invested_hist

    return df, logs, data.columns


with st.spinner('🚀 퀀트 엔진을 가동하여 시장 데이터를 연산 중입니다...'):
    df, full_logs, tickers = load_and_calculate_data(BACKTEST_START, BACKTEST_END, INITIAL_CAPITAL, MONTHLY_CONTRIBUTION)
    strategies = ['AMLS v4', 'QQQ', 'QLD', 'TQQQ', 'SPY']


# ════════════════════════════════════════════════════════════
# 섹션 0. 실시간 시장 레이더
# ════════════════════════════════════════════════════════════
today_status = df.iloc[-1]
date_str = df.index[-1].strftime('%Y년 %m월 %d일')

st.subheader("📡 0. 실시간 시장 레이더 ({} 종가 기준)".format(date_str))

m1, m2, m3, m4 = st.columns(4)
m1.metric("현재 적용 국면", "Regime {}".format(int(today_status['Signal_Regime'])))
m2.metric("공포 지수 (VIX)", "{:.2f}".format(today_status['^VIX']))
m3.metric("누적 투입 원금", "${:,.0f}".format(df['Invested'].iloc[-1]))
m4.metric("AMLS 최종 자산", "${:,.0f}".format(df['AMLS v4_Value'].iloc[-1]))

st.markdown("##### 🔍 나스닥 (QQQ) 기술적 지표")
q1, q2, q3, q4 = st.columns(4)
qqq_close = today_status['QQQ']
ma50 = today_status['QQQ_MA50']
ma200 = today_status['QQQ_MA200']
rsi14 = today_status['QQQ_RSI']
dist_50 = (qqq_close / ma50 - 1) * 100
dist_200 = (qqq_close / ma200 - 1) * 100

q1.metric("QQQ 종가", "${:.2f}".format(qqq_close))
q2.metric("50일 이평선 (추세선)", "${:.2f}".format(ma50), "{:.2f}% (이격도)".format(dist_50))
q3.metric("200일 이평선 (생명선)", "${:.2f}".format(ma200), "{:.2f}% (이격도)".format(dist_200))
q4.metric("RSI 14 (과매수/과매도)", "{:.2f}".format(rsi14), "70 이상 과열 / 30 이하 침체", delta_color="off")

st.divider()


# ════════════════════════════════════════════════════════════
# 섹션 1. 국면별 포트폴리오 비율 (도넛 차트)
# ════════════════════════════════════════════════════════════
st.subheader("🍩 1. 국면별 포트폴리오 비율 (Regime Allocation)")

def get_v4_weights_for_plot(regime):
    w = {t: 0.0 for t in tickers}
    if regime == 1:
        w['TQQQ'], w['SOXL/USD'], w['QLD'], w['SSO'], w['GLD'], w['현금'] = 30, 20, 20, 15, 10, 5
    elif regime == 2:
        w['QLD'], w['SSO'], w['GLD'], w['QQQ'], w['USD'], w['현금'] = 25, 20, 20, 15, 10, 10
    elif regime == 3:
        w['GLD'], w['현금'], w['QQQ'], w['SPY'] = 35, 35, 20, 10
    elif regime == 4:
        w['GLD'], w['현금'], w['QQQ'] = 50, 40, 10
    return {k: v for k, v in w.items() if v > 0}

col1, col2, col3, col4 = st.columns(4)
colors = {
    'TQQQ': '#e74c3c', 'SOXL/USD': '#8e44ad', 'USD': '#9b59b6',
    'QLD': '#e67e22', 'SSO': '#f39c12', 'QQQ': '#3498db',
    'SPY': '#2980b9', 'GLD': '#f1c40f', '현금': '#2ecc71'
}

for idx, col in enumerate([col1, col2, col3, col4]):
    reg = idx + 1
    w = get_v4_weights_for_plot(reg)
    fig_pie = go.Figure(data=[go.Pie(
        labels=list(w.keys()), values=list(w.values()), hole=.5,
        marker=dict(colors=[colors.get(k, '#95a5a6') for k in w.keys()])
    )])
    fig_pie.update_layout(
        title_text="Regime {}".format(reg), title_x=0.5,
        margin=dict(t=30, b=0, l=0, r=0), height=250, showlegend=False
    )
    fig_pie.update_traces(textinfo='label+percent', textposition='inside')
    col.plotly_chart(fig_pie, use_container_width=True)

st.divider()


# ════════════════════════════════════════════════════════════
# 섹션 2. 핵심 지표 비교
# ════════════════════════════════════════════════════════════
st.subheader("📊 2. 핵심 지표 비교 (Key Metrics)")

def calc_metrics(series, invested):
    final = series.iloc[-1]
    total_ret = (final / invested.iloc[-1]) - 1
    days = (series.index[-1] - series.index[0]).days
    cagr = (final / invested.iloc[-1]) ** (365.25 / days) - 1 if days > 0 else 0
    mdd = ((series / series.cummax()) - 1).min()
    sharpe = (series.pct_change().mean() * 252) / (series.pct_change().std() * np.sqrt(252))
    return [
        "{:.1f}%".format(total_ret * 100),
        "{:.1f}%".format(cagr * 100),
        "{:.1f}%".format(mdd * 100),
        "{:.2f}".format(sharpe),
        "${:,.0f}".format(final)
    ]

metrics_rows = [calc_metrics(df['{}_Value'.format(s)], df['Invested']) for s in strategies]
metrics_df = pd.DataFrame(
    metrics_rows, index=strategies,
    columns=['총 수익률', '연평균 수익률(CAGR)', '최대 낙폭(MDD)', '샤프 지수', '최종 자산($)']
)
st.dataframe(
    metrics_df.style
    .highlight_max(subset=['연평균 수익률(CAGR)', '최종 자산($)'], color='lightgreen')
    .highlight_min(subset=['최대 낙폭(MDD)'], color='lightcoral'),
    use_container_width=True
)

st.divider()


# ════════════════════════════════════════════════════════════
# 섹션 3. 연도별 수익률
# ════════════════════════════════════════════════════════════
st.subheader("📅 3. 연도별 수익률 (Yearly Returns)")

years = df.index.year.unique()
yearly_ret = pd.DataFrame(index=strategies, columns=[str(y) for y in years])
for y in years:
    for s in strategies:
        y_data = df[df.index.year == y]['{}_Value'.format(s)]
        yearly_ret.loc[s, str(y)] = "{:.1f}%".format((y_data.iloc[-1] / y_data.iloc[0] - 1) * 100)
st.dataframe(yearly_ret, use_container_width=True)

st.divider()


# ════════════════════════════════════════════════════════════
# 섹션 4. 자산 성장 및 Drawdown 비교
# ════════════════════════════════════════════════════════════
st.subheader("📉 4. 자산 성장 및 계좌 낙폭 (Drawdown) 비교")

fig = make_subplots(
    rows=2, cols=1, shared_xaxes=True,
    row_heights=[0.7, 0.3], vertical_spacing=0.05
)

line_colors = ['#8e44ad', '#3498db', '#f39c12', '#e74c3c', '#2c3e50']
for s, c in zip(strategies, line_colors):
    fig.add_trace(go.Scatter(
        x=df.index, y=df['{}_Value'.format(s)], name=s,
        line=dict(color=c, width=3 if s == 'AMLS v4' else 1.5)
    ), row=1, col=1)
    dd = (df['{}_Value'.format(s)] / df['{}_Value'.format(s)].cummax()) - 1
    fig.add_trace(go.Scatter(
        x=df.index, y=dd * 100, name='{} DD'.format(s),
        line=dict(color=c, width=1.5 if s == 'AMLS v4' else 1,
                  dash='solid' if s == 'AMLS v4' else 'dot')
    ), row=2, col=1)

fig.add_trace(go.Scatter(
    x=df.index, y=df['Invested'], name='누적 원금',
    line=dict(color='black', width=2, dash='dash')
), row=1, col=1)
fig.update_yaxes(type="log", row=1, col=1)
fig.add_hline(y=-20, line_dash="dash", line_color="red", row=2, col=1, annotation_text="-20% 방어선")
fig.update_layout(
    height=800, margin=dict(l=0, r=0, t=30, b=0),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
st.plotly_chart(fig, use_container_width=True)

st.divider()


# ════════════════════════════════════════════════════════════
# 섹션 5. 레짐 체류 분포
# ════════════════════════════════════════════════════════════
st.subheader("⏱️ 5. 레짐 체류 일자 (Regime Distribution)")

regime_counts = df['Signal_Regime'].value_counts().sort_index()
reg_df = pd.DataFrame({
    "국면": ["Regime {}".format(int(r)) for r in [1, 2, 3, 4]],
    "체류 일수": ["{}일".format(regime_counts.get(r, 0)) for r in [1, 2, 3, 4]],
    "비율(%)": ["{:.1f}%".format(regime_counts.get(r, 0) / len(df) * 100) for r in [1, 2, 3, 4]]
})
st.dataframe(reg_df, hide_index=True, use_container_width=True)

st.divider()


# ════════════════════════════════════════════════════════════
# 섹션 6. 전체 리밸런싱 로그
# ════════════════════════════════════════════════════════════
st.subheader("📋 6. 전체 리밸런싱 이력 (Rebalance Logs)")
st.markdown("최근 발생한 리밸런싱 내역부터 역순으로 보여줍니다.")
logs_df = pd.DataFrame(full_logs)[::-1]
logs_df['평가액'] = logs_df['평가액'].apply(lambda x: "${:,.0f}".format(x))
st.dataframe(logs_df, hide_index=True, use_container_width=True, height=400)
