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

# --- 페이지 기본 설정 (가장 위에 있어야 함) ---
st.set_page_config(page_title="AMLS v4 퀀트 관제탑", layout="wide", initial_sidebar_state="expanded")

# --- 데이터 영구 보존을 위한 파일 세팅 (포트폴리오용) ---
DATA_FILE = "amls_portfolio_data.json"

def load_portfolio_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
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
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# --- 메인 네비게이션 사이드바 ---
st.sidebar.title("🦅 AMLS v4 관제탑")
app_mode = st.sidebar.radio("원하시는 메뉴를 선택하세요", ["1. 📈 AMLS 백테스트 대시보드", "2. 💼 내 실전 포트폴리오 관리"])
st.sidebar.markdown("---")

# =====================================================================
# 1. AMLS 백테스트 대시보드 모드
# =====================================================================
if app_mode == "1. 📈 AMLS 백테스트 대시보드":
    st.title("🛡️ AMLS v4 퀀트 투자 대시보드 (Final Edition)")

    st.sidebar.header("⚙️ 백테스트 설정")
    st.sidebar.markdown("이곳에서 설정값을 바꾸면 대시보드가 실시간으로 다시 계산됩니다.")
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
            w = {t: 0.0 for t in data.columns}
            semi = 'SOXL' if use_soxl else 'USD'
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
        return df, logs, data.columns

    with st.spinner('🚀 퀀트 엔진을 가동하여 시장 데이터를 연산 중입니다...'):
        df, full_logs, tickers = load_and_calculate_data(BACKTEST_START, BACKTEST_END, INITIAL_CAPITAL, MONTHLY_CONTRIBUTION)
        strategies = ['AMLS v4', 'QQQ', 'QLD', 'TQQQ', 'SPY']

    # --- 실시간 시장 레이더 ---
    today_status = df.iloc[-1]
    date_str = df.index[-1].strftime('%Y년 %m월 %d일')

    st.subheader(f"📡 0. 실시간 시장 레이더 ({date_str} 종가 기준)")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("현재 적용 국면", f"Regime {int(today_status['Signal_Regime'])}")
    m2.metric("공포 지수 (VIX)", f"{today_status['^VIX']:.2f}")
    m3.metric("누적 투입 원금", f"${df['Invested'].iloc[-1]:,.0f}")
    m4.metric("AMLS 최종 자산", f"${df['AMLS v4_Value'].iloc[-1]:,.0f}")

    st.markdown("##### 🔍 나스닥 (QQQ) 기술적 지표")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("QQQ 종가", f"${today_status['QQQ']:.2f}")
    q2.metric("50일 이평선 (추세선)", f"${today_status['QQQ_MA50']:.2f}", f"{(today_status['QQQ'] / today_status['QQQ_MA50'] - 1) * 100:.2f}% (이격도)")
    q3.metric("200일 이평선 (생명선)", f"${today_status['QQQ_MA200']:.2f}", f"{(today_status['QQQ'] / today_status['QQQ_MA200'] - 1) * 100:.2f}% (이격도)")
    q4.metric("RSI 14 (과매수/과매도)", f"{today_status['QQQ_RSI']:.2f}", "70 이상 과열 / 30 이하 침체", delta_color="off")

    st.divider()

    # --- 1. 포트폴리오 비율 ---
    st.subheader("🍩 1. 국면별 포트폴리오 비율 (Regime Allocation)")
    def get_v4_weights_for_plot(regime):
        w = {t: 0.0 for t in tickers}
        if regime == 1: w['TQQQ'], w['SOXL/USD'], w['QLD'], w['SSO'], w['GLD'], w['현금'] = 30, 20, 20, 15, 10, 5
        elif regime == 2: w['QLD'], w['SSO'], w['GLD'], w['QQQ'], w['USD'], w['현금'] = 25, 20, 20, 15, 10, 10
        elif regime == 3: w['GLD'], w['현금'], w['QQQ'], w['SPY'] = 35, 35, 20, 10
        elif regime == 4: w['GLD'], w['현금'], w['QQQ'] = 50, 40, 10
        return {k: v for k, v in w.items() if v > 0}

    col1, col2, col3, col4 = st.columns(4)
    colors = {'TQQQ': '#e74c3c', 'SOXL/USD': '#8e44ad', 'USD': '#9b59b6', 'QLD': '#e67e22', 'SSO': '#f39c12', 'QQQ': '#3498db', 'SPY': '#2980b9', 'GLD': '#f1c40f', '현금': '#2ecc71'}

    for idx, col in enumerate([col1, col2, col3, col4]):
        reg = idx + 1
        w = get_v4_weights_for_plot(reg)
        fig_pie = go.Figure(data=[go.Pie(labels=list(w.keys()), values=list(w.values()), hole=.5, marker=dict(colors=[colors.get(k, '#95a5a6') for k in w.keys()]))])
        fig_pie.update_layout(title_text=f"Regime {reg}", title_x=0.5, margin=dict(t=30, b=0, l=0, r=0), height=250, showlegend=False)
        fig_pie.update_traces(textinfo='label+percent', textposition='inside')
        col.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # --- 2. 핵심 지표 ---
    st.subheader("📊 2. 핵심 지표 비교 (Key Metrics)")
    def calc_metrics(series, invested):
        final = series.iloc[-1]
        total_ret = (final / invested.iloc[-1]) - 1
        days = (series.index[-1] - series.index[0]).days
        cagr = (final / invested.iloc[-1]) ** (365.25 / days) - 1 if days > 0 else 0
        mdd = ((series / series.cummax()) - 1).min()
        sharpe = (series.pct_change().mean() * 252) / (series.pct_change().std() * np.sqrt(252))
        return [f"{total_ret * 100:.1f}%", f"{cagr * 100:.1f}%", f"{mdd * 100:.1f}%", f"{sharpe:.2f}", f"${final:,.0f}"]

    metrics_rows = [calc_metrics(df[f'{s}_Value'], df['Invested']) for s in strategies]
    metrics_df = pd.DataFrame(metrics_rows, index=strategies, columns=['총 수익률', '연평균 수익률(CAGR)', '최대 낙폭(MDD)', '샤프 지수', '최종 자산($)'])
    st.dataframe(metrics_df.style.highlight_max(subset=['연평균 수익률(CAGR)', '최종 자산($)'], color='lightgreen').highlight_min(subset=['최대 낙폭(MDD)'], color='lightcoral'), use_container_width=True)

    st.divider()

    # --- 3. 연도별 수익률 ---
    st.subheader("📅 3. 연도별 수익률 (Yearly Returns)")
    years = df.index.year.unique()
    yearly_ret = pd.DataFrame(index=strategies, columns=[str(y) for y in years])
    for y in years:
        for s in strategies:
            y_data = df[df.index.year == y][f'{s}_Value']
            yearly_ret.loc[s, str(y)] = f"{(y_data.iloc[-1] / y_data.iloc[0] - 1) * 100:.1f}%"
    st.dataframe(yearly_ret, use_container_width=True)

    st.divider()

    # --- 4. 자산 성장 및 Drawdown ---
    st.subheader("📉 4. 자산 성장 및 계좌 낙폭 (Drawdown) 비교")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    line_colors = ['#8e44ad', '#3498db', '#f39c12', '#e74c3c', '#2c3e50']
    
    for s, c in zip(strategies, line_colors):
        fig.add_trace(go.Scatter(x=df.index, y=df[f'{s}_Value'], name=s, line=dict(color=c, width=3 if s == 'AMLS v4' else 1.5)), row=1, col=1)
        dd = (df[f'{s}_Value'] / df[f'{s}_Value'].cummax()) - 1
        fig.add_trace(go.Scatter(x=df.index, y=dd * 100, name=f'{s} DD', line=dict(color=c, width=1.5 if s == 'AMLS v4' else 1, dash='solid' if s == 'AMLS v4' else 'dot')), row=2, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df['Invested'], name='누적 원금', line=dict(color='black', width=2, dash='dash')), row=1, col=1)
    fig.update_yaxes(type="log", row=1, col=1)
    fig.add_hline(y=-20, line_dash="dash", line_color="red", row=2, col=1, annotation_text="-20% 방어선")
    fig.update_layout(height=800, margin=dict(l=0, r=0, t=30, b=0), hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- 5. 레짐 체류 ---
    st.subheader("⏱️ 5. 레짐 체류 일자 (Regime Distribution)")
    regime_counts = df['Signal_Regime'].value_counts().sort_index()
    reg_df = pd.DataFrame({
        "국면": [f"Regime {int(r)}" for r in [1, 2, 3, 4]],
        "체류 일수": [f"{regime_counts.get(r, 0)}일" for r in [1, 2, 3, 4]],
        "비율(%)": [f"{regime_counts.get(r, 0) / len(df) * 100:.1f}%" for r in [1, 2, 3, 4]]
    })
    st.dataframe(reg_df, hide_index=True, use_container_width=True)

    st.divider()

    # --- 6. 리밸런싱 로그 ---
    st.subheader("📋 6. 전체 리밸런싱 이력 (Rebalance Logs)")
    logs_df = pd.DataFrame(full_logs)[::-1]
    logs_df['평가액'] = logs_df['평가액'].apply(lambda x: f"${x:,.0f}")
    st.dataframe(logs_df, hide_index=True, use_container_width=True, height=400)


# =====================================================================
# 2. 내 실전 포트폴리오 관리 모드
# =====================================================================
elif app_mode == "2. 💼 내 실전 포트폴리오 관리":
    st.title("💼 AMLS v4 실전 포트폴리오 트래커")
    st.markdown("현재 시장의 **AMLS 국면(Regime)**을 파악하고, 내 보유 종목의 **평균 단가 대비 수익률, 리밸런싱 지침**, **자산 성장 추이**를 추적합니다.")

    TICKERS = ['QQQ', 'TQQQ', 'SOXL', 'USD', 'QLD', 'SSO', 'SPY', 'SMH', 'GLD', '^VIX']

    def get_target_weights(regime, use_soxl):
        w = {t: 0.0 for t in TICKERS}
        semi = 'SOXL' if use_soxl else 'USD'
        if regime == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'], w['CASH'] = 0.30, 0.20, 0.20, 0.15, 0.10, 0.05
        elif regime == 2: w['QLD'], w['SSO'], w['GLD'], w['QQQ'], w['USD'], w['CASH'] = 0.25, 0.20, 0.20, 0.15, 0.10, 0.10
        elif regime == 3: w['GLD'], w['CASH'], w['QQQ'], w['SPY'] = 0.35, 0.35, 0.20, 0.10
        elif regime == 4: w['GLD'], w['CASH'], w['QQQ'] = 0.50, 0.40, 0.10
        return {k: v for k, v in w.items() if v > 0}

    @st.cache_data(ttl=1800)
    def get_market_regime():
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
        today = df.iloc[-1]
        vix, qqq, ma200, ma50 = today['^VIX'], today['QQQ'], today['QQQ_MA200'], today['QQQ_MA50']
        smh, smh_ma50, smh_3m_ret, smh_rsi = today['SMH'], today['SMH_MA50'], today['SMH_3M_Ret'], today['SMH_RSI']

        if vix > 40: regime = 4
        elif qqq < ma200: regime = 3
        elif qqq >= ma200 and ma50 >= ma200 and vix < 25: regime = 1
        else: regime = 2

        cond1, cond2, cond3 = smh > smh_ma50, smh_3m_ret > 0.05, smh_rsi > 50
        use_soxl = cond1 and cond2 and cond3
        
        target_w = get_target_weights(regime, use_soxl)
        semi_target = "SOXL (3배)" if use_soxl else "USD (2배)"
        if regime in [3, 4]: semi_target = "미보유 (대피)"
        elif regime == 2: semi_target = "USD (2배 - 축소)"

        return {
            'regime': regime, 'vix': vix, 'qqq': qqq, 'ma200': ma200, 'ma50': ma50,
            'smh': smh, 'smh_ma50': smh_ma50, 'smh_3m_ret': smh_3m_ret, 'smh_rsi': smh_rsi,
            'cond1': cond1, 'cond2': cond2, 'cond3': cond3,
            'semi_target': semi_target, 'date': today.name, 'target_weights': target_w,
            'latest_prices': {t: today[t] for t in TICKERS if t != '^VIX'}
        }

    with st.spinner("시장 국면을 정밀 판독 중입니다..."):
        mr = get_market_regime()

    st.subheader("🧭 0. AMLS v4 시장 레이더 & 리밸런싱 지침")
    st.info(f"기준일: **{mr['date'].strftime('%Y년 %m월 %d일')} 종가**")

    r_col1, r_col2, r_col3, r_col4 = st.columns(4)
    r_col1.metric("📌 오늘의 확정 국면", f"Regime {mr['regime']}")
    r_col2.metric("📌 공포 지수 (VIX)", f"{mr['vix']:.2f}")
    r_col3.metric("📌 QQQ 200일선 이격도", f"{(mr['qqq'] / mr['ma200'] - 1) * 100:.2f}%")
    r_col4.metric("📌 반도체 스위칭 타겟", f"{mr['semi_target']}")

    col_ind1, col_ind2 = st.columns(2)
    with col_ind1:
        st.markdown("##### 🎯 레짐 판단 3대 핵심 지표")
        vix_text = f"**1. VIX:** 현재 {mr['vix']:.2f} ➔ **{'위험 (>40)' if mr['vix'] > 40 else ('경계 (>25)' if mr['vix'] >= 25 else '안정 (<25)')}**"
        if mr['vix'] > 40: st.error(vix_text, icon="🚨")
        elif mr['vix'] >= 25: st.warning(vix_text, icon="⚠️")
        else: st.success(vix_text, icon="✅")
        
        qqq_text = f"**2. 장기 추세:** QQQ(${mr['qqq']:.2f}) vs 200일선(${mr['ma200']:.2f})"
        if mr['qqq'] >= mr['ma200']: st.success(qqq_text + " ➔ **상승 (위)**", icon="✅")
        else: st.error(qqq_text + " ➔ **하락 (아래)**", icon="🚨")
        
        cross_text = f"**3. 배열:** 50일선(${mr['ma50']:.2f}) vs 200일선(${mr['ma200']:.2f})"
        if mr['ma50'] >= mr['ma200']: st.success(cross_text + " ➔ **정배열**", icon="✅")
        else: st.error(cross_text + " ➔ **역배열**", icon="🚨")

    with col_ind2:
        st.markdown("##### ⚡ 반도체(SOXL) 진입 모멘텀 지표")
        if mr['cond1']: st.success(f"**1. 단기 추세:** SMH > 50일선 ➔ **합격**", icon="✅")
        else: st.error(f"**1. 단기 추세:** SMH < 50일선 ➔ **미달**", icon="❌")
        
        if mr['cond2']: st.success(f"**2. 수익률:** 최근 3개월 ({mr['smh_3m_ret']*100:.2f}%) ➔ **합격**", icon="✅")
        else: st.error(f"**2. 수익률:** 최근 3개월 ({mr['smh_3m_ret']*100:.2f}%) ➔ **미달**", icon="❌")
        
        if mr['cond3']: st.success(f"**3. 모멘텀:** RSI ({mr['smh_rsi']:.1f}) > 50 ➔ **합격**", icon="✅")
        else: st.error(f"**3. 모멘텀:** RSI ({mr['smh_rsi']:.1f}) < 50 ➔ **미달**", icon="❌")

    st.divider()

    st.subheader("📝 1. 내 포트폴리오 기입란 & 수익률/리밸런싱 현황판")
    st.markdown("💡 표 안의 숫자를 **더블 클릭**하여 수량과 평단가(소수점 2자리)를 입력하세요.")

    if 'init_portfolio' not in st.session_state:
        saved_data = load_portfolio_data()
        if saved_data and len(saved_data.get("portfolio", [])) > 0:
            pf_df = pd.DataFrame(saved_data["portfolio"])
            pf_df["수량 (주/달러)"] = pf_df["수량 (주/달러)"].astype(float)
            pf_df["평균 단가 ($)"] = pf_df["평균 단가 ($)"].astype(float)
            st.session_state['init_portfolio'] = pf_df
            st.session_state['portfolio_history'] = saved_data.get("history", [])
            fd = saved_data.get("first_entry_date")
            st.session_state['first_entry_date'] = datetime.fromisoformat(fd) if fd else None
            st.session_state['journal_text'] = saved_data.get("journal_text", "")
        else:
            initial_df = pd.DataFrame({
                "티커 (Ticker)": ["TQQQ", "QLD", "QQQ", "SOXL", "USD", "GLD", "CASH"],
                "수량 (주/달러)": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "평균 단가 ($)": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            })
            st.session_state['init_portfolio'] = initial_df
            st.session_state['portfolio_history'] = []
            st.session_state['first_entry_date'] = None
            st.session_state['journal_text'] = ""

        st.session_state['last_portfolio'] = st.session_state['init_portfolio'].copy()

    col_table, col_chart = st.columns([1, 1.5])

    with col_table:
        edited_df = st.data_editor(
            st.session_state['init_portfolio'],
            num_rows="dynamic",
            key="portfolio_editor",
            use_container_width=True,
            column_config={
                "티커 (Ticker)": st.column_config.TextColumn("티커 (Ticker)"),
                "수량 (주/달러)": st.column_config.NumberColumn("수량", min_value=0.0, format="%.2f", step=0.1),
                "평균 단가 ($)": st.column_config.NumberColumn("평균 단가 ($)", min_value=0.0, format="%.2f", step=0.1)
            }
        )

        def get_portfolio_state(df):
            state = {}
            for _, row in df.iterrows():
                tkr = str(row["티커 (Ticker)"]).upper().strip()
                if tkr and tkr.lower() not in ['nan', 'none', '']:
                    try: qty = float(row["수량 (주/달러)"])
                    except: qty = 0.0
                    try: avg_p = float(row["평균 단가 ($)"])
                    except: avg_p = 0.0
                    if tkr in state:
                        state[tkr]['qty'] += qty
                        state[tkr]['avg_p'] = avg_p
                    else:
                        state[tkr] = {'qty': qty, 'avg_p': avg_p}
            return state

        old_state = get_portfolio_state(st.session_state['last_portfolio'])
        new_state = get_portfolio_state(edited_df)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        changes_made = False

        if not edited_df.equals(st.session_state['last_portfolio']):
            for tkr, old_val in old_state.items():
                if tkr in new_state:
                    new_val = new_state[tkr]
                    if old_val['qty'] != new_val['qty']:
                        st.session_state['portfolio_history'].append({"변경 일시": now_str, "티커": tkr, "상태": "수량 변경 🔄", "변경 전": f"{old_val['qty']:.2f}", "변경 후": f"{new_val['qty']:.2f}"})
                        changes_made = True
                    if old_val['avg_p'] != new_val['avg_p']:
                        st.session_state['portfolio_history'].append({"변경 일시": now_str, "티커": tkr, "상태": "평단가 변경 💰", "변경 전": f"${old_val['avg_p']:.2f}", "변경 후": f"${new_val['avg_p']:.2f}"})
                        changes_made = True
                else:
                    st.session_state['portfolio_history'].append({"변경 일시": now_str, "티커": tkr, "상태": "항목 삭제 ❌", "변경 전": f"{old_val['qty']:.2f}", "변경 후": "삭제됨"})
                    changes_made = True

            for tkr, new_val in new_state.items():
                if tkr not in old_state:
                    st.session_state['portfolio_history'].append({"변경 일시": now_str, "티커": tkr, "상태": "신규 추가 🟢", "변경 전": "없음", "변경 후": f"{new_val['qty']:.2f}"})
                    changes_made = True
                    if st.session_state['first_entry_date'] is None and new_val['qty'] > 0:
                        st.session_state['first_entry_date'] = datetime.now()

            if changes_made:
                st.session_state['last_portfolio'] = edited_df.copy()
                save_portfolio_data(edited_df, st.session_state['portfolio_history'], st.session_state['first_entry_date'], st.session_state['journal_text'])

    with col_chart:
        asset_values = {}
        total_invested_principal = 0.0 
        
        for _, row in edited_df.iterrows():
            tkr = str(row["티커 (Ticker)"]).upper().strip()
            try: 
                shares = float(row["수량 (주/달러)"])
                avg_price = float(row.get("평균 단가 ($)", 0.0))
            except: 
                shares, avg_price = 0.0, 0.0
                
            if shares > 0:
                if tkr == "CASH":
                    asset_values[tkr] = asset_values.get(tkr, 0) + shares
                    total_invested_principal += shares
                else:
                    curr_price = mr['latest_prices'].get(tkr, 0.0)
                    if curr_price > 0:
                        asset_values[tkr] = asset_values.get(tkr, 0) + (shares * curr_price)
                    if avg_price > 0:
                        total_invested_principal += (shares * avg_price)
                    
        total_value = sum(asset_values.values()) if asset_values else 0.0

        if total_value > 0:
            fig_bar = go.Figure()
            palette = ['#e74c3c', '#3498db', '#f1c40f', '#2ecc71', '#9b59b6', '#e67e22', '#1abc9c', '#34495e']
            sorted_assets = sorted(asset_values.items(), key=lambda x: x[1], reverse=True)
            
            for idx, (tkr, val) in enumerate(sorted_assets):
                weight = (val / total_value) * 100
                fig_bar.add_trace(go.Bar(
                    y=['내 포트폴리오 비중'], x=[weight], name=tkr, orientation='h',
                    text=f"<b>{tkr}</b><br>{weight:.1f}%", textposition='inside', insidetextanchor='middle',
                    marker=dict(color=palette[idx % len(palette)], line=dict(color='white', width=1.5)),
                    hoverinfo='text', hovertext=f"{tkr}: ${val:,.0f} ({weight:.1f}%)"
                ))

            fig_bar.update_layout(
                barmode='stack', height=200, margin=dict(l=0, r=0, t=40, b=0),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, 100]),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                showlegend=False,
                title=dict(text=f"총 자산 평가액: <b>${total_value:,.0f}</b>", font=dict(size=18), x=0.5, xanchor='center')
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("수량을 기입하시면 비중 그래프가 나타납니다.")

    st.write("")
    st.markdown("##### 💵 종목별 수익률 & 리밸런싱 액션 지침")
    st.markdown("현재 평가액과 오늘의 Regime 목표 비중을 비교하여 **부족한 것은 [매수], 넘치는 것은 [매도]**를 지시합니다.")

    status_data = []
    all_tickers = set([t for t in asset_values.keys()] + list(mr['target_weights'].keys()))

    for tkr in all_tickers:
        tkr = tkr.upper()
        my_val = asset_values.get(tkr, 0.0)
        my_weight = (my_val / total_value) * 100 if total_value > 0 else 0.0
        
        shares, avg_price = 0.0, 0.0
        for _, row in edited_df.iterrows():
            if str(row["티커 (Ticker)"]).upper().strip() == tkr:
                try: 
                    shares += float(row["수량 (주/달러)"])
                    avg_price = float(row.get("평균 단가 ($)", 0.0))
                except: pass
                
        target_w_dec = mr['target_weights'].get(tkr, 0.0)
        target_val = total_value * target_w_dec if total_value > 0 else 0.0
        
        diff_val = target_val - my_val
        if abs(diff_val) < 50: action = "적정 (유지)"
        elif diff_val > 0: action = f"🟢 약 ${diff_val:,.0f} 매수"
        else: action = f"🔴 약 ${abs(diff_val):,.0f} 매도"

        if shares > 0:
            if tkr == "CASH":
                ret_pct, ret_amt = 0.0, 0.0
            else:
                curr_price = mr['latest_prices'].get(tkr, 0.0)
                if avg_price > 0:
                    ret_pct = ((curr_price - avg_price) / avg_price) * 100
                    ret_amt = (curr_price - avg_price) * shares
                else:
                    ret_pct, ret_amt = 0.0, 0.0
        else:
            ret_pct, ret_amt = 0.0, 0.0

        if my_val > 0 or target_w_dec > 0:
            status_data.append({
                "종목": tkr, "현재 비중": f"{my_weight:.1f}%", "목표 비중": f"{target_w_dec*100:.1f}%",
                "평가액": f"${my_val:,.0f}", "목표액": f"${target_val:,.0f}", "리밸런싱 액션": action,
                "수익률": f"{ret_pct:+.2f}%" if shares > 0 and tkr != "CASH" else "-",
                "수익금": f"${ret_amt:+,.0f}" if shares > 0 and tkr != "CASH" else "-"
            })

    if status_data:
        status_df = pd.DataFrame(status_data).sort_values(by="목표 비중", ascending=False)
        def color_status(val):
            if type(val) == str:
                if '매수' in val or '+' in val: return 'color: #2ecc71; font-weight: bold;'
                elif '매도' in val or ('-' in val and val != '-'): return 'color: #e74c3c; font-weight: bold;'
                elif '유지' in val: return 'color: #95a5a6;'
            return ''
        st.dataframe(status_df.style.map(color_status, subset=['리밸런싱 액션', '수익률', '수익금']), hide_index=True, use_container_width=True)

    st.divider()

    if total_value > 0:
        with st.spinner("자산 가치 추이를 계산 중입니다..."):
            st.subheader("📈 2. 포트폴리오 가치 추이 및 순수익")
            
            default_date = st.session_state.get('first_entry_date')
            if default_date is None: default_date = datetime.today() - timedelta(days=90)
                
            col_date, _ = st.columns([1, 2])
            with col_date:
                user_start_date = st.date_input("📅 포트폴리오 매수 시작일 (이 날짜부터 차트 생성)", value=default_date)
                st.session_state['first_entry_date'] = datetime.combine(user_start_date, datetime.min.time())
                save_portfolio_data(st.session_state['init_portfolio'], st.session_state['portfolio_history'], st.session_state['first_entry_date'], st.session_state['journal_text'])

            v_col1, v_col2, v_col3 = st.columns(3)
            pure_profit = total_value - total_invested_principal
            profit_pct = (pure_profit / total_invested_principal * 100) if total_invested_principal > 0 else 0.0
            
            v_col1.metric("내 평가액 총합", f"${total_value:,.2f}")
            v_col2.metric("내가 넣은 원금 총합", f"${total_invested_principal:,.2f}")
            v_col3.metric("누적 순수익금", f"${pure_profit:+,.2f}", f"{profit_pct:+.2f}% 수익률")

            chart_start_ts = pd.Timestamp(user_start_date)
            fetch_start = (chart_start_ts - timedelta(days=10)).strftime('%Y-%m-%d') 
            
            try:
                benchmark_index = yf.download("QQQ", start=fetch_start, progress=False)['Close'].index
                portfolio_value_series = pd.Series(0.0, index=benchmark_index)
                principal_series = pd.Series(0.0, index=benchmark_index)

                for _, row in edited_df.iterrows():
                    tkr = str(row["티커 (Ticker)"]).upper().strip()
                    try: 
                        shares = float(row["수량 (주/달러)"])
                        avg_p = float(row.get("평균 단가 ($)", 0.0))
                    except: 
                        shares, avg_p = 0.0, 0.0
                        
                    if shares > 0:
                        if tkr == "CASH":
                            portfolio_value_series += shares
                            principal_series += shares
                        else:
                            try:
                                stock_series = yf.download(tkr, start=fetch_start, progress=False)['Close']
                                if not stock_series.empty:
                                    if isinstance(stock_series, pd.DataFrame): stock_series = stock_series.iloc[:, 0]
                                    stock_series = stock_series.reindex(benchmark_index).ffill().fillna(0)
                                    portfolio_value_series += stock_series * shares
                                    principal_series += (shares * avg_p)
                            except: pass

                portfolio_value_series = portfolio_value_series.dropna()
                principal_series = principal_series.dropna()
                
                portfolio_value_series = portfolio_value_series[portfolio_value_series.index >= chart_start_ts]
                principal_series = principal_series[principal_series.index >= chart_start_ts]

                if len(portfolio_value_series) > 0:
