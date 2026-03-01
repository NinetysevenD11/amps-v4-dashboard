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

# 탭 이동 시 데이터 증발 방지를 위한 글로벌 세션 초기화
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

# --- 메인 네비게이션 사이드바 ---
st.sidebar.markdown("### 🦅 AMLS v4 관제탑")
app_mode = st.sidebar.radio("모드 선택", ["[1] 백테스트 시뮬레이터", "[2] 실전 포트폴리오 관리"])
st.sidebar.markdown("---")

# =====================================================================
# 1. AMLS 백테스트 대시보드 모드
# =====================================================================
if app_mode == "[1] 백테스트 시뮬레이터":
    st.title("AMLS v4 퀀트 백테스트 엔진")
    st.markdown("과거 데이터를 바탕으로 AMLS v4 전략의 성과와 국면별 특징을 시뮬레이션합니다.")

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

        current_regime, pending_regime, confirm_count = 3, None, 0
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
                semi_target = "SOXL (3x)" if use_soxl and today_reg == 1 else ("USD (2x)" if today_reg in [1, 2] else "-")
                
                logs.append({
                    "날짜": today.strftime('%Y-%m-%d'), "유형": log_type, "국면": f"Regime {int(today_reg)}",
                    "반도체 스위칭": semi_target, "평가액": ports['AMLS v4']
                })

        for s in strategies: df[f'{s}_Value'] = hists[s]
        df['Invested'] = invested_hist
        return df, logs, data.columns

    with st.spinner('퀀트 엔진을 가동하여 시장 데이터를 연산 중입니다...'):
        df, full_logs, tickers = load_and_calculate_data(BACKTEST_START, BACKTEST_END, INITIAL_CAPITAL, MONTHLY_CONTRIBUTION)
        strategies = ['AMLS v4', 'QQQ', 'QLD', 'TQQQ', 'SPY']

    today_status = df.iloc[-1]
    date_str = df.index[-1].strftime('%Y년 %m월 %d일')

    # --- 백테스트 레이더 ---
    with st.container(border=True):
        st.markdown(f"**[ 실시간 시장 레이더 ]** &nbsp; | &nbsp; 기준일: {date_str} 종가")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("현재 적용 국면", f"Regime {int(today_status['Signal_Regime'])}")
        m2.metric("공포 지수 (VIX)", f"{today_status['^VIX']:.2f}")
        m3.metric("누적 투입 원금", f"${df['Invested'].iloc[-1]:,.0f}")
        m4.metric("AMLS 최종 자산", f"${df['AMLS v4_Value'].iloc[-1]:,.0f}")
        
        st.divider()
        st.markdown("**🔍 나스닥 (QQQ) 기술적 지표**")
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("QQQ 종가", f"${today_status['QQQ']:.2f}")
        q2.metric("50일 이평선 (추세선)", f"${today_status['QQQ_MA50']:.2f}", f"{(today_status['QQQ'] / today_status['QQQ_MA50'] - 1) * 100:.2f}% (이격도)")
        q3.metric("200일 이평선 (생명선)", f"${today_status['QQQ_MA200']:.2f}", f"{(today_status['QQQ'] / today_status['QQQ_MA200'] - 1) * 100:.2f}% (이격도)")
        q4.metric("RSI 14 (과열/침체)", f"{today_status['QQQ_RSI']:.2f}", "70 이상 과열 / 30 이하 침체", delta_color="off")

    st.write("")

    # --- 백테스트 차트 및 표 ---
    st.markdown("**[ 국면별 포트폴리오 목표 비중 ]**")
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
        st.markdown("**[ 연도별 수익률 ]**")
        years = df.index.year.unique()
        yearly_ret = pd.DataFrame(index=strategies, columns=[str(y) for y in years])
        for y in years:
            for s in strategies:
                y_data = df[df.index.year == y][f'{s}_Value']
                yearly_ret.loc[s, str(y)] = f"{(y_data.iloc[-1] / y_data.iloc[0] - 1) * 100:.1f}%"
        st.dataframe(yearly_ret, use_container_width=True)

    st.write("")
    st.markdown("**[ 자산 성장 및 계좌 낙폭 (Drawdown) ]**")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    line_colors = ['#8e44ad', '#3498db', '#f39c12', '#e74c3c', '#2c3e50']
    
    for s, c in zip(strategies, line_colors):
        fig.add_trace(go.Scatter(x=df.index, y=df[f'{s}_Value'], name=s, line=dict(color=c, width=3 if s == 'AMLS v4' else 1.5)), row=1, col=1)
        dd = (df[f'{s}_Value'] / df[f'{s}_Value'].cummax()) - 1
        fig.add_trace(go.Scatter(x=df.index, y=dd * 100, name=f'{s} DD', line=dict(color=c, width=1.5 if s == 'AMLS v4' else 1, dash='solid' if s == 'AMLS v4' else 'dot')), row=2, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df['Invested'], name='누적 투입 원금', line=dict(color='black', width=2, dash='dash')), row=1, col=1)
    fig.update_yaxes(type="log", row=1, col=1)
    fig.add_hline(y=-20, line_dash="dash", line_color="red", row=2, col=1, annotation_text="-20% 방어선")
    fig.update_layout(height=600, margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)

    col_dist, col_log = st.columns([1, 2])
    with col_dist:
        st.markdown("**[ 레짐 체류 일자 분포 ]**")
        regime_counts = df['Signal_Regime'].value_counts().sort_index()
        reg_df = pd.DataFrame({
            "국면": [f"Regime {int(r)}" for r in [1, 2, 3, 4]],
            "일수": [f"{regime_counts.get(r, 0)}일" for r in [1, 2, 3, 4]],
            "비율": [f"{regime_counts.get(r, 0) / len(df) * 100:.1f}%" for r in [1, 2, 3, 4]]
        })
        st.dataframe(reg_df, hide_index=True, use_container_width=True)
        
    with col_log:
        st.markdown("**[ 전체 리밸런싱 이력 (최근순) ]**")
        logs_df = pd.DataFrame(full_logs)[::-1]
        logs_df['평가액'] = logs_df['평가액'].apply(lambda x: f"${x:,.0f}")
        st.dataframe(logs_df, hide_index=True, use_container_width=True, height=200)


# =====================================================================
# 2. 내 실전 포트폴리오 관리 모드
# =====================================================================
elif app_mode == "[2] 실전 포트폴리오 관리":
    st.title("AMLS 실전 포트폴리오 관제탑")
    st.markdown("현재 시장 상태를 파악하고, 내 포트폴리오의 실시간 수익률 및 리밸런싱 지침을 확인합니다.", help="입력된 데이터는 로컬 환경에 자동 보존됩니다.")

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
        for t in TICKERS:
            df[t] = data[t]
        
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

    # --- 실시간 레이더 패널 (상세 지표 복구됨) ---
    with st.container(border=True):
        st.markdown(f"**[ 시장 레이더 요약 ]** &nbsp; | &nbsp; 기준일: {mr['date'].strftime('%Y-%m-%d')}")
        r_col1, r_col2, r_col3, r_col4 = st.columns(4)
        
        regime_color = "#e74c3c" if mr['regime'] >= 3 else "#2ecc71"
        r_col1.markdown(f"현재 확정 국면<br><span style='font-size: 24px; font-weight: bold; color: {regime_color};'>Regime {mr['regime']}</span>", unsafe_allow_html=True)
        r_col2.metric("공포 지수 (VIX)", f"{mr['vix']:.2f}")
        r_col3.metric("QQQ 200일선 이격도", f"{(mr['qqq'] / mr['ma200'] - 1) * 100:+.2f}%")
        r_col4.markdown(f"반도체 스위칭 타겟<br><span style='font-size: 20px; font-weight: bold; color: #3498db;'>{mr['semi_target']}</span>", unsafe_allow_html=True)
        
        st.divider()
        col_ind1, col_ind2 = st.columns(2)
        with col_ind1:
            st.markdown("##### 🎯 레짐 판단 3대 핵심 지표")
            if mr['vix'] > 40: st.error(f"**1. VIX:** 현재 {mr['vix']:.2f} ➔ **위험 (>40)**", icon="🚨")
            elif mr['vix'] >= 25: st.warning(f"**1. VIX:** 현재 {mr['vix']:.2f} ➔ **경계 (>25)**", icon="⚠️")
            else: st.success(f"**1. VIX:** 현재 {mr['vix']:.2f} ➔ **안정 (<25)**", icon="✅")
            
            qqq_text = f"**2. 장기 추세:** QQQ(${mr['qqq']:.2f}) vs 200일선(${mr['ma200']:.2f})"
            if mr['qqq'] >= mr['ma200']: st.success(qqq_text + " ➔ **상승 (위)**", icon="✅")
            else: st.error(qqq_text + " ➔ **하락 (아래)**", icon="🚨")
            
            cross_text = f"**3. 배열:** 50일선(${mr['ma50']:.2f}) vs 200일선(${mr['ma200']:.2f})"
            if mr['ma50'] >= mr['ma200']: st.success(cross_text + " ➔ **정배열**", icon="✅")
            else: st.error(cross_text + " ➔ **역배열**", icon="🚨")

        with col_ind2:
            st.markdown("##### ⚡ 반도체(SOXL) 진입 모멘텀 지표")
            if mr['cond1']: st.success("**1. 단기 추세:** SMH > 50일선 ➔ **합격**", icon="✅")
            else: st.error("**1. 단기 추세:** SMH < 50일선 ➔ **미달**", icon="❌")
            
            if mr['cond2']: st.success(f"**2. 수익률:** 최근 3개월 ({mr['smh_3m_ret']*100:.2f}%) ➔ **합격**", icon="✅")
            else: st.error(f"**2. 수익률:** 최근 3개월 ({mr['smh_3m_ret']*100:.2f}%) ➔ **미달**", icon="❌")
            
            if mr['cond3']: st.success(f"**3. 모멘텀:** RSI ({mr['smh_rsi']:.1f}) > 50 ➔ **합격**", icon="✅")
            else: st.error(f"**3. 모멘텀:** RSI ({mr['smh_rsi']:.1f}) < 50 ➔ **미달**", icon="❌")

    st.write("")

    # --- 포트폴리오 기입 및 현황 패널 ---
    col_header1, col_header2 = st.columns([5, 1])
    with col_header1:
        st.markdown("**[ 내 포트폴리오 자산 비중 ]**")
    with col_header2:
        # 🔥 초기화 버튼 로직 추가
        if st.button("🔄 초기화 (Reset)", type="primary", use_container_width=True):
            st.session_state['portfolio_df'] = pd.DataFrame({
                "티커 (Ticker)": ["TQQQ", "QLD", "QQQ", "SOXL", "USD", "GLD", "CASH"],
                "수량 (주/달러)": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "평균 단가 ($)": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            })
            st.session_state['portfolio_history'] = [{"일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "내용": "사용자에 의해 포트폴리오가 전체 초기화되었습니다."}]
            st.session_state['first_entry_date'] = None
            st.session_state['journal_text'] = ""
            save_portfolio_data(st.session_state['portfolio_df'], st.session_state['portfolio_history'], st.session_state['first_entry_date'], st.session_state['journal_text'])
            st.rerun()
    
    col_table, col_chart = st.columns([1, 1.2])

    with col_table:
        st.caption("표 안의 숫자를 더블 클릭하여 수량과 평단가를 수정하세요.")
        
        edited_df = st.data_editor(
            st.session_state['portfolio_df'],
            num_rows="dynamic",
            key="portfolio_editor",
            use_container_width=True,
            column_config={
                "티커 (Ticker)": st.column_config.TextColumn("종목 (TICKER)"),
                "수량 (주/달러)": st.column_config.NumberColumn("보유 수량", min_value=0.0, format="%.2f", step=1.0),
                "평균 단가 ($)": st.column_config.NumberColumn("평균 단가 ($)", min_value=0.0, format="%.2f", step=1.0)
            }
        )

        def get_portfolio_state(df):
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

        old_state = get_portfolio_state(st.session_state['portfolio_df'])
        new_state = get_portfolio_state(edited_df)
        
        if old_state != new_state:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state['portfolio_history'].append({"일시": now_str, "내용": "포트폴리오 수량/평단가 수정됨"})
            
            st.session_state['portfolio_df'] = edited_df.copy() 
            
            if st.session_state['first_entry_date'] is None:
                st.session_state['first_entry_date'] = datetime.now()
                
            save_portfolio_data(st.session_state['portfolio_df'], st.session_state['portfolio_history'], st.session_state['first_entry_date'], st.session_state['journal_text'])
            st.rerun()

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
                    if curr_price > 0:
                        asset_values[tkr] = asset_values.get(tkr, 0) + (shares * curr_price)
                    if avg_price > 0:
                        total_invested_principal += (shares * avg_price)
                    
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

            fig_bar.update_layout(
                barmode='stack', height=180, margin=dict(l=0, r=0, t=30, b=0),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, 100]),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                showlegend=False,
                title=dict(text=f"총 평가액: <b>${total_value:,.2f}</b>", font=dict(size=16), x=0.5, xanchor='center')
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("수량을 기입하시면 비중 그래프가 나타납니다.")

    st.write("")
    
    # --- 리밸런싱 지시표 패널 ---
    st.markdown("**[ 종목별 수익률 & 리밸런싱 액션 지침 ]**")

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
                "종목": tkr, 
                "목표 비중": f"{target_w_dec*100:.1f}%",
                "현재 비중": f"{my_weight:.1f}%", 
                "목표 금액": f"${target_val:,.0f}", 
                "현재 금액": f"${my_val:,.0f}", 
                "수익률 (%)": f"{ret_pct:+.2f}%" if shares > 0 and tkr != "CASH" else "-",
                "수익금 ($)": f"${ret_amt:+,.0f}" if shares > 0 and tkr != "CASH" else "-",
                "리밸런싱 액션": action
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

    st.write("")

    # --- 성과 추적 패널 ---
    st.markdown("**[ 자산 가치 추이 및 순수익 ]**")
    if total_value > 0:
        with st.container(border=True):
            default_date = st.session_state.get('first_entry_date')
            if default_date is None: default_date = datetime.today() - timedelta(days=90)
                
            col_date, _ = st.columns([1, 3])
            with col_date:
                user_start_date = st.date_input("포트폴리오 매수 시작일", value=default_date)
                st.session_state['first_entry_date'] = datetime.combine(user_start_date, datetime.min.time())
                save_portfolio_data(st.session_state['portfolio_df'], st.session_state['portfolio_history'], st.session_state['first_entry_date'], st.session_state['journal_text'])

            pure_profit = total_value - total_invested_principal
            profit_pct = (pure_profit / total_invested_principal * 100) if total_invested_principal > 0 else 0.0
            
            p_col1, p_col2, p_col3 = st.columns(3)
            p_col1.metric("총 평가액", f"${total_value:,.2f}")
            p_col2.metric("투입 원금 총합", f"${total_invested_principal:,.2f}")
            p_col3.metric("누적 순수익금", f"${pure_profit:+,.2f}", f"{profit_pct:+.2f}%")

            chart_start_ts = pd.Timestamp(user_start_date)
            fetch_start = (chart_start_ts - timedelta(days=10)).strftime('%Y-%m-%d') 
            
            try:
                benchmark_index = yf.download("QQQ", start=fetch_start, progress=False)['Close'].index
                portfolio_value_series = pd.Series(0.0, index=benchmark_index)
                principal_series = pd.Series(0.0, index=benchmark_index)

                for _, row in st.session_state['portfolio_df'].iterrows():
                    tkr = str(row.iloc[0]).upper().strip()
                    try: shares = float(row.iloc[1])
                    except: shares = 0.0
                    try: avg_p = float(row.iloc[2])
                    except: avg_p = 0.0
                        
                    if shares > 0:
                        if tkr == "CASH":
                            portfolio_value_series += shares
                            principal_series += shares
                        else:
                            try:
                                stock_data = yf.download(tkr, start=fetch_start, progress=False)
                                if 'Close' in stock_data.columns:
                                    stock_series = stock_data['Close']
                                    if not stock_series.empty:
                                        if isinstance(stock_series, pd.DataFrame): 
                                            stock_series = stock_series.iloc[:, 0]
                                        stock_series = stock_series.reindex(benchmark_index).ffill().fillna(0)
                                        portfolio_value_series += stock_series * shares
                                        principal_series += (shares * avg_p)
                            except: pass

                portfolio_value_series = portfolio_value_series.dropna()
                principal_series = principal_series.dropna()
                
                portfolio_value_series = portfolio_value_series[portfolio_value_series.index >= chart_start_ts]
                principal_series = principal_series[principal_series.index >= chart_start_ts]

                if len(portfolio_value_series) > 0:
                    fig_perf = go.Figure()
                    fig_perf.add_trace(go.Scatter(x=portfolio_value_series.index, y=portfolio_value_series.values, mode='lines', name='총 평가액', line=dict(color='#3498db', width=2), fill='tozeroy', fillcolor='rgba(52, 152, 219, 0.1)'))
                    fig_perf.add_trace(go.Scatter(x=principal_series.index, y=principal_series.values, mode='lines', name='투입 원금', line=dict(color='#e74c3c', width=2, dash='dash')))
                    fig_perf.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="달러 ($)", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                    st.plotly_chart(fig_perf, use_container_width=True)
                else:
                    st.info("선택한 날짜 이후의 데이터가 없습니다.")
            except Exception as e:
                pass
    else:
        st.info("수량을 기입하시면 자산 가치 추이 차트가 표시됩니다.")

    st.write("")

    # --- 일지 및 로그 패널 ---
    col_jnl, col_hist = st.columns([1.5, 1])

    with col_jnl:
        st.markdown("**[ 나만의 매매 복기 일지 ]**")
        def save_journal():
            save_portfolio_data(st.session_state['portfolio_df'], st.session_state['portfolio_history'], st.session_state['first_entry_date'], st.session_state['journal_text'])
            
        st.session_state['journal_text'] = st.text_area("시장 상황, 다짐, 실수 등을 기록하세요. (자동 저장)", value=st.session_state.get('journal_text', ''), height=200, on_change=save_journal, label_visibility="collapsed")

    with col_hist:
        st.markdown("**[ 시스템 변경 로그 ]**")
        if st.session_state['portfolio_history']:
            history_df = pd.DataFrame(st.session_state['portfolio_history'])[::-1]
            st.dataframe(history_df, hide_index=True, use_container_width=True, height=200)
        else:
            st.info("로그 내역이 없습니다.")
