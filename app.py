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

warnings.filterwarnings('ignore')

# =====================================================================
# [0] 시스템 설정 및 동적 테마 엔진
# =====================================================================
st.set_page_config(page_title="AMLS 퀀트 포트폴리오", layout="wide", initial_sidebar_state="expanded")

SETTINGS_FILE = "amls_settings_v11.json"
ACCOUNTS_FILE = "amls_multi_accounts.json"
REQUIRED_TICKERS = ["TQQQ", "QLD", "QQQ", "SOXL", "USD", "SSO", "GLD", "SPY", "CASH"] 

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"theme": "애플 테마"}

def save_settings(settings_data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings_data, f, ensure_ascii=False, indent=4)

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

# =====================================================================
# [1] 세션 스테이트 (초기화 및 마이그레이션)
# =====================================================================
if 'settings' not in st.session_state:
    st.session_state['settings'] = load_settings()

if 'accounts' not in st.session_state:
    loaded = load_accounts_data()
    if not loaded:
        loaded = {
            "AMLS v4.4": {  
                "portfolio": [{"티커 (Ticker)": t, "수량 (주/달러)": 0.0, "평균 단가 ($)": 0.0, "매입 환율": 0.0, "태그": "코어"} for t in REQUIRED_TICKERS],
                "history": [], "first_entry_date": None, "journal_text": "", "target_seed": 10000.0, "seed_history": {}, "target_portfolio_value": 100000.0,
                "layout_order": ["🎯 목표 달성률", "📊 실시간 요약", "⚡ 시스템 분석관", "🚀 실전 퀀트 무기", "💼 포트폴리오 & 리밸런싱", "🧩 자산 상관관계 히트맵", "🔮 10년 은퇴 시뮬레이션", "📈 성장 곡선", "📈 목표 달성률 추이", "📝 매매 일지"]
            }
        }
    st.session_state['accounts'] = loaded

needs_save = False
if "기본 계좌 (AMLS)" in st.session_state['accounts']:
    st.session_state['accounts']["AMLS v4.4"] = st.session_state['accounts'].pop("기본 계좌 (AMLS)")
    needs_save = True
if "AMLS v4.3" in st.session_state['accounts']:
    st.session_state['accounts']["AMLS v4.4"] = st.session_state['accounts'].pop("AMLS v4.3")
    needs_save = True

for acc_name, acc_data in st.session_state['accounts'].items():
    if "seed_history" not in acc_data: acc_data["seed_history"] = {}; needs_save = True
    if "target_portfolio_value" not in acc_data: acc_data["target_portfolio_value"] = 100000.0; needs_save = True
    if "layout_order" not in acc_data: 
        acc_data["layout_order"] = ["🎯 목표 달성률", "📊 실시간 요약", "⚡ 시스템 분석관", "🚀 실전 퀀트 무기", "💼 포트폴리오 & 리밸런싱", "🧩 자산 상관관계 히트맵", "🔮 10년 은퇴 시뮬레이션", "📈 성장 곡선", "📈 목표 달성률 추이", "📝 매매 일지"]
        needs_save = True

    existing_tickers = [item["티커 (Ticker)"] for item in acc_data["portfolio"]]
    port_dict = {item["티커 (Ticker)"]: item for item in acc_data["portfolio"]}
    new_port = []
    for req_t in REQUIRED_TICKERS:
        if req_t in port_dict: 
            item = port_dict[req_t]
            if "매입 환율" not in item: item["매입 환율"] = 0.0; needs_save = True
            if "태그" not in item: item["태그"] = "코어" if req_t != "CASH" else "현금"; needs_save = True
            new_port.append(item)
        else: 
            new_port.append({"티커 (Ticker)": req_t, "수량 (주/달러)": 0.0, "평균 단가 ($)": 0.0, "매입 환율": 0.0, "태그": "코어" if req_t != "CASH" else "현금"})
            needs_save = True
    acc_data["portfolio"] = new_port

if needs_save: save_accounts_data(st.session_state['accounts'])


# =====================================================================
# [2] 동적 테마 엔진 (애플 테마 고정)
# =====================================================================
TEXT_COLOR = "#1d1d1f"; TEXT_SUB = "#8e8e93"
PANEL_BG = "rgba(255,255,255,0.65)"; PANEL_BORDER = "1px solid rgba(255,255,255,0.5)"; PANEL_RADIUS = "16px"
WIDGET_THEME = "light"
C_UP = "#34c759"; C_DOWN = "#ff3b30"; C_WARN = "#ff9500"; C_SAFE = "#007aff"
BASE_CHART_COLORS = {'TQQQ':'#ff3b30', 'SOXL':'#af52de', 'USD':'#5856d6', 'QLD':'#ff9500', 'SSO':'#ffcc00', 'QQQ':'#007aff', 'SPY':'#34a853', 'GLD':'#34c759', 'CASH':'#8e8e93'}

if "text_color" not in st.session_state['settings']: st.session_state['settings']["text_color"] = TEXT_COLOR
if "chart_colors" not in st.session_state['settings']: st.session_state['settings']["chart_colors"] = BASE_CHART_COLORS.copy()
for tkr in REQUIRED_TICKERS:
    if tkr not in st.session_state['settings']["chart_colors"]:
        st.session_state['settings']["chart_colors"][tkr] = BASE_CHART_COLORS.get(tkr, "#888888")

TEXT_COLOR = st.session_state['settings']["text_color"]
COLOR_PALETTE = st.session_state['settings']["chart_colors"]

THEME_LAYOUT = dict(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_COLOR, size=13), margin=dict(l=0, r=0, t=30, b=0), xaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.05)'), yaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.05)'))

def apply_custom_css():
    css_base = f"""
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
    .stApp {{ background: radial-gradient(circle at 15% 50%, rgba(240, 244, 255, 1), rgba(255, 255, 255, 0)), radial-gradient(circle at 85% 30%, rgba(230, 240, 255, 1), rgba(255, 255, 255, 0)); background-color: #f5f5f7; font-family: 'Pretendard', sans-serif; color: {TEXT_COLOR}; letter-spacing: -0.01em; }}
    div[data-testid="stVerticalBlockBorderWrapper"] > div, .st-emotion-cache-1104k38, .st-emotion-cache-16txtl3 {{ background: {PANEL_BG}; backdrop-filter: blur(20px); border: {PANEL_BORDER}; border-radius: 20px; box-shadow: 0 4px 24px -1px rgba(0, 0, 0, 0.06); padding: 1.5rem; transition: transform 0.2s ease, box-shadow 0.2s ease; }}
    .stButton>button {{ background-color: rgba(255, 255, 255, 0.8); color: #007aff; border: 1px solid rgba(0, 122, 255, 0.3); border-radius: 12px; font-weight: 600; padding: 0.5rem 1rem; backdrop-filter: blur(10px); transition: all 0.2s; }}
    .stButton>button:hover {{ background-color: #007aff; color: #ffffff; transform: scale(1.02); }}
    input, textarea, select, div[data-baseweb="select"] > div {{ background-color: rgba(255, 255, 255, 0.5); backdrop-filter: blur(10px); color: {TEXT_COLOR}; border: 1px solid rgba(0,0,0,0.1); border-radius: 12px; }}
    [data-testid="stDataFrame"] {{ border-radius: 16px; border: 1px solid rgba(0,0,0,0.05); background: rgba(255, 255, 255, 0.5); }}
    [data-testid="stSidebar"] {{ background: rgba(245, 245, 247, 0.7); backdrop-filter: blur(20px); border-right: 1px solid rgba(0,0,0,0.05); }}
    button[data-baseweb="tab"][aria-selected="true"] {{ color: #1d1d1f; border-bottom-color: #1d1d1f; border-bottom-width: 2px; }}
    .sidebar-link {{ display: flex; align-items: center; padding: 8px 12px; margin-bottom: 4px; border-radius: 10px; text-decoration: none !important; color: {TEXT_COLOR}; font-weight: 600; font-size: 0.95rem; transition: background-color 0.2s, transform 0.1s; }}
    .sidebar-link:hover {{ background-color: rgba(0,0,0,0.05); transform: translateX(2px); }}
    div[data-testid="stMetricValue"] > div, div[data-testid="stMetricDelta"] > div, p, span, label, .stMarkdown {{ white-space: normal !important; word-break: keep-all !important; overflow-wrap: break-word !important; }}
    div[data-testid="stMetricValue"] {{ font-weight: bold; font-size: 1.8rem; color: {TEXT_COLOR}; }}
    .info-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px; }}
    @media (max-width: 800px) {{ .info-grid {{ grid-template-columns: 1fr; }} }}
    .info-panel {{ background: {PANEL_BG}; border: {PANEL_BORDER}; border-radius: {PANEL_RADIUS}; padding: 16px; height: 100%; box-shadow: 0 4px 12px rgba(0,0,0,0.03); display: flex; flex-direction: column; justify-content: center; }}
    """
    st.markdown(f"<style>{css_base}</style>", unsafe_allow_html=True)

apply_custom_css()

# --- Plotly Sparkline (미니 차트) 생성 함수 ---
def get_plotly_sparkline(data_list, color, hline=None):
    if not data_list or all(pd.isna(x) for x in data_list): return go.Figure()
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=data_list, mode='lines', line=dict(color=color, width=2), hoverinfo='skip'))
    if hline is not None:
        fig.add_hline(y=hline, line_dash="dash", line_color="red", line_width=1)
    fig.update_layout(
        showlegend=False, margin=dict(l=0, r=0, t=0, b=0), height=40,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
    )
    return fig

def get_plotly_dual_sparkline(d1, d2, c1, c2):
    if not d1 or not d2: return go.Figure()
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=d2, mode='lines', line=dict(color=c2, width=1.5, dash='dash'), hoverinfo='skip'))
    fig.add_trace(go.Scatter(y=d1, mode='lines', line=dict(color=c1, width=2), hoverinfo='skip'))
    fig.update_layout(
        showlegend=False, margin=dict(l=0, r=0, t=0, b=0), height=40,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
    )
    return fig


# =====================================================================
# [3] 글로벌 백엔드 함수
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
    
    actual_regime_v4_4 = []
    current_v4_4 = 3
    pend_v4_4 = None
    cnt_v4_4 = 0

    for i in range(len(df)):
        tr = df['Target_Regime'].iloc[i]
        
        if tr > current_v4_4: 
            current_v4_4 = tr; pend_v4_4 = None; cnt_v4_4 = 0; actual_regime_v4_4.append(current_v4_4)
        elif tr < current_v4_4:
            if tr == pend_v4_4:
                cnt_v4_4 += 1
                if cnt_v4_4 >= 5: current_v4_4 = tr; pend_v4_4 = None; cnt_v4_4 = 0; actual_regime_v4_4.append(current_v4_4)
                else: actual_regime_v4_4.append(current_v4_4 - 1)
            else: 
                pend_v4_4 = tr; cnt_v4_4 = 1; actual_regime_v4_4.append(current_v4_4 - 1)
        else: 
            pend_v4_4 = None; cnt_v4_4 = 0; actual_regime_v4_4.append(current_v4_4)

    df['Signal_Regime_v4_4'] = pd.Series(actual_regime_v4_4, index=df.index).shift(1).bfill()

    def get_v4_4_weights(regime, use_soxl):
        w = {t: 0.0 for t in data.columns}; semi = 'SOXL' if use_soxl else 'USD'
        if regime == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'], w['SPY'] = 0.30, 0.20, 0.20, 0.15, 0.10, 0.05
        elif regime == 2: w['QLD'], w['SSO'], w['GLD'], w['USD'], w['QQQ'], w['SPY'] = 0.30, 0.25, 0.25, 0.10, 0.05, 0.05
        elif regime == 3: w['GLD'], w['QQQ'] = 0.50, 0.15
        elif regime == 4: w['GLD'], w['QQQ'] = 0.50, 0.10
        total_w = sum(w.values())
        if total_w < 1.0: w['CASH'] = round(1.0 - total_w, 4)
        return w

    strategies = ['AMLS v4.4', 'QQQ', 'QLD', 'TQQQ']
    ports = {s: init_cap for s in strategies}
    hists = {s: [init_cap] for s in ports.keys()}
    total_invested = init_cap
    weights_v4_4 = {t: 0.0 for t in data.columns}; weights_v4_4['CASH'] = 1.0
    logs, days_since_v4_4 = [], 0

    for i in range(1, len(df)):
        today, yesterday = df.index[i], df.index[i-1]
        days_since_v4_4 += 1
        
        ret_v4_4 = 0
        for t in data.columns: ret_v4_4 += weights_v4_4.get(t, 0) * daily_returns[t].iloc[i]
        
        ports['AMLS v4.4'] *= (1 + ret_v4_4)
        for s in ['QQQ', 'QLD', 'TQQQ']: ports[s] *= (1 + daily_returns[s].iloc[i])
        
        for t in data.columns:
            if ports['AMLS v4.4'] > 0: weights_v4_4[t] = weights_v4_4.get(t,0)*(1+daily_returns[t].iloc[i])/(1+ret_v4_4)
        if ports['AMLS v4.4'] > 0: weights_v4_4['CASH'] = weights_v4_4.get('CASH',0) / (1+ret_v4_4)
            
        if today.month != yesterday.month:
            for s in ports: ports[s] += monthly_cont
            total_invested += monthly_cont
        for s in ports: hists[s].append(ports[s])
        
        use_soxl = (df['SMH'].iloc[i-1] > df['SMH_MA50'].iloc[i-1]) and (df['SMH_3M_Ret'].iloc[i-1] > 0.05) and (df['SMH_RSI'].iloc[i-1] > 50)

        sig_r_v4_4 = df['Signal_Regime_v4_4'].iloc[i]
        rebal_v4_4 = False
        if sig_r_v4_4 != df['Signal_Regime_v4_4'].iloc[i-1] or i == 1: rebal_v4_4 = True
        elif rebal_freq == "월 1회" and today.month != yesterday.month: rebal_v4_4 = True
        elif "주 1회" in rebal_freq and days_since_v4_4 >= 5: rebal_v4_4 = True
        elif "2주 1회" in rebal_freq and days_since_v4_4 >= 10: rebal_v4_4 = True
        elif "3주 1회" in rebal_freq and days_since_v4_4 >= 15: rebal_v4_4 = True
        
        if rebal_v4_4:
            weights_v4_4 = get_v4_4_weights(sig_r_v4_4, use_soxl)
            log_type = "레짐 전환" if sig_r_v4_4 != df['Signal_Regime_v4_4'].iloc[i-1] else f"정기 ({rebal_freq.split(' ')[0]})"
            semi_target = "SOXL" if use_soxl and sig_r_v4_4 == 1 else ("USD" if sig_r_v4_4 in [1, 2] else "-")
            logs.append({"날짜": today.strftime('%Y-%m-%d'), "유형": log_type, "국면": f"R{int(sig_r_v4_4)}", "반도체": semi_target, "평가액": ports['AMLS v4.4']})
            days_since_v4_4 = 0

    for s in ports: df[f'{s}_Value'] = hists[s]
    inv_arr = [init_cap]; curr_inv = init_cap
    for i in range(1, len(df)):
        if df.index[i].month != df.index[i-1].month: curr_inv += monthly_cont
        inv_arr.append(curr_inv)
    df['Invested'] = inv_arr
    return df, logs, data.columns

# 마켓 터미널 전용 주도 섹터 스캐너 함수
@st.cache_data(ttl=3600)
def get_sector_momentum():
    sectors = {'XLK':'기술', 'XLV':'헬스케어', 'XLE':'에너지', 'XLF':'금융', 'XLI':'산업재',
               'XLY':'소비재', 'XLP':'필수소비재', 'XLU':'유틸리티', 'XLB':'소재', 'XLRE':'부동산'}
    try:
        data = yf.download(list(sectors.keys()), period="6mo", progress=False)['Close'].ffill()
        sector_returns = {}
        for s, k_name in sectors.items():
            if s in data.columns and not data[s].dropna().empty:
                if len(data[s].dropna()) > 63:
                    ret3m = (data[s].iloc[-1] / data[s].iloc[-64]) - 1
                    sector_returns[k_name] = ret3m
        return sorted(sector_returns.items(), key=lambda x: x[1], reverse=True)[:3]
    except:
        return []

# =====================================================================
# [4] 페이지 구성: 글로벌 마켓 대시보드
# =====================================================================
def page_market_dashboard():
    st.title("🌐 매크로 터미널")
    
    components.html(f"""<div class="tradingview-widget-container" style="border-radius: {PANEL_RADIUS}; overflow: hidden; border: {PANEL_BORDER};">
<div class="tradingview-widget-container__widget"></div>
<script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>
{{
"symbols": [
{{"proName": "FOREXCOM:SPXUSD", "title": "S&P 500"}},
{{"proName": "FOREXCOM:NSXUSD", "title": "NASDAQ 100"}},
{{"description": "TQQQ", "proName": "NASDAQ:TQQQ"}},
{{"description": "SOXL", "proName": "ARCA:SOXL"}},
{{"description": "USD/KRW", "proName": "FX_IDC:USDKRW"}},
{{"description": "GOLD", "proName": "OANDA:XAUUSD"}}
],
"showSymbolLogo": true, "colorTheme": "{WIDGET_THEME}", "locale": "kr"
}}
</script>
</div>""", height=70)

    col_left, col_right = st.columns([1, 1.8])
    with col_left:
        with st.container(border=True):
            st.markdown("##### 📈 주요 지수")
            tickers = ['^GSPC', '^IXIC', '^VIX', 'USDKRW=X']
            indices_df = yf.download(tickers, start=datetime.today()-timedelta(days=365), progress=False)['Close'].ffill()
            if not indices_df.empty:
                c1, c2 = st.columns(2); latest = indices_df.iloc[-1]; prev = indices_df.iloc[-2]
                c1.metric("S&P 500", f"{latest.get('^GSPC', 0):,.0f}", f"{(latest.get('^GSPC',0)/prev.get('^GSPC',1)-1)*100:+.2f}%")
                c2.metric("NASDAQ", f"{latest.get('^IXIC', 0):,.0f}", f"{(latest.get('^IXIC',0)/prev.get('^IXIC',1)-1)*100:+.2f}%")
                c3, c4 = st.columns(2)
                c3.metric("VIX", f"{latest.get('^VIX', 0):,.2f}", f"{(latest.get('^VIX',0)/prev.get('^VIX',1)-1)*100:+.2f}%", delta_color="inverse")
                c4.metric("USD/KRW", f"₩{latest.get('USDKRW=X', 0):,.1f}", f"{(latest.get('USDKRW=X',0)/prev.get('USDKRW=X',1)-1)*100:+.2f}%", delta_color="inverse")
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=indices_df.index, y=indices_df['^GSPC']/indices_df['^GSPC'].iloc[0]*100, name="S&P 500", line=dict(color=C_SAFE, width=2)))
                fig.add_trace(go.Scatter(x=indices_df.index, y=indices_df['^IXIC']/indices_df['^IXIC'].iloc[0]*100, name="NASDAQ", line=dict(color=C_UP, width=2)))
                custom_l = THEME_LAYOUT.copy(); custom_l.update(height=240, showlegend=False)
                fig.update_layout(**custom_l)
                st.plotly_chart(fig, use_container_width=True)

    with col_right:
        with st.container(border=True):
            st.markdown("##### 🗺️ 글로벌 증시 히트맵")
            tab_sp, tab_ndx = st.tabs(["S&P 500", "NASDAQ 100"])
            
            with tab_sp:
                components.html(f"""
                <div class="tradingview-widget-container">
                  <div class="tradingview-widget-container__widget"></div>
                  <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js" async>
                  {{
                  "exchanges": [],
                  "dataSource": "SPX500",
                  "grouping": "sector",
                  "blockSize": "market_cap_basic",
                  "blockColor": "change",
                  "locale": "kr",
                  "colorTheme": "{WIDGET_THEME}",
                  "hasTopBar": false,
                  "isDataSetEnabled": false,
                  "isZoomEnabled": true,
                  "hasSymbolTooltip": true,
                  "width": "100%",
                  "height": "400"
                }}
                  </script>
                </div>
                """, height=400)
            with tab_ndx:
                components.html(f"""
                <div class="tradingview-widget-container">
                  <div class="tradingview-widget-container__widget"></div>
                  <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js" async>
                  {{
                  "exchanges": [],
                  "dataSource": "NDX",
                  "grouping": "sector",
                  "blockSize": "market_cap_basic",
                  "blockColor": "change",
                  "locale": "kr",
                  "colorTheme": "{WIDGET_THEME}",
                  "hasTopBar": false,
                  "isDataSetEnabled": false,
                  "isZoomEnabled": true,
                  "hasSymbolTooltip": true,
                  "width": "100%",
                  "height": "400"
                }}
                  </script>
                </div>
                """, height=400)

    st.markdown("---")
    col_mac1, col_mac2 = st.columns([1, 1.8])
    
    with col_mac1:
        with st.container(border=True):
            st.markdown("##### 🛢️ 금리 & 원자재 & 크립토")
            macro_tickers = ['^TNX', 'CL=F', 'GC=F', 'BTC-USD']
            macro_names = {'^TNX': '미 10년물 국채금리', 'CL=F': 'WTI 원유', 'GC=F': '국제 금', 'BTC-USD': '비트코인'}
            
            try:
                macro_df = yf.download(macro_tickers, period="5d", progress=False)['Close'].ffill()
                if not macro_df.empty:
                    latest_m = macro_df.iloc[-1]
                    prev_m = macro_df.iloc[-2]
                    
                    mc1, mc2 = st.columns(2)
                    mc1.metric(macro_names['^TNX'], f"{latest_m.get('^TNX', 0):.3f}%", f"{(latest_m.get('^TNX', 0) - prev_m.get('^TNX', 0)):+.3f}bp", delta_color="inverse")
                    mc2.metric(macro_names['CL=F'], f"${latest_m.get('CL=F', 0):.2f}", f"{(latest_m.get('CL=F', 0)/prev_m.get('CL=F', 1)-1)*100:+.2f}%", delta_color="inverse")
                    
                    st.write("")
                    mc3, mc4 = st.columns(2)
                    mc3.metric(macro_names['GC=F'], f"${latest_m.get('GC=F', 0):,.1f}", f"{(latest_m.get('GC=F', 0)/prev_m.get('GC=F', 1)-1)*100:+.2f}%")
                    mc4.metric(macro_names['BTC-USD'], f"${latest_m.get('BTC-USD', 0):,.0f}", f"{(latest_m.get('BTC-USD', 0)/prev_m.get('BTC-USD', 1)-1)*100:+.2f}%")
            except:
                st.info("데이터를 불러오는 중입니다...")
                
        with st.container(border=True):
            st.markdown("##### 🔄 주도 섹터 스캐너 (3개월 수익률 TOP 3)")
            top_sectors = get_sector_momentum()
            if top_sectors:
                sec_html = ""
                for i, (s_name, s_ret) in enumerate(top_sectors):
                    medals = ["🥇", "🥈", "🥉"]
                    sec_html += f"<div style='display:flex; justify-content:space-between; margin-bottom:6px;'><span style='font-weight:bold; color:{TEXT_COLOR};'>{medals[i]} {s_name}</span><span style='color:{C_UP if s_ret>0 else C_DOWN}; font-weight:bold;'>{s_ret*100:+.1f}%</span></div>"
                st.markdown(f"<div style='padding: 10px; border-radius: 10px; background-color: rgba(0,0,0,0.03);'>{sec_html}</div>", unsafe_allow_html=True)
            else:
                st.info("데이터 로딩 중...")

    with col_mac2:
        with st.container(border=True):
            st.markdown("##### 🔥 시장 주도주 (Top Gainers & Losers)")
            components.html(f"""
            <div class="tradingview-widget-container">
              <div class="tradingview-widget-container__widget"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-hotlists.js" async>
              {{
              "colorTheme": "{WIDGET_THEME}",
              "dateRange": "12M",
              "exchange": "US",
              "showChart": true,
              "locale": "kr",
              "largeChartUrl": "",
              "isTransparent": true,
              "showSymbolLogo": true,
              "showFloatingTooltip": false,
              "width": "100%",
              "height": "350"
            }}
              </script>
            </div>
            """, height=350)

    st.markdown("---")
    with st.container(border=True):
        st.markdown("##### 🇺🇸 미국 핵심 경제 캘린더 (한국어)")
        components.html(f"""
        <div class="tradingview-widget-container">
          <div class="tradingview-widget-container__widget"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-events.js" async>
          {{
          "colorTheme": "{WIDGET_THEME}",
          "isTransparent": true,
          "width": "100%",
          "height": "450",
          "locale": "kr",
          "importanceFilter": "0,1",
          "currencyFilter": "USD"
        }}
          </script>
        </div>
        """, height=450)


# =====================================================================
# [5] 페이지 구성: AMLS 백테스트
# =====================================================================
def page_amls_backtest():
    st.title("🦅 V4.4 전략 시뮬레이터")

    st.sidebar.header("⚙️ 시뮬레이션 설정")
    BACKTEST_START = st.sidebar.date_input("시작일", datetime(2018, 1, 1))
    BACKTEST_END = st.sidebar.date_input("종료일", datetime.today())
    INITIAL_CAPITAL = st.sidebar.number_input("초기 자본금 ($)", value=10000, step=1000)
    MONTHLY_CONTRIBUTION = st.sidebar.number_input("월 적립금 ($)", value=2000, step=500)
    REBAL_FREQ = st.sidebar.selectbox("🔄 리밸런싱 주기", ["월 1회", "주 1회 (5거래일)", "2주 1회 (10거래일)", "3주 1회 (15거래일)"], index=0)

    with st.spinner('과거 데이터를 분석 중입니다...'):
        df, logs, tickers = load_amls_backtest_data(BACKTEST_START, BACKTEST_END, INITIAL_CAPITAL, MONTHLY_CONTRIBUTION, REBAL_FREQ)
    
    def calc_metrics(series, invested_series):
        final_val = series.iloc[-1]; total_inv = invested_series.iloc[-1]
        total_ret = (final_val / total_inv) - 1
        days = (series.index[-1] - series.index[0]).days
        cagr = (final_val / invested_series.iloc[-1]) ** (365.25 / days) - 1 if days > 0 else 0
        mdd = ((series / series.cummax()) - 1).min()
        daily_ret = series.pct_change().dropna()
        sharpe = (daily_ret.mean() * 252) / (daily_ret.std() * np.sqrt(252)) if daily_ret.std() != 0 else 0
        return final_val, total_ret, cagr, mdd, sharpe

    strats = ['AMLS v4.4', 'QQQ', 'QLD', 'TQQQ']
    metrics_data = []
    for s in strats:
        fv, tr, cagr, mdd, shp = calc_metrics(df[f'{s}_Value'], df['Invested'])
        metrics_data.append({"전략": s, "최종 금액": f"${fv:,.0f}", "수익률": f"{tr*100:+.1f}%", "CAGR": f"{cagr*100:.1f}%", "MDD": f"{mdd*100:.1f}%", "샤프": f"{shp:.2f}"})
    metrics_df = pd.DataFrame(metrics_data).set_index("전략")

    tab1, tab2, tab3 = st.tabs(["📊 요약", "📈 성장 곡선", "📝 매매 로그"])

    with tab1:
        st.markdown("#### 🏆 성과 요약")
        st.info(f"투입 원금: ${df['Invested'].iloc[-1]:,.0f}")
        st.dataframe(metrics_df, use_container_width=True)

        st.markdown("#### 🥧 V4.4 국면별 비중")
        c1, c2, c3, c4 = st.columns(4)
        def get_w(reg):
            if reg == 1: return {'TQQQ':30, 'SOXL/USD':20, 'QLD':20, 'SSO':15, 'GLD':10, 'SPY':5}
            elif reg == 2: return {'QLD':30, 'SSO':25, 'GLD':25, 'USD':10, 'QQQ':5, 'SPY':5}
            elif reg == 3: return {'GLD':50, 'CASH':35, 'QQQ':15}
            elif reg == 4: return {'GLD':50, 'CASH':40, 'QQQ':10}
        
        for i, col in enumerate([c1, c2, c3, c4]):
            r = i+1; w = {k:v for k,v in get_w(r).items() if v>0}
            fig_p = go.Figure(go.Pie(labels=list(w.keys()), values=list(w.values()), hole=0.5, marker=dict(colors=[COLOR_PALETTE.get(k.split('/')[0], '#888') for k in w.keys()])))
            cust_p = THEME_LAYOUT.copy(); cust_p.update(title=f"R{r}", title_x=0.5, height=250, margin=dict(t=40,b=10,l=10,r=10), showlegend=False)
            fig_p.update_layout(**cust_p)
            fig_p.update_traces(textinfo='label+percent', textposition='inside', textfont=dict(color="#ffffff", size=11))
            col.plotly_chart(fig_p, use_container_width=True)

    with tab2:
        st.markdown("#### 📈 자산 곡선")
        use_log = st.checkbox("Y축 로그 스케일", value=False)
        fig_eq = go.Figure()
        
        fig_eq.add_trace(go.Scatter(x=df.index, y=df['AMLS v4.4_Value'], name='AMLS v4.4', line=dict(color=C_UP, width=3)))
        fig_eq.add_trace(go.Scatter(x=df.index, y=df['QQQ_Value'], name='QQQ', line=dict(color=C_SAFE, width=1.5)))
        fig_eq.add_trace(go.Scatter(x=df.index, y=df['TQQQ_Value'], name='TQQQ', line=dict(color=C_DOWN, width=1.5)))
        fig_eq.add_trace(go.Scatter(x=df.index, y=df['Invested'], name='원금', line=dict(color='#888', width=1.5, dash='dot')))
        
        if use_log: fig_eq.update_yaxes(type="log")
        cust_eq = THEME_LAYOUT.copy(); cust_eq.update(height=450, hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        fig_eq.update_layout(**cust_eq)
        st.plotly_chart(fig_eq, use_container_width=True)

    with tab3:
        st.markdown("#### 📝 매매 로그")
        log_df = pd.DataFrame(logs)[::-1]
        if not log_df.empty:
            log_df['평가액'] = log_df['평가액'].apply(lambda x: f"${x:,.0f}")
            st.dataframe(log_df, hide_index=True, use_container_width=True, height=400)


# =====================================================================
# [6] 페이지 구성: 내 포트폴리오 관리 
# =====================================================================
def make_portfolio_page(acc_name):
    def page_func():
        st.title(f"💼 {acc_name}")
        
        curr_acc_data = st.session_state['accounts'][acc_name]
        
        DEFAULT_LAYOUT = ["🎯 목표 달성률", "📊 실시간 요약", "⚡ 시스템 분석관", "🚀 실전 퀀트 무기", "💼 포트폴리오 & 리밸런싱", "🧩 자산 상관관계 히트맵", "🔮 10년 은퇴 시뮬레이션", "📈 성장 곡선", "📈 목표 달성률 추이", "📝 매매 일지"]
        current_layout = curr_acc_data.get("layout_order", [])
        
        if "💼 기입표" in current_layout: current_layout[current_layout.index("💼 기입표")] = "💼 포트폴리오 & 리밸런싱"
        if "🍩 자산 배분 & 지침" in current_layout: current_layout.remove("🍩 자산 배분 & 지침")
        if "🍩 배분 및 지침" in current_layout: current_layout.remove("🍩 배분 및 지침")
            
        for item in DEFAULT_LAYOUT:
            if item not in current_layout: current_layout.append(item)
        current_layout = [x for x in current_layout if x in DEFAULT_LAYOUT]
        
        if current_layout != curr_acc_data.get("layout_order", []):
            curr_acc_data["layout_order"] = current_layout
            save_accounts_data(st.session_state['accounts'])

        pf_df = pd.DataFrame(curr_acc_data["portfolio"])
        for col in ["수량 (주/달러)", "평균 단가 ($)", "매입 환율"]:
            if col in pf_df.columns: pf_df[col] = pf_df[col].astype(float)

        @st.cache_data(ttl=1800)
        def get_market_status():
            TICKERS = ['QQQ', 'TQQQ', 'SOXL', 'USD', 'QLD', 'SSO', 'SPY', 'SMH', 'GLD', '^VIX',
                       'HYG', 'IEF', 'QQQE']
            data = yf.download(TICKERS, start=datetime.today()-timedelta(days=400), progress=False)['Close'].ffill()
            today = data.iloc[-1]; yesterday = data.iloc[-2]
            
            ma200_s = data['QQQ'].rolling(200).mean()
            ma50_s = data['QQQ'].rolling(50).mean()
            smh_ma50_s = data['SMH'].rolling(50).mean()
            smh_3m_ret_s = data['SMH'].pct_change(63)
            smh_rsi_s = ta.rsi(data['SMH'], length=14)
            qqq_rsi_s = ta.rsi(data['QQQ'], length=14)
            
            target_regimes = []
            for i in range(len(data)):
                v = data['^VIX'].iloc[i]; q = data['QQQ'].iloc[i]; m200 = ma200_s.iloc[i]; m50 = ma50_s.iloc[i]
                if pd.isna(m200): target_regimes.append(2); continue
                if v > 40: target_regimes.append(4)
                elif q < m200: target_regimes.append(3)
                elif q >= m200 and m50 >= m200 and v < 25: target_regimes.append(1)
                else: target_regimes.append(2)
                
            current_v4_4 = 3; pend_v4_4 = None; cnt_v4_4 = 0; actual_regime_v4_4 = []
            regime_entry_dates = []; current_entry_date = data.index[0]
            
            for i, tr in enumerate(target_regimes):
                prev_regime_state = current_v4_4
                if tr > current_v4_4: 
                    current_v4_4 = tr; pend_v4_4 = None; cnt_v4_4 = 0; actual_regime_v4_4.append(current_v4_4)
                elif tr < current_v4_4:
                    if tr == pend_v4_4:
                        cnt_v4_4 += 1
                        if cnt_v4_4 >= 5: current_v4_4 = tr; pend_v4_4 = None; cnt_v4_4 = 0; actual_regime_v4_4.append(current_v4_4)
                        else: actual_regime_v4_4.append(current_v4_4 - 1)
                    else: 
                        pend_v4_4 = tr; cnt_v4_4 = 1; actual_regime_v4_4.append(current_v4_4 - 1)
                else: 
                    pend_v4_4 = None; cnt_v4_4 = 0; actual_regime_v4_4.append(current_v4_4)
                    
                if actual_regime_v4_4[-1] != prev_regime_state:
                    current_entry_date = data.index[i]
                regime_entry_dates.append(current_entry_date)
                    
            applied_series = pd.Series(actual_regime_v4_4, index=data.index).shift(1).bfill()
            entry_dates_series = pd.Series(regime_entry_dates, index=data.index).shift(1).bfill()
            
            current_reg = applied_series.iloc[-1]
            regime_start_date = entry_dates_series.iloc[-1]
            regime_duration = len(data.loc[regime_start_date:])

            target_reg = int(target_regimes[-1])
            is_waiting = (pend_v4_4 is not None and target_reg < current_v4_4)

            hyg_ief_ratio = data['HYG'] / data['IEF']
            hyg_ief_ma50 = hyg_ief_ratio.rolling(50).mean().iloc[-1]
            hyg_ief_curr = hyg_ief_ratio.iloc[-1]
            
            qqq_20d = (data['QQQ'].iloc[-1] / data['QQQ'].iloc[-21]) - 1 if len(data) > 21 else 0
            if 'QQQE' in data.columns and len(data['QQQE'].dropna()) > 21:
                qqqe_20d = (data['QQQE'].iloc[-1] / data['QQQE'].iloc[-21]) - 1
            else: qqqe_20d = qqq_20d

            try:
                fx_data = yf.download('USDKRW=X', period='5d', progress=False)['Close'].ffill()
                current_usdkrw = float(fx_data.iloc[:, 0].iloc[-1] if isinstance(fx_data, pd.DataFrame) else fx_data.iloc[-1])
            except: current_usdkrw = 0.0

            hist_len = 45
            hist_vix = data['^VIX'].tail(hist_len).fillna(method='bfill').tolist()
            hist_qqq = data['QQQ'].tail(hist_len).fillna(method='bfill').tolist()
            hist_ma200 = ma200_s.tail(hist_len).fillna(method='bfill').tolist()
            hist_ma50 = ma50_s.tail(hist_len).fillna(method='bfill').tolist()

            return {
                'regime': int(current_reg), 'target_regime': target_reg, 'is_waiting': is_waiting, 'wait_days': cnt_v4_4, 
                'regime_duration': regime_duration, 'regime_start_date': regime_start_date,
                'vix': today['^VIX'], 'qqq': today['QQQ'], 'ma200': ma200_s.iloc[-1], 'ma50': ma50_s.iloc[-1],
                'qqq_rsi': qqq_rsi_s.iloc[-1],
                'smh': today['SMH'], 'smh_ma50': smh_ma50_s.iloc[-1], 'smh_3m_ret': smh_3m_ret_s.iloc[-1], 'smh_rsi': smh_rsi_s.iloc[-1],
                'prices': today.to_dict(), 'prev_prices': yesterday.to_dict(), 'date': data.index[-1], 'usdkrw': current_usdkrw,
                'hyg_ief_curr': hyg_ief_curr, 'hyg_ief_ma50': hyg_ief_ma50,
                'qqq_20d': qqq_20d, 'qqqe_20d': qqqe_20d,
                'hist_vix': hist_vix, 'hist_qqq': hist_qqq, 'hist_ma200': hist_ma200, 'hist_ma50': hist_ma50
            }

        @st.cache_data(ttl=60)
        def get_realtime_prices():
            RT_TICKERS = ['QQQ', 'TQQQ', 'SOXL', 'USD', 'QLD', 'SSO', 'SPY', 'SMH', 'GLD', '^VIX', 'USDKRW=X']
            try:
                rt = yf.download(RT_TICKERS, period='1d', interval='5m', prepost=True, progress=False)['Close']
                if rt.empty: return None
                return rt.ffill().iloc[-1].to_dict()
            except: return None

        with st.spinner("AI 엔진 및 데이터 동기화 중..."): 
            ms = get_market_status()
            rt_prices = get_realtime_prices()

        if rt_prices:
            for k, v in rt_prices.items():
                if k in ms['prices'] and pd.notna(v): ms['prices'][k] = v
            if pd.notna(rt_prices.get('^VIX', None)): ms['vix'] = rt_prices['^VIX']
            if pd.notna(rt_prices.get('QQQ', None)): ms['qqq'] = rt_prices['QQQ']
            if pd.notna(rt_prices.get('SMH', None)): ms['smh'] = rt_prices['SMH']
            if pd.notna(rt_prices.get('USDKRW=X', None)): ms['usdkrw'] = rt_prices['USDKRW=X']
            
            vix_rt, qqq_rt = ms['vix'], ms['qqq']
            if vix_rt > 40: rt_tgt = 4
            elif qqq_rt < ms['ma200']: rt_tgt = 3
            elif qqq_rt >= ms['ma200'] and ms['ma50'] >= ms['ma200'] and vix_rt < 25: rt_tgt = 1
            else: rt_tgt = 2
            
            ms['target_regime'] = rt_tgt
            if rt_tgt > ms['regime']:
                ms['regime'] = rt_tgt
                ms['is_waiting'] = False
            
            from datetime import timezone
            now_utc = datetime.now(timezone.utc)
            et_hour = (now_utc.hour - 5) % 24 
            if 4 <= et_hour < 9.5: price_label = "Pre"
            elif 9.5 <= et_hour < 16: price_label = "Live"
            elif 16 <= et_hour < 20: price_label = "After"
            else: price_label = "Live"
        else: price_label = "Close"

        live_prices = {k: ms['prices'].get(k, 1.0) for k in REQUIRED_TICKERS}; live_prices['CASH'] = 1.0
        prev_prices = {k: ms['prev_prices'].get(k, live_prices[k]) for k in REQUIRED_TICKERS}; prev_prices['CASH'] = 1.0
        current_usdkrw = ms['usdkrw']
        
        disp_df = pf_df.copy()
        disp_df["현재가 ($)"] = disp_df["티커 (Ticker)"].apply(lambda x: live_prices.get(x, 0.0))
        disp_df["현재 환율"] = current_usdkrw
        
        def cy(row):
            if row["수량 (주/달러)"] == 0 or row["평균 단가 ($)"] == 0 or row["티커 (Ticker)"] == "CASH": return 0.0
            return (row["현재가 ($)"] - row["평균 단가 ($)"]) / row["평균 단가 ($)"] * 100
        disp_df["수익률 (%)"] = disp_df.apply(cy, axis=1)
        
        def cy_krw(row):
            if row["수량 (주/달러)"] == 0 or row["평균 단가 ($)"] == 0 or row["티커 (Ticker)"] == "CASH": return 0.0
            if row["매입 환율"] <= 0 or current_usdkrw <= 0: return 0.0
            buy_krw = row["평균 단가 ($)"] * row["매입 환율"]; now_krw = row["현재가 ($)"] * current_usdkrw
            return (now_krw - buy_krw) / buy_krw * 100
        disp_df["원화 수익률 (%)"] = disp_df.apply(cy_krw, axis=1)

        total_val_now = 0.0; total_val_yest = 0.0; auto_seed = 0.0
        best_ticker = "-"; best_ret = -999.0
        asset_vals = {}; weights_dict = {}
        
        for _, row in disp_df.iterrows():
            tkr = str(row["티커 (Ticker)"]).upper().strip()
            qty = float(row["수량 (주/달러)"] if pd.notna(row["수량 (주/달러)"]) else 0)
            avg_p = float(row["평균 단가 ($)"] if pd.notna(row["평균 단가 ($)"]) else 0)
            
            v_now = qty * live_prices.get(tkr, 0.0) if tkr != "CASH" else qty
            v_yest = qty * prev_prices.get(tkr, 0.0) if tkr != "CASH" else qty
            
            if v_now > 0: asset_vals[tkr] = v_now
            if qty > 0:
                total_val_now += v_now
                total_val_yest += v_yest
                auto_seed += qty if tkr == "CASH" else qty * avg_p
                r_ret = row["수익률 (%)"]
                if tkr != "CASH" and r_ret > best_ret: best_ret = r_ret; best_ticker = tkr

        if total_val_now > 0:
            for k, v in asset_vals.items(): weights_dict[k] = v / total_val_now

        daily_diff = total_val_now - total_val_yest
        daily_diff_pct = (daily_diff / total_val_yest * 100) if total_val_yest > 0 else 0.0

        st.session_state['accounts'][acc_name]["target_seed"] = auto_seed
        rebal_base = total_val_now if total_val_now > 0 else auto_seed

        today_str = datetime.now().strftime("%Y-%m-%d")
        history_changed = False
        last_seed = curr_acc_data["seed_history"].get(today_str, {}).get("seed")
        last_equity = curr_acc_data["seed_history"].get(today_str, {}).get("equity")
        if total_val_now > 0 or auto_seed > 0:
            if last_seed != auto_seed or last_equity != total_val_now:
                curr_acc_data["seed_history"][today_str] = {"seed": auto_seed, "equity": total_val_now}
                history_changed = True
        if history_changed: save_accounts_data(st.session_state['accounts'])

        with st.sidebar.expander("🛠️ 화면 레이아웃 편집"):
            st.caption("위아래 버튼으로 순서를 변경하세요.")
            for i, block_name in enumerate(current_layout):
                c_name, c_up, c_dn = st.columns([5, 1, 1])
                c_name.markdown(f"<div style='padding-top:5px; font-size: 0.9rem;'>{i+1}. {block_name}</div>", unsafe_allow_html=True)
                if c_up.button("▲", key=f"up_{i}_{acc_name}") and i > 0:
                    current_layout[i], current_layout[i-1] = current_layout[i-1], current_layout[i]
                    curr_acc_data["layout_order"] = current_layout
                    save_accounts_data(st.session_state['accounts']); st.rerun()
                if c_dn.button("▼", key=f"dn_{i}_{acc_name}") and i < len(current_layout)-1:
                    current_layout[i], current_layout[i+1] = current_layout[i+1], current_layout[i]
                    curr_acc_data["layout_order"] = current_layout
                    save_accounts_data(st.session_state['accounts']); st.rerun()

        for block in current_layout:
            
            if block == "🎯 목표 달성률":
                target_val = curr_acc_data.get("target_portfolio_value", 100000.0)
                progress_pct = (total_val_now / target_val) * 100 if target_val > 0 else 0.0
                
                st.markdown("#### 🎯 포트폴리오 목표 달성률")
                c_prog, c_set = st.columns([4, 1.2])
                with c_set:
                    new_target = st.number_input("목표 금액 설정", min_value=0.0, value=float(target_val), step=10000.0, format="%.0f", key=f"tgt_{acc_name}")
                    if new_target != target_val:
                        st.session_state['accounts'][acc_name]["target_portfolio_value"] = new_target
                        save_accounts_data(st.session_state['accounts'])
                        st.rerun()
                with c_prog:
                    pb_bg = "rgba(0,0,0,0.1)"
                    st.markdown(f"""<div class='info-panel' style='display:flex; flex-direction:column; justify-content:center;'>
<div style='display:flex; justify-content:space-between; margin-bottom:8px; font-weight:bold; font-size:1.05rem;'>
<span>현재: ${total_val_now:,.0f}</span>
<span style='color:{C_DOWN};'>목표: ${target_val:,.0f}</span>
</div>
<div style='background-color:{pb_bg}; border-radius:8px; height:16px; width:100%; position:relative; overflow:hidden;'>
<div style='background-color:{C_UP}; width:{min(100.0, progress_pct)}%; height:100%; border-radius:8px;'></div>
</div>
<div style='text-align:right; margin-top:5px; font-weight:bold;'>{progress_pct:.2f}%</div>
</div>""", unsafe_allow_html=True)
                st.write("")

            elif block == "📊 실시간 요약":
                st.markdown(f"#### 📊 자산 및 시황 요약 (기준: {price_label})")
                pn_col = C_UP if daily_diff > 0 else (C_DOWN if daily_diff < 0 else TEXT_COLOR)
                pn_ico = "▲" if daily_diff > 0 else ("▼" if daily_diff < 0 else "-")
                st.markdown(f"""
                <div class='info-panel' style='display:flex; flex-direction:row; justify-content:space-between; align-items:center; text-align:center; padding:20px;'>
                    <div style='flex:1; border-right:1px dashed rgba(150,150,150,0.4); padding:0 10px;'>
                        <div style='font-size:0.85rem; font-weight:bold; opacity:0.8; color:{TEXT_COLOR};'>💰 총 평가액 (Total)</div>
                        <div style='font-size:1.6rem; font-weight:bold; margin-top:5px; color:{TEXT_COLOR};'>${total_val_now:,.0f}</div>
                    </div>
                    <div style='flex:1; border-right:1px dashed rgba(150,150,150,0.4); padding:0 10px;'>
                        <div style='font-size:0.85rem; font-weight:bold; opacity:0.8; color:{TEXT_COLOR};'>일간 손익 (Daily)</div>
                        <div style='color:{pn_col}; font-size:1.6rem; font-weight:bold; margin-top:5px;'>{pn_ico} {abs(daily_diff_pct):.2f}%</div>
                        <div style='color:{pn_col}; font-size:0.8rem;'>({daily_diff:+.0f} $)</div>
                    </div>
                    <div style='flex:1; padding:0 10px;'>
                        <div style='font-size:0.85rem; font-weight:bold; opacity:0.8; color:{TEXT_COLOR};'>👑 포트폴리오 MVP</div>
                        <div style='font-size:1.6rem; font-weight:bold; margin-top:5px; color:{TEXT_COLOR};'>{best_ticker}</div>
                        <div style='font-size:0.8rem; font-weight:bold; color:{TEXT_COLOR};'>수익률 {best_ret:+.1f}%</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.write("")
                
            elif block == "⚡ 시스템 분석관":
                st.markdown("#### ⚡ 실시간 시스템 분석관 요약")
                app_reg = ms['regime']
                tgt_reg = ms['target_regime']
                is_wait = ms['is_waiting']
                wait_d = ms['wait_days']
                dur = ms['regime_duration']
                start_dt = ms['regime_start_date'].strftime('%Y-%m-%d')
                
                vix_c = ms['vix']; qqq_c = ms['qqq']; ma200_c = ms['ma200']; smh_c = ms['smh']; smh_ma50_c = ms['smh_ma50']; ma50_c = ms['ma50']
                
                s_stat = "✅ 돌파" if smh_c > smh_ma50_c else "❌ 붕괴"
                s_col = C_UP if smh_c > smh_ma50_c else C_DOWN
                r_stat = "✅ 통과" if ms['smh_3m_ret'] > 0.05 else "❌ 미달"
                r_col = C_UP if ms['smh_3m_ret'] > 0.05 else C_DOWN
                rsi_stat = "✅ 통과" if ms['smh_rsi'] > 50 else "❌ 미달"
                rsi_col = C_UP if ms['smh_rsi'] > 50 else C_DOWN
                
                is_soxl_appr = (smh_c > smh_ma50_c and ms['smh_3m_ret'] > 0.05 and ms['smh_rsi'] > 50)
                soxl_res = f"<span style='color:{C_UP}; font-weight:bold;'>✅ SOXL 편입 승인</span>" if is_soxl_appr else f"<span style='color:{C_WARN}; font-weight:bold;'>⚠️ USD 방어 유지</span>"
                soxl_bg = "rgba(52, 199, 89, 0.15)" if is_soxl_appr else "rgba(255, 149, 0, 0.15)"

                wait_msg = ""
                if is_wait and tgt_reg < app_reg:
                    wait_msg = f"<div style='margin-top:6px; padding:6px; background-color:rgba(255,193,7,0.15); border-left:3px solid #ffc107; font-size:0.8rem;'><span style='color:#ff9800; font-weight:bold;'>⏳ 상향 전환 검증 진행 중 ({wait_d}/5일차)</span><br>휩쏘 방지를 위해 R{app_reg} 유지 중</div>"
                elif tgt_reg > app_reg:
                    wait_msg = f"<div style='margin-top:6px; padding:6px; background-color:rgba(231,76,60,0.15); border-left:3px solid #e74c3c; font-size:0.8rem;'><span style='color:#e74c3c; font-weight:bold;'>🚨 하락 전환 주의</span><br>내일 아침 즉시 하향 전환(R{tgt_reg}) 예상</div>"

                dur_text = f"<br><span style='color:{C_SAFE}; font-weight:bold;'>⏱️ 현재 R{app_reg} 진입일: {start_dt} ({dur}일째 체류 중)</span>"

                if app_reg == 1:
                    reg_t = f"<span style='color:{C_UP}; font-weight:bold;'>[R1: 완벽한 강세장]</span>"
                    reg_d = f"<div style='margin-bottom: 5px;'><span style='color:{C_UP};'>■</span> <b>거시 및 추세 진단:</b> VIX 지수({vix_c:.1f})가 하향 안정화되었으며, 나스닥(QQQ)이 장기 추세선(200MA)을 확고히 지지하고 있습니다. 시장의 위험 선호 심리가 지배적인 완벽한 정배열 상승 국면입니다.</div><div><span style='color:{C_UP};'>■</span> <b>운용 전략:</b> 포트폴리오의 공격성을 최대치로 끌어올려 상승 랠리에 동참해야 합니다. 3배수 레버리지(TQQQ) 비중을 확대하여 벤치마크 대비 초과 수익(Alpha)을 극대화하십시오.</div>{dur_text}{wait_msg}"
                elif app_reg == 2:
                    reg_t = f"<span style='color:{C_WARN}; font-weight:bold;'>[R2: 조정/경계]</span>"
                    reg_d = f"<div style='margin-bottom: 5px;'><span style='color:{C_WARN};'>■</span> <b>거시 및 추세 진단:</b> 장기 추세는 유효하나 VIX 지수({vix_c:.1f})가 상승하며 시장 노이즈가 발생하고 있습니다. 단기 모멘텀(50MA) 약화로 인한 기술적 피로도가 누적된 상태입니다.</div><div><span style='color:{C_WARN};'>■</span> <b>운용 전략:</b> 변동성 확대에 대비해 수익금 보존에 집중해야 할 시기입니다. 3배수 투기 비중을 축소하고, 2배수(QLD, USD) 및 방어 자산(GLD) 비중을 늘려 포트폴리오 안전 마진을 확보하십시오.</div>{dur_text}{wait_msg}"
                elif app_reg == 3:
                    reg_t = f"<span style='color:{C_DOWN}; font-weight:bold;'>[R3: 장기 하락장]</span>"
                    reg_d = f"<div style='margin-bottom: 5px;'><span style='color:{C_DOWN};'>■</span> <b>거시 및 추세 진단:</b> 나스닥(QQQ)이 핵심 지지선인 200일 이평선을 하향 이탈하며 중장기 역배열 추세가 컨펌되었습니다. 자본 이탈이 가속화되는 베어마켓 진입 초기일 가능성이 높습니다.</div><div><span style='color:{C_DOWN};'>■</span> <b>운용 전략:</b> 주식형 레버리지 상품을 전면 청산하고 극단적인 방어 태세를 갖추십시오. 자산의 절반 이상을 안전 자산(GLD, CASH)으로 대피시켜 계좌의 치명적 손실(MDD)을 방어해야 합니다.</div>{dur_text}{wait_msg}"
                else:
                    reg_t = f"<span style='color:{C_DOWN}; font-weight:bold;'>[R4: 시스템 패닉]</span>"
                    reg_d = f"<div style='margin-bottom: 5px;'><span style='color:{C_DOWN};'>■</span> <b>거시 및 추세 진단:</b> VIX 지수가 40을 돌파({vix_c:.1f})하며 극단적 공포 현상이 지표로 확인되었습니다. 거시 경제 펀더멘털의 심각한 균열이 의심되는 시스템 리스크 구간입니다.</div><div><span style='color:{C_DOWN};'>■</span> <b>운용 전략:</b> 모든 투기적 포지션을 즉시 중단하십시오. '살아남는 것'이 유일한 목표이며, 무모한 바닥 잡기(Water-fishing)를 지양하고 시장이 이성을 되찾을 때까지 현금 보유 비중을 최대로 유지하십시오.</div>{dur_text}{wait_msg}"

                vix_status = "🔴 패닉 (>40)" if vix_c > 40 else ("🟡 경계 (25~40)" if vix_c >= 25 else "🟢 안정 (<25)")
                vix_col = C_DOWN if vix_c > 40 else (C_WARN if vix_c >= 25 else C_UP)
                trend_status = "🟢 상승" if qqq_c >= ma200_c else "🔴 하락"
                trend_col = C_UP if qqq_c >= ma200_c else C_DOWN
                trend_gap = (qqq_c / ma200_c - 1) * 100
                align_status = "🟢 정배열" if ma50_c >= ma200_c else "🔴 역배열"
                align_col = C_UP if ma50_c >= ma200_c else C_DOWN
                align_gap = (ma50_c / ma200_c - 1) * 100

                html_str = f"""
<div class='info-grid'>
<div class='info-panel' style='display:flex; flex-direction:column; justify-content:space-between;'>
<div style='font-weight:bold; margin-bottom:12px; border-bottom:1px solid currentColor; padding-bottom:6px; opacity:0.8;'>⚡ SOXL 진입 판독기</div>
<div style='display: flex; flex-direction: column; gap: 10px;'>
<div style='background: rgba(0,0,0,0.04); padding: 10px 14px; border-radius: 8px; border-left: 4px solid {s_col};'>
<div style='display: flex; justify-content: space-between; align-items: center;'>
<span style='font-size: 0.75rem; opacity: 0.8;'>① 50MA 추세</span>
<span style='font-size: 0.85rem; font-weight: bold; color: {s_col};'>{s_stat}</span>
</div>
<div style='display: flex; justify-content: space-between; align-items: center; margin-top: 4px;'>
<span style='font-size: 1.1rem; font-weight: bold;'>${smh_c:.2f}</span>
<span style='font-size: 0.75rem; opacity: 0.6;'>기준: ${smh_ma50_c:.2f}</span>
</div>
</div>
<div style='background: rgba(0,0,0,0.04); padding: 10px 14px; border-radius: 8px; border-left: 4px solid {r_col};'>
<div style='display: flex; justify-content: space-between; align-items: center;'>
<span style='font-size: 0.75rem; opacity: 0.8;'>② 3M 수익률</span>
<span style='font-size: 0.85rem; font-weight: bold; color: {r_col};'>{r_stat}</span>
</div>
<div style='display: flex; justify-content: space-between; align-items: center; margin-top: 4px;'>
<span style='font-size: 1.1rem; font-weight: bold;'>{ms['smh_3m_ret']*100:+.2f}%</span>
<span style='font-size: 0.75rem; opacity: 0.6;'>기준: +5.0% 이상</span>
</div>
</div>
<div style='background: rgba(0,0,0,0.04); padding: 10px 14px; border-radius: 8px; border-left: 4px solid {rsi_col};'>
<div style='display: flex; justify-content: space-between; align-items: center;'>
<span style='font-size: 0.75rem; opacity: 0.8;'>③ 과열/침체 (RSI)</span>
<span style='font-size: 0.85rem; font-weight: bold; color: {rsi_col};'>{rsi_stat}</span>
</div>
<div style='display: flex; justify-content: space-between; align-items: center; margin-top: 4px;'>
<span style='font-size: 1.1rem; font-weight: bold;'>{ms['smh_rsi']:.1f}</span>
<span style='font-size: 0.75rem; opacity: 0.6;'>기준: 50.0 이상</span>
</div>
</div>
</div>
<div style='margin-top:15px; padding:12px; border-radius:8px; background-color:{soxl_bg}; text-align: center;'>
<div style='font-size: 1rem; font-weight: bold;'>{soxl_res}</div>
</div>
</div>

<div class='info-panel' style='grid-column: span 2; display:flex; flex-direction:column; justify-content:flex-start;'>
<div style='font-weight:bold; margin-bottom:8px; border-bottom:1px solid currentColor; padding-bottom:4px; opacity:0.8;'>🤖 AI 전략 분석관 리서치 Report</div>
<div style='font-size:0.9rem; line-height:1.7; padding-top: 5px;'>
<div style='font-size:1.1rem; margin-bottom:8px;'>{reg_t}</div>
{reg_d}
</div>
<div style='margin-top: auto; padding-top: 15px; border-top: 1px dashed currentColor; opacity: 0.9;'>
<div style='font-weight:bold; margin-bottom:10px; font-size: 0.85rem;'>🔍 타겟 국면(Regime) 산출 근거 시각화 <span style='font-weight:normal; opacity:0.8;'>(현재 AI 타겟: R{tgt_reg})</span></div>
</div>
</div>
</div>
"""
                st.markdown(html_str, unsafe_allow_html=True)
                
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.markdown(f"""<div style='text-align:center; padding: 10px; background: rgba(0,0,0,0.04); border-radius: 8px; min-width: 120px;'>
<div style='font-size: 0.75rem; opacity: 0.8;'>조건 1. 공포 지수 (VIX)</div>
<div style='font-size: 1.05rem; font-weight: bold; color: {vix_col}; margin-top: 5px;'>{vix_status}</div>
</div>""", unsafe_allow_html=True)
                    st.plotly_chart(get_plotly_sparkline(ms['hist_vix'], vix_col, hline=40 if vix_c>30 else 25), use_container_width=True, config={'displayModeBar': False})
                    st.markdown(f"<div style='text-align:center; font-size: 0.7rem; margin-top: -10px; opacity: 0.7;'>현재: {vix_c:.2f}</div>", unsafe_allow_html=True)
                with m2:
                    st.markdown(f"""<div style='text-align:center; padding: 10px; background: rgba(0,0,0,0.04); border-radius: 8px; min-width: 120px;'>
<div style='font-size: 0.75rem; opacity: 0.8;'>조건 2. 장기 추세 (QQQ)</div>
<div style='font-size: 1.05rem; font-weight: bold; color: {trend_col}; margin-top: 5px;'>{trend_status}</div>
</div>""", unsafe_allow_html=True)
                    st.plotly_chart(get_plotly_dual_sparkline(ms['hist_qqq'], ms['hist_ma200'], trend_col, 'rgba(150,150,150,0.5)'), use_container_width=True, config={'displayModeBar': False})
                    st.markdown(f"<div style='text-align:center; font-size: 0.7rem; margin-top: -10px; opacity: 0.7;'>200MA 이격: {trend_gap:+.1f}%</div>", unsafe_allow_html=True)
                with m3:
                    st.markdown(f"""<div style='text-align:center; padding: 10px; background: rgba(0,0,0,0.04); border-radius: 8px; min-width: 120px;'>
<div style='font-size: 0.75rem; opacity: 0.8;'>조건 3. 이평선 배열</div>
<div style='font-size: 1.05rem; font-weight: bold; color: {align_col}; margin-top: 5px;'>{align_status}</div>
</div>""", unsafe_allow_html=True)
                    st.plotly_chart(get_plotly_dual_sparkline(ms['hist_ma50'], ms['hist_ma200'], align_col, 'rgba(150,150,150,0.5)'), use_container_width=True, config={'displayModeBar': False})
                    st.markdown(f"<div style='text-align:center; font-size: 0.7rem; margin-top: -10px; opacity: 0.7;'>50MA 이격: {align_gap:+.1f}%</div>", unsafe_allow_html=True)

                st.write("")
                
            elif block == "🚀 실전 퀀트 무기":
                st.markdown("#### 🚀 실전 퀀트 무기 (Macro & Momentum)")
                
                q_rsi = ms['qqq_rsi']
                if q_rsi > 70: dca_col, dca_stat, dca_desc = C_DOWN, "🔥 과열 (Overbought)", "QQQ RSI가 70 초과. 신규 자금 투입 <b>보류 권장</b>."
                elif q_rsi < 30: dca_col, dca_stat, dca_desc = C_UP, "❄️ 바닥 (Oversold)", "QQQ RSI가 30 미만. 적립금 <b>200% 투입 권장</b>."
                else: dca_col, dca_stat, dca_desc = C_SAFE, "🟢 정상 (Neutral)", "적절한 가격대. 계획된 <b>월 적립금 정상 투입</b>."

                sm_curr, sm_ma50 = ms['hyg_ief_curr'], ms['hyg_ief_ma50']
                if pd.notna(sm_curr) and pd.notna(sm_ma50):
                    if sm_curr < sm_ma50: sm_col, sm_stat, sm_desc = C_DOWN, "🚨 자금 이탈 (Risk-Off)", "하이일드 투매 현상. 증시 폭락 선행 지표 감지."
                    else: sm_col, sm_stat, sm_desc = C_UP, "✅ 자금 유입 (Risk-On)", "스마트머니가 위험 자산에 안정적으로 체류 중."
                else: sm_col, sm_stat, sm_desc = TEXT_SUB, "데이터 부족", "데이터 로딩 중"

                q_20, qe_20 = ms['qqq_20d'], ms['qqqe_20d']
                if q_20 > 0 and qe_20 < 0: br_col, br_stat, br_desc = C_WARN, "⚠️ 가짜 상승 (Divergence)", "지수는 오르나 대다수 종목 하락. 소수 대형주 독주."
                elif q_20 < 0 and qe_20 > 0: br_col, br_stat, br_desc = C_UP, "💡 숨은 강세 (Accumulation)", "지수는 내리나 대다수 반등 중. 폭넓은 매수세 유입."
                else: br_col, br_stat, br_desc = C_SAFE, "🟢 건전한 동조화", "시총 가중치와 동일 가중치가 함께 움직임."

                st.markdown(f"""
                <div style='display: flex; gap: 15px; margin-bottom: 15px; flex-wrap: wrap;'>
                    <div style='flex: 1; min-width: 250px; background: {PANEL_BG}; border: {PANEL_BORDER}; border-radius: {PANEL_RADIUS}; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.03);'>
                        <div style='font-weight:bold; margin-bottom:8px; border-bottom:1px dashed rgba(150,150,150,0.4); padding-bottom:4px;'>💰 스마트 DCA (자금 투입)</div>
                        <div style='font-size:0.85rem; line-height:1.6;'>
                            <span style='color:{dca_col}; font-weight:bold; font-size:1rem;'>{dca_stat}</span><br>
                            <span style='opacity:0.9;'>{dca_desc}</span>
                        </div>
                    </div>
                    <div style='flex: 1; min-width: 250px; background: {PANEL_BG}; border: {PANEL_BORDER}; border-radius: {PANEL_RADIUS}; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.03);'>
                        <div style='font-weight:bold; margin-bottom:8px; border-bottom:1px dashed rgba(150,150,150,0.4); padding-bottom:4px;'>🚨 채권 스프레드 (스마트머니)</div>
                        <div style='font-size:0.85rem; line-height:1.6;'>
                            <span style='color:{sm_col}; font-weight:bold; font-size:1rem;'>{sm_stat}</span><br>
                            <span style='opacity:0.9;'>{sm_desc}</span>
                        </div>
                    </div>
                    <div style='flex: 1; min-width: 250px; background: {PANEL_BG}; border: {PANEL_BORDER}; border-radius: {PANEL_RADIUS}; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.03);'>
                        <div style='font-weight:bold; margin-bottom:8px; border-bottom:1px dashed rgba(150,150,150,0.4); padding-bottom:4px;'>⚖️ 시장 폭 (Market Breadth)</div>
                        <div style='font-size:0.85rem; line-height:1.6;'>
                            <span style='color:{br_col}; font-weight:bold; font-size:1rem;'>{br_stat}</span><br>
                            <span style='opacity:0.9;'>{br_desc}</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.write("")

            elif block == "💼 포트폴리오 & 리밸런싱":
                st.markdown(f"#### 💼 포트폴리오 기입 및 현황")
                col_tab, col_pie = st.columns([1.6, 1])
                
                with col_tab:
                    def color_y(val):
                        if isinstance(val, (int, float)):
                            if val > 0: return f'color: {C_UP}; font-weight: bold;'
                            elif val < 0: return f'color: {C_DOWN}; font-weight: bold;'
                        return ''

                    ed_disp = st.data_editor(
                        disp_df.style.map(color_y, subset=["수익률 (%)", "원화 수익률 (%)"]), 
                        num_rows="dynamic", use_container_width=True, height=320, key=f"ed_{acc_name}",
                        column_order=["태그", "티커 (Ticker)", "수량 (주/달러)", "평균 단가 ($)", "매입 환율", "현재가 ($)", "수익률 (%)", "원화 수익률 (%)"],
                        column_config={
                            "태그": st.column_config.SelectboxColumn("태그", options=["코어", "위성", "헷지", "현금", "단기픽"], required=True),
                            "티커 (Ticker)": st.column_config.TextColumn("종목명"),
                            "현재가 ($)": st.column_config.NumberColumn("현재가 💵", disabled=True, format="$ %.2f"),
                            "현재 환율": st.column_config.NumberColumn("현재 환율 💱", disabled=True, format="₩ %.1f"),
                            "수익률 (%)": st.column_config.NumberColumn("수익률 📈", disabled=True, format="%.2f %%"),
                            "원화 수익률 (%)": st.column_config.NumberColumn("원화 수익 🇰🇷", disabled=True, format="%.2f %%"),
                            "매입 환율": st.column_config.NumberColumn("매입 환율 💱", format="₩ %.1f"),
                        }
                    )
                    base_cols = ["티커 (Ticker)", "수량 (주/달러)", "평균 단가 ($)", "매입 환율", "태그"]
                    if not ed_disp[base_cols].equals(pf_df[base_cols]):
                        st.session_state['accounts'][acc_name]["portfolio"] = ed_disp[base_cols].to_dict(orient="records")
                        save_accounts_data(st.session_state['accounts']); st.rerun()

                with col_pie:
                    with st.container(border=True):
                        if total_val_now > 0:
                            fig = go.Figure(go.Pie(labels=list(asset_vals.keys()), values=list(asset_vals.values()), hole=0.6, marker=dict(colors=[COLOR_PALETTE.get(k.split('/')[0], '#888') for k in asset_vals.keys()])))
                            cust_p2 = THEME_LAYOUT.copy()
                            cust_p2.update(height=280, showlegend=False, margin=dict(t=10, b=10, l=10, r=10), annotations=[dict(text=f"100%", x=0.5, y=0.5, showarrow=False, font=dict(color=TEXT_COLOR, size=16))])
                            fig.update_layout(**cust_p2)
                            fig.update_traces(textposition='inside', textinfo='percent+label', textfont_size=13, textfont_color="#fff")
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.markdown("<div style='height: 280px; display: flex; align-items: center; justify-content: center; color: #888;'>자산을 입력해 주세요.</div>", unsafe_allow_html=True)
                
                st.write("")
                st.markdown("#### ⚖️ 기계적 리밸런싱 지침 (Tolerance: ±1.5주)")
                with st.container(border=True):
                    status_d = []
                    smh_cond = (ms['smh'] > ms['smh_ma50']) and (ms['smh_3m_ret'] > 0.05) and (ms['smh_rsi'] > 50)
                    
                    def get_w_local(reg, usx):
                        w = {t: 0.0 for t in REQUIRED_TICKERS}; semi = 'SOXL' if usx else 'USD'
                        if reg == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'], w['SPY'] = 0.30, 0.20, 0.20, 0.15, 0.10, 0.05
                        elif reg == 2: w['QLD'], w['SSO'], w['GLD'], w['USD'], w['QQQ'], w['SPY'] = 0.30, 0.25, 0.25, 0.10, 0.05, 0.05
                        elif reg == 3: w['GLD'], w['QQQ'] = 0.50, 0.15
                        elif reg == 4: w['GLD'], w['QQQ'] = 0.50, 0.10
                        total_w = sum(w.values())
                        if total_w < 1.0: w['CASH'] = round(1.0 - total_w, 4)
                        return {k: v for k, v in w.items() if v > 0}
                        
                    target_w_dict = get_w_local(ms['regime'], smh_cond)
                    
                    target_seed = st.number_input("운용 시드 설정 ($)", value=float(curr_acc_data.get("target_seed", 10000.0)), step=1000.0, key=f"seed_{acc_name}")
                    if target_seed != curr_acc_data.get("target_seed"):
                        st.session_state['accounts'][acc_name]["target_seed"] = target_seed
                        save_accounts_data(st.session_state['accounts'])

                    all_tkrs = set([t for t in asset_vals.keys()] + list(target_w_dict.keys()))
                    for tkr in all_tkrs:
                        tkr = tkr.upper()
                        my_v = asset_vals.get(tkr, 0.0); my_w = (my_v / total_val_now * 100) if total_val_now > 0 else 0.0
                        tw = target_w_dict.get(tkr, 0.0)
                        
                        tv = target_seed * tw
                        diff = tv - my_v
                        cp = live_prices.get(tkr, 0.0)
                        
                        if tkr != "CASH" and cp > 0:
                            shares_to_trade = abs(diff) / cp
                            action_suffix = f" (약 {shares_to_trade:.1f}주)"
                            if shares_to_trade <= 1.5: action = "유지 (적정)"
                            elif diff > 0: action = f"매수 ${diff:,.0f}{action_suffix}"
                            else: action = f"매도 ${abs(diff):,.0f}{action_suffix}"
                        elif tkr == "CASH":
                            if abs(diff) < 50: action = "유지 (적정)"
                            elif diff > 0: action = f"추가 ${diff:,.0f}"
                            else: action = f"인출 ${abs(diff):,.0f}"
                        else: action = "유지 (적정)"
                        
                        if my_v > 0 or tw > 0: 
                            status_d.append({"종목": tkr, "목표비중": f"{tw*100:.1f}%", "현재비중": f"{my_w:.1f}%", "목표액": f"${tv:,.0f}", "현재액": f"${my_v:,.0f}", "리밸런싱 액션": action})
                            
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
                            if '매수' in val_s or '추가' in val_s: return f'color: {C_UP}; font-weight:bold;'
                            elif '매도' in val_s or '인출' in val_s: return f'color: {C_DOWN}; font-weight:bold;'
                            elif '적정' in val_s: return f'color: {TEXT_SUB};'
                            return ''
                        st.dataframe(status_df.style.map(color_act, subset=['리밸런싱 액션']), use_container_width=True, hide_index=True)
                st.write("")

            elif block == "🧩 자산 상관관계 히트맵":
                st.markdown("#### 🧩 자산 상관관계 분석 (Correlation Matrix)")
                st.caption("거물의 시선: 지난 1년간 내 포트폴리오 종목들이 얼마나 똑같이 움직였을까? 1.0에 가까우면 동조화, 음수면 훌륭한 헷징 수단이라네.")
                with st.container(border=True):
                    active_tkrs = [t for t in asset_vals.keys() if t != "CASH"]
                    if len(active_tkrs) > 1:
                        try:
                            corr_data = yf.download(active_tkrs, period="1y", progress=False)['Close']
                            corr_matrix = corr_data.pct_change().corr().round(2)
                            fig_corr = go.Figure(data=go.Heatmap(
                                z=corr_matrix.values, x=corr_matrix.columns, y=corr_matrix.index,
                                text=corr_matrix.values, texttemplate="%{text}",
                                colorscale="RdYlGn", zmin=-1, zmax=1
                            ))
                            cust_corr = THEME_LAYOUT.copy(); cust_corr.update(height=400, margin=dict(l=10, r=10, t=10, b=10))
                            fig_corr.update_layout(**cust_corr)
                            st.plotly_chart(fig_corr, use_container_width=True)
                        except Exception as e:
                            st.info("상관관계 데이터를 불러오기에 종목 수가 부족하거나 일시적인 네트워크 오류입니다.")
                    else:
                        st.info("히트맵을 분석하려면 주식 종목이 2개 이상 필요합니다.")
                st.write("")

            elif block == "🔮 10년 은퇴 시뮬레이션":
                st.markdown("#### 🔮 10년 은퇴 몬테카를로 시뮬레이션")
                st.caption("거물의 시선: 과거의 평균 수익률과 변동성을 바탕으로, 자네가 10년 뒤 얼마나 큰 부를 이룰 수 있을지 확률론적으로 그려봤네.")
                with st.container(border=True):
                    if total_val_now > 1000 and sum(weights_dict.values()) > 0:
                        try:
                            sim_tkrs = [t for t in weights_dict.keys() if t != "CASH"]
                            sim_data = yf.download(sim_tkrs, period="5y", progress=False)['Close'].pct_change().dropna()
                            port_ret = sum(sim_data[t].mean() * weights_dict[t] for t in sim_tkrs if t in sim_data.columns) * 252
                            port_vol = np.sqrt(sum((sim_data[t].std() * np.sqrt(252))**2 * (weights_dict[t]**2) for t in sim_tkrs if t in sim_data.columns))
                            
                            years = 10; days = years * 252
                            np.random.seed(42) 
                            dt = 1/252
                            drift = (port_ret - 0.5 * port_vol**2) * dt
                            vol = port_vol * np.sqrt(dt)
                            paths = np.zeros((days, 3)); paths[0] = total_val_now
                            
                            z_scores = [1.28, 0, -1.28] 
                            for t in range(1, days):
                                for j in range(3):
                                    paths[t][j] = paths[t-1][j] * np.exp(drift + vol * z_scores[j])

                            x_dates = [datetime.today() + timedelta(days=i) for i in range(days)]
                            fig_mc = go.Figure()
                            fig_mc.add_trace(go.Scatter(x=x_dates, y=paths[:, 0], name="낙관적 (상위 10%)", line=dict(color=C_UP, width=1, dash='dash')))
                            fig_mc.add_trace(go.Scatter(x=x_dates, y=paths[:, 1], name="기대 평균", line=dict(color=C_SAFE, width=3)))
                            fig_mc.add_trace(go.Scatter(x=x_dates, y=paths[:, 2], name="비관적 (하위 10%)", line=dict(color=C_DOWN, width=1, dash='dash')))
                            
                            cust_mc = THEME_LAYOUT.copy()
                            cust_mc.update(height=400, hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                            fig_mc.update_layout(**cust_mc)
                            st.plotly_chart(fig_mc, use_container_width=True)
                            st.success(f"**분석 결과:** 10년 후 당신의 자산은 평균적으로 **${paths[-1][1]:,.0f}** 에 도달할 것으로 기대됩니다. (연평균 기대 수익률 {port_ret*100:.1f}%, 변동성 {port_vol*100:.1f}% 가정)")
                        except Exception as e:
                            st.info("데이터가 부족하여 시뮬레이션을 실행할 수 없습니다.")
                    else:
                        st.info("시뮬레이션을 돌리기엔 자금이 너무 적거나 포트폴리오가 비어있습니다.")
                st.write("")

            elif block == "📈 목표 달성률 추이":
                st.markdown("#### 📈 목표 달성률 추이")
                hist_dict = curr_acc_data.get("seed_history", {})
                target_val = curr_acc_data.get("target_portfolio_value", 100000.0)
                
                if hist_dict and target_val > 0:
                    with st.container(border=True):
                        hist_df = pd.DataFrame.from_dict(hist_dict, orient='index')
                        hist_df.index = pd.to_datetime(hist_df.index)
                        hist_df = hist_df.sort_index()

                        hist_df['achieve_pct'] = (hist_df['equity'] / target_val) * 100

                        fig_achieve = go.Figure()
                        fig_achieve.add_trace(go.Scatter(
                            x=hist_df.index, y=hist_df['achieve_pct'], 
                            name="달성률", mode='lines+markers',
                            line=dict(color=C_UP, width=3), 
                            marker=dict(size=6),
                            fill='tozeroy', fillcolor='rgba(0,0,0,0)'
                        ))
                        fig_achieve.add_hline(y=100, line_dash="dash", line_color=C_DOWN, annotation_text="목표 달성 (100%)", annotation_position="top left")
                        
                        cust_s = THEME_LAYOUT.copy()
                        cust_s.update(height=350, hovermode="x unified", yaxis=dict(showgrid=True, ticksuffix="%"))
                        fig_achieve.update_layout(**cust_s)
                        st.plotly_chart(fig_achieve, use_container_width=True)
                        st.caption("💡 접속 시 자동으로 해당 날짜의 총 평가액을 기록하여 목표 금액 대비 달성률(%) 궤적을 추적합니다.")
                else:
                    st.info("아직 충분한 자산 기록이 없거나 목표 금액이 설정되지 않았습니다.")
                st.write("")

            elif block == "📈 성장 곡선":
                st.markdown("**📈 자산 성장 곡선**")
                hist_dict = curr_acc_data.get("seed_history", {})
                if hist_dict:
                    with st.container(border=True):
                        hist_df = pd.DataFrame.from_dict(hist_dict, orient='index')
                        hist_df.index = pd.to_datetime(hist_df.index)
                        hist_df = hist_df.sort_index()

                        fed_str = curr_acc_data.get("first_entry_date")
                        col_date, _ = st.columns([1, 3])
                        with col_date:
                            default_date = pd.to_datetime(fed_str).date() if fed_str else (datetime.today() - timedelta(days=90)).date()
                            u_date = st.date_input("기준일 설정", value=default_date, key=f"date_{acc_name}")
                            if str(u_date) != str(fed_str)[:10]: 
                                st.session_state['accounts'][acc_name]["first_entry_date"] = str(u_date)
                                save_accounts_data(st.session_state['accounts'])
                        
                        try:
                            if fed_str:
                                fed_dt = pd.to_datetime(fed_str)
                                if fed_dt < hist_df.index[0]:
                                    hist_df.loc[fed_dt] = {"seed": auto_seed, "equity": auto_seed}
                                    hist_df = hist_df.sort_index()

                            hist_df = hist_df.resample('D').ffill()

                            fig_seed = go.Figure()
                            fig_seed.add_trace(go.Scatter(x=hist_df.index, y=hist_df['equity'], name="실제 총 평가액", line=dict(color=C_UP, width=3, shape='hv'), mode='lines'))
                            fig_seed.add_trace(go.Scatter(x=hist_df.index, y=hist_df['seed'], name="투입 시드 원금", line=dict(color=C_DOWN, width=2, dash='dot', shape='hv'), mode='lines'))
                            
                            cust_s = THEME_LAYOUT.copy()
                            cust_s.update(height=350, hovermode="x unified", yaxis=dict(showgrid=True, autorange=True, rangemode="normal"))
                            fig_seed.update_layout(**cust_s)
                            st.plotly_chart(fig_seed, use_container_width=True)
                        except Exception as e: pass
                st.write("")

            elif block == "📝 매매 일지":
                col_log1, col_log2 = st.columns([1.5, 1])
                with col_log1:
                    st.markdown("**📝 매매 일지**")
                    def save_j(): st.session_state['accounts'][acc_name]["journal_text"] = st.session_state[f"j_{acc_name}"]; save_accounts_data(st.session_state['accounts'])
                    st.text_area("LOG...", value=curr_acc_data.get('journal_text', ''), key=f"j_{acc_name}", height=300, on_change=save_j, label_visibility="collapsed")
                with col_log2:
                    st.markdown("**🔔 시스템 로그**")
                    history = curr_acc_data.get('history', [])
                    if history: st.dataframe(pd.DataFrame(history)[::-1], hide_index=True, use_container_width=True, height=300)
                st.write("")

    page_func.__name__ = f"pf_{abs(hash(acc_name))}"
    return page_func


# --- 페이지 구성: 계좌 관리 ---
def page_manage_accounts():
    st.title("⚙️ 계좌 관리")
    new_acc = st.text_input("새 계좌명")
    if st.button("개설", type="primary") and new_acc:
        if new_acc not in st.session_state['accounts']:
            st.session_state['accounts'][new_acc] = {"portfolio": [{"티커 (Ticker)": t, "수량 (주/달러)": 0.0, "평균 단가 ($)": 0.0, "매입 환율": 0.0, "태그": "코어"} for t in REQUIRED_TICKERS], "history": [{"Date": datetime.now().strftime("%Y-%m-%d"), "Log": "계좌 개설"}], "target_seed": 10000.0, "seed_history": {}, "target_portfolio_value": 100000.0, "layout_order": ["🎯 목표 달성률", "📊 실시간 요약", "⚡ 시스템 분석관", "🚀 실전 퀀트 무기", "💼 포트폴리오 & 리밸런싱", "🧩 자산 상관관계 히트맵", "🔮 10년 은퇴 시뮬레이션", "📈 성장 곡선", "📈 목표 달성률 추이", "📝 매매 일지"]}
            save_accounts_data(st.session_state['accounts']); st.rerun()
    st.divider()
    for acc in list(st.session_state['accounts'].keys()):
        c1, c2 = st.columns([4, 1])
        c1.write(f"📁 **{acc}**")
        if c2.button("삭제", key=f"del_{acc}", disabled=len(st.session_state['accounts']) <=1):
            del st.session_state['accounts'][acc]; save_accounts_data(st.session_state['accounts']); st.rerun()

# --- 페이지 구성: 전략 명세서 ---
def page_strategy_specification():
    st.title("📜 전략 명세서")
    st.markdown("### 🏷️ 버전: v4.4 (최신 안정화 버전)")
    st.table(pd.DataFrame({"우선순위": ["1", "2", "3", "4"], "조건": ["VIX > 40", "QQQ < 200일선", "정배열 & VIX < 25", "그 외 조건"], "레짐": ["R4 (위기)", "R3 (약세)", "R1 (강세)", "R2 (보통)"]}))


# =====================================================================
# [7] 사이드바 설정 및 네비게이션
# =====================================================================

st.sidebar.markdown("---")

st.sidebar.markdown(f"<div style='font-size:1.1rem; font-weight:700; color:{TEXT_COLOR}; margin-bottom:10px;'>⭐ 즐겨찾기</div>", unsafe_allow_html=True)
st.sidebar.markdown(f"""<div style="display:flex; flex-direction:column; gap:2px;">
<div style="font-size:0.8rem; font-weight:bold; margin-top:5px; color:{TEXT_SUB};">유튜브</div>
<a href="https://www.youtube.com/@JB_Insight" target="_blank" class="sidebar-link"><span>📊</span> JB 인사이트</a>
<a href="https://www.youtube.com/@odokgod" target="_blank" class="sidebar-link"><span>📻</span> 오독</a>
<a href="https://www.youtube.com/@TQQQCRAZY" target="_blank" class="sidebar-link"><span>🔥</span> TQQQ 미친놈</a>
<a href="https://www.youtube.com/@developmong" target="_blank" class="sidebar-link"><span>🐒</span> 디벨롭몽</a>
<div style="font-size:0.8rem; font-weight:bold; margin-top:15px; color:{TEXT_SUB};">차트 분석</div>
<a href="https://kr.investing.com/" target="_blank" class="sidebar-link"><span>🌍</span> 인베스팅닷컴</a>
<a href="https://kr.tradingview.com/" target="_blank" class="sidebar-link"><span>📉</span> 트레이딩뷰</a>
<div style="font-size:0.8rem; font-weight:bold; margin-top:15px; color:{TEXT_SUB};">AI 도우미</div>
<a href="https://claude.ai/" target="_blank" class="sidebar-link"><span>🧠</span> 클로드</a>
<a href="https://gemini.google.com/" target="_blank" class="sidebar-link"><span>✨</span> 제미나이</a>
</div>""", unsafe_allow_html=True)
st.sidebar.markdown("---")

with st.sidebar.expander("💾 백업 및 복구"):
    st.download_button("📥 백업 다운로드", data=json.dumps(st.session_state['accounts']), file_name="amls_backup.json")
    up_f = st.file_uploader("📤 복구 업로드", type=['json'])
    if up_f and st.button("⚠️ 복구 실행"):
        st.session_state['accounts'] = json.load(up_f)
        save_accounts_data(st.session_state['accounts'])
        st.rerun()

pages = {
    "시스템": [st.Page(page_market_dashboard, title="마켓 터미널", icon="🌐"), st.Page(page_amls_backtest, title="백테스트 엔진", icon="🦅")],
    "포트폴리오": [],
    "설정": [st.Page(page_strategy_specification, title="전략 명세서", icon="📜"), st.Page(page_manage_accounts, title="계좌 관리", icon="⚙️")]
}

for name in st.session_state['accounts'].keys():
    pages["포트폴리오"].append(st.Page(make_portfolio_page(name), title=name, icon="💼"))

pg = st.navigation(pages)
pg.run()
