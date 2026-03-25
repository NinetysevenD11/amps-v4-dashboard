import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import warnings
import json
import os

warnings.filterwarnings('ignore')

# ==========================================
# 1. 설정 및 데이터
# ==========================================
st.set_page_config(page_title="AMLS V4.5 FINANCE STRATEGY", layout="wide", page_icon="🌿", initial_sidebar_state="expanded")

# --- 🎨 테마 커스텀 시스템 ---
if 'main_color'   not in st.session_state: st.session_state.main_color   = '#10B981'
if 'bg_color'     not in st.session_state: st.session_state.bg_color     = '#F7F6F2'
if 'tc_heading'   not in st.session_state: st.session_state.tc_heading   = '#111118'
if 'tc_body'      not in st.session_state: st.session_state.tc_body      = '#2D2D2D'
if 'tc_muted'     not in st.session_state: st.session_state.tc_muted     = '#6B6B7A'
if 'tc_label'     not in st.session_state: st.session_state.tc_label     = '#9494A0'
if 'tc_data'      not in st.session_state: st.session_state.tc_data      = '#111118'
if 'tc_sidebar'   not in st.session_state: st.session_state.tc_sidebar   = '#2D2D2D'

main_color = st.session_state.main_color
bg_color   = st.session_state.bg_color
tc_heading = st.session_state.tc_heading
tc_body    = st.session_state.tc_body
tc_muted   = st.session_state.tc_muted
tc_label   = st.session_state.tc_label
tc_data    = st.session_state.tc_data
tc_sidebar = st.session_state.tc_sidebar

def hex_to_rgb(hex_col):
    h = hex_col.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
r_c, g_c, b_c = hex_to_rgb(main_color)

def apply_theme(text):
    if not isinstance(text, str): return text
    text = text.replace("#10B981", main_color)
    text = text.replace("#10b981", main_color)
    text = text.replace("16, 185, 129", f"{r_c}, {g_c}, {b_c}")
    text = text.replace("16,185,129", f"{r_c},{g_c},{b_c}")
    return text

SECTOR_TICKERS = ['XLK','XLV','XLF','XLY','XLC','XLI','XLP','XLE','XLU','XLRE','XLB']
CORE_TICKERS   = ['QQQ','TQQQ','SOXL','USD','QLD','SSO','SPY','SMH','GLD','^VIX','HYG','IEF','QQQE','UUP','^TNX','BTC-USD','IWM']
TICKERS        = CORE_TICKERS + SECTOR_TICKERS
ASSET_LIST     = ['TQQQ','SOXL','USD','QLD','SSO','SPY','QQQ','GLD','CASH']

PORTFOLIO_FILE = 'portfolio_autosave.json'

def sanitize_portfolio():
    for a in ASSET_LIST:
        val = st.session_state.portfolio.get(a)
        if isinstance(val, (int, float)) or val is None:
            st.session_state.portfolio[a] = {'shares': float(val or 0.0), 'avg_price': 1.0 if a == 'CASH' else 0.0, 'fx': 1350.0}
        elif isinstance(val, dict):
            if 'shares' not in val: val['shares'] = 0.0
            if 'avg_price' not in val: val['avg_price'] = 1.0 if a == 'CASH' else 0.0
            if 'fx' not in val: val['fx'] = 1350.0
        else:
            st.session_state.portfolio[a] = {'shares': 0.0, 'avg_price': 0.0, 'fx': 1350.0}

if 'goal_usd' not in st.session_state:
    st.session_state.goal_usd = 100000.0

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {asset: {'shares':0.0, 'avg_price':0.0, 'fx':1350.0} for asset in ASSET_LIST}
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                loaded = json.load(f)
                for k, v in loaded.items():
                    st.session_state.portfolio[k] = v
        except: pass

sanitize_portfolio()

def save_portfolio_to_disk():
    try:
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump(st.session_state.portfolio, f)
    except: pass

@st.cache_data(ttl=3600, show_spinner=False)
def load_data():
    end_date   = datetime.now()
    start_date = end_date - timedelta(days=900)
    for attempt in range(3):
        try:
            data = yf.download(TICKERS, start=start_date.strftime("%Y-%m-%d"),
                               end=end_date.strftime("%Y-%m-%d"),
                               progress=False, auto_adjust=True)['Close']
            if data.empty:
                continue
            df = pd.DataFrame(index=data.index)
            for t in TICKERS:
                if t in data.columns: df[t] = data[t]
            df = df.ffill().bfill()
            df['QQQ_MA20']      = df['QQQ'].rolling(20).mean()
            df['QQQ_MA50']      = df['QQQ'].rolling(50).mean()
            df['QQQ_MA200']     = df['QQQ'].rolling(200).mean()
            df['TQQQ_MA200']    = df['TQQQ'].rolling(200).mean()
            df['SMH_MA50']      = df['SMH'].rolling(50).mean()
            df['VIX_MA5']       = df['^VIX'].rolling(5).mean()
            df['VIX_MA20']      = df['^VIX'].rolling(20).mean()
            df['VIX_MA50']      = df['^VIX'].rolling(50).mean()
            df['SMH_3M_Ret']    = df['SMH'].pct_change(63)
            df['SMH_1M_Ret']    = df['SMH'].pct_change(21)
            df['SMH_RSI']       = ta.rsi(df['SMH'], length=14)
            df['HYG_IEF_Ratio'] = df['HYG'] / df['IEF']
            df['HYG_IEF_MA20']  = df['HYG_IEF_Ratio'].rolling(20).mean()
            df['HYG_IEF_MA50']  = df['HYG_IEF_Ratio'].rolling(50).mean()
            df['QQQ_20d_Ret']   = df['QQQ'].pct_change(20)
            df['QQQE_20d_Ret']  = df['QQQE'].pct_change(20)
            df['QQQ_RSI']       = ta.rsi(df['QQQ'], length=14)
            df['GLD_SPY_Ratio'] = df['GLD'] / df['SPY']
            df['GLD_SPY_MA50']  = df['GLD_SPY_Ratio'].rolling(50).mean()
            df['QQQ_High52']    = df['QQQ'].rolling(252).max()
            df['QQQ_DD']        = (df['QQQ'] / df['QQQ_High52']) - 1
            df['UUP_MA50']      = df['UUP'].rolling(50).mean()
            df['TNX_MA50']      = df['^TNX'].rolling(50).mean()
            df['BTC_MA50']      = df['BTC-USD'].rolling(50).mean()
            df['IWM_SPY_Ratio'] = df['IWM'] / df['SPY']
            df['IWM_SPY_MA50']  = df['IWM_SPY_Ratio'].rolling(50).mean()
            for sec in SECTOR_TICKERS: df[f'{sec}_1M'] = df[sec].pct_change(21)
            result = df.dropna()
            if not result.empty:
                return result
        except Exception:
            import time
            time.sleep(1)
    return None

def get_target_v45(row):
    if row['^VIX'] > 40: return 4
    credit_stress = row['HYG_IEF_Ratio'] < row['HYG_IEF_MA20']
    if row['QQQ'] < row['QQQ_MA200']: return 3
    if row['QQQ_DD'] < -0.10 and credit_stress: return 3
    bull_trend = row['QQQ'] >= row['QQQ_MA200'] and row['QQQ_MA50'] >= row['QQQ_MA200']
    low_vix    = row['VIX_MA20'] < 22
    credit_ok  = row['HYG_IEF_Ratio'] >= row['HYG_IEF_MA50']
    if bull_trend and low_vix and credit_ok: return 1
    return 2

def apply_asymmetric_delay(targets):
    res = []; hist_curr = 3; pend = None; cnt = 0
    for t in targets:
        if t > hist_curr: hist_curr = t; pend = None; cnt = 0
        elif t < hist_curr:
            if t == pend:
                cnt += 1
                if cnt >= 5: hist_curr = t; pend = None; cnt = 0
            else: pend = t; cnt = 1
        else: pend = None; cnt = 0
        res.append(hist_curr)
    return pd.Series(res, index=targets.index).shift(1).bfill()

@st.cache_data(ttl=3600)
def load_custom_backtest_data(start_date, end_date):
    fetch_start = pd.to_datetime(start_date) - timedelta(days=400)
    f_start_str = fetch_start.strftime("%Y-%m-%d")
    f_end_str = (pd.to_datetime(end_date) + timedelta(days=1)).strftime("%Y-%m-%d")
    data = yf.download(TICKERS, start=f_start_str, end=f_end_str, progress=False, auto_adjust=True)['Close']
    bt_df = pd.DataFrame(index=data.index)
    for t in TICKERS: bt_df[t] = data[t]
    bt_df = bt_df.ffill().bfill()
    bt_df['QQQ_MA20']      = bt_df['QQQ'].rolling(20).mean()
    bt_df['QQQ_MA50']      = bt_df['QQQ'].rolling(50).mean()
    bt_df['QQQ_MA200']     = bt_df['QQQ'].rolling(200).mean()
    bt_df['TQQQ_MA200']    = bt_df['TQQQ'].rolling(200).mean()
    bt_df['SMH_MA50']      = bt_df['SMH'].rolling(50).mean()
    bt_df['VIX_MA5']       = bt_df['^VIX'].rolling(5).mean()
    bt_df['VIX_MA20']      = bt_df['^VIX'].rolling(20).mean()
    bt_df['VIX_MA50']      = bt_df['^VIX'].rolling(50).mean()
    bt_df['SMH_3M_Ret']    = bt_df['SMH'].pct_change(63)
    bt_df['SMH_1M_Ret']    = bt_df['SMH'].pct_change(21)
    bt_df['SMH_RSI']       = ta.rsi(bt_df['SMH'], length=14)
    bt_df['HYG_IEF_Ratio'] = bt_df['HYG'] / bt_df['IEF']
    bt_df['HYG_IEF_MA20']  = bt_df['HYG_IEF_Ratio'].rolling(20).mean()
    bt_df['HYG_IEF_MA50']  = bt_df['HYG_IEF_Ratio'].rolling(50).mean()
    bt_df['QQQ_20d_Ret']   = bt_df['QQQ'].pct_change(20)
    bt_df['QQQE_20d_Ret']  = bt_df['QQQE'].pct_change(20)
    bt_df['QQQ_RSI']       = ta.rsi(bt_df['QQQ'], length=14)
    bt_df['GLD_SPY_Ratio'] = bt_df['GLD'] / bt_df['SPY']
    bt_df['GLD_SPY_MA50']  = bt_df['GLD_SPY_Ratio'].rolling(50).mean()
    bt_df['QQQ_High52']    = bt_df['QQQ'].rolling(252).max()
    bt_df['QQQ_DD']        = (bt_df['QQQ'] / bt_df['QQQ_High52']) - 1
    bt_df['UUP_MA50']      = bt_df['UUP'].rolling(50).mean()
    bt_df['TNX_MA50']      = bt_df['^TNX'].rolling(50).mean()
    bt_df['BTC_MA50']      = bt_df['BTC-USD'].rolling(50).mean()
    bt_df['IWM_SPY_Ratio'] = bt_df['IWM'] / bt_df['SPY']
    bt_df['IWM_SPY_MA50']  = bt_df['IWM_SPY_Ratio'].rolling(50).mean()
    bt_df = bt_df.dropna()
    if bt_df.empty: return bt_df
    bt_df['Target'] = bt_df.apply(get_target_v45, axis=1)
    bt_df['Regime'] = apply_asymmetric_delay(bt_df['Target'])
    bt_df = bt_df.loc[pd.to_datetime(start_date):pd.to_datetime(end_date)]
    return bt_df

REALTIME_TICKERS = ['QQQ','TQQQ','SMH','^VIX','HYG','IEF','UUP','GLD','SPY','SOXL','USD','QLD','SSO','USDKRW=X', '^TNX', 'BTC-USD', 'IWM']

@st.cache_data(ttl=60)
def fetch_realtime_prices():
    prices = {}
    for ticker in REALTIME_TICKERS:
        try:
            info  = yf.Ticker(ticker).fast_info
            price = info.get('last_price') or info.get('lastPrice')
            if price and price > 0: prices[ticker] = float(price)
        except: pass
    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc + timedelta(hours=9)
    fetch_time = now_kst.strftime("%Y-%m-%d %H:%M:%S")
    return prices, fetch_time

@st.cache_data(ttl=1800)
def fetch_fear_and_greed():
    try:
        url = "https://production.api.cnn.io/data/ext/fear_and_greed/latest"
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        req = urllib.request.Request(url, headers=headers)
        res = urllib.request.urlopen(req, timeout=5)
        data = json.loads(res.read().decode('utf-8'))
        return float(data['fear_and_greed']['score'])
    except: return None

@st.cache_data(ttl=900)
def fetch_macro_news():
    headlines_for_ai, news_items = [], []
    try:
        search_query = urllib.parse.quote("미국증시 OR 연준 OR 나스닥 OR 금리")
        url  = f"https://news.google.com/rss/search?q={search_query}&hl=ko&gl=KR&ceid=KR:ko"
        req  = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        root = ET.fromstring(urllib.request.urlopen(req).read())
        for item in root.findall('.//item')[:12]:
            t, l, d = item.find('title').text, item.find('link').text, item.find('pubDate').text
            headlines_for_ai.append(t); news_items.append({"title":t,"link":l,"date":d[:-4]})
    except: pass
    return headlines_for_ai, news_items

@st.cache_data(ttl=300)
def fetch_global_markets():
    global_tickers = {
        'SPY':'S&P 500','QQQ':'Nasdaq 100','DIA':'Dow Jones','IWM':'Russell 2000',
        'EWJ':'Japan','EWT':'Taiwan','EWY':'Korea','FXI':'China','EWH':'HongKong',
        'VGK':'Europe','EWG':'Germany','EWU':'UK','EWQ':'France','EWC':'Canada',
        'EEM':'Emg Mkt','EWZ':'Brazil','EWA':'Australia',
    }
    asset_tickers = {
        '^TNX':'US 10Y','GLD':'Gold','SLV':'Silver','USO':'Oil',
        'BTC-USD':'Bitcoin','ETH-USD':'Ethereum','UUP':'DXY',
    }
    leader_tickers = {
        'AAPL':'Apple','MSFT':'Microsoft','NVDA':'Nvidia','AMZN':'Amazon',
        'GOOGL':'Alphabet','META':'Meta','TSLA':'Tesla',
        'AVGO':'Broadcom','AMD':'AMD','TSM':'TSMC',
    }
    all_t = list(global_tickers.keys()) + list(asset_tickers.keys()) + list(leader_tickers.keys())
    results = {}
    try:
        end = datetime.now()
        start = end - timedelta(days=5)
        raw = yf.download(all_t, start=start.strftime('%Y-%m-%d'),
                          end=end.strftime('%Y-%m-%d'), progress=False, auto_adjust=True)['Close']
        for t in all_t:
            if t in raw.columns:
                s = raw[t].dropna()
                if len(s) >= 2:
                    chg = (s.iloc[-1] / s.iloc[-2] - 1) * 100
                    results[t] = {'price': float(s.iloc[-1]), 'chg': float(chg)}
                elif len(s) == 1:
                    results[t] = {'price': float(s.iloc[-1]), 'chg': 0.0}
    except: pass
    return results, global_tickers, asset_tickers, leader_tickers

with st.spinner('시장 데이터 수집 중...'):
    df = load_data()
    if df is not None and not df.empty:
        st.session_state['_df_cache'] = df
    elif '_df_cache' in st.session_state:
        df = st.session_state['_df_cache']
    rt_prices, last_update_time = fetch_realtime_prices()

if df is None or df.empty:
    st.markdown("""
    <div style="background:#FEF2F2;border:1px solid #FCA5A5;border-left:4px solid #DC2626;
        padding:20px 24px;margin:20px 0;font-family:'Plus Jakarta Sans',sans-serif;">
        <div style="font-size:1.1em;font-weight:700;color:#DC2626;margin-bottom:6px;">
            📡 야후 파이낸스(Yahoo Finance) 연결 실패
        </div>
        <div style="font-size:0.9em;color:#7F1D1D;line-height:1.6;">
            Streamlit Cloud에서 야후 파이낸스 서버에 일시적으로 연결하지 못했습니다.<br>
            보통 30초~2분 내에 자동 복구됩니다.
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("🔄  다시 시도", type="primary", use_container_width=False):
        st.cache_data.clear()
        st.rerun()
    st.stop()

last_index = df.index[-1]
rt_injected = []
for ticker, price in rt_prices.items():
    if ticker in df.columns and price > 0:
        df.at[last_index, ticker] = price
        rt_injected.append(ticker)

if 'QQQ' in rt_injected:
    df.at[last_index, 'QQQ_DD'] = (df.at[last_index, 'QQQ'] / df['QQQ_High52'].iloc[-1]) - 1
if 'HYG' in rt_injected and 'IEF' in rt_injected:
    df.at[last_index, 'HYG_IEF_Ratio'] = df.at[last_index, 'HYG'] / df.at[last_index, 'IEF']
if 'IWM' in rt_injected and 'SPY' in rt_injected:
    df.at[last_index, 'IWM_SPY_Ratio'] = df.at[last_index, 'IWM'] / df.at[last_index, 'SPY']

last_row = df.iloc[-1].copy()

rt_ok    = len(rt_injected) >= 3
rt_label = f"⬤ LIVE  {len(rt_injected)} feeds" if rt_ok else "⬤ DELAYED"

vix_close, vix_ma5, vix_ma20 = last_row['^VIX'], last_row['VIX_MA5'], last_row['VIX_MA20']
qqq_close, qqq_ma50, qqq_ma200 = last_row['QQQ'], last_row['QQQ_MA50'], last_row['QQQ_MA200']
smh_close, smh_ma50, smh_3m, smh_1m, smh_rsi = (last_row['SMH'], last_row['SMH_MA50'],
    last_row['SMH_3M_Ret'], last_row['SMH_1M_Ret'], last_row['SMH_RSI'])

df['Target'] = df.apply(get_target_v45, axis=1)
df['Regime'] = apply_asymmetric_delay(df['Target'])

live_regime   = get_target_v45(last_row)
hist_regime   = int(df.iloc[-2]['Regime'])
curr_regime   = live_regime if live_regime > hist_regime else hist_regime
target_regime = live_regime

smh_c1 = smh_close > smh_ma50
smh_c2 = (smh_3m > 0.05 or smh_1m > 0.10)
smh_c3 = smh_rsi > 50
smh_cond = smh_c1 and smh_c2 and smh_c3

def get_weights_v45(reg, smh_ok):
    w = {t: 0.0 for t in ASSET_LIST}
    semi = 'SOXL' if smh_ok else 'USD'
    if reg == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'], w['SPY'] = 0.30, 0.20, 0.20, 0.15, 0.10, 0.05
    elif reg == 2: w['TQQQ'], w['QLD'], w['SSO'], w['USD'], w['GLD'], w['SPY'] = 0.15, 0.30, 0.25, 0.10, 0.15, 0.05
    elif reg == 3: w['GLD'], w['CASH'], w['QQQ'] = 0.50, 0.35, 0.15
    elif reg == 4: w['GLD'], w['CASH'], w['QQQ'] = 0.50, 0.40, 0.10
    return w
target_weights = get_weights_v45(curr_regime, smh_cond)

if curr_regime == live_regime: regime_committee_msg = "🟢 조건 부합 (안정)"
elif live_regime > curr_regime: regime_committee_msg = f"🔴 R{live_regime} 하향 즉시 반영"
else: regime_committee_msg = f"🟡 R{live_regime} 승급 대기 (5일)"

# ==========================================
# 2. 라이트 테마 색상 변수 (차트용)
# ==========================================
b_color   = 'rgba(0,0,0,0)'
t_color   = '#4A4A57'
line_c    = main_color
dash_c    = '#B0B0BE'
rsi_low_c = main_color

chart_layout = dict(
    paper_bgcolor=b_color,
    plot_bgcolor=b_color,
    font=dict(family="DM Mono, DM Sans, monospace", color=t_color),
    margin=dict(l=0, r=0, t=40, b=0),
)
radar_layout = dict(
    height=200,
    margin=dict(l=10, r=10, t=15, b=15),
    paper_bgcolor=b_color,
    plot_bgcolor=b_color,
    font=dict(family="DM Mono, DM Sans, monospace", color=t_color),
)

_ax = dict(gridcolor='rgba(0,0,0,0.07)', linecolor='rgba(0,0,0,0.12)', showgrid=True, zeroline=False)
_ax_r = dict(gridcolor='rgba(0,0,0,0.07)', zeroline=False, showgrid=True)

regime_info = {1:("R1  BULL","풀 가동"),2:("R2  CORR","방어 진입"), 3:("R3  BEAR","대피"),4:("R4  PANIC","최대 방어")}

# ==========================================
# 3. CSS
# ==========================================
css_block = f"""<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&display=swap');

    :root {{
        --paper:      {bg_color};
        --paper-2:    {bg_color}dd;
        --paper-3:    {bg_color}bb;
        --ink:        {tc_heading};
        --ink-2:      {tc_body};
        --ink-3:      {tc_body};
        --ink-4:      {tc_muted};
        --ink-5:      {tc_label};
        --rule:       rgba(0,0,0,0.10);
        --rule-strong:rgba(0,0,0,0.18);
        --acc:        #10B981;
        --acc-pale:   rgba(16,185,129,0.08);
        --acc-mid:    rgba(16,185,129,0.18);
        --acc-line:   rgba(16,185,129,0.40);
        --bull:       #059669;
        --bear:       #DC2626;
        --warn:       #D97706;
        --u:          8px;
    }}

    *, *::before, *::after {{ box-sizing: border-box; }}

    .stApp, [data-testid="stAppViewContainer"] {{
        background-color: {bg_color} !important;
        background-image:
            radial-gradient(circle, rgba(0,0,0,0.055) 1px, transparent 1px),
            radial-gradient(ellipse 70% 40% at 5% 0%, rgba(16,185,129,0.055) 0%, transparent 55%) !important;
        background-size: 24px 24px, 100% 100% !important;
        color: {tc_body} !important;
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 14px;
    }}

    [data-testid="stHeader"] {{
        background: rgba(247,246,242,0.92) !important;
        backdrop-filter: blur(12px);
        border-bottom: 1px solid var(--rule-strong);
    }}
    #MainMenu {{ visibility:hidden; }} footer {{ visibility:hidden; }}
    .main .block-container {{
        max-width: 1540px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }}

    [data-testid="stSidebar"] {{
        background: var(--paper-2) !important;
        border-right: 1px solid var(--rule-strong) !important;
        box-shadow: none !important;
    }}
    [data-testid="stSidebar"]::after {{
        content:'';
        position:absolute; top:15%; right:0; width:2px; height:70%;
        background:linear-gradient(180deg, transparent, var(--acc-line), transparent);
        pointer-events:none;
    }}

    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-baseweb="radio"] > div:first-child {{ display:none !important; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {{
        gap:0px !important; padding:0 !important; background:transparent !important;
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-baseweb="radio"] {{
        display:flex !important; align-items:center !important;
        padding:10px 20px !important; margin:0 !important;
        border-radius:0 !important;
        border:none !important;
        border-bottom:1px solid var(--rule) !important;
        background:transparent !important;
        cursor:pointer !important; width:100% !important;
        transition:background 0.15s ease !important;
        position:relative;
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-baseweb="radio"] p {{
        color:var(--ink-3) !important; font-weight:500 !important;
        font-size:0.82rem !important; margin:0 !important;
        font-family:'DM Sans' !important; letter-spacing:0.01em !important;
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-baseweb="radio"]:hover {{
        background:var(--paper-3) !important;
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) {{
        background:var(--paper) !important;
        border-bottom:1px solid var(--rule) !important;
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked)::before {{
        content:'';
        position:absolute; left:0; top:0; bottom:0; width:3px;
        background:var(--acc);
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) p {{
        color:var(--ink) !important; font-weight:700 !important;
    }}

    .sidebar-link {{
        display:flex; align-items:center; gap:10px;
        padding:10px 20px; margin:0;
        border-bottom:1px solid var(--rule);
        text-decoration:none !important;
        color:var(--ink-3) !important;
        font-weight:500; font-size:0.82rem;
        transition:background 0.15s; background:transparent;
        font-family:'DM Sans';
        position:relative;
    }}
    .sidebar-link:hover {{
        background:var(--paper-3) !important;
        color:var(--ink) !important;
    }}

    .glass-card {{
        background: #FAFAF7 !important;
        border: 1px solid var(--rule-strong) !important;
        border-top: 2px solid var(--ink-2) !important;
        border-radius: 0 !important;
        padding: 20px 22px !important;
        box-shadow: none !important;
        height: 100%; display:flex; flex-direction:column;
        justify-content:space-between;
        transition: border-top-color 0.2s ease;
        position:relative;
    }}
    .glass-card:hover {{
        border-top-color: var(--acc) !important;
        transform: none !important;
        box-shadow: 0 4px 24px rgba(0,0,0,0.06) !important;
    }}
    .glass-card h3 {{
        font-family: 'DM Mono', monospace !important;
        font-size: 0.6em !important; font-weight: 400 !important;
        color: var(--ink-4) !important;
        margin-bottom: 14px !important;
        letter-spacing: 0.20em; text-transform: uppercase;
        border-bottom: 1px solid var(--rule); padding-bottom: 9px;
    }}

    .glass-inset {{
        background: var(--paper-2) !important;
        border: 1px solid var(--rule) !important;
        border-left: 3px solid var(--acc) !important;
        border-radius: 0 !important;
        padding: 14px 16px 12px !important;
        text-align: left; margin-bottom: 14px;
        box-shadow: none !important;
    }}

    div[data-testid="stVerticalBlockBorderWrapper"] > div {{
        background: #FAFAF7 !important;
        border: 1px solid var(--rule-strong) !important;
        border-top: 2px solid var(--ink-2) !important;
        border-radius: 0 !important;
        padding: 20px 22px !important;
        box-shadow: none !important;
        transition: border-top-color 0.2s ease;
        position:relative;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"] > div:hover {{
        border-top-color: var(--acc) !important;
        box-shadow: 0 4px 24px rgba(0,0,0,0.06) !important;
        transform: none !important;
    }}

    [data-testid="stMetric"] {{
        background: #FAFAF7 !important;
        border: 1px solid var(--rule-strong) !important;
        border-top: 2px solid var(--ink-2) !important;
        border-radius: 0 !important;
        padding: 16px 18px !important;
        box-shadow: none !important;
        margin-bottom: 8px;
        transition: border-top-color 0.2s;
        position:relative;
    }}
    [data-testid="stMetric"]:hover {{
        border-top-color: var(--acc) !important;
        transform: none !important;
    }}
    [data-testid="stMetricLabel"] > div > div > p {{
        font-size: 0.65em !important; font-weight: 500; color: var(--ink-4) !important;
        white-space:normal !important; letter-spacing: 0.14em; text-transform:uppercase;
        font-family:'DM Mono', monospace !important;
    }}
    [data-testid="stMetricValue"] > div {{
        font-family:'DM Mono', monospace !important;
        font-size:1.4em !important; font-weight:400;
        color:var(--ink) !important;
        font-variant-numeric: tabular-nums;
    }}
    div[data-testid="stMetricDelta"] > div {{
        font-size:0.8em !important; font-weight:500;
        font-family:'DM Mono', monospace !important;
        font-variant-numeric: tabular-nums;
    }}

    [data-testid="stButton"] > button {{
        background: transparent !important;
        border: 1px solid var(--rule-strong) !important;
        color: var(--ink-2) !important;
        border-radius: 0 !important;
        padding: 7px 16px !important;
        font-weight: 500 !important; font-size: 0.78em !important;
        transition: all 0.15s ease !important;
        font-family:'DM Mono', monospace !important;
        letter-spacing: 0.06em; text-transform: uppercase;
    }}
    [data-testid="stButton"] > button:hover {{
        background: var(--acc-pale) !important;
        border-color: var(--acc-line) !important;
        color: var(--bull) !important;
    }}

    h1 {{
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 2.2em !important; font-weight: 800 !important;
        letter-spacing: -1.5px; margin: 0 !important;
        color: {tc_heading} !important;
    }}
    h2 {{
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        color: {tc_heading} !important; font-weight: 800 !important;
        letter-spacing: -0.5px;
    }}
    h3 {{ font-family: 'Plus Jakarta Sans', sans-serif !important; color: {tc_body} !important; }}
    p  {{ color: {tc_body} !important; line-height: 1.65; }}
    strong {{ color: {tc_heading} !important; }}

    [data-testid="stMetricValue"],
    .cval, .mint-table td {{ font-variant-numeric: tabular-nums; }}

    .crow {{
        display:flex; justify-content:space-between; align-items:center;
        padding: 10px 0;
        border-bottom: 1px solid var(--rule);
        font-size: 0.9em;
    }}
    .crow:last-child {{ border-bottom:none; }}
    .clabel {{
        color: {tc_muted}; font-weight:500;
        font-family:'DM Sans'; font-size:1em;
    }}
    .cval {{
        font-family:'DM Mono', monospace; font-weight:400;
        color:#10B981; font-size:0.9em;
        letter-spacing:0.02em; font-variant-numeric:tabular-nums;
    }}

    [data-testid="stMetricLabel"] > div > div > p {{
        font-size: 0.65em !important; font-weight: 500;
        color: {tc_label} !important;
        white-space:normal !important; letter-spacing: 0.14em; text-transform:uppercase;
        font-family:'DM Mono', monospace !important;
    }}
    [data-testid="stMetricValue"] > div {{
        font-family:'DM Mono', monospace !important;
        font-size:1.4em !important; font-weight:400;
        color:{tc_data} !important;
        font-variant-numeric: tabular-nums;
    }}

    [data-testid="stSidebar"] p      {{ color:{tc_sidebar} !important; }}
    [data-testid="stSidebar"] strong {{ color:{tc_heading}   !important; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-baseweb="radio"] p {{
        color:{tc_sidebar} !important;
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) p {{
        color:{tc_heading} !important; font-weight:700 !important;
    }}

    .radar-link {{ text-decoration:none !important; display:block; }}
    .radar-link-title {{
        font-size:0.62em; font-weight:500; color:{tc_label};
        transition:color 0.15s; font-family:'DM Mono', monospace;
        letter-spacing:0.16em; text-transform:uppercase;
    }}
    .radar-link:hover .radar-link-title {{ color:var(--acc) !important; }}

    .mint-table {{
        width:100%; border-collapse:collapse;
        font-family:'DM Mono', monospace;
    }}
    .mint-table th {{
        padding:8px 12px; font-weight:400; color:var(--ink-4);
        text-align:right; font-size:0.68em;
        letter-spacing:0.16em; text-transform:uppercase;
        border-bottom: 2px solid var(--ink-3);
        background: var(--paper-2);
    }}
    .mint-table td {{
        padding:10px 12px;
        background: #FAFAF7;
        color:var(--ink-2); text-align:right;
        border-bottom: 1px solid var(--rule);
        font-size:0.8em;
        font-variant-numeric:tabular-nums;
        transition:background 0.12s;
    }}
    .mint-table tr:hover td {{ background:var(--acc-pale); }}
    .mint-table td:first-child {{
        border-left:3px solid transparent;
        text-align:left; font-family:'DM Sans';
        font-weight:700; color:var(--bull);
        font-size:0.82em;
    }}
    .mint-table tr:hover td:first-child {{ border-left-color:var(--acc); }}
    .mint-table th:first-child {{ text-align:left; }}

    [data-testid="stNumberInput"] > div > div,
    [data-testid="stTextInput"] > div > div {{
        background:#FAFAF7 !important;
        border:1px solid var(--rule-strong) !important;
        border-radius:0 !important;
        color:var(--ink) !important;
    }}
    [data-testid="stDateInput"] > div > div {{
        background:#FAFAF7 !important;
        border:1px solid var(--rule-strong) !important;
        border-radius:0 !important;
        color:var(--ink) !important;
    }}
    [data-baseweb="select"] > div {{
        background:#FAFAF7 !important;
        border:1px solid var(--rule-strong) !important;
        border-radius:0 !important;
    }}

    [data-testid="stFileUploader"] {{
        background:var(--paper-2) !important;
        border:1px dashed var(--rule-strong) !important;
        border-radius:0 !important;
    }}

    [data-testid="stExpander"] {{
        background:#FAFAF7 !important;
        border:1px solid var(--rule-strong) !important;
        border-radius:0 !important;
    }}

    hr {{ border-color:var(--rule-strong) !important; }}

    ::-webkit-scrollbar {{ width:3px; height:3px; }}
    ::-webkit-scrollbar-track {{ background:var(--paper-2); }}
    ::-webkit-scrollbar-thumb {{ background:var(--ink-5); }}
    ::-webkit-scrollbar-thumb:hover {{ background:var(--ink-3); }}

    @keyframes pulseGlow {{
        0%,100% {{ opacity:1; }}
        50% {{ opacity:0.7; }}
    }}
    @keyframes fadeUp {{
        from {{ opacity:0; transform:translateY(10px); }}
        to   {{ opacity:1; transform:translateY(0); }}
    }}
    .live-pulse {{ animation:pulseGlow 2.8s ease-in-out infinite; }}

    .main .block-container > div > div:nth-child(1) {{ animation:fadeUp 0.35s ease 0.05s both; }}
    .main .block-container > div > div:nth-child(2) {{ animation:fadeUp 0.35s ease 0.10s both; }}
    .main .block-container > div > div:nth-child(3) {{ animation:fadeUp 0.35s ease 0.15s both; }}
    .main .block-container > div > div:nth-child(4) {{ animation:fadeUp 0.35s ease 0.20s both; }}
    .main .block-container > div > div:nth-child(5) {{ animation:fadeUp 0.35s ease 0.25s both; }}

    [data-testid="stDataEditor"] {{
        border:1px solid var(--rule-strong) !important;
        border-radius:0 !important;
    }}

    [data-testid="stDataFrame"] {{
        border:1px solid var(--rule-strong) !important;
        border-radius:0 !important;
    }}

    .mint-table td {{ color:{tc_body} !important; }}
    .mint-table th {{ color:{tc_label} !important; }}

</style>"""

st.markdown(apply_theme(css_block), unsafe_allow_html=True)

# ==========================================
# 4. 사이드바 UI
# ==========================================
sidebar_top = st.sidebar.container()
sidebar_top.markdown(apply_theme(f"""
<div style="padding:20px 20px 14px; border-bottom:1px solid rgba(0,0,0,0.10);">
    <div style="font-family:'DM Mono'; font-size:0.58em; color:#9494A0; letter-spacing:0.22em; text-transform:uppercase; margin-bottom:8px;">Quantitative Engine</div>
    <div style="font-family:'Plus Jakarta Sans',sans-serif; font-size:1.5em; font-weight:800; color:#111118; letter-spacing:-0.5px; letter-spacing:-0.3px; line-height:1.1; margin-bottom:12px;">
        AMLS <span style="color:#10B981;">V4.5</span>
    </div>
    <div class="live-pulse" style="display:inline-flex; align-items:center; gap:5px; font-family:'DM Mono'; font-size:0.65em; color:#059669; padding:4px 10px; background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.25); letter-spacing:0.06em;">
        {rt_label}
    </div>
</div>
"""), unsafe_allow_html=True)

st.sidebar.markdown("""<div style="font-family:'DM Mono'; font-size:0.62em; font-weight:400; color:#4A5568; letter-spacing:0.2em; text-transform:uppercase; padding:14px 15px 6px;">Navigation</div>""", unsafe_allow_html=True)
page = st.sidebar.radio("MENU",
    ["📊 Dashboard", "💼 Portfolio", "🍫 12-Pack Radar", "📈 Backtest Lab", "📰 Macro News"],
    label_visibility="collapsed")

st.sidebar.markdown("""<div style="font-family:'DM Mono'; font-size:0.62em; font-weight:400; color:#4A5568; letter-spacing:0.2em; text-transform:uppercase; padding:6px 15px;">Theme Color</div>""", unsafe_allow_html=True)
col1, col2, col3 = st.sidebar.columns([0.1, 1, 0.1])
with col2:
    new_color = st.color_picker("메인 컬러", st.session_state.main_color, label_visibility="collapsed", key="cp_theme")
    if new_color != st.session_state.main_color:
        st.session_state.main_color = new_color
        st.rerun()

st.sidebar.markdown("""<div style="font-family:'DM Mono'; font-size:0.62em; font-weight:400; color:#4A5568; letter-spacing:0.2em; text-transform:uppercase; padding:14px 15px 4px; border-top:1px solid rgba(0,0,0,0.08);">배경 색상</div>""", unsafe_allow_html=True)
_bg_c1, _bg_c2, _bg_c3 = st.sidebar.columns([0.1, 1, 0.1])
with _bg_c2:
    _new_bg = st.color_picker("배경색", st.session_state.bg_color, label_visibility="collapsed", key="cp_bg")
    if _new_bg != st.session_state.bg_color:
        st.session_state.bg_color = _new_bg
        st.rerun()

with st.sidebar.expander("🎨  글씨 색상 설정", expanded=False):
    _tc_defs = [
        ("heading",  "헤딩  (제목·큰 숫자)",    "tc_heading",  "cp_tc_heading"),
        ("body",     "본문  (설명·라벨)",        "tc_body",     "cp_tc_body"),
        ("muted",    "뮤트  (보조 텍스트)",      "tc_muted",    "cp_tc_muted"),
        ("label",    "서브라벨  (캡션·단위)",    "tc_label",    "cp_tc_label"),
        ("data",     "데이터  (숫자·표)",        "tc_data",     "cp_tc_data"),
        ("sidebar",  "사이드바  (메뉴)",         "tc_sidebar",  "cp_tc_sidebar"),
    ]
    for _role, _disp, _key, _widget_key in _tc_defs:
        _lc, _rc = st.columns([2, 1])
        _lc.markdown(
            f'<div style="font-family:DM Mono,monospace;font-size:0.72em;'
            f'color:{getattr(st.session_state, _key)};padding:6px 0 0 2px;">{_disp}</div>',
            unsafe_allow_html=True
        )
        _picked = _rc.color_picker("", getattr(st.session_state, _key),
                                    label_visibility="collapsed", key=_widget_key)
        if _picked != getattr(st.session_state, _key):
            setattr(st.session_state, _key, _picked)
            st.rerun()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    if st.button("↺  색상 전체 초기화", use_container_width=True, key="reset_colors"):
        for _k, _v in [("main_color","#10B981"),("bg_color","#F7F6F2"),
                        ("tc_heading","#111118"),("tc_body","#2D2D2D"),
                        ("tc_muted","#6B6B7A"),("tc_label","#9494A0"),
                        ("tc_data","#111118"),("tc_sidebar","#2D2D2D")]:
            setattr(st.session_state, _k, _v)
        st.rerun()

st.sidebar.markdown("""<div style="font-family:'DM Mono'; font-size:0.62em; font-weight:400; color:#4A5568; letter-spacing:0.2em; text-transform:uppercase; padding:6px 15px;">Bookmarks</div>""", unsafe_allow_html=True)
st.sidebar.markdown("""
<div style="display:flex; flex-direction:column; gap:0px; padding:0 12px;">
    <a href="https://www.youtube.com/@JB_Insight" target="_blank" class="sidebar-link">📊 JB 인사이트</a>
    <a href="https://www.youtube.com/@odokgod" target="_blank" class="sidebar-link">📻 오독</a>
    <a href="https://www.youtube.com/@TQQQCRAZY" target="_blank" class="sidebar-link">🔥 TQQQ 미친놈</a>
    <a href="https://www.youtube.com/@developmong" target="_blank" class="sidebar-link">🐒 디벨롭몽</a>
    <a href="https://kr.investing.com/" target="_blank" class="sidebar-link">🌍 인베스팅닷컴</a>
    <a href="https://kr.tradingview.com/" target="_blank" class="sidebar-link">📉 트레이딩뷰</a>
    <a href="https://claude.ai/" target="_blank" class="sidebar-link">🧠 클로드</a>
    <a href="https://gemini.google.com/" target="_blank" class="sidebar-link">✨ 제미나이</a>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""<div style="font-family:'DM Mono'; font-size:0.62em; font-weight:400; color:#4A5568; letter-spacing:0.2em; text-transform:uppercase; padding:14px 20px 6px; border-top:1px solid rgba(0,0,0,0.08);">Portfolio Data</div>""", unsafe_allow_html=True)

import json as _json2
_sb_json = _json2.dumps(st.session_state.portfolio)
st.sidebar.download_button(
    "💾  Backup (JSON 저장)",
    data=_sb_json,
    file_name="portfolio.json",
    mime="application/json",
    use_container_width=True,
    key="sb_backup"
)

_sidebar_upload = st.sidebar.file_uploader(
    "📂  Restore (JSON 불러오기)",
    type="json",
    key="sb_uploader",
    label_visibility="visible"
)
if _sidebar_upload is not None:
    try:
        import json as _json
        _loaded = _json.load(_sidebar_upload)
        st.session_state.portfolio.update(_loaded)
        sanitize_portfolio()
        save_portfolio_to_disk()
        st.sidebar.success("✅ 복구 완료")
        st.rerun()
    except:
        st.sidebar.error("❌ 파일 형식 오류")

# ==========================================
# 5. 메인 헤더
# ==========================================
_qqq_chg  = (last_row['QQQ'] / last_row['QQQ_MA200'] - 1) * 100
_vix_now  = last_row['^VIX']
_smh_chg  = last_row['SMH_1M_Ret'] * 100

def _pill(label, value, color):
    return (f'<div style="display:flex;flex-direction:column;align-items:center;'
            f'padding:8px 18px;background:#FFFFFF;border:1px solid rgba(0,0,0,0.07);'
            f'border-top:2px solid {color};border-radius:12px;min-width:90px;">'
            f'<span style="font-family:\'DM Mono\';font-size:0.6em;color:#4A5568;letter-spacing:0.14em;text-transform:uppercase;">{label}</span>'
            f'<span style="font-family:\'DM Mono\';font-size:1.05em;font-weight:500;color:#0F172A;margin-top:2px;">{value}</span>'
            f'</div>')

_p_qqq  = _pill("QQQ/200MA", f"{_qqq_chg:+.1f}%", main_color if _qqq_chg >= 0 else "#EF4444")
_p_vix  = _pill("VIX", f"{_vix_now:.1f}", main_color if _vix_now < 20 else ("#F59E0B" if _vix_now < 30 else "#EF4444"))
_p_smh  = _pill("SMH 1M", f"{_smh_chg:+.1f}%", main_color if _smh_chg >= 0 else "#EF4444")
_p_reg  = _pill("REGIME", f"R{curr_regime}", main_color)

_hdr_left = apply_theme(f"""
<div style="display:flex;flex-direction:column;justify-content:center;">
    <div style="font-family:'Plus Jakarta Sans';font-size:2.5em;font-weight:800;letter-spacing:-2px;color:#0F172A;line-height:1;">
        AMLS <span style="color:#10B981;">V4.5</span>
    </div>
    <div style="font-family:'DM Mono';font-size:0.65em;color:#4A5568;letter-spacing:0.22em;text-transform:uppercase;margin-top:4px;">
        The Wall Street Quantitative Strategy
    </div>
</div>
""")

_hdr_right = apply_theme(f"""
<div style="display:flex;flex-direction:column;align-items:flex-end;gap:8px;">
    <div style="display:flex;gap:6px;">
        {_p_qqq}{_p_vix}{_p_smh}{_p_reg}
    </div>
    <div style="display:flex;align-items:center;gap:10px;">
        <div class="live-pulse" style="font-family:'DM Mono';font-size:0.68em;color:#059669;padding:4px 12px;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.3);border-radius:6px;letter-spacing:0.06em;">{rt_label}</div>
        <div style="font-family:'DM Mono';font-size:0.68em;color:#4A5568;letter-spacing:0.04em;">⏱ {last_update_time}</div>
    </div>
</div>
""")

hdr_c1, hdr_c2 = st.columns([1, 1.6])
with hdr_c1:
    st.markdown(_hdr_left, unsafe_allow_html=True)
with hdr_c2:
    c_sync1, c_sync2 = st.columns([4, 1])
    with c_sync2:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button("↺ 동기화", use_container_width=True):
            fetch_realtime_prices.clear()
            load_data.clear()
            st.rerun()
    with c_sync1:
        st.markdown(_hdr_right, unsafe_allow_html=True)

st.markdown(apply_theme(f"""
<div style="position:relative;margin:14px 0 24px;height:1px;background:rgba(0,0,0,0.07);">
    <div style="position:absolute;left:0;top:0;width:100%;height:1px;background:rgba(0,0,0,0.12);"></div>
    <div style="position:absolute;left:0;top:-1px;width:80px;height:3px;background:var(--acc);"></div>
</div>
"""), unsafe_allow_html=True)

# ==========================================
# 6. 페이지 라우팅
# ==========================================
if page == "📊 Dashboard":

    def _lg_row(label, val, passed):
        icon  = "●" if passed else "○"
        color = main_color if passed else "#B0B0BE"
        if isinstance(val, (int, float)):
            val_str = f"${val:.2f}" if val > 5 else f"{val:.2f}"
        elif isinstance(val, str) and '%' in val:
            val_str = val
        else:
            val_str = str(val)
        return (f'<div class="crow">'
                f'<span class="clabel">{label}</span>'
                f'<span class="cval" style="color:{color};">{val_str}&nbsp;'
                f'<span style="font-size:0.7em;">{icon}</span></span>'
                f'</div>')

    soxl_title = "SOXL  APPROVED" if smh_cond else "USD  DEFENSE"
    soxl_strat = "3× Leverage Active" if smh_cond else "2× Defense Mode"
    soxl_color = main_color if smh_cond else "#9494A0"

    _qqq_vs  = (last_row['QQQ']  / last_row['QQQ_MA200']  - 1) * 100
    _tqqq_vs = (last_row['TQQQ'] / last_row['TQQQ_MA200'] - 1) * 100
    _smh_vs  = (last_row['SMH']  / last_row['SMH_MA50']   - 1) * 100
    _vix_val = last_row['^VIX']
    _rsi_val = last_row['SMH_RSI']

    def _tick(label, val, sub, ok):
        c   = "#059669" if ok else "#DC2626"
        dot = "▲" if ok else "▼"
        return (
            f'<div style="display:inline-flex;flex-direction:column;'
            f'padding:0 20px;border-right:1px solid rgba(0,0,0,0.09);min-width:110px;">'
            f'<span style="font-family:DM Mono,monospace;font-size:0.65em;color:#9494A0;'
        f'letter-spacing:0.14em;text-transform:uppercase;">{label}</span>'
            f'<span style="font-family:DM Mono,monospace;font-size:1.05em;color:#111118;'
            f'font-variant-numeric:tabular-nums;">{val}</span>'
            f'<span style="font-family:DM Mono,monospace;font-size:0.76em;color:{c};">'
            f'{dot} {sub}</span>'
            f'</div>'
        )

    tickers = (
        _tick("QQQ",     f"${last_row['QQQ']:.2f}",            f"{_qqq_vs:+.2f}%",           _qqq_vs>=0)  +
        _tick("TQQQ",    f"${last_row['TQQQ']:.2f}",           f"{_tqqq_vs:+.2f}%",          _tqqq_vs>=0) +
        _tick("VIX",     f"{_vix_val:.2f}",                    f"MA20: {last_row['VIX_MA20']:.1f}", _vix_val<20) +
        _tick("SMH 1M",  f"{last_row['SMH_1M_Ret']*100:+.1f}%",f"vs 50MA: {_smh_vs:+.1f}%", last_row['SMH_1M_Ret']>=0) +
        _tick("SMH RSI", f"{_rsi_val:.1f}",                    "> 50 target",                _rsi_val>50)
    )

    st.markdown(
        f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);'
        f'border-left:3px solid #111118;padding:12px 0 12px 18px;'
        f'margin-bottom:14px;display:flex;align-items:center;overflow-x:auto;">'
        f'<span style="font-family:DM Mono,monospace;font-size:0.65em;color:#9494A0;'
        f'letter-spacing:0.18em;text-transform:uppercase;white-space:nowrap;'
        f'padding-right:16px;border-right:1px solid rgba(0,0,0,0.09);">Live&nbsp;Feed</span>'
        f'{tickers}'
        f'<div style="margin-left:auto;padding:0 14px;white-space:nowrap;">'
        f'<span class="live-pulse" style="font-family:DM Mono,monospace;font-size:0.6em;'
        f'color:#059669;letter-spacing:0.06em;">{rt_label}</span>'
        f'</div></div>',
        unsafe_allow_html=True
    )

    left_col, right_col = st.columns([1, 2.4])

    with left_col:
        r_colors = {1: main_color, 2: "#D97706", 3: "#DC2626", 4: "#7C3AED"}
        regime_accent = r_colors[curr_regime]

        cond_rows = (
            _lg_row('VIX < 40',     f'{vix_close:.2f}',  vix_close<=40)       +
            _lg_row('QQQ > 200MA',  f'${qqq_close:.2f}', qqq_close>=qqq_ma200) +
            _lg_row('50MA ≥ 200MA', f'${qqq_ma50:.2f}',  qqq_ma50>=qqq_ma200)
        )
        st.markdown(apply_theme(
            f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);'
            f'border-top:3px solid {regime_accent};'
            f'padding:20px 18px 16px;margin-bottom:10px;position:relative;overflow:hidden;">'
            f'<div style="position:absolute;right:-4px;bottom:-16px;'
            f'font-family:Plus Jakarta Sans,sans-serif;font-size:7em;font-weight:800;'
            f'color:rgba(0,0,0,0.04);line-height:1;pointer-events:none;user-select:none;">'
            f'{curr_regime}</div>'
            f'<div style="font-family:DM Mono,monospace;font-size:0.68em;color:#9494A0;'
            f'letter-spacing:0.18em;text-transform:uppercase;margin-bottom:10px;">Market Regime</div>'
            f'<div style="font-family:Plus Jakarta Sans,sans-serif;font-size:2em;'
            f'font-weight:800;letter-spacing:-1px;color:{regime_accent};'
            f'letter-spacing:-0.5px;line-height:1;margin-bottom:4px;">'
            f'{regime_info[curr_regime][0]}</div>'
            f'<div style="font-family:DM Mono,monospace;font-size:0.72em;color:#6B6B7A;'
            f'letter-spacing:0.1em;text-transform:uppercase;margin-bottom:14px;">'
            f'{regime_info[curr_regime][1]}</div>'
            f'{cond_rows}'
            f'<div style="margin-top:8px;padding:6px 10px;'
            f'background:rgba(16,185,129,0.07);border-left:2px solid {main_color};'
            f'font-family:DM Mono,monospace;font-size:0.76em;color:#059669;">'
            f'{regime_committee_msg}</div>'
            f'</div>'
        ), unsafe_allow_html=True)

        soxl_rows = (
            _lg_row('SMH > 50MA',       f'${smh_close:.2f}', smh_c1) +
            _lg_row('Momentum 1M >10%', f'{smh_1m*100:.1f}%', smh_c2) +
            _lg_row('RSI > 50',         f'{smh_rsi:.1f}',    smh_c3)
        )
        st.markdown(apply_theme(
            f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);'
            f'border-top:3px solid {soxl_color};'
            f'padding:18px 18px 14px;margin-bottom:10px;">'
            f'<div style="font-family:DM Mono,monospace;font-size:0.68em;color:#9494A0;'
            f'letter-spacing:0.18em;text-transform:uppercase;margin-bottom:8px;">Semi-Conductor Gate</div>'
            f'<div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.6em;'
            f'font-weight:400;color:{soxl_color};margin-bottom:4px;">'
            f'{soxl_title}</div>'
            f'<div style="font-family:DM Mono,monospace;font-size:0.7em;color:#6B6B7A;'
            f'letter-spacing:0.1em;text-transform:uppercase;margin-bottom:12px;">{soxl_strat}</div>'
            f'{soxl_rows}'
            f'</div>'
        ), unsafe_allow_html=True)

        weight_bar_rows = ""
        for k, v in target_weights.items():
            if v <= 0:
                continue
            pct   = v * 100
            bar_w = int(pct * 2.5)
            weight_bar_rows += (
                f'<div style="display:flex;align-items:center;'
                f'justify-content:space-between;padding:7px 0;'
                f'border-bottom:1px solid rgba(0,0,0,0.05);">'
                f'<span style="font-family:DM Mono,monospace;font-size:0.84em;'
                f'color:#2C2C35;min-width:48px;">{k}</span>'
                f'<div style="flex:1;margin:0 9px;height:4px;'
                f'background:rgba(0,0,0,0.07);overflow:hidden;">'
                f'<div style="height:4px;width:{bar_w}%;background:{main_color};"></div>'
                f'</div>'
                f'<span style="font-family:DM Mono,monospace;font-size:0.84em;'
                f'color:{main_color};font-variant-numeric:tabular-nums;'
                f'min-width:36px;text-align:right;">{pct:.0f}%</span>'
                f'</div>'
            )
        st.markdown(apply_theme(
            f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);'
            f'border-top:3px solid #111118;padding:18px 18px 14px;">'
            f'<div style="font-family:DM Mono,monospace;font-size:0.68em;color:#9494A0;'
            f'letter-spacing:0.18em;text-transform:uppercase;margin-bottom:12px;">'
            f'Target Weights  ·  R{curr_regime}</div>'
            f'{weight_bar_rows}'
            f'</div>'
        ), unsafe_allow_html=True)

    with right_col:
        r_labels = {1:"R1  BULL", 2:"R2  CORR", 3:"R3  BEAR", 4:"R4  PANIC"}
        r_clrs   = {1: main_color, 2:"#D97706", 3:"#DC2626", 4:"#7C3AED"}
        tabs_html = ""
        for r in [1, 2, 3, 4]:
            active   = (r == curr_regime)
            bg_t     = r_clrs[r] if active else "transparent"
            ft_t     = "#FFFFFF" if active else "#9494A0"
            bdr_t    = f"1px solid {r_clrs[r]}" if active else "1px solid rgba(0,0,0,0.08)"
            tabs_html += (
                f'<div style="padding:7px 16px;border:{bdr_t};background:{bg_t};">'
                f'<span style="font-family:DM Mono,monospace;font-size:0.76em;'
                f'font-weight:500;color:{ft_t};letter-spacing:0.05em;">{r_labels[r]}</span>'
                f'</div>'
            )
        st.markdown(
            f'<div style="display:flex;gap:4px;margin-bottom:10px;align-items:center;">'
            f'{tabs_html}'
            f'<div style="margin-left:auto;font-family:DM Mono,monospace;font-size:0.7em;'
            f'color:#9494A0;">⏱ {last_update_time}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        df_recent = df.iloc[-500:]

        fig_qqq = go.Figure()
        fig_qqq.add_trace(go.Scatter(
            x=df_recent.index, y=df_recent['QQQ'], name='QQQ',
            line=dict(color=line_c, width=2),
            fill='tozeroy', fillcolor=f'rgba({r_c},{g_c},{b_c},0.06)'
        ))
        fig_qqq.add_trace(go.Scatter(
            x=df_recent.index, y=df_recent['QQQ_MA200'], name='200MA',
            line=dict(color=dash_c, width=1.2, dash='dot')
        ))
        fig_qqq.update_layout(
            title=dict(text="QQQ  /  200-Day Moving Average",
                       font=dict(family='DM Mono', size=13, color=t_color)),
            height=330, **chart_layout,
            legend=dict(orientation='h', yanchor='bottom', y=1.0,
                        xanchor='right', x=1,
                        font=dict(family='DM Mono', size=11, color=t_color))
        )
        fig_qqq.update_xaxes(**_ax)
        fig_qqq.update_yaxes(**_ax)

        fig_tqqq = go.Figure()
        fig_tqqq.add_trace(go.Scatter(
            x=df_recent.index, y=df_recent['TQQQ'], name='TQQQ',
            line=dict(color=line_c, width=2),
            fill='tozeroy', fillcolor=f'rgba({r_c},{g_c},{b_c},0.06)'
        ))
        fig_tqqq.add_trace(go.Scatter(
            x=df_recent.index, y=df_recent['TQQQ_MA200'], name='200MA',
            line=dict(color=dash_c, width=1.2, dash='dot')
        ))
        fig_tqqq.update_layout(
            title=dict(text="TQQQ  /  200-Day Moving Average",
                       font=dict(family='DM Mono', size=13, color=t_color)),
            height=330, **chart_layout,
            legend=dict(orientation='h', yanchor='bottom', y=1.0,
                        xanchor='right', x=1,
                        font=dict(family='DM Mono', size=11, color=t_color))
        )
        fig_tqqq.update_xaxes(**_ax)
        fig_tqqq.update_yaxes(**_ax)

        with st.container(border=True):
            st.plotly_chart(fig_qqq, use_container_width=True)
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.plotly_chart(fig_tqqq, use_container_width=True)

    with st.spinner("글로벌 마켓 데이터 로딩..."):
        _gm_data, _gm_tickers, _asset_tickers, _leader_tickers = fetch_global_markets()

    def _sec_label(txt):
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:12px;margin:24px 0 14px;">'
            f'<div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.1em;font-weight:700;'
            f'color:{tc_heading};letter-spacing:-0.3px;white-space:nowrap;">'
            f'{txt}</div>'
            f'<div style="flex:1;height:1px;background:rgba(0,0,0,0.12);"></div>'
            f'</div>',
            unsafe_allow_html=True)

    def _chg_color(v): return "#059669" if v >= 0 else "#DC2626"
    def _chg_arrow(v): return "▲" if v >= 0 else "▼"

    _sec_label("① Nasdaq 100  ·  Heatmap")

    _qqq_stocks = {
        'AAPL': ('Technology', 'Apple'),
        'MSFT': ('Technology', 'Microsoft'),
        'NVDA': ('Technology', 'Nvidia'),
        'AVGO': ('Technology', 'Broadcom'),
        'AMD':  ('Technology', 'AMD'),
        'INTC': ('Technology', 'Intel'),
        'QCOM': ('Technology', 'Qualcomm'),
        'TXN':  ('Technology', 'Texas Instr'),
        'ORCL': ('Technology', 'Oracle'),
        'ADBE': ('Technology', 'Adobe'),
        'CRM':  ('Technology', 'Salesforce'),
        'NOW':  ('Technology', 'ServiceNow'),
        'INTU': ('Technology', 'Intuit'),
        'GOOGL':('Communication', 'Alphabet'),
        'META': ('Communication', 'Meta'),
        'NFLX': ('Communication', 'Netflix'),
        'AMZN': ('Consumer', 'Amazon'),
        'TSLA': ('Consumer', 'Tesla'),
        'BKNG': ('Consumer', 'Booking'),
        'MCD':  ('Consumer', "McDonald's"),
        'COST': ('Consumer', 'Costco'),
        'SBUX': ('Consumer', 'Starbucks'),
        'PYPL': ('Financials', 'PayPal'),
        'ISRG': ('Healthcare', 'Intuitive Surg'),
        'GILD': ('Healthcare', 'Gilead'),
        'AMGN': ('Healthcare', 'Amgen'),
        'REGN': ('Healthcare', 'Regeneron'),
        'HON':  ('Industrials', 'Honeywell'),
        'PEP':  ('Staples', 'PepsiCo'),
    }

    _qqq_tlist = list(_qqq_stocks.keys())
    _qqq_missing = [t for t in _qqq_tlist if t not in _gm_data]
    if _qqq_missing:
        try:
            _end_q = datetime.now()
            _start_q = _end_q - timedelta(days=5)
            _raw_q = yf.download(_qqq_missing,
                                  start=_start_q.strftime('%Y-%m-%d'),
                                  end=_end_q.strftime('%Y-%m-%d'),
                                  progress=False, auto_adjust=True)['Close']
            for _t in _qqq_missing:
                _col_q = _raw_q[_t] if _t in _raw_q.columns else None
                if _col_q is not None:
                    _s = _col_q.dropna()
                    if len(_s) >= 2:
                        _gm_data[_t] = {'price': float(_s.iloc[-1]),
                                         'chg': float((_s.iloc[-1]/_s.iloc[-2]-1)*100)}
                    elif len(_s) == 1:
                        _gm_data[_t] = {'price': float(_s.iloc[-1]), 'chg': 0.0}
        except:
            pass

    _tm_labels, _tm_parents, _tm_values, _tm_colors, _tm_text = [], [], [], [], []
    _tm_labels.append("Nasdaq 100"); _tm_parents.append(""); _tm_values.append(0); _tm_colors.append(0); _tm_text.append("")

    _sector_set = {}
    for _t, (_sec, _name) in _qqq_stocks.items():
        if _sec not in _sector_set:
            _sector_set[_sec] = True
            _tm_labels.append(_sec); _tm_parents.append("Nasdaq 100")
            _tm_values.append(0); _tm_colors.append(0); _tm_text.append("")

    for _t, (_sec, _name) in _qqq_stocks.items():
        _d   = _gm_data.get(_t, {})
        _chg = _d.get('chg', 0.0)
        _px  = _d.get('price', 0.0)
        _tm_labels.append(f"{_t}")
        _tm_parents.append(_sec)
        _tm_values.append(max(abs(_px) * 0.1, 1))
        _tm_colors.append(_chg)
        _tm_text.append(f"{_name}<br>{_px:,.1f}<br>{_chg:+.2f}%")

    _tm_fig = go.Figure(go.Treemap(
        labels=_tm_labels,
        parents=_tm_parents,
        values=_tm_values,
        customdata=_tm_text,
        hovertemplate='%{customdata}<extra></extra>',
        texttemplate='<b>%{label}</b><br>%{customdata}',
        textfont=dict(size=11, family='DM Mono'),
        marker=dict(
            colors=_tm_colors,
            colorscale=[
                [0.0, '#DC2626'],
                [0.3, '#FCA5A5'],
                [0.5, '#F7F6F2'],
                [0.7, '#6EE7B7'],
                [1.0, '#059669'],
            ],
            cmid=0,
            cmin=-3, cmax=3,
            showscale=True,
            colorbar=dict(
                thickness=12, len=0.6,
                title=dict(text='%', font=dict(size=10, family='DM Mono')),
                tickfont=dict(size=9, family='DM Mono'),
                tickformat='+.1f',
            )
        ),
        branchvalues='total',
        tiling=dict(packing='squarify'),
    ))
    _tm_fig.update_layout(
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='DM Mono', color=t_color),
        margin=dict(l=0, r=0, t=10, b=0),
    )
    with st.container(border=True):
        st.plotly_chart(_tm_fig, use_container_width=True)

    _sec_label("② Rates  /  Commodities  /  Crypto")
    _asset_icons = {'^TNX':'📈','GLD':'🥇','SLV':'⚪','USO':'🛢','BTC-USD':'₿','ETH-USD':'Ξ','UUP':'💵'}
    _asset_cols = st.columns(7)
    for _i, (_t, _name) in enumerate(_asset_tickers.items()):
        _d   = _gm_data.get(_t, {})
        _chg = _d.get('chg', 0.0)
        _px  = _d.get('price', 0.0)
        _clr = _chg_color(_chg)
        _ico = _asset_icons.get(_t, '')
        with _asset_cols[_i]:
            st.markdown(
                f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);'
                f'border-top:2px solid {_clr};padding:12px 10px;text-align:center;">'
                f'<div style="font-size:1.1em;margin-bottom:4px;">{_ico}</div>'
                f'<div style="font-family:DM Mono,monospace;font-size:0.6em;color:#9494A0;'
                f'letter-spacing:0.1em;text-transform:uppercase;">{_name}</div>'
                f'<div style="font-family:DM Mono,monospace;font-size:0.88em;color:#111118;'
                f'font-variant-numeric:tabular-nums;margin:3px 0;">${_px:,.2f}</div>'
                f'<div style="font-family:DM Mono,monospace;font-size:0.8em;'
                f'color:{_clr};font-weight:600;">{_chg_arrow(_chg)} {_chg:+.2f}%</div>'
                f'</div>', unsafe_allow_html=True)

    _sec_label("③ Market Leaders  ·  Magnificent 7  +  Semis")
    _ld_sorted = sorted(_leader_tickers.items(),
                        key=lambda x: _gm_data.get(x[0],{}).get('chg',0), reverse=True)
    _ld_cols = st.columns(5)
    for _i, (_t, _name) in enumerate(_ld_sorted):
        _d   = _gm_data.get(_t, {})
        _chg = _d.get('chg', 0.0)
        _px  = _d.get('price', 0.0)
        _clr = _chg_color(_chg)
        _rank_color = "#D97706" if _i == 0 else ("#9494A0" if _i >= 3 else "#111118")
        with _ld_cols[_i % 5]:
            st.markdown(
                f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);'
                f'border-top:2px solid {_clr};padding:12px 14px;margin-bottom:8px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
                f'<span style="font-family:DM Mono,monospace;font-size:0.62em;color:#9494A0;'
                f'text-transform:uppercase;letter-spacing:0.1em;">{_t}</span>'
                f'<span style="font-family:DM Mono,monospace;font-size:0.62em;'
                f'color:{_rank_color};font-weight:600;">#{_i+1}</span>'
                f'</div>'
                f'<div style="font-family:DM Sans,sans-serif;font-size:0.82em;'
                f'color:#2C2C35;margin:3px 0;">{_name}</div>'
                f'<div style="font-family:DM Mono,monospace;font-size:1.0em;color:#111118;'
                f'font-variant-numeric:tabular-nums;">${_px:,.2f}</div>'
                f'<div style="font-family:DM Mono,monospace;font-size:0.82em;'
                f'color:{_clr};font-weight:600;">{_chg_arrow(_chg)} {_chg:+.2f}%</div>'
                f'</div>', unsafe_allow_html=True)

    _sec_label("④ Sector Scanner  ·  1-Month Performance")
    _sec_data_full = [
        {'t': s, 'name': {'XLK':'Technology','XLV':'Health Care','XLF':'Financials',
            'XLY':'Cons. Discret','XLC':'Comm. Svc','XLI':'Industrials',
            'XLP':'Cons. Staples','XLE':'Energy','XLU':'Utilities',
            'XLRE':'Real Estate','XLB':'Materials'}.get(s, s),
         'ret1m': last_row.get(f'{s}_1M', 0.0) * 100}
        for s in SECTOR_TICKERS
    ]
    _sec_sorted_full = sorted(_sec_data_full, key=lambda x: x['ret1m'], reverse=True)

    _sec_fig = go.Figure()
    _sec_names_plot  = [x['name'] for x in _sec_sorted_full]
    _sec_rets_plot   = [x['ret1m'] for x in _sec_sorted_full]
    _sec_colors_plot = [_chg_color(v) for v in _sec_rets_plot]
    _sec_fig.add_trace(go.Bar(
        x=_sec_names_plot, y=_sec_rets_plot,
        marker_color=_sec_colors_plot, marker_line_width=0,
        text=[f"{v:+.1f}%" for v in _sec_rets_plot],
        textposition='outside', textfont=dict(size=10, family='DM Mono')
    ))
    _sec_fig.update_layout(
        height=260, showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='DM Mono', color=t_color),
        margin=dict(l=0, r=0, t=20, b=40)
    )
    _sec_fig.update_xaxes(**_ax_r, tickfont=dict(size=10))
    _sec_fig.update_yaxes(tickformat='.1f', ticksuffix='%', **_ax_r)
    with st.container(border=True):
        st.plotly_chart(_sec_fig, use_container_width=True)

    _sec_label("⑤ US Economic Calendar  ·  Key Events This Week")
    _cal_l, _cal_r = st.columns([1.4, 1])
    with _cal_l:
        from datetime import date
        _today    = date.today()
        _weekday  = _today.weekday()
        _mon      = _today - timedelta(days=_weekday)
        def _wd(offset):
            d = _mon + timedelta(days=offset)
            return d.strftime('%m/%d (%a)')

        _cal_events = [
            (_wd(0), "월", "ISM 제조업 PMI",           "보통", "#D97706"),
            (_wd(0), "월", "건설 지출",                 "낮음", "#9494A0"),
            (_wd(1), "화", "JOLTS 구인 건수",           "높음", "#DC2626"),
            (_wd(1), "화", "공장 수주",                 "보통", "#D97706"),
            (_wd(2), "수", "ADP 민간 고용 변화",        "높음", "#DC2626"),
            (_wd(2), "수", "ISM 서비스 PMI",            "보통", "#D97706"),
            (_wd(2), "수", "FOMC 의사록",               "높음", "#DC2626"),
            (_wd(3), "목", "신규 실업수당 청구건수",    "보통", "#D97706"),
            (_wd(3), "목", "무역수지",                  "보통", "#D97706"),
            (_wd(4), "금", "비농업 고용 (NFP)",         "매우높음", "#DC2626"),
            (_wd(4), "금", "실업률",                    "매우높음", "#DC2626"),
            (_wd(4), "금", "평균 시간당 임금",          "보통", "#D97706"),
        ]
        st.markdown(
            '<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);">'
            '<table style="width:100%;border-collapse:collapse;font-family:DM Mono,monospace;">'
            '<tr style="border-bottom:2px solid #111118;">'
            '<th style="padding:8px 10px;font-size:0.6em;color:#9494A0;letter-spacing:0.14em;'
            'text-transform:uppercase;text-align:left;font-weight:400;">날짜</th>'
            '<th style="padding:8px 10px;font-size:0.6em;color:#9494A0;letter-spacing:0.14em;'
            'text-transform:uppercase;text-align:left;font-weight:400;">지표</th>'
            '<th style="padding:8px 10px;font-size:0.6em;color:#9494A0;letter-spacing:0.14em;'
            'text-transform:uppercase;text-align:center;font-weight:400;">영향</th>'
            '</tr>'
            + "".join([
                f'<tr style="border-bottom:1px solid rgba(0,0,0,0.05);">'
                f'<td style="padding:7px 10px;font-size:0.7em;color:#9494A0;white-space:nowrap;">'
                f'{date_s}</td>'
                f'<td style="padding:7px 10px;font-size:0.82em;color:#2C2C35;font-family:Plus Jakarta Sans,sans-serif;">{evt}</td>'
                f'<td style="padding:7px 10px;text-align:center;">'
                f'<span style="background:{imp_c}22;color:{imp_c};border:1px solid {imp_c}55;'
                f'font-size:0.62em;padding:2px 8px;letter-spacing:0.04em;">{imp}</span></td>'
                f'</tr>'
                for date_s, _, evt, imp, imp_c in _cal_events
            ])
            + '</table></div>',
            unsafe_allow_html=True
        )
    with _cal_r:
        _high_events = [e for e in _cal_events if e[3] in ("높음", "매우높음")]
        st.markdown(
            f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);'
            f'border-top:2px solid #DC2626;padding:16px 18px;">'
            f'<div style="font-family:DM Mono,monospace;font-size:0.6em;color:#9494A0;'
            f'letter-spacing:0.16em;text-transform:uppercase;margin-bottom:10px;">'
            f'High Impact Events</div>'
            + "".join([
                f'<div style="display:flex;align-items:center;gap:8px;padding:7px 0;'
                f'border-bottom:1px solid rgba(0,0,0,0.05);">'
                f'<div style="width:6px;height:6px;border-radius:50%;background:#DC2626;'
                f'flex-shrink:0;"></div>'
                f'<div>'
                f'<div style="font-family:DM Mono,monospace;font-size:0.62em;color:#9494A0;">'
                f'{d}</div>'
                f'<div style="font-family:Plus Jakarta Sans,sans-serif;font-size:0.85em;color:#2C2C35;'
                f'font-weight:500;">{e}</div>'
                f'</div></div>'
                for d, _, e, imp, _ in _high_events
            ])
            + f'<div style="margin-top:10px;padding:8px;background:rgba(220,38,38,0.05);'
            f'border-left:2px solid #DC2626;">'
            f'<span style="font-family:DM Mono,monospace;font-size:0.66em;color:#9494A0;">'
            f'고영향 이벤트 총 <b style="color:#DC2626;">{len(_high_events)}건</b></span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True
        )

# ──────────────────────────────────────────
elif page == "💼 Portfolio":

    # ── 데이터 계산 ─────────────────────────────────────────
    current_prices = {}
    for t in ASSET_LIST:
        if t == 'CASH': current_prices[t] = 1.0
        elif t in rt_prices: current_prices[t] = rt_prices[t]
        elif t in df.columns: current_prices[t] = df[t].iloc[-1]
        else: current_prices[t] = 0.0

    cur_fx        = rt_prices.get('USDKRW=X', 1350.0)
    curr_vals     = {a: st.session_state.portfolio[a]['shares'] * current_prices[a] for a in ASSET_LIST}
    total_val_usd = sum(curr_vals.values())
    total_val_krw = total_val_usd * cur_fx
    invested_cost = sum(
        st.session_state.portfolio[a]['shares'] * st.session_state.portfolio[a]['avg_price']
        for a in ASSET_LIST if a != 'CASH'
    )
    pnl_usd   = total_val_usd - invested_cost
    pnl_pct   = (pnl_usd / invested_cost * 100) if invested_cost > 0 else 0.0
    pnl_color = "#059669" if pnl_pct >= 0 else "#DC2626"
    pnl_sign  = "▲" if pnl_pct >= 0 else "▼"
    diff_vals = {a: (total_val_usd * target_weights.get(a, 0.0)) - curr_vals[a] for a in ASSET_LIST} if total_val_usd > 0 else {a: 0.0 for a in ASSET_LIST}
    C_GREEN = main_color
    C_RED   = "#DC2626"
    r_acc   = {1: main_color, 2: "#D97706", 3: "#DC2626", 4: "#7C3AED"}[curr_regime]

    # ══════════════════════════════════════════════════════════
    # ZONE 0 — 다크 터미널 마스트헤드
    # ══════════════════════════════════════════════════════════
    def _kv(label, val, color="#E2E8F0", sub=""):
        sub_html = (
            f'<span style="font-family:DM Mono,monospace;font-size:0.62em;'
            f'color:rgba(255,255,255,0.35);">{sub}</span>'
        ) if sub else ""
        return (
            f'<div style="display:flex;flex-direction:column;padding:0 22px;'
            f'border-right:1px solid rgba(255,255,255,0.07);min-width:110px;">'
            f'<span style="font-family:DM Mono,monospace;font-size:0.55em;'
            f'color:rgba(255,255,255,0.38);letter-spacing:0.2em;text-transform:uppercase;'
            f'margin-bottom:3px;">{label}</span>'
            f'<span style="font-family:DM Mono,monospace;font-size:1.0em;font-weight:500;'
            f'color:{color};font-variant-numeric:tabular-nums;line-height:1.2;">{val}</span>'
            f'{sub_html}'
            f'</div>'
        )

    st.markdown(apply_theme(
        f'<div style="background:#111118;border-left:4px solid {r_acc};'
        f'padding:14px 0;margin-bottom:18px;display:flex;align-items:center;overflow-x:auto;">'
        f'<div style="padding:0 22px 0 18px;border-right:1px solid rgba(255,255,255,0.07);'
        f'min-width:170px;flex-shrink:0;">'
        f'<div style="font-family:DM Mono,monospace;font-size:0.54em;'
        f'color:rgba(255,255,255,0.32);letter-spacing:0.22em;text-transform:uppercase;'
        f'margin-bottom:3px;">AMLS V4.5</div>'
        f'<div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.15em;'
        f'font-weight:800;color:#FFFFFF;letter-spacing:-0.5px;line-height:1;">Portfolio</div>'
        f'</div>'
        + _kv("Total NAV",  f"${total_val_usd:,.2f}", "#FFFFFF",              f"₩{total_val_krw:,.0f}")
        + _kv("USD / KRW",  f"₩{cur_fx:,.0f}",        "rgba(255,255,255,0.7)","환율")
        + _kv("P & L",      f"{pnl_pct:+.2f}%",
              "#6EE7B7" if pnl_pct >= 0 else "#FCA5A5",
              f"{pnl_sign} ${pnl_usd:,.0f}")
        + _kv("Regime",     f"R{curr_regime}  {regime_info[curr_regime][1]}", r_acc)
        + _kv("투자 원금",  f"${invested_cost:,.0f}",  "rgba(255,255,255,0.7)","취득원가")
        + f'<div style="margin-left:auto;padding:0 18px;flex-shrink:0;">'
        + f'<span class="live-pulse" style="font-family:DM Mono,monospace;font-size:0.6em;'
        + f'color:#6EE7B7;letter-spacing:0.06em;">{rt_label}</span>'
        + f'</div></div>'
    ), unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════
    # ZONE 1 — Goal Tracker
    # ══════════════════════════════════════════════════════════
    _gc_a, _gc_b = st.columns([1, 3.5])
    with _gc_a:
        new_goal = st.number_input(
            "🎯 목표 금액 (USD)", min_value=1000.0, max_value=100_000_000.0,
            value=st.session_state.goal_usd, step=1000.0, format="%.0f", key="goal_input"
        )
        if new_goal != st.session_state.goal_usd:
            st.session_state.goal_usd = new_goal
            st.rerun()

    with _gc_b:
        _goal    = st.session_state.goal_usd
        _pct_raw = (total_val_usd / _goal * 100) if _goal > 0 else 0.0
        _pct     = min(_pct_raw, 100.0)
        _over    = _pct_raw > 100.0
        _remain  = max(_goal - total_val_usd, 0.0)

        if _over:         _gc, _gbadge, _gicon = "#059669", "목표 달성!", "🏆"
        elif _pct >= 75:  _gc, _gbadge, _gicon = main_color, "75% 돌파",  "⚡"
        elif _pct >= 50:  _gc, _gbadge, _gicon = "#D97706",  "순항 중",   "📈"
        else:             _gc, _gbadge, _gicon = "#94A3B8",  "시작 단계", "🌱"

        _gr, _gg, _gb = hex_to_rgb(_gc)
        _pin_x = min(_pct, 98.5)

        _seg_html = "".join([
            f'<div style="position:absolute;left:{m}%;top:-20px;bottom:-4px;'
            f'width:1px;background:rgba(0,0,0,0.09);">'
            f'<span style="position:absolute;top:0;left:50%;transform:translateX(-50%);'
            f'font-family:DM Mono,monospace;font-size:0.52em;color:#BBBBBB;'
            f'white-space:nowrap;">{m}%</span></div>'
            for m in [25, 50, 75, 100]
        ])

        st.markdown(apply_theme(
            f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.11);'
            f'border-left:4px solid {_gc};padding:16px 24px 14px;margin-bottom:0;">'

            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;">'
            f'<div style="display:flex;align-items:center;gap:10px;">'
            f'<span style="font-size:1.1em;">{_gicon}</span>'
            f'<span style="font-family:DM Mono,monospace;font-size:0.6em;color:#9494A0;'
            f'letter-spacing:0.18em;text-transform:uppercase;">Goal Tracker</span>'
            f'<span style="background:rgba({_gr},{_gg},{_gb},0.10);'
            f'border:1px solid rgba({_gr},{_gg},{_gb},0.28);color:{_gc};'
            f'font-family:DM Mono,monospace;font-size:0.6em;padding:2px 10px;'
            f'letter-spacing:0.06em;">{_gbadge}</span>'
            f'</div>'
            f'<div style="display:flex;gap:28px;align-items:baseline;">'
            f'<div style="text-align:center;">'
            f'<div style="font-family:DM Mono,monospace;font-size:0.52em;color:#9494A0;'
            f'text-transform:uppercase;letter-spacing:0.1em;">현재</div>'
            f'<div style="font-family:DM Mono,monospace;font-size:0.9em;color:#111118;'
            f'font-variant-numeric:tabular-nums;">${total_val_usd:,.2f}</div></div>'
            f'<div style="text-align:center;">'
            f'<div style="font-family:DM Mono,monospace;font-size:0.52em;color:#9494A0;'
            f'text-transform:uppercase;letter-spacing:0.1em;">목표</div>'
            f'<div style="font-family:DM Mono,monospace;font-size:0.9em;color:#111118;'
            f'font-variant-numeric:tabular-nums;">${_goal:,.0f}</div></div>'
            f'<div style="text-align:right;">'
            f'<div style="font-family:DM Mono,monospace;font-size:0.52em;color:#9494A0;'
            f'text-transform:uppercase;letter-spacing:0.1em;">{"초과달성" if _over else "잔여"}</div>'
            f'<div style="font-family:DM Mono,monospace;font-size:0.9em;font-weight:600;'
            f'color:{_gc};font-variant-numeric:tabular-nums;">'
            f'{"🎉" if _over else f"${_remain:,.0f}"}</div></div>'
            f'<div style="padding-left:20px;border-left:1px solid rgba(0,0,0,0.09);">'
            f'<span style="font-family:DM Mono,monospace;font-size:2.4em;font-weight:400;'
            f'color:{_gc};font-variant-numeric:tabular-nums;letter-spacing:-2px;line-height:1;">'
            f'{_pct_raw:.1f}%</span>'
            f'</div>'
            f'</div>'
            f'</div>'

            f'<div style="position:relative;padding-top:22px;">'
            + _seg_html +
            f'<div style="position:relative;height:12px;background:rgba(0,0,0,0.07);">'
            f'<div style="height:12px;width:{_pct:.2f}%;'
            f'background:linear-gradient(90deg,rgba({_gr},{_gg},{_gb},0.4),{_gc});"></div>'
            f'<div style="position:absolute;left:{_pin_x}%;top:-6px;bottom:-6px;width:3px;'
            f'background:{_gc};transform:translateX(-50%);">'
            f'<div style="position:absolute;top:-8px;left:50%;transform:translateX(-50%);'
            f'width:13px;height:13px;border-radius:50%;background:{_gc};'
            f'box-shadow:0 0 8px rgba({_gr},{_gg},{_gb},0.55);"></div>'
            f'</div>'
            f'</div>'
            f'</div>'
            f'</div>'
        ), unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════
    # ZONE 2 — 3열 메인 그리드
    # ══════════════════════════════════════════════════════════

    def _zone_label(text):
        return apply_theme(
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">'
            f'<div style="width:3px;height:14px;background:{main_color};flex-shrink:0;"></div>'
            f'<span style="font-family:DM Mono,monospace;font-size:0.6em;font-weight:600;'
            f'color:{tc_heading};letter-spacing:0.2em;text-transform:uppercase;">{text}</span>'
            f'<div style="flex:1;height:1px;background:rgba(0,0,0,0.10);"></div>'
            f'</div>'
        )

    _z_left, _z_mid, _z_right = st.columns([1, 1.5, 0.9])

    # ── LEFT: Position Input + Quick Orders ─────────────────
    with _z_left:
        st.markdown(_zone_label("Position Input"), unsafe_allow_html=True)

        _edata = []
        for asset in ASSET_LIST:
            v = st.session_state.portfolio.get(asset, {})
            _edata.append({
                "Asset":        asset,
                "Shares":       float(v.get('shares', 0.0)),
                "Avg Price($)": float(v.get('avg_price', 1.0 if asset == 'CASH' else 0.0)),
                "FX Rate(₩)":  float(v.get('fx', 1350.0))
            })
        _df_ed = pd.DataFrame(_edata)
        with st.container(border=True):
            _df_edited = st.data_editor(
                _df_ed, disabled=["Asset"], hide_index=True,
                use_container_width=True, key="pf_editor",
                column_config={
                    "Shares":       st.column_config.NumberColumn("Shares", format="%.4f"),
                    "Avg Price($)": st.column_config.NumberColumn("Avg($)", format="%.2f"),
                    "FX Rate(₩)":  st.column_config.NumberColumn("FX(₩)",  format="%.0f"),
                }
            )
        if not _df_edited.equals(_df_ed):
            for _, row in _df_edited.iterrows():
                st.session_state.portfolio[row["Asset"]] = {
                    'shares':    float(row["Shares"]),
                    'avg_price': float(row["Avg Price($)"]),
                    'fx':        float(row["FX Rate(₩)"])
                }
            save_portfolio_to_disk()
            st.rerun()

        # Quick Orders
        if total_val_usd > 0:
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            st.markdown(_zone_label("Quick Orders"), unsafe_allow_html=True)

            _sells, _buys = [], []
            for asset in ASSET_LIST:
                _cp = current_prices[asset] if current_prices[asset] > 0 else 1.0
                _dv = diff_vals[asset]
                if asset != 'CASH' and _dv < -_cp * 0.05:
                    _sells.append((asset, f"{abs(_dv)/_cp:,.2f}주 매도"))
                elif asset == 'CASH' and _dv < -1.0:
                    _sells.append(("CASH", f"${abs(_dv):,.0f} 사용"))
                if asset != 'CASH' and _dv > _cp * 0.05:
                    _buys.append((asset, f"{_dv/_cp:,.2f}주 매수"))
                elif asset == 'CASH' and _dv > 1.0:
                    _buys.append(("CASH", f"${_dv:,.0f} 확보"))

            _qo1, _qo2 = st.columns(2)

            def _qo_block(col, title, items, accent, bg):
                _rows = "".join([
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'padding:6px 0;border-bottom:1px solid rgba(0,0,0,0.05);">'
                    f'<span style="font-family:DM Mono,monospace;font-size:0.8em;'
                    f'font-weight:700;color:{tc_body};">{a}</span>'
                    f'<span style="font-family:DM Mono,monospace;font-size:0.76em;'
                    f'color:{accent};font-weight:500;font-variant-numeric:tabular-nums;">{v}</span>'
                    f'</div>'
                    for a, v in items
                ]) or (
                    f'<div style="text-align:center;padding:8px 0;">'
                    f'<span style="font-family:DM Mono,monospace;font-size:0.7em;color:#CCCCCC;">— 없음</span>'
                    f'</div>'
                )
                col.markdown(
                    f'<div style="background:{bg};border:1px solid rgba(0,0,0,0.08);'
                    f'border-top:2px solid {accent};padding:10px 12px;">'
                    f'<div style="font-family:Plus Jakarta Sans,sans-serif;font-size:0.78em;'
                    f'font-weight:700;color:{accent};margin-bottom:6px;">{title}</div>'
                    f'{_rows}</div>',
                    unsafe_allow_html=True
                )

            with _qo1: _qo_block(_qo1, "🔴  SELL", _sells, "#DC2626", "rgba(220,38,38,0.03)")
            with _qo2: _qo_block(_qo2, "🟢  BUY",  _buys,  "#059669", "rgba(5,150,105,0.03)")

    # ── CENTER: 도넛 차트 + Delta Bar ───────────────────────
    with _z_mid:
        st.markdown(_zone_label("Allocation  ·  Visual"), unsafe_allow_html=True)

        _pie_colors = [line_c,'#B0B0BE','#34D399','#6EE7B7','#A7F3D0',
                       '#059669','#047857','#065F46','#D1FAE5']
        _pie_base = dict(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family="DM Mono", color=t_color),
            showlegend=True,
            legend=dict(orientation='v', x=1.0, y=0.5,
                        font=dict(size=8, family='DM Mono'),
                        bgcolor='rgba(0,0,0,0)'),
            margin=dict(l=0, r=72, t=28, b=0),
            height=210
        )

        _pc1, _pc2 = st.columns(2)

        _lcur = [a for a in ASSET_LIST if curr_vals[a] > 0]
        _vcur = [curr_vals[a] for a in _lcur]
        with _pc1:
            if sum(_vcur) > 0:
                _fig_c = go.Figure(go.Pie(
                    labels=_lcur, values=_vcur, hole=.55,
                    textinfo='percent', textfont=dict(size=9),
                    marker=dict(colors=_pie_colors, line=dict(color='#FAFAF7', width=1.5))
                ))
                _fig_c.update_layout(
                    title=dict(text="Current", font=dict(family="DM Mono", size=11, color=t_color), x=0),
                    **_pie_base
                )
                with st.container(border=True):
                    st.plotly_chart(_fig_c, use_container_width=True)
            else:
                st.markdown(
                    f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);'
                    f'height:210px;display:flex;align-items:center;justify-content:center;">'
                    f'<span style="font-family:DM Mono,monospace;font-size:0.7em;color:#CCCCCC;">'
                    f'포지션 없음</span></div>',
                    unsafe_allow_html=True
                )

        _ltgt = [a for a in ASSET_LIST if target_weights.get(a, 0) > 0]
        _vtgt = [target_weights[a] for a in _ltgt]
        with _pc2:
            _fig_t = go.Figure(go.Pie(
                labels=_ltgt, values=_vtgt, hole=.55,
                textinfo='percent', textfont=dict(size=9),
                marker=dict(colors=_pie_colors, line=dict(color='#FAFAF7', width=1.5))
            ))
            _fig_t.update_layout(
                title=dict(text=f"Target  R{curr_regime}", font=dict(family="DM Mono", size=11, color=t_color), x=0),
                **_pie_base
            )
            with st.container(border=True):
                st.plotly_chart(_fig_t, use_container_width=True)

        # Delta bar
        _dlabels = [a for a in ASSET_LIST if abs(diff_vals[a]) >= 1.0]
        _dvals   = [diff_vals[a] for a in _dlabels]
        if _dlabels:
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            _fig_d = go.Figure(go.Bar(
                x=_dlabels, y=_dvals,
                marker_color=[C_GREEN if v > 0 else C_RED for v in _dvals],
                text=[f"${v:+,.0f}" for v in _dvals],
                textposition='outside', textfont=dict(size=9, family='DM Mono'),
                marker_line_width=0
            ))
            _fig_d.update_layout(
                title=dict(text="Δ Rebalancing ($)", font=dict(family='DM Mono', size=11, color=t_color)),
                height=190,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color=t_color, family="DM Mono", size=9),
                showlegend=False, margin=dict(t=28, b=8, l=0, r=0)
            )
            _fig_d.update_xaxes(**_ax_r, tickfont=dict(size=9))
            _fig_d.update_yaxes(**_ax_r)
            with st.container(border=True):
                st.plotly_chart(_fig_d, use_container_width=True)

    # ── RIGHT: Regime 카드 + Target Weights + Live Prices + SMH Gate ─
    with _z_right:

        # Regime 카드 — 메인 컬러 테두리 라이트 버전
        st.markdown(apply_theme(
            f'<div style="background:rgba({r_c},{g_c},{b_c},0.06);'
            f'border:1px solid rgba({r_c},{g_c},{b_c},0.25);'
            f'border-left:4px solid {r_acc};'
            f'padding:14px 16px;margin-bottom:12px;">'
            f'<div style="font-family:DM Mono,monospace;font-size:0.55em;'
            f'color:{tc_label};letter-spacing:0.18em;text-transform:uppercase;'
            f'margin-bottom:4px;">Current Regime</div>'
            f'<div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.55em;'
            f'font-weight:800;color:{r_acc};letter-spacing:-0.5px;line-height:1;'
            f'margin-bottom:3px;">{regime_info[curr_regime][0]}</div>'
            f'<div style="font-family:DM Mono,monospace;font-size:0.62em;'
            f'color:{tc_muted};letter-spacing:0.1em;text-transform:uppercase;">'
            f'{regime_info[curr_regime][1]}</div>'
            f'<div style="margin-top:8px;padding-top:8px;'
            f'border-top:1px solid rgba({r_c},{g_c},{b_c},0.18);'
            f'font-family:DM Mono,monospace;font-size:0.6em;color:{tc_muted};">'
            f'{regime_committee_msg}</div>'
            f'</div>'
        ), unsafe_allow_html=True)

        # Target Weights
        st.markdown(_zone_label(f"Target Weights  ·  R{curr_regime}"), unsafe_allow_html=True)

        _wt_items = sorted([(k, v) for k, v in target_weights.items() if v > 0],
                           key=lambda x: x[1], reverse=True)
        _max_wt = max(v for _, v in _wt_items) if _wt_items else 1

        _wt_html = ""
        for _wk, _wv in _wt_items:
            _wpct    = _wv * 100
            _bar_w   = int(_wv / _max_wt * 100)
            _cur_pct = (curr_vals.get(_wk, 0) / total_val_usd * 100) if total_val_usd > 0 else 0
            _dp      = _wpct - _cur_pct
            _dc      = "#059669" if _dp > 0.5 else ("#DC2626" if _dp < -0.5 else "#9494A0")
            _ds      = f"{_dp:+.1f}%" if abs(_dp) > 0.5 else "—"

            _wt_html += (
                f'<div style="padding:7px 0;border-bottom:1px solid rgba(0,0,0,0.05);">'
                f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:5px;">'
                f'<span style="font-family:DM Mono,monospace;font-size:0.84em;font-weight:700;color:{tc_body};">{_wk}</span>'
                f'<div style="display:flex;align-items:baseline;gap:5px;">'
                f'<span style="font-family:DM Mono,monospace;font-size:0.9em;font-weight:600;color:{main_color};">{_wpct:.0f}%</span>'
                f'<span style="font-family:DM Mono,monospace;font-size:0.65em;color:{_dc};">{_ds}</span>'
                f'</div>'
                f'</div>'
                f'<div style="height:5px;background:rgba(0,0,0,0.07);position:relative;">'
                f'<div style="height:5px;width:{_bar_w}%;background:{main_color};max-width:100%;"></div>'
                + (f'<div style="position:absolute;left:{min(_cur_pct/_max_wt*100,99):.1f}%;'
                   f'top:-2px;bottom:-2px;width:2px;background:{tc_label};opacity:0.6;"></div>'
                   if total_val_usd > 0 and _cur_pct > 0.5 else "")
                + f'</div>'
                f'</div>'
            )

        with st.container(border=True):
            st.markdown(f'<div style="padding:4px 0;">{_wt_html}</div>', unsafe_allow_html=True)

        # Live Prices — 포트폴리오 종목 실시간 가격
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown(_zone_label("Live Prices"), unsafe_allow_html=True)

        _lp_rows = ""
        for _asset in ASSET_LIST:
            if _asset == 'CASH':
                _lp_p    = 1.0
                _lp_str  = "$1.00"
                _lp_c    = tc_muted
                _lp_dot  = "●"
            else:
                _lp_p   = current_prices.get(_asset, 0.0)
                _lp_str = f"${_lp_p:,.2f}" if _lp_p > 0 else "—"
                _lp_c   = tc_muted
                _lp_dot = "·"

            # 평단 대비 수익/손실 색상
            _avg = st.session_state.portfolio[_asset].get('avg_price', 0.0)
            _shs = st.session_state.portfolio[_asset].get('shares', 0.0)
            if _asset != 'CASH' and _avg > 0 and _lp_p > 0:
                _lp_ret = (_lp_p / _avg - 1) * 100
                _lp_c   = "#059669" if _lp_ret >= 0 else "#DC2626"
                _lp_sub = f"{_lp_ret:+.1f}%"
            elif _asset == 'CASH' and _shs > 0:
                _lp_sub = f"${_shs:,.0f}"
                _lp_c   = tc_muted
            else:
                _lp_sub = "—"

            _lp_rows += (
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:6px 0;border-bottom:1px solid rgba(0,0,0,0.05);">'
                f'<span style="font-family:DM Mono,monospace;font-size:0.8em;'
                f'font-weight:700;color:{tc_body};">{_asset}</span>'
                f'<div style="text-align:right;">'
                f'<div style="font-family:DM Mono,monospace;font-size:0.8em;'
                f'color:{tc_body};font-variant-numeric:tabular-nums;">{_lp_str}</div>'
                f'<div style="font-family:DM Mono,monospace;font-size:0.65em;color:{_lp_c};">{_lp_sub}</div>'
                f'</div>'
                f'</div>'
            )

        with st.container(border=True):
            st.markdown(
                f'<div style="padding:4px 0;">{_lp_rows}'
                f'<div style="padding-top:6px;">'
                f'<span style="font-family:DM Mono,monospace;font-size:0.58em;color:{tc_label};">'
                f'⏱ {last_update_time}</span>'
                f'</div></div>',
                unsafe_allow_html=True
            )

        # SMH Gate 상태
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown(_zone_label("SMH Gate"), unsafe_allow_html=True)

        _smh_items = [
            ("SMH > 50MA",       smh_c1, f"${smh_close:.2f}"),
            ("Momentum ≥ 10%",   smh_c2, f"{smh_1m*100:.1f}%"),
            ("RSI > 50",         smh_c3, f"{smh_rsi:.1f}"),
        ]
        _smh_passed = sum(1 for _, ok, _ in _smh_items if ok)
        _smh_top    = main_color if smh_cond else "#9494A0"
        _smh_label  = "SOXL APPROVED" if smh_cond else "USD DEFENSE"

        _smh_rows = ""
        for _sl, _sok, _sv in _smh_items:
            _sc = main_color if _sok else "#9494A0"
            _si = "●" if _sok else "○"
            _smh_rows += (
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:6px 0;border-bottom:1px solid rgba(0,0,0,0.05);">'
                f'<div style="display:flex;align-items:center;gap:6px;">'
                f'<span style="font-family:DM Mono,monospace;font-size:0.7em;color:{_sc};">{_si}</span>'
                f'<span style="font-family:DM Sans,sans-serif;font-size:0.78em;color:{tc_body};">{_sl}</span>'
                f'</div>'
                f'<span style="font-family:DM Mono,monospace;font-size:0.76em;'
                f'color:{_sc};font-weight:600;font-variant-numeric:tabular-nums;">{_sv}</span>'
                f'</div>'
            )

        with st.container(border=True):
            st.markdown(apply_theme(
                f'<div style="padding:2px 0;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid rgba(0,0,0,0.08);">'
                f'<span style="font-family:DM Mono,monospace;font-size:0.72em;'
                f'font-weight:600;color:{_smh_top};">{_smh_label}</span>'
                f'<span style="background:rgba({r_c},{g_c},{b_c},0.08);'
                f'border:1px solid rgba({r_c},{g_c},{b_c},0.22);color:{_smh_top};'
                f'font-family:DM Mono,monospace;font-size:0.6em;padding:2px 8px;">'
                f'{_smh_passed}/3</span>'
                f'</div>'
                f'{_smh_rows}'
                f'</div>'
            ), unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════
    # ZONE 3 — Rebalancing Matrix (전체 너비)
    # ══════════════════════════════════════════════════════════
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    st.markdown(apply_theme(
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">'
        f'<div style="width:3px;height:14px;background:{main_color};flex-shrink:0;"></div>'
        f'<span style="font-family:DM Mono,monospace;font-size:0.6em;font-weight:600;'
        f'color:{tc_heading};letter-spacing:0.2em;text-transform:uppercase;">'
        f'Rebalancing Matrix</span>'
        f'<div style="flex:1;height:1px;background:rgba(0,0,0,0.10);"></div>'
        f'<span style="font-family:DM Mono,monospace;font-size:0.57em;color:{tc_label};'
        f'letter-spacing:0.08em;white-space:nowrap;">'
        f'R{curr_regime}  ·  {regime_info[curr_regime][1]}  ·  ⏱ {last_update_time}</span>'
        f'</div>'
    ), unsafe_allow_html=True)

    if total_val_usd > 0:
        _rhtml = (
            '<div style="overflow-x:auto;">'
            '<table class="mint-table">'
            '<thead><tr>'
            '<th style="text-align:left;">Asset</th>'
            '<th>현재가</th>'
            '<th>평균단가</th>'
            '<th>수익률</th>'
            '<th>평가액 ($)</th>'
            '<th>목표 비중</th>'
            '<th>목표액 ($)</th>'
            '<th>Δ ($)</th>'
            '<th style="text-align:center;">Action</th>'
            '</tr></thead><tbody>'
        )
        for asset in ASSET_LIST:
            _shs  = st.session_state.portfolio[asset]['shares']
            _avgp = st.session_state.portfolio[asset]['avg_price']
            _curp = current_prices[asset] if current_prices[asset] > 0 else 1.0
            _curv = curr_vals[asset]
            _tgtw = target_weights.get(asset, 0.0)
            _tgtv = total_val_usd * _tgtw
            _diff = diff_vals[asset]

            if asset == 'CASH':
                _curp_str, _avgp_str, _ret, _retstr = "—", "—", 0.0, "—"
            else:
                _curp_str = f"${_curp:.2f}"
                _avgp_str = f"${_avgp:.2f}" if _avgp > 0 else "—"
                _ret      = (_curp / _avgp - 1) * 100 if _avgp > 0 else 0.0
                _retstr   = f"{_ret:+.1f}%"

            _retc    = C_GREEN if _ret >= 0 else C_RED
            _curw    = (_curv / total_val_usd * 100) if total_val_usd > 0 else 0

            if abs(_diff) < _curp * 0.05 and asset != 'CASH':
                _act, _dstr, _rbg = (
                    "<span style='font-family:DM Mono,monospace;font-size:0.74em;"
                    "color:#9494A0;letter-spacing:0.08em;'>HOLD</span>",
                    "<span style='color:#9494A0;'>—</span>",
                    "#FAFAF7"
                )
            elif abs(_diff) < 1.0 and asset == 'CASH':
                _act, _dstr, _rbg = (
                    "<span style='font-family:DM Mono,monospace;font-size:0.74em;"
                    "color:#9494A0;letter-spacing:0.08em;'>HOLD</span>",
                    "<span style='color:#9494A0;'>—</span>",
                    "#FAFAF7"
                )
            elif _diff > 0:
                _act = (f"<span style='font-family:DM Mono,monospace;font-size:0.72em;"
                        f"font-weight:700;color:#059669;letter-spacing:0.1em;"
                        f"background:rgba(5,150,105,0.09);padding:3px 10px;"
                        f"border-left:2px solid #059669;'>▲ BUY</span>")
                _dstr = f"<span style='color:#059669;font-weight:600;'>+${_diff:,.0f}</span>"
                _rbg  = "rgba(5,150,105,0.025)"
            else:
                _act = (f"<span style='font-family:DM Mono,monospace;font-size:0.72em;"
                        f"font-weight:700;color:#DC2626;letter-spacing:0.1em;"
                        f"background:rgba(220,38,38,0.08);padding:3px 10px;"
                        f"border-left:2px solid #DC2626;'>▼ SELL</span>")
                _dstr = f"<span style='color:#DC2626;font-weight:600;'>-${abs(_diff):,.0f}</span>"
                _rbg  = "rgba(220,38,38,0.025)"

            if _tgtw > 0 or _curv > 0 or _shs > 0:
                _rhtml += (
                    f'<tr style="background:{_rbg};">'
                    f'<td style="font-weight:700;color:#059669;font-family:DM Mono,monospace;font-size:0.85em;">{asset}</td>'
                    f'<td style="color:#4A4A57;">{_curp_str}</td>'
                    f'<td style="color:#6B6B7A;">{_avgp_str}</td>'
                    f'<td><span style="color:{_retc};font-weight:600;">{_retstr}</span></td>'
                    f'<td style="font-weight:500;">{_curv:,.0f}'
                    f'<span style="font-family:DM Mono,monospace;font-size:0.68em;color:#9494A0;'
                    f'margin-left:4px;">({_curw:.0f}%)</span></td>'
                    f'<td style="color:{main_color};font-weight:700;">{_tgtw*100:.0f}%</td>'
                    f'<td>{_tgtv:,.0f}</td>'
                    f'<td>{_dstr}</td>'
                    f'<td style="text-align:center;">{_act}</td>'
                    f'</tr>'
                )
        _rhtml += "</tbody></table></div>"
        with st.container(border=True):
            st.markdown(apply_theme(_rhtml), unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);'
            f'padding:32px;text-align:center;">'
            f'<span style="font-family:DM Mono,monospace;font-size:0.82em;color:#CCCCCC;">'
            f'포지션을 입력하면 리밸런싱 매트릭스가 표시됩니다.</span></div>',
            unsafe_allow_html=True
        )


# ──────────────────────────────────────────
elif page == "🍫 12-Pack Radar":

    df_view  = df.iloc[-120:]
    qqq_rsi  = last_row['QQQ_RSI']
    qqq_dd   = last_row['QQQ_DD']
    cnn_fgi  = fetch_fear_and_greed()
    if cnn_fgi is not None:
        fg_score = cnn_fgi
    else:
        vix_score = max(0, min(100, 100-(last_row['^VIX']-12)/28*100))
        dd_score  = max(0, min(100, (qqq_dd+0.20)/0.20*100))
        rsi_score = max(0, min(100, qqq_rsi))
        fg_score  = (vix_score+dd_score+rsi_score)/3

    sec_names = {'XLK':'TECH','XLV':'HEALTH','XLF':'FIN','XLY':'CONS','XLC':'COMM',
                 'XLI':'IND','XLP':'STAPLE','XLE':'ENGY','XLU':'UTIL','XLRE':'REAL','XLB':'MAT'}
    sec_data  = [{'섹터':sec_names[s],'수익률':last_row[f'{s}_1M']*100} for s in SECTOR_TICKERS]
    sec_df    = pd.DataFrame(sec_data).sort_values(by='수익률', ascending=True)
    top_sec, bot_sec = sec_df.iloc[-1]['섹터'], sec_df.iloc[0]['섹터']

    risk_cnt, warn_cnt, safe_cnt = 0, 0, 0
    if qqq_rsi < 40: safe_cnt+=1
    elif qqq_rsi > 70: warn_cnt+=1
    else: safe_cnt+=1
    if qqq_dd < -0.20: risk_cnt+=1
    elif qqq_dd < -0.10: warn_cnt+=1
    else: safe_cnt+=1
    if fg_score < 30: safe_cnt+=1
    elif fg_score > 70: warn_cnt+=1
    else: safe_cnt+=1
    if last_row['HYG_IEF_Ratio'] < last_row['HYG_IEF_MA50']: risk_cnt+=1
    else: safe_cnt+=1
    if (last_row['QQQ_20d_Ret']>0 and last_row['QQQE_20d_Ret']<0): warn_cnt+=1
    else: safe_cnt+=1
    if last_row['GLD_SPY_Ratio'] > last_row['GLD_SPY_MA50']: warn_cnt+=1
    else: safe_cnt+=1
    if last_row['UUP'] > last_row['UUP_MA50']: risk_cnt+=1
    else: safe_cnt+=1
    if last_row['^TNX'] > last_row['TNX_MA50']: warn_cnt+=1
    else: safe_cnt+=1
    if last_row['BTC-USD'] < last_row['BTC_MA50']: warn_cnt+=1
    else: safe_cnt+=1
    if last_row['IWM_SPY_Ratio'] < last_row['IWM_SPY_MA50']: warn_cnt+=1
    else: safe_cnt+=1
    if last_row['^VIX'] > last_row['VIX_MA50']: risk_cnt+=1
    else: safe_cnt+=1
    if top_sec not in ['UTIL', 'STAPLE', 'HEALTH']: safe_cnt+=1
    else: warn_cnt+=1

    if risk_cnt >= 3:
        radar_status = "극단적 위험 구간 (Risk-Off)"
        radar_msg    = "시장에 극단적인 공포가 덮쳤습니다. 현재 복수의 매크로 지표가 시스템 리스크를 강하게 경고하고 있습니다. 단순한 조정을 넘어선 투매 구간일 확률이 높으니, 모든 레버리지 포지션을 해제하고 현금과 달러, 금 등 안전 자산 비중을 최대로 늘려 폭풍우가 지나가기를 기다리셔야 합니다."
        radar_color  = "#DC2626"
    elif warn_cnt >= 4 or risk_cnt >= 1:
        radar_status = "변동성 주의 (Warning)"
        radar_msg    = "시장 곳곳에서 균열의 조짐이 감지되고 있습니다. 표면적인 지수는 버티고 있을지 몰라도 내부 자금 흐름이나 심리 지표가 점차 악화되고 있습니다. 신규 매수는 철저히 보류하시고, 포트폴리오의 리스크 노출도를 점검하며 보수적인 관망 자세를 유지하는 것이 좋습니다."
        radar_color  = "#D97706"
    else:
        radar_status = "안정적 순항 (Safe)"
        radar_msg    = "현재 글로벌 매크로 지표와 시장 심리가 모두 안정적인 궤도에 올라와 있습니다. 추세를 꺾을 만한 시스템 리스크가 보이지 않으니, AMLS 알고리즘이 제시하는 비중에 맞춰 자신감 있게 추세 추종 전략을 전개하시기 바랍니다."
        radar_color  = main_color

    total_signals = risk_cnt + warn_cnt + safe_cnt
    risk_pct  = int(risk_cnt  / total_signals * 100) if total_signals else 0
    warn_pct  = int(warn_cnt  / total_signals * 100) if total_signals else 0
    safe_pct  = int(safe_cnt  / total_signals * 100) if total_signals else 0

    st.markdown(apply_theme(
        f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);'
        f'border-left:3px solid {radar_color};padding:14px 20px;margin-bottom:12px;">'
        f'<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap;">'
        f'<div style="flex:3;min-width:260px;">'
        f'<div style="font-family:DM Mono,monospace;font-size:0.57em;color:#9494A0;'
        f'letter-spacing:0.18em;text-transform:uppercase;margin-bottom:4px;">Macro Signal Status</div>'
        f'<div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.2em;font-weight:700;letter-spacing:-0.3px;font-style:normal;coloric;'
        f'color:{radar_color};line-height:1.1;margin-bottom:8px;">{radar_status}</div>'
        f'<div style="font-family:DM Sans,sans-serif;font-size:0.82em;color:#4A4A57;line-height:1.6;">{radar_msg}</div>'
        f'</div>'
        f'<div style="flex:1;min-width:180px;">'
        f'<div style="display:flex;gap:6px;margin-bottom:8px;">'
        f'<div style="flex:1;border-top:2px solid #DC2626;padding:8px 6px;background:rgba(220,38,38,0.04);">'
        f'<div style="font-family:DM Mono,monospace;font-size:1.5em;color:#DC2626;line-height:1;">{risk_cnt}</div>'
        f'<div style="font-family:DM Mono,monospace;font-size:0.57em;color:#9494A0;letter-spacing:0.14em;text-transform:uppercase;">Risk</div>'
        f'</div>'
        f'<div style="flex:1;border-top:2px solid #D97706;padding:8px 6px;background:rgba(217,119,6,0.04);">'
        f'<div style="font-family:DM Mono,monospace;font-size:1.5em;color:#D97706;line-height:1;">{warn_cnt}</div>'
        f'<div style="font-family:DM Mono,monospace;font-size:0.57em;color:#9494A0;letter-spacing:0.14em;text-transform:uppercase;">Warn</div>'
        f'</div>'
        f'<div style="flex:1;border-top:2px solid {main_color};padding:8px 6px;background:rgba({r_c},{g_c},{b_c},0.04);">'
        f'<div style="font-family:DM Mono,monospace;font-size:1.5em;color:{main_color};line-height:1;">{safe_cnt}</div>'
        f'<div style="font-family:DM Mono,monospace;font-size:0.57em;color:#9494A0;letter-spacing:0.14em;text-transform:uppercase;">Safe</div>'
        f'</div>'
        f'</div>'
        f'<div style="height:4px;background:rgba(0,0,0,0.07);display:flex;overflow:hidden;">'
        f'<div style="width:{risk_pct}%;background:#DC2626;"></div>'
        f'<div style="width:{warn_pct}%;background:#D97706;"></div>'
        f'<div style="width:{safe_pct}%;background:{main_color};"></div>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;font-family:DM Mono,monospace;'
        f'font-size:0.58em;color:#9494A0;margin-top:3px;">'
        f'<span>{risk_pct}% risk</span><span>{warn_pct}% warn</span><span>{safe_pct}% safe</span></div>'
        f'</div>'
        f'</div></div>'
    ), unsafe_allow_html=True)

    def _badge(label, color, icon):
        p = {
            'green':  (f'rgba({r_c},{g_c},{b_c},0.10)', main_color),
            'orange': ('rgba(217,119,6,0.10)',           '#D97706'),
            'red':    ('rgba(220,38,38,0.10)',           '#DC2626'),
            'blue':   ('rgba(59,130,246,0.10)',          '#3B82F6')
        }
        bg, fg = p[color]
        return (f'<span style="background:{bg};color:{fg};border:1px solid {fg};'
                f'padding:2px 7px;font-size:0.68em;font-weight:500;'
                f'font-family:DM Mono,monospace;letter-spacing:0.05em;white-space:nowrap;">'
                f'{icon} {label}</span>')

    b1  = _badge("BUY","green","▲") if qqq_rsi<40 else (_badge("OVER","red","▼") if qqq_rsi>70 else _badge("NEUTRAL","blue","—"))
    b2  = _badge("BEAR−20%","red","▼") if qqq_dd<-0.20 else (_badge("CORR−10%","orange","▼") if qqq_dd<-0.10 else _badge("SAFE","green","▲"))
    b3  = _badge("FEAR","green","▲") if fg_score<30 else (_badge("GREED","red","▼") if fg_score>70 else _badge("NEUTRAL","blue","—"))
    b4  = f'<span style="background:rgba({r_c},{g_c},{b_c},0.10);color:{main_color};border:1px solid {main_color};padding:2px 7px;font-size:0.68em;font-family:DM Mono,monospace;">▲{top_sec}/▼{bot_sec}</span>'
    b5  = _badge("RISK OFF","red","▼") if last_row['HYG_IEF_Ratio']<last_row['HYG_IEF_MA50'] else _badge("RISK ON","green","▲")
    b6  = _badge("NARROW","orange","⚠") if (last_row['QQQ_20d_Ret']>0 and last_row['QQQE_20d_Ret']<0) else _badge("BROAD","green","▲")
    b7  = _badge("GOLD","orange","▲") if last_row['GLD_SPY_Ratio']>last_row['GLD_SPY_MA50'] else _badge("EQUITY","green","▲")
    b8  = _badge("USD STR","red","▼") if last_row['UUP']>last_row['UUP_MA50'] else _badge("USD WK","green","▲")
    b9  = _badge("YIELD↑","red","▼") if last_row['^TNX'] > last_row['TNX_MA50'] else _badge("YIELD↓","green","▲")
    b10 = _badge("RISK OFF","red","▼") if last_row['BTC-USD'] < last_row['BTC_MA50'] else _badge("RISK ON","green","▲")
    b11 = _badge("NARROW","orange","⚠") if last_row['IWM_SPY_Ratio'] < last_row['IWM_SPY_MA50'] else _badge("BROAD","green","▲")
    b12 = _badge("EXPAND","red","▼") if last_row['^VIX'] > last_row['VIX_MA50'] else _badge("SHRINK","green","▲")

    gauge_steps = [
        {'range':[0,25],  'color':"rgba(220,38,38,0.4)"},
        {'range':[25,45], 'color':"rgba(217,119,6,0.3)"},
        {'range':[45,55], 'color':"rgba(0,0,0,0.04)"},
        {'range':[55,75], 'color':f"rgba({r_c},{g_c},{b_c},0.3)"},
        {'range':[75,100],'color':f"rgba({r_c},{g_c},{b_c},0.5)"}
    ]

    desc1  = "나스닥 100(QQQ)의 단기 과열 및 침체를 나타내는 RSI 지표. 30↓ 투매→매수기회, 70↑ 과열→신규진입중단."
    desc2  = "QQQ 52주 고점 대비 하락률. -10% 건전한 조정, -20% 돌파시 약세장 진입으로 즉각 방어 필요."
    desc3  = "CNN Fear & Greed 지수. 극단적 공포 구간이 역사적 매수 기회, 극단적 탐욕 구간은 수익실현 시점."
    desc4  = "월간 섹터 자금흐름. 방어주(유틸/필수소비/헬스) 강세시 경기침체 대비 시그널."
    desc5  = "HYG/IEF 비율. 하이일드 채권이 국채 대비 약세면 스마트머니가 선제 이탈 중."
    desc6  = "QQQ(시총가중) vs QQQE(동일가중). 괴리 발생시 소수 대형주만 끌어올리는 가짜 상승 경고."
    desc7  = "GLD/SPY 비율. 금이 상대 강세면 기관의 Risk-Off 전환, 구조적 리스크 시그널."
    desc8  = "달러지수(UUP). 50일선 상향 돌파시 기술주 강한 하방압력, 주식비중 축소 정석."
    desc9  = "미 10년물 금리. 50일선 상향 돌파시 나스닥 성장주에 강한 역풍, 레버리지 주의."
    desc10 = "비트코인 트렌드. 50일선 하향시 글로벌 유동성 가뭄 선행 경고."
    desc11 = "IWM/SPY 비율. 중소형주 상대약세시 시장 내부 균열, TZA 전략 고려 가능."
    desc12 = "VIX 추세. 50일선 상향 돌파시 변동성 확장 국면 진입, 시스템 패닉 시그널."

    def r_head(num, title, badge, url, desc):
        return (
            f'<div style="border-bottom:1px solid rgba(0,0,0,0.08);padding-bottom:8px;margin-bottom:8px;">'
            f'<div style="display:flex;align-items:center;gap:4px;margin-bottom:4px;">'
            f'<span style="font-family:DM Mono,monospace;font-size:0.62em;color:#9494A0;'
            f'min-width:18px;">{num:02d}</span>'
            f'<a href="{url}" target="_blank" style="text-decoration:none;flex:1;">'
            f'<span style="font-family:DM Mono,monospace;font-size:0.66em;font-weight:500;'
            f'color:#2C2C35;letter-spacing:0.08em;text-transform:uppercase;">{title}&nbsp;↗</span>'
            f'</a>'
            f'{badge}'
            f'</div>'
            f'<div style="font-family:DM Sans,sans-serif;font-size:0.73em;color:#6B6B7A;'
            f'line-height:1.4;letter-spacing:-0.1px;">{desc}</div>'
            f'</div>'
        )

    u1  = "https://kr.tradingview.com/chart/?symbol=NASDAQ:QQQ"
    u2  = "https://kr.tradingview.com/chart/?symbol=NASDAQ:QQQ"
    u3  = "https://edition.cnn.com/markets/fear-and-greed"
    u4  = "https://finviz.com/map.ashx?t=sec"
    u5  = "https://fred.stlouisfed.org/series/BAMLH0A0HYM2"
    u6  = "https://kr.tradingview.com/chart/?symbol=NASDAQ:QQQE"
    u7  = "https://kr.tradingview.com/chart/?symbol=AMEX:GLD"
    u8  = "https://kr.tradingview.com/chart/?symbol=AMEX:UUP"
    u9  = "https://kr.tradingview.com/chart/?symbol=TVC:US10Y"
    u10 = "https://kr.tradingview.com/chart/?symbol=BINANCE:BTCUSD"
    u11 = "https://kr.tradingview.com/chart/?symbol=AMEX:IWM"
    u12 = "https://kr.tradingview.com/chart/?symbol=CBOE:VIX"

    row1 = st.columns(4)
    with row1[0]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(1, "DCA · RSI", b1, u1, desc1)), unsafe_allow_html=True)
            fig1=go.Figure()
            fig1.add_trace(go.Scatter(x=df_view.index, y=df_view['QQQ_RSI'], line=dict(color=line_c, width=1.8)))
            fig1.add_hline(y=70, line_dash='dot', line_color='#B0B0BE', line_width=1)
            fig1.add_hline(y=30, line_dash='dot', line_color=rsi_low_c, line_width=1)
            fig1.update_layout(**radar_layout, showlegend=False)
            fig1.update_xaxes(**_ax_r)
            fig1.update_yaxes(range=[10,90], **_ax_r)
            st.plotly_chart(fig1, use_container_width=True)
    with row1[1]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(2, "Drawdown", b2, u2, desc2)), unsafe_allow_html=True)
            fig2=go.Figure()
            fig2.add_trace(go.Scatter(x=df_view.index, y=df_view['QQQ_DD'], fill='tozeroy', fillcolor='rgba(220,38,38,0.07)', line=dict(color='#DC2626', width=1.8)))
            fig2.update_layout(**radar_layout, showlegend=False)
            fig2.update_xaxes(**_ax_r)
            fig2.update_yaxes(tickformat='.0%', **_ax_r)
            st.plotly_chart(fig2, use_container_width=True)
    with row1[2]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(3, "Fear & Greed", b3, u3, desc3)), unsafe_allow_html=True)
            fig3=go.Figure(go.Indicator(
                mode="gauge+number", value=fg_score, domain={'x':[0,1],'y':[0,1]},
                gauge={'axis':{'range':[0,100],'tickcolor':t_color},'bar':{'color':line_c,'thickness':0.2},'steps':gauge_steps,'borderwidth':0}
            ))
            fig3.update_layout(height=200, margin=dict(l=15,r=15,t=10,b=10), paper_bgcolor=b_color, font=dict(family="DM Mono", color=t_color))
            st.plotly_chart(fig3, use_container_width=True)
    with row1[3]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(4, "Sector 1M", b4, u4, desc4)), unsafe_allow_html=True)
            fig4=go.Figure(go.Bar(
                x=sec_df['수익률'], y=sec_df['섹터'], orientation='h',
                marker_color=[dash_c if v<0 else line_c for v in sec_df['수익률']],
                marker_line_width=0
            ))
            fig4.update_layout(**radar_layout, showlegend=False)
            fig4.update_xaxes(**_ax_r)
            fig4.update_yaxes(**_ax_r)
            st.plotly_chart(fig4, use_container_width=True)

    row2 = st.columns(4)
    with row2[0]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(5, "Credit Spread", b5, u5, desc5)), unsafe_allow_html=True)
            fig5=go.Figure()
            fig5.add_trace(go.Scatter(x=df_view.index, y=df_view['HYG_IEF_Ratio'], line=dict(color=line_c, width=1.8)))
            fig5.add_trace(go.Scatter(x=df_view.index, y=df_view['HYG_IEF_MA50'],  line=dict(color=dash_c, dash='dot', width=1.1)))
            fig5.update_layout(**radar_layout, showlegend=False)
            fig5.update_xaxes(**_ax_r); fig5.update_yaxes(**_ax_r)
            st.plotly_chart(fig5, use_container_width=True)
    with row2[1]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(6, "Mkt Breadth", b6, u6, desc6)), unsafe_allow_html=True)
            fig6=go.Figure()
            fig6.add_trace(go.Scatter(x=df_view.index, y=df_view['QQQ_20d_Ret'],  name='QQQ',  line=dict(color=line_c, width=1.8)))
            fig6.add_trace(go.Scatter(x=df_view.index, y=df_view['QQQE_20d_Ret'], name='QQQE', line=dict(color=dash_c, dash='dot', width=1.1)))
            fig6.update_layout(**radar_layout, showlegend=False)
            fig6.update_xaxes(**_ax_r)
            fig6.update_yaxes(tickformat='.0%', **_ax_r)
            st.plotly_chart(fig6, use_container_width=True)
    with row2[2]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(7, "Gold / Equity", b7, u7, desc7)), unsafe_allow_html=True)
            fig7=go.Figure()
            fig7.add_trace(go.Scatter(x=df_view.index, y=df_view['GLD_SPY_Ratio'], line=dict(color=line_c, width=1.8)))
            fig7.add_trace(go.Scatter(x=df_view.index, y=df_view['GLD_SPY_MA50'],  line=dict(color=dash_c, dash='dot', width=1.1)))
            fig7.update_layout(**radar_layout, showlegend=False)
            fig7.update_xaxes(**_ax_r); fig7.update_yaxes(**_ax_r)
            st.plotly_chart(fig7, use_container_width=True)
    with row2[3]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(8, "USD (UUP)", b8, u8, desc8)), unsafe_allow_html=True)
            fig8=go.Figure()
            fig8.add_trace(go.Scatter(x=df_view.index, y=df_view['UUP'],       line=dict(color=line_c, width=1.8)))
            fig8.add_trace(go.Scatter(x=df_view.index, y=df_view['UUP_MA50'],  line=dict(color=dash_c, dash='dot', width=1.1)))
            fig8.update_layout(**radar_layout, showlegend=False)
            fig8.update_xaxes(**_ax_r); fig8.update_yaxes(**_ax_r)
            st.plotly_chart(fig8, use_container_width=True)

    row3 = st.columns(4)
    with row3[0]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(9, "10Y Yield", b9, u9, desc9)), unsafe_allow_html=True)
            fig9=go.Figure()
            fig9.add_trace(go.Scatter(x=df_view.index, y=df_view['^TNX'],      line=dict(color=line_c, width=1.8)))
            fig9.add_trace(go.Scatter(x=df_view.index, y=df_view['TNX_MA50'],  line=dict(color=dash_c, dash='dot', width=1.1)))
            fig9.update_layout(**radar_layout, showlegend=False)
            fig9.update_xaxes(**_ax_r); fig9.update_yaxes(**_ax_r)
            st.plotly_chart(fig9, use_container_width=True)
    with row3[1]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(10, "Bitcoin", b10, u10, desc10)), unsafe_allow_html=True)
            fig10=go.Figure()
            fig10.add_trace(go.Scatter(x=df_view.index, y=df_view['BTC-USD'],  line=dict(color=line_c, width=1.8)))
            fig10.add_trace(go.Scatter(x=df_view.index, y=df_view['BTC_MA50'], line=dict(color=dash_c, dash='dot', width=1.1)))
            fig10.update_layout(**radar_layout, showlegend=False)
            fig10.update_xaxes(**_ax_r); fig10.update_yaxes(**_ax_r)
            st.plotly_chart(fig10, use_container_width=True)
    with row3[2]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(11, "Russell/SP500", b11, u11, desc11)), unsafe_allow_html=True)
            fig11=go.Figure()
            fig11.add_trace(go.Scatter(x=df_view.index, y=df_view['IWM_SPY_Ratio'], line=dict(color=line_c, width=1.8)))
            fig11.add_trace(go.Scatter(x=df_view.index, y=df_view['IWM_SPY_MA50'],  line=dict(color=dash_c, dash='dot', width=1.1)))
            fig11.update_layout(**radar_layout, showlegend=False)
            fig11.update_xaxes(**_ax_r); fig11.update_yaxes(**_ax_r)
            st.plotly_chart(fig11, use_container_width=True)
    with row3[3]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(12, "VIX Trend", b12, u12, desc12)), unsafe_allow_html=True)
            fig12=go.Figure()
            fig12.add_trace(go.Scatter(x=df_view.index, y=df_view['^VIX'],      line=dict(color=line_c, width=1.8)))
            fig12.add_trace(go.Scatter(x=df_view.index, y=df_view['VIX_MA50'],  line=dict(color=dash_c, dash='dot', width=1.1)))
            fig12.update_layout(**radar_layout, showlegend=False)
            fig12.update_xaxes(**_ax_r); fig12.update_yaxes(**_ax_r)
            st.plotly_chart(fig12, use_container_width=True)


elif page == "📈 Backtest Lab":
    st.markdown(apply_theme("""
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:20px;">
        <div>
            <h2 style="font-family:'Plus Jakarta Sans';font-size:1.7em;color:#0F172A;margin:0;">📈 Backtest Lab</h2>
            <div style="font-family:'DM Mono';font-size:0.65em;color:#4A5568;letter-spacing:0.16em;text-transform:uppercase;margin-top:3px;">Strategy Simulator  ·  Historical Analysis</div>
        </div>
    </div>"""), unsafe_allow_html=True)

    panel_cfg, panel_res = st.columns([1, 2.8])

    with panel_cfg:
        with st.container(border=True):
            st.markdown("""<div style="font-family:'DM Mono';font-size:0.62em;color:#4A5568;margin-bottom:14px;letter-spacing:0.2em;text-transform:uppercase;">⚙  Config</div>""", unsafe_allow_html=True)
            bt_start = st.date_input("Start Date", datetime(2020, 1, 1), key="bt_start_input")
            bt_end   = st.date_input("End Date",   datetime.today(),     key="bt_end_input")
            monthly_cont = st.number_input("월 적립금 ($)", value=2000, step=500, key="bt_monthly_input")

    with panel_res:
        with st.spinner("시뮬레이션 가동 중..."):
            bt_df = load_custom_backtest_data(bt_start, bt_end)

            if bt_df.empty:
                st.error("해당 기간의 데이터가 존재하지 않거나 부족합니다. 기간을 조정해주세요.")
            else:
                daily_ret = bt_df[['QQQ','TQQQ','SOXL','USD','QLD','SSO','SPY','SMH','GLD']].pct_change().fillna(0)
                w_orig = get_weights_v45(bt_df['Regime'].iloc[0], False)

                val_o, val_q, val_qld, val_tqqq = 10000, 10000, 10000, 10000
                hist_o, hist_q, hist_qld, hist_tqqq = [val_o], [val_q], [val_qld], [val_tqqq]
                invested = [10000]; curr_inv = 10000

                for i in range(1, len(bt_df)):
                    today     = bt_df.index[i]
                    yesterday = bt_df.index[i-1]
                    ret_o = sum(w_orig.get(t,0) * daily_ret[t].iloc[i] for t in w_orig if t in daily_ret.columns)
                    val_o *= (1 + ret_o); val_q *= (1 + daily_ret['QQQ'].iloc[i])
                    val_qld *= (1 + daily_ret['QLD'].iloc[i]); val_tqqq *= (1 + daily_ret['TQQQ'].iloc[i])
                    if today.month != yesterday.month:
                        val_o += monthly_cont; val_q += monthly_cont
                        val_qld += monthly_cont; val_tqqq += monthly_cont
                        curr_inv += monthly_cont
                    hist_o.append(val_o); hist_q.append(val_q)
                    hist_qld.append(val_qld); hist_tqqq.append(val_tqqq)
                    invested.append(curr_inv)
                    smh_cond_i = (bt_df['SMH'].iloc[i] > bt_df['SMH_MA50'].iloc[i]) and (bt_df['SMH_3M_Ret'].iloc[i] > 0.05) and (bt_df['SMH_RSI'].iloc[i] > 50)
                    w_orig = get_weights_v45(bt_df['Regime'].iloc[i], smh_cond_i)

                res_df = pd.DataFrame(index=bt_df.index)
                res_df['V4.5'], res_df['QQQ'], res_df['QLD'], res_df['TQQQ'] = hist_o, hist_q, hist_qld, hist_tqqq
                res_df['Invested'] = invested
                days = (res_df.index[-1] - res_df.index[0]).days

                def calc_metrics(series, inv_series):
                    final_val = series.iloc[-1]; total_inv = inv_series.iloc[-1]
                    ret  = (final_val / total_inv) - 1
                    cagr = (final_val / total_inv) ** (365.25 / days) - 1 if days > 0 else 0
                    mdd  = ((series / series.cummax()) - 1).min()
                    return ret, cagr, mdd

                ret_o, cagr_o, mdd_o       = calc_metrics(res_df['V4.5'], res_df['Invested'])
                ret_q, cagr_q, mdd_q       = calc_metrics(res_df['QQQ'],  res_df['Invested'])
                ret_qld, cagr_qld, mdd_qld = calc_metrics(res_df['QLD'],  res_df['Invested'])
                ret_t, cagr_t, mdd_t       = calc_metrics(res_df['TQQQ'], res_df['Invested'])

                mc1, mc2, mc3, mc4 = st.columns(4)

                def _mc_html(title, ret, cagr, mdd, is_main=False):
                    border_top = f"rgba({r_c},{g_c},{b_c},0.55)" if is_main else "rgba(0,0,0,0.12)"
                    bg        = f"rgba({r_c},{g_c},{b_c},0.06)" if is_main else "#FFFFFF"
                    tag_html  = (f'<span style="background:rgba({r_c},{g_c},{b_c},0.1);'
                                 f'color:{main_color};border-radius:5px;padding:2px 8px;'
                                 f'font-size:0.6em;font-family:DM Mono,monospace;'
                                 f'border:1px solid rgba({r_c},{g_c},{b_c},0.25);'
                                 f'letter-spacing:0.1em;">STRATEGY</span>') if is_main else ''
                    ret_c     = "#059669" if ret >= 0 else "#EF4444"
                    return (
                        f'<div style="background:{bg};border:1px solid rgba(0,0,0,0.08);'
                        f'border-top:2px solid {border_top};border-radius:14px;'
                        f'padding:16px 18px;box-shadow:0 2px 12px rgba(0,0,0,0.05);'
                        f'min-height:100px;">'
                        f'<div style="font-family:DM Mono,monospace;font-size:0.62em;'
                        f'color:#4A5568;letter-spacing:0.14em;text-transform:uppercase;'
                        f'margin-bottom:6px;">{title}&nbsp;&nbsp;{tag_html}</div>'
                        f'<div style="font-family:DM Mono,monospace;font-size:1.6em;'
                        f'font-weight:400;color:#0F172A;letter-spacing:-0.5px;'
                        f'margin-bottom:6px;">CAGR {cagr*100:.1f}%</div>'
                        f'<div style="font-family:DM Mono,monospace;font-size:0.72em;'
                        f'color:#4A5568;">'
                        f'누적&nbsp;<b style="color:{ret_c};">{ret*100:.1f}%</b>'
                        f'&nbsp;&nbsp;MDD&nbsp;<b style="color:#EF4444;">{mdd*100:.1f}%</b>'
                        f'</div></div>'
                    )

                with mc1: st.markdown(_mc_html("✦ AMLS V4.5", ret_o,   cagr_o,   mdd_o,   True), unsafe_allow_html=True)
                with mc2: st.markdown(_mc_html("QQQ",          ret_q,   cagr_q,   mdd_q),         unsafe_allow_html=True)
                with mc3: st.markdown(_mc_html("QLD",          ret_qld, cagr_qld, mdd_qld),        unsafe_allow_html=True)
                with mc4: st.markdown(_mc_html("TQQQ",         ret_t,   cagr_t,   mdd_t),          unsafe_allow_html=True)

                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                fig_eq = go.Figure()
                fig_eq.add_trace(go.Scatter(x=res_df.index, y=res_df['QQQ'],  name='QQQ',  line=dict(color='#CBD5E1', width=1.2, dash='dot')))
                fig_eq.add_trace(go.Scatter(x=res_df.index, y=res_df['QLD'],  name='QLD',  line=dict(color='#3B82F6', width=1.2, dash='dash')))
                fig_eq.add_trace(go.Scatter(x=res_df.index, y=res_df['TQQQ'], name='TQQQ', line=dict(color='#EF4444', width=1.2, dash='dash')))
                fig_eq.add_trace(go.Scatter(x=res_df.index, y=res_df['V4.5'], name='AMLS', line=dict(color=main_color, width=3)))
                fig_eq.update_layout(
                    title=dict(text="Equity Curve  ·  Log Scale", font=dict(family='DM Mono', size=13, color=t_color)),
                    height=380, yaxis_type='log', **chart_layout
                )
                fig_eq.update_xaxes(**_ax)
                fig_eq.update_yaxes(**_ax)
                with st.container(border=True):
                    st.plotly_chart(fig_eq, use_container_width=True)

                st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

                def get_dd_series(s): return (s / s.cummax()) - 1
                fig_dd = go.Figure()
                fig_dd.add_trace(go.Scatter(x=res_df.index, y=get_dd_series(res_df['QQQ']),  name='QQQ',  line=dict(color='#CBD5E1', width=1)))
                fig_dd.add_trace(go.Scatter(x=res_df.index, y=get_dd_series(res_df['QLD']),  name='QLD',  line=dict(color='#3B82F6', width=1)))
                fig_dd.add_trace(go.Scatter(x=res_df.index, y=get_dd_series(res_df['TQQQ']), name='TQQQ', line=dict(color='#EF4444', width=1)))
                fig_dd.add_trace(go.Scatter(x=res_df.index, y=get_dd_series(res_df['V4.5']), name='AMLS',
                                             fill='tozeroy', fillcolor=f'rgba({r_c},{g_c},{b_c},0.1)',
                                             line=dict(color=main_color, width=2.2)))
                fig_dd.update_layout(
                    title=dict(text="Drawdown Curve", font=dict(family='DM Mono', size=13, color=t_color)),
                    height=260, **chart_layout
                )
                fig_dd.update_xaxes(**_ax)
                fig_dd.update_yaxes(tickformat='.0%', **_ax)
                with st.container(border=True):
                    st.plotly_chart(fig_dd, use_container_width=True)

                st.divider()
            if st.button("✦ AI 추론 요약 실행", use_container_width=True):
                try:
                    import google.generativeai as genai
                    api_key = st.secrets["GEMINI_API_KEY"]
                    genai.configure(api_key=api_key)
                    models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    model  = genai.GenerativeModel(models[0].replace('models/',''))
                    prompt = f"""너는 최고 퀀트 애널리스트야. AMLS V4.5 전략 백테스트 결과를 분석해.
[AMLS] 누적수익률: {ret_o*100:.1f}%, CAGR: {cagr_o*100:.1f}%, MDD: {mdd_o*100:.1f}%
[TQQQ] 누적수익률: {ret_t*100:.1f}%, CAGR: {cagr_t*100:.1f}%, MDD: {mdd_t*100:.1f}%
AMLS 전략이 레버리지 MDD를 어떻게 회피하면서 수익을 냈는지 3단락으로 분석해."""
                    with st.spinner("AI 분석 중..."):
                        response = model.generate_content(prompt)
                        st.markdown(apply_theme(f"""<div class="glass-card" style="height:auto !important; padding:28px !important; color:#CBD5E1; font-weight:400; line-height:1.75; font-size:0.95em;">{response.text}</div>"""), unsafe_allow_html=True)
                except KeyError:
                    st.error("🚨 GEMINI_API_KEY 누락")

# ──────────────────────────────────────────
elif page == "📰 Macro News":
    headlines_for_ai, news_items = fetch_macro_news()

    st.markdown(apply_theme(f"""
    <div style="border-top:3px solid #111118;border-bottom:1px solid rgba(0,0,0,0.12);
        padding:18px 0 14px;margin-bottom:24px;">
        <div style="display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:10px;">
            <div>
                <div style="font-family:'DM Mono',monospace;font-size:0.6em;color:#9494A0;
                    letter-spacing:0.22em;text-transform:uppercase;margin-bottom:6px;">
                    Global Macro  ·  Wall Street Analysis Engine
                </div>
                <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:2.2em;
                    font-weight:800;color:{tc_heading};
                    letter-spacing:-1.5px;line-height:1;">
                    Market Briefing
                </div>
            </div>
            <div style="display:flex;align-items:center;gap:12px;padding-bottom:4px;">
                <div class="live-pulse" style="font-family:'DM Mono',monospace;font-size:0.65em;
                    color:#059669;padding:4px 12px;
                    background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);
                    letter-spacing:0.06em;">{rt_label}</div>
                <div style="font-family:'DM Mono',monospace;font-size:0.62em;color:#9494A0;
                    letter-spacing:0.05em;">{last_update_time}</div>
            </div>
        </div>
    </div>
    """), unsafe_allow_html=True)

    news_left, news_right = st.columns([1, 1.6])

    with news_left:
        st.markdown(
            f'<div style="font-family:DM Mono,monospace;font-size:0.6em;font-weight:500;'
            f'color:#6B6B7A;letter-spacing:0.2em;text-transform:uppercase;'
            f'padding-bottom:6px;border-bottom:2px solid #111118;margin-bottom:14px;">'
            f'AI  Analyst  ·  System-2 Reasoning</div>',
            unsafe_allow_html=True
        )

        if st.button("↻  심층 추론 요약 실행", use_container_width=True):
            try:
                import google.generativeai as genai
                api_key = st.secrets["GEMINI_API_KEY"]
                if not headlines_for_ai:
                    st.warning("분석할 뉴스가 없습니다.")
                else:
                    with st.spinner("AI 분석 중..."):
                        genai.configure(api_key=api_key)
                        models = [m.name for m in genai.list_models()
                                  if 'generateContent' in m.supported_generation_methods]
                        model  = genai.GenerativeModel(models[0].replace('models/',''))
                        prompt = ("너는 퀀트 애널리스트야. 다음 뉴스를 섹터별, 리스크 요소, "
                                  "최종 투자 스탠스로 나누어 3문단으로 요약해.\n"
                                  + "\n".join(headlines_for_ai))
                        response = model.generate_content(prompt)
                        st.markdown(
                            f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);'
                            f'border-left:3px solid {main_color};padding:20px 22px;'
                            f'margin-top:12px;">'
                            f'<div style="font-family:DM Mono,monospace;font-size:0.58em;'
                            f'color:#9494A0;letter-spacing:0.16em;text-transform:uppercase;'
                            f'margin-bottom:10px;">AI Summary</div>'
                            f'<div style="font-family:DM Sans,sans-serif;font-size:0.9em;'
                            f'color:{tc_body};line-height:1.75;">{response.text}</div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
            except KeyError:
                st.error("🚨 GEMINI_API_KEY 누락")
        else:
            st.markdown(
                f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);'
                f'border-left:3px solid rgba(0,0,0,0.15);padding:20px 22px;margin-top:12px;">'
                f'<div style="font-family:DM Mono,monospace;font-size:0.6em;color:#9494A0;'
                f'letter-spacing:0.14em;text-transform:uppercase;margin-bottom:10px;">How It Works</div>'
                f'<div style="font-family:DM Sans,sans-serif;font-size:0.85em;color:{tc_muted};'
                f'line-height:1.7;">'
                f'버튼을 누르면 Google Gemini AI가 최신 뉴스 헤드라인을<br>'
                f'<b style="color:{tc_body};">① 섹터별 분류</b> → '
                f'<b style="color:{tc_body};">② 리스크 요소 추출</b> → '
                f'<b style="color:{tc_body};">③ 최종 투자 스탠스</b><br>'
                f'3단계로 구조화해서 요약해 드립니다.'
                f'</div></div>',
                unsafe_allow_html=True
            )

        if news_items:
            st.markdown(
                f'<div style="margin-top:16px;padding:10px 14px;'
                f'background:rgba(0,0,0,0.03);border-left:2px solid rgba(0,0,0,0.15);">'
                f'<span style="font-family:DM Mono,monospace;font-size:0.7em;color:#9494A0;">'
                f'수집된 헤드라인  <b style="color:{tc_data};">{len(news_items)}건</b>'
                f'  ·  Google News RSS</span>'
                f'</div>',
                unsafe_allow_html=True
            )

    with news_right:
        st.markdown(
            f'<div style="font-family:DM Mono,monospace;font-size:0.6em;font-weight:500;'
            f'color:#6B6B7A;letter-spacing:0.2em;text-transform:uppercase;'
            f'padding-bottom:6px;border-bottom:2px solid #111118;margin-bottom:14px;">'
            f'Latest Headlines  ·  {len(news_items) if news_items else 0} items</div>',
            unsafe_allow_html=True
        )

        if news_items:
            for idx, item in enumerate(news_items):
                _num_color  = main_color if idx < 3 else "#9494A0"
                _top_border = f"2px solid {main_color}" if idx == 0 else "1px solid rgba(0,0,0,0.10)"
                st.markdown(
                    f'<div style="display:flex;gap:14px;padding:12px 0;'
                    f'border-bottom:1px solid rgba(0,0,0,0.07);'
                    f'border-top:{_top_border if idx == 0 else "none"};">'
                    f'<div style="font-family:DM Mono,monospace;font-size:0.75em;'
                    f'color:{_num_color};font-weight:600;min-width:22px;'
                    f'padding-top:2px;font-variant-numeric:tabular-nums;">'
                    f'{idx+1:02d}</div>'
                    f'<div style="flex:1;">'
                    f'<a href="{item["link"]}" target="_blank" style="text-decoration:none;">'
                    f'<div style="font-family:DM Sans,sans-serif;font-size:0.88em;'
                    f'color:{tc_body};line-height:1.5;font-weight:{"500" if idx < 3 else "400"};'
                    f'transition:color 0.15s;"'
                    f' onmouseover="this.style.color=\'{main_color}\'"'
                    f' onmouseout="this.style.color=\'{tc_body}\'">'
                    f'{item["title"]}'
                    f'</div>'
                    f'</a>'
                    f'<div style="font-family:DM Mono,monospace;font-size:0.65em;'
                    f'color:#9494A0;margin-top:4px;letter-spacing:0.04em;">'
                    f'{item["date"]}</div>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        else:
            st.markdown(
                f'<div style="padding:20px;background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);">'
                f'<span style="font-family:DM Mono,monospace;font-size:0.8em;color:#9494A0;">'
                f'뉴스를 불러올 수 없습니다. 잠시 후 다시 시도해주세요.</span></div>',
                unsafe_allow_html=True
            )
