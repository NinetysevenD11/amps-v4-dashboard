import streamlit as st
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
# 1. 앱 설정 및 세션 상태 초기화
# ==========================================
st.set_page_config(page_title="AMLS V4.5 FINANCE STRATEGY", layout="wide", page_icon="🌿", initial_sidebar_state="expanded")

if 'display_mode' not in st.session_state: st.session_state.display_mode  = 'PC'
if 'lc_lr_split'  not in st.session_state: st.session_state.lc_lr_split   = 38
if 'lc_delta_wt'  not in st.session_state: st.session_state.lc_delta_wt   = 52
if 'lc_editor_h'  not in st.session_state: st.session_state.lc_editor_h   = 355
if 'lc_goal_inp'  not in st.session_state: st.session_state.lc_goal_inp   = 22
if 'lc_pie_h'     not in st.session_state: st.session_state.lc_pie_h      = 200
if 'lc_pie_split' not in st.session_state: st.session_state.lc_pie_split  = 50
if 'lc_bar_h'     not in st.session_state: st.session_state.lc_bar_h      = 185
if 'lc_show_lp'   not in st.session_state: st.session_state.lc_show_lp    = True
if 'lc_show_qo'   not in st.session_state: st.session_state.lc_show_qo    = True
if 'lc_show_reg'  not in st.session_state: st.session_state.lc_show_reg   = True
if 'main_color'   not in st.session_state: st.session_state.main_color   = '#10B981'
if 'bg_color'     not in st.session_state: st.session_state.bg_color     = '#F7F6F2'
if 'tc_heading'   not in st.session_state: st.session_state.tc_heading   = '#111118'
if 'tc_body'      not in st.session_state: st.session_state.tc_body      = '#2D2D2D'
if 'tc_muted'     not in st.session_state: st.session_state.tc_muted     = '#6B6B7A'
if 'tc_label'     not in st.session_state: st.session_state.tc_label     = '#9494A0'
if 'tc_data'      not in st.session_state: st.session_state.tc_data      = '#111118'
if 'tc_sidebar'   not in st.session_state: st.session_state.tc_sidebar   = '#2D2D2D'
if '_ls_loaded'   not in st.session_state: st.session_state._ls_loaded   = False

if 'rebal_locked' not in st.session_state: st.session_state.rebal_locked = False
if 'rebal_plan'   not in st.session_state: st.session_state.rebal_plan   = None

# ==========================================
# 2. 로컬 스토리지 & 포트폴리오 관리 (기본 함수)
# ==========================================
def _ls_save_all():
    _layout = json.dumps({"display_mode": st.session_state.display_mode, "lc_lr_split": st.session_state.lc_lr_split, "lc_delta_wt": st.session_state.lc_delta_wt, "lc_editor_h": st.session_state.lc_editor_h, "lc_goal_inp": st.session_state.lc_goal_inp, "lc_pie_h": st.session_state.lc_pie_h, "lc_pie_split": st.session_state.lc_pie_split, "lc_bar_h": st.session_state.lc_bar_h, "lc_show_lp": st.session_state.lc_show_lp, "lc_show_qo": st.session_state.lc_show_qo, "lc_show_reg": st.session_state.lc_show_reg})
    _theme = json.dumps({"main_color": st.session_state.main_color, "bg_color": st.session_state.bg_color, "tc_heading": st.session_state.tc_heading, "tc_body": st.session_state.tc_body, "tc_muted": st.session_state.tc_muted, "tc_label": st.session_state.tc_label, "tc_data": st.session_state.tc_data, "tc_sidebar": st.session_state.tc_sidebar})
    _pf = json.dumps(st.session_state.portfolio)
    _goal = str(st.session_state.goal_usd)
    _dm = st.session_state.display_mode
    def _esc(s): return s.replace("\\", "\\\\").replace("`", "\\`")
    st.markdown(f"""<script>(function(){{try{{var p={{amls_portfolio:`{_esc(_pf)}`,amls_goal:`{_esc(_goal)}`,amls_layout:`{_esc(_layout)}`,amls_theme:`{_esc(_theme)}`,amls_dispmode:`{_esc(_dm)}`}};Object.keys(p).forEach(function(k){{localStorage.setItem(k,p[k]);}});}}catch(e){{}}}} )();</script>""", unsafe_allow_html=True)

def _ls_load():
    if st.session_state._ls_loaded: return
    st.markdown("""<script>(function(){var keys=["amls_portfolio","amls_goal","amls_layout","amls_theme","amls_dispmode"];var changed=false;var params=new URLSearchParams(window.location.search);keys.forEach(function(k){var v=localStorage.getItem(k);if(v&&!params.has(k)){params.set(k,encodeURIComponent(v));changed=true;}});if(changed){var newUrl=window.location.pathname+"?"+params.toString();window.history.replaceState(null,"",newUrl);window.location.reload();}})();</script>""", unsafe_allow_html=True)
    st.session_state._ls_loaded = True

SECTOR_TICKERS = ['XLK','XLV','XLF','XLY','XLC','XLI','XLP','XLE','XLU','XLRE','XLB']
CORE_TICKERS   = ['QQQ','TQQQ','SOXL','USD','QLD','SSO','SPYG','SMH','GLD','^VIX','HYG','IEF','QQQE','UUP','^TNX','BTC-USD','IWM']
TICKERS        = CORE_TICKERS + SECTOR_TICKERS
ASSET_LIST     = ['TQQQ','SOXL','USD','QLD','SSO','SPYG','QQQ','GLD','CASH']
PORTFOLIO_FILE = 'portfolio_autosave.json'

def _restore_from_qp():
    _qp, _changed = st.query_params.to_dict(), False
    if "amls_portfolio" in _qp:
        try:
            _pf = json.loads(_qp["amls_portfolio"])
            if 'portfolio' not in st.session_state or not any(st.session_state.portfolio[a]['shares'] for a in ASSET_LIST if a != 'CASH'):
                for k, v in _pf.items():
                    if k == 'SPY': st.session_state.portfolio['SPYG'] = v
                    elif k in ASSET_LIST: st.session_state.portfolio[k] = v
                _changed = True
        except: pass
    if "amls_goal" in _qp:
        try:
            _g = float(_qp["amls_goal"])
            if st.session_state.goal_usd == 100000.0: st.session_state.goal_usd = _g; _changed = True
        except: pass
    if "amls_layout" in _qp:
        try:
            _lay = json.loads(_qp["amls_layout"])
            _lc_defaults = {"display_mode":"PC", "lc_lr_split":38, "lc_delta_wt":52, "lc_editor_h":355, "lc_goal_inp":22, "lc_pie_h":200, "lc_pie_split":50, "lc_bar_h":185, "lc_show_lp":True, "lc_show_qo":True, "lc_show_reg":True}
            for _k, _dv in _lc_defaults.items():
                if _k in _lay:
                    _cur, _new = getattr(st.session_state, _k), _lay[_k]
                    if isinstance(_dv, bool): _new = bool(_new)
                    elif isinstance(_dv, int): _new = int(_new)
                    if _cur == _dv and _cur != _new: setattr(st.session_state, _k, _new); _changed = True
        except: pass
    if "amls_theme" in _qp:
        try:
            _th = json.loads(_qp["amls_theme"])
            _defaults = {"main_color":"#10B981", "bg_color":"#F7F6F2", "tc_heading":"#111118", "tc_body":"#2D2D2D", "tc_muted":"#6B6B7A", "tc_label":"#9494A0", "tc_data":"#111118", "tc_sidebar":"#2D2D2D"}
            for _k in _defaults:
                if _k in _th and getattr(st.session_state, _k) == _defaults.get(_k): setattr(st.session_state, _k, _th[_k]); _changed = True
        except: pass
    if "amls_dispmode" in _qp:
        _dm = _qp["amls_dispmode"]
        if _dm in ("PC","Tablet","Mobile") and st.session_state.display_mode == "PC": st.session_state.display_mode = _dm
    if any(k in _qp for k in ["amls_portfolio","amls_goal","amls_layout","amls_theme","amls_dispmode"]):
        for _k in ["amls_portfolio","amls_goal","amls_layout","amls_theme","amls_dispmode"]:
            if _k in st.query_params: del st.query_params[_k]
        if _changed: st.rerun()

_restore_from_qp()

main_color, bg_color, tc_heading, tc_body = st.session_state.main_color, st.session_state.bg_color, st.session_state.tc_heading, st.session_state.tc_body
tc_muted, tc_label, tc_data, tc_sidebar = st.session_state.tc_muted, st.session_state.tc_label, st.session_state.tc_data, st.session_state.tc_sidebar

def hex_to_rgb(hex_col): h = hex_col.lstrip('#'); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
r_c, g_c, b_c = hex_to_rgb(main_color)

def apply_theme(text):
    if not isinstance(text, str): return text
    return text.replace("#10B981", main_color).replace("#10b981", main_color).replace("16, 185, 129", f"{r_c}, {g_c}, {b_c}").replace("16,185,129", f"{r_c},{g_c},{b_c}")

def sanitize_portfolio():
    for a in ASSET_LIST:
        val = st.session_state.portfolio.get(a)
        if isinstance(val, (int, float)) or val is None: st.session_state.portfolio[a] = {'shares': float(val or 0.0), 'avg_price': 1.0 if a == 'CASH' else 0.0}
        elif isinstance(val, dict):
            if 'shares' not in val: val['shares'] = 0.0
            if 'avg_price' not in val: val['avg_price'] = 1.0 if a == 'CASH' else 0.0
        else: st.session_state.portfolio[a] = {'shares': 0.0, 'avg_price': 0.0}

if 'goal_usd' not in st.session_state: st.session_state.goal_usd = 100000.0
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {asset: {'shares':0.0, 'avg_price':0.0} for asset in ASSET_LIST}
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                loaded = json.load(f)
                for k, v in loaded.items():
                    if k == 'SPY': st.session_state.portfolio['SPYG'] = v
                    elif k in ASSET_LIST: st.session_state.portfolio[k] = v
        except: pass

sanitize_portfolio()

def save_portfolio_to_disk():
    try:
        with open(PORTFOLIO_FILE, 'w') as f: json.dump(st.session_state.portfolio, f)
    except: pass
    st.session_state['_needs_ls_save'] = True


# ==========================================
# 3. 데이터 로딩 및 전략 엔진 (먼저 실행)
# ==========================================
@st.cache_data(ttl=3600, show_spinner=False)
def load_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=900)
    for attempt in range(3):
        try:
            data = yf.download(TICKERS, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)['Close']
            if data.empty: continue
            if 'QQQ' in data.columns: data = data.dropna(subset=['QQQ'])
            df = pd.DataFrame(index=data.index)
            for t in TICKERS:
                if t in data.columns: df[t] = data[t]
            df = df.ffill().bfill()
            df['QQQ_MA20'] = df['QQQ'].rolling(20).mean()
            df['QQQ_MA50'] = df['QQQ'].rolling(50).mean()
            df['QQQ_MA200'] = df['QQQ'].rolling(200).mean()
            df['TQQQ_MA200'] = df['TQQQ'].rolling(200).mean()
            df['SMH_MA50'] = df['SMH'].rolling(50).mean()
            df['VIX_MA5'] = df['^VIX'].rolling(5).mean()
            df['VIX_MA20'] = df['^VIX'].rolling(20).mean()
            df['VIX_MA50'] = df['^VIX'].rolling(50).mean()
            df['SMH_3M_Ret'] = df['SMH'].pct_change(63)
            df['SMH_1M_Ret'] = df['SMH'].pct_change(21)
            df['SMH_RSI'] = ta.rsi(df['SMH'], length=14)
            df['HYG_IEF_Ratio'] = df['HYG'] / df['IEF']
            df['HYG_IEF_MA20'] = df['HYG_IEF_Ratio'].rolling(20).mean()
            df['HYG_IEF_MA50'] = df['HYG_IEF_Ratio'].rolling(50).mean()
            df['QQQ_20d_Ret'] = df['QQQ'].pct_change(20)
            df['QQQE_20d_Ret'] = df['QQQE'].pct_change(20)
            df['QQQ_RSI'] = ta.rsi(df['QQQ'], length=14)
            df['GLD_SPYG_Ratio'] = df['GLD'] / df['SPYG']
            df['GLD_SPYG_MA50'] = df['GLD_SPYG_Ratio'].rolling(50).mean()
            df['QQQ_High52'] = df['QQQ'].rolling(252).max()
            df['QQQ_DD'] = (df['QQQ'] / df['QQQ_High52']) - 1
            df['UUP_MA50'] = df['UUP'].rolling(50).mean()
            df['TNX_MA50'] = df['^TNX'].rolling(50).mean()
            df['BTC_MA50'] = df['BTC-USD'].rolling(50).mean()
            df['IWM_SPYG_Ratio'] = df['IWM'] / df['SPYG']
            df['IWM_SPYG_MA50'] = df['IWM_SPYG_Ratio'].rolling(50).mean()
            for sec in SECTOR_TICKERS: df[f'{sec}_1M'] = df[sec].pct_change(21)
            result = df.dropna()
            if not result.empty: return result
        except: import time; time.sleep(1)
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
        if t > hist_curr:  
            hist_curr = t; pend = None; cnt = 0
        elif t < hist_curr:
            if hist_curr == 3 and t <= 2:
                hist_curr = 2
                if t == 1: pend = 1; cnt = 1  
                else: pend = None; cnt = 0
            else:
                if t == pend:
                    cnt += 1
                    if cnt >= 5: hist_curr = t; pend = None; cnt = 0
                else: pend = t; cnt = 1
        else: pend = None; cnt = 0
        res.append(hist_curr)
    return pd.Series(res, index=targets.index).shift(1).bfill()

@st.cache_data(ttl=15)
def fetch_realtime_prices():
    prices = {}
    now_kst = datetime.now(timezone.utc) + timedelta(hours=9)
    try:
        batch_data = yf.download(REALTIME_TICKERS, period="2d", interval="1m", prepost=True, progress=False, auto_adjust=True, threads=True)['Close']
        if isinstance(batch_data, pd.Series): batch_data = batch_data.to_frame(name=REALTIME_TICKERS[0])
        if not batch_data.empty:
            batch_data = batch_data.ffill()
            latest_row = batch_data.iloc[-1]
            for ticker in REALTIME_TICKERS:
                if ticker in latest_row.index and pd.notna(latest_row[ticker]):
                    val = float(latest_row[ticker])
                    if val > 0: prices[ticker] = val
    except Exception: pass
    missing_tickers = [t for t in REALTIME_TICKERS if t not in prices]
    if missing_tickers:
        for ticker in missing_tickers:
            try:
                info = yf.Ticker(ticker).fast_info
                price = info.get('last_price') or info.get('lastPrice')
                if price and price > 0: prices[ticker] = float(price)
            except: pass
    return prices, now_kst.strftime("%Y-%m-%d %H:%M:%S")

@st.cache_data(ttl=1800)
def fetch_fear_and_greed():
    try:
        url = "https://production.api.cnn.io/data/ext/fear_and_greed/latest"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
        return float(json.loads(urllib.request.urlopen(req, timeout=5).read().decode('utf-8'))['fear_and_greed']['score'])
    except: return None

@st.cache_data(ttl=900)
def fetch_macro_news():
    headlines_for_ai, news_items = [], []
    try:
        q = urllib.parse.quote("미국증시 OR 연준 OR 나스닥 OR 금리")
        url  = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
        root = ET.fromstring(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})).read())
        for item in root.findall('.//item')[:12]:
            t, l, d = item.find('title').text, item.find('link').text, item.find('pubDate').text
            headlines_for_ai.append(t); news_items.append({"title":t,"link":l,"date":d[:-4]})
    except: pass
    return headlines_for_ai, news_items

@st.cache_data(ttl=300)
def fetch_global_markets():
    gt = {'SPYG':'S&P 500 Growth','QQQ':'Nasdaq 100','DIA':'Dow Jones','IWM':'Russell 2000','EWJ':'Japan','EWT':'Taiwan','EWY':'Korea','FXI':'China','VGK':'Europe','EWG':'Germany','EWU':'UK','EWQ':'France','EWC':'Canada','EEM':'Emg Mkt','EWZ':'Brazil','EWA':'Australia'}
    at = {'^TNX':'US 10Y','GLD':'Gold','SLV':'Silver','USO':'Oil','BTC-USD':'Bitcoin','ETH-USD':'Ethereum','UUP':'DXY'}
    lt = {'AAPL':'Apple','MSFT':'Microsoft','NVDA':'Nvidia','AMZN':'Amazon','GOOGL':'Alphabet','META':'Meta','TSLA':'Tesla','AVGO':'Broadcom','AMD':'AMD','TSM':'TSMC'}
    all_t = list(gt.keys()) + list(at.keys()) + list(lt.keys())
    results = {}
    try:
        end = datetime.now()
        raw = yf.download(all_t, start=(end - timedelta(days=5)).strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'), progress=False, auto_adjust=True)['Close']
        if isinstance(raw, pd.Series): raw = raw.to_frame(name=all_t[0])
        for t in all_t:
            if t in raw.columns:
                s = raw[t].dropna()
                if len(s) >= 2: results[t] = {'price': float(s.iloc[-1]), 'chg': float((s.iloc[-1] / s.iloc[-2] - 1) * 100)}
                elif len(s) == 1: results[t] = {'price': float(s.iloc[-1]), 'chg': 0.0}
    except: pass
    return results, gt, at, lt

@st.cache_data(ttl=3600)
def load_custom_backtest_data(start_date, end_date):
    fetch_start = pd.to_datetime(start_date) - timedelta(days=400)
    data = yf.download(TICKERS, start=fetch_start.strftime("%Y-%m-%d"), end=(pd.to_datetime(end_date) + timedelta(days=1)).strftime("%Y-%m-%d"), progress=False, auto_adjust=True)['Close']
    if 'QQQ' in data.columns: data = data.dropna(subset=['QQQ'])
    bt_df = pd.DataFrame(index=data.index)
    for t in TICKERS: bt_df[t] = data[t]
    bt_df = bt_df.ffill().bfill()
    bt_df['QQQ_MA20'] = bt_df['QQQ'].rolling(20).mean()
    bt_df['QQQ_MA50'] = bt_df['QQQ'].rolling(50).mean()
    bt_df['QQQ_MA200'] = bt_df['QQQ'].rolling(200).mean()
    bt_df['TQQQ_MA200'] = bt_df['TQQQ'].rolling(200).mean()
    bt_df['SMH_MA50'] = bt_df['SMH'].rolling(50).mean()
    bt_df['VIX_MA5'] = bt_df['^VIX'].rolling(5).mean()
    bt_df['VIX_MA20'] = bt_df['^VIX'].rolling(20).mean()
    bt_df['VIX_MA50'] = bt_df['^VIX'].rolling(50).mean()
    bt_df['SMH_3M_Ret'] = bt_df['SMH'].pct_change(63)
    bt_df['SMH_1M_Ret'] = bt_df['SMH'].pct_change(21)
    bt_df['SMH_RSI'] = ta.rsi(bt_df['SMH'], length=14)
    bt_df['HYG_IEF_Ratio'] = bt_df['HYG'] / bt_df['IEF']
    bt_df['HYG_IEF_MA20'] = bt_df['HYG_IEF_Ratio'].rolling(20).mean()
    bt_df['HYG_IEF_MA50'] = bt_df['HYG_IEF_Ratio'].rolling(50).mean()
    bt_df['QQQ_20d_Ret'] = bt_df['QQQ'].pct_change(20)
    bt_df['QQQE_20d_Ret'] = bt_df['QQQE'].pct_change(20)
    bt_df['QQQ_RSI'] = ta.rsi(bt_df['QQQ'], length=14)
    bt_df['GLD_SPYG_Ratio'] = bt_df['GLD'] / bt_df['SPYG']
    bt_df['GLD_SPYG_MA50'] = bt_df['GLD_SPYG_Ratio'].rolling(50).mean()
    bt_df['QQQ_High52'] = bt_df['QQQ'].rolling(252).max()
    bt_df['QQQ_DD'] = (bt_df['QQQ'] / bt_df['QQQ_High52']) - 1
    bt_df['UUP_MA50'] = bt_df['UUP'].rolling(50).mean()
    bt_df['TNX_MA50'] = bt_df['^TNX'].rolling(50).mean()
    bt_df['BTC_MA50'] = bt_df['BTC-USD'].rolling(50).mean()
    bt_df['IWM_SPYG_Ratio'] = bt_df['IWM'] / bt_df['SPYG']
    bt_df['IWM_SPYG_MA50'] = bt_df['IWM_SPYG_Ratio'].rolling(50).mean()
    bt_df = bt_df.dropna()
    if bt_df.empty: return bt_df
    bt_df['Target'] = bt_df.apply(get_target_v45, axis=1)
    bt_df['Regime'] = apply_asymmetric_delay(bt_df['Target'])
    bt_df = bt_df.loc[pd.to_datetime(start_date):pd.to_datetime(end_date)]
    return bt_df

# === 데이터 로드 및 핵심 변수 계산 실행 ===
with st.spinner('데이터 수집 중...'):
    df = load_data()
    if df is not None and not df.empty: st.session_state['_df_cache'] = df
    elif '_df_cache' in st.session_state: df = st.session_state['_df_cache']
    rt_prices, last_update_time = fetch_realtime_prices()

if df is None or df.empty: st.error("야후 파이낸스 연결 실패"); st.stop()

last_index = df.index[-1]
rt_injected = []
for ticker, price in rt_prices.items():
    if ticker in df.columns and price > 0: df.at[last_index, ticker] = price; rt_injected.append(ticker)

if 'QQQ' in rt_injected: df.at[last_index, 'QQQ_DD'] = (df.at[last_index, 'QQQ'] / df['QQQ_High52'].iloc[-1]) - 1
if 'HYG' in rt_injected and 'IEF' in rt_injected: df.at[last_index, 'HYG_IEF_Ratio'] = df.at[last_index, 'HYG'] / df.at[last_index, 'IEF']
if 'IWM' in rt_injected and 'SPYG' in rt_injected: df.at[last_index, 'IWM_SPYG_Ratio'] = df.at[last_index, 'IWM'] / df.at[last_index, 'SPYG']
if 'GLD' in rt_injected and 'SPYG' in rt_injected: df.at[last_index, 'GLD_SPYG_Ratio'] = df.at[last_index, 'GLD'] / df.at[last_index, 'SPYG']

last_row = df.iloc[-1].copy()
rt_ok, rt_label = len(rt_injected) >= 3, f"⬤ LIVE {len(rt_injected)} feeds" if len(rt_injected) >= 3 else "⬤ DELAYED"
vix_close, vix_ma20 = last_row['^VIX'], last_row['VIX_MA20']
qqq_close, qqq_ma50, qqq_ma200 = last_row['QQQ'], last_row['QQQ_MA50'], last_row['QQQ_MA200']
smh_close, smh_ma50, smh_3m, smh_1m, smh_rsi = last_row['SMH'], last_row['SMH_MA50'], last_row['SMH_3M_Ret'], last_row['SMH_1M_Ret'], last_row['SMH_RSI']

df['Target'] = df.apply(get_target_v45, axis=1)
df['Regime'] = apply_asymmetric_delay(df['Target'])
live_regime, hist_regime = get_target_v45(last_row), int(df.iloc[-1]['Regime'])

if live_regime > hist_regime: curr_regime = live_regime
elif hist_regime == 3 and live_regime <= 2: curr_regime = 2
else: curr_regime = hist_regime

smh_cond = (smh_close > smh_ma50) and (smh_3m > 0.05 or smh_1m > 0.10) and (smh_rsi > 50)
def get_weights_v45(reg, smh_ok):
    w = {t: 0.0 for t in ASSET_LIST}; semi = 'SOXL' if smh_ok else 'USD'
    if reg == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'], w['SPYG'] = 0.30, 0.20, 0.20, 0.15, 0.10, 0.05
    elif reg == 2: w['TQQQ'], w['QLD'], w['SSO'], w['USD'], w['GLD'], w['SPYG'] = 0.15, 0.30, 0.25, 0.10, 0.15, 0.05
    elif reg == 3: w['GLD'], w['CASH'], w['QQQ'] = 0.50, 0.35, 0.15
    elif reg == 4: w['GLD'], w['CASH'], w['QQQ'] = 0.50, 0.40, 0.10
    return w
target_weights = get_weights_v45(curr_regime, smh_cond)

if curr_regime == live_regime: regime_committee_msg = "🟢 조건 부합 (안정)"
elif live_regime > curr_regime: regime_committee_msg = f"🔴 R{live_regime} 방어 즉시 반영"
elif hist_regime == 3 and live_regime == 1 and curr_regime == 2: regime_committee_msg = "🟡 R2 1차 회복 · R1 승급 대기 (5일)"
else: regime_committee_msg = f"🟡 R{live_regime} 승급 대기 (5일)"

regime_info = {1:("R1 BULL","풀 가동"),2:("R2 CORR","방어 진입"), 3:("R3 BEAR","대피"),4:("R4 PANIC","최대 방어")}

# ==========================================
# 4. 테마 및 CSS 스타일 적용
# ==========================================
b_color, t_color, line_c, dash_c, rsi_low_c = 'rgba(0,0,0,0)', '#4A4A57', main_color, '#B0B0BE', main_color
chart_layout = dict(paper_bgcolor=b_color, plot_bgcolor=b_color, font=dict(family="DM Mono, DM Sans, monospace", color=t_color), margin=dict(l=0, r=0, t=40, b=0))
radar_layout = dict(height=200, margin=dict(l=10, r=10, t=15, b=15), paper_bgcolor=b_color, plot_bgcolor=b_color, font=dict(family="DM Mono, DM Sans, monospace", color=t_color))
_ax, _ax_r = dict(gridcolor='rgba(0,0,0,0.07)', linecolor='rgba(0,0,0,0.12)', showgrid=True, zeroline=False), dict(gridcolor='rgba(0,0,0,0.07)', zeroline=False, showgrid=True)

css_block = f"""<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&display=swap');
    :root {{ --paper:{bg_color}; --paper-2:{bg_color}dd; --paper-3:{bg_color}bb; --ink:{tc_heading}; --ink-2:{tc_body}; --ink-3:{tc_body}; --ink-4:{tc_muted}; --ink-5:{tc_label}; --rule:rgba(0,0,0,0.10); --rule-strong:rgba(0,0,0,0.18); --acc:#10B981; --acc-pale:rgba(16,185,129,0.08); --acc-mid:rgba(16,185,129,0.18); --acc-line:rgba(16,185,129,0.40); --bull:#059669; --bear:#DC2626; --warn:#D97706; --u:8px; }}
    *,*::before,*::after {{ box-sizing:border-box; }}
    .stApp,[data-testid="stAppViewContainer"] {{ background-color:{bg_color} !important; background-image:radial-gradient(circle, rgba(0,0,0,0.055) 1px, transparent 1px), radial-gradient(ellipse 70% 40% at 5% 0%, rgba(16,185,129,0.055) 0%, transparent 55%) !important; background-size:24px 24px, 100% 100% !important; color:{tc_body} !important; font-family:'Plus Jakarta Sans', sans-serif; font-size:14px; }}
    [data-testid="stHeader"] {{ background:rgba(247,246,242,0.92) !important; backdrop-filter:blur(12px); border-bottom:1px solid var(--rule-strong); }}
    #MainMenu {{ visibility:hidden; }} footer {{ visibility:hidden; }}
    .main .block-container {{ max-width:1540px; padding-top:1.5rem; padding-bottom:3rem; }}
    [data-testid="stSidebar"] {{ background:{bg_color} !important; border-right:1px solid var(--rule-strong) !important; box-shadow:none !important; }}
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] div {{ color:{tc_sidebar}; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-baseweb="radio"] > div:first-child {{ display:none !important; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {{ gap:0px !important; padding:0 !important; background:transparent !important; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-baseweb="radio"] {{ display:flex !important; align-items:center !important; padding:11px 20px !important; margin:0 !important; border-radius:0 !important; border:none !important; border-bottom:1px solid var(--rule) !important; background:transparent !important; cursor:pointer !important; width:100% !important; transition:background 0.15s ease !important; position:relative; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-baseweb="radio"] p {{ color:{tc_sidebar} !important; font-weight:400 !important; font-size:0.84rem !important; margin:0 !important; font-family:'DM Sans' !important; letter-spacing:0.01em !important; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-baseweb="radio"]:hover {{ background:var(--paper-3) !important; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) {{ background:var(--acc-pale) !important; border-bottom:1px solid var(--rule) !important; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked)::before {{ content:''; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--acc); }}
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) p {{ color:{tc_heading} !important; font-weight:600 !important; }}
    .sidebar-link {{ display:flex; align-items:center; gap:10px; padding:9px 20px; margin:0; border-bottom:1px solid var(--rule); text-decoration:none !important; color:{tc_sidebar} !important; font-weight:400; font-size:0.82rem; transition:background 0.15s, color 0.15s; background:transparent; font-family:'DM Sans'; position:relative; }}
    .sidebar-link:hover {{ background:var(--paper-3) !important; color:{tc_heading} !important; }}
    [data-testid="stSidebar"] [data-testid="stButton"] > button {{ background:transparent !important; border:1px solid var(--rule-strong) !important; color:{tc_sidebar} !important; border-radius:0 !important; padding:7px 14px !important; font-weight:400 !important; font-size:0.76em !important; transition:all 0.15s ease !important; font-family:'DM Mono', monospace !important; letter-spacing:0.05em; text-transform:uppercase; }}
    [data-testid="stSidebar"] [data-testid="stButton"] > button:hover {{ background:var(--acc-pale) !important; border-color:var(--acc-line) !important; color:var(--bull) !important; }}
    [data-testid="stSidebar"] [data-testid="stSlider"] label p {{ color:{tc_label} !important; font-family:'DM Mono', monospace !important; font-size:0.72em !important; }}
    [data-testid="stSidebar"] [data-testid="stCheckbox"] label p {{ color:{tc_body} !important; font-size:0.78em !important; }}
    [data-testid="stSidebar"] [data-testid="stDownloadButton"] > button {{ background:transparent !important; border:1px solid var(--rule-strong) !important; color:{tc_sidebar} !important; border-radius:0 !important; font-family:'DM Mono', monospace !important; font-size:0.74em !important; padding:7px 14px !important; text-transform:uppercase; letter-spacing:0.05em; }}
    [data-testid="stSidebar"] [data-testid="stDownloadButton"] > button:hover {{ background:var(--acc-pale) !important; border-color:var(--acc-line) !important; color:var(--bull) !important; }}
    [data-testid="stSidebar"] [data-testid="stFileUploader"] {{ background:var(--paper-2) !important; border:1px dashed var(--rule-strong) !important; border-radius:0 !important; }}
    [data-testid="stSidebar"] [data-testid="stExpander"] {{ background:transparent !important; border:none !important; border-top:1px solid var(--rule) !important; border-radius:0 !important; }}
    [data-testid="stSidebar"] [data-testid="stExpander"] summary p {{ color:{tc_label} !important; font-family:'DM Mono', monospace !important; font-size:0.74em !important; letter-spacing:0.12em; text-transform:uppercase; }}
    [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {{ background:var(--paper-3) !important; }}
    .sb-section {{ padding:10px 20px 6px; font-family:'DM Mono', monospace; font-size:0.58em; font-weight:500; color:{tc_label}; letter-spacing:0.22em; text-transform:uppercase; border-top:1px solid var(--rule); margin-top:2px; }}
    .sb-section:first-child {{ border-top:none; }}
    .glass-card {{ background:#FAFAF7 !important; border:1px solid var(--rule-strong) !important; border-top:2px solid var(--ink-2) !important; border-radius:0 !important; padding:20px 22px !important; box-shadow:none !important; height:100%; display:flex; flex-direction:column; justify-content:space-between; transition:border-top-color 0.2s ease; position:relative; }}
    .glass-card:hover {{ border-top-color:var(--acc) !important; transform:none !important; box-shadow:0 4px 24px rgba(0,0,0,0.06) !important; }}
    .glass-card h3 {{ font-family:'DM Mono', monospace !important; font-size:0.6em !important; font-weight:400 !important; color:var(--ink-4) !important; margin-bottom:14px !important; letter-spacing:0.20em; text-transform:uppercase; border-bottom:1px solid var(--rule); padding-bottom:9px; }}
    .glass-inset {{ background:var(--paper-2) !important; border:1px solid var(--rule) !important; border-left:3px solid var(--acc) !important; border-radius:0 !important; padding:14px 16px 12px !important; text-align:left; margin-bottom:14px; box-shadow:none !important; }}
    div[data-testid="stVerticalBlockBorderWrapper"] > div {{ background:#FAFAF7 !important; border:1px solid var(--rule-strong) !important; border-top:2px solid var(--ink-2) !important; border-radius:0 !important; padding:20px 22px !important; box-shadow:none !important; transition:border-top-color 0.2s ease; position:relative; }}
    div[data-testid="stVerticalBlockBorderWrapper"] > div:hover {{ border-top-color:var(--acc) !important; box-shadow:0 4px 24px rgba(0,0,0,0.06) !important; transform:none !important; }}
    [data-testid="stMetric"] {{ background:#FAFAF7 !important; border:1px solid var(--rule-strong) !important; border-top:2px solid var(--ink-2) !important; border-radius:0 !important; padding:16px 18px !important; box-shadow:none !important; margin-bottom:8px; transition:border-top-color 0.2s; position:relative; }}
    [data-testid="stMetric"]:hover {{ border-top-color:var(--acc) !important; transform:none !important; }}
    [data-testid="stMetricLabel"] > div > div > p {{ font-size:0.65em !important; font-weight:500; color:var(--ink-4) !important; white-space:normal !important; letter-spacing:0.14em; text-transform:uppercase; font-family:'DM Mono', monospace !important; }}
    [data-testid="stMetricValue"] > div {{ font-family:'DM Mono', monospace !important; font-size:1.4em !important; font-weight:400; color:var(--ink) !important; font-variant-numeric:tabular-nums; }}
    div[data-testid="stMetricDelta"] > div {{ font-size:0.8em !important; font-weight:500; font-family:'DM Mono', monospace !important; font-variant-numeric:tabular-nums; }}
    [data-testid="stButton"] > button {{ background:transparent !important; border:1px solid var(--rule-strong) !important; color:var(--ink-2) !important; border-radius:0 !important; padding:7px 16px !important; font-weight:500 !important; font-size:0.78em !important; transition:all 0.15s ease !important; font-family:'DM Mono', monospace !important; letter-spacing:0.06em; text-transform:uppercase; }}
    [data-testid="stButton"] > button:hover {{ background:var(--acc-pale) !important; border-color:var(--acc-line) !important; color:var(--bull) !important; }}
    h1 {{ font-family:'Plus Jakarta Sans', sans-serif !important; font-size:2.2em !important; font-weight:800 !important; letter-spacing:-1.5px; margin:0 !important; color:{tc_heading} !important; }}
    h2 {{ font-family:'Plus Jakarta Sans', sans-serif !important; color:{tc_heading} !important; font-weight:800 !important; letter-spacing:-0.5px; }}
    h3 {{ font-family:'Plus Jakarta Sans', sans-serif !important; color:{tc_body} !important; }}
    p  {{ color:{tc_body} !important; line-height:1.65; }}
    strong {{ color:{tc_heading} !important; }}
    [data-testid="stMetricValue"], .cval, .mint-table td {{ font-variant-numeric:tabular-nums; }}
    .crow {{ display:flex; justify-content:space-between; align-items:center; padding:10px 0; border-bottom:1px solid var(--rule); font-size:0.9em; }}
    .crow:last-child {{ border-bottom:none; }}
    .clabel {{ color:{tc_muted}; font-weight:500; font-family:'DM Sans'; font-size:1em; }}
    .cval {{ font-family:'DM Mono', monospace; font-weight:400; color:#10B981; font-size:0.9em; letter-spacing:0.02em; font-variant-numeric:tabular-nums; }}
    [data-testid="stMetricLabel"] > div > div > p {{ font-size:0.65em !important; font-weight:500; color:{tc_label} !important; white-space:normal !important; letter-spacing:0.14em; text-transform:uppercase; font-family:'DM Mono', monospace !important; }}
    [data-testid="stMetricValue"] > div {{ font-family:'DM Mono', monospace !important; font-size:1.4em !important; font-weight:400; color:{tc_data} !important; font-variant-numeric:tabular-nums; }}
    [data-testid="stSidebar"] p {{ color:{tc_sidebar} !important; }}
    [data-testid="stSidebar"] strong {{ color:{tc_heading} !important; }}
    .radar-link {{ text-decoration:none !important; display:block; }}
    .radar-link-title {{ font-size:0.62em; font-weight:500; color:{tc_label}; transition:color 0.15s; font-family:'DM Mono', monospace; letter-spacing:0.16em; text-transform:uppercase; }}
    .radar-link:hover .radar-link-title {{ color:var(--acc) !important; }}
    .mint-table {{ width:100%; border-collapse:collapse; font-family:'DM Mono', monospace; }}
    .mint-table th {{ padding:8px 12px; font-weight:400; color:var(--ink-4); text-align:right; font-size:0.68em; letter-spacing:0.16em; text-transform:uppercase; border-bottom:2px solid var(--ink-3); background:var(--paper-2); }}
    .mint-table td {{ padding:10px 12px; background:#FAFAF7; color:var(--ink-2); text-align:right; border-bottom:1px solid var(--rule); font-size:0.8em; font-variant-numeric:tabular-nums; transition:background 0.12s; }}
    .mint-table tr:hover td {{ background:var(--acc-pale); }}
    .mint-table td:first-child {{ border-left:3px solid transparent; text-align:left; font-family:'DM Sans'; font-weight:700; color:var(--bull); font-size:0.82em; }}
    .mint-table tr:hover td:first-child {{ border-left-color:var(--acc); }}
    .mint-table th:first-child {{ text-align:left; }}
    [data-testid="stNumberInput"] > div > div, [data-testid="stTextInput"] > div > div, [data-testid="stDateInput"] > div > div, [data-baseweb="select"] > div {{ background:#FAFAF7 !important; border:1px solid var(--rule-strong) !important; border-radius:0 !important; color:var(--ink) !important; }}
    [data-testid="stFileUploader"] {{ background:var(--paper-2) !important; border:1px dashed var(--rule-strong) !important; border-radius:0 !important; }}
    [data-testid="stExpander"] {{ background:#FAFAF7 !important; border:1px solid var(--rule-strong) !important; border-radius:0 !important; }}
    hr {{ border-color:var(--rule-strong) !important; }}
    ::-webkit-scrollbar {{ width:3px; height:3px; }}
    ::-webkit-scrollbar-track {{ background:var(--paper-2); }}
    ::-webkit-scrollbar-thumb {{ background:var(--ink-5); }}
    ::-webkit-scrollbar-thumb:hover {{ background:var(--ink-3); }}
    @keyframes pulseGlow {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.7; }} }}
    .live-pulse {{ animation:pulseGlow 2.8s ease-in-out infinite; }}
    [data-testid="stDataEditor"], [data-testid="stDataFrame"] {{ border:1px solid var(--rule-strong) !important; border-radius:0 !important; }}
</style>"""
st.markdown(apply_theme(css_block), unsafe_allow_html=True)

# ==========================================
# 5. 사이드바 및 공통 헤더 렌더링
# ==========================================
st.sidebar.markdown(apply_theme(f"""<div style="padding:22px 20px 16px;background:{bg_color};border-bottom:1px solid rgba(0,0,0,0.09);"><div style="font-family:'DM Mono';font-size:0.52em;color:{tc_label};letter-spacing:0.26em;text-transform:uppercase;margin-bottom:8px;">Quantitative Engine</div><div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:1.65em;font-weight:800;color:{tc_heading};letter-spacing:-1px;line-height:1;margin-bottom:14px;">AMLS <span style="color:#10B981;">V4.5</span></div><div style="display:flex;align-items:center;justify-content:space-between;"><div class="live-pulse" style="display:inline-flex;align-items:center;gap:5px;font-family:'DM Mono';font-size:0.6em;color:#059669;padding:3px 10px;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);letter-spacing:0.06em;">{rt_label}</div><div style="font-family:'DM Mono';font-size:0.58em;color:{tc_label};letter-spacing:0.04em;">R{curr_regime} · {regime_info[curr_regime][1]}</div></div></div>"""), unsafe_allow_html=True)
st.sidebar.markdown('<div class="sb-section" style="border-top:none;">Navigation</div>', unsafe_allow_html=True)
page = st.sidebar.radio("MENU", ["📊 Dashboard", "💼 Portfolio", "🍫 12-Pack Radar", "📈 Backtest Lab", "📰 Macro News"], label_visibility="collapsed")
display_mode = st.session_state.display_mode

with st.sidebar.expander("🎨 Appearance", expanded=False):
    c1, c2 = st.columns(2)
    with c1: 
        nc = st.color_picker("Accent", st.session_state.main_color, key="cp_theme")
        if nc != st.session_state.main_color: st.session_state.main_color = nc; st.session_state['_needs_ls_save'] = True
    with c2:
        nbg = st.color_picker("BG", st.session_state.bg_color, key="cp_bg")
        if nbg != st.session_state.bg_color: st.session_state.bg_color = nbg; st.session_state['_needs_ls_save'] = True
    if st.button("↺ 초기화", use_container_width=True):
        for k, v in [("main_color","#10B981"),("bg_color","#F7F6F2"),("tc_heading","#111118"),("tc_body","#2D2D2D")]: setattr(st.session_state, k, v)
        st.session_state['_needs_ls_save'] = True; st.rerun()

with st.sidebar.expander("⚙️ Layout (PC)", expanded=False):
    v = st.slider("좌열 너비 %", 20, 60, st.session_state.lc_lr_split, key="sl_lr")
    if v != st.session_state.lc_lr_split: st.session_state.lc_lr_split = v; st.session_state['_needs_ls_save'] = True
    v = st.slider("Goal 입력창 %", 10, 40, st.session_state.lc_goal_inp, key="sl_gi")
    if v != st.session_state.lc_goal_inp: st.session_state.lc_goal_inp = v; st.session_state['_needs_ls_save'] = True

dmc1, dmc2, dmc3 = st.sidebar.columns(3)
for col, nm in [(dmc1,"PC"), (dmc2,"Tablet"), (dmc3,"Mobile")]:
    if col.button(nm, use_container_width=True): st.session_state.display_mode = nm; st.session_state['_needs_ls_save'] = True; st.rerun()

def _pill(label, value, color): return f'<div style="display:flex;flex-direction:column;align-items:center;padding:8px 18px;background:#FFFFFF;border:1px solid rgba(0,0,0,0.07);border-top:2px solid {color};border-radius:12px;min-width:90px;"><span style="font-family:\'DM Mono\';font-size:0.6em;color:#4A5568;letter-spacing:0.14em;text-transform:uppercase;">{label}</span><span style="font-family:\'DM Mono\';font-size:1.05em;font-weight:500;color:#0F172A;margin-top:2px;">{value}</span></div>'
_qqq_chg, _vix_now, _smh_chg = (last_row['QQQ']/last_row['QQQ_MA200']-1)*100, last_row['^VIX'], last_row['SMH_1M_Ret']*100
_p_qqq = _pill("QQQ/200MA", f"{_qqq_chg:+.1f}%", main_color if _qqq_chg >= 0 else "#EF4444")
_p_vix = _pill("VIX", f"{_vix_now:.1f}", main_color if _vix_now < 20 else "#EF4444")
_p_smh = _pill("SMH 1M", f"{_smh_chg:+.1f}%", main_color if _smh_chg >= 0 else "#EF4444")
_p_reg = _pill("REGIME", f"R{curr_regime}", main_color)

hdr_c1, hdr_c2 = st.columns([1, 1.6])
with hdr_c1: st.markdown(apply_theme(f"""<div style="display:flex;flex-direction:column;justify-content:center;"><div style="font-family:'Plus Jakarta Sans';font-size:2.5em;font-weight:800;letter-spacing:-2px;color:#0F172A;line-height:1;">AMLS <span style="color:#10B981;">V4.5</span></div><div style="font-family:'DM Mono';font-size:0.65em;color:#4A5568;letter-spacing:0.22em;text-transform:uppercase;margin-top:4px;">The Wall Street Quantitative Strategy</div></div>"""), unsafe_allow_html=True)
with hdr_c2:
    cs1, cs2 = st.columns([4, 1])
    with cs2: st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True); [fetch_realtime_prices.clear(), load_data.clear(), st.rerun()] if st.button("↺ 동기화", use_container_width=True) else None
    with cs1: st.markdown(apply_theme(f"""<div style="display:flex;flex-direction:column;align-items:flex-end;gap:8px;"><div style="display:flex;gap:6px;">{_p_qqq}{_p_vix}{_p_smh}{_p_reg}</div><div style="display:flex;align-items:center;gap:10px;"><div class="live-pulse" style="font-family:'DM Mono';font-size:0.68em;color:#059669;padding:4px 12px;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.3);border-radius:6px;letter-spacing:0.06em;">{rt_label}</div><div style="font-family:'DM Mono';font-size:0.68em;color:#4A5568;letter-spacing:0.04em;">⏱ {last_update_time}</div></div></div>"""), unsafe_allow_html=True)
st.markdown(apply_theme(f"""<div style="position:relative;margin:14px 0 24px;height:1px;background:rgba(0,0,0,0.07);"><div style="position:absolute;left:0;top:-1px;width:80px;height:3px;background:var(--acc);"></div></div>"""), unsafe_allow_html=True)

# ==========================================
# 6. 메인 페이지 라우팅 로직
# ==========================================
if page == "📊 Dashboard":
    def _lg_row(label, val, passed):
        icon, color = ("●", main_color) if passed else ("○", "#B0B0BE")
        val_str = f"${val:.2f}" if isinstance(val, (int, float)) and val > 5 else f"{val:.2f}" if isinstance(val, (int, float)) else str(val)
        return f'<div class="crow"><span class="clabel">{label}</span><span class="cval" style="color:{color};">{val_str}&nbsp;<span style="font-size:0.7em;">{icon}</span></span></div>'
    soxl_title, soxl_strat, soxl_color = ("SOXL APPROVED", "3× Leverage Active", main_color) if smh_cond else ("USD DEFENSE", "2× Defense Mode", "#9494A0")
    def _tick(label, val, sub, ok): return f'<div style="display:inline-flex;flex-direction:column;padding:0 20px;border-right:1px solid rgba(0,0,0,0.09);min-width:110px;"><span style="font-family:DM Mono,monospace;font-size:0.65em;color:#9494A0;letter-spacing:0.14em;text-transform:uppercase;">{label}</span><span style="font-family:DM Mono,monospace;font-size:1.05em;color:#111118;font-variant-numeric:tabular-nums;">{val}</span><span style="font-family:DM Mono,monospace;font-size:0.76em;color:{"#059669" if ok else "#DC2626"};\">{"▲" if ok else "▼"} {sub}</span></div>'
    
    tickers = _tick("QQQ", f"${last_row['QQQ']:.2f}", f"{_qqq_chg:+.2f}%", _qqq_chg>=0) + _tick("TQQQ", f"${last_row['TQQQ']:.2f}", f"{(last_row['TQQQ']/last_row['TQQQ_MA200']-1)*100:+.2f}%", last_row['TQQQ']>=last_row['TQQQ_MA200']) + _tick("VIX", f"{last_row['^VIX']:.2f}", f"MA20: {last_row['VIX_MA20']:.1f}", last_row['^VIX']<20) + _tick("SMH 1M", f"{last_row['SMH_1M_Ret']*100:+.1f}%", f"vs 50MA: {(last_row['SMH']/last_row['SMH_MA50']-1)*100:+.1f}%", last_row['SMH_1M_Ret']>=0) + _tick("SMH RSI", f"{last_row['SMH_RSI']:.1f}", "> 50 target", last_row['SMH_RSI']>50)
    st.markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);border-left:3px solid #111118;padding:12px 0 12px 18px;margin-bottom:14px;display:flex;align-items:center;overflow-x:auto;"><span style="font-family:DM Mono;font-size:0.65em;color:#9494A0;letter-spacing:0.18em;text-transform:uppercase;white-space:nowrap;padding-right:16px;border-right:1px solid rgba(0,0,0,0.09);">Live Feed</span>{tickers}<div style="margin-left:auto;padding:0 14px;white-space:nowrap;"><span class="live-pulse" style="font-family:DM Mono;font-size:0.6em;color:#059669;letter-spacing:0.06em;">{rt_label}</span></div></div>', unsafe_allow_html=True)
    
    lcol, rcol = st.columns([1, 2.4])
    with lcol:
        r_acc = {1:main_color, 2:"#D97706", 3:"#DC2626", 4:"#7C3AED"}[curr_regime]
        credit_check = last_row['HYG_IEF_Ratio'] >= last_row['HYG_IEF_MA20']
        st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);border-top:3px solid {r_acc};padding:20px 18px 16px;margin-bottom:10px;position:relative;overflow:hidden;"><div style="position:absolute;right:-4px;bottom:-16px;font-family:Plus Jakarta Sans;font-size:7em;font-weight:800;color:rgba(0,0,0,0.04);line-height:1;pointer-events:none;">{curr_regime}</div><div style="font-family:DM Mono;font-size:0.68em;color:#9494A0;letter-spacing:0.18em;text-transform:uppercase;margin-bottom:10px;">Market Regime</div><div style="font-family:Plus Jakarta Sans;font-size:2em;font-weight:800;color:{r_acc};line-height:1;margin-bottom:4px;">{regime_info[curr_regime][0]}</div><div style="font-family:DM Mono;font-size:0.72em;color:#6B6B7A;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:14px;">{regime_info[curr_regime][1]}</div>{_lg_row("VIX < 40", f"{vix_close:.2f}", vix_close<=40) + _lg_row(f"QQQ > 200MA [{qqq_ma200:.2f}]", f"${qqq_close:.2f}", qqq_close>=qqq_ma200) + _lg_row(f"50MA ≥ 200MA [{qqq_ma200:.2f}]", f"${qqq_ma50:.2f}", qqq_ma50>=qqq_ma200) + _lg_row("Credit Stress 방어", "안정" if credit_check else "경계", credit_check)}<div style="margin-top:8px;padding:6px 10px;background:rgba(16,185,129,0.07);border-left:2px solid {main_color};font-family:DM Mono;font-size:0.76em;color:#059669;">{regime_committee_msg}</div></div>'), unsafe_allow_html=True)
        st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);border-top:3px solid {soxl_color};padding:18px 18px 14px;margin-bottom:10px;"><div style="font-family:DM Mono;font-size:0.68em;color:#9494A0;letter-spacing:0.18em;text-transform:uppercase;margin-bottom:8px;">Semi-Conductor Gate</div><div style="font-family:Plus Jakarta Sans;font-size:1.6em;font-weight:400;color:{soxl_color};margin-bottom:4px;">{soxl_title}</div><div style="font-family:DM Mono;font-size:0.7em;color:#6B6B7A;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:12px;">{soxl_strat}</div>{_lg_row("SMH > 50MA", f"${smh_close:.2f}", smh_close > smh_ma50) + _lg_row("Momentum 1M >10%", f"{smh_1m*100:.1f}%", smh_3m > 0.05 or smh_1m > 0.10) + _lg_row("RSI > 50", f"{smh_rsi:.1f}", smh_rsi > 50)}</div>'), unsafe_allow_html=True)
        wrows = "".join([f'<div style="display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:1px solid rgba(0,0,0,0.05);"><span style="font-family:DM Mono;font-size:0.84em;color:#2C2C35;min-width:48px;">{k}</span><div style="flex:1;margin:0 9px;height:4px;background:rgba(0,0,0,0.07);overflow:hidden;"><div style="height:4px;width:{int(v*250)}%;background:{main_color};"></div></div><span style="font-family:DM Mono;font-size:0.84em;color:{main_color};font-variant-numeric:tabular-nums;min-width:36px;text-align:right;">{v*100:.0f}%</span></div>' for k, v in target_weights.items() if v > 0])
        st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);border-top:3px solid #111118;padding:18px 18px 14px;"><div style="font-family:DM Mono;font-size:0.68em;color:#9494A0;letter-spacing:0.18em;text-transform:uppercase;margin-bottom:12px;">Target Weights · R{curr_regime}</div>{wrows}</div>'), unsafe_allow_html=True)
    with rcol:
        r_clrs, tabs_html = {1:main_color, 2:"#D97706", 3:"#DC2626", 4:"#7C3AED"}, ""
        for r in [1,2,3,4]: tabs_html += f'<div style="padding:7px 16px;border:{"1px solid "+r_clrs[r] if r==curr_regime else "1px solid rgba(0,0,0,0.08)"};background:{r_clrs[r] if r==curr_regime else "transparent"};"><span style="font-family:DM Mono;font-size:0.76em;font-weight:500;color:{"#FFFFFF" if r==curr_regime else "#9494A0"};letter-spacing:0.05em;">{regime_info[r][0]}</span></div>'
        st.markdown(f'<div style="display:flex;gap:4px;margin-bottom:10px;align-items:center;">{tabs_html}<div style="margin-left:auto;font-family:DM Mono;font-size:0.7em;color:#9494A0;">⏱ {last_update_time}</div></div>', unsafe_allow_html=True)
        for t, m in [("QQQ","QQQ_MA200"),("TQQQ","TQQQ_MA200")]:
            fig = go.Figure(); fig.add_trace(go.Scatter(x=df.iloc[-500:].index, y=df.iloc[-500:][t], name=t, line=dict(color=line_c, width=2), fill='tozeroy', fillcolor=f'rgba({r_c},{g_c},{b_c},0.06)')); fig.add_trace(go.Scatter(x=df.iloc[-500:].index, y=df.iloc[-500:][m], name='200MA', line=dict(color=dash_c, width=1.2, dash='dot'))); fig.update_layout(title=dict(text=f"{t} / 200-Day Moving Average", font=dict(family='DM Mono', size=13)), height=330, **chart_layout, legend=dict(orientation='h', x=1, xanchor='right', y=1.1)); fig.update_xaxes(**_ax); fig.update_yaxes(**_ax); st.container(border=True).plotly_chart(fig, use_container_width=True)
    
    _gm, _gt, _at, _lt = fetch_global_markets()
    def _sec_label(txt): st.markdown(f'<div style="display:flex;align-items:center;gap:12px;margin:24px 0 14px;"><div style="font-family:Plus Jakarta Sans;font-size:1.1em;font-weight:700;">{txt}</div><div style="flex:1;height:1px;background:rgba(0,0,0,0.12);"></div></div>', unsafe_allow_html=True)

    _sec_label("① Nasdaq 100 Heatmap"); tlabels, tparents, tvalues, tcolors, ttext = ["Nasdaq 100"], [""], [0], [0], [""]
    qs = {'AAPL':('Technology','Apple'),'MSFT':('Technology','Microsoft'),'NVDA':('Technology','Nvidia'),'AVGO':('Technology','Broadcom'),'AMD':('Technology','AMD'),'INTC':('Technology','Intel'),'QCOM':('Technology','Qualcomm'),'TXN':('Technology','Texas Instr'),'ORCL':('Technology','Oracle'),'ADBE':('Technology','Adobe'),'CRM':('Technology','Salesforce'),'NOW':('Technology','ServiceNow'),'INTU':('Technology','Intuit'),'GOOGL':('Communication','Alphabet'),'META':('Communication','Meta'),'NFLX':('Communication','Netflix'),'AMZN':('Consumer','Amazon'),'TSLA':('Consumer','Tesla'),'BKNG':('Consumer','Booking'),'MCD':('Consumer',"McDonald's"),'COST':('Consumer','Costco'),'SBUX':('Consumer','Starbucks'),'PYPL':('Financials','PayPal'),'ISRG':('Healthcare','Intuitive Surg'),'GILD':('Healthcare','Gilead'),'AMGN':('Healthcare','Amgen'),'REGN':('Healthcare','Regeneron'),'HON':('Industrials','Honeywell'),'PEP':('Staples','PepsiCo')}
    s_set = {}
    for t, (s, n) in qs.items():
        if s not in s_set: s_set[s]=True; tlabels.append(s); tparents.append("Nasdaq 100"); tvalues.append(0); tcolors.append(0); ttext.append(s)
        d = _gm.get(t, {}); tlabels.append(t); tparents.append(s); tvalues.append(max(abs(d.get('price', 0.0)) * 0.1, 1)); tcolors.append(d.get('chg', 0.0)); ttext.append(f"{n}<br>{d.get('price',0.0):,.1f}<br>{d.get('chg',0.0):+.2f}%")
    tm_fig = go.Figure(go.Treemap(labels=tlabels, parents=tparents, values=tvalues, customdata=ttext, hovertemplate='%{customdata}<extra></extra>', texttemplate='<b>%{label}</b><br>%{customdata}', marker=dict(colors=tcolors, colorscale=[[0, '#DC2626'],[0.3, '#FCA5A5'],[0.5, '#F7F6F2'],[0.7, '#6EE7B7'],[1, '#059669']], cmid=0, cmin=-3, cmax=3, showscale=True), branchvalues='remainder'))
    tm_fig.update_layout(height=400, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)'); st.container(border=True).plotly_chart(tm_fig, use_container_width=True)
    
    _sec_label("② Assets & Leaders"); acols = st.columns(7)
    idict = {"^TNX":"📈","GLD":"🥇","SLV":"⚪","USO":"🛢","BTC-USD":"₿","ETH-USD":"Ξ","UUP":"💵"}
    for i, (t, n) in enumerate(_at.items()):
        d = _gm.get(t, {}); clr = "#059669" if d.get('chg',0)>=0 else "#DC2626"
        acols[i].markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.1);border-top:2px solid {clr};padding:12px 10px;text-align:center;"><div style="font-size:1.1em;">{idict.get(t,"")}</div><div style="font-size:0.6em;color:#9494A0;text-transform:uppercase;">{n}</div><div style="font-size:0.88em;color:#111118;">${d.get("price",0):,.2f}</div><div style="font-size:0.8em;color:{clr};font-weight:600;">{"▲" if d.get("chg",0)>=0 else "▼"} {d.get("chg",0):+.2f}%</div></div>', unsafe_allow_html=True)
    lcols = st.columns(5)
    for i, (t, n) in enumerate(sorted(_lt.items(), key=lambda x:_gm.get(x[0],{}).get('chg',0), reverse=True)):
        d = _gm.get(t, {}); clr = "#059669" if d.get('chg',0)>=0 else "#DC2626"
        lcols[i%5].markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.1);border-top:2px solid {clr};padding:12px 14px;margin-bottom:8px;"><div style="display:flex;justify-content:space-between;"><span style="font-size:0.62em;color:#9494A0;">{t}</span><span style="font-size:0.62em;font-weight:600;">#{i+1}</span></div><div style="font-size:0.82em;margin:3px 0;">{n}</div><div style="font-size:1.0em;color:#111118;">${d.get("price",0):,.2f}</div><div style="font-size:0.82em;color:{clr};font-weight:600;">{"▲" if d.get("chg",0)>=0 else "▼"} {d.get("chg",0):+.2f}%</div></div>', unsafe_allow_html=True)

# ==========================================
# 페이지 2: 💼 Portfolio
# ==========================================
elif page == "💼 Portfolio":
    cp = {t: (rt_prices.get(t, df[t].iloc[-1]) if t != 'CASH' else 1.0) for t in ASSET_LIST}
    fx = rt_prices.get('USDKRW=X', 1350.0); cvals = {a: st.session_state.portfolio[a]['shares'] * cp[a] for a in ASSET_LIST}
    tval_u, tcost_u = sum(cvals.values()), sum(st.session_state.portfolio[a]['shares'] * st.session_state.portfolio[a]['avg_price'] for a in ASSET_LIST if a != 'CASH')
    tval_k, pnl_u, pnl_p = tval_u * fx, tval_u - tcost_u, ((tval_u - tcost_u)/tcost_u*100 if tcost_u > 0 else 0.0)
    ldiff = {a: (tval_u * target_weights.get(a, 0.0)) - cvals[a] for a in ASSET_LIST} if tval_u > 0 else {a: 0.0 for a in ASSET_LIST}

    # 💡 Goal Tracker (원화 표기 포함)
    def _goal_tracker_html(total_val_krw):
        g_u, pct_r = st.session_state.goal_usd, (tval_u / st.session_state.goal_usd * 100) if st.session_state.goal_usd > 0 else 0.0
        pct = min(pct_r, 100.0); gc = "#059669" if pct_r > 100 else (main_color if pct >= 75 else ("#D97706" if pct >= 50 else "#94A3B8"))
        gr, gg, gb = hex_to_rgb(gc); seg = "".join([f'<div style="position:absolute;left:{m}%;top:0;bottom:-18px;width:1px;background:rgba(0,0,0,0.08);"><span style="position:absolute;top:calc(100% + 2px);left:50%;transform:translateX(-50%);font-family:DM Mono;font-size:0.5em;color:#BBBBBB;white-space:nowrap;">{m}%</span></div>' for m in [25, 50, 75, 100]])
        return apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.11);border-left:4px solid {gc};padding:10px 18px;display:flex;align-items:center;gap:18px;"><div style="display:flex;align-items:center;gap:8px;"><span style="font-family:DM Mono;font-size:0.56em;color:{tc_label};text-transform:uppercase;">Goal Tracker</span></div><div style="flex:1;position:relative;padding-bottom:18px;">{seg}<div style="height:8px;background:rgba(0,0,0,0.07);"><div style="height:8px;width:{pct:.2f}%;background:linear-gradient(90deg,rgba({gr},{gg},{gb},0.4),{gc});"></div></div></div><div style="display:flex;gap:20px;align-items:center;"><div style="text-align:center;"><div style="font-size:0.5em;color:{tc_label};text-transform:uppercase;">현재</div><div style="font-size:0.82em;color:{tc_body};">${tval_u:,.0f} / ₩{total_val_krw:,.0f}</div></div><div style="text-align:center;"><div style="font-size:0.5em;color:{tc_label};text-transform:uppercase;">목표</div><div style="font-size:0.82em;color:{tc_body};">${g_u:,.0f}</div></div><div style="text-align:right;padding-left:14px;border-left:1px solid rgba(0,0,0,0.08);"><span style="font-family:DM Mono;font-size:1.8em;color:{gc};line-height:1;">{pct_r:.1f}%</span></div></div></div>')

    def _pf_editor(height=355):
        edata = [{"Asset": a, "Shares": float(st.session_state.portfolio[a].get('shares', 0.0)), "Avg Price($)": float(st.session_state.portfolio[a].get('avg_price', 1.0 if a == 'CASH' else 0.0))} for a in ASSET_LIST]
        df_edited = st.data_editor(pd.DataFrame(edata), disabled=["Asset"], hide_index=True, use_container_width=True, height=height, column_config={"Shares": st.column_config.NumberColumn("Shares", format="%.4f"), "Avg Price($)": st.column_config.NumberColumn("Avg($)", format="%.2f")})
        if not df_edited.equals(pd.DataFrame(edata)):
            for _, row in df_edited.iterrows(): st.session_state.portfolio[row["Asset"]] = {'shares': float(row["Shares"]), 'avg_price': float(row["Avg Price($)"])}
            save_portfolio_to_disk(); st.session_state.rebal_locked=False; st.rerun()

    def generate_rebal_plan():
        s_diff = {a: (tval_u * target_weights.get(a, 0.0)) - cvals[a] for a in ASSET_LIST}; slist, blist, hlist = [], [], []
        for a in ASSET_LIST:
            if a == 'CASH': hlist.append(a); continue
            curp, diff = cp[a], s_diff[a]; sh = int(abs(diff)/curp)
            if diff < -(curp*0.05) and sh >= 1: slist.append((a, -(sh*curp), sh, curp))
            elif diff > (curp*0.05) and sh >= 1: blist.append((a, (sh*curp), sh, curp))
            elif cvals[a]>0 or target_weights.get(a,0)>0: hlist.append(a)
        st.session_state.rebal_plan = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "total": tval_u, "regime": curr_regime, "sells": slist, "buys": blist, "holds": hlist, "vals": cvals, "tgtw": target_weights}; st.session_state.rebal_locked = True

    def _rebalancing_matrix(is_mobile=False):
        if tval_u <= 0: st.markdown('<div style="background:#FAFAF7;padding:28px;text-align:center;color:#CCCCCC;">포지션을 입력하세요.</div>', unsafe_allow_html=True); return
        if not st.session_state.rebal_locked:
            st.markdown(apply_theme('<div style="background:rgba(217,119,6,0.08);border:1px solid rgba(217,119,6,0.3);padding:16px;text-align:center;margin-bottom:14px;"><div style="font-size:0.85em;color:#D97706;margin-bottom:10px;">지침 고정(Snapshot)이 필요합니다.</div></div>'), unsafe_allow_html=True)
            if st.button("📸 리밸런싱 지침 고정", use_container_width=True): generate_rebal_plan(); st.rerun()
            return
        p = st.session_state.rebal_plan; c1, c2 = st.columns([3, 1]); c1.markdown(apply_theme(f'<div style="background:rgba({r_c},{g_c},{b_c},0.07);border:1px solid rgba({r_c},{g_c},{b_c},0.22);padding:8px 14px;color:{main_color};font-size:0.62em;">✔ 고정됨 — {p["ts"]}</div>'), unsafe_allow_html=True)
        if c2.button("🔄 초기화", key=f"rp_{is_mobile}"): st.session_state.rebal_locked=False; st.session_state.rebal_plan=None; st.rerun()
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        t_sel = sum(abs(d) for a, d, s, c in p["sells"]); a_cash = t_sel + p["vals"].get('CASH', 0.0)
        
        if not is_mobile:
            e1, e2, e3 = st.columns([1, 0.12, 1])
            with e1:
                st.markdown('<div style="font-size:0.58em;font-weight:700;color:#DC2626;border-bottom:2px solid #DC2626;">STEP 1 · 매도</div>', unsafe_allow_html=True)
                rows = "".join([f'<tr><td style="font-weight:700;color:#059669;">{a}</td><td>${c:.2f}</td><td>{p["tgtw"].get(a,0)*100:.0f}%</td><td><span style="color:#DC2626;">-${abs(d):,.0f}</span></td><td><span style="color:#DC2626;font-weight:700;">{int(s):,.0f}주</span></td></tr>' for a, d, s, c in p["sells"]])
                if rows: st.markdown('<table class="mint-table"><thead><tr><th>Asset</th><th>가</th><th>목표</th><th>금액</th><th>수량</th></tr></thead><tbody>'+rows+'</tbody></table>', unsafe_allow_html=True)
                st.markdown(f'<div style="background:rgba(220,38,38,0.05);padding:8px 14px;margin-top:6px;font-size:0.62em;">가용 현금: ${a_cash:,.0f}</div>', unsafe_allow_html=True)
            with e2: st.markdown('<div style="display:flex;align-items:center;justify-content:center;height:120px;font-size:1.6em;color:#9494A0;">→</div>', unsafe_allow_html=True)
            with e3:
                st.markdown('<div style="font-size:0.58em;font-weight:700;color:#059669;border-bottom:2px solid #059669;">STEP 2 · 매수</div>', unsafe_allow_html=True); rem_c = a_cash; brows = ""
                for a, d, s, c in p["buys"]:
                    ash = int(min(s, rem_c/c)); abuy = ash * c; rem_c -= abuy; brows += f'<tr><td style="font-weight:700;color:#059669;">{a}</td><td>${c:.2f}</td><td>{p["tgtw"].get(a,0)*100:.0f}%</td><td><span style="color:#059669;">+${abuy:,.0f}</span></td><td><span style="color:#059669;font-weight:700;">{ash:,.0f}주</span></td></tr>'
                if brows: st.markdown('<table class="mint-table"><thead><tr><th>Asset</th><th>가</th><th>목표</th><th>금액</th><th>수량</th></tr></thead><tbody>'+brows+'</tbody></table>', unsafe_allow_html=True)
                st.markdown(f'<div style="background:rgba({r_c},{g_c},{b_c},0.06);padding:8px 14px;margin-top:6px;font-size:0.62em;">잔여 현금: ${max(rem_c,0):,.0f}</div>', unsafe_allow_html=True)
        else:
            for a, d, s, c in p["sells"]: st.markdown(f'<div style="background:rgba(220,38,38,0.035);border-left:3px solid #DC2626;padding:10px 14px;margin-bottom:5px;"><div style="display:flex;justify-content:space-between;"><span style="font-weight:700;">{a}</span><span style="color:#DC2626;font-weight:700;">▼ {int(s):,.0f}주 매도</span></div></div>', unsafe_allow_html=True)
            rem_c = a_cash
            for a, d, s, c in p["buys"]:
                ash = int(min(s, rem_c/c)); abuy = ash * c; rem_c -= abuy
                if ash >= 1: st.markdown(f'<div style="background:rgba(5,150,105,0.035);border-left:3px solid #059669;padding:10px 14px;margin-bottom:5px;"><div style="display:flex;justify-content:space-between;"><span style="font-weight:700;">{a}</span><span style="color:#059669;font-weight:700;">▲ {ash:,.0f}주 매수</span></div></div>', unsafe_allow_html=True)

    # 💡 P&L 및 화살표 출력 시 f-string 버그 해결됨
    def _kv(l, v, c, s=""): return f'<div style="display:flex;flex-direction:column;padding:0 20px;border-right:1px solid rgba(255,255,255,0.06);min-width:115px;"><span style="font-size:0.53em;color:rgba(255,255,255,0.35);text-transform:uppercase;">{l}</span><span style="font-size:1.0em;font-weight:500;color:{c};">{v}</span><span style="font-size:0.6em;color:rgba(255,255,255,0.3);">{s}</span></div>'
    _pnl_icon = '▲' if pnl_p >= 0 else '▼'
    st.markdown(apply_theme(f'<div style="background:#111118;border-left:4px solid {r_acc};padding:13px 0;margin-bottom:14px;display:flex;align-items:center;overflow-x:auto;"><div style="padding:0 20px 0 16px;border-right:1px solid rgba(255,255,255,0.06);"><div style="font-size:0.52em;color:rgba(255,255,255,0.3);text-transform:uppercase;">AMLS V4.5</div><div style="font-family:Plus Jakarta Sans;font-size:1.1em;font-weight:800;color:#FFFFFF;line-height:1;">Portfolio</div></div>{_kv("Total NAV", f"${tval_u:,.2f}", "#FFFFFF", f"₩{tval_k:,.0f}")}{_kv("USD/KRW", f"₩{fx:,.0f}", "rgba(255,255,255,0.65)", "환율")}{_kv("P&L", f"{pnl_p:+.2f}%", "#6EE7B7" if pnl_p>=0 else "#FCA5A5", f"{_pnl_icon} ${pnl_u:,.0f}")}{_kv("Regime", f"R{curr_regime}", r_acc)}<div style="margin-left:auto;padding:0 16px;"><span class="live-pulse" style="font-size:0.58em;color:#6EE7B7;">{rt_label}</span></div></div>'), unsafe_allow_html=True)

    if display_mode == "PC":
        g1, g2 = st.columns([st.session_state.lc_goal_inp, 100-st.session_state.lc_goal_inp])
        with g1:
            ng = st.number_input("목표($)", value=st.session_state.goal_usd, format="%.0f", key="goal_input", label_visibility="collapsed")
            if ng != st.session_state.goal_usd: st.session_state.goal_usd = ng; st.rerun()
        with g2: st.markdown(_goal_tracker_html(tval_k), unsafe_allow_html=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        cl, cr = st.columns([st.session_state.lc_lr_split, 100-st.session_state.lc_lr_split])
        with cl:
            with st.container(border=True): 
                st.markdown(apply_theme(f'<div style="border-bottom:1px solid rgba(0,0,0,0.09);padding-bottom:7px;margin-bottom:8px;font-size:0.58em;font-weight:600;text-transform:uppercase;">Position Input</div>'), unsafe_allow_html=True)
                _pf_editor(st.session_state.lc_editor_h)
        with cr:
            _pie_cfg = dict(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(family="DM Mono", color=t_color), showlegend=True, margin=dict(l=0, r=70, t=28, b=0), height=200)
            p1, p2 = st.columns(2)
            with p1:
                _fc = go.Figure(go.Pie(labels=[a for a in ASSET_LIST if cvals[a]>0], values=[cvals[a] for a in ASSET_LIST if cvals[a]>0], hole=.55, textinfo='percent', marker=dict(colors=[line_c,'#B0B0BE','#34D399','#6EE7B7','#A7F3D0','#059669','#047857','#065F46','#D1FAE5'], line=dict(color='#FAFAF7', width=1.5))))
                _fc.update_layout(title=dict(text="Current", font=dict(family="DM Mono", size=11), x=0), **_pie_cfg); st.container(border=True).plotly_chart(_fc, use_container_width=True)
            with p2:
                _ft = go.Figure(go.Pie(labels=[a for a in ASSET_LIST if target_weights.get(a,0)>0], values=[target_weights[a] for a in ASSET_LIST if target_weights.get(a,0)>0], hole=.55, textinfo='percent', marker=dict(colors=[line_c,'#B0B0BE','#34D399','#6EE7B7','#A7F3D0','#059669','#047857','#065F46','#D1FAE5'], line=dict(color='#FAFAF7', width=1.5))))
                _ft.update_layout(title=dict(text=f"Target R{curr_regime}", font=dict(family="DM Mono", size=11), x=0), **_pie_cfg); st.container(border=True).plotly_chart(_ft, use_container_width=True)
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            rc1, rc2 = st.columns([st.session_state.lc_delta_wt, 100-st.session_state.lc_delta_wt])
            with rc2: 
                wrows = "".join([f'<div style="padding:4px 0;border-bottom:1px solid rgba(0,0,0,0.04);"><div style="display:flex;justify-content:space-between;"><span style="font-weight:700;">{k}</span><span style="color:{main_color};font-weight:600;">{v*100:.0f}%</span></div><div style="height:4px;background:rgba(0,0,0,0.07);"><div style="height:4px;width:{int(v/max(target_weights.values())*100)}%;background:{main_color};"></div></div></div>' for k, v in target_weights.items() if v > 0])
                st.container(border=True).markdown(apply_theme(f'<div style="font-size:0.55em;font-weight:600;text-transform:uppercase;margin-bottom:6px;">Target Weights · R{curr_regime}</div>{wrows}'), unsafe_allow_html=True)
        st.markdown(apply_theme(f'<div style="display:flex;align-items:center;gap:8px;margin-top:12px;margin-bottom:8px;"><div style="width:2px;height:12px;background:{main_color};"></div><span style="font-size:0.58em;font-weight:600;text-transform:uppercase;">Rebalancing Matrix</span></div>'), unsafe_allow_html=True); _rebalancing_matrix()

    elif display_mode == "Mobile":
        st.markdown(f"<style>.main .block-container {{ max-width:460px !important; padding:0.4rem !important; }}</style>", unsafe_allow_html=True)
        ng = st.number_input("🎯 목표($)", value=st.session_state.goal_usd, format="%.0f", key="goal_input"); st.session_state.goal_usd = ng if ng != st.session_state.goal_usd else st.session_state.goal_usd
        st.markdown(_goal_tracker_html(tval_k), unsafe_allow_html=True); st.markdown(_regime_card_html(False), unsafe_allow_html=True)
        with st.container(border=True): st.markdown(_sl("Position Input"), unsafe_allow_html=True); _pf_editor(400)
        _target_weights_block(); st.markdown(apply_theme(f'<div style="margin-bottom:8px;"><span style="font-weight:600;text-transform:uppercase;">Rebalancing</span></div>'), unsafe_allow_html=True); _rebalancing_matrix(True)

# ==========================================
# 페이지 3: 🍫 12-Pack Radar
# ==========================================
elif page == "🍫 12-Pack Radar":
    def run_ai_radar():
        try:
            import google.generativeai as genai; genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            valid = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target = next((m for m in valid if 'gemini-1.5-flash' in m), valid[0]) if valid else None
            if not target: st.error("모델 오류"); return
            p = f"너는 월스트리트 퀀트 애널리스트야. AMLS V4.5 지표를 분석해줘.\n[레짐] R{curr_regime}\n[신호] Risk {risk_cnt}, Warn {warn_cnt}, Safe {safe_cnt}\n1. QQQ RSI: {last_row['QQQ_RSI']:.1f}\n2. QQQ DD: {last_row['QQQ_DD']*100:.1f}%\n3. FGI: {fg_score:.0f}\n섹터별 분류, 리스크 요소, 투자 스탠스로 요약해줘."
            with st.spinner("AI 분석 중..."): res = genai.GenerativeModel(target.replace('models/','')).generate_content(p); st.markdown(apply_theme(f'<div style="background:#FAFAF7;border-left:4px solid {main_color};padding:20px 24px;font-size:0.88em;">{res.text}</div>'), unsafe_allow_html=True)
        except Exception as e: st.error(f"오류: {e}")

    df_view  = df.iloc[-120:]
    qqq_rsi  = last_row['QQQ_RSI']; qqq_dd = last_row['QQQ_DD']; cnn_fgi = fetch_fear_and_greed()
    fg_score = cnn_fgi if cnn_fgi else (max(0, min(100, 100-(last_row['^VIX']-12)/28*100)) + max(0, min(100, (qqq_dd+0.20)/0.20*100)) + max(0, min(100, qqq_rsi)))/3
    sec_names = {'XLK':'TECH','XLV':'HEALTH','XLF':'FIN','XLY':'CONS','XLC':'COMM','XLI':'IND','XLP':'STAPLE','XLE':'ENGY','XLU':'UTIL','XLRE':'REAL','XLB':'MAT'}
    sec_df = pd.DataFrame([{'섹터':sec_names[s],'수익률':last_row[f'{s}_1M']*100} for s in SECTOR_TICKERS]).sort_values(by='수익률')
    top_sec, bot_sec = sec_df.iloc[-1]['섹터'], sec_df.iloc[0]['섹터']

    risk_cnt = sum([qqq_dd<-0.20, last_row['HYG_IEF_Ratio']<last_row['HYG_IEF_MA50'], last_row['UUP']>last_row['UUP_MA50'], last_row['^VIX']>last_row['VIX_MA50']])
    warn_cnt = sum([qqq_rsi>70, -0.20<=qqq_dd<-0.10, fg_score>70, (last_row['QQQ_20d_Ret']>0 and last_row['QQQE_20d_Ret']<0), last_row['GLD_SPYG_Ratio']>last_row['GLD_SPYG_MA50'], last_row['^TNX']>last_row['TNX_MA50'], last_row['BTC-USD']<last_row['BTC_MA50'], last_row['IWM_SPYG_Ratio']<last_row['IWM_SPYG_MA50'], top_sec in ['UTIL', 'STAPLE', 'HEALTH']])
    safe_cnt = 12 - risk_cnt - warn_cnt

    if risk_cnt >= 3: radar_status, radar_msg, radar_color = "극단적 위험 구간 (Risk-Off)", "시스템 리스크 경고. 레버리지 해제 요망.", "#DC2626"
    elif warn_cnt >= 4 or risk_cnt >= 1: radar_status, radar_msg, radar_color = "변동성 주의 (Warning)", "균열 조짐 발생. 신규 매수 보류 및 관망 요망.", "#D97706"
    else: radar_status, radar_msg, radar_color = "안정적 순항 (Safe)", "매크로 지표 안정적. 추세 추종 전략 전개 요망.", main_color

    st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);border-left:3px solid {radar_color};padding:14px 20px;margin-bottom:12px;"><div style="display:flex;justify-content:space-between;"><div style="font-family:DM Mono;font-size:1.2em;font-weight:700;">Macro Signal Status</div><div>Risk {risk_cnt} | Warn {warn_cnt} | Safe {safe_cnt}</div></div></div>'), unsafe_allow_html=True)
    if st.button("🤖 AI 종합 투자의견 생성"): run_ai_radar()

# ==========================================
# 페이지 4: 📈 Backtest Lab
# ==========================================
elif page == "📈 Backtest Lab":
    st.markdown(apply_theme("""<div style="display:flex;align-items:center;gap:16px;margin-bottom:20px;"><div><h2 style="font-family:'Plus Jakarta Sans';font-size:1.7em;color:#0F172A;margin:0;">📈 Backtest Lab</h2></div></div>"""), unsafe_allow_html=True)
    panel_cfg, panel_res = st.columns([1, 2.8])
    with panel_cfg:
        with st.container(border=True):
            bt_start = st.date_input("Start Date", datetime(2020, 1, 1))
            bt_end   = st.date_input("End Date", datetime.today())
            monthly_cont = st.number_input("월 적립금 ($)", value=2000, step=500)

    with panel_res:
        with st.spinner("시뮬레이션 가동 중..."):
            bt_df = load_custom_backtest_data(bt_start, bt_end)
            if bt_df.empty: st.error("데이터 부족")
            else:
                daily_ret = bt_df[['QQQ','TQQQ','SOXL','USD','QLD','SSO','SPYG','SMH','GLD']].pct_change().fillna(0)
                w_orig = get_weights_v45(bt_df['Regime'].iloc[0], False)
                val_o, val_q, val_tqqq = 10000, 10000, 10000
                hist_o, hist_q, hist_tqqq, invested, curr_inv = [val_o], [val_q], [val_tqqq], [10000], 10000

                for i in range(1, len(bt_df)):
                    today, yesterday = bt_df.index[i], bt_df.index[i-1]
                    val_o *= (1 + sum(w_orig.get(t,0) * daily_ret[t].iloc[i] for t in w_orig if t in daily_ret.columns))
                    val_q *= (1 + daily_ret['QQQ'].iloc[i]); val_tqqq *= (1 + daily_ret['TQQQ'].iloc[i])
                    if today.month != yesterday.month: val_o += monthly_cont; val_q += monthly_cont; val_tqqq += monthly_cont; curr_inv += monthly_cont
                    hist_o.append(val_o); hist_q.append(val_q); hist_tqqq.append(val_tqqq); invested.append(curr_inv)
                    w_orig = get_weights_v45(bt_df['Regime'].iloc[i], (bt_df['SMH'].iloc[i] > bt_df['SMH_MA50'].iloc[i]) and (bt_df['SMH_3M_Ret'].iloc[i] > 0.05) and (bt_df['SMH_RSI'].iloc[i] > 50))

                res_df = pd.DataFrame({'V4.5': hist_o, 'QQQ': hist_q, 'TQQQ': hist_tqqq, 'Invested': invested}, index=bt_df.index)
                days = (res_df.index[-1] - res_df.index[0]).days
                def calc_m(s, i_s): return (s.iloc[-1]/i_s.iloc[-1]-1), ((s.iloc[-1]/i_s.iloc[-1])**(365.25/days)-1 if days>0 else 0), (((s/s.cummax())-1).min())
                
                ret_o, cagr_o, mdd_o = calc_m(res_df['V4.5'], res_df['Invested'])
                mc1, mc2 = st.columns(2)
                mc1.markdown(apply_theme(f'<div style="background:rgba({r_c},{g_c},{b_c},0.06);padding:16px;">CAGR {cagr_o*100:.1f}% | MDD {mdd_o*100:.1f}%</div>'), unsafe_allow_html=True)
                
                fig_eq = go.Figure()
                fig_eq.add_trace(go.Scatter(x=res_df.index, y=res_df['QQQ'], name='QQQ', line=dict(color='#CBD5E1', width=1.2, dash='dot')))
                fig_eq.add_trace(go.Scatter(x=res_df.index, y=res_df['V4.5'], name='AMLS', line=dict(color=main_color, width=3)))
                fig_eq.update_layout(title="Equity Curve", height=380, yaxis_type='log', **chart_layout); fig_eq.update_xaxes(**_ax); fig_eq.update_yaxes(**_ax)
                with st.container(border=True): st.plotly_chart(fig_eq, use_container_width=True)

# ==========================================
# 페이지 5: 📰 Macro News
# ==========================================
elif page == "📰 Macro News":
    headlines_for_ai, news_items = fetch_macro_news()
    st.markdown(apply_theme(f"""<div style="border-top:3px solid #111118;border-bottom:1px solid rgba(0,0,0,0.12);padding:18px 0 14px;margin-bottom:24px;"><div style="font-size:2.2em;font-weight:800;">Market Briefing</div></div>"""), unsafe_allow_html=True)
    nl, nr = st.columns([1, 1.6])
    with nl:
        if st.button("↻ 심층 추론 요약 실행", use_container_width=True):
            try:
                import google.generativeai as genai
                if not headlines_for_ai: st.warning("뉴스가 없습니다.")
                else:
                    with st.spinner("AI 분석 중..."):
                        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                        valid = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                        target = next((m for m in valid if 'gemini-1.5-flash' in m), valid[0]) if valid else None
                        res = genai.GenerativeModel(target.replace('models/','')).generate_content("다음 뉴스를 요약해.\n" + "\n".join(headlines_for_ai))
                        st.markdown(apply_theme(f'<div style="background:#FAFAF7;border-left:3px solid {main_color};padding:20px;">{res.text}</div>'), unsafe_allow_html=True)
            except Exception as e: st.error(f"오류: {e}")
    with nr:
        for idx, item in enumerate(news_items):
            st.markdown(f'<div style="padding:12px 0;border-bottom:1px solid rgba(0,0,0,0.07);"><a href="{item["link"]}" target="_blank" style="text-decoration:none;color:{tc_body};">{item["title"]}</a></div>', unsafe_allow_html=True)

_ls_save_all()
