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
                "portfolio": [{"티커 (Ticker)": t, "수량 (주/달러)": 0.0, "평균 단가 ($)": 0.0, "매입 환율": 0.0} for t in REQUIRED_TICKERS],
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
            else: new_port.append({"티커 (Ticker)": req_t, "수량 (주/달러)": 0.0, "평균 단가 ($)": 0.0, "매입 환율": 0.0})
        acc_data["portfolio"] = new_port
        needs_save = True
    # 매입 환율 필드 마이그레이션 (기존 데이터에 없으면 추가)
    for item in acc_data["portfolio"]:
        if "매입 환율" not in item:
            item["매입 환율"] = 0.0
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
            current_v4 = tr; pend_v4 = None; cnt_v4 = 0; actual_regime_v4.append(current_v4)
        elif tr < current_v4:
            if tr == pend_v4:
                cnt_v4 += 1
                if cnt_v4 >= 5: current_v4 = tr; pend_v4 = None; cnt_v4 = 0; actual_regime_v4.append(current_v4)
                else: actual_regime_v4.append(current_v4)
            else: pend_v4 = tr; cnt_v4 = 1; actual_regime_v4.append(current_v4)
        else: pend_v4 = None; cnt_v4 = 0; actual_regime_v4.append(current_v4)
        
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

    strategies = ['AMLS v4.3', 'AMLS v4', 'QQQ', 'QLD', 'TQQQ']
    ports = {s: init_cap for s in strategies}
    hists = {s: [init_cap] for s in ports.keys()}
    total_invested = init_cap
    weights_v4 = {t: 0.0 for t in data.columns}; weights_v4_3 = {t: 0.0 for t in data.columns}
    logs, days_since_v4, days_since_v4_3 = [], 0, 0

    for i in range(1, len(df)):
        today, yesterday = df.index[i], df.index[i-1]
        days_since_v4 += 1
        days_since_v4_3 += 1
        
        ret_v4 = sum(weights_v4[t] * daily_returns[t].iloc[i] for t in data.columns)
        ret_v4_3 = sum(weights_v4_3[t] * daily_returns[t].iloc[i] for t in data.columns)
        
        ports['AMLS v4'] *= (1 + ret_v4); ports['AMLS v4.3'] *= (1 + ret_v4_3)
        for s in ['QQQ', 'QLD', 'TQQQ']: ports[s] *= (1 + daily_returns[s].iloc[i])
        
        for t in data.columns:
            if ports['AMLS v4'] > 0: weights_v4[t] = weights_v4[t]*(1+daily_returns[t].iloc[i])/(1+ret_v4)
            if ports['AMLS v4.3'] > 0: weights_v4_3[t] = weights_v4_3[t]*(1+daily_returns[t].iloc[i])/(1+ret_v4_3)
            
        if today.month != yesterday.month:
            for s in ports: ports[s] += monthly_cont
            total_invested += monthly_cont
            
        for s in ports: hists[s].append(ports[s])
        
        use_soxl = (df['SMH'].iloc[i-1] > df['SMH_MA50'].iloc[i-1]) and (df['SMH_3M_Ret'].iloc[i-1] > 0.05) and (df['SMH_RSI'].iloc[i-1] > 50)
        
        sig_r_v4 = df['Signal_Regime_v4'].iloc[i]
        rebal_v4 = False
        if sig_r_v4 != df['Signal_Regime_v4'].iloc[i-1] or i == 1: rebal_v4 = True
        elif rebal_freq == "월 1회" and today.month != yesterday.month: rebal_v4 = True
        elif "주 1회" in rebal_freq and days_since_v4 >= 5: rebal_v4 = True
        elif "2주 1회" in rebal_freq and days_since_v4 >= 10: rebal_v4 = True
        elif "3주 1회" in rebal_freq and days_since_v4 >= 15: rebal_v4 = True
        
        if rebal_v4:
            weights_v4 = get_v4_weights(sig_r_v4, use_soxl)
            days_since_v4 = 0

        sig_r_v4_3 = df['Signal_Regime_v4_3'].iloc[i]
        rebal_v4_3 = False
        if sig_r_v4_3 != df['Signal_Regime_v4_3'].iloc[i-1] or i == 1: rebal_v4_3 = True
        elif rebal_freq == "월 1회" and today.month != yesterday.month: rebal_v4_3 = True
        elif "주 1회" in rebal_freq and days_since_v4_3 >= 5: rebal_v4_3 = True
        elif "2주 1회" in rebal_freq and days_since_v4_3 >= 10: rebal_v4_3 = True
        elif "3주 1회" in rebal_freq and days_since_v4_3 >= 15: rebal_v4_3 = True
        
        if rebal_v4_3:
            weights_v4_3 = get_v4_3_weights(sig_r_v4_3, use_soxl)
            log_type = "🚨 레짐 전환" if sig_r_v4_3 != df['Signal_Regime_v4_3'].iloc[i-1] else f"🔄 정기 ({rebal_freq.split(' ')[0]})"
            semi_target = "SOXL (3x)" if use_soxl and sig_r_v4_3 == 1 else ("USD (2x)" if sig_r_v4_3 in [1, 2] else "-")
            logs.append({"날짜": today.strftime('%Y-%m-%d'), "유형": log_type, "국면": f"R{int(sig_r_v4_3)}", "반도체": semi_target, "평가액": ports['AMLS v4.3']})
            days_since_v4_3 = 0

    for s in ports: df[f'{s}_Value'] = hists[s]
    
    inv_arr = [init_cap]
    curr_inv = init_cap
    for i in range(1, len(df)):
        if df.index[i].month != df.index[i-1].month: curr_inv += monthly_cont
        inv_arr.append(curr_inv)
    df['Invested'] = inv_arr
    
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
# [3] 페이지 구성: AMLS 백테스트 (티어시트)
# =====================================================================
def page_amls_backtest():
    st.title("🦅 AMLS 퀀트 백테스트 엔진 (Tearsheet)")
    st.markdown("다양한 시장 조건과 벤치마크(QQQ, QLD, TQQQ)를 비교 분석하는 전문가용 시뮬레이터입니다.")

    st.sidebar.header("⚙️ 백테스트 파라미터")
    BACKTEST_START = st.sidebar.date_input("시작일", datetime(2018, 1, 1))
    BACKTEST_END = st.sidebar.date_input("종료일", datetime.today())
    INITIAL_CAPITAL = st.sidebar.number_input("초기 자본금 ($)", value=10000, step=1000)
    MONTHLY_CONTRIBUTION = st.sidebar.number_input("매월 추가 적립금 ($)", value=2000, step=500)
    REBAL_FREQ = st.sidebar.selectbox("🔄 정기 리밸런싱 주기", ["월 1회", "주 1회 (5거래일)", "2주 1회 (10거래일)", "3주 1회 (15거래일)"], index=0)

    with st.spinner('방대한 시장 데이터를 연산 중입니다. 잠시만 기다려주세요...'):
        df, logs, tickers = load_amls_backtest_data(BACKTEST_START, BACKTEST_END, INITIAL_CAPITAL, MONTHLY_CONTRIBUTION, REBAL_FREQ)
    
    def calc_metrics(series, invested_series):
        final_val = series.iloc[-1]
        total_inv = invested_series.iloc[-1]
        total_ret = (final_val / total_inv) - 1
        days = (series.index[-1] - series.index[0]).days
        cagr = (final_val / invested_series.iloc[-1]) ** (365.25 / days) - 1 if days > 0 else 0
        mdd = ((series / series.cummax()) - 1).min()
        daily_ret = series.pct_change().dropna()
        sharpe = (daily_ret.mean() * 252) / (daily_ret.std() * np.sqrt(252)) if daily_ret.std() != 0 else 0
        return final_val, total_ret, cagr, mdd, sharpe

    strats = ['AMLS v4.3', 'QQQ', 'QLD', 'TQQQ']
    metrics_data = []
    for s in strats:
        fv, tr, cagr, mdd, shp = calc_metrics(df[f'{s}_Value'], df['Invested'])
        metrics_data.append({
            "전략/종목": s,
            "최종 평가금액": f"${fv:,.0f}",
            "누적 수익률": f"{tr*100:+.1f}%",
            "연평균(CAGR)": f"{cagr*100:.1f}%",
            "최대 낙폭(MDD)": f"{mdd*100:.1f}%",
            "샤프 지수": f"{shp:.2f}"
        })
    metrics_df = pd.DataFrame(metrics_data).set_index("전략/종목")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 성과 비교 요약", "📈 자산 추이 및 낙폭", "🗓️ 연도별 분석", "📝 매매 로그"])

    with tab1:
        st.markdown("#### 🏆 핵심 퍼포먼스 비교표")
        st.info(f"**투입 원금 총합:** ${df['Invested'].iloc[-1]:,.0f} (초기 {INITIAL_CAPITAL} + 매월 {MONTHLY_CONTRIBUTION} 적립)")
        st.dataframe(metrics_df, use_container_width=True)

        st.markdown("#### 🥧 AMLS v4.3 국면별 자산 배분 비중")
        c1, c2, c3, c4 = st.columns(4)
        def get_w(reg):
            if reg == 1: return {'TQQQ':30, 'SOXL/USD':20, 'QLD':20, 'SSO':15, 'GLD':10, 'CASH':5}
            elif reg == 2: return {'QLD':30, 'SSO':25, 'GLD':20, 'USD':10, 'QQQ':5, 'CASH':10}
            elif reg == 3: return {'GLD':50, 'CASH':35, 'QQQ':15}
            elif reg == 4: return {'GLD':50, 'CASH':40, 'QQQ':10}
        colors = {'TQQQ':'#e74c3c', 'SOXL/USD':'#8e44ad', 'USD':'#9b59b6', 'QLD':'#e67e22', 'SSO':'#f39c12', 'QQQ':'#3498db', 'GLD':'#f1c40f', 'CASH':'#2ecc71'}
        for i, col in enumerate([c1, c2, c3, c4]):
            r = i+1; w = {k:v for k,v in get_w(r).items() if v>0}
            fig_p = go.Figure(go.Pie(labels=list(w.keys()), values=list(w.values()), hole=0.5, marker=dict(colors=[colors.get(k, '#000') for k in w.keys()])))
            fig_p.update_layout(title=f"Regime {r}", title_x=0.5, height=250, margin=dict(t=30,b=0,l=0,r=0), showlegend=False)
            fig_p.update_traces(textinfo='label+percent', textposition='inside')
            col.plotly_chart(fig_p, use_container_width=True)

    with tab2:
        st.markdown("#### 📈 자산 성장 곡선")
        use_log = st.checkbox("Y축 로그 스케일 적용", value=False)
        fig_eq = go.Figure()
        colors_line = {'AMLS v4.3': '#2ecc71', 'QQQ': '#3498db', 'QLD': '#f39c12', 'TQQQ': '#e74c3c'}
        for s in strats:
            fig_eq.add_trace(go.Scatter(x=df.index, y=df[f'{s}_Value'], name=s, line=dict(color=colors_line[s], width=3 if 'AMLS' in s else 1.5)))
        fig_eq.add_trace(go.Scatter(x=df.index, y=df['Invested'], name='원금 (Invested)', line=dict(color='gray', width=2, dash='dot')))
        if use_log: fig_eq.update_yaxes(type="log")
        fig_eq.update_layout(height=450, template="plotly_dark", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig_eq, use_container_width=True)

        st.markdown("#### 📉 전략별 최대 낙폭 (Under Water)")
        fig_dd = go.Figure()
        for s in strats:
            dd = (df[f'{s}_Value'] / df[f'{s}_Value'].cummax() - 1) * 100
            fig_dd.add_trace(go.Scatter(x=df.index, y=dd, name=f'{s} DD', line=dict(color=colors_line[s], width=2 if 'AMLS' in s else 1)))
        fig_dd.add_hline(y=-30, line_dash="dash", line_color="red", annotation_text="-30% 위험선")
        fig_dd.update_layout(height=300, template="plotly_dark", hovermode="x unified", margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig_dd, use_container_width=True)

    with tab3:
        st.markdown("#### 🗓️ 연도별 누적 수익률 비교")
        years = df.index.year.unique()
        yr_data = []
        for y in years:
            y_df = df[df.index.year == y]
            if len(y_df) > 0:
                row = {"Year": str(y)}
                for s in strats:
                    ret = (y_df[f'{s}_Value'].iloc[-1] / y_df[f'{s}_Value'].iloc[0] - 1) * 100
                    row[s] = ret
                yr_data.append(row)
        yr_df = pd.DataFrame(yr_data).set_index("Year")
        
        fig_yr = go.Figure()
        for s in strats:
            fig_yr.add_trace(go.Bar(name=s, x=yr_df.index, y=yr_df[s], marker_color=colors_line[s]))
        fig_yr.update_layout(barmode='group', height=400, template="plotly_dark", yaxis_title="수익률 (%)")
        st.plotly_chart(fig_yr, use_container_width=True)
        
        st.dataframe(yr_df.style.format("{:.1f}%"), use_container_width=True)

    with tab4:
        st.markdown("#### 📝 시스템 리밸런싱 로그")
        st.caption(f"적용된 정기 리밸런싱 주기: **{REBAL_FREQ}**")
        log_df = pd.DataFrame(logs)[::-1]
        if not log_df.empty:
            log_df['평가액'] = log_df['평가액'].apply(lambda x: f"${x:,.0f}")
            st.dataframe(log_df, hide_index=True, use_container_width=True)


# =====================================================================
# [4] 페이지 구성: 내 포트폴리오 관리 (UI 최적화 및 액션 지침 복구)
# =====================================================================
def make_portfolio_page(acc_name):
    def page_func():
        st.title(f"🏦 {acc_name} 포트폴리오 관제탑")
        curr_acc_data = st.session_state['accounts'][acc_name]
        pf_df = pd.DataFrame(curr_acc_data["portfolio"])
        pf_df["수량 (주/달러)"] = pf_df["수량 (주/달러)"].astype(float)
        pf_df["평균 단가 ($)"] = pf_df["평균 단가 ($)"].astype(float)
        pf_df["매입 환율"] = pf_df["매입 환율"].astype(float)

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
            
            if today['^VIX'] > 40: reg = 4
            elif today['QQQ'] < ma200: reg = 3
            elif today['QQQ'] >= ma200 and ma50 >= ma200 and today['^VIX'] < 25: reg = 1
            else: reg = 2

            # 현재 환율 가져오기
            try:
                fx_data = yf.download('USDKRW=X', period='5d', progress=False)['Close'].ffill()
                if isinstance(fx_data, pd.DataFrame): fx_data = fx_data.iloc[:, 0]
                current_usdkrw = float(fx_data.iloc[-1])
            except:
                current_usdkrw = 0.0

            return {
                'regime': reg, 'vix': today['^VIX'], 'qqq': today['QQQ'], 'ma200': ma200, 'ma50': ma50,
                'smh': today['SMH'], 'smh_ma50': smh_ma50, 'smh_3m_ret': smh_3m_ret, 'smh_rsi': smh_rsi,
                'prices': today.to_dict(), 'prev_prices': yesterday.to_dict(), 'date': data.index[-1],
                'usdkrw': current_usdkrw
            }

        with st.spinner("시장 데이터 동기화 및 AI 분석 중..."): 
            ms = get_market_status()

        # 🔥 실시간 시장 인텔리전스
        st.markdown("### 📡 실시간 시장 인텔리전스 (Market Intelligence)")
        with st.container(border=True):
            st.markdown(f"**기준일:** {ms['date'].strftime('%Y-%m-%d')} 종가")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                vix_val = ms['vix']
                fig_vix = go.Figure(go.Indicator(
                    mode = "gauge+number", value = vix_val, title = {'text': "시장 공포탐욕 지수 (VIX)", 'font': {'size': 14}},
                    gauge = {
                        'axis': {'range': [0, 80], 'tickwidth': 1, 'tickcolor': "white"},
                        'bar': {'color': "white", 'thickness': 0.2},
                        'steps': [{'range': [0, 25], 'color': "#2ecc71"}, {'range': [25, 40], 'color': "#f39c12"}, {'range': [40, 80], 'color': "#e74c3c"}],
                        'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 40}
                    }))
                fig_vix.update_layout(height=240, margin=dict(l=30, r=30, t=50, b=20), template="plotly_dark")
                st.plotly_chart(fig_vix, use_container_width=True)

            with col2:
                q_dist = (ms['qqq'] / ms['ma200'] - 1) * 100
                fig_qqq = go.Figure(go.Indicator(
                    mode = "gauge+number", value = q_dist, number={'suffix': "%", 'valueformat': "+.1f"},
                    title = {'text': "QQQ 200일선 이격도", 'font': {'size': 14}},
                    gauge = {
                        'axis': {'range': [-30, 30], 'tickwidth': 1, 'tickcolor': "white"},
                        'bar': {'color': "white", 'thickness': 0.2},
                        'steps': [{'range': [-30, 0], 'color': "#e74c3c"}, {'range': [0, 30], 'color': "#2ecc71"}],
                        'threshold': {'line': {'color': "yellow", 'width': 4}, 'thickness': 0.75, 'value': 0}
                    }))
                fig_qqq.update_layout(height=240, margin=dict(l=30, r=30, t=50, b=20), template="plotly_dark")
                st.plotly_chart(fig_qqq, use_container_width=True)

            with col3:
                rsi_val = ms['smh_rsi']
                fig_rsi = go.Figure(go.Indicator(
                    mode = "gauge+number", value = rsi_val, title = {'text': "반도체(SMH) RSI 모멘텀", 'font': {'size': 14}},
                    gauge = {
                        'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                        'bar': {'color': "white", 'thickness': 0.2},
                        'steps': [{'range': [0, 30], 'color': "#e74c3c"}, {'range': [30, 50], 'color': "#f39c12"}, {'range': [50, 100], 'color': "#3498db"}],
                        'threshold': {'line': {'color': "green", 'width': 4}, 'thickness': 0.75, 'value': 50}
                    }))
                fig_rsi.update_layout(height=240, margin=dict(l=30, r=30, t=50, b=20), template="plotly_dark")
                st.plotly_chart(fig_rsi, use_container_width=True)

            st.divider()

            st.markdown("#### ⚡ 반도체 3배(SOXL) 진입 판독기")
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                s_icon = "✅" if ms['smh'] > ms['smh_ma50'] else "❌"
                st.info(f"**{s_icon} 단기 추세 (50일선)**\n\n`{'돌파 (강세)' if ms['smh'] > ms['smh_ma50'] else '붕괴 (약세)'}`")
            with col_s2:
                ret_val = ms['smh_3m_ret'] * 100
                r_icon = "✅" if ret_val > 5.0 else "❌"
                st.info(f"**{r_icon} 3개월 누적 수익률**\n\n`{ret_val:+.2f}%` (기준: > 5%)")
            with col_s3:
                rsi_icon = "✅" if rsi_val > 50 else "❌"
                st.info(f"**{rsi_icon} 상대강도지수 (RSI 14)**\n\n`{rsi_val:.1f}` (기준: > 50)")

            st.divider()

            st.markdown("##### 🤖 AMLS AI 전략 분석관 Report")
            app_reg = ms['regime']
            
            col_a1, col_a2 = st.columns([1, 4])
            with col_a1:
                bg_color = "#e74c3c" if app_reg >= 3 else "#2ecc71"
                st.markdown(f"<div style='text-align: center; padding: 20px; border-radius: 10px; background-color: {bg_color};'><h1 style='color: white; margin:0;'>R{app_reg}</h1><p style='color: white; margin:0;'>현재 국면</p></div>", unsafe_allow_html=True)
            with col_a2:
                if app_reg == 4:
                    st.error("🚨 **[초비상] 패닉장 도래!** VIX 지수가 40을 돌파했습니다. 시스템이 시장의 붕괴를 감지했습니다. 모든 주식 포지션을 전량 청산하고 즉시 **현금 및 금(GLD)**으로 대피하십시오.")
                elif app_reg == 3:
                    st.warning("⚠️ **[경고] 장기 하락장 진입.** 나스닥이 생명선인 200일 이동평균선을 하향 이탈했습니다. 하락 추세가 컨펌되었으므로, 레버리지 상품을 청산하고 방어 태세(GLD 50%)를 굳건히 하십시오.")
                elif app_reg == 1:
                    st.success("🔥 **[강세] 완벽한 골디락스 상승장.** VIX가 안정적이고 이평선이 정배열을 이뤘습니다. 적극적인 **3배 레버리지(TQQQ, SOXL) 베팅**을 통해 자산을 폭발적으로 증식시킬 최적의 구간입니다.")
                else:
                    st.info("🛡️ **[조정] 안전 마진 확보 구간.** 상승 추세는 살아있으나 변동성이 확대되거나 단기 모멘텀이 꺾였습니다. 과도한 레버리지를 축소하고 QLD/SSO 등 2배수로 속도를 조절하세요.")

        # --- 💼 자산 기입표 & 도넛 차트 (환율 칸 추가) ---
        st.write("")
        c_h1, c_h2 = st.columns([5, 1])
        with c_h1: st.markdown(f"**[ 💼 포트폴리오 기입표 및 실시간 수익률 ]**")
        with c_h2:
            if st.button("🔄 숫자 리셋", use_container_width=True):
                st.session_state['accounts'][acc_name]["portfolio"] = [{"티커 (Ticker)": t, "수량 (주/달러)": 0.0, "평균 단가 ($)": 0.0, "매입 환율": 0.0} for t in REQUIRED_TICKERS]
                save_accounts_data(st.session_state['accounts']); st.rerun()

        live_prices = {k: ms['prices'].get(k, 1.0) for k in REQUIRED_TICKERS}
        live_prices['CASH'] = 1.0
        current_usdkrw = ms['usdkrw']
        
        disp_df = pf_df.copy()
        disp_df["현재가 ($)"] = disp_df["티커 (Ticker)"].apply(lambda x: live_prices.get(x, 0.0))
        disp_df["현재 환율"] = current_usdkrw
        def cy(row):
            if row["수량 (주/달러)"] == 0 or row["평균 단가 ($)"] == 0 or row["티커 (Ticker)"] == "CASH": return 0.0
            return (row["현재가 ($)"] - row["평균 단가 ($)"]) / row["평균 단가 ($)"] * 100
        disp_df["수익률 (%)"] = disp_df.apply(cy, axis=1)

        def color_y(val):
            if isinstance(val, (int, float)):
                if val > 0: return 'color: #ff4b4b; font-weight: bold;'
                elif val < 0: return 'color: #3498db; font-weight: bold;'
            return ''

        c_t, c_c = st.columns([1.2, 1])
        with c_t:
            st.caption("💡 더블 클릭하여 수량, 평단가, 매입 환율을 입력하세요. (현재가·현재 환율·수익률은 자동 연동)")
            ed_disp = st.data_editor(
                disp_df.style.map(color_y, subset=["수익률 (%)"]), 
                num_rows="dynamic", use_container_width=True, height=350,
                column_config={
                    "현재가 ($)": st.column_config.NumberColumn(disabled=True, format="$ %.2f"),
                    "현재 환율": st.column_config.NumberColumn(disabled=True, format="₩ %.1f"),
                    "수익률 (%)": st.column_config.NumberColumn(disabled=True, format="%.2f %%"),
                    "매입 환율": st.column_config.NumberColumn(format="₩ %.1f"),
                }
            )
            base_cols = ["티커 (Ticker)", "수량 (주/달러)", "평균 단가 ($)", "매입 환율"]
            if not ed_disp[base_cols].equals(pf_df[["티커 (Ticker)", "수량 (주/달러)", "평균 단가 ($)", "매입 환율"]]):
                st.session_state['accounts'][acc_name]["portfolio"] = ed_disp[base_cols].to_dict(orient="records")
                save_accounts_data(st.session_state['accounts']); st.rerun()

        with c_c:
            st.markdown("<div style='margin-top: 45px;'></div>", unsafe_allow_html=True)
            asset_vals = {}
            for _, r in ed_disp.iterrows():
                v = r["수량 (주/달러)"] * r["현재가 ($)"] if r["티커 (Ticker)"] != "CASH" else r["수량 (주/달러)"]
                if v > 0: asset_vals[r["티커 (Ticker)"]] = v
            
            total_val = sum(asset_vals.values())
            if total_val > 0:
                fig = go.Figure(go.Pie(labels=list(asset_vals.keys()), values=list(asset_vals.values()), hole=0.6, marker=dict(colors=['#2ecc71','#3498db','#9b59b6','#f1c40f','#e74c3c'])))
                fig.update_layout(height=320, margin=dict(l=0,r=0,t=0,b=0), showlegend=False, annotations=[dict(text=f"총 평가액<br><b>${total_val:,.0f}</b>", x=0.5, y=0.5, font_size=16, showarrow=False)])
                st.plotly_chart(fig, use_container_width=True)

        # 🔥 리밸런싱 액션 지침 복구 (주식 수 계산 추가)
        st.write("")
        st.markdown("**[ 🎯 리밸런싱 액션 지침 ]**")
        target_seed = st.number_input("운용 시드 입력 ($)", value=float(curr_acc_data.get("target_seed", 10000.0)), step=1000.0, key=f"seed_{acc_name}")
        if target_seed != curr_acc_data.get("target_seed"):
            st.session_state['accounts'][acc_name]["target_seed"] = target_seed
            save_accounts_data(st.session_state['accounts'])

        status_d = []
        smh_cond = (ms['smh'] > ms['smh_ma50']) and (ms['smh_3m_ret'] > 0.05) and (ms['smh_rsi'] > 50)
        
        def get_w_local(reg, usx):
            w = {t: 0.0 for t in REQUIRED_TICKERS}
            semi = 'SOXL' if usx else 'USD'
            if reg == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'], w['CASH'] = 0.30, 0.20, 0.20, 0.15, 0.10, 0.05
            elif reg == 2: w['QLD'], w['SSO'], w['GLD'], w['USD'], w['QQQ'], w['CASH'] = 0.30, 0.25, 0.20, 0.10, 0.05, 0.10
            elif reg == 3: w['GLD'], w['CASH'], w['QQQ'] = 0.50, 0.35, 0.15
            elif reg == 4: w['GLD'], w['CASH'], w['QQQ'] = 0.50, 0.40, 0.10
            return {k: v for k, v in w.items() if v > 0}
            
        target_w_dict = get_w_local(ms['regime'], smh_cond)

        all_tkrs = set([t for t in asset_vals.keys()] + list(target_w_dict.keys()))
        for tkr in all_tkrs:
            tkr = tkr.upper()
            my_v = asset_vals.get(tkr, 0.0)
            my_w = (my_v / total_val * 100) if total_val > 0 else 0.0
            tw = target_w_dict.get(tkr, 0.0)
            tv = target_seed * tw
            diff = tv - my_v
            cp = live_prices.get(tkr, 0.0)
            
            if tkr != "CASH" and cp > 0:
                shares_to_trade = abs(diff) / cp
                action_suffix = f" (약 {shares_to_trade:.1f}주)"
            else:
                action_suffix = ""

            if abs(diff) < 50: action = "적정 (유지)"
            elif diff > 0: action = f"🟢 ${diff:,.0f} 매수{action_suffix}"
            else: action = f"🔴 ${abs(diff):,.0f} 매도{action_suffix}"
            
            if my_v > 0 or tw > 0: 
                status_d.append({"종목": tkr, "목표비중": f"{tw*100:.1f}%", "현재비중": f"{my_w:.1f}%", "목표액": f"${tv:,.0f}", "현재액": f"${my_v:,.0f}", "액션": action})
                
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
                if '매수' in val_s: return 'color: #ff4b4b; font-weight: bold;'
                elif '매도' in val_s: return 'color: #3498db; font-weight: bold;'
                return ''
            st.dataframe(status_df.style.map(color_act, subset=['액션']), use_container_width=True, hide_index=True)


        # --- 📈 자산 가치 추이: 운용 시드 곡선 ---
        st.write("")
        st.markdown("**[ 📈 00시 종가 기준 운용 시드(Target Seed) 성장 곡선 ]**")
        
        if target_seed > 0:
            with st.container(border=True):
                fed_str = curr_acc_data.get("first_entry_date")
                default_date = pd.to_datetime(fed_str).date() if fed_str else (datetime.today() - timedelta(days=90)).date()
                col_date, _ = st.columns([1, 3])
                with col_date:
                    u_date = st.date_input("투자 시작일 (시뮬레이션 기점)", value=default_date, key=f"date_{acc_name}")
                    if str(u_date) != str(fed_str)[:10]: 
                        st.session_state['accounts'][acc_name]["first_entry_date"] = str(u_date)
                        save_accounts_data(st.session_state['accounts'])
                
                try:
                    chart_start_ts = pd.Timestamp(u_date)
                    fetch_start = (chart_start_ts - timedelta(days=5)).strftime('%Y-%m-%d')
                    bench_data = yf.download("QQQ", start=fetch_start, progress=False)['Close'].ffill()
                    
                    if not bench_data.empty:
                        if isinstance(bench_data, pd.DataFrame): bench_series = bench_data.iloc[:, 0]
                        else: bench_series = bench_data
                        
                        bench_series = bench_series[bench_series.index >= chart_start_ts]
                        seed_curve = (bench_series / bench_series.iloc[0]) * target_seed
                        
                        fig_seed = go.Figure()
                        fig_seed.add_trace(go.Scatter(x=seed_curve.index, y=seed_curve.values, name="운용 시드 궤적", line=dict(color='#00d1ff', width=3), fill='tozeroy', fillcolor='rgba(0, 209, 255, 0.1)'))
                        fig_seed.add_trace(go.Scatter(x=seed_curve.index, y=[target_seed]*len(seed_curve), name="현재 시드 원금", line=dict(color='#e74c3c', width=2, dash='dot')))
                        fig_seed.update_layout(height=350, template="plotly_dark", margin=dict(l=10,r=10,t=10,b=10), yaxis_title="운용 자산 ($)", hovermode="x unified")
                        st.plotly_chart(fig_seed, use_container_width=True)
                except Exception as e: pass

        # 하단 로그
        st.write("")
        col_log1, col_log2 = st.columns([1.5, 1])
        with col_log1:
            st.markdown("**[ 매매 복기 일지 ]**")
            def save_j(): st.session_state['accounts'][acc_name]["journal_text"] = st.session_state[f"j_{acc_name}"]; save_accounts_data(st.session_state['accounts'])
            st.text_area("시장의 주요 이슈와 매매 감정을 자유롭게 기록하세요.", value=curr_acc_data.get('journal_text', ''), key=f"j_{acc_name}", height=150, on_change=save_j, label_visibility="collapsed")
        with col_log2:
            st.markdown("**[ 시스템 로그 ]**")
            history = curr_acc_data.get('history', [])
            if history: st.dataframe(pd.DataFrame(history)[::-1], hide_index=True, use_container_width=True, height=150)

    page_func.__name__ = f"pf_{abs(hash(acc_name))}"
    return page_func


# --- 페이지 구성: 계좌 관리 ---
def page_manage_accounts():
    st.title("⚙️ 포트폴리오 계좌 관리")
    new_acc = st.text_input("신규 계좌 이름")
    if st.button("🚀 계좌 개설", type="primary") and new_acc:
        if new_acc not in st.session_state['accounts']:
            st.session_state['accounts'][new_acc] = {"portfolio": [{"티커 (Ticker)": t, "수량 (주/달러)": 0.0, "평균 단가 ($)": 0.0, "매입 환율": 0.0} for t in REQUIRED_TICKERS], "history": [{"Date": datetime.now().strftime("%Y-%m-%d"), "Log": "✨ 계좌 개설"}], "target_seed": 10000.0}
            save_accounts_data(st.session_state['accounts']); st.rerun()
    st.divider()
    for acc in list(st.session_state['accounts'].keys()):
        c1, c2 = st.columns([4, 1])
        c1.write(f"💼 **{acc}**")
        if c2.button("삭제", key=f"del_{acc}", disabled=len(st.session_state['accounts']) <=1):
            del st.session_state['accounts'][acc]; save_accounts_data(st.session_state['accounts']); st.rerun()

# --- 페이지 구성: 전략 명세서 ---
def page_strategy_specification():
    st.title("📜 AMLS 적응형 다중 레버리지 전략 명세서")
    st.caption("DEPARTMENT OF QUANTITATIVE STRATEGY | 정량전략부 공식 문서")
    st.markdown("""---""")

    with st.container():
        st.markdown("### 🏷️ 버전: v4.3 (단계적 진입 로직)")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.info("**문서 요약**\n- **기준 자산:** QQQ (나스닥100 ETF)\n- **레짐 판단:** QQQ vs 200일 MA + VIX + MA50/MA200 골든크로스\n- **전환 규칙:** 하향 즉시 / 상향 5일 확인 (확인 중 한 단계 위 배분 적용)\n- **핵심 ETF:** TQQQ, SOXL, USD, QLD, SSO, QQQ, SPY, GLD")
        with col_s2:
            st.success("**목표 지표**\n- **목표 MDD:** -35% 이내\n- **진화 단계:** v4 → v4.2 → v4.3\n- **핵심 가치:** 하락장 생존 및 상승장 초입 수익 극대화")

    st.markdown("### I. 진화 경로: v4 → v4.2 → v4.3")
    st.markdown("- **v4 (기본):** 4단계 레짐(R1~R4)과 비대칭 전환 규칙(하향 즉시, 상향 5일 확인) 확립.\n- **v4.2 (R2/R3 개선):** R2 레버리지를 1.45x에서 1.75x로 상향. R3의 GLD 비중을 50%로 높여 폭락장 방어 강화.\n- **v4.3 (단계적 진입):** 상향 전환 5일 확인 대기 기간 동안 기존 레짐이 아닌 **한 단계 위 레짐 배분**을 적용하여 수익 누락 방지.")

    st.markdown("### II. 레짐 판단 기준")
    st.table(pd.DataFrame({"우선순위": ["1", "2", "3", "4"], "조건": ["VIX > 40", "QQQ < 200일 MA", "QQQ > MA200 & MA50 > MA200 & VIX < 25", "위 조건 모두 불충족"], "목표 레짐": ["R4 (위기)", "R3 (약세)", "R1 (강세)", "R2 (보통)"]}))

    st.markdown("### III. 레짐별 자산 배분표 (v4.3)")
    tabs = st.tabs(["Regime 1", "Regime 2", "Regime 3", "Regime 4"])
    with tabs[0]: st.write("**실효 레버리지: 약 2.25배**"); st.table(pd.DataFrame({"종목": ["TQQQ", "SOXL/USD", "QLD", "SSO", "GLD", "현금"], "비중": ["30%", "20%", "20%", "15%", "10%", "5%"]}))
    with tabs[1]: st.write("**실효 레버리지: 약 1.75배**"); st.table(pd.DataFrame({"종목": ["QLD", "SSO", "GLD", "USD", "QQQ", "현금"], "비중": ["30%", "25%", "20%", "10%", "5%", "10%"]}))
    with tabs[2]: st.write("**실효 레버리지: 약 0.15배**"); st.table(pd.DataFrame({"종목": ["QQQ", "GLD", "현금"], "비중": ["15%", "50%", "35%"]}))
    with tabs[3]: st.write("**실효 레버리지: 약 0.10배**"); st.table(pd.DataFrame({"종목": ["GLD", "QQQ", "현금"], "비중": ["50%", "10%", "40%"]}))

    st.markdown("### IV. 반도체 동적 스위칭 (SOXL/USD)")
    st.write("R1 반도체 슬롯(20%)은 아래 세 조건을 모두 충족할 때만 **SOXL(3x)**을 사용합니다.\n- SMH > SMH 50일 MA (추세 상승)\n- SMH 3개월 수익률 > 5% (중기 모멘텀)\n- SMH RSI(14) > 50 (과매도 탈출)")


# =====================================================================
# [5] 네비게이션 라우팅
# =====================================================================
pages = {
    "🌐 마켓 터미널": [st.Page(page_market_dashboard, title="실시간 시장 지표", icon="🗺️")],
    "📊 백테스팅": [st.Page(page_amls_backtest, title="AMLS 시뮬레이터", icon="🦅")],
    "🏦 내 포트폴리오": [],
    "📜 전략 가이드": [st.Page(page_strategy_specification, title="공식 명세서 (v4.3)", icon="📄")]
}

for name in st.session_state['accounts'].keys():
    pages["🏦 내 포트폴리오"].append(st.Page(make_portfolio_page(name), title=name, icon="💼"))

pages["🏦 내 포트폴리오"].append(st.Page(page_manage_accounts, title="⚙️ 계좌 관리", icon="⚙️"))

# 사이드바 데이터 백업
with st.sidebar.expander("💾 백업/복구"):
    st.download_button("📥 백업 받기", data=json.dumps(st.session_state['accounts']), file_name="amls_backup.json")
    up_f = st.file_uploader("📤 복구하기", type=['json'])
    if up_f and st.button("⚠️ 복구 실행"):
        st.session_state['accounts'] = json.load(up_f)
        save_accounts_data(st.session_state['accounts'])
        st.rerun()

pg = st.navigation(pages)
pg.run()
