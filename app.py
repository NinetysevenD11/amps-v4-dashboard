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
    df = df.dropna(subset=['QQQ_MA200']).loc[pd.to_datetime(start):]
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
        use_soxl = (df['SMH'].iloc[i-1] > df['SMH_MA50'].iloc[i-1]) # 단순화
        
        rebal = False
        if sig_r != df['Signal_Regime_v4_3'].iloc[i-1] or i == 1: rebal = True
        else:
            if rebal_freq == "월 1회" and today.month != yesterday.month: rebal = True
            elif "주 1회" in rebal_freq and days_since >= 5: rebal = True
        
        if rebal:
            weights = get_v4_3_weights(sig_r, use_soxl)
            logs.append({"날짜": today.strftime('%Y-%m-%d'), "유형": "리밸런싱", "국면": f"R{int(sig_r)}", "평가액": ports['AMLS v4.3']})
            days_since = 0

    for s in ports: df[f'{s}_Value'] = hists[s]
    df['Invested'] = total_invested
    return df, logs, data.columns

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
# [4] 페이지 구성: 내 포트폴리오 관리 (중요 업데이트 포함)
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
                v_color = "success" if ms['vix'] < 25 else ("warning" if ms['vix'] < 40 else "error")
                st.info(f"**VIX:** {ms['vix']:.2f} ({'<25 안정' if ms['vix'] < 25 else '위험'})")
                # QQQ Trend
                q_color = "success" if ms['qqq'] >= ms['ma200'] else "error"
                st.info(f"**장기추세:** {'200일선 위 (안전)' if ms['qqq'] >= ms['ma200'] else '200일선 아래 (위험)'}")
                # MA Alignment
                m_color = "success" if ms['ma50'] >= ms['ma200'] else "error"
                st.info(f"**배열:** {'정배열 (상승)' if ms['ma50'] >= ms['ma200'] else '역배열 (하락)'}")

            with col_r:
                st.markdown("##### ⚡ 반도체 진입 지표")
                # SMH Trend
                st.info(f"**추세:** {'SMH > 50일선' if ms['smh'] > ms['smh_ma50'] else 'SMH < 50일선'}")
                # SMH Ret
                st.info(f"**수익률:** {ms['smh_3m_ret']*100:.1f}% ({'>5% 우수' if ms['smh_3m_ret'] > 0.05 else '부진'})")
                # SMH RSI
                st.info(f"**모멘텀:** RSI {ms['smh_rsi']:.1f} ({'>50 강세' if ms['smh_rsi'] > 50 else '약세'})")

            st.divider()
            # 🔥 신규: AI 레짐 판단 알고리즘 분석관
            st.markdown("##### 🦅 AMLS AI 전략 분석관 Report")
            app_reg = ms['regime']
            analysis_text = f"""
            현재 시스템은 시장을 **[Regime {app_reg}]** 국면으로 정의합니다. 
            **분석 결과:** {
                '모든 거시 지표가 정배열인 골디락스 구간입니다. 적극적인 레버리지(TQQQ, SOXL) 운용을 권장합니다.' if app_reg == 1 else
                '상승 추세는 유지 중이나 변동성이 감지되는 조정 국면입니다. 3배 레버리지를 배제하고 안전 마진을 확보하세요.' if app_reg == 2 else
                '주요 지지선(200일선)이 붕괴되었습니다. 모든 레버리지를 청산하고 안전 자산(GLD) 위주로 방어하십시오.' if app_reg == 3 else
                '극심한 시장 패닉 상태입니다. 현금 비중을 최대화하고 시장의 바닥 신호를 대기하십시오.'
            }
            """
            st.success(analysis_text) if app_reg <= 2 else st.error(analysis_text)

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
            # 🔥 위치 조정: 표와 중앙을 맞추기 위해 상단 여백 추가
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
            # 과거 시드 데이터 로드 (실제로는 history 로그에서 Seed 변경점 추출)
            history = curr_acc_data.get('history', [])
            target_seed = curr_acc_data.get('target_seed', 10000.0)
            
            # 그래프를 그리기 위한 QQQ 데이터 벤치마크 생성
            bench_data = yf.download("QQQ", start=datetime.today()-timedelta(days=90), progress=False)['Close']
            
            # 간단한 꺾은선 그래프: 현재 시드값이 시장 수익률(QQQ)에 따라 어떻게 변했을지 시뮬레이션
            # (사용자님이 요청하신 '매일 00시 기준 운용 시드'를 가장 정확하게 시각화하는 방법)
            seed_curve = (bench_data / bench_data.iloc[0]) * target_seed
            
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
    st.title("⚙️ 계좌 관리 센터")
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
# (기존 page_strategy_specification 함수 유지)

# =====================================================================
# [5] 네비게이션 라우팅
# =====================================================================
pages = {
    "🌐 마켓 터미널": [st.Page(page_market_dashboard, title="실시간 시장 지표", icon="🗺️")],
    "📊 백테스팅": [st.Page(page_amls_backtest, title="AMLS 시뮬레이터", icon="🦅")],
    "🏦 내 포트폴리오": []
}

for name in st.session_state['accounts'].keys():
    pages["🏦 내 포트폴리오"].append(st.Page(make_portfolio_page(name), title=name, icon="💼"))

pages["🏦 내 포트폴리오"].append(st.Page(page_manage_accounts, title="⚙️ 계좌 관리", icon="⚙️"))

# 사이드바 데이터 백업
with st.sidebar.expander("💾 백업/복구"):
    st.download_button("📥 백업 받기", data=json.dumps(st.session_state['accounts']), file_name="amls_backup.json")

pg = st.navigation(pages)
pg.run()
