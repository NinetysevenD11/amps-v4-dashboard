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

def _restore_from_qp():
    _qp, _changed = st.query_params.to_dict(), False
    if "amls_portfolio" in _qp:
        try:
            _pf = json.loads(_qp["amls_portfolio"])
            if 'portfolio' not in st.session_state or not any(st.session_state.portfolio[a]['shares'] for a in ASSET_LIST if a != 'CASH'):
                for k, v in _pf.items(): st.session_state.portfolio[k] = v
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

SECTOR_TICKERS = ['XLK','XLV','XLF','XLY','XLC','XLI','XLP','XLE','XLU','XLRE','XLB']
CORE_TICKERS   = ['QQQ','TQQQ','SOXL','USD','QLD','SSO','SPY','SMH','GLD','^VIX','HYG','IEF','QQQE','UUP','^TNX','BTC-USD','IWM']
TICKERS        = CORE_TICKERS + SECTOR_TICKERS
ASSET_LIST     = ['TQQQ','SOXL','USD','QLD','SSO','SPY','QQQ','GLD','CASH']
PORTFOLIO_FILE = 'portfolio_autosave.json'

def sanitize_portfolio():
    for a in ASSET_LIST:
        val = st.session_state.portfolio.get(a)
        if isinstance(val, (int, float)) or val is None: st.session_state.portfolio[a] = {'shares': float(val or 0.0), 'avg_price': 1.0 if a == 'CASH' else 0.0, 'fx': 1350.0}
        elif isinstance(val, dict):
            if 'shares' not in val: val['shares'] = 0.0
            if 'avg_price' not in val: val['avg_price'] = 1.0 if a == 'CASH' else 0.0
            if 'fx' not in val: val['fx'] = 1350.0
        else: st.session_state.portfolio[a] = {'shares': 0.0, 'avg_price': 0.0, 'fx': 1350.0}

if 'goal_usd' not in st.session_state: st.session_state.goal_usd = 100000.0
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {asset: {'shares':0.0, 'avg_price':0.0, 'fx':1350.0} for asset in ASSET_LIST}
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                loaded = json.load(f)
                for k, v in loaded.items(): st.session_state.portfolio[k] = v
        except: pass

if 'rebal_snapshot' not in st.session_state: st.session_state.rebal_snapshot = None
if 'rebal_ts'       not in st.session_state: st.session_state.rebal_ts = ""

sanitize_portfolio()

def save_portfolio_to_disk():
    try:
        with open(PORTFOLIO_FILE, 'w') as f: json.dump(st.session_state.portfolio, f)
    except: pass
    st.session_state['_needs_ls_save'] = True

@st.cache_data(ttl=3600, show_spinner=False)
def load_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=900)
    for attempt in range(3):
        try:
            data = yf.download(TICKERS, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)['Close']
            if data.empty: continue
            # 💡 Trading Days 필터링 (주말 방지)
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
            df['GLD_SPY_Ratio'] = df['GLD'] / df['SPY']
            df['GLD_SPY_MA50'] = df['GLD_SPY_Ratio'].rolling(50).mean()
            df['QQQ_High52'] = df['QQQ'].rolling(252).max()
            df['QQQ_DD'] = (df['QQQ'] / df['QQQ_High52']) - 1
            df['UUP_MA50'] = df['UUP'].rolling(50).mean()
            df['TNX_MA50'] = df['^TNX'].rolling(50).mean()
            df['BTC_MA50'] = df['BTC-USD'].rolling(50).mean()
            df['IWM_SPY_Ratio'] = df['IWM'] / df['SPY']
            df['IWM_SPY_MA50'] = df['IWM_SPY_Ratio'].rolling(50).mean()
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

# 💡 R3 -> R2 즉각 승급이 반영된 지연 로직
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
    bt_df['GLD_SPY_Ratio'] = bt_df['GLD'] / bt_df['SPY']
    bt_df['GLD_SPY_MA50'] = bt_df['GLD_SPY_Ratio'].rolling(50).mean()
    bt_df['QQQ_High52'] = bt_df['QQQ'].rolling(252).max()
    bt_df['QQQ_DD'] = (bt_df['QQQ'] / bt_df['QQQ_High52']) - 1
    bt_df['UUP_MA50'] = bt_df['UUP'].rolling(50).mean()
    bt_df['TNX_MA50'] = bt_df['^TNX'].rolling(50).mean()
    bt_df['BTC_MA50'] = bt_df['BTC-USD'].rolling(50).mean()
    bt_df['IWM_SPY_Ratio'] = bt_df['IWM'] / bt_df['SPY']
    bt_df['IWM_SPY_MA50'] = bt_df['IWM_SPY_Ratio'].rolling(50).mean()
    bt_df = bt_df.dropna()
    if bt_df.empty: return bt_df
    bt_df['Target'] = bt_df.apply(get_target_v45, axis=1)
    bt_df['Regime'] = apply_asymmetric_delay(bt_df['Target'])
    bt_df = bt_df.loc[pd.to_datetime(start_date):pd.to_datetime(end_date)]
    return bt_df

REALTIME_TICKERS = ['QQQ','TQQQ','SMH','^VIX','HYG','IEF','UUP','GLD','SPY','SOXL','USD','QLD','SSO','USDKRW=X', '^TNX', 'BTC-USD', 'IWM']

# 💡 실시간 데이터 수집 (프리장/애프터장 반영)
@st.cache_data(ttl=15)
def fetch_realtime_prices():
    prices = {}
    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc + timedelta(hours=9)
    fetch_time = now_kst.strftime("%Y-%m-%d %H:%M:%S")
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
    return prices, fetch_time

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
    global_tickers = {'SPY':'S&P 500','QQQ':'Nasdaq 100','DIA':'Dow Jones','IWM':'Russell 2000','EWJ':'Japan','EWT':'Taiwan','EWY':'Korea','FXI':'China','EWH':'HongKong','VGK':'Europe','EWG':'Germany','EWU':'UK','EWQ':'France','EWC':'Canada','EEM':'Emg Mkt','EWZ':'Brazil','EWA':'Australia'}
    asset_tickers = {'^TNX':'US 10Y','GLD':'Gold','SLV':'Silver','USO':'Oil','BTC-USD':'Bitcoin','ETH-USD':'Ethereum','UUP':'DXY'}
    leader_tickers = {'AAPL':'Apple','MSFT':'Microsoft','NVDA':'Nvidia','AMZN':'Amazon','GOOGL':'Alphabet','META':'Meta','TSLA':'Tesla','AVGO':'Broadcom','AMD':'AMD','TSM':'TSMC'}
    all_t = list(global_tickers.keys()) + list(asset_tickers.keys()) + list(leader_tickers.keys())
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
    return results, global_tickers, asset_tickers, leader_tickers

with st.spinner('시장 데이터 수집 중...'):
    df = load_data()
    if df is not None and not df.empty: st.session_state['_df_cache'] = df
    elif '_df_cache' in st.session_state: df = st.session_state['_df_cache']
    rt_prices, last_update_time = fetch_realtime_prices()

if df is None or df.empty:
    st.error("야후 파이낸스 연결 실패")
    st.stop()

last_index = df.index[-1]
rt_injected = []
for ticker, price in rt_prices.items():
    if ticker in df.columns and price > 0:
        df.at[last_index, ticker] = price
        rt_injected.append(ticker)

if 'QQQ' in rt_injected: df.at[last_index, 'QQQ_DD'] = (df.at[last_index, 'QQQ'] / df['QQQ_High52'].iloc[-1]) - 1
if 'HYG' in rt_injected and 'IEF' in rt_injected: df.at[last_index, 'HYG_IEF_Ratio'] = df.at[last_index, 'HYG'] / df.at[last_index, 'IEF']
if 'IWM' in rt_injected and 'SPY' in rt_injected: df.at[last_index, 'IWM_SPY_Ratio'] = df.at[last_index, 'IWM'] / df.at[last_index, 'SPY']

last_row = df.iloc[-1].copy()
rt_ok    = len(rt_injected) >= 3
rt_label = f"⬤ LIVE  {len(rt_injected)} feeds" if rt_ok else "⬤ DELAYED"

vix_close, vix_ma5, vix_ma20 = last_row['^VIX'], last_row['VIX_MA5'], last_row['VIX_MA20']
qqq_close, qqq_ma50, qqq_ma200 = last_row['QQQ'], last_row['QQQ_MA50'], last_row['QQQ_MA200']
smh_close, smh_ma50, smh_3m, smh_1m, smh_rsi = last_row['SMH'], last_row['SMH_MA50'], last_row['SMH_3M_Ret'], last_row['SMH_1M_Ret'], last_row['SMH_RSI']

df['Target'] = df.apply(get_target_v45, axis=1)
df['Regime'] = apply_asymmetric_delay(df['Target'])

live_regime   = get_target_v45(last_row)
hist_regime   = int(df.iloc[-1]['Regime'])

if live_regime > hist_regime: curr_regime = live_regime
elif hist_regime == 3 and live_regime <= 2: curr_regime = 2
else: curr_regime = hist_regime

target_regime = live_regime
smh_cond = (smh_close > smh_ma50) and (smh_3m > 0.05 or smh_1m > 0.10) and (smh_rsi > 50)

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
elif live_regime > curr_regime: regime_committee_msg = f"🔴 R{live_regime} 방어 즉시 반영"
elif hist_regime == 3 and live_regime == 1 and curr_regime == 2: regime_committee_msg = "🟡 R2 1차 회복 · R1 승급 대기 (5일)"
else: regime_committee_msg = f"🟡 R{live_regime} 승급 대기 (5일)"

b_color, t_color, line_c, dash_c, rsi_low_c = 'rgba(0,0,0,0)', '#4A4A57', main_color, '#B0B0BE', main_color
chart_layout = dict(paper_bgcolor=b_color, plot_bgcolor=b_color, font=dict(family="DM Mono, DM Sans, monospace", color=t_color), margin=dict(l=0, r=0, t=40, b=0))
radar_layout = dict(height=200, margin=dict(l=10, r=10, t=15, b=15), paper_bgcolor=b_color, plot_bgcolor=b_color, font=dict(family="DM Mono, DM Sans, monospace", color=t_color))
_ax = dict(gridcolor='rgba(0,0,0,0.07)', linecolor='rgba(0,0,0,0.12)', showgrid=True, zeroline=False)
_ax_r = dict(gridcolor='rgba(0,0,0,0.07)', zeroline=False, showgrid=True)
regime_info = {1:("R1  BULL","풀 가동"),2:("R2  CORR","방어 진입"), 3:("R3  BEAR","대피"),4:("R4  PANIC","최대 방어")}

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

st.sidebar.markdown(apply_theme(f"""<div style="padding:22px 20px 16px;background:{bg_color};border-bottom:1px solid rgba(0,0,0,0.09);"><div style="font-family:'DM Mono';font-size:0.52em;color:{tc_label};letter-spacing:0.26em;text-transform:uppercase;margin-bottom:8px;">Quantitative Engine</div><div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:1.65em;font-weight:800;color:{tc_heading};letter-spacing:-1px;line-height:1;margin-bottom:14px;">AMLS <span style="color:#10B981;">V4.5</span></div><div style="display:flex;align-items:center;justify-content:space-between;"><div class="live-pulse" style="display:inline-flex;align-items:center;gap:5px;font-family:'DM Mono';font-size:0.6em;color:#059669;padding:3px 10px;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);letter-spacing:0.06em;">{rt_label}</div><div style="font-family:'DM Mono';font-size:0.58em;color:{tc_label};letter-spacing:0.04em;">R{curr_regime}  ·  {regime_info[curr_regime][1]}</div></div></div>"""), unsafe_allow_html=True)
st.sidebar.markdown('<div class="sb-section" style="border-top:none;">Navigation</div>', unsafe_allow_html=True)
page = st.sidebar.radio("MENU", ["📊 Dashboard", "💼 Portfolio", "🍫 12-Pack Radar", "📈 Backtest Lab", "📰 Macro News"], label_visibility="collapsed")
display_mode = st.session_state.display_mode

with st.sidebar.expander("🎨  Appearance", expanded=False):
    _ac1, _ac2 = st.columns(2)
    with _ac1:
        st.markdown('<div style="font-family:DM Mono,monospace;font-size:0.65em;color:rgba(255,255,255,0.35);margin-bottom:4px;">Accent</div>', unsafe_allow_html=True)
        new_color = st.color_picker("Accent", st.session_state.main_color, label_visibility="collapsed", key="cp_theme")
        if new_color != st.session_state.main_color: st.session_state.main_color = new_color; st.session_state['_needs_ls_save'] = True; st.rerun()
    with _ac2:
        st.markdown('<div style="font-family:DM Mono,monospace;font-size:0.65em;color:rgba(255,255,255,0.35);margin-bottom:4px;">Background</div>', unsafe_allow_html=True)
        _new_bg = st.color_picker("BG", st.session_state.bg_color, label_visibility="collapsed", key="cp_bg")
        if _new_bg != st.session_state.bg_color: st.session_state.bg_color = _new_bg; st.session_state['_needs_ls_save'] = True; st.rerun()
    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
    _tc_defs = [("헤딩","tc_heading","cp_tc_heading"),("본문","tc_body","cp_tc_body"),("뮤트","tc_muted","cp_tc_muted"),("레이블","tc_label","cp_tc_label"),("데이터","tc_data","cp_tc_data"),("사이드","tc_sidebar","cp_tc_sidebar")]
    for (_d1, _k1, _w1), (_d2, _k2, _w2) in [(_tc_defs[i], _tc_defs[i+1]) for i in range(0, len(_tc_defs)-1, 2)]:
        _cc1, _cc2 = st.columns(2)
        with _cc1:
            st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.65em;color:rgba(255,255,255,0.35);margin-bottom:4px;">{_d1}</div>', unsafe_allow_html=True)
            _p1 = st.color_picker("", getattr(st.session_state, _k1), label_visibility="collapsed", key=_w1)
            if _p1 != getattr(st.session_state, _k1): setattr(st.session_state, _k1, _p1); st.session_state['_needs_ls_save'] = True; st.rerun()
        with _cc2:
            st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.65em;color:rgba(255,255,255,0.35);margin-bottom:4px;">{_d2}</div>', unsafe_allow_html=True)
            _p2 = st.color_picker("", getattr(st.session_state, _k2), label_visibility="collapsed", key=_w2)
            if _p2 != getattr(st.session_state, _k2): setattr(st.session_state, _k2, _p2); st.session_state['_needs_ls_save'] = True; st.rerun()
    if st.button("↺  초기화", use_container_width=True, key="reset_colors"):
        for _k, _v in [("main_color","#10B981"),("bg_color","#F7F6F2"),("tc_heading","#111118"),("tc_body","#2D2D2D"),("tc_muted","#6B6B7A"),("tc_label","#9494A0"),("tc_data","#111118"),("tc_sidebar","#2D2D2D")]: setattr(st.session_state, _k, _v)
        st.session_state['_needs_ls_save'] = True; st.rerun()

with st.sidebar.expander("🔗  Bookmarks", expanded=False):
    st.markdown("""<div style="display:flex;flex-direction:column;gap:0;"><a href="https://www.youtube.com/@JB_Insight" target="_blank" class="sidebar-link">📊 JB 인사이트</a><a href="https://www.youtube.com/@odokgod" target="_blank" class="sidebar-link">📻 오독</a><a href="https://www.youtube.com/@TQQQCRAZY" target="_blank" class="sidebar-link">🔥 TQQQ 미친놈</a><a href="https://www.youtube.com/@developmong" target="_blank" class="sidebar-link">🐒 디벨롭몽</a><a href="https://kr.investing.com/" target="_blank" class="sidebar-link">🌍 인베스팅닷컴</a><a href="https://kr.tradingview.com/" target="_blank" class="sidebar-link">📉 트레이딩뷰</a></div>""", unsafe_allow_html=True)

with st.sidebar.expander("💾  Portfolio Data", expanded=False):
    st.download_button("⬇  Backup (JSON)", data=json.dumps(st.session_state.portfolio), file_name="portfolio.json", mime="application/json", use_container_width=True, key="sb_backup")
    st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
    _sidebar_upload = st.file_uploader("⬆  Restore (JSON)", type="json", key="sb_uploader", label_visibility="visible")
    if _sidebar_upload is not None:
        try: st.session_state.portfolio.update(json.load(_sidebar_upload)); sanitize_portfolio(); save_portfolio_to_disk(); st.success("✅ 복구 완료"); st.rerun()
        except: st.error("❌ 파일 형식 오류")

with st.sidebar.expander("⚙️  Layout Controls  (PC)", expanded=False):
    def _lc_sec(title): st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.58em;font-weight:600;color:{tc_label};letter-spacing:0.16em;text-transform:uppercase;margin:10px 0 6px;padding-bottom:4px;border-bottom:1px solid rgba(0,0,0,0.08);">{title}</div>', unsafe_allow_html=True)
    _lc_sec("① 열 분할")
    _v = st.slider("좌열 너비 %", 20, 60, st.session_state.lc_lr_split, 2, key="sl_lr"); 
    if _v != st.session_state.lc_lr_split: st.session_state.lc_lr_split = _v; st.session_state['_needs_ls_save'] = True; st.rerun()
    _v = st.slider("Goal 입력창 %", 10, 40, st.session_state.lc_goal_inp, 2, key="sl_gi"); 
    if _v != st.session_state.lc_goal_inp: st.session_state.lc_goal_inp = _v; st.session_state['_needs_ls_save'] = True; st.rerun()
    _lc_sec("② 컴포넌트 높이")
    _v = st.slider("에디터 높이 px", 200, 600, st.session_state.lc_editor_h, 20, key="sl_eh"); 
    if _v != st.session_state.lc_editor_h: st.session_state.lc_editor_h = _v; st.session_state['_needs_ls_save'] = True; st.rerun()
    _v = st.slider("파이차트 높이 px", 140, 340, st.session_state.lc_pie_h, 20, key="sl_ph"); 
    if _v != st.session_state.lc_pie_h: st.session_state.lc_pie_h = _v; st.session_state['_needs_ls_save'] = True; st.rerun()
    _v = st.slider("Delta Bar 높이 px", 120, 320, st.session_state.lc_bar_h, 20, key="sl_bh"); 
    if _v != st.session_state.lc_bar_h: st.session_state.lc_bar_h = _v; st.session_state['_needs_ls_save'] = True; st.rerun()
    _lc_sec("③ 내부 비율")
    _v = st.slider("파이 Current/Target %", 30, 70, st.session_state.lc_pie_split, 5, key="sl_ps"); 
    if _v != st.session_state.lc_pie_split: st.session_state.lc_pie_split = _v; st.session_state['_needs_ls_save'] = True; st.rerun()
    _v = st.slider("Delta Bar / Weights %", 30, 70, st.session_state.lc_delta_wt, 5, key="sl_dw"); 
    if _v != st.session_state.lc_delta_wt: st.session_state.lc_delta_wt = _v; st.session_state['_needs_ls_save'] = True; st.rerun()
    _lc_sec("④ 패널 표시")
    _c1, _c2, _c3 = st.columns(3)
    _nreg = _c1.checkbox("Regime", value=st.session_state.lc_show_reg, key="ck_reg")
    _nlp  = _c2.checkbox("Live Px", value=st.session_state.lc_show_lp, key="ck_lp")
    _nqo  = _c3.checkbox("Orders", value=st.session_state.lc_show_qo, key="ck_qo")
    if _nreg != st.session_state.lc_show_reg: st.session_state.lc_show_reg = _nreg; st.session_state['_needs_ls_save'] = True; st.rerun()
    if _nlp  != st.session_state.lc_show_lp: st.session_state.lc_show_lp = _nlp; st.session_state['_needs_ls_save'] = True; st.rerun()
    if _nqo  != st.session_state.lc_show_qo: st.session_state.lc_show_qo = _nqo; st.session_state['_needs_ls_save'] = True; st.rerun()
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    if st.button("↺  전체 초기화", use_container_width=True, key="lc_reset"):
        for _k, _dv in [("lc_lr_split", 38), ("lc_goal_inp", 22), ("lc_editor_h", 355), ("lc_pie_h", 200), ("lc_bar_h", 185), ("lc_pie_split", 50), ("lc_delta_wt", 52), ("lc_show_reg", True), ("lc_show_lp", True), ("lc_show_qo", True)]: setattr(st.session_state, _k, _dv)
        st.session_state['_needs_ls_save'] = True; st.rerun()

st.sidebar.markdown(apply_theme(f"""<div style="padding:10px 20px 6px;border-top:1px solid rgba(0,0,0,0.08);"><div style="font-family:'DM Mono';font-size:0.52em;color:{tc_label};letter-spacing:0.22em;text-transform:uppercase;margin-bottom:8px;">Display Mode</div><div style="display:flex;gap:4px;">{"".join([f'<div style="flex:1;padding:7px 0;text-align:center;background:{"rgba("+str(r_c)+","+str(g_c)+","+str(b_c)+",0.10)" if st.session_state.display_mode==nm else "rgba(0,0,0,0.03)"};border:1px solid {"rgba("+str(r_c)+","+str(g_c)+","+str(b_c)+",0.35)" if st.session_state.display_mode==nm else "rgba(0,0,0,0.10)"};font-family:DM Mono,monospace;font-size:0.68em;font-weight:{"700" if st.session_state.display_mode==nm else "400"};color:{main_color if st.session_state.display_mode==nm else tc_label};">{ic} {nm}</div>' for ic, nm in [("🖥","PC"),("📱","Tablet"),("📲","Mobile")]])}</div></div>"""), unsafe_allow_html=True)
_dm_c1, _dm_c2, _dm_c3 = st.sidebar.columns(3)
for _dmc, _dmnm in [(_dm_c1,"PC"), (_dm_c2,"Tablet"), (_dm_c3,"Mobile")]:
    if _dmc.button(_dmnm, key=f"dm_{_dmnm}", use_container_width=True): st.session_state.display_mode = _dmnm; st.session_state['_needs_ls_save'] = True; st.rerun()

_qqq_chg  = (last_row['QQQ'] / last_row['QQQ_MA200'] - 1) * 100
_vix_now  = last_row['^VIX']
_smh_chg  = last_row['SMH_1M_Ret'] * 100

def _pill(label, value, color): return f'<div style="display:flex;flex-direction:column;align-items:center;padding:8px 18px;background:#FFFFFF;border:1px solid rgba(0,0,0,0.07);border-top:2px solid {color};border-radius:12px;min-width:90px;"><span style="font-family:\'DM Mono\';font-size:0.6em;color:#4A5568;letter-spacing:0.14em;text-transform:uppercase;">{label}</span><span style="font-family:\'DM Mono\';font-size:1.05em;font-weight:500;color:#0F172A;margin-top:2px;">{value}</span></div>'

_p_qqq  = _pill("QQQ/200MA", f"{_qqq_chg:+.1f}%", main_color if _qqq_chg >= 0 else "#EF4444")
_p_vix  = _pill("VIX", f"{_vix_now:.1f}", main_color if _vix_now < 20 else ("#F59E0B" if _vix_now < 30 else "#EF4444"))
_p_smh  = _pill("SMH 1M", f"{_smh_chg:+.1f}%", main_color if _smh_chg >= 0 else "#EF4444")
_p_reg  = _pill("REGIME", f"R{curr_regime}", main_color)
_hdr_left = apply_theme(f"""<div style="display:flex;flex-direction:column;justify-content:center;"><div style="font-family:'Plus Jakarta Sans';font-size:2.5em;font-weight:800;letter-spacing:-2px;color:#0F172A;line-height:1;">AMLS <span style="color:#10B981;">V4.5</span></div><div style="font-family:'DM Mono';font-size:0.65em;color:#4A5568;letter-spacing:0.22em;text-transform:uppercase;margin-top:4px;">The Wall Street Quantitative Strategy</div></div>""")
_hdr_right = apply_theme(f"""<div style="display:flex;flex-direction:column;align-items:flex-end;gap:8px;"><div style="display:flex;gap:6px;">{_p_qqq}{_p_vix}{_p_smh}{_p_reg}</div><div style="display:flex;align-items:center;gap:10px;"><div class="live-pulse" style="font-family:'DM Mono';font-size:0.68em;color:#059669;padding:4px 12px;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.3);border-radius:6px;letter-spacing:0.06em;">{rt_label}</div><div style="font-family:'DM Mono';font-size:0.68em;color:#4A5568;letter-spacing:0.04em;">⏱ {last_update_time}</div></div></div>""")

hdr_c1, hdr_c2 = st.columns([1, 1.6])
with hdr_c1: st.markdown(_hdr_left, unsafe_allow_html=True)
with hdr_c2:
    c_sync1, c_sync2 = st.columns([4, 1])
    with c_sync2:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button("↺ 동기화", use_container_width=True): fetch_realtime_prices.clear(); load_data.clear(); st.rerun()
    with c_sync1: st.markdown(_hdr_right, unsafe_allow_html=True)
st.markdown(apply_theme(f"""<div style="position:relative;margin:14px 0 24px;height:1px;background:rgba(0,0,0,0.07);"><div style="position:absolute;left:0;top:0;width:100%;height:1px;background:rgba(0,0,0,0.12);"></div><div style="position:absolute;left:0;top:-1px;width:80px;height:3px;background:var(--acc);"></div></div>"""), unsafe_allow_html=True)


# ==========================================
# 라우팅 1. Dashboard
# ==========================================
if page == "📊 Dashboard":
    def _lg_row(label, val, passed):
        icon, color = ("●", main_color) if passed else ("○", "#B0B0BE")
        val_str = f"${val:.2f}" if isinstance(val, (int, float)) and val > 5 else f"{val:.2f}" if isinstance(val, (int, float)) else str(val)
        return f'<div class="crow"><span class="clabel">{label}</span><span class="cval" style="color:{color};">{val_str}&nbsp;<span style="font-size:0.7em;">{icon}</span></span></div>'
    soxl_title, soxl_strat, soxl_color = ("SOXL  APPROVED", "3× Leverage Active", main_color) if smh_cond else ("USD  DEFENSE", "2× Defense Mode", "#9494A0")
    _qqq_vs  = (last_row['QQQ']  / last_row['QQQ_MA200']  - 1) * 100
    _tqqq_vs = (last_row['TQQQ'] / last_row['TQQQ_MA200'] - 1) * 100
    _smh_vs  = (last_row['SMH']  / last_row['SMH_MA50']   - 1) * 100
    def _tick(label, val, sub, ok): return f'<div style="display:inline-flex;flex-direction:column;padding:0 20px;border-right:1px solid rgba(0,0,0,0.09);min-width:110px;"><span style="font-family:DM Mono,monospace;font-size:0.65em;color:#9494A0;letter-spacing:0.14em;text-transform:uppercase;">{label}</span><span style="font-family:DM Mono,monospace;font-size:1.05em;color:#111118;font-variant-numeric:tabular-nums;">{val}</span><span style="font-family:DM Mono,monospace;font-size:0.76em;color:{"#059669" if ok else "#DC2626"};\">{"▲" if ok else "▼"} {sub}</span></div>'
    tickers = _tick("QQQ", f"${last_row['QQQ']:.2f}", f"{_qqq_vs:+.2f}%", _qqq_vs>=0) + _tick("TQQQ", f"${last_row['TQQQ']:.2f}", f"{_tqqq_vs:+.2f}%", _tqqq_vs>=0) + _tick("VIX", f"{last_row['^VIX']:.2f}", f"MA20: {last_row['VIX_MA20']:.1f}", last_row['^VIX']<20) + _tick("SMH 1M", f"{last_row['SMH_1M_Ret']*100:+.1f}%", f"vs 50MA: {_smh_vs:+.1f}%", last_row['SMH_1M_Ret']>=0) + _tick("SMH RSI", f"{last_row['SMH_RSI']:.1f}", "> 50 target", last_row['SMH_RSI']>50)
    st.markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);border-left:3px solid #111118;padding:12px 0 12px 18px;margin-bottom:14px;display:flex;align-items:center;overflow-x:auto;"><span style="font-family:DM Mono,monospace;font-size:0.65em;color:#9494A0;letter-spacing:0.18em;text-transform:uppercase;white-space:nowrap;padding-right:16px;border-right:1px solid rgba(0,0,0,0.09);">Live&nbsp;Feed</span>{tickers}<div style="margin-left:auto;padding:0 14px;white-space:nowrap;"><span class="live-pulse" style="font-family:DM Mono,monospace;font-size:0.6em;color:#059669;letter-spacing:0.06em;">{rt_label}</span></div></div>', unsafe_allow_html=True)

    left_col, right_col = st.columns([1, 2.4])
    with left_col:
        regime_accent = {1: main_color, 2: "#D97706", 3: "#DC2626", 4: "#7C3AED"}[curr_regime]
        credit_check = last_row['HYG_IEF_Ratio'] >= last_row['HYG_IEF_MA20']
        st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);border-top:3px solid {regime_accent};padding:20px 18px 16px;margin-bottom:10px;position:relative;overflow:hidden;"><div style="position:absolute;right:-4px;bottom:-16px;font-family:Plus Jakarta Sans,sans-serif;font-size:7em;font-weight:800;color:rgba(0,0,0,0.04);line-height:1;pointer-events:none;user-select:none;">{curr_regime}</div><div style="font-family:DM Mono,monospace;font-size:0.68em;color:#9494A0;letter-spacing:0.18em;text-transform:uppercase;margin-bottom:10px;">Market Regime</div><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:2em;font-weight:800;letter-spacing:-1px;color:{regime_accent};line-height:1;margin-bottom:4px;">{regime_info[curr_regime][0]}</div><div style="font-family:DM Mono,monospace;font-size:0.72em;color:#6B6B7A;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:14px;">{regime_info[curr_regime][1]}</div>{_lg_row("VIX < 40", f"{vix_close:.2f}", vix_close<=40) + _lg_row(f"QQQ > 200MA [{qqq_ma200:.2f}]", f"${qqq_close:.2f}", qqq_close>=qqq_ma200) + _lg_row(f"50MA ≥ 200MA [{qqq_ma200:.2f}]", f"${qqq_ma50:.2f}", qqq_ma50>=qqq_ma200) + _lg_row("Credit Stress 방어", "안정" if credit_check else "경계", credit_check)}<div style="margin-top:8px;padding:6px 10px;background:rgba(16,185,129,0.07);border-left:2px solid {main_color};font-family:DM Mono,monospace;font-size:0.76em;color:#059669;">{regime_committee_msg}</div></div>'), unsafe_allow_html=True)
        st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);border-top:3px solid {soxl_color};padding:18px 18px 14px;margin-bottom:10px;"><div style="font-family:DM Mono,monospace;font-size:0.68em;color:#9494A0;letter-spacing:0.18em;text-transform:uppercase;margin-bottom:8px;">Semi-Conductor Gate</div><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.6em;font-weight:400;color:{soxl_color};margin-bottom:4px;">{soxl_title}</div><div style="font-family:DM Mono,monospace;font-size:0.7em;color:#6B6B7A;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:12px;">{soxl_strat}</div>{_lg_row("SMH > 50MA", f"${smh_close:.2f}", smh_close > smh_ma50) + _lg_row("Momentum 1M >10%", f"{smh_1m*100:.1f}%", smh_3m > 0.05 or smh_1m > 0.10) + _lg_row("RSI > 50", f"{smh_rsi:.1f}", smh_rsi > 50)}</div>'), unsafe_allow_html=True)
        weight_bar_rows = ""
        for k, v in target_weights.items():
            if v > 0: weight_bar_rows += f'<div style="display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:1px solid rgba(0,0,0,0.05);"><span style="font-family:DM Mono,monospace;font-size:0.84em;color:#2C2C35;min-width:48px;">{k}</span><div style="flex:1;margin:0 9px;height:4px;background:rgba(0,0,0,0.07);overflow:hidden;"><div style="height:4px;width:{int(v*250)}%;background:{main_color};"></div></div><span style="font-family:DM Mono,monospace;font-size:0.84em;color:{main_color};font-variant-numeric:tabular-nums;min-width:36px;text-align:right;">{v*100:.0f}%</span></div>'
        st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);border-top:3px solid #111118;padding:18px 18px 14px;"><div style="font-family:DM Mono,monospace;font-size:0.68em;color:#9494A0;letter-spacing:0.18em;text-transform:uppercase;margin-bottom:12px;">Target Weights  ·  R{curr_regime}</div>{weight_bar_rows}</div>'), unsafe_allow_html=True)

    with right_col:
        r_clrs, tabs_html = {1: main_color, 2:"#D97706", 3:"#DC2626", 4:"#7C3AED"}, ""
        for r in [1, 2, 3, 4]: tabs_html += f'<div style="padding:7px 16px;border:{"1px solid "+r_clrs[r] if r==curr_regime else "1px solid rgba(0,0,0,0.08)"};background:{r_clrs[r] if r==curr_regime else "transparent"};"><span style="font-family:DM Mono,monospace;font-size:0.76em;font-weight:500;color:{"#FFFFFF" if r==curr_regime else "#9494A0"};letter-spacing:0.05em;">{regime_info[r][0]}</span></div>'
        st.markdown(f'<div style="display:flex;gap:4px;margin-bottom:10px;align-items:center;">{tabs_html}<div style="margin-left:auto;font-family:DM Mono,monospace;font-size:0.7em;color:#9494A0;">⏱ {last_update_time}</div></div>', unsafe_allow_html=True)
        
        df_recent = df.iloc[-500:]
        for title, t1, t2 in [("QQQ  /  200-Day Moving Average", "QQQ", "QQQ_MA200"), ("TQQQ  /  200-Day Moving Average", "TQQQ", "TQQQ_MA200")]:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_recent.index, y=df_recent[t1], name=t1, line=dict(color=line_c, width=2), fill='tozeroy', fillcolor=f'rgba({r_c},{g_c},{b_c},0.06)'))
            fig.add_trace(go.Scatter(x=df_recent.index, y=df_recent[t2], name='200MA', line=dict(color=dash_c, width=1.2, dash='dot')))
            fig.update_layout(title=dict(text=title, font=dict(family='DM Mono', size=13, color=t_color)), height=330, **chart_layout, legend=dict(orientation='h', yanchor='bottom', y=1.0, xanchor='right', x=1, font=dict(family='DM Mono', size=11, color=t_color)))
            fig.update_xaxes(**_ax); fig.update_yaxes(**_ax)
            with st.container(border=True): st.plotly_chart(fig, use_container_width=True)
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    with st.spinner("글로벌 마켓 데이터 로딩..."): _gm_data, _gm_tickers, _asset_tickers, _leader_tickers = fetch_global_markets()

    def _sec_label(txt): st.markdown(f'<div style="display:flex;align-items:center;gap:12px;margin:24px 0 14px;"><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.1em;font-weight:700;color:{tc_heading};letter-spacing:-0.3px;white-space:nowrap;">{txt}</div><div style="flex:1;height:1px;background:rgba(0,0,0,0.12);"></div></div>', unsafe_allow_html=True)

    _sec_label("① Nasdaq 100  ·  Heatmap")
    _qqq_stocks = {'AAPL':('Technology','Apple'),'MSFT':('Technology','Microsoft'),'NVDA':('Technology','Nvidia'),'AVGO':('Technology','Broadcom'),'AMD':('Technology','AMD'),'INTC':('Technology','Intel'),'QCOM':('Technology','Qualcomm'),'TXN':('Technology','Texas Instr'),'ORCL':('Technology','Oracle'),'ADBE':('Technology','Adobe'),'CRM':('Technology','Salesforce'),'NOW':('Technology','ServiceNow'),'INTU':('Technology','Intuit'),'GOOGL':('Communication','Alphabet'),'META':('Communication','Meta'),'NFLX':('Communication','Netflix'),'AMZN':('Consumer','Amazon'),'TSLA':('Consumer','Tesla'),'BKNG':('Consumer','Booking'),'MCD':('Consumer',"McDonald's"),'COST':('Consumer','Costco'),'SBUX':('Consumer','Starbucks'),'PYPL':('Financials','PayPal'),'ISRG':('Healthcare','Intuitive Surg'),'GILD':('Healthcare','Gilead'),'AMGN':('Healthcare','Amgen'),'REGN':('Healthcare','Regeneron'),'HON':('Industrials','Honeywell'),'PEP':('Staples','PepsiCo')}
    _tm_labels, _tm_parents, _tm_values, _tm_colors, _tm_text = ["Nasdaq 100"], [""], [0], [0], [""]
    _sector_set = {}
    for _t, (_sec, _name) in _qqq_stocks.items():
        if _sec not in _sector_set:
            _sector_set[_sec] = True
            _tm_labels.append(_sec); _tm_parents.append("Nasdaq 100"); _tm_values.append(0); _tm_colors.append(0); _tm_text.append(_sec)
    for _t, (_sec, _name) in _qqq_stocks.items():
        _d = _gm_data.get(_t, {})
        _tm_labels.append(f"{_t}"); _tm_parents.append(_sec)
        _tm_values.append(max(abs(_d.get('price', 0.0)) * 0.1, 1)); _tm_colors.append(_d.get('chg', 0.0))
        _tm_text.append(f"{_name}<br>{_d.get('price',0.0):,.1f}<br>{_d.get('chg',0.0):+.2f}%")

    _tm_fig = go.Figure(go.Treemap(labels=_tm_labels, parents=_tm_parents, values=_tm_values, customdata=_tm_text, hovertemplate='%{customdata}<extra></extra>', texttemplate='<b>%{label}</b><br>%{customdata}', textfont=dict(size=11, family='DM Mono'), marker=dict(colors=_tm_colors, colorscale=[[0.0, '#DC2626'],[0.3, '#FCA5A5'],[0.5, '#F7F6F2'],[0.7, '#6EE7B7'],[1.0, '#059669']], cmid=0, cmin=-3, cmax=3, showscale=True, colorbar=dict(thickness=12, len=0.6, title=dict(text='%', font=dict(size=10, family='DM Mono')), tickfont=dict(size=9, family='DM Mono'), tickformat='+.1f')), branchvalues='remainder', tiling=dict(packing='squarify')))
    _tm_fig.update_layout(height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(family='DM Mono', color=t_color), margin=dict(l=0, r=0, t=10, b=0))
    with st.container(border=True): st.plotly_chart(_tm_fig, use_container_width=True)

    _sec_label("② Rates  /  Commodities  /  Crypto")
    _asset_cols = st.columns(7)
    _ico_dict = {"^TNX":"📈","GLD":"🥇","SLV":"⚪","USO":"🛢","BTC-USD":"₿","ETH-USD":"Ξ","UUP":"💵"}
    for _i, (_t, _name) in enumerate(_asset_tickers.items()):
        _d = _gm_data.get(_t, {}); _chg, _px = _d.get('chg', 0.0), _d.get('price', 0.0)
        _clr = "#059669" if _chg >= 0 else "#DC2626"
        _ico = _ico_dict.get(_t, "")
        with _asset_cols[_i]: st.markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);border-top:2px solid {_clr};padding:12px 10px;text-align:center;"><div style="font-size:1.1em;margin-bottom:4px;">{_ico}</div><div style="font-family:DM Mono,monospace;font-size:0.6em;color:#9494A0;letter-spacing:0.1em;text-transform:uppercase;">{_name}</div><div style="font-family:DM Mono,monospace;font-size:0.88em;color:#111118;margin:3px 0;">${_px:,.2f}</div><div style="font-family:DM Mono,monospace;font-size:0.8em;color:{_clr};font-weight:600;">{"▲" if _chg>=0 else "▼"} {_chg:+.2f}%</div></div>', unsafe_allow_html=True)

    _sec_label("③ Market Leaders")
    _ld_cols = st.columns(5)
    for _i, (_t, _name) in enumerate(sorted(_leader_tickers.items(), key=lambda x: _gm_data.get(x[0],{}).get('chg',0), reverse=True)):
        _d = _gm_data.get(_t, {}); _chg, _px = _d.get('chg', 0.0), _d.get('price', 0.0)
        _clr = "#059669" if _chg >= 0 else "#DC2626"
        with _ld_cols[_i % 5]: st.markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);border-top:2px solid {_clr};padding:12px 14px;margin-bottom:8px;"><div style="display:flex;justify-content:space-between;align-items:baseline;"><span style="font-family:DM Mono,monospace;font-size:0.62em;color:#9494A0;">{_t}</span><span style="font-family:DM Mono,monospace;font-size:0.62em;color:{"#D97706" if _i==0 else ("#9494A0" if _i>=3 else "#111118")};font-weight:600;">#{_i+1}</span></div><div style="font-family:DM Sans,sans-serif;font-size:0.82em;color:#2C2C35;margin:3px 0;">{_name}</div><div style="font-family:DM Mono,monospace;font-size:1.0em;color:#111118;">${_px:,.2f}</div><div style="font-family:DM Mono,monospace;font-size:0.82em;color:{_clr};font-weight:600;">{"▲" if _chg>=0 else "▼"} {_chg:+.2f}%</div></div>', unsafe_allow_html=True)

    _sec_label("④ Sector Scanner")
    _sec_data_full = [{'t': s, 'name': {'XLK':'Technology','XLV':'Health Care','XLF':'Financials','XLY':'Cons. Discret','XLC':'Comm. Svc','XLI':'Industrials','XLP':'Cons. Staples','XLE':'Energy','XLU':'Utilities','XLRE':'Real Estate','XLB':'Materials'}.get(s, s), 'ret1m': last_row.get(f'{s}_1M', 0.0) * 100} for s in SECTOR_TICKERS]
    _sec_sorted_full = sorted(_sec_data_full, key=lambda x: x['ret1m'], reverse=True)
    _sec_fig = go.Figure(go.Bar(x=[x['name'] for x in _sec_sorted_full], y=[x['ret1m'] for x in _sec_sorted_full], marker_color=["#059669" if v>=0 else "#DC2626" for v in [x['ret1m'] for x in _sec_sorted_full]], text=[f"{v:+.1f}%" for v in [x['ret1m'] for x in _sec_sorted_full]], textposition='outside', textfont=dict(size=10, family='DM Mono')))
    _sec_fig.update_layout(height=260, showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(family='DM Mono', color=t_color), margin=dict(l=0, r=0, t=20, b=40)); _sec_fig.update_xaxes(**_ax_r, tickfont=dict(size=10)); _sec_fig.update_yaxes(tickformat='.1f', ticksuffix='%', **_ax_r)
    with st.container(border=True): st.plotly_chart(_sec_fig, use_container_width=True)

# ==========================================
# 라우팅 2. Portfolio
# ==========================================
elif page == "💼 Portfolio":
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
    invested_cost = sum(st.session_state.portfolio[a]['shares'] * st.session_state.portfolio[a]['avg_price'] for a in ASSET_LIST if a != 'CASH')
    pnl_usd   = total_val_usd - invested_cost
    pnl_pct   = (pnl_usd / invested_cost * 100) if invested_cost > 0 else 0.0
    diff_vals = {a: (total_val_usd * target_weights.get(a, 0.0)) - curr_vals[a] for a in ASSET_LIST} if total_val_usd > 0 else {a: 0.0 for a in ASSET_LIST}
    C_GREEN, C_RED = main_color, "#DC2626"
    r_acc = {1: main_color, 2: "#D97706", 3: "#DC2626", 4: "#7C3AED"}[curr_regime]

    def _sl(text): return apply_theme(f'<div style="display:flex;align-items:center;gap:7px;margin-bottom:8px;padding-bottom:7px;border-bottom:1px solid rgba(0,0,0,0.09);"><div style="width:2px;height:12px;background:{main_color};flex-shrink:0;"></div><span style="font-family:DM Mono,monospace;font-size:0.58em;font-weight:600;color:{tc_heading};letter-spacing:0.2em;text-transform:uppercase;">{text}</span></div>')
    def _kv(label, val, color, sub=""): return f'<div style="display:flex;flex-direction:column;padding:0 20px;border-right:1px solid rgba(255,255,255,0.06);min-width:115px;"><span style="font-family:DM Mono,monospace;font-size:0.53em;color:rgba(255,255,255,0.35);letter-spacing:0.2em;text-transform:uppercase;margin-bottom:3px;">{label}</span><span style="font-family:DM Mono,monospace;font-size:1.0em;font-weight:500;color:{color};font-variant-numeric:tabular-nums;line-height:1.2;">{val}</span>{f"<span style=\'font-family:DM Mono,monospace;font-size:0.6em;color:rgba(255,255,255,0.3);\'>{sub}</span>" if sub else ""}</div>'
    
    def _lp_build():
        _html = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:3px;">'
        for _asset in ASSET_LIST:
            _lp_p = current_prices.get(_asset, 0.0) if _asset != 'CASH' else 1.0
            _lp_str = f"${_lp_p:,.2f}" if _lp_p > 0 else "—"
            _avg = st.session_state.portfolio[_asset].get('avg_price', 0.0)
            _shs = st.session_state.portfolio[_asset].get('shares', 0.0)
            if _asset != 'CASH' and _avg > 0 and _lp_p > 0:
                _lr = (_lp_p / _avg - 1) * 100
                _lc, _ls = ("#059669" if _lr >= 0 else "#DC2626"), f"{_lr:+.1f}%"
            elif _asset == 'CASH' and _shs > 0: _lc, _ls = tc_muted, f"${_shs:,.0f}"
            else: _lc, _ls = "#BBBBBB", "—"
            _html += f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.08);border-left:2px solid {_lc};padding:5px 8px;"><div style="display:flex;justify-content:space-between;align-items:baseline;gap:4px;"><span style="font-family:DM Mono,monospace;font-size:0.72em;font-weight:700;color:{tc_body};">{_asset}</span><span style="font-family:DM Mono,monospace;font-size:0.7em;color:{tc_body};font-variant-numeric:tabular-nums;">{_lp_str}</span></div><div style="font-family:DM Mono,monospace;font-size:0.6em;color:{_lc};text-align:right;">{_ls}</div></div>'
        return _html + f'</div><div style="text-align:right;margin-top:3px;"><span style="font-family:DM Mono,monospace;font-size:0.52em;color:{tc_label};">⏱ {last_update_time}</span></div>'

    def _qo_build(col, title, items, accent, bg):
        _rows = "".join([f'<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid rgba(0,0,0,0.04);"><span style="font-family:DM Mono,monospace;font-size:0.78em;font-weight:700;color:{tc_body};">{a}</span><span style="font-family:DM Mono,monospace;font-size:0.74em;color:{accent};font-variant-numeric:tabular-nums;">{v}</span></div>' for a, v in items]) or f'<div style="padding:6px 0;text-align:center;font-family:DM Mono,monospace;font-size:0.68em;color:#CCCCCC;">— 없음</div>'
        col.markdown(f'<div style="background:{bg};border:1px solid rgba(0,0,0,0.07);border-top:2px solid {accent};padding:8px 10px;"><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:0.76em;font-weight:700;color:{accent};margin-bottom:5px;">{title}</div>{_rows}</div>', unsafe_allow_html=True)

    def _sells_buys():
        _sells, _buys = [], []
        for asset in ASSET_LIST:
            _cp, _dv = current_prices[asset] if current_prices[asset] > 0 else 1.0, diff_vals[asset]
            if asset != 'CASH' and _dv < -_cp * 0.05: _sells.append((asset, f"{abs(_dv)/_cp:,.2f}주 매도"))
            elif asset == 'CASH' and _dv < -1.0: _sells.append(("CASH", f"${abs(_dv):,.0f} 사용"))
            if asset != 'CASH' and _dv > _cp * 0.05: _buys.append((asset, f"{_dv/_cp:,.2f}주 매수"))
            elif asset == 'CASH' and _dv > 1.0: _buys.append(("CASH", f"${_dv:,.0f} 확보"))
        return _sells, _buys

    def _goal_tracker_html():
        _goal = st.session_state.goal_usd
        _pct_raw = (total_val_usd / _goal * 100) if _goal > 0 else 0.0
        _pct = min(_pct_raw, 100.0)
        if _pct_raw > 100.0: _gc, _gbadge = "#059669", "ACHIEVED"
        elif _pct >= 75: _gc, _gbadge = main_color, "75%+"
        elif _pct >= 50: _gc, _gbadge = "#D97706", "ON TRACK"
        else: _gc, _gbadge = "#94A3B8", "GROWING"
        _gr, _gg, _gb = hex_to_rgb(_gc)
        _seg = "".join([f'<div style="position:absolute;left:{m}%;top:0;bottom:-18px;width:1px;background:rgba(0,0,0,0.08);"><span style="position:absolute;top:calc(100% + 2px);left:50%;transform:translateX(-50%);font-family:DM Mono,monospace;font-size:0.5em;color:#BBBBBB;white-space:nowrap;">{m}%</span></div>' for m in [25, 50, 75, 100]])
        return apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.11);border-left:4px solid {_gc};padding:10px 18px;display:flex;align-items:center;gap:18px;"><div style="display:flex;align-items:center;gap:8px;flex-shrink:0;"><span style="font-family:DM Mono,monospace;font-size:0.56em;color:{tc_label};letter-spacing:0.18em;text-transform:uppercase;">Goal Tracker</span><span style="background:rgba({_gr},{_gg},{_gb},0.1);border:1px solid rgba({_gr},{_gg},{_gb},0.28);color:{_gc};font-family:DM Mono,monospace;font-size:0.55em;padding:1px 8px;">{_gbadge}</span></div><div style="flex:1;position:relative;padding-bottom:18px;">{_seg}<div style="height:8px;background:rgba(0,0,0,0.07);"><div style="height:8px;width:{_pct:.2f}%;background:linear-gradient(90deg,rgba({_gr},{_gg},{_gb},0.4),{_gc});"></div></div></div><div style="display:flex;gap:20px;flex-shrink:0;align-items:center;"><div style="text-align:center;"><div style="font-family:DM Mono,monospace;font-size:0.5em;color:{tc_label};text-transform:uppercase;letter-spacing:0.1em;">현재</div><div style="font-family:DM Mono,monospace;font-size:0.82em;color:{tc_body};font-variant-numeric:tabular-nums;">${total_val_usd:,.0f}</div></div><div style="text-align:center;"><div style="font-family:DM Mono,monospace;font-size:0.5em;color:{tc_label};text-transform:uppercase;letter-spacing:0.1em;">목표</div><div style="font-family:DM Mono,monospace;font-size:0.82em;color:{tc_body};font-variant-numeric:tabular-nums;">${_goal:,.0f}</div></div><div style="text-align:right;padding-left:14px;border-left:1px solid rgba(0,0,0,0.08);"><span style="font-family:DM Mono,monospace;font-size:1.8em;font-weight:400;color:{_gc};font-variant-numeric:tabular-nums;letter-spacing:-1.5px;line-height:1;">{_pct_raw:.1f}%</span></div></div></div>')

    def _regime_card_html(horizontal=False):
        if horizontal: return apply_theme(f'<div style="background:rgba({r_c},{g_c},{b_c},0.07);border:1px solid rgba({r_c},{g_c},{b_c},0.22);border-left:4px solid {r_acc};padding:12px 20px;display:flex;align-items:center;gap:32px;"><div style="flex:1;"><div style="font-family:DM Mono,monospace;font-size:0.53em;color:{tc_label};letter-spacing:0.18em;text-transform:uppercase;margin-bottom:3px;">Current Regime</div><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.5em;font-weight:800;color:{r_acc};letter-spacing:-0.5px;line-height:1;margin-bottom:1px;">{regime_info[curr_regime][0]}</div><div style="font-family:DM Mono,monospace;font-size:0.6em;color:{tc_muted};letter-spacing:0.1em;text-transform:uppercase;">{regime_info[curr_regime][1]}</div></div><div style="width:1px;height:48px;background:rgba({r_c},{g_c},{b_c},0.2);flex-shrink:0;"></div><div style="flex:1;font-family:DM Mono,monospace;font-size:0.64em;color:{tc_muted};">{regime_committee_msg}</div></div>')
        else: return apply_theme(f'<div style="background:rgba({r_c},{g_c},{b_c},0.07);border:1px solid rgba({r_c},{g_c},{b_c},0.22);border-left:4px solid {r_acc};padding:14px 16px;margin-bottom:10px;"><div style="font-family:DM Mono,monospace;font-size:0.53em;color:{tc_label};letter-spacing:0.18em;text-transform:uppercase;margin-bottom:4px;">Current Regime</div><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.45em;font-weight:800;color:{r_acc};letter-spacing:-0.5px;line-height:1;margin-bottom:2px;">{regime_info[curr_regime][0]}</div><div style="font-family:DM Mono,monospace;font-size:0.6em;color:{tc_muted};letter-spacing:0.1em;text-transform:uppercase;">{regime_info[curr_regime][1]}</div><div style="margin-top:7px;padding-top:7px;border-top:1px solid rgba({r_c},{g_c},{b_c},0.18);font-family:DM Mono,monospace;font-size:0.58em;color:{tc_muted};">{regime_committee_msg}</div></div>')

    def _pf_editor(height=355):
        _edata = [{"Asset": asset, "Shares": float(st.session_state.portfolio.get(asset, {}).get('shares', 0.0)), "Avg Price($)": float(st.session_state.portfolio.get(asset, {}).get('avg_price', 1.0 if asset == 'CASH' else 0.0)), "FX Rate(₩)": float(st.session_state.portfolio.get(asset, {}).get('fx', 1350.0))} for asset in ASSET_LIST]
        _df_ed = pd.DataFrame(_edata)
        _df_edited = st.data_editor(_df_ed, disabled=["Asset"], hide_index=True, use_container_width=True, key="pf_editor", height=height, column_config={"Shares": st.column_config.NumberColumn("Shares", format="%.4f"), "Avg Price($)": st.column_config.NumberColumn("Avg($)", format="%.2f"), "FX Rate(₩)": st.column_config.NumberColumn("FX(₩)", format="%.0f")})
        if not _df_edited.equals(_df_ed):
            for _, row in _df_edited.iterrows(): st.session_state.portfolio[row["Asset"]] = {'shares': float(row["Shares"]), 'avg_price': float(row["Avg Price($)"]), 'fx': float(row["FX Rate(₩)"])}
            save_portfolio_to_disk(); st.rerun()

    def _pie_charts():
        _pie_colors, _pie_cfg = [line_c,'#B0B0BE','#34D399','#6EE7B7','#A7F3D0','#059669','#047857','#065F46','#D1FAE5'], dict(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(family="DM Mono", color=t_color), showlegend=True, legend=dict(orientation='v', x=1.0, y=0.5, font=dict(size=8, family='DM Mono'), bgcolor='rgba(0,0,0,0)'), margin=dict(l=0, r=70, t=28, b=0), height=200)
        _rb1, _rb2 = st.columns(2)
        _lcur, _vcur = [a for a in ASSET_LIST if curr_vals[a] > 0], [curr_vals[a] for a in ASSET_LIST if curr_vals[a] > 0]
        with _rb1:
            if sum(_vcur) > 0:
                _fc = go.Figure(go.Pie(labels=_lcur, values=_vcur, hole=.55, textinfo='percent', textfont=dict(size=9), marker=dict(colors=_pie_colors, line=dict(color='#FAFAF7', width=1.5))))
                _fc.update_layout(title=dict(text="Current", font=dict(family="DM Mono", size=11, color=t_color), x=0), **_pie_cfg)
                with st.container(border=True): st.plotly_chart(_fc, use_container_width=True)
            else: st.markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.09);height:200px;display:flex;align-items:center;justify-content:center;"><span style="font-family:DM Mono,monospace;font-size:0.7em;color:#CCCCCC;">포지션 없음</span></div>', unsafe_allow_html=True)
        _ltgt, _vtgt = [a for a in ASSET_LIST if target_weights.get(a, 0) > 0], [target_weights[a] for a in ASSET_LIST if target_weights.get(a, 0) > 0]
        with _rb2:
            _ft = go.Figure(go.Pie(labels=_ltgt, values=_vtgt, hole=.55, textinfo='percent', textfont=dict(size=9), marker=dict(colors=_pie_colors, line=dict(color='#FAFAF7', width=1.5))))
            _ft.update_layout(title=dict(text=f"Target  R{curr_regime}", font=dict(family="DM Mono", size=11, color=t_color), x=0), **_pie_cfg)
            with st.container(border=True): st.plotly_chart(_ft, use_container_width=True)

    def _delta_bar():
        _dlabels, _dvals = [a for a in ASSET_LIST if abs(diff_vals[a]) >= 1.0], [diff_vals[a] for a in ASSET_LIST if abs(diff_vals[a]) >= 1.0]
        if _dlabels:
            _fd = go.Figure(go.Bar(x=_dlabels, y=_dvals, marker_color=[C_GREEN if v > 0 else C_RED for v in _dvals], text=[f"${v:+,.0f}" for v in _dvals], textposition='outside', textfont=dict(size=8, family='DM Mono'), marker_line_width=0))
            _fd.update_layout(title=dict(text="Δ Rebalancing ($)", font=dict(family='DM Mono', size=10, color=t_color)), height=185, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color=t_color, family="DM Mono", size=8), showlegend=False, margin=dict(t=24, b=4, l=0, r=0)); _fd.update_xaxes(**_ax_r, tickfont=dict(size=8)); _fd.update_yaxes(**_ax_r)
            with st.container(border=True): st.plotly_chart(_fd, use_container_width=True)
        else: st.markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.09);height:185px;display:flex;align-items:center;justify-content:center;"><span style="font-family:DM Mono,monospace;font-size:0.68em;color:#CCCCCC;">Δ 없음</span></div>', unsafe_allow_html=True)

    def _target_weights_block():
        _wt_items = sorted([(k, v) for k, v in target_weights.items() if v > 0], key=lambda x: x[1], reverse=True)
        _max_wt = max(v for _, v in _wt_items) if _wt_items else 1
        _wt_rows = ""
        for _wk, _wv in _wt_items:
            _wpct, _bw, _cp2 = _wv * 100, int(_wv / _max_wt * 100), (curr_vals.get(_wk, 0) / total_val_usd * 100) if total_val_usd > 0 else 0
            _dp = _wpct - _cp2
            _dc = "#059669" if _dp > 0.5 else ("#DC2626" if _dp < -0.5 else "#9494A0")
            _ds = f"{_dp:+.1f}%" if abs(_dp) > 0.5 else "—"
            _wt_rows += f'<div style="padding:4px 0;border-bottom:1px solid rgba(0,0,0,0.04);"><div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:3px;"><span style="font-family:DM Mono,monospace;font-size:0.78em;font-weight:700;color:{tc_body};">{_wk}</span><div style="display:flex;gap:3px;align-items:baseline;"><span style="font-family:DM Mono,monospace;font-size:0.84em;font-weight:600;color:{main_color};">{_wpct:.0f}%</span><span style="font-family:DM Mono,monospace;font-size:0.58em;color:{_dc};">{_ds}</span></div></div><div style="height:4px;background:rgba(0,0,0,0.07);"><div style="height:4px;width:{_bw}%;background:{main_color};"></div></div></div>'
        with st.container(border=True): st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.55em;font-weight:600;color:{tc_label};letter-spacing:0.18em;text-transform:uppercase;margin-bottom:6px;padding-bottom:5px;border-bottom:1px solid rgba(0,0,0,0.08);">Target Weights · R{curr_regime}</div><div>{_wt_rows}</div>', unsafe_allow_html=True)

    def _rebalancing_matrix():
        if total_val_usd <= 0: st.markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.09);padding:28px;text-align:center;"><span style="font-family:DM Mono,monospace;font-size:0.8em;color:#CCCCCC;">포지션을 입력하면 리밸런싱 매트릭스가 표시됩니다.</span></div>', unsafe_allow_html=True); return
        _btn_c, _ts_c = st.columns([1, 3])
        with _btn_c:
            if st.button("📸  리밸런싱 계획 확정", use_container_width=True, key="rebal_confirm"):
                _now = datetime.now().strftime("%Y-%m-%d %H:%M")
                st.session_state.rebal_snapshot = {"portfolio": {a: dict(st.session_state.portfolio[a]) for a in ASSET_LIST}, "current_prices": dict(current_prices), "curr_vals": dict(curr_vals), "total_val_usd": total_val_usd, "target_weights": dict(target_weights), "curr_regime": curr_regime, "ts": _now}
                st.session_state.rebal_ts = _now; st.rerun()
        with _ts_c:
            _snap = st.session_state.rebal_snapshot
            if _snap:
                if any(st.session_state.portfolio[a]['shares'] != _snap['portfolio'][a]['shares'] for a in ASSET_LIST):
                    st.markdown(f'<div style="background:rgba(217,119,6,0.08);border:1px solid rgba(217,119,6,0.3);padding:8px 14px;display:flex;align-items:center;gap:8px;"><span style="font-family:DM Mono,monospace;font-size:0.62em;color:#D97706;">⚠  포트폴리오가 수정되었습니다. 재확정 버튼을 눌러주세요.</span></div>', unsafe_allow_html=True)
                else: st.markdown(f'<div style="background:rgba({r_c},{g_c},{b_c},0.07);border:1px solid rgba({r_c},{g_c},{b_c},0.22);padding:8px 14px;display:flex;align-items:center;gap:8px;"><span style="font-family:DM Mono,monospace;font-size:0.62em;color:{main_color};">✔  확정된 계획 — {_snap["ts"]}  ·  총자산 ${_snap["total_val_usd"]:,.0f}  ·  R{_snap["curr_regime"]}</span></div>', unsafe_allow_html=True)
            else: st.markdown(f'<div style="background:rgba(0,0,0,0.04);border:1px solid rgba(0,0,0,0.10);padding:8px 14px;"><span style="font-family:DM Mono,monospace;font-size:0.62em;color:{tc_label};">확정 버튼을 눌러야 리밸런싱 계획이 생성됩니다.</span></div>', unsafe_allow_html=True)

        if not _snap: return
        _s_pf, _s_px, _s_vals, _s_total, _s_tgtw = _snap["portfolio"], _snap["current_prices"], _snap["curr_vals"], _snap["total_val_usd"], _snap["target_weights"]
        _s_diff = {a: (_s_total * _s_tgtw.get(a, 0.0)) - _s_vals[a] for a in ASSET_LIST}
        _sell_list, _buy_list = [], []
        for asset in ASSET_LIST:
            _cp, _diff, _threshold = _s_px[asset] if _s_px[asset] > 0 else 1.0, _s_diff[asset], _s_px[asset] * 0.05 if asset != 'CASH' else 1.0
            if _diff < -_threshold: _sell_list.append((asset, _diff, abs(_diff) / _cp if asset != 'CASH' else 0, _cp))
            elif _diff > _threshold: _buy_list.append((asset, _diff, _diff / _cp if asset != 'CASH' else 0, _cp))
        _sell_list.sort(key=lambda x: x[1]); _buy_list.sort(key=lambda x: -x[1])
        _total_sell_proceeds, _existing_cash, _total_buy_needed = sum(abs(d) for _, d, _, _ in _sell_list), _s_vals.get('CASH', 0.0), sum(d for _, d, _, _ in _buy_list)
        _available_cash = _total_sell_proceeds + _existing_cash
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        _ep1, _ep2, _ep3 = st.columns([1, 0.12, 1])

        with _ep1:
            _sell_rows = ""
            for asset, diff, sh, cp in _sell_list:
                _sell_rows += f'<tr style="background:rgba(220,38,38,0.025);"><td style="font-weight:700;color:#059669;font-family:DM Mono,monospace;font-size:0.84em;">{asset}</td><td style="color:{tc_muted};">${cp:.2f}</td><td style="color:{tc_label};">{_s_vals[asset]:,.0f}</td><td style="color:{main_color};font-weight:700;">{_s_tgtw.get(asset,0)*100:.0f}%</td><td style="color:{tc_label};">{_s_total * _s_tgtw.get(asset, 0.0):,.0f}</td><td><span style="color:#DC2626;font-weight:600;">-${abs(diff):,.0f}</span></td><td><span style="font-family:DM Mono,monospace;font-size:0.7em;font-weight:700;color:#DC2626;background:rgba(220,38,38,0.08);padding:2px 8px;border-left:2px solid #DC2626;">▼ SELL</span></td><td style="color:{tc_muted};font-size:0.8em;">{f"{sh:,.4f}주" if asset != "CASH" else f"${abs(diff):,.0f}"}</td></tr>'
            st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.58em;font-weight:700;color:#DC2626;letter-spacing:0.16em;text-transform:uppercase;margin-bottom:6px;padding-bottom:5px;border-bottom:2px solid #DC2626;">STEP 1  ·  매도 실행</div>', unsafe_allow_html=True)
            if _sell_rows:
                with st.container(border=True): st.markdown('<div style="overflow-x:auto;"><table class="mint-table"><thead><tr><th style="text-align:left;">Asset</th><th>현재가</th><th>현재액</th><th>목표%</th><th>목표액</th><th>매도금액</th><th style="text-align:center;">Action</th><th>수량</th></tr></thead><tbody>' + _sell_rows + '</tbody></table></div>', unsafe_allow_html=True)
                st.markdown(apply_theme(f'<div style="background:rgba(220,38,38,0.05);border:1px solid rgba(220,38,38,0.2);padding:8px 14px;margin-top:6px;"><span style="font-family:DM Mono,monospace;font-size:0.62em;color:#DC2626;font-weight:600;">매각 대금  ${_total_sell_proceeds:,.0f}</span>{f"  <span style=\'color:{tc_label};\'>+ 보유현금 ${_existing_cash:,.0f}</span>" if _existing_cash > 1 else ""}  →  <span style="color:{tc_body};font-weight:700;">가용 현금 ${_available_cash:,.0f}</span></div>'), unsafe_allow_html=True)
            else: st.markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.09);padding:20px;text-align:center;"><span style="font-family:DM Mono,monospace;font-size:0.72em;color:#CCCCCC;">매도 항목 없음</span></div>', unsafe_allow_html=True)

        with _ep2: st.markdown(f'<div style="display:flex;align-items:center;justify-content:center;height:100%;min-height:120px;font-size:1.6em;color:{tc_label};">→</div>', unsafe_allow_html=True)

        with _ep3:
            _remaining_cash, _buy_rows = _available_cash, ""
            for asset, diff, sh, cp in _buy_list:
                _actual_buy = min(diff, _remaining_cash)
                _actual_sh = _actual_buy / cp if cp > 0 and asset != 'CASH' else 0
                _shortfall = diff - _actual_buy
                _buy_color = "#059669" if _actual_buy >= diff * 0.95 else "#D97706"
                _buy_rows += f'<tr style="background:rgba(5,150,105,0.025);"><td style="font-weight:700;color:#059669;font-family:DM Mono,monospace;font-size:0.84em;">{asset}</td><td style="color:{tc_muted};">${cp:.2f}</td><td style="color:{tc_label};">{_s_vals[asset]:,.0f}</td><td style="color:{main_color};font-weight:700;">{_s_tgtw.get(asset,0)*100:.0f}%</td><td style="color:{tc_label};">{_s_total * _s_tgtw.get(asset, 0.0):,.0f}</td><td><span style="color:{_buy_color};font-weight:600;">+${_actual_buy:,.0f}</span>{f"<span style=\'font-family:DM Mono,monospace;font-size:0.62em;color:#D97706;margin-left:4px;\'>(부족 ${_shortfall:,.0f})</span>" if _shortfall > 1 else ""}</td><td><span style="font-family:DM Mono,monospace;font-size:0.7em;font-weight:700;color:{_buy_color};background:rgba(5,150,105,0.09);padding:2px 8px;border-left:2px solid {_buy_color};">▲ BUY</span></td><td style="color:{tc_muted};font-size:0.8em;">{f"{_actual_sh:,.4f}주" if asset != "CASH" else f"${_actual_buy:,.0f}"}</td></tr>'
                _remaining_cash -= _actual_buy
                if _remaining_cash <= 0: break
            st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.58em;font-weight:700;color:#059669;letter-spacing:0.16em;text-transform:uppercase;margin-bottom:6px;padding-bottom:5px;border-bottom:2px solid #059669;">STEP 2  ·  매수 실행</div>', unsafe_allow_html=True)
            if _buy_rows:
                with st.container(border=True): st.markdown('<div style="overflow-x:auto;"><table class="mint-table"><thead><tr><th style="text-align:left;">Asset</th><th>현재가</th><th>현재액</th><th>목표%</th><th>목표액</th><th>매수금액</th><th style="text-align:center;">Action</th><th>수량</th></tr></thead><tbody>' + _buy_rows + '</tbody></table></div>', unsafe_allow_html=True)
                st.markdown(apply_theme(f'<div style="background:rgba({r_c},{g_c},{b_c},0.06);border:1px solid rgba({r_c},{g_c},{b_c},0.22);padding:8px 14px;margin-top:6px;"><span style="font-family:DM Mono,monospace;font-size:0.62em;color:{main_color};font-weight:600;">총 매수 ${min(_total_buy_needed, _available_cash):,.0f}</span>{f"  <span style=\'color:{tc_label};\'>잔여 현금 ${max(_remaining_cash, 0):,.0f}</span>" if max(_remaining_cash, 0) > 1 else ""}</div>'), unsafe_allow_html=True)
            else: st.markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.09);padding:20px;text-align:center;"><span style="font-family:DM Mono,monospace;font-size:0.72em;color:#CCCCCC;">매수 항목 없음</span></div>', unsafe_allow_html=True)

        _hold_items = [a for a in ASSET_LIST if abs(_s_diff[a]) <= (_s_px[a] * 0.05 if a != 'CASH' else 1.0) and (_s_vals[a] > 0 or _s_tgtw.get(a, 0) > 0)]
        if _hold_items: st.markdown(f'<div style="display:flex;align-items:center;gap:10px;margin-top:10px;padding:8px 14px;background:#FAFAF7;border:1px solid rgba(0,0,0,0.09);"><span style="font-family:DM Mono,monospace;font-size:0.58em;color:{tc_label};letter-spacing:0.14em;text-transform:uppercase;white-space:nowrap;">HOLD</span><div style="display:flex;gap:4px;flex-wrap:wrap;">{" ".join([f"<span style=\'background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);font-family:DM Mono,monospace;font-size:0.68em;color:{tc_label};padding:2px 10px;\'>{a}</span>" for a in _hold_items])}</div></div>', unsafe_allow_html=True)

    st.markdown(apply_theme(f'<div style="background:#111118;border-left:4px solid {r_acc};padding:13px 0;margin-bottom:14px;display:flex;align-items:center;overflow-x:auto;"><div style="padding:0 20px 0 16px;border-right:1px solid rgba(255,255,255,0.06);flex-shrink:0;"><div style="font-family:DM Mono,monospace;font-size:0.52em;color:rgba(255,255,255,0.3);letter-spacing:0.22em;text-transform:uppercase;margin-bottom:2px;">AMLS V4.5</div><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.1em;font-weight:800;color:#FFFFFF;letter-spacing:-0.3px;line-height:1;">Portfolio</div></div>{_kv("Total NAV", f"${total_val_usd:,.2f}", "#FFFFFF", f"₩{total_val_krw:,.0f}")}{_kv("USD / KRW", f"₩{cur_fx:,.0f}", "rgba(255,255,255,0.65)", "환율")}{_kv("P & L", f"{pnl_pct:+.2f}%", "#6EE7B7" if pnl_pct >= 0 else "#FCA5A5", f"{"▲" if pnl_pct >= 0 else "▼"} ${pnl_usd:,.0f}")}{_kv("Regime", f"R{curr_regime}  {regime_info[curr_regime][1]}", r_acc)}{_kv("투자원금", f"${invested_cost:,.0f}", "rgba(255,255,255,0.65)", "취득원가")}<div style="margin-left:auto;padding:0 16px;flex-shrink:0;"><span class="live-pulse" style="font-family:DM Mono,monospace;font-size:0.58em;color:#6EE7B7;letter-spacing:0.06em;">{rt_label}</span></div></div>'), unsafe_allow_html=True)

    if display_mode == "PC":
        _gi_col, _gb_col = st.columns([st.session_state.lc_goal_inp, 100 - st.session_state.lc_goal_inp])
        with _gi_col:
            new_goal = st.number_input("목표금액", min_value=1000.0, max_value=100_000_000.0, value=st.session_state.goal_usd, step=1000.0, format="%.0f", key="goal_input", label_visibility="collapsed")
            if new_goal != st.session_state.goal_usd: st.session_state.goal_usd = new_goal; st.rerun()
            st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.6em;color:{tc_label};text-align:center;margin-top:-4px;">목표 금액 (USD)</div>', unsafe_allow_html=True)
        with _gb_col: st.markdown(_goal_tracker_html(), unsafe_allow_html=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        _col_l, _col_r = st.columns([st.session_state.lc_lr_split, 100 - st.session_state.lc_lr_split])
        with _col_l:
            with st.container(border=True):
                st.markdown(_sl("Position Input"), unsafe_allow_html=True)
                _pf_editor(st.session_state.lc_editor_h)
                if st.session_state.lc_show_lp:
                    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
                    st.markdown(_sl("Live Prices"), unsafe_allow_html=True); st.markdown(_lp_build(), unsafe_allow_html=True)
                if st.session_state.lc_show_qo:
                    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
                    st.markdown(_sl("Quick Orders"), unsafe_allow_html=True)
                    _sells, _buys = _sells_buys(); _qo1, _qo2 = st.columns(2)
                    with _qo1: _qo_build(_qo1, "🔴  SELL", _sells, "#DC2626", "rgba(220,38,38,0.03)")
                    with _qo2: _qo_build(_qo2, "🟢  BUY", _buys, "#059669", "rgba(5,150,105,0.03)")
        with _col_r:
            if st.session_state.lc_show_reg: st.markdown(_regime_card_html(horizontal=True), unsafe_allow_html=True); st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            _pie_charts(); st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            _rc1, _rc2 = st.columns([st.session_state.lc_delta_wt, 100 - st.session_state.lc_delta_wt])
            with _rc1: _delta_bar()
            with _rc2: _target_weights_block()
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown(apply_theme(f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;"><div style="width:2px;height:12px;background:{main_color};flex-shrink:0;"></div><span style="font-family:DM Mono,monospace;font-size:0.58em;font-weight:600;color:{tc_heading};letter-spacing:0.2em;text-transform:uppercase;">Rebalancing Matrix</span><div style="flex:1;height:1px;background:rgba(0,0,0,0.09);"></div><span style="font-family:DM Mono,monospace;font-size:0.56em;color:{tc_label};">R{curr_regime} · {regime_info[curr_regime][1]} · ⏱ {last_update_time}</span></div>'), unsafe_allow_html=True)
        _rebalancing_matrix()

    elif display_mode == "Tablet":
        st.markdown(f"""<style>.main .block-container {{ max-width: 1340px !important; padding: 1rem 0.8rem !important; }} .stApp {{ font-size: 12px !important; }} [data-testid="stButton"] > button {{ padding: 8px 12px !important; }} [data-testid="stDataEditor"] td, [data-testid="stDataEditor"] th {{ font-size: 0.88em !important; padding: 6px 8px !important; }} .mint-table td {{ padding: 9px 10px !important; font-size: 0.84em !important; }} .mint-table th {{ padding: 8px 10px !important; font-size: 0.7em !important; }}</style>""", unsafe_allow_html=True)
        _tgi, _tgb = st.columns([1, 3.5])
        with _tgi:
            new_goal = st.number_input("목표금액", min_value=1000.0, max_value=100_000_000.0, value=st.session_state.goal_usd, step=1000.0, format="%.0f", key="goal_input", label_visibility="collapsed")
            if new_goal != st.session_state.goal_usd: st.session_state.goal_usd = new_goal; st.rerun()
            st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.68em;color:{tc_label};text-align:center;margin-top:-4px;">목표 금액 (USD)</div>', unsafe_allow_html=True)
        with _tgb: st.markdown(_goal_tracker_html(), unsafe_allow_html=True)
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown(_regime_card_html(horizontal=True), unsafe_allow_html=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        _tc_l, _tc_r = st.columns([1, 1.4])
        with _tc_l:
            with st.container(border=True):
                st.markdown(_sl("Position Input"), unsafe_allow_html=True); _pf_editor(400)
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                st.markdown(_sl("Live Prices"), unsafe_allow_html=True); st.markdown(_lp_build(), unsafe_allow_html=True)
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                st.markdown(_sl("Quick Orders"), unsafe_allow_html=True)
                _sells, _buys = _sells_buys(); _tqo1, _tqo2 = st.columns(2)
                with _tqo1: _qo_build(_tqo1, "🔴  SELL", _sells, "#DC2626", "rgba(220,38,38,0.03)")
                with _tqo2: _qo_build(_tqo2, "🟢  BUY", _buys, "#059669", "rgba(5,150,105,0.03)")
        with _tc_r:
            _pie_charts(); st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            _tr1, _tr2 = st.columns(2)
            with _tr1: _delta_bar()
            with _tr2: _target_weights_block()
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        st.markdown(apply_theme(f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;"><div style="width:2px;height:14px;background:{main_color};flex-shrink:0;"></div><span style="font-family:DM Mono,monospace;font-size:0.66em;font-weight:600;color:{tc_heading};letter-spacing:0.18em;text-transform:uppercase;">Rebalancing Matrix</span><div style="flex:1;height:1px;background:rgba(0,0,0,0.09);"></div><span style="font-family:DM Mono,monospace;font-size:0.62em;color:{tc_label};">R{curr_regime} · {regime_info[curr_regime][1]}</span></div>'), unsafe_allow_html=True)
        _rebalancing_matrix()

    elif display_mode == "Mobile":
        st.markdown(f"""<style>.main .block-container {{ max-width: 460px !important; padding: 0.4rem 0.3rem 2rem !important; margin: 0 auto !important; }} .stApp {{ font-size: 11px !important; }} [data-testid="stDataEditor"] td, [data-testid="stDataEditor"] th {{ font-size: 0.88em !important; padding: 8px 6px !important; }} [data-testid="stButton"] > button {{ padding: 10px 14px !important; min-height: 40px !important; }} [data-testid="stNumberInput"] input {{ font-size: 1em !important; min-height: 40px !important; }} .mint-table td {{ padding: 9px 8px !important; font-size: 0.82em !important; }} .mint-table th {{ padding: 7px 8px !important; font-size: 0.68em !important; }}</style>""", unsafe_allow_html=True)
        new_goal = st.number_input("🎯 목표 금액 (USD)", min_value=1000.0, max_value=100_000_000.0, value=st.session_state.goal_usd, step=1000.0, format="%.0f", key="goal_input")
        if new_goal != st.session_state.goal_usd: st.session_state.goal_usd = new_goal; st.rerun()
        _goal, _pct_raw = st.session_state.goal_usd, (total_val_usd / st.session_state.goal_usd * 100) if st.session_state.goal_usd > 0 else 0.0
        _pct = min(_pct_raw, 100.0)
        if _pct_raw > 100.0: _gc, _gbadge = "#059669", "🏆 ACHIEVED"
        elif _pct >= 75: _gc, _gbadge = main_color, "⚡ 75%+"
        elif _pct >= 50: _gc, _gbadge = "#D97706", "📈 ON TRACK"
        else: _gc, _gbadge = "#94A3B8", "🌱 GROWING"
        _gr, _gg, _gb = hex_to_rgb(_gc)
        st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.11);border-left:4px solid {_gc};padding:14px 16px;margin-bottom:10px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;"><span style="font-family:DM Mono,monospace;font-size:0.62em;color:{tc_label};letter-spacing:0.16em;text-transform:uppercase;">Goal Tracker</span><span style="font-family:DM Mono,monospace;font-size:0.6em;background:rgba({_gr},{_gg},{_gb},0.1);border:1px solid rgba({_gr},{_gg},{_gb},0.28);color:{_gc};padding:2px 10px;">{_gbadge}</span></div><div style="height:10px;background:rgba(0,0,0,0.07);margin-bottom:8px;"><div style="height:10px;width:{_pct:.2f}%;background:linear-gradient(90deg,rgba({_gr},{_gg},{_gb},0.4),{_gc});"></div></div><div style="display:flex;justify-content:space-between;align-items:baseline;"><div><div style="font-family:DM Mono,monospace;font-size:0.54em;color:{tc_label};text-transform:uppercase;">현재 / 목표</div><div style="font-family:DM Mono,monospace;font-size:0.9em;color:{tc_body};font-variant-numeric:tabular-nums;">${total_val_usd:,.0f} / ${_goal:,.0f}</div></div><span style="font-family:DM Mono,monospace;font-size:2.2em;font-weight:400;color:{_gc};font-variant-numeric:tabular-nums;letter-spacing:-1.5px;line-height:1;">{_pct_raw:.1f}%</span></div></div>'), unsafe_allow_html=True)
        st.markdown(_regime_card_html(horizontal=False), unsafe_allow_html=True)
        with st.container(border=True): st.markdown(_sl("Position Input"), unsafe_allow_html=True); _pf_editor(400)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        with st.container(border=True): st.markdown(_sl("Live Prices"), unsafe_allow_html=True); st.markdown(_lp_build(), unsafe_allow_html=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(_sl("Quick Orders"), unsafe_allow_html=True); _sells, _buys = _sells_buys(); _mqo1, _mqo2 = st.columns(2)
            with _mqo1: _qo_build(_mqo1, "🔴  SELL", _sells, "#DC2626", "rgba(220,38,38,0.03)")
            with _mqo2: _qo_build(_mqo2, "🟢  BUY", _buys, "#059669", "rgba(5,150,105,0.03)")
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True); _target_weights_block()
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        _pie_colors_m, _pie_cfg_m = [line_c,'#B0B0BE','#34D399','#6EE7B7','#A7F3D0','#059669','#047857','#065F46','#D1FAE5'], dict(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(family="DM Mono", color=t_color), showlegend=True, legend=dict(orientation='h', x=0.5, xanchor='center', y=-0.12, font=dict(size=9, family='DM Mono'), bgcolor='rgba(0,0,0,0)'), margin=dict(l=0, r=0, t=28, b=50), height=240)
        _lcur_m, _vcur_m = [a for a in ASSET_LIST if curr_vals[a] > 0], [curr_vals[a] for a in ASSET_LIST if curr_vals[a] > 0]
        if sum(_vcur_m) > 0:
            _fm = go.Figure(go.Pie(labels=_lcur_m, values=_vcur_m, hole=.52, textinfo='percent', textfont=dict(size=9), marker=dict(colors=_pie_colors_m, line=dict(color='#FAFAF7', width=1.5))))
            _fm.update_layout(title=dict(text="Current Allocation", font=dict(family="DM Mono", size=12, color=t_color), x=0.5, xanchor='center'), **_pie_cfg_m)
            with st.container(border=True): st.plotly_chart(_fm, use_container_width=True)
        _ltgt_m, _vtgt_m = [a for a in ASSET_LIST if target_weights.get(a, 0) > 0], [target_weights[a] for a in ASSET_LIST if target_weights.get(a, 0) > 0]
        _ft_m = go.Figure(go.Pie(labels=_ltgt_m, values=_vtgt_m, hole=.52, textinfo='percent', textfont=dict(size=9), marker=dict(colors=_pie_colors_m, line=dict(color='#FAFAF7', width=1.5))))
        _ft_m.update_layout(title=dict(text=f"Target  R{curr_regime}", font=dict(family="DM Mono", size=12, color=t_color), x=0.5, xanchor='center'), **_pie_cfg_m)
        with st.container(border=True): st.plotly_chart(_ft_m, use_container_width=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown(apply_theme(f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;"><div style="width:2px;height:12px;background:{main_color};flex-shrink:0;"></div><span style="font-family:DM Mono,monospace;font-size:0.62em;font-weight:600;color:{tc_heading};letter-spacing:0.18em;text-transform:uppercase;">Rebalancing</span><div style="flex:1;height:1px;background:rgba(0,0,0,0.09);"></div></div>'), unsafe_allow_html=True)
        if total_val_usd > 0:
            for asset in ASSET_LIST:
                _shs, _avgp, _curp, _curv, _tgtw = st.session_state.portfolio[asset]['shares'], st.session_state.portfolio[asset]['avg_price'], current_prices[asset] if current_prices[asset] > 0 else 1.0, curr_vals[asset], target_weights.get(asset, 0.0)
                _tgtv, _diff, _curw = total_val_usd * _tgtw, diff_vals[asset], (_curv / total_val_usd * 100) if total_val_usd > 0 else 0
                if _tgtw == 0 and _curv == 0 and _shs == 0: continue
                if asset == 'CASH': _ret, _retstr, _retc = 0.0, "—", "#9494A0"
                else: _ret, _retstr, _retc = (_curp / _avgp - 1) * 100 if _avgp > 0 else 0.0, f"{(_curp / _avgp - 1) * 100:+.1f}%" if _avgp > 0 else "0.0%", C_GREEN if (_curp / _avgp - 1) >= 0 else C_RED
                if abs(_diff) < _curp * 0.05 and asset != 'CASH': _act_txt, _act_c, _rbg = "HOLD", "#9494A0", "#FAFAF7"
                elif abs(_diff) < 1.0 and asset == 'CASH': _act_txt, _act_c, _rbg = "HOLD", "#9494A0", "#FAFAF7"
                elif _diff > 0: _act_txt, _act_c, _rbg = "▲ BUY", "#059669", "rgba(5,150,105,0.035)"
                else: _act_txt, _act_c, _rbg = "▼ SELL", "#DC2626", "rgba(220,38,38,0.035)"
                _delta_str = f"+${_diff:,.0f}" if _diff > 0 else f"-${abs(_diff):,.0f}" if _diff < 0 else "—"
                st.markdown(apply_theme(f'<div style="background:{_rbg};border:1px solid rgba(0,0,0,0.09);border-left:3px solid {_act_c};padding:10px 14px;margin-bottom:5px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;"><span style="font-family:DM Mono,monospace;font-size:0.88em;font-weight:700;color:#059669;">{asset}</span><span style="font-family:DM Mono,monospace;font-size:0.76em;font-weight:700;color:{_act_c};background:rgba(0,0,0,0.04);padding:3px 10px;border:1px solid {_act_c}40;">{_act_txt}</span></div><div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:4px;"><div><div style="font-family:DM Mono,monospace;font-size:0.52em;color:{tc_label};text-transform:uppercase;">평가액</div><div style="font-family:DM Mono,monospace;font-size:0.78em;color:{tc_body};font-variant-numeric:tabular-nums;">${_curv:,.0f} <span style="font-size:0.7em;color:{tc_label};">({_curw:.0f}%)</span></div></div><div><div style="font-family:DM Mono,monospace;font-size:0.52em;color:{tc_label};text-transform:uppercase;">목표 %</div><div style="font-family:DM Mono,monospace;font-size:0.78em;color:{main_color};font-weight:600;">{_tgtw*100:.0f}%</div></div><div><div style="font-family:DM Mono,monospace;font-size:0.52em;color:{tc_label};text-transform:uppercase;">수익률</div><div style="font-family:DM Mono,monospace;font-size:0.78em;color:{_retc};font-weight:600;">{_retstr}</div></div><div><div style="font-family:DM Mono,monospace;font-size:0.52em;color:{tc_label};text-transform:uppercase;">Δ 금액</div><div style="font-family:DM Mono,monospace;font-size:0.78em;color:{_act_c};font-weight:600;font-variant-numeric:tabular-nums;">{_delta_str}</div></div></div></div>'), unsafe_allow_html=True)
        else: st.markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.09);padding:28px;text-align:center;"><span style="font-family:DM Mono,monospace;font-size:0.8em;color:#CCCCCC;">포지션을 입력하면 리밸런싱 정보가 표시됩니다.</span></div>', unsafe_allow_html=True)


# ==========================================
# 라우팅 3. 12-Pack Radar
# ==========================================
elif page == "🍫 12-Pack Radar":
    df_view  = df.iloc[-120:]
    qqq_rsi  = last_row['QQQ_RSI']
    qqq_dd   = last_row['QQQ_DD']
    cnn_fgi  = fetch_fear_and_greed()
    if cnn_fgi is not None: fg_score = cnn_fgi
    else: fg_score = (max(0, min(100, 100-(last_row['^VIX']-12)/28*100)) + max(0, min(100, (qqq_dd+0.20)/0.20*100)) + max(0, min(100, qqq_rsi)))/3

    sec_names = {'XLK':'TECH','XLV':'HEALTH','XLF':'FIN','XLY':'CONS','XLC':'COMM','XLI':'IND','XLP':'STAPLE','XLE':'ENGY','XLU':'UTIL','XLRE':'REAL','XLB':'MAT'}
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

    if risk_cnt >= 3: radar_status, radar_msg, radar_color = "극단적 위험 구간 (Risk-Off)", "시장에 극단적인 공포가 덮쳤습니다. 현재 복수의 매크로 지표가 시스템 리스크를 강하게 경고하고 있습니다. 단순한 조정을 넘어선 투매 구간일 확률이 높으니, 모든 레버리지 포지션을 해제하고 현금과 달러, 금 등 안전 자산 비중을 최대로 늘려 폭풍우가 지나가기를 기다리셔야 합니다.", "#DC2626"
    elif warn_cnt >= 4 or risk_cnt >= 1: radar_status, radar_msg, radar_color = "변동성 주의 (Warning)", "시장 곳곳에서 균열의 조짐이 감지되고 풀 지표가 점차 악화되고 있습니다. 신규 매수는 철저히 보류하시고, 포트폴리오의 리스크 노출도를 점검하며 보수적인 관망 자세를 유지하는 것이 좋습니다.", "#D97706"
    else: radar_status, radar_msg, radar_color = "안정적 순항 (Safe)", "현재 글로벌 매크로 지표와 시장 심리가 모두 안정적인 궤도에 올라와 있습니다. 추세를 꺾을 만한 시스템 리스크가 보이지 않으니, AMLS 알고리즘이 제시하는 비중에 맞춰 자신감 있게 추세 추종 전략을 전개하시기 바랍니다.", main_color

    total_signals = risk_cnt + warn_cnt + safe_cnt
    risk_pct  = int(risk_cnt  / total_signals * 100) if total_signals else 0
    warn_pct  = int(warn_cnt  / total_signals * 100) if total_signals else 0
    safe_pct  = int(safe_cnt  / total_signals * 100) if total_signals else 0

    st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);border-left:3px solid {radar_color};padding:14px 20px;margin-bottom:12px;"><div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap;"><div style="flex:3;min-width:260px;"><div style="font-family:DM Mono,monospace;font-size:0.57em;color:#9494A0;letter-spacing:0.18em;text-transform:uppercase;margin-bottom:4px;">Macro Signal Status</div><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.2em;font-weight:700;letter-spacing:-0.3px;font-style:normal;coloric;color:{radar_color};line-height:1.1;margin-bottom:8px;">{radar_status}</div><div style="font-family:DM Sans,sans-serif;font-size:0.82em;color:#4A4A57;line-height:1.6;">{radar_msg}</div></div><div style="flex:1;min-width:180px;"><div style="display:flex;gap:6px;margin-bottom:8px;"><div style="flex:1;border-top:2px solid #DC2626;padding:8px 6px;background:rgba(220,38,38,0.04);"><div style="font-family:DM Mono,monospace;font-size:1.5em;color:#DC2626;line-height:1;">{risk_cnt}</div><div style="font-family:DM Mono,monospace;font-size:0.57em;color:#9494A0;letter-spacing:0.14em;text-transform:uppercase;">Risk</div></div><div style="flex:1;border-top:2px solid #D97706;padding:8px 6px;background:rgba(217,119,6,0.04);"><div style="font-family:DM Mono,monospace;font-size:1.5em;color:#D97706;line-height:1;">{warn_cnt}</div><div style="font-family:DM Mono,monospace;font-size:0.57em;color:#9494A0;letter-spacing:0.14em;text-transform:uppercase;">Warn</div></div><div style="flex:1;border-top:2px solid {main_color};padding:8px 6px;background:rgba({r_c},{g_c},{b_c},0.04);"><div style="font-family:DM Mono,monospace;font-size:1.5em;color:{main_color};line-height:1;">{safe_cnt}</div><div style="font-family:DM Mono,monospace;font-size:0.57em;color:#9494A0;letter-spacing:0.14em;text-transform:uppercase;">Safe</div></div></div><div style="height:4px;background:rgba(0,0,0,0.07);display:flex;overflow:hidden;"><div style="width:{risk_pct}%;background:#DC2626;"></div><div style="width:{warn_pct}%;background:#D97706;"></div><div style="width:{safe_pct}%;background:{main_color};"></div></div><div style="display:flex;justify-content:space-between;font-family:DM Mono,monospace;font-size:0.58em;color:#9494A0;margin-top:3px;"><span>{risk_pct}% risk</span><span>{warn_pct}% warn</span><span>{safe_pct}% safe</span></div></div></div></div>'), unsafe_allow_html=True)

    def _badge(label, color, icon):
        bg, fg = {'green':(f'rgba({r_c},{g_c},{b_c},0.10)', main_color), 'orange':('rgba(217,119,6,0.10)', '#D97706'), 'red':('rgba(220,38,38,0.10)', '#DC2626'), 'blue':('rgba(59,130,246,0.10)', '#3B82F6')}[color]
        return f'<span style="background:{bg};color:{fg};border:1px solid {fg};padding:2px 7px;font-size:0.68em;font-weight:500;font-family:DM Mono,monospace;letter-spacing:0.05em;white-space:nowrap;">{icon} {label}</span>'

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

    gauge_steps = [{'range':[0,25], 'color':"rgba(220,38,38,0.4)"}, {'range':[25,45], 'color':"rgba(217,119,6,0.3)"}, {'range':[45,55], 'color':"rgba(0,0,0,0.04)"}, {'range':[55,75], 'color':f"rgba({r_c},{g_c},{b_c},0.3)"}, {'range':[75,100],'color':f"rgba({r_c},{g_c},{b_c},0.5)"}]

    def r_head(num, title, badge, url, desc): return f'<div style="border-bottom:1px solid rgba(0,0,0,0.08);padding-bottom:8px;margin-bottom:8px;"><div style="display:flex;align-items:center;gap:4px;margin-bottom:4px;"><span style="font-family:DM Mono,monospace;font-size:0.62em;color:#9494A0;min-width:18px;">{num:02d}</span><a href="{url}" target="_blank" style="text-decoration:none;flex:1;"><span style="font-family:DM Mono,monospace;font-size:0.66em;font-weight:500;color:#2C2C35;letter-spacing:0.08em;text-transform:uppercase;">{title}&nbsp;↗</span></a>{badge}</div><div style="font-family:DM Sans,sans-serif;font-size:0.73em;color:#6B6B7A;line-height:1.4;letter-spacing:-0.1px;">{desc}</div></div>'

    row1 = st.columns(4)
    with row1[0]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(1, "DCA · RSI", b1, "https://kr.tradingview.com/chart/?symbol=NASDAQ:QQQ", "나스닥 100(QQQ)의 단기 과열 및 침체를 나타내는 RSI 지표. 30↓ 투매→매수기회, 70↑ 과열→신규진입중단.")), unsafe_allow_html=True)
            fig1=go.Figure(); fig1.add_trace(go.Scatter(x=df_view.index, y=df_view['QQQ_RSI'], line=dict(color=line_c, width=1.8))); fig1.add_hline(y=70, line_dash='dot', line_color='#B0B0BE', line_width=1); fig1.add_hline(y=30, line_dash='dot', line_color=rsi_low_c, line_width=1); fig1.update_layout(**radar_layout, showlegend=False); fig1.update_xaxes(**_ax_r); fig1.update_yaxes(range=[10,90], **_ax_r); st.plotly_chart(fig1, use_container_width=True)
    with row1[1]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(2, "Drawdown", b2, "https://kr.tradingview.com/chart/?symbol=NASDAQ:QQQ", "QQQ 52주 고점 대비 하락률. -10% 건전한 조정, -20% 돌파시 약세장 진입으로 즉각 방어 필요.")), unsafe_allow_html=True)
            fig2=go.Figure(); fig2.add_trace(go.Scatter(x=df_view.index, y=df_view['QQQ_DD'], fill='tozeroy', fillcolor='rgba(220,38,38,0.07)', line=dict(color='#DC2626', width=1.8))); fig2.update_layout(**radar_layout, showlegend=False); fig2.update_xaxes(**_ax_r); fig2.update_yaxes(tickformat='.0%', **_ax_r); st.plotly_chart(fig2, use_container_width=True)
    with row1[2]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(3, "Fear & Greed", b3, "https://edition.cnn.com/markets/fear-and-greed", "CNN Fear & Greed 지수. 극단적 공포 구간이 역사적 매수 기회, 극단적 탐욕 구간은 수익실현 시점.")), unsafe_allow_html=True)
            fig3=go.Figure(go.Indicator(mode="gauge+number", value=fg_score, domain={'x':[0,1],'y':[0,1]}, gauge={'axis':{'range':[0,100],'tickcolor':t_color},'bar':{'color':line_c,'thickness':0.2},'steps':gauge_steps,'borderwidth':0})); fig3.update_layout(height=200, margin=dict(l=15,r=15,t=10,b=10), paper_bgcolor=b_color, font=dict(family="DM Mono", color=t_color)); st.plotly_chart(fig3, use_container_width=True)
    with row1[3]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(4, "Sector 1M", b4, "https://finviz.com/map.ashx?t=sec", "월간 섹터 자금흐름. 방어주(유틸/필수소비/헬스) 강세시 경기침체 대비 시그널.")), unsafe_allow_html=True)
            fig4=go.Figure(go.Bar(x=sec_df['수익률'], y=sec_df['섹터'], orientation='h', marker_color=[dash_c if v<0 else line_c for v in sec_df['수익률']], marker_line_width=0)); fig4.update_layout(**radar_layout, showlegend=False); fig4.update_xaxes(**_ax_r); fig4.update_yaxes(**_ax_r); st.plotly_chart(fig4, use_container_width=True)

    row2 = st.columns(4)
    with row2[0]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(5, "Credit Spread", b5, "https://fred.stlouisfed.org/series/BAMLH0A0HYM2", "HYG/IEF 비율. 하이일드 채권이 국채 대비 약세면 스마트머니가 선제 이탈 중.")), unsafe_allow_html=True)
            fig5=go.Figure(); fig5.add_trace(go.Scatter(x=df_view.index, y=df_view['HYG_IEF_Ratio'], line=dict(color=line_c, width=1.8))); fig5.add_trace(go.Scatter(x=df_view.index, y=df_view['HYG_IEF_MA50'], line=dict(color=dash_c, dash='dot', width=1.1))); fig5.update_layout(**radar_layout, showlegend=False); fig5.update_xaxes(**_ax_r); fig5.update_yaxes(**_ax_r); st.plotly_chart(fig5, use_container_width=True)
    with row2[1]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(6, "Mkt Breadth", b6, "https://kr.tradingview.com/chart/?symbol=NASDAQ:QQQE", "QQQ(시총가중) vs QQQE(동일가중). 괴리 발생시 소수 대형주만 끌어올리는 가짜 상승 경고.")), unsafe_allow_html=True)
            fig6=go.Figure(); fig6.add_trace(go.Scatter(x=df_view.index, y=df_view['QQQ_20d_Ret'], name='QQQ', line=dict(color=line_c, width=1.8))); fig6.add_trace(go.Scatter(x=df_view.index, y=df_view['QQQE_20d_Ret'], name='QQQE', line=dict(color=dash_c, dash='dot', width=1.1))); fig6.update_layout(**radar_layout, showlegend=False); fig6.update_xaxes(**_ax_r); fig6.update_yaxes(tickformat='.0%', **_ax_r); st.plotly_chart(fig6, use_container_width=True)
    with row2[2]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(7, "Gold / Equity", b7, "https://kr.tradingview.com/chart/?symbol=AMEX:GLD", "GLD/SPY 비율. 금이 상대 강세면 기관의 Risk-Off 전환, 구조적 리스크 시그널.")), unsafe_allow_html=True)
            fig7=go.Figure(); fig7.add_trace(go.Scatter(x=df_view.index, y=df_view['GLD_SPY_Ratio'], line=dict(color=line_c, width=1.8))); fig7.add_trace(go.Scatter(x=df_view.index, y=df_view['GLD_SPY_MA50'], line=dict(color=dash_c, dash='dot', width=1.1))); fig7.update_layout(**radar_layout, showlegend=False); fig7.update_xaxes(**_ax_r); fig7.update_yaxes(**_ax_r); st.plotly_chart(fig7, use_container_width=True)
    with row2[3]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(8, "USD (UUP)", b8, "https://kr.tradingview.com/chart/?symbol=AMEX:UUP", "달러지수(UUP). 50일선 상향 돌파시 기술주 강한 하방압력, 주식비중 축소 정석.")), unsafe_allow_html=True)
            fig8=go.Figure(); fig8.add_trace(go.Scatter(x=df_view.index, y=df_view['UUP'], line=dict(color=line_c, width=1.8))); fig8.add_trace(go.Scatter(x=df_view.index, y=df_view['UUP_MA50'], line=dict(color=dash_c, dash='dot', width=1.1))); fig8.update_layout(**radar_layout, showlegend=False); fig8.update_xaxes(**_ax_r); fig8.update_yaxes(**_ax_r); st.plotly_chart(fig8, use_container_width=True)

    row3 = st.columns(4)
    with row3[0]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(9, "10Y Yield", b9, "https://kr.tradingview.com/chart/?symbol=TVC:US10Y", "미 10년물 금리. 50일선 상향 돌파시 나스닥 성장주에 강한 역풍, 레버리지 주의.")), unsafe_allow_html=True)
            fig9=go.Figure(); fig9.add_trace(go.Scatter(x=df_view.index, y=df_view['^TNX'], line=dict(color=line_c, width=1.8))); fig9.add_trace(go.Scatter(x=df_view.index, y=df_view['TNX_MA50'], line=dict(color=dash_c, dash='dot', width=1.1))); fig9.update_layout(**radar_layout, showlegend=False); fig9.update_xaxes(**_ax_r); fig9.update_yaxes(**_ax_r); st.plotly_chart(fig9, use_container_width=True)
    with row3[1]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(10, "Bitcoin", b10, "https://kr.tradingview.com/chart/?symbol=BINANCE:BTCUSD", "비트코인 트렌드. 50일선 하향시 글로벌 유동성 가뭄 선행 경고.")), unsafe_allow_html=True)
            fig10=go.Figure(); fig10.add_trace(go.Scatter(x=df_view.index, y=df_view['BTC-USD'], line=dict(color=line_c, width=1.8))); fig10.add_trace(go.Scatter(x=df_view.index, y=df_view['BTC_MA50'], line=dict(color=dash_c, dash='dot', width=1.1))); fig10.update_layout(**radar_layout, showlegend=False); fig10.update_xaxes(**_ax_r); fig10.update_yaxes(**_ax_r); st.plotly_chart(fig10, use_container_width=True)
    with row3[2]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(11, "Russell/SP500", b11, "https://kr.tradingview.com/chart/?symbol=AMEX:IWM", "IWM/SPY 비율. 중소형주 상대약세시 시장 내부 균열, TZA 전략 고려 가능.")), unsafe_allow_html=True)
            fig11=go.Figure(); fig11.add_trace(go.Scatter(x=df_view.index, y=df_view['IWM_SPY_Ratio'], line=dict(color=line_c, width=1.8))); fig11.add_trace(go.Scatter(x=df_view.index, y=df_view['IWM_SPY_MA50'], line=dict(color=dash_c, dash='dot', width=1.1))); fig11.update_layout(**radar_layout, showlegend=False); fig11.update_xaxes(**_ax_r); fig11.update_yaxes(**_ax_r); st.plotly_chart(fig11, use_container_width=True)
    with row3[3]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(12, "VIX Trend", b12, "https://kr.tradingview.com/chart/?symbol=CBOE:VIX", "VIX 추세. 50일선 상향 돌파시 변동성 확장 국면 진입, 시스템 패닉 시그널.")), unsafe_allow_html=True)
            fig12=go.Figure(); fig12.add_trace(go.Scatter(x=df_view.index, y=df_view['^VIX'], line=dict(color=line_c, width=1.8))); fig12.add_trace(go.Scatter(x=df_view.index, y=df_view['VIX_MA50'], line=dict(color=dash_c, dash='dot', width=1.1))); fig12.update_layout(**radar_layout, showlegend=False); fig12.update_xaxes(**_ax_r); fig12.update_yaxes(**_ax_r); st.plotly_chart(fig12, use_container_width=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown(apply_theme(f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;"><div style="width:2px;height:14px;background:{main_color};flex-shrink:0;"></div><span style="font-family:DM Mono,monospace;font-size:0.6em;font-weight:600;color:{tc_heading};letter-spacing:0.2em;text-transform:uppercase;">AI  Quant  Analyst  ·  12-Signal Synthesis</span><div style="flex:1;height:1px;background:rgba(0,0,0,0.10);"></div><span style="font-family:DM Mono,monospace;font-size:0.56em;color:{tc_label};">Powered by Google Gemini</span></div>'), unsafe_allow_html=True)
    _ai_col_l, _ai_col_r = st.columns([1, 2])
    with _ai_col_l:
        _sig_data = [("01 DCA·RSI", "BUY" if qqq_rsi<40 else ("OVER" if qqq_rsi>70 else "NEUTRAL"), f"QQQ RSI {qqq_rsi:.1f}", main_color if qqq_rsi<40 else ("#DC2626" if qqq_rsi>70 else "#9494A0")), ("02 Drawdown", "BEAR" if qqq_dd<-0.20 else ("CORR" if qqq_dd<-0.10 else "SAFE"), f"DD {qqq_dd*100:.1f}%", "#DC2626" if qqq_dd<-0.10 else main_color), ("03 Fear&Greed", "FEAR" if fg_score<30 else ("GREED" if fg_score>70 else "NEUTRAL"), f"FGI {fg_score:.0f}", main_color if fg_score<30 else ("#DC2626" if fg_score>70 else "#9494A0")), ("04 Sector", f"▲{top_sec}", f"▼{bot_sec}", main_color if top_sec not in ['UTIL','STAPLE','HEALTH'] else "#D97706"), ("05 Credit", "RISK-OFF" if last_row['HYG_IEF_Ratio']<last_row['HYG_IEF_MA50'] else "RISK-ON", "HYG/IEF ratio", "#DC2626" if last_row['HYG_IEF_Ratio']<last_row['HYG_IEF_MA50'] else main_color), ("06 Breadth", "NARROW" if (last_row['QQQ_20d_Ret']>0 and last_row['QQQE_20d_Ret']<0) else "BROAD", "QQQ vs QQQE", "#D97706" if (last_row['QQQ_20d_Ret']>0 and last_row['QQQE_20d_Ret']<0) else main_color), ("07 Gold/Equity", "GOLD↑" if last_row['GLD_SPY_Ratio']>last_row['GLD_SPY_MA50'] else "EQUITY↑", "GLD/SPY ratio", "#D97706" if last_row['GLD_SPY_Ratio']>last_row['GLD_SPY_MA50'] else main_color), ("08 USD", "USD↑" if last_row['UUP']>last_row['UUP_MA50'] else "USD↓", "UUP vs 50MA", "#DC2626" if last_row['UUP']>last_row['UUP_MA50'] else main_color), ("09 10Y Yield", "YIELD↑" if last_row['^TNX']>last_row['TNX_MA50'] else "YIELD↓", f"TNX {last_row['^TNX']:.2f}%", "#DC2626" if last_row['^TNX']>last_row['TNX_MA50'] else main_color), ("10 Bitcoin", "RISK-OFF" if last_row['BTC-USD']<last_row['BTC_MA50'] else "RISK-ON", "BTC vs 50MA", "#DC2626" if last_row['BTC-USD']<last_row['BTC_MA50'] else main_color), ("11 Russell/SP", "NARROW" if last_row['IWM_SPY_Ratio']<last_row['IWM_SPY_MA50'] else "BROAD", "IWM/SPY ratio", "#D97706" if last_row['IWM_SPY_Ratio']<last_row['IWM_SPY_MA50'] else main_color), ("12 VIX Trend", "EXPAND" if last_row['^VIX']>last_row['VIX_MA50'] else "SHRINK", f"VIX {last_row['^VIX']:.1f}", "#DC2626" if last_row['^VIX']>last_row['VIX_MA50'] else main_color)]
        _sig_rows = "".join([f'<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid rgba(0,0,0,0.05);"><span style="font-family:DM Mono,monospace;font-size:0.66em;color:{tc_label};">{_sn}</span><div style="text-align:right;"><span style="font-family:DM Mono,monospace;font-size:0.7em;font-weight:700;color:{_sc};">{_ss}</span><span style="font-family:DM Mono,monospace;font-size:0.58em;color:{tc_label};margin-left:6px;">{_sv}</span></div></div>' for _sn, _ss, _sv, _sc in _sig_data])
        with st.container(border=True): st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.56em;font-weight:600;color:{tc_label};letter-spacing:0.18em;text-transform:uppercase;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid rgba(0,0,0,0.09);">12 Signal Snapshot</div><div>{_sig_rows}</div><div style="display:flex;justify-content:space-between;margin-top:10px;padding-top:8px;border-top:1px solid rgba(0,0,0,0.08);"><span style="font-family:DM Mono,monospace;font-size:0.58em;color:#DC2626;">Risk {risk_cnt}개</span><span style="font-family:DM Mono,monospace;font-size:0.58em;color:#D97706;">Warn {warn_cnt}개</span><span style="font-family:DM Mono,monospace;font-size:0.58em;color:{main_color};">Safe {safe_cnt}개</span></div>', unsafe_allow_html=True)
    with _ai_col_r:
        if st.button("🤖  AI 종합 투자의견 생성", use_container_width=True, key="radar_ai_btn"):
            try:
                import google.generativeai as genai
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                _model = genai.GenerativeModel([m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods][0].replace('models/', ''))
                _prompt = f"너는 월스트리트 출신 퀀트 애널리스트야. AMLS V4.5 시스템의 12개 매크로 신호를 분석해서 투자의견을 내줘.\n[현재 레짐] R{curr_regime} — {regime_info[curr_regime][1]}\n[신호 요약] Risk {risk_cnt}개 / Warn {warn_cnt}개 / Safe {safe_cnt}개\n[12개 실시간 신호]\n1. QQQ RSI: {qqq_rsi:.1f}\n2. QQQ 고점대비 낙폭: {qqq_dd*100:.1f}%\n3. CNN Fear&Greed: {fg_score:.0f}\n4. 주도섹터: {top_sec} / 약세섹터: {bot_sec}\n5. 신용스프레드 HYG/IEF: {'위험' if last_row['HYG_IEF_Ratio']<last_row['HYG_IEF_MA50'] else '안전'}\n6. 시장폭: {'좁아짐' if (last_row['QQQ_20d_Ret']>0 and last_row['QQQE_20d_Ret']<0) else '넓음'}\n7. 금/주식 비율: {'금강세' if last_row['GLD_SPY_Ratio']>last_row['GLD_SPY_MA50'] else '주식강세'}\n8. 달러: {'강세' if last_row['UUP']>last_row['UUP_MA50'] else '약세'}\n9. 미10년물금리 {last_row['^TNX']:.2f}%: {'상승' if last_row['^TNX']>last_row['TNX_MA50'] else '하락'}\n10. 비트코인: {'위험' if last_row['BTC-USD']<last_row['BTC_MA50'] else '안전'}\n11. 러셀2000/S&P500: {'약세' if last_row['IWM_SPY_Ratio']<last_row['IWM_SPY_MA50'] else '강세'}\n12. VIX {last_row['^VIX']:.1f}: {'확장' if last_row['^VIX']>last_row['VIX_MA50'] else '축소'}\n아래 3개 섹션으로 구성해서 한국어로 작성해줘:\n**① 시장 환경 진단**\n**② 핵심 리스크 & 기회 요인**\n**③ AMLS 전략 투자의견**"
                with st.spinner("AI 분석 중..."): _response = _model.generate_content(_prompt)
                st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.11);border-left:4px solid {main_color};padding:20px 24px;"><div style="font-family:DM Mono,monospace;font-size:0.56em;color:{tc_label};letter-spacing:0.16em;text-transform:uppercase;margin-bottom:12px;">AI Quant Analysis  ·  {last_update_time}</div><div style="font-family:DM Sans,sans-serif;font-size:0.88em;color:{tc_body};line-height:1.8;">{_response.text}</div></div>'), unsafe_allow_html=True)
            except KeyError: st.error("🚨 GEMINI_API_KEY 누락")
            except Exception as _e: st.error(f"🚨 오류: {str(_e)}")
        else:
            st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);border-left:3px solid rgba(0,0,0,0.12);padding:24px 26px;"><div style="font-family:DM Mono,monospace;font-size:0.58em;color:{tc_label};letter-spacing:0.14em;text-transform:uppercase;margin-bottom:12px;">How It Works</div><div style="font-family:DM Sans,sans-serif;font-size:0.86em;color:{tc_muted};line-height:1.75;">버튼을 누르면 Google Gemini AI가 위 12개 실시간 지표를<br><b style="color:{tc_body};">① 시장환경 진단</b> →  <b style="color:{tc_body};">② 리스크·기회 요인</b> →  <b style="color:{tc_body};">③ AMLS 투자의견</b><br>3단계로 종합 분석합니다.</div><div style="margin-top:16px;padding:10px 14px;background:rgba({r_c},{g_c},{b_c},0.07);border-left:2px solid {main_color};"><span style="font-family:DM Mono,monospace;font-size:0.68em;color:{tc_body};">현재 레짐: <b style="color:{main_color};">R{curr_regime}</b>  ·  Risk <b style="color:#DC2626;">{risk_cnt}</b>  Warn <b style="color:#D97706;">{warn_cnt}</b>  Safe <b style="color:{main_color};">{safe_cnt}</b></span></div></div>'), unsafe_allow_html=True)

# ==========================================
# 라우팅 4. Backtest Lab
# ==========================================
elif page == "📈 Backtest Lab":
    st.markdown(apply_theme("""<div style="display:flex;align-items:center;gap:16px;margin-bottom:20px;"><div><h2 style="font-family:'Plus Jakarta Sans';font-size:1.7em;color:#0F172A;margin:0;">📈 Backtest Lab</h2><div style="font-family:'DM Mono';font-size:0.65em;color:#4A5568;letter-spacing:0.16em;text-transform:uppercase;margin-top:3px;">Strategy Simulator  ·  Historical Analysis</div></div></div>"""), unsafe_allow_html=True)
    panel_cfg, panel_res = st.columns([1, 2.8])
    with panel_cfg:
        with st.container(border=True):
            st.markdown("""<div style="font-family:'DM Mono';font-size:0.62em;color:#4A5568;margin-bottom:14px;letter-spacing:0.2em;text-transform:uppercase;">⚙  Config</div>""", unsafe_allow_html=True)
            bt_start = st.date_input("Start Date", datetime(2020, 1, 1), key="bt_start_input")
            bt_end   = st.date_input("End Date", datetime.today(), key="bt_end_input")
            monthly_cont = st.number_input("월 적립금 ($)", value=2000, step=500, key="bt_monthly_input")

    with panel_res:
        with st.spinner("시뮬레이션 가동 중..."):
            bt_df = load_custom_backtest_data(bt_start, bt_end)
            if bt_df.empty: st.error("해당 기간의 데이터가 부족합니다.")
            else:
                daily_ret = bt_df[['QQQ','TQQQ','SOXL','USD','QLD','SSO','SPY','SMH','GLD']].pct_change().fillna(0)
                w_orig = get_weights_v45(bt_df['Regime'].iloc[0], False)
                val_o, val_q, val_qld, val_tqqq = 10000, 10000, 10000, 10000
                hist_o, hist_q, hist_qld, hist_tqqq, invested, curr_inv = [val_o], [val_q], [val_qld], [val_tqqq], [10000], 10000

                for i in range(1, len(bt_df)):
                    today, yesterday = bt_df.index[i], bt_df.index[i-1]
                    val_o *= (1 + sum(w_orig.get(t,0) * daily_ret[t].iloc[i] for t in w_orig if t in daily_ret.columns))
                    val_q *= (1 + daily_ret['QQQ'].iloc[i])
                    val_qld *= (1 + daily_ret['QLD'].iloc[i])
                    val_tqqq *= (1 + daily_ret['TQQQ'].iloc[i])
                    if today.month != yesterday.month:
                        val_o += monthly_cont; val_q += monthly_cont; val_qld += monthly_cont; val_tqqq += monthly_cont; curr_inv += monthly_cont
                    hist_o.append(val_o); hist_q.append(val_q); hist_qld.append(val_qld); hist_tqqq.append(val_tqqq); invested.append(curr_inv)
                    w_orig = get_weights_v45(bt_df['Regime'].iloc[i], (bt_df['SMH'].iloc[i] > bt_df['SMH_MA50'].iloc[i]) and (bt_df['SMH_3M_Ret'].iloc[i] > 0.05) and (bt_df['SMH_RSI'].iloc[i] > 50))

                res_df = pd.DataFrame({'V4.5': hist_o, 'QQQ': hist_q, 'QLD': hist_qld, 'TQQQ': hist_tqqq, 'Invested': invested}, index=bt_df.index)
                days = (res_df.index[-1] - res_df.index[0]).days
                def calc_m(s, i_s): return (s.iloc[-1]/i_s.iloc[-1]-1), ((s.iloc[-1]/i_s.iloc[-1])**(365.25/days)-1 if days>0 else 0), (((s/s.cummax())-1).min())
                
                ret_o, cagr_o, mdd_o = calc_m(res_df['V4.5'], res_df['Invested'])
                ret_q, cagr_q, mdd_q = calc_m(res_df['QQQ'], res_df['Invested'])
                ret_t, cagr_t, mdd_t = calc_m(res_df['TQQQ'], res_df['Invested'])

                mc1, mc2, mc3 = st.columns(3)
                def _mc_html(t, r, c, m, main=False): return f'<div style="background:{"rgba("+str(r_c)+","+str(g_c)+","+str(b_c)+",0.06)" if main else "#FFFFFF"};border:1px solid rgba(0,0,0,0.08);border-top:2px solid {"rgba("+str(r_c)+","+str(g_c)+","+str(b_c)+",0.55)" if main else "rgba(0,0,0,0.12)"};border-radius:14px;padding:16px 18px;"><div style="font-size:0.62em;color:#4A5568;margin-bottom:6px;">{t}</div><div style="font-size:1.6em;color:#0F172A;margin-bottom:6px;">CAGR {c*100:.1f}%</div><div style="font-size:0.72em;color:#4A5568;">누적 <b style="color:{"#059669" if r>=0 else "#EF4444"};">{r*100:.1f}%</b>  MDD <b style="color:#EF4444;">{m*100:.1f}%</b></div></div>'
                with mc1: st.markdown(_mc_html("✦ AMLS V4.5", ret_o, cagr_o, mdd_o, True), unsafe_allow_html=True)
                with mc2: st.markdown(_mc_html("QQQ", ret_q, cagr_q, mdd_q), unsafe_allow_html=True)
                with mc3: st.markdown(_mc_html("TQQQ", ret_t, cagr_t, mdd_t), unsafe_allow_html=True)

                fig_eq = go.Figure()
                fig_eq.add_trace(go.Scatter(x=res_df.index, y=res_df['QQQ'], name='QQQ', line=dict(color='#CBD5E1', width=1.2, dash='dot')))
                fig_eq.add_trace(go.Scatter(x=res_df.index, y=res_df['TQQQ'], name='TQQQ', line=dict(color='#EF4444', width=1.2, dash='dash')))
                fig_eq.add_trace(go.Scatter(x=res_df.index, y=res_df['V4.5'], name='AMLS', line=dict(color=main_color, width=3)))
                fig_eq.update_layout(title="Equity Curve", height=380, yaxis_type='log', **chart_layout); fig_eq.update_xaxes(**_ax); fig_eq.update_yaxes(**_ax)
                with st.container(border=True): st.plotly_chart(fig_eq, use_container_width=True)

# ==========================================
# 라우팅 5. Macro News
# ==========================================
elif page == "📰 Macro News":
    headlines_for_ai, news_items = fetch_macro_news()
    st.markdown(apply_theme(f"""<div style="border-top:3px solid #111118;border-bottom:1px solid rgba(0,0,0,0.12);padding:18px 0 14px;margin-bottom:24px;"><div style="display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:10px;"><div><div style="font-family:'DM Mono',monospace;font-size:0.6em;color:#9494A0;letter-spacing:0.22em;text-transform:uppercase;margin-bottom:6px;">Global Macro  ·  Wall Street Analysis Engine</div><div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:2.2em;font-weight:800;color:{tc_heading};letter-spacing:-1.5px;line-height:1;">Market Briefing</div></div></div></div>"""), unsafe_allow_html=True)
    nl, nr = st.columns([1, 1.6])
    with nl:
        if st.button("↻  심층 추론 요약 실행", use_container_width=True):
            try:
                import google.generativeai as genai
                if not headlines_for_ai: st.warning("분석할 뉴스가 없습니다.")
                else:
                    with st.spinner("AI 분석 중..."):
                        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                        _model = genai.GenerativeModel([m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods][0].replace('models/',''))
                        _res = _model.generate_content("다음 뉴스를 섹터별, 리스크 요소, 최종 투자 스탠스로 나누어 요약해.\n" + "\n".join(headlines_for_ai))
                        st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);border-left:3px solid {main_color};padding:20px 22px;margin-top:12px;"><div style="font-family:DM Mono,monospace;font-size:0.58em;color:#9494A0;letter-spacing:0.16em;text-transform:uppercase;margin-bottom:10px;">AI Summary</div><div style="font-family:DM Sans,sans-serif;font-size:0.9em;color:{tc_body};line-height:1.75;">{_res.text}</div></div>'), unsafe_allow_html=True)
            except KeyError: st.error("🚨 GEMINI_API_KEY 누락")
        else: st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);border-left:3px solid rgba(0,0,0,0.15);padding:20px 22px;margin-top:12px;"><div style="font-family:DM Mono,monospace;font-size:0.6em;color:#9494A0;letter-spacing:0.14em;text-transform:uppercase;margin-bottom:10px;">How It Works</div><div style="font-family:DM Sans,sans-serif;font-size:0.85em;color:{tc_muted};line-height:1.7;">버튼을 누르면 AI가 최신 뉴스를 3단계로 요약합니다.</div></div>'), unsafe_allow_html=True)
    with nr:
        for idx, item in enumerate(news_items):
            st.markdown(f'<div style="display:flex;gap:14px;padding:12px 0;border-bottom:1px solid rgba(0,0,0,0.07);"><div style="font-family:DM Mono,monospace;font-size:0.75em;color:{main_color if idx<3 else "#9494A0"};font-weight:600;">{idx+1:02d}</div><div><a href="{item["link"]}" target="_blank" style="text-decoration:none;"><div style="color:{tc_body};">{item["title"]}</div></a><div style="font-size:0.65em;color:#9494A0;margin-top:4px;">{item["date"]}</div></div></div>', unsafe_allow_html=True)

_ls_save_all()
