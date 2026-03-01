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

# --- 💾 글로벌 데이터 로드 및 세션 유지 (탭 이동 시 증발 방지) ---
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

# 탭 이동에도 데이터가 유지되도록 앱 최상단에서 세션 초기화
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
st.sidebar.markdown("### AMLS v4 TERMINAL")
app_mode = st.sidebar.radio("MODE SELECTION", ["[1] BACKTEST ENGINE", "[2] PORTFOLIO MANAGER"])
st.sidebar.markdown("---")

# =====================================================================
# 1. AMLS 백테스트 대시보드 모드 (기존 기능 유지)
# =====================================================================
if app_mode == "[1] BACKTEST ENGINE":
    st.title("AMLS v4 Quant Backtest Engine")
    st.markdown("과거 데이터를 바탕으로 AMLS v4 전략의 성과를 시뮬레이션합니다.")

    st.sidebar.header("PARAMETER SETTINGS")
    BACKTEST_START = st.sidebar.date_input("Start Date", datetime(2018, 1, 1))
    BACKTEST_END = st.sidebar.date_input("End Date", datetime.today())
    INITIAL_CAPITAL = st.sidebar.number_input("Initial Capital ($)", value=10000, step=1000)
    MONTHLY_CONTRIBUTION = st.sidebar.number_input("Monthly Contribution ($)", value=2000, step=500)

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

                log_type = "Regime Change" if today_reg != df['Signal_Regime'].iloc[i-1] else "Monthly Rebalance"
                semi_target = "SOXL (3x)" if use_soxl and today_reg == 1 else ("USD (2x)" if today_reg in [1, 2] else "-")
                
                logs.append({
                    "Date": today.strftime('%Y-%m-%d'), "Type": log_type, "Regime": f"Regime {int(today_reg)}",
                    "Semi Target": semi_target, "Equity": ports['AMLS v4']
                })

        for s in strategies: df[f'{s}_Value'] = hists[s]
        df['Invested'] = invested_hist
        return df, logs, data.columns

    with st.spinner('Calculating backtest logic...'):
        df, full_logs, tickers = load_and_calculate_data(BACKTEST_START, BACKTEST_END, INITIAL_CAPITAL, MONTHLY_CONTRIBUTION)
        strategies = ['AMLS v4', 'QQQ', 'QLD', 'TQQQ', 'SPY']

    today_status = df.iloc[-1]
    date_str = df.index[-1].strftime('%Y-%m-%d')

    st.markdown(f"**MARKET SNAPSHOT ({date_str})**")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Current Regime", f"Regime {int(today_status['Signal_Regime'])}")
    m2.metric("VIX", f"{today_status['^VIX']:.2f}")
    m3.metric("Total Invested", f"${df['Invested'].iloc[-1]:,.0f}")
    m4.metric("AMLS Equity", f"${df['AMLS v4_Value'].iloc[-1]:,.0f}")

    st.divider()

    st.markdown("**REGIME ALLOCATION TARGETS**")
    def get_v4_weights_for_plot(regime):
        w = {t: 0.0 for t in tickers}
        if regime == 1: w['TQQQ'], w['SOXL/USD'], w['QLD'], w['SSO'], w['GLD'], w['CASH'] = 30, 20, 20, 15, 10, 5
        elif regime == 2: w['QLD'], w['SSO'], w['GLD'], w['QQQ'], w['USD'], w['CASH'] = 25, 20, 20, 15, 10, 10
        elif regime == 3: w['GLD'], w['CASH'], w['QQQ'], w['SPY'] = 35, 35, 20, 10
        elif regime == 4: w['GLD'], w['CASH'], w['QQQ'] = 50, 40, 10
        return {k: v for k, v in w.items() if v > 0}

    col1, col2, col3, col4 = st.columns(4)
    colors = {'TQQQ': '#e74c3c', 'SOXL/USD': '#8e44ad', 'USD': '#9b59b6', 'QLD': '#e67e22', 'SSO': '#f39c12', 'QQQ': '#3498db', 'SPY': '#2980b9', 'GLD': '#f1c40f', 'CASH': '#2ecc71'}

    for idx, col in enumerate([col1, col2, col3, col4]):
        reg = idx + 1
        w = get_v4_weights_for_plot(reg)
        fig_pie = go.Figure(data=[go.Pie(labels=list(w.keys()), values=list(w.values()), hole=.5, marker=dict(colors=[colors.get(k, '#95a5a6') for k in w.keys()]))])
        fig_pie.update_layout(title_text=f"Regime {reg}", title_x=0.5, margin=dict(t=30, b=0, l=0, r=0), height=250, showlegend=False)
        fig_pie.update_traces(textinfo='label+percent', textposition='inside')
        col.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    st.markdown("**PERFORMANCE COMPARISON**")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    line_colors = ['#8e44ad', '#3498db', '#f39c12', '#e74c3c', '#2c3e50']
    
    for s, c in zip(strategies, line_colors):
        fig.add_trace(go.Scatter(x=df.index, y=df[f'{s}_Value'], name=s, line=dict(color=c, width=3 if s == 'AMLS v4' else 1.5)), row=1, col=1)
        dd = (df[f'{s}_Value'] / df[f'{s}_Value'].cummax()) - 1
        fig.add_trace(go.Scatter(x=df.index, y=dd * 100, name=f'{s} DD', line=dict(color=c, width=1.5 if s == 'AMLS v4' else 1, dash='solid' if s == 'AMLS v4' else 'dot')), row=2, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df['Invested'], name='Principal', line=dict(color='black', width=2, dash='dash')), row=1, col=1)
    fig.update_yaxes(type="log", row=1, col=1)
    fig.add_hline(y=-20, line_dash="dash", line_color="red", row=2, col=1)
    fig.update_layout(height=600, margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)


# =====================================================================
# 2. 내 실전 포트폴리오 관리 모드 (Professional UI)
# =====================================================================
elif app_mode == "[2] PORTFOLIO MANAGER":
    st.title("AMLS PORTFOLIO MANAGER")
    st.markdown("실시간 계좌 상태 모니터링 및 리밸런싱 실행 관제탑입니다.", help="입력된 데이터는 로컬 환경에 자동 보존됩니다.")

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
        
        semi_target = "SOXL (3x)" if use_soxl else "USD (2x)"
        if regime in [3, 4]: semi_target = "HOLD CASH"
        elif regime == 2: semi_target = "USD (2x) REDUCED"

        return {
            'regime': regime, 'vix': vix, 'qqq': qqq, 'ma200': ma200, 'ma50': ma50,
            'smh': smh, 'smh_ma50': smh_ma50, 'smh_3m_ret': smh_3m_ret, 'smh_rsi': smh_rsi,
            'cond1': cond1, 'cond2': cond2, 'cond3': cond3,
            'semi_target': semi_target, 'date': today.name, 'target_weights': target_w,
            'latest_prices': {t: today[t] for t in TICKERS if t != '^VIX'}
        }

    with st.spinner("Connecting to market data..."):
        mr = get_market_regime()

    # --- 실시간 레이더 패널 (프로페셔널 UI) ---
    with st.container(border=True):
        st.markdown(f"**[ MARKET RADAR ]** &nbsp; | &nbsp; As of {mr['date'].strftime('%Y-%m-%d')}")
        r_col1, r_col2, r_col3, r_col4 = st.columns(4)
        
        regime_color = "#e74c3c" if mr['regime'] >= 3 else "#2ecc71"
        r_col1.markdown(f"Current Regime<br><span style='font-size: 24px; font-weight: bold; color: {regime_color};'>Regime {mr['regime']}</span>", unsafe_allow_html=True)
        r_col2.metric("VIX Index", f"{mr['vix']:.2f}")
        r_col3.metric("QQQ to 200MA", f"{(mr['qqq'] / mr['ma200'] - 1) * 100:+.2f}%")
        r_col4.markdown(f"Semi Target<br><span style='font-size: 20px; font-weight: bold; color: #3498db;'>{mr['semi_target']}</span>", unsafe_allow_html=True)

    st.write("")

    # --- 포트폴리오 기입 및 현황 패널 ---
    st.markdown("**[ HOLDINGS & ALLOCATION ]**")
    
    col_table, col_chart = st.columns([1, 1.2])

    with col_table:
        st.caption("Double-click cells to edit Holdings and Avg Price.")
        
        # 데이터 에디터 출력 및 상태 변경 즉시 반영
        edited_df = st.data_editor(
            st.session_state['portfolio_df'],
            num_rows="dynamic",
            key="portfolio_editor",
            use_container_width=True,
            column_config={
                "티커 (Ticker)": st.column_config.TextColumn("TICKER"),
                "수량 (주/달러)": st.column_config.NumberColumn("SHARES", min_value=0.0, format="%.2f", step=1.0),
                "평균 단가 ($)": st.column_config.NumberColumn("AVG PRICE ($)", min_value=0.0, format="%.2f", step=1.0)
            }
        )

        # 상태 변경 감지용 함수
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
        
        # 변경사항이 있으면 세션에 덮어쓰고 JSON 파일에 저장
        if old_state != new_state:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 간단 로깅
            st.session_state['portfolio_history'].append({"Date": now_str, "Log": "Portfolio data updated manually."})
            
            st.session_state['portfolio_df'] = edited_df.copy() # 핵심: 세션 업데이트
            
            if st.session_state['first_entry_date'] is None:
                st.session_state['first_entry_date'] = datetime.now()
                
            save_portfolio_data(st.session_state['portfolio_df'], st.session_state['portfolio_history'], st.session_state['first_entry_date'], st.session_state['journal_text'])
            st.rerun() # UI 즉시 갱신

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
                    y=['Portfolio Weight'], x=[weight], name=tkr, orientation='h',
                    text=f"<b>{tkr}</b><br>{weight:.1f}%", textposition='inside', insidetextanchor='middle',
                    marker=dict(color=palette[idx % len(palette)], line=dict(color='white', width=1.0)),
                    hoverinfo='text', hovertext=f"{tkr}: ${val:,.0f} ({weight:.1f}%)"
                ))

            fig_bar.update_layout(
                barmode='stack', height=180, margin=dict(l=0, r=0, t=30, b=0),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, 100]),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                showlegend=False,
                title=dict(text=f"Total Equity: <b>${total_value:,.2f}</b>", font=dict(size=16), x=0.5, xanchor='center')
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Input shares to view portfolio allocation.")

    st.write("")
    
    # --- 리밸런싱 지시표 패널 ---
    st.markdown("**[ EXECUTION: REBALANCING ACTION PLAN ]**")

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
        if abs(diff_val) < 50: action = "HOLD (Target Met)"
        elif diff_val > 0: action = f"BUY ${diff_val:,.0f}"
        else: action = f"SELL ${abs(diff_val):,.0f}"

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
                "Asset": tkr, 
                "Target %": f"{target_w_dec*100:.1f}%",
                "Actual %": f"{my_weight:.1f}%", 
                "Target Vol ($)": f"${target_val:,.0f}", 
                "Actual Vol ($)": f"${my_val:,.0f}", 
                "Return (%)": f"{ret_pct:+.2f}%" if shares > 0 and tkr != "CASH" else "-",
                "P&L ($)": f"${ret_amt:+,.0f}" if shares > 0 and tkr != "CASH" else "-",
                "ACTION REQUIRED": action
            })

    if status_data:
        status_df = pd.DataFrame(status_data).sort_values(by="Target %", ascending=False)
        def color_status(val):
            if type(val) == str:
                if 'BUY' in val or ('+' in val and val != '-'): return 'color: #18bc9c; font-weight: bold;'
                elif 'SELL' in val or ('-' in val and val != '-'): return 'color: #e74c3c; font-weight: bold;'
                elif 'HOLD' in val: return 'color: #95a5a6;'
            return ''
        st.dataframe(status_df.style.map(color_status, subset=['ACTION REQUIRED', 'Return (%)', 'P&L ($)']), hide_index=True, use_container_width=True)

    st.write("")

    # --- 성과 추적 패널 ---
    st.markdown("**[ PERFORMANCE TRACKING ]**")
    if total_value > 0:
        with st.container(border=True):
            default_date = st.session_state.get('first_entry_date')
            if default_date is None: default_date = datetime.today() - timedelta(days=90)
                
            col_date, _ = st.columns([1, 3])
            with col_date:
                user_start_date = st.date_input("Inception Date (시작일)", value=default_date)
                st.session_state['first_entry_date'] = datetime.combine(user_start_date, datetime.min.time())
                save_portfolio_data(st.session_state['portfolio_df'], st.session_state['portfolio_history'], st.session_state['first_entry_date'], st.session_state['journal_text'])

            pure_profit = total_value - total_invested_principal
            profit_pct = (pure_profit / total_invested_principal * 100) if total_invested_principal > 0 else 0.0
            
            p_col1, p_col2, p_col3 = st.columns(3)
            p_col1.metric("Gross Equity (총 평가액)", f"${total_value:,.2f}")
            p_col2.metric("Total Principal (총 원금)", f"${total_invested_principal:,.2f}")
            p_col3.metric("Net Profit (순수익)", f"${pure_profit:+,.2f}", f"{profit_pct:+.2f}%")

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
                    fig_perf.add_trace(go.Scatter(x=portfolio_value_series.index, y=portfolio_value_series.values, mode='lines', name='Gross Equity', line=dict(color='#3498db', width=2), fill='tozeroy', fillcolor='rgba(52, 152, 219, 0.1)'))
                    fig_perf.add_trace(go.Scatter(x=principal_series.index, y=principal_series.values, mode='lines', name='Principal Input', line=dict(color='#e74c3c', width=2, dash='dash')))
                    fig_perf.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="USD ($)", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                    st.plotly_chart(fig_perf, use_container_width=True)
                else:
                    st.info("Insufficient trading days to plot performance.")
            except Exception as e:
                pass
    else:
        st.info("Please input holdings above to view performance tracking.")

    st.write("")

    # --- 일지 및 로그 패널 ---
    col_jnl, col_hist = st.columns([1.5, 1])

    with col_jnl:
        st.markdown("**[ TRADING JOURNAL ]**")
        def save_journal():
            save_portfolio_data(st.session_state['portfolio_df'], st.session_state['portfolio_history'], st.session_state['first_entry_date'], st.session_state['journal_text'])
            
        st.session_state['journal_text'] = st.text_area("Record market thoughts and execution rationale here. (Auto-saved)", value=st.session_state.get('journal_text', ''), height=200, on_change=save_journal, label_visibility="collapsed")

    with col_hist:
        st.markdown("**[ SYSTEM LOGS ]**")
        if st.session_state['portfolio_history']:
            history_df = pd.DataFrame(st.session_state['portfolio_history'])[::-1]
            st.dataframe(history_df, hide_index=True, use_container_width=True, height=200)
        else:
            st.info("No system logs available.")
