import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import urllib.request, urllib.parse, json, os, warnings
import xml.etree.ElementTree as ET

warnings.filterwarnings('ignore')
st.set_page_config(page_title="AMLS V5 FINANCE STRATEGY", layout="wide", page_icon="🌿", initial_sidebar_state="expanded")

if 'display_mode' not in st.session_state: st.session_state.display_mode = 'PC'
if 'lc_lr_split' not in st.session_state: st.session_state.lc_lr_split = 38
if 'lc_delta_wt' not in st.session_state: st.session_state.lc_delta_wt = 52
if 'lc_editor_h' not in st.session_state: st.session_state.lc_editor_h = 355
if 'lc_goal_inp' not in st.session_state: st.session_state.lc_goal_inp = 22
if 'lc_pie_h' not in st.session_state: st.session_state.lc_pie_h = 200
if 'lc_pie_split' not in st.session_state: st.session_state.lc_pie_split = 50
if 'lc_bar_h' not in st.session_state: st.session_state.lc_bar_h = 185
if 'lc_show_lp' not in st.session_state: st.session_state.lc_show_lp = True
if 'lc_show_qo' not in st.session_state: st.session_state.lc_show_qo = True
if 'lc_show_reg' not in st.session_state: st.session_state.lc_show_reg = True
if 'main_color' not in st.session_state: st.session_state.main_color = '#10B981'
if 'bg_color' not in st.session_state: st.session_state.bg_color = '#F7F6F2'
if 'tc_heading' not in st.session_state: st.session_state.tc_heading = '#111118'
if 'tc_body' not in st.session_state: st.session_state.tc_body = '#2D2D2D'
if 'tc_muted' not in st.session_state: st.session_state.tc_muted = '#6B6B7A'
if 'tc_label' not in st.session_state: st.session_state.tc_label = '#9494A0'
if 'tc_data' not in st.session_state: st.session_state.tc_data = '#111118'
if 'tc_sidebar' not in st.session_state: st.session_state.tc_sidebar = '#2D2D2D'
if '_ls_loaded' not in st.session_state: st.session_state._ls_loaded = False
if 'rebal_locked' not in st.session_state: st.session_state.rebal_locked = False
if 'rebal_plan' not in st.session_state: st.session_state.rebal_plan = None
if 'param_vix_limit' not in st.session_state: st.session_state.param_vix_limit = 40.0
if 'param_ma_long' not in st.session_state: st.session_state.param_ma_long = 200
if 'param_ma_short' not in st.session_state: st.session_state.param_ma_short = 50
if 'trade_log' not in st.session_state: st.session_state.trade_log = []
if 'messages' not in st.session_state: st.session_state.messages = []
if 'use_custom_weights' not in st.session_state: st.session_state.use_custom_weights = False
if 'custom_weights' not in st.session_state:
    st.session_state.custom_weights = {
        "R1": {'TQQQ':30, 'SOXL':20, 'USD':0, 'QLD':20, 'SSO':15, 'SPYG':5, 'QQQ':0, 'SHV':10, 'CASH':0},
        "R2": {'TQQQ':15, 'SOXL':0, 'USD':10, 'QLD':30, 'SSO':25, 'SPYG':5, 'QQQ':0, 'SHV':15, 'CASH':0},
        "R3": {'TQQQ':0, 'SOXL':0, 'USD':0, 'QLD':0, 'SSO':0, 'SPYG':0, 'QQQ':15, 'SHV':50, 'CASH':35},
        "R4": {'TQQQ':0, 'SOXL':0, 'USD':0, 'QLD':0, 'SSO':0, 'SPYG':0, 'QQQ':10, 'SHV':50, 'CASH':40}
    }

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
CORE_TICKERS   = ['QQQ','TQQQ','SOXL','USD','QLD','SSO','SPYG','SMH','GLD','^VIX','HYG','IEF','QQQE','UUP','^TNX','BTC-USD','IWM']
TICKERS        = CORE_TICKERS + SECTOR_TICKERS + ['SHV']
ASSET_LIST     = ['TQQQ','SOXL','USD','QLD','SSO','SPYG','QQQ','SHV','CASH']
ISA_ASSET_LIST = ['133690.KS','462900.KS','225040.KS','360750.KS','411060.KS','CASH']
ISA_NAMES      = {'133690.KS':'TIGER 나스닥100','462900.KS':'TIGER 나스닥100 2X','225040.KS':'TIGER S&P500 2X','360750.KS':'TIGER S&P500','411060.KS':'ACE KRX금현물','CASH':'현금(₩)'}
PORTFOLIO_FILE = 'portfolio_autosave.json'
PORTFOLIO_ISA_FILE = 'portfolio_isa_autosave.json'
PORTFOLIO_TOSS_FILE = 'portfolio_toss_autosave.json'
TRADE_LOG_FILE = 'trade_log_autosave.json'

if not st.session_state.trade_log and os.path.exists(TRADE_LOG_FILE):
    try:
        with open(TRADE_LOG_FILE, 'r', encoding='utf-8') as f:
            _loaded_log = json.load(f)
            if isinstance(_loaded_log, list):
                st.session_state.trade_log = _loaded_log
    except: pass

def sanitize_portfolio(pf):
    for a in ASSET_LIST:
        val = pf.get(a)
        if isinstance(val, (int, float)) or val is None: pf[a] = {'shares': float(val or 0.0), 'avg_price': 1.0 if a == 'CASH' else 0.0, 'fx': 1350.0}
        elif isinstance(val, dict):
            if 'shares' not in val: val['shares'] = 0.0
            if 'avg_price' not in val: val['avg_price'] = 1.0 if a == 'CASH' else 0.0
            if 'fx' not in val: val['fx'] = 1350.0
        else: pf[a] = {'shares': 0.0, 'avg_price': 0.0, 'fx': 1350.0}

if 'goal_usd' not in st.session_state: st.session_state.goal_usd = 100000.0

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {asset: {'shares':0.0, 'avg_price':0.0, 'fx':1350.0} for asset in ASSET_LIST}
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                loaded = json.load(f)
                for k, v in loaded.items(): st.session_state.portfolio[k] = v
        except: pass

if 'portfolio_isa' not in st.session_state:
    st.session_state.portfolio_isa = {asset: {'shares':0.0, 'avg_price':0.0, 'fx':1350.0} for asset in ISA_ASSET_LIST}
    if os.path.exists(PORTFOLIO_ISA_FILE):
        try:
            with open(PORTFOLIO_ISA_FILE, 'r') as f:
                loaded = json.load(f)
                for k, v in loaded.items(): st.session_state.portfolio_isa[k] = v
        except: pass

if 'portfolio_toss' not in st.session_state:
    st.session_state.portfolio_toss = {}
    if os.path.exists(PORTFOLIO_TOSS_FILE):
        try:
            with open(PORTFOLIO_TOSS_FILE, 'r') as f:
                loaded = json.load(f)
                for k, v in loaded.items(): st.session_state.portfolio_toss[k] = v
        except: pass

sanitize_portfolio(st.session_state.portfolio)
for _isa_a in ISA_ASSET_LIST:
    if _isa_a not in st.session_state.portfolio_isa:
        st.session_state.portfolio_isa[_isa_a] = {'shares':0.0, 'avg_price':0.0, 'fx':1350.0}

def save_portfolio_to_disk():
    try:
        with open(PORTFOLIO_FILE, 'w') as f: json.dump(st.session_state.portfolio, f)
        with open(PORTFOLIO_ISA_FILE, 'w') as f: json.dump(st.session_state.portfolio_isa, f)
        with open(PORTFOLIO_TOSS_FILE, 'w') as f: json.dump(st.session_state.portfolio_toss, f)
    except: pass
    st.session_state['_needs_ls_save'] = True

def save_trade_log_to_disk():
    try:
        with open(TRADE_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.trade_log, f, ensure_ascii=False)
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
            df['GLD_SPY_Ratio'] = df['GLD'] / df['SPYG']
            df['GLD_SPY_MA50'] = df['GLD_SPY_Ratio'].rolling(50).mean()
            df['QQQ_High52'] = df['QQQ'].rolling(252).max()
            df['QQQ_DD'] = (df['QQQ'] / df['QQQ_High52']) - 1
            df['UUP_MA50'] = df['UUP'].rolling(50).mean()
            df['TNX_MA50'] = df['^TNX'].rolling(50).mean()
            df['BTC_MA50'] = df['BTC-USD'].rolling(50).mean()
            df['IWM_SPY_Ratio'] = df['IWM'] / df['SPYG']
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
    bt_df['GLD_SPY_Ratio'] = bt_df['GLD'] / bt_df['SPYG']
    bt_df['GLD_SPY_MA50'] = bt_df['GLD_SPY_Ratio'].rolling(50).mean()
    bt_df['QQQ_High52'] = bt_df['QQQ'].rolling(252).max()
    bt_df['QQQ_DD'] = (bt_df['QQQ'] / bt_df['QQQ_High52']) - 1
    bt_df['UUP_MA50'] = bt_df['UUP'].rolling(50).mean()
    bt_df['TNX_MA50'] = bt_df['^TNX'].rolling(50).mean()
    bt_df['BTC_MA50'] = bt_df['BTC-USD'].rolling(50).mean()
    bt_df['IWM_SPY_Ratio'] = bt_df['IWM'] / bt_df['SPYG']
    bt_df['IWM_SPY_MA50'] = bt_df['IWM_SPY_Ratio'].rolling(50).mean()
    bt_df = bt_df.dropna()
    if bt_df.empty: return bt_df
    bt_df['Target'] = bt_df.apply(get_target_v45, axis=1)
    bt_df['Regime'] = apply_asymmetric_delay(bt_df['Target'])
    bt_df = bt_df.loc[pd.to_datetime(start_date):pd.to_datetime(end_date)]
    return bt_df

REALTIME_TICKERS = ['QQQ','TQQQ','SMH','^VIX','HYG','IEF','UUP','GLD','SPYG','SOXL','USD','QLD','SSO','SHV','USDKRW=X', '^TNX', 'BTC-USD', 'IWM']

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_cnn_fear_greed():
    """CNN 공식 Fear & Greed Index를 production.dataviz API에서 직접 조회"""
    try:
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        url = f"https://production.dataviz.cnn.io/index/fearandgreed/graphdata/{start_date}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://www.cnn.com',
            'Referer': 'https://www.cnn.com/',
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        now_block = data.get('fear_and_greed', {})
        return {
            'score': float(now_block.get('score', 0)),
            'rating': now_block.get('rating', 'unknown'),
            'prev_close': float(now_block.get('previous_close', 0)),
            'week_ago': float(now_block.get('previous_1_week', 0)),
            'month_ago': float(now_block.get('previous_1_month', 0)),
            'year_ago': float(now_block.get('previous_1_year', 0)),
            'ok': True,
        }
    except Exception as e:
        return {'score': None, 'rating': None, 'ok': False, 'error': str(e)}

@st.cache_data(ttl=15)
def fetch_realtime_prices():
    prices = {}
    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc + timedelta(hours=9)
    fetch_time = now_kst.strftime("%Y-%m-%d %H:%M:%S")
    
    # 1차 시도: 대량 다운로드 (1분봉, 공백은 ffill로 채움)
    try:
        batch_data = yf.download(REALTIME_TICKERS, period="5d", interval="1m", prepost=True, progress=False, threads=True)
        if 'Close' in batch_data: batch_data = batch_data['Close']
        if isinstance(batch_data, pd.Series): batch_data = batch_data.to_frame(name=REALTIME_TICKERS[0])
        if not batch_data.empty:
            batch_data = batch_data.ffill()
            latest_row = batch_data.iloc[-1]
            for ticker in REALTIME_TICKERS:
                if ticker in latest_row.index and pd.notna(latest_row[ticker]):
                    val = float(latest_row[ticker])
                    if val > 0: prices[ticker] = val
    except Exception: pass

    # 2차 시도: 누락된 티커에 대해 정밀 조회 (프리/애프터마켓 직접 타겟팅)
    missing_tickers = [t for t in REALTIME_TICKERS if t not in prices]
    if missing_tickers:
        for ticker in missing_tickers:
            try:
                tk = yf.Ticker(ticker)
                info = tk.info
                # 현재가, 애프터마켓, 프리마켓, 정규장 순서로 값이 있는지 확인
                price = info.get('currentPrice') or info.get('postMarketPrice') or info.get('preMarketPrice') or info.get('regularMarketPrice')
                if price and price > 0: 
                    prices[ticker] = float(price)
                else:
                    # fast_info로 마지막 체결가 확인
                    price = tk.fast_info.get('last_price')
                    if price and price > 0: prices[ticker] = float(price)
            except: pass
            
    return prices, fetch_time

@st.cache_data(ttl=900)
def fetch_macro_news():
    headlines_for_ai, news_items = [], []
    try:
        search_query = '("미국증시" OR "나스닥" OR "연준" OR "FOMC" OR "파월" OR "미국 금리" OR "미국 CPI" -한은 -한국은행 -코스피 -코스닥 -금통위) when:12h'
        q = urllib.parse.quote(search_query)
        url  = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
        root = ET.fromstring(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})).read())
        for item in root.findall('.//item')[:12]:
            t, l, d = item.find('title').text, item.find('link').text, item.find('pubDate').text
            headlines_for_ai.append(t); news_items.append({"title":t,"link":l,"date":d[:-4]})
    except: pass
    return headlines_for_ai, news_items

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
if 'IWM' in rt_injected and 'SPYG' in rt_injected: df.at[last_index, 'IWM_SPY_Ratio'] = df.at[last_index, 'IWM'] / df.at[last_index, 'SPYG']

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
r_acc = {1: main_color, 2: "#D97706", 3: "#DC2626", 4: "#7C3AED"}[curr_regime]

target_regime = live_regime
smh_cond = (smh_close > smh_ma50) and (smh_3m > 0.05 or smh_1m > 0.10) and (smh_rsi > 50)

def get_weights_v45(reg, smh_ok):
    w = {t: 0.0 for t in ASSET_LIST}
    semi = 'SOXL' if smh_ok else 'USD'
    if reg == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['SHV'], w['SPYG'] = 0.30, 0.20, 0.20, 0.15, 0.10, 0.05
    elif reg == 2: w['TQQQ'], w['QLD'], w['SSO'], w['USD'], w['SHV'], w['SPYG'] = 0.15, 0.30, 0.25, 0.10, 0.15, 0.05
    elif reg == 3: w['SHV'], w['CASH'], w['QQQ'] = 0.50, 0.35, 0.15
    elif reg == 4: w['SHV'], w['CASH'], w['QQQ'] = 0.50, 0.40, 0.10
    return w

target_weights = get_weights_v45(curr_regime, smh_cond)
current_prices = {t: (rt_prices.get(t, df[t].iloc[-1] if t in df.columns else 0.0) if t != 'CASH' else 1.0) for t in ASSET_LIST}
cp = current_prices    

if curr_regime == live_regime: regime_committee_msg = "🟢 조건 부합 (안정)"
elif live_regime > curr_regime: regime_committee_msg = f"🔴 R{live_regime} 방어 즉시 반영"
elif hist_regime == 3 and live_regime == 1 and curr_regime == 2: regime_committee_msg = "🟡 R2 1차 회복 · R1 승급 대기 (5일)"
else: regime_committee_msg = f"🟡 R{live_regime} 승급 대기 (5일)"

b_color, t_color, line_c, dash_c, rsi_low_c = 'rgba(0,0,0,0)', '#4A4A57', main_color, '#B0B0BE', main_color
chart_layout = dict(paper_bgcolor=b_color, plot_bgcolor=b_color, font=dict(family="DM Mono, DM Sans, monospace", color=t_color), margin=dict(l=0, r=0, t=40, b=0))
radar_layout = dict(height=200, margin=dict(l=10, r=10, t=15, b=15), paper_bgcolor=b_color, plot_bgcolor=b_color, font=dict(family="DM Mono, DM Sans, monospace", color=t_color))
_ax = dict(gridcolor='rgba(0,0,0,0.07)', linecolor='rgba(0,0,0,0.12)', showgrid=True, zeroline=False)
_ax_r = dict(gridcolor='rgba(0,0,0,0.07)', zeroline=False, showgrid=True)
regime_info = {1:("R1 BULL","풀 가동"),2:("R2 CORR","방어 진입"), 3:("R3 BEAR","대피"),4:("R4 PANIC","최대 방어")}

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

st.sidebar.markdown(apply_theme(f"""<div style="padding:22px 20px 16px;background:{bg_color};border-bottom:1px solid rgba(0,0,0,0.09);"><div style="font-family:'DM Mono';font-size:0.52em;color:{tc_label};letter-spacing:0.26em;text-transform:uppercase;margin-bottom:8px;">Quantitative Engine</div><div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:1.65em;font-weight:800;color:{tc_heading};letter-spacing:-1px;line-height:1;margin-bottom:14px;">AMLS <span style="color:#10B981;">V5</span></div><div style="display:flex;align-items:center;justify-content:space-between;"><div class="live-pulse" style="display:inline-flex;align-items:center;gap:5px;font-family:'DM Mono';font-size:0.6em;color:#059669;padding:3px 10px;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);letter-spacing:0.06em;">{rt_label}</div><div style="font-family:'DM Mono';font-size:0.58em;color:{tc_label};letter-spacing:0.04em;">R{curr_regime}  ·  {regime_info[curr_regime][1]}</div></div></div>"""), unsafe_allow_html=True)
st.sidebar.markdown('<div class="sb-section" style="border-top:none;">Navigation</div>', unsafe_allow_html=True)
page = st.sidebar.radio("MENU", ["📊 Dashboard", "💼 Portfolio", "🤖 AI Quant Assistant", "📝 Trade Journal", "🍫 12-Pack Radar", "📈 Backtest Lab", "📰 Macro News"], label_visibility="collapsed")
display_mode = st.session_state.display_mode

with st.sidebar.expander("🎨  Appearance", expanded=False):
    _ac1, _ac2 = st.columns(2)
    with _ac1:
        st.markdown('<div style="font-family:DM Mono,monospace;font-size:0.65em;color:rgba(255,255,255,0.35);margin-bottom:4px;">Accent</div>', unsafe_allow_html=True)
        new_color = st.color_picker("Accent", st.session_state.main_color, label_visibility="collapsed", key="cp_theme")
        if new_color != st.session_state.main_color: st.session_state.main_color = new_color; st.session_state['_needs_ls_save'] = True
    with _ac2:
        st.markdown('<div style="font-family:DM Mono,monospace;font-size:0.65em;color:rgba(255,255,255,0.35);margin-bottom:4px;">Background</div>', unsafe_allow_html=True)
        _new_bg = st.color_picker("BG", st.session_state.bg_color, label_visibility="collapsed", key="cp_bg")
        if _new_bg != st.session_state.bg_color: st.session_state.bg_color = _new_bg; st.session_state['_needs_ls_save'] = True
    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
    _tc_defs = [("헤딩","tc_heading","cp_tc_heading"),("본문","tc_body","cp_tc_body"),("뮤트","tc_muted","cp_tc_muted"),("레이블","tc_label","cp_tc_label"),("데이터","tc_data","cp_tc_data"),("사이드","tc_sidebar","cp_tc_sidebar")]
    for (_d1, _k1, _w1), (_d2, _k2, _w2) in [(_tc_defs[i], _tc_defs[i+1]) for i in range(0, len(_tc_defs)-1, 2)]:
        _cc1, _cc2 = st.columns(2)
        with _cc1:
            st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.65em;color:rgba(255,255,255,0.35);margin-bottom:4px;">{_d1}</div>', unsafe_allow_html=True)
            _p1 = st.color_picker("", getattr(st.session_state, _k1), label_visibility="collapsed", key=_w1)
            if _p1 != getattr(st.session_state, _k1): setattr(st.session_state, _k1, _p1); st.session_state['_needs_ls_save'] = True
        with _cc2:
            st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.65em;color:rgba(255,255,255,0.35);margin-bottom:4px;">{_d2}</div>', unsafe_allow_html=True)
            _p2 = st.color_picker("", getattr(st.session_state, _k2), label_visibility="collapsed", key=_w2)
            if _p2 != getattr(st.session_state, _k2): setattr(st.session_state, _k2, _p2); st.session_state['_needs_ls_save'] = True
    if st.button("↺  초기화", use_container_width=True, key="reset_colors"):
        for _k, _v in [("main_color","#10B981"),("bg_color","#F7F6F2"),("tc_heading","#111118"),("tc_body","#2D2D2D"),("tc_muted","#6B6B7A"),("tc_label","#9494A0"),("tc_data","#111118"),("tc_sidebar","#2D2D2D")]: setattr(st.session_state, _k, _v)
        st.session_state['_needs_ls_save'] = True; st.rerun()

with st.sidebar.expander("🔗  Bookmarks", expanded=False):
    st.markdown("""<div style="display:flex;flex-direction:column;gap:0;"><a href="https://www.youtube.com/@JB_Insight" target="_blank" class="sidebar-link">📊 JB 인사이트</a><a href="https://www.youtube.com/@odokgod" target="_blank" class="sidebar-link">📻 오독</a><a href="https://www.youtube.com/@TQQQCRAZY" target="_blank" class="sidebar-link">🔥 TQQQ 미친놈</a><a href="https://www.youtube.com/@developmong" target="_blank" class="sidebar-link">🐒 디벨롭몽</a><a href="https://kr.investing.com/" target="_blank" class="sidebar-link">🌍 인베스팅닷컴</a><a href="https://kr.tradingview.com/" target="_blank" class="sidebar-link">📉 트레이딩뷰</a></div>""", unsafe_allow_html=True)

with st.sidebar.expander("💾  Portfolio Data", expanded=False):
    _all_backup = json.dumps({"portfolio": st.session_state.portfolio, "portfolio_isa": st.session_state.portfolio_isa, "portfolio_toss": st.session_state.portfolio_toss, "goal_usd": st.session_state.goal_usd, "trade_log": st.session_state.trade_log})
    st.download_button("⬇  전체 백업 (3계좌)", data=_all_backup, file_name="amls_backup.json", mime="application/json", use_container_width=True, key="sb_backup")
    st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
    _sidebar_upload = st.file_uploader("⬆  복원 (JSON)", type="json", key="sb_uploader", label_visibility="visible")
    if _sidebar_upload is not None:
        try:
            _loaded = json.load(_sidebar_upload)
            if "portfolio" in _loaded:
                st.session_state.portfolio.update(_loaded["portfolio"]); sanitize_portfolio(st.session_state.portfolio)
            if "portfolio_isa" in _loaded:
                st.session_state.portfolio_isa.update(_loaded["portfolio_isa"]); sanitize_portfolio(st.session_state.portfolio_isa)
            if "portfolio_toss" in _loaded:
                st.session_state.portfolio_toss.clear(); st.session_state.portfolio_toss.update(_loaded["portfolio_toss"])
            if "goal_usd" in _loaded:
                st.session_state.goal_usd = float(_loaded["goal_usd"])
            if "trade_log" in _loaded and isinstance(_loaded["trade_log"], list):
                st.session_state.trade_log = _loaded["trade_log"]
                save_trade_log_to_disk()
            save_portfolio_to_disk(); st.session_state.rebal_locked=False; st.success("✅ 3계좌 + 매매일지 복구 완료"); st.rerun()
        except: st.error("❌ 파일 형식 오류")

with st.sidebar.expander("⚙️  Layout Controls  (PC)", expanded=False):
    def _lc_sec(title): st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.58em;font-weight:600;color:{tc_label};letter-spacing:0.16em;text-transform:uppercase;margin:10px 0 6px;padding-bottom:4px;border-bottom:1px solid rgba(0,0,0,0.08);">{title}</div>', unsafe_allow_html=True)
    _lc_sec("① 열 분할")
    _v = st.slider("좌열 너비 %", 20, 60, st.session_state.lc_lr_split, 2, key="sl_lr") 
    if _v != st.session_state.lc_lr_split: st.session_state.lc_lr_split = _v; st.session_state['_needs_ls_save'] = True
    _v = st.slider("Goal 입력창 %", 10, 40, st.session_state.lc_goal_inp, 2, key="sl_gi") 
    if _v != st.session_state.lc_goal_inp: st.session_state.lc_goal_inp = _v; st.session_state['_needs_ls_save'] = True
    _lc_sec("② 컴포넌트 높이")
    _v = st.slider("에디터 높이 px", 200, 600, st.session_state.lc_editor_h, 20, key="sl_eh") 
    if _v != st.session_state.lc_editor_h: st.session_state.lc_editor_h = _v; st.session_state['_needs_ls_save'] = True
    _v = st.slider("파이차트 높이 px", 140, 340, st.session_state.lc_pie_h, 20, key="sl_ph") 
    if _v != st.session_state.lc_pie_h: st.session_state.lc_pie_h = _v; st.session_state['_needs_ls_save'] = True
    _v = st.slider("Delta Bar 높이 px", 120, 320, st.session_state.lc_bar_h, 20, key="sl_bh") 
    if _v != st.session_state.lc_bar_h: st.session_state.lc_bar_h = _v; st.session_state['_needs_ls_save'] = True
    _lc_sec("③ 내부 비율")
    _v = st.slider("파이 Current/Target %", 30, 70, st.session_state.lc_pie_split, 5, key="sl_ps") 
    if _v != st.session_state.lc_pie_split: st.session_state.lc_pie_split = _v; st.session_state['_needs_ls_save'] = True
    _v = st.slider("Delta Bar / Weights %", 30, 70, st.session_state.lc_delta_wt, 5, key="sl_dw") 
    if _v != st.session_state.lc_delta_wt: st.session_state.lc_delta_wt = _v; st.session_state['_needs_ls_save'] = True
    _lc_sec("④ 패널 표시")
    _c1, _c2, _c3 = st.columns(3)
    _nreg = _c1.checkbox("Regime", value=st.session_state.lc_show_reg, key="ck_reg")
    _nlp  = _c2.checkbox("Live Px", value=st.session_state.lc_show_lp, key="ck_lp")
    _nqo  = _c3.checkbox("Orders", value=st.session_state.lc_show_qo, key="ck_qo")
    if _nreg != st.session_state.lc_show_reg: st.session_state.lc_show_reg = _nreg; st.session_state['_needs_ls_save'] = True
    if _nlp  != st.session_state.lc_show_lp: st.session_state.lc_show_lp = _nlp; st.session_state['_needs_ls_save'] = True
    if _nqo  != st.session_state.lc_show_qo: st.session_state.lc_show_qo = _nqo; st.session_state['_needs_ls_save'] = True
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    if st.button("↺  전체 초기화", use_container_width=True, key="lc_reset"):
        for _k, _dv in [("lc_lr_split", 38), ("lc_goal_inp", 22), ("lc_editor_h", 355), ("lc_pie_h", 200), ("lc_bar_h", 185), ("lc_pie_split", 50), ("lc_delta_wt", 52), ("lc_show_reg", True), ("lc_show_lp", True), ("lc_show_qo", True)]: setattr(st.session_state, _k, _dv)
        st.session_state['_needs_ls_save'] = True; st.rerun()

_qqq_chg  = (last_row['QQQ'] / last_row['QQQ_MA200'] - 1) * 100
_vix_now  = last_row['^VIX']
_smh_chg  = last_row['SMH_1M_Ret'] * 100

def _pill(label, value, color): return f'<div style="display:flex;flex-direction:column;align-items:center;padding:8px 18px;background:#FFFFFF;border:1px solid rgba(0,0,0,0.07);border-top:2px solid {color};border-radius:12px;min-width:90px;"><span style="font-family:\'DM Mono\';font-size:0.6em;color:#4A5568;letter-spacing:0.14em;text-transform:uppercase;">{label}</span><span style="font-family:\'DM Mono\';font-size:1.05em;font-weight:500;color:#0F172A;margin-top:2px;">{value}</span></div>'

_p_qqq  = _pill("QQQ/200MA", f"{_qqq_chg:+.1f}%", main_color if _qqq_chg >= 0 else "#EF4444")
_p_vix  = _pill("VIX", f"{_vix_now:.1f}", main_color if _vix_now < 20 else ("#F59E0B" if _vix_now < 30 else "#EF4444"))
_p_smh  = _pill("SMH 1M", f"{_smh_chg:+.1f}%", main_color if _smh_chg >= 0 else "#EF4444")
_p_reg  = _pill("REGIME", f"R{curr_regime}", main_color)
_hdr_left = apply_theme(f"""<div style="display:flex;flex-direction:column;justify-content:center;"><div style="font-family:'Plus Jakarta Sans';font-size:2.5em;font-weight:800;letter-spacing:-2px;color:#0F172A;line-height:1;">AMLS <span style="color:#10B981;">V5</span></div><div style="font-family:'DM Mono';font-size:0.65em;color:#4A5568;letter-spacing:0.22em;text-transform:uppercase;margin-top:4px;">The Wall Street Quantitative Strategy</div></div>""")
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
        st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);border-top:3px solid {regime_accent};padding:20px 18px 16px;margin-bottom:10px;position:relative;overflow:hidden;"><div style="position:absolute;right:-4px;bottom:-16px;font-family:Plus Jakarta Sans,sans-serif;font-size:7em;font-weight:800;color:rgba(0,0,0,0.04);line-height:1;pointer-events:none;user-select:none;">{curr_regime}</div><div style="font-family:DM Mono,monospace;font-size:0.68em;color:#9494A0;letter-spacing:0.18em;text-transform:uppercase;margin-bottom:10px;">Market Regime</div><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:2em;font-weight:800;letter-spacing:-1px;color:{regime_accent};line-height:1;margin-bottom:4px;">{regime_info[curr_regime][0]}</div><div style="font-family:DM Mono,monospace;font-size:0.72em;color:#6B6B7A;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:14px;">{regime_info[curr_regime][1]}</div>{_lg_row("VIX < 40", f"{vix_close:.2f}", vix_close<=40) + _lg_row("VIX MA20 < 22  (R1 승급 조건)", f"{vix_ma20:.2f}", vix_ma20<22) + _lg_row(f"QQQ > 200MA [{qqq_ma200:.2f}]", f"${qqq_close:.2f}", qqq_close>=qqq_ma200) + _lg_row(f"50MA ≥ 200MA [{qqq_ma50:.2f}]", f"${qqq_ma50:.2f}", qqq_ma50>=qqq_ma200) + _lg_row("Credit Stress 방어", "안정" if credit_check else "경계", credit_check)}<div style="margin-top:8px;padding:6px 10px;background:rgba(16,185,129,0.07);border-left:2px solid {main_color};font-family:DM Mono,monospace;font-size:0.76em;color:#059669;">{regime_committee_msg}</div></div>'), unsafe_allow_html=True)
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

    def _sec_label(txt): st.markdown(f'<div style="display:flex;align-items:center;gap:12px;margin:24px 0 14px;"><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.1em;font-weight:700;color:{tc_heading};letter-spacing:-0.3px;white-space:nowrap;">{txt}</div><div style="flex:1;height:1px;background:rgba(0,0,0,0.12);"></div></div>', unsafe_allow_html=True)


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
    if 'acc_tab' not in st.session_state: st.session_state.acc_tab = "일반"
    _tab_items = [("일반", "💼", "일반 계좌", "AMLS 레짐 연동"), ("ISA", "🛡️", "ISA 계좌", "절세 전략"), ("TOSS", "🌱", "TOSS 장기투자", "자유 적립")]
    _tab_cols = st.columns(len(_tab_items))
    for _i, (_tid, _tico, _tname, _tsub) in enumerate(_tab_items):
        _sel = st.session_state.acc_tab == _tid
        with _tab_cols[_i]:
            st.markdown(f'<div style="background:{"#FFFFFF" if _sel else "#FAFAF7"};border:{"2px solid "+main_color if _sel else "1px solid rgba(0,0,0,0.08)"};border-radius:14px;padding:14px 16px;text-align:center;{"box-shadow:0 2px 8px rgba(0,0,0,0.06);" if _sel else ""}"><div style="font-size:1.3em;margin-bottom:4px;">{_tico}</div><div style="font-family:DM Mono,monospace;font-size:0.78em;font-weight:{"700" if _sel else "400"};color:{"#0F172A" if _sel else "#9494A0"};">{_tname}</div><div style="font-family:DM Mono,monospace;font-size:0.56em;color:{main_color if _sel else "#BBBBBB"};margin-top:2px;">{_tsub}</div></div>', unsafe_allow_html=True)
            if st.button(f"선택", key=f"acc_tab_{_tid}", use_container_width=True):
                st.session_state.acc_tab = _tid; st.rerun()
    st.markdown(f'<style>[data-testid="stHorizontalBlock"] [data-testid="stButton"] > button {{background:{bg_color} !important;border:1px solid rgba(0,0,0,0.10) !important;border-radius:8px !important;color:{tc_muted} !important;font-family:DM Mono,monospace !important;font-size:0.68em !important;padding:6px 12px !important;margin-top:6px !important;letter-spacing:0.05em;}}</style>', unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    acc_choice = "🟦 일반 계좌" if st.session_state.acc_tab == "일반" else ("🟩 ISA 계좌" if st.session_state.acc_tab == "ISA" else "🧪 TOSS 장기투자")
    
    is_toss = "TOSS" in acc_choice
    is_isa = "ISA" in acc_choice
    active_pf = st.session_state.portfolio if "일반" in acc_choice else (st.session_state.portfolio_isa if "ISA" in acc_choice else st.session_state.portfolio_toss)
    target_assets = list(active_pf.keys()) if is_toss else (ISA_ASSET_LIST if is_isa else ASSET_LIST)

    cur_fx = rt_prices.get('USDKRW=X', 1350.0)           
    current_prices = {t: (rt_prices.get(t, last_row.get(t, 1.0)) if t != 'CASH' else 1.0) for t in target_assets}
    current_prices = {t: (rt_prices.get(t, last_row.get(t, 1.0)) if t != 'CASH' else 1.0) for t in target_assets}
    if is_isa:
        _isa_missing = [t for t in target_assets if t not in current_prices or current_prices.get(t, 0) <= 0]
        _isa_missing = [t for t in _isa_missing if t != 'CASH']
        for t in _isa_missing:
            try:
                _hist = yf.Ticker(t).history(period="5d")
                if not _hist.empty:
                    current_prices[t] = float(_hist['Close'].dropna().iloc[-1])
            except:
                current_prices[t] = 0.0
    if is_isa:
        _isa_tickers = [t for t in target_assets if t != 'CASH']
        for t in _isa_tickers:
            _krw_price = 0.0
            try:
                _hist = yf.Ticker(t).history(period="5d")
                if not _hist.empty:
                    _krw_price = float(_hist['Close'].dropna().iloc[-1])
            except: pass
            if _krw_price <= 0:
                try:
                    _info = yf.Ticker(t).fast_info
                    _p = _info.get('last_price') or _info.get('lastPrice') or _info.get('previousClose')
                    if _p and _p > 0: _krw_price = float(_p)
                except: pass
            current_prices[t] = _krw_price / cur_fx if _krw_price > 0 else 0.0
    if is_toss:
        _toss_missing = [t for t in target_assets if t not in rt_prices and t not in df.columns and t != 'CASH']
        for t in _toss_missing:
            try:
                _hist = yf.Ticker(t).history(period="5d", prepost=True)
                if not _hist.empty:
                    current_prices[t] = float(_hist['Close'].dropna().iloc[-1])
                    continue
            except: pass
            try:
                _info = yf.Ticker(t).fast_info
                _p = _info.get('last_price') or _info.get('lastPrice') or _info.get('previousClose')
                if _p and _p > 0: current_prices[t] = float(_p)
            except:
                current_prices[t] = active_pf[t].get('cur_price', 0.0)

    curr_vals = {a: active_pf[a].get('shares', 0.0) * current_prices[a] for a in target_assets}
    total_val_usd = sum(curr_vals.values())
    total_val_krw = total_val_usd * cur_fx
    invested_cost = sum(active_pf[a].get('shares', 0.0) * active_pf[a].get('avg_price', 0.0) for a in target_assets if a != 'CASH')
    pnl_usd = total_val_usd - invested_cost
    pnl_pct = (pnl_usd / invested_cost * 100) if invested_cost > 0 else 0.0
    live_diff_vals = {a: (total_val_usd * target_weights.get(a, 0.0)) - curr_vals.get(a, 0.0) for a in target_assets} if total_val_usd > 0 else {a: 0.0 for a in target_assets}
    
    C_GREEN, C_RED = main_color, "#DC2626"
    r_acc = {1: main_color, 2: "#D97706", 3: "#DC2626", 4: "#7C3AED"}[curr_regime]

    def _sl(text): return apply_theme(f'<div style="display:flex;align-items:center;gap:7px;margin-bottom:8px;padding-bottom:7px;border-bottom:1px solid rgba(0,0,0,0.09);"><div style="width:2px;height:12px;background:{main_color};flex-shrink:0;"></div><span style="font-family:DM Mono,monospace;font-size:0.58em;font-weight:600;color:{tc_heading};letter-spacing:0.2em;text-transform:uppercase;">{text}</span></div>')
    def _kv(label, val, color, sub=""): return f'<div style="display:flex;flex-direction:column;padding:0 20px;border-right:1px solid rgba(0,0,0,0.08);min-width:115px;"><span style="font-family:DM Mono,monospace;font-size:0.53em;color:{tc_label};letter-spacing:0.2em;text-transform:uppercase;margin-bottom:3px;">{label}</span><span style="font-family:DM Mono,monospace;font-size:1.0em;font-weight:700;color:{color};font-variant-numeric:tabular-nums;line-height:1.2;">{val}</span>{f"<span style=\'font-family:DM Mono,monospace;font-size:0.6em;color:{tc_muted};\'>{sub}</span>" if sub else ""}</div>'
    
    st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.11);border-left:4px solid {r_acc};padding:13px 0;margin-bottom:14px;display:flex;align-items:center;overflow-x:auto;"><div style="padding:0 20px 0 16px;border-right:1px solid rgba(0,0,0,0.08);flex-shrink:0;"><div style="font-family:DM Mono,monospace;font-size:0.52em;color:{tc_label};letter-spacing:0.22em;text-transform:uppercase;margin-bottom:2px;">AMLS V5</div><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.1em;font-weight:800;color:{tc_heading};letter-spacing:-0.3px;line-height:1;">Portfolio</div></div>{_kv("Total NAV", f"${total_val_usd:,.2f}", tc_heading, f"₩{total_val_krw:,.0f}")}{_kv("USD / KRW", f"₩{cur_fx:,.0f}", tc_muted, "환율")}{_kv("P & L", f"{pnl_pct:+.2f}%", "#059669" if pnl_pct >= 0 else "#DC2626", f"{"▲" if pnl_pct >= 0 else "▼"} ${abs(pnl_usd):,.0f}")}{_kv("Regime", f"R{curr_regime}  {regime_info[curr_regime][1]}", r_acc)}{_kv("투자원금", f"${invested_cost:,.0f}", tc_muted, "취득원가")}<div style="margin-left:auto;padding:0 16px;flex-shrink:0;"><span class="live-pulse" style="font-family:DM Mono,monospace;font-size:0.58em;color:{main_color};letter-spacing:0.06em;">{rt_label}</span></div></div>'), unsafe_allow_html=True)    

    def _lp_build():
        _html = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:3px;">'
        for _asset in target_assets:
            _lp_p = current_prices.get(_asset, 0.0) if _asset != 'CASH' else 1.0
            _lp_str = f"${_lp_p:,.2f}" if _lp_p > 0 else "—"
            _avg = active_pf[_asset].get('avg_price', 0.0)
            _shs = active_pf[_asset].get('shares', 0.0)
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
        if st.session_state.rebal_locked and st.session_state.rebal_plan:
            p = st.session_state.rebal_plan
            _s = [(a, f"{int(sh):,.0f}주 매도") for a, d, sh, cp in p['sells'] if int(sh) >= 1]
            _b = [(a, f"{int(sh):,.0f}주 매수") for a, d, sh, cp in p['buys'] if int(sh) >= 1]
            return _s, _b
        else:
            _sells, _buys = [], []
            for asset in target_assets:
                if asset == 'CASH': continue
                _cp = current_prices.get(asset, 1.0) if current_prices.get(asset, 0.0) > 0 else 1.0
                _dv = live_diff_vals.get(asset, 0.0)
                _sh = int(abs(_dv) / _cp)
                if _dv < -_cp * 0.05 and _sh >= 1: _sells.append((asset, f"{_sh:,.0f}주 매도"))
                elif _dv > _cp * 0.05 and _sh >= 1: _buys.append((asset, f"{_sh:,.0f}주 매수"))
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
        return apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.11);border-left:4px solid {_gc};padding:10px 18px;display:flex;align-items:center;gap:18px;"><div style="display:flex;align-items:center;gap:8px;flex-shrink:0;"><span style="font-family:DM Mono,monospace;font-size:0.56em;color:{tc_label};letter-spacing:0.18em;text-transform:uppercase;">Goal Tracker</span><span style="background:rgba({_gr},{_gg},{_gb},0.1);border:1px solid rgba({_gr},{_gg},{_gb},0.28);color:{_gc};font-family:DM Mono,monospace;font-size:0.55em;padding:1px 8px;">{_gbadge}</span></div><div style="flex:1;position:relative;padding-bottom:18px;">{_seg}<div style="height:8px;background:rgba(0,0,0,0.07);"><div style="height:8px;width:{_pct:.2f}%;background:linear-gradient(90deg,rgba({_gr},{_gg},{_gb},0.4),{_gc});"></div></div></div><div style="display:flex;gap:20px;flex-shrink:0;align-items:center;"><div style="text-align:center;"><div style="font-family:DM Mono,monospace;font-size:0.5em;color:{tc_label};text-transform:uppercase;letter-spacing:0.1em;">현재</div><div style="font-family:DM Mono,monospace;font-size:0.82em;color:{tc_body};font-variant-numeric:tabular-nums;">${total_val_usd:,.0f}<br><span style="font-size:0.7em;color:{tc_label};">₩{total_val_usd * cur_fx:,.0f}</span></div></div><div style="text-align:center;"><div style="font-family:DM Mono,monospace;font-size:0.5em;color:{tc_label};text-transform:uppercase;letter-spacing:0.1em;">목표</div><div style="font-family:DM Mono,monospace;font-size:0.82em;color:{tc_body};font-variant-numeric:tabular-nums;">${_goal:,.0f}<br><span style="font-size:0.7em;color:{tc_label};">₩{_goal * cur_fx:,.0f}</span></div></div><div style="text-align:right;padding-left:14px;border-left:1px solid rgba(0,0,0,0.08);"><span style="font-family:DM Mono,monospace;font-size:1.8em;font-weight:400;color:{_gc};font-variant-numeric:tabular-nums;letter-spacing:-1.5px;line-height:1;">{_pct_raw:.1f}%</span></div></div></div>')

    def _regime_card_html(horizontal=False):
        if horizontal: return apply_theme(f'<div style="background:rgba({r_c},{g_c},{b_c},0.07);border:1px solid rgba({r_c},{g_c},{b_c},0.22);border-left:4px solid {r_acc};padding:12px 20px;display:flex;align-items:center;gap:32px;"><div style="flex:1;"><div style="font-family:DM Mono,monospace;font-size:0.53em;color:{tc_label};letter-spacing:0.18em;text-transform:uppercase;margin-bottom:3px;">Current Regime</div><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.5em;font-weight:800;color:{r_acc};letter-spacing:-0.5px;line-height:1;margin-bottom:1px;">{regime_info[curr_regime][0]}</div><div style="font-family:DM Mono,monospace;font-size:0.6em;color:{tc_muted};letter-spacing:0.1em;text-transform:uppercase;">{regime_info[curr_regime][1]}</div></div><div style="width:1px;height:48px;background:rgba({r_c},{g_c},{b_c},0.2);flex-shrink:0;"></div><div style="flex:1;font-family:DM Mono,monospace;font-size:0.64em;color:{tc_muted};">{regime_committee_msg}</div></div>')
        else: return apply_theme(f'<div style="background:rgba({r_c},{g_c},{b_c},0.07);border:1px solid rgba({r_c},{g_c},{b_c},0.22);border-left:4px solid {r_acc};padding:14px 16px;margin-bottom:10px;"><div style="font-family:DM Mono,monospace;font-size:0.53em;color:{tc_label};letter-spacing:0.18em;text-transform:uppercase;margin-bottom:4px;">Current Regime</div><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.45em;font-weight:800;color:{r_acc};letter-spacing:-0.5px;line-height:1;margin-bottom:2px;">{regime_info[curr_regime][0]}</div><div style="font-family:DM Mono,monospace;font-size:0.6em;color:{tc_muted};letter-spacing:0.1em;text-transform:uppercase;">{regime_info[curr_regime][1]}</div><div style="margin-top:7px;padding-top:7px;border-top:1px solid rgba({r_c},{g_c},{b_c},0.18);font-family:DM Mono,monospace;font-size:0.58em;color:{tc_muted};">{regime_committee_msg}</div></div>')

    def _pf_editor(height=355):
        edata = []
        for a in target_assets:
            shares = float(active_pf[a].get('shares', 0.0))
            avg_p = float(active_pf[a].get('avg_price', 1.0 if a == 'CASH' else 0.0))
            cur_p = current_prices.get(a, 0.0)
            if is_isa:
                avg_display = avg_p * cur_fx
                cur_display = cur_p * cur_fx
            else:
                avg_display = avg_p
                cur_display = cur_p
            ret_pct = ((cur_p / avg_p) - 1) * 100 if a != 'CASH' and avg_p > 0 else 0.0
            if is_isa:
                _display_name = ISA_NAMES.get(a, a)
                edata.append({"Asset": a, "종목명": _display_name, "Shares": shares, "Avg Price(₩)": avg_display, "Current Price(₩)": cur_display, "Return(%)": ret_pct})
            elif is_toss:
                edata.append({"Asset": a, "Shares": shares, "Avg Price($)": avg_p, "Current Price($)": cur_p, "Return(%)": ret_pct})
            else:
                edata.append({"Asset": a, "Shares": shares, "Avg Price($)": avg_p, "Current Price($)": cur_p, "Return(%)": ret_pct})

        if is_isa:
            disabled_cols = ["Asset", "종목명", "Current Price(₩)", "Return(%)"]
            col_config = {
                "Asset": st.column_config.TextColumn("티커", width=100),
                "종목명": st.column_config.TextColumn("종목명", width=140),
                "Shares": st.column_config.NumberColumn("수량", format="%.4f"),
                "Avg Price(₩)": st.column_config.NumberColumn("평단(₩)", format="%.0f"),
                "Current Price(₩)": st.column_config.NumberColumn("현재가(₩)", format="%.0f"),
                "Return(%)": st.column_config.NumberColumn("수익률", format="%+.2f%%")
            }
        elif is_toss:
            disabled_cols = ["Return(%)"]
            col_config = {
                "Asset": st.column_config.TextColumn("Asset (종목)"),
                "Shares": st.column_config.NumberColumn("Shares", format="%.4f"),
                "Avg Price($)": st.column_config.NumberColumn("Avg($)", format="%.2f"),
                "Current Price($)": st.column_config.NumberColumn("Current($)", format="%.2f"),
                "Return(%)": st.column_config.NumberColumn("Ret(%)", format="%+.2f%%")
            }
        else:
            disabled_cols = ["Asset", "Current Price($)", "Return(%)"]
            col_config = {
                "Asset": st.column_config.TextColumn("Asset (종목)"),
                "Shares": st.column_config.NumberColumn("Shares", format="%.4f"),
                "Avg Price($)": st.column_config.NumberColumn("Avg($)", format="%.2f"),
                "Current Price($)": st.column_config.NumberColumn("Current($)", format="%.2f"),
                "Return(%)": st.column_config.NumberColumn("Ret(%)", format="%+.2f%%")
            }

        row_mode = "dynamic" if is_toss else "fixed"
        _df_orig = pd.DataFrame(edata) if edata else pd.DataFrame()

        _editor_key = f"pf_editor_{st.session_state.acc_tab}"
        df_edited = st.data_editor(
            _df_orig,
            disabled=disabled_cols, hide_index=True, num_rows=row_mode,
            use_container_width=True, height=height, column_config=col_config,
            key=_editor_key
        )

        if not _df_orig.equals(df_edited):
            if is_toss:
                new_pf = {}
                for _, row in df_edited.iterrows():
                    asset_name = str(row["Asset"]).strip()
                    if asset_name and asset_name.lower() != "nan":
                        new_pf[asset_name] = {'shares': float(row["Shares"] if pd.notna(row["Shares"]) else 0.0), 'avg_price': float(row["Avg Price($)"] if pd.notna(row["Avg Price($)"]) else 0.0), 'cur_price': float(row["Current Price($)"] if pd.notna(row["Current Price($)"]) else 0.0)}
                active_pf.clear()
                active_pf.update(new_pf)
            elif is_isa:
                for _, row in df_edited.iterrows():
                    _avg_krw = float(row["Avg Price(₩)"])
                    _avg_usd = _avg_krw / cur_fx if cur_fx > 0 else 0.0
                    active_pf[row["Asset"]] = {'shares': float(row["Shares"]), 'avg_price': _avg_usd}
            else:
                for _, row in df_edited.iterrows():
                    active_pf[row["Asset"]] = {'shares': float(row["Shares"]), 'avg_price': float(row["Avg Price($)"])}
            save_portfolio_to_disk(); st.session_state.rebal_locked=False; st.rerun()

    def _pie_charts():
        _pie_colors, _pie_cfg = [line_c,'#B0B0BE','#34D399','#6EE7B7','#A7F3D0','#059669','#047857','#065F46','#D1FAE5'], dict(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(family="DM Mono", color=t_color), showlegend=True, legend=dict(orientation='v', x=1.0, y=0.5, font=dict(size=8, family='DM Mono'), bgcolor='rgba(0,0,0,0)'), margin=dict(l=0, r=70, t=28, b=0), height=200)
        _rb1, _rb2 = st.columns(2)
        _lcur, _vcur = [a for a in target_assets if curr_vals.get(a, 0) > 0], [curr_vals.get(a, 0) for a in target_assets if curr_vals.get(a, 0) > 0]
        
        with _rb1:
            if sum(_vcur) > 0:
                _fc = go.Figure(go.Pie(labels=_lcur, values=_vcur, hole=.55, textinfo='percent', textfont=dict(size=9), marker=dict(colors=_pie_colors, line=dict(color='#FAFAF7', width=1.5))))
                _fc.update_layout(title=dict(text="Current", font=dict(family="DM Mono", size=11, color=t_color), x=0), **_pie_cfg)
                with st.container(border=True): st.plotly_chart(_fc, use_container_width=True)
            else: st.markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.09);height:200px;display:flex;align-items:center;justify-content:center;"><span style="font-family:DM Mono,monospace;font-size:0.7em;color:#CCCCCC;">포지션 없음</span></div>', unsafe_allow_html=True)
        
        _ltgt, _vtgt = [a for a in target_assets if target_weights.get(a, 0) > 0], [target_weights.get(a, 0) for a in target_assets if target_weights.get(a, 0) > 0]
        with _rb2:
            if _vtgt:
                _ft = go.Figure(go.Pie(labels=_ltgt, values=_vtgt, hole=.55, textinfo='percent', textfont=dict(size=9), marker=dict(colors=_pie_colors, line=dict(color='#FAFAF7', width=1.5))))
                _ft.update_layout(title=dict(text=f"Target  R{curr_regime}", font=dict(family="DM Mono", size=11, color=t_color), x=0), **_pie_cfg)
                with st.container(border=True): st.plotly_chart(_ft, use_container_width=True)
            else:
                st.markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.09);height:200px;display:flex;flex-direction:column;align-items:center;justify-content:center;"><span style="font-family:DM Mono,monospace;font-size:0.7em;color:#CCCCCC;">자유 적립식 계좌</span><span style="font-family:DM Mono,monospace;font-size:0.5em;color:#DDDDDD;margin-top:4px;">(목표 비중 없음)</span></div>', unsafe_allow_html=True)

    def _delta_bar():
        _dlabels, _dvals = [a for a in target_assets if abs(live_diff_vals.get(a, 0)) >= 1.0], [live_diff_vals.get(a, 0) for a in target_assets if abs(live_diff_vals.get(a, 0)) >= 1.0]
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

    def generate_rebal_plan():
        _s_px, _s_vals, _s_total, _s_tgtw = dict(current_prices), dict(curr_vals), total_val_usd, dict(target_weights)
        _s_diff = {a: (_s_total * _s_tgtw.get(a, 0.0)) - _s_vals.get(a, 0.0) for a in ASSET_LIST}
        _sell_list, _buy_list, _hold_list = [], [], []
        for asset in ASSET_LIST:
            if asset == 'CASH': 
                _hold_list.append(asset)
                continue
            _cp = _s_px.get(asset, 1.0) if _s_px.get(asset, 0.0) > 0 else 1.0
            _diff = _s_diff.get(asset, 0.0)
            _threshold, _sh = _cp * 0.05, int(abs(_diff) / _cp)
            if _diff < -_threshold and _sh >= 1: _sell_list.append((asset, -(_sh * _cp), _sh, _cp))
            elif _diff > _threshold and _sh >= 1: _buy_list.append((asset, (_sh * _cp), _sh, _cp))
            elif _s_vals.get(asset, 0.0) > 0 or _s_tgtw.get(asset, 0) > 0: _hold_list.append(asset)
        _sell_list.sort(key=lambda x: x[1]); _buy_list.sort(key=lambda x: -x[1])
        st.session_state.rebal_plan = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "total": _s_total, "regime": curr_regime, "sells": _sell_list, "buys": _buy_list, "holds": _hold_list, "prices": _s_px, "vals": _s_vals, "tgtw": _s_tgtw}
        st.session_state.rebal_locked = True

    def _rebalancing_matrix(is_mobile=False):
        if total_val_usd <= 0:
            st.markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.09);padding:28px;text-align:center;"><span style="font-family:DM Mono,monospace;font-size:0.8em;color:#CCCCCC;">포지션을 입력하면 리밸런싱 매트릭스가 표시됩니다.</span></div>', unsafe_allow_html=True)
            return
        if not st.session_state.rebal_locked or not st.session_state.rebal_plan:
            st.markdown(apply_theme(f'<div style="background:rgba(217,119,6,0.08);border:1px solid rgba(217,119,6,0.3);padding:16px;text-align:center;margin-bottom:14px;"><div style="font-size:0.85em;color:#D97706;margin-bottom:10px;">리밸런싱 도중 포지션 변경 시 지침이 바뀌는 것을 방지하려면<br>현재 상태를 <b>고정(Snapshot)</b>해야 합니다.</div></div>'), unsafe_allow_html=True)
            if st.button("📸 리밸런싱 액션 플랜 생성 (지침 고정)", use_container_width=True): generate_rebal_plan(); st.rerun()
            return

        plan = st.session_state.rebal_plan
        _c1, _c2 = st.columns([3, 1]) if not is_mobile else st.columns([2,1])
        with _c1: st.markdown(apply_theme(f'<div style="background:rgba({r_c},{g_c},{b_c},0.07);border:1px solid rgba({r_c},{g_c},{b_c},0.22);padding:8px 14px;display:flex;align-items:center;gap:8px;"><span style="font-family:DM Mono,monospace;font-size:0.62em;color:{main_color};">✔ 고정된 플랜 — {plan["ts"]}</span></div>'), unsafe_allow_html=True)
        with _c2:
            if st.button("🔄 초기화", use_container_width=True, key=f"reset_plan_{is_mobile}"): st.session_state.rebal_locked = False; st.session_state.rebal_plan = None; st.rerun()
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        _s_total, _s_tgtw, _s_vals = plan["total"], plan["tgtw"], plan["vals"]
        _sell_list, _buy_list = plan["sells"], plan["buys"]
        _total_sell_proceeds = sum(abs(d) for a, d, sh, cp in _sell_list)
        _existing_cash = _s_vals.get('CASH', 0.0)
        _available_cash = _total_sell_proceeds + _existing_cash
        _total_buy_needed = sum(d for a, d, sh, cp in _buy_list)

        if not is_mobile:
            _ep1, _ep2, _ep3 = st.columns([1, 0.12, 1])
            with _ep1:
                _sell_rows = ""
                for asset, diff, sh, cp in _sell_list:
                    _sell_rows += f'<tr style="background:rgba(220,38,38,0.025);"><td style="font-weight:700;color:#059669;font-family:DM Mono,monospace;font-size:0.84em;">{asset}</td><td style="color:{tc_muted};">${cp:.2f}</td><td style="color:{tc_label};">{_s_vals[asset]:,.0f}</td><td style="color:{main_color};font-weight:700;">{_s_tgtw.get(asset,0)*100:.0f}%</td><td style="color:{tc_label};">{_s_total * _s_tgtw.get(asset, 0.0):,.0f}</td><td><span style="color:#DC2626;font-weight:600;">-${abs(diff):,.0f}</span></td><td><span style="font-family:DM Mono,monospace;font-size:0.7em;font-weight:700;color:#DC2626;background:rgba(220,38,38,0.08);padding:2px 8px;border-left:2px solid #DC2626;">▼ SELL</span></td><td style="color:{tc_muted};font-size:0.8em;">{int(sh):,.0f}주</td></tr>'
                st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.58em;font-weight:700;color:#DC2626;letter-spacing:0.16em;text-transform:uppercase;margin-bottom:6px;padding-bottom:5px;border-bottom:2px solid #DC2626;">STEP 1  ·  매도 실행</div>', unsafe_allow_html=True)
                if _sell_rows:
                    with st.container(border=True): st.markdown('<div style="overflow-x:auto;"><table class="mint-table"><thead><tr><th style="text-align:left;">Asset</th><th>기준가</th><th>기준액</th><th>목표%</th><th>목표액</th><th>매도금액</th><th style="text-align:center;">Action</th><th>수량</th></tr></thead><tbody>' + _sell_rows + '</tbody></table></div>', unsafe_allow_html=True)
                    st.markdown(apply_theme(f'<div style="background:rgba(220,38,38,0.05);border:1px solid rgba(220,38,38,0.2);padding:8px 14px;margin-top:6px;"><span style="font-family:DM Mono,monospace;font-size:0.62em;color:#DC2626;font-weight:600;">매각 대금  ${_total_sell_proceeds:,.0f}</span>{f"  <span style=\'color:{tc_label};\'>+ 보유현금 ${_existing_cash:,.0f}</span>" if _existing_cash > 1 else ""}  →  <span style="color:{tc_body};font-weight:700;">가용 현금 ${_available_cash:,.0f}</span></div>'), unsafe_allow_html=True)
                else: st.markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.09);padding:20px;text-align:center;"><span style="font-family:DM Mono,monospace;font-size:0.72em;color:#CCCCCC;">매도 항목 없음</span></div>', unsafe_allow_html=True)
            with _ep2: st.markdown(f'<div style="display:flex;align-items:center;justify-content:center;height:100%;min-height:120px;font-size:1.6em;color:{tc_label};">→</div>', unsafe_allow_html=True)
            with _ep3:
                _remaining_cash, _buy_rows = _available_cash, ""
                for asset, diff, sh, cp in _buy_list:
                    _actual_sh = int(min(sh, _remaining_cash / cp)) 
                    _actual_buy = _actual_sh * cp
                    if _actual_sh < 1: continue
                    _shortfall, _buy_color = diff - _actual_buy, "#059669" if _actual_buy >= diff * 0.95 else "#D97706"
                    _buy_rows += f'<tr style="background:rgba(5,150,105,0.025);"><td style="font-weight:700;color:#059669;font-family:DM Mono,monospace;font-size:0.84em;">{asset}</td><td style="color:{tc_muted};">${cp:.2f}</td><td style="color:{tc_label};">{_s_vals[asset]:,.0f}</td><td style="color:{main_color};font-weight:700;">{_s_tgtw.get(asset,0)*100:.0f}%</td><td style="color:{tc_label};">{_s_total * _s_tgtw.get(asset, 0.0):,.0f}</td><td><span style="color:{_buy_color};font-weight:600;">+${_actual_buy:,.0f}</span>{f"<span style=\'font-family:DM Mono,monospace;font-size:0.62em;color:#D97706;margin-left:4px;\'>(부족 ${_shortfall:,.0f})</span>" if _shortfall > 1 else ""}</td><td><span style="font-family:DM Mono,monospace;font-size:0.7em;font-weight:700;color:{_buy_color};background:rgba(5,150,105,0.09);padding:2px 8px;border-left:2px solid {_buy_color};">▲ BUY</span></td><td style="color:{tc_muted};font-size:0.8em;">{int(_actual_sh):,.0f}주</td></tr>'
                    _remaining_cash -= _actual_buy
                    if _remaining_cash <= 0: break
                st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.58em;font-weight:700;color:#059669;letter-spacing:0.16em;text-transform:uppercase;margin-bottom:6px;padding-bottom:5px;border-bottom:2px solid #059669;">STEP 2  ·  매수 실행</div>', unsafe_allow_html=True)
                if _buy_rows:
                    with st.container(border=True): st.markdown('<div style="overflow-x:auto;"><table class="mint-table"><thead><tr><th style="text-align:left;">Asset</th><th>기준가</th><th>기준액</th><th>목표%</th><th>목표액</th><th>매수금액</th><th style="text-align:center;">Action</th><th>수량</th></tr></thead><tbody>' + _buy_rows + '</tbody></table></div>', unsafe_allow_html=True)
                    st.markdown(apply_theme(f'<div style="background:rgba({r_c},{g_c},{b_c},0.06);border:1px solid rgba({r_c},{g_c},{b_c},0.22);padding:8px 14px;margin-top:6px;"><span style="font-family:DM Mono,monospace;font-size:0.62em;color:{main_color};font-weight:600;">총 매수 ${min(_total_buy_needed, _available_cash):,.0f}</span>{f"  <span style=\'color:{tc_label};\'>잔여 현금 ${max(_remaining_cash, 0):,.0f}</span>" if max(_remaining_cash, 0) > 1 else ""}</div>'), unsafe_allow_html=True)
                else: st.markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.09);padding:20px;text-align:center;"><span style="font-family:DM Mono,monospace;font-size:0.72em;color:#CCCCCC;">매수 항목 없음</span></div>', unsafe_allow_html=True)
            if plan["holds"]: st.markdown(f'<div style="display:flex;align-items:center;gap:10px;margin-top:10px;padding:8px 14px;background:#FAFAF7;border:1px solid rgba(0,0,0,0.09);"><span style="font-family:DM Mono,monospace;font-size:0.58em;color:{tc_label};letter-spacing:0.14em;text-transform:uppercase;white-space:nowrap;">HOLD</span><div style="display:flex;gap:4px;flex-wrap:wrap;">{" ".join([f"<span style=\'background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);font-family:DM Mono,monospace;font-size:0.68em;color:{tc_label};padding:2px 10px;\'>{a}</span>" for a in plan["holds"]])}</div></div>', unsafe_allow_html=True)
        else:
            st.markdown(apply_theme(f'<div style="background:rgba(220,38,38,0.05);border:1px solid rgba(220,38,38,0.2);padding:8px 14px;margin-bottom:10px;"><span style="font-family:DM Mono,monospace;font-size:0.62em;color:#DC2626;font-weight:600;">매각 대금  ${_total_sell_proceeds:,.0f}</span>{f"  <span style=\'color:{tc_label};\'>+ 보유현금 ${_existing_cash:,.0f}</span>" if _existing_cash > 1 else ""}  →  <span style="color:{tc_body};font-weight:700;">가용 현금 ${_available_cash:,.0f}</span></div>'), unsafe_allow_html=True)
            _remaining_cash = _available_cash
            for action_type, lst in [("SELL", _sell_list), ("BUY", _buy_list)]:
                for asset, diff, sh, cp in lst:
                    if action_type == "BUY":
                        _actual_sh = int(min(sh, _remaining_cash / cp))
                        _actual_buy = _actual_sh * cp
                        if _actual_sh < 1: continue
                        _diff_to_show, _sh_to_show = _actual_buy, _actual_sh
                        _remaining_cash -= _actual_buy
                    else: _diff_to_show, _sh_to_show = abs(diff), sh
                    _curv, _tgtw = _s_vals.get(asset, 0), _s_tgtw.get(asset, 0.0)
                    _curw = (_curv / _s_total * 100) if _s_total > 0 else 0
                    _act_txt, _act_c, _rbg = ("▲ BUY", "#059669", "rgba(5,150,105,0.035)") if action_type=="BUY" else ("▼ SELL", "#DC2626", "rgba(220,38,38,0.035)")
                    st.markdown(apply_theme(f'<div style="background:{_rbg};border:1px solid rgba(0,0,0,0.09);border-left:3px solid {_act_c};padding:10px 14px;margin-bottom:5px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;"><span style="font-family:DM Mono,monospace;font-size:0.88em;font-weight:700;color:#059669;">{asset}</span><span style="font-family:DM Mono,monospace;font-size:0.76em;font-weight:700;color:{_act_c};background:rgba(0,0,0,0.04);padding:3px 10px;border:1px solid {_act_c}40;">{_act_txt}</span></div><div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:4px;"><div><div style="font-family:DM Mono,monospace;font-size:0.52em;color:{tc_label};text-transform:uppercase;">기준액</div><div style="font-family:DM Mono,monospace;font-size:0.78em;color:{tc_body};font-variant-numeric:tabular-nums;">${_curv:,.0f} <span style="font-size:0.7em;color:{tc_label};">({_curw:.0f}%)</span></div></div><div><div style="font-family:DM Mono,monospace;font-size:0.52em;color:{tc_label};text-transform:uppercase;">목표 %</div><div style="font-family:DM Mono,monospace;font-size:0.78em;color:{main_color};font-weight:600;">{_tgtw*100:.0f}%</div></div><div><div style="font-family:DM Mono,monospace;font-size:0.52em;color:{tc_label};text-transform:uppercase;">Δ 금액</div><div style="font-family:DM Mono,monospace;font-size:0.78em;color:{_act_c};font-weight:600;">{"+$" if action_type=="BUY" else "-$"}{_diff_to_show:,.0f}</div></div><div><div style="font-family:DM Mono,monospace;font-size:0.52em;color:{tc_label};text-transform:uppercase;">수량</div><div style="font-family:DM Mono,monospace;font-size:0.78em;color:{_act_c};font-weight:600;font-variant-numeric:tabular-nums;">{int(_sh_to_show):,.0f}주</div></div></div></div>'), unsafe_allow_html=True)
            if plan["holds"]: st.markdown(f'<div style="display:flex;align-items:center;gap:10px;margin-top:10px;padding:8px 14px;background:#FAFAF7;border:1px solid rgba(0,0,0,0.09);"><span style="font-family:DM Mono,monospace;font-size:0.58em;color:{tc_label};letter-spacing:0.14em;text-transform:uppercase;white-space:nowrap;">HOLD</span><div style="display:flex;gap:4px;flex-wrap:wrap;">{" ".join([f"<span style=\'background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);font-family:DM Mono,monospace;font-size:0.68em;color:{tc_label};padding:2px 10px;\'>{a}</span>" for a in plan["holds"]])}</div></div>', unsafe_allow_html=True)

    if display_mode == "PC":
        _gi_col, _gb_col = st.columns([st.session_state.lc_goal_inp, 100 - st.session_state.lc_goal_inp])
        with _gi_col:
            new_goal = st.number_input("목표금액", min_value=1000.0, max_value=100_000_000.0, value=st.session_state.goal_usd, step=1000.0, format="%.0f", key="goal_input", label_visibility="collapsed")
            if new_goal != st.session_state.goal_usd: st.session_state.goal_usd = new_goal; st.rerun()
            st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.6em;color:{tc_label};text-align:center;margin-top:-4px;">목표 금액 (USD)</div>', unsafe_allow_html=True)
        with _gb_col: st.markdown(_goal_tracker_html(), unsafe_allow_html=True)
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        if is_toss:
            # — 토스 스타일 종목 카드 —
            def _toss_card(ticker, shares, avg_p, cur_p, cur_fx_val):
                if shares <= 0: return ""
                pnl_pct_card = ((cur_p / avg_p) - 1) * 100 if avg_p > 0 else 0.0
                pnl_usd_card = (cur_p - avg_p) * shares if avg_p > 0 else 0.0
                total_usd = cur_p * shares
                total_krw = total_usd * cur_fx_val
                pnl_color = "#059669" if pnl_pct_card >= 0 else "#DC2626"
                pnl_arrow = "▲" if pnl_pct_card >= 0 else "▼"
                return f'''<div style="background:#FFFFFF;border:1px solid rgba(0,0,0,0.08);border-radius:16px;padding:20px 22px;margin-bottom:10px;transition:box-shadow 0.2s;">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                        <div>
                            <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:1.05em;font-weight:700;color:#0F172A;">{ticker}</div>
                            <div style="font-family:'DM Mono',monospace;font-size:0.65em;color:#9494A0;margin-top:2px;">{shares:.4g}주 보유</div>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-family:'DM Mono',monospace;font-size:1.15em;font-weight:700;color:#0F172A;">${cur_p:,.2f}</div>
                            <div style="font-family:'DM Mono',monospace;font-size:0.72em;color:{pnl_color};font-weight:600;margin-top:2px;">{pnl_arrow} {pnl_pct_card:+.2f}%</div>
                        </div>
                    </div>
                    <div style="margin-top:14px;padding-top:12px;border-top:1px solid rgba(0,0,0,0.06);display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;">
                        <div>
                            <div style="font-family:'DM Mono',monospace;font-size:0.52em;color:#9494A0;letter-spacing:0.1em;text-transform:uppercase;">평균단가</div>
                            <div style="font-family:'DM Mono',monospace;font-size:0.82em;color:#4A4A57;">${avg_p:,.2f}</div>
                        </div>
                        <div>
                            <div style="font-family:'DM Mono',monospace;font-size:0.52em;color:#9494A0;letter-spacing:0.1em;text-transform:uppercase;">평가금액</div>
                            <div style="font-family:'DM Mono',monospace;font-size:0.82em;color:#0F172A;">${total_usd:,.0f}</div>
                            <div style="font-family:'DM Mono',monospace;font-size:0.62em;color:#9494A0;">₩{total_krw:,.0f}</div>
                        </div>
                        <div>
                            <div style="font-family:'DM Mono',monospace;font-size:0.52em;color:#9494A0;letter-spacing:0.1em;text-transform:uppercase;">수익금</div>
                            <div style="font-family:'DM Mono',monospace;font-size:0.82em;color:{pnl_color};font-weight:600;">{pnl_arrow} ${abs(pnl_usd_card):,.0f}</div>
                        </div>
                    </div>
                </div>'''

            _toss_total_usd = sum(active_pf[t].get('shares',0) * current_prices.get(t,0) for t in target_assets)
            _toss_total_cost = sum(active_pf[t].get('shares',0) * active_pf[t].get('avg_price',0) for t in target_assets)
            _toss_pnl = _toss_total_usd - _toss_total_cost
            _toss_pnl_pct = (_toss_pnl / _toss_total_cost * 100) if _toss_total_cost > 0 else 0.0
            _toss_pnl_c = "#059669" if _toss_pnl >= 0 else "#DC2626"

            st.markdown(apply_theme(f'''<div style="background:linear-gradient(135deg, #FAFAF7 0%, #F0FDF4 100%);border:1px solid rgba(0,0,0,0.08);border-radius:20px;padding:24px 28px;margin-bottom:16px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div style="font-family:'DM Mono',monospace;font-size:0.6em;color:#9494A0;letter-spacing:0.2em;text-transform:uppercase;">TOSS 장기투자</div>
                        <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:2em;font-weight:800;color:#0F172A;letter-spacing:-1px;margin-top:4px;">${_toss_total_usd:,.0f}</div>
                        <div style="font-family:'DM Mono',monospace;font-size:0.78em;color:#9494A0;margin-top:2px;">₩{_toss_total_usd * cur_fx:,.0f}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-family:'DM Mono',monospace;font-size:1.4em;font-weight:700;color:{_toss_pnl_c};">{"▲" if _toss_pnl >= 0 else "▼"} {_toss_pnl_pct:+.2f}%</div>
                        <div style="font-family:'DM Mono',monospace;font-size:0.78em;color:{_toss_pnl_c};">{"+" if _toss_pnl >= 0 else ""}${_toss_pnl:,.0f}</div>
                        <div style="font-family:'DM Mono',monospace;font-size:0.58em;color:#9494A0;margin-top:4px;">투자원금 ${_toss_total_cost:,.0f}</div>
                    </div>
                </div>
            </div>'''), unsafe_allow_html=True)

            t_col_l, t_col_r = st.columns([1.2, 1])
            with t_col_l:
                st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.6em;color:{tc_label};letter-spacing:0.18em;text-transform:uppercase;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid rgba(0,0,0,0.08);">보유 종목  ·  {len([t for t in target_assets if active_pf[t].get("shares",0) > 0])}개</div>', unsafe_allow_html=True)
                _has_holdings = False
                for t in sorted(target_assets, key=lambda x: active_pf[x].get('shares',0) * current_prices.get(x,0), reverse=True):
                    _sh = active_pf[t].get('shares', 0)
                    if _sh > 0:
                        _has_holdings = True
                        _avg = active_pf[t].get('avg_price', 0)
                        _cur = current_prices.get(t, 0)
                        st.markdown(_toss_card(t, _sh, _avg, _cur, cur_fx), unsafe_allow_html=True)
                if not _has_holdings:
                    st.markdown(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.08);border-radius:16px;padding:40px;text-align:center;"><div style="font-size:2em;margin-bottom:8px;">🌱</div><div style="font-family:DM Mono,monospace;font-size:0.78em;color:#9494A0;">아래 에디터에서 종목을 추가하세요</div></div>', unsafe_allow_html=True)
            with t_col_r:
                # ── 종목별 수익률 바 ──
                _holdings = [(t, active_pf[t].get('shares',0), active_pf[t].get('avg_price',0), current_prices.get(t,0)) for t in target_assets if active_pf[t].get('shares',0) > 0]
                _rets = [((cp/ap)-1)*100 for _,s,ap,cp in _holdings if ap > 0 and cp > 0]
                _best = max(_holdings, key=lambda x: ((x[3]/x[2])-1)*100 if x[2]>0 else -999) if _holdings else None
                _worst = min(_holdings, key=lambda x: ((x[3]/x[2])-1)*100 if x[2]>0 else 999) if _holdings else None
                _avg_ret = sum(_rets)/len(_rets) if _rets else 0

                with st.container(border=True):
                    st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.55em;font-weight:600;color:{tc_label};letter-spacing:0.18em;text-transform:uppercase;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid rgba(0,0,0,0.08);">종목별 수익률</div>', unsafe_allow_html=True)
                    if _holdings:
                        _sorted_ret = sorted(_holdings, key=lambda x: ((x[3]/x[2])-1)*100 if x[2]>0 else 0, reverse=True)
                        _max_abs = max(abs(((cp/ap)-1)*100) for _,_,ap,cp in _sorted_ret if ap>0) if _sorted_ret else 1
                        _ret_html = ""
                        for _rt, _rs, _ra, _rc in _sorted_ret:
                            if _ra <= 0: continue
                            _rpct = ((_rc/_ra)-1)*100
                            _rc2 = "#059669" if _rpct >= 0 else "#DC2626"
                            _bar_w = abs(_rpct) / max(_max_abs, 1) * 45
                            if _rpct >= 0:
                                _bar = f'<div style="display:flex;align-items:center;height:8px;"><div style="width:50%;"></div><div style="width:{_bar_w}%;height:8px;background:{_rc2};border-radius:0 4px 4px 0;"></div></div>'
                            else:
                                _bar = f'<div style="display:flex;align-items:center;height:8px;direction:rtl;"><div style="width:50%;"></div><div style="width:{_bar_w}%;height:8px;background:{_rc2};border-radius:4px 0 0 4px;"></div></div>'
                            _ret_html += f'''<div style="display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid rgba(0,0,0,0.04);">
                                <span style="font-family:DM Mono,monospace;font-size:0.78em;font-weight:700;color:#0F172A;min-width:50px;">{_rt}</span>
                                <div style="flex:1;">{_bar}</div>
                                <span style="font-family:DM Mono,monospace;font-size:0.74em;font-weight:600;color:{_rc2};min-width:52px;text-align:right;">{_rpct:+.1f}%</span>
                            </div>'''
                        st.markdown(_ret_html, unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div style="padding:20px;text-align:center;font-family:DM Mono,monospace;font-size:0.72em;color:#CCCCCC;">종목을 추가하세요</div>', unsafe_allow_html=True)

                st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

                # ── 투자 요약 카드 ──
                with st.container(border=True):
                    st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.55em;font-weight:600;color:{tc_label};letter-spacing:0.18em;text-transform:uppercase;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid rgba(0,0,0,0.08);">투자 요약</div>', unsafe_allow_html=True)
                    st.markdown(f'''<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                        <div style="background:#FAFAF7;border-radius:10px;padding:12px 14px;border:1px solid rgba(0,0,0,0.05);">
                            <div style="font-family:DM Mono,monospace;font-size:0.52em;color:#9494A0;letter-spacing:0.1em;text-transform:uppercase;">보유 종목</div>
                            <div style="font-family:DM Mono,monospace;font-size:1.3em;font-weight:700;color:#0F172A;">{len(_holdings)}개</div>
                        </div>
                        <div style="background:#FAFAF7;border-radius:10px;padding:12px 14px;border:1px solid rgba(0,0,0,0.05);">
                            <div style="font-family:DM Mono,monospace;font-size:0.52em;color:#9494A0;letter-spacing:0.1em;text-transform:uppercase;">평균 수익률</div>
                            <div style="font-family:DM Mono,monospace;font-size:1.3em;font-weight:700;color:{"#059669" if _avg_ret>=0 else "#DC2626"};">{_avg_ret:+.1f}%</div>
                        </div>
                        <div style="background:#FAFAF7;border-radius:10px;padding:12px 14px;border:1px solid rgba(0,0,0,0.05);">
                            <div style="font-family:DM Mono,monospace;font-size:0.52em;color:#9494A0;letter-spacing:0.1em;text-transform:uppercase;">🏆 최고 수익</div>
                            <div style="font-family:DM Mono,monospace;font-size:0.88em;font-weight:700;color:#059669;">{_best[0] if _best else "—"}</div>
                            <div style="font-family:DM Mono,monospace;font-size:0.68em;color:#059669;">{((_best[3]/_best[2])-1)*100:+.1f}%</div>
                        </div>
                        <div style="background:#FAFAF7;border-radius:10px;padding:12px 14px;border:1px solid rgba(0,0,0,0.05);">
                            <div style="font-family:DM Mono,monospace;font-size:0.52em;color:#9494A0;letter-spacing:0.1em;text-transform:uppercase;">📉 최저 수익</div>
                            <div style="font-family:DM Mono,monospace;font-size:0.88em;font-weight:700;color:#DC2626;">{_worst[0] if _worst else "—"}</div>
                            <div style="font-family:DM Mono,monospace;font-size:0.68em;color:#DC2626;">{((_worst[3]/_worst[2])-1)*100:+.1f}%</div>
                        </div>
                    </div>''', unsafe_allow_html=True)

                st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

                # ── 종목별 비중 랭킹 ──
                with st.container(border=True):
                    st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.55em;font-weight:600;color:{tc_label};letter-spacing:0.18em;text-transform:uppercase;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid rgba(0,0,0,0.08);">비중 랭킹</div>', unsafe_allow_html=True)
                    if _holdings and _toss_total_usd > 0:
                        _sorted_h = sorted(_holdings, key=lambda x: x[1]*x[3], reverse=True)
                        _rank_html = ""
                        for _ri, (_rt, _rs, _ra, _rc) in enumerate(_sorted_h):
                            _rval = _rs * _rc
                            _rpct = (_rval / _toss_total_usd * 100)
                            _rank_html += f'''<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid rgba(0,0,0,0.04);">
                                <span style="font-family:DM Mono,monospace;font-size:0.62em;color:#9494A0;min-width:18px;">{_ri+1}</span>
                                <span style="font-family:DM Mono,monospace;font-size:0.82em;font-weight:700;color:#0F172A;min-width:55px;">{_rt}</span>
                                <div style="flex:1;height:6px;background:rgba(0,0,0,0.05);border-radius:3px;overflow:hidden;">
                                    <div style="height:6px;width:{min(_rpct, 100):.1f}%;background:linear-gradient(90deg, {main_color}88, {main_color});border-radius:3px;"></div>
                                </div>
                                <span style="font-family:DM Mono,monospace;font-size:0.74em;color:{main_color};font-weight:600;min-width:42px;text-align:right;">{_rpct:.1f}%</span>
                            </div>'''
                        st.markdown(_rank_html, unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div style="padding:20px;text-align:center;font-family:DM Mono,monospace;font-size:0.72em;color:#CCCCCC;">종목을 추가하세요</div>', unsafe_allow_html=True)

                st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

                # ── 장기 투자 원칙 ──
                with st.container(border=True):
                    st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:0.55em;font-weight:600;color:{tc_label};letter-spacing:0.18em;text-transform:uppercase;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid rgba(0,0,0,0.08);">장기 투자 원칙</div>', unsafe_allow_html=True)
                    st.markdown(f'''<div style="font-family:DM Sans,sans-serif;font-size:0.82em;color:{tc_muted};line-height:1.8;">
                        <div style="padding:6px 0;border-bottom:1px solid rgba(0,0,0,0.04);">🌱 <b style="color:{tc_body};">분할매수(최소 5분할)</b>로 적립식 투자 진행</div>
                        <div style="padding:6px 0;border-bottom:1px solid rgba(0,0,0,0.04);">🔕 <b style="color:{tc_body};">기대 수익률 달성 시</b> 미련 없이 수익 실현하기</div>
                        <div style="padding:6px 0;border-bottom:1px solid rgba(0,0,0,0.04);">📊 <b style="color:{tc_body};">분기 1회</b> 비중 점검 (리밸런싱 X)</div>
                        <div style="padding:6px 0;">💎 <b style="color:{tc_body};">최소 3년</b> 이상 보유 목표</div>
                    </div>''', unsafe_allow_html=True)

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown(_sl("TOSS Portfolio Editor"), unsafe_allow_html=True)
                _pf_editor(300)
        else:
            _col_l, _col_r = st.columns([st.session_state.lc_lr_split, 100 - st.session_state.lc_lr_split])
            with _col_l:
                with st.container(border=True):
                    st.markdown(_sl("Position Input"), unsafe_allow_html=True)
                    _pf_editor(st.session_state.lc_editor_h)
                    if st.session_state.lc_show_lp:
                        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True); st.markdown(_sl("Live Prices"), unsafe_allow_html=True); st.markdown(_lp_build(), unsafe_allow_html=True)
                    if st.session_state.lc_show_qo:
                        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True); st.markdown(_sl("Quick Orders"), unsafe_allow_html=True)
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
            st.markdown(apply_theme(f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;"><div style="width:2px;height:12px;background:{main_color};flex-shrink:0;"></div><span style="font-family:DM Mono,monospace;font-size:0.58em;font-weight:600;color:{tc_heading};letter-spacing:0.2em;text-transform:uppercase;">Rebalancing Matrix</span><div style="flex:1;height:1px;background:rgba(0,0,0,0.09);"></div><span style="font-family:DM Mono,monospace;font-size:0.56em;color:{tc_label};">R{curr_regime} · {regime_info[curr_regime][1]}</span></div>'), unsafe_allow_html=True)
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
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True); st.markdown(_sl("Live Prices"), unsafe_allow_html=True); st.markdown(_lp_build(), unsafe_allow_html=True)
                if not is_toss:
                    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True); st.markdown(_sl("Quick Orders"), unsafe_allow_html=True)
                    _sells, _buys = _sells_buys(); _tqo1, _tqo2 = st.columns(2)
                    with _tqo1: _qo_build(_tqo1, "🔴  SELL", _sells, "#DC2626", "rgba(220,38,38,0.03)")
                    with _tqo2: _qo_build(_tqo2, "🟢  BUY", _buys, "#059669", "rgba(5,150,105,0.03)")
        with _tc_r:
            _pie_charts(); st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            if not is_toss:
                _tr1, _tr2 = st.columns(2)
                with _tr1: _delta_bar()
                with _tr2: _target_weights_block()
        if not is_toss:
            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
            st.markdown(apply_theme(f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;"><div style="width:2px;height:14px;background:{main_color};flex-shrink:0;"></div><span style="font-family:DM Mono,monospace;font-size:0.66em;font-weight:600;color:{tc_heading};letter-spacing:0.18em;text-transform:uppercase;">Rebalancing Matrix</span><div style="flex:1;height:1px;background:rgba(0,0,0,0.09);"></div><span style="font-family:DM Mono,monospace;font-size:0.62em;color:{tc_label};">R{curr_regime} · {regime_info[curr_regime][1]}</span></div>'), unsafe_allow_html=True)
            _rebalancing_matrix()

    elif display_mode == "Mobile":
        st.markdown(f"""<style>.main .block-container {{ max-width: 460px !important; padding: 0.4rem 0.3rem 2rem !important; margin: 0 auto !important; }} .stApp {{ font-size: 11px !important; }} [data-testid="stDataEditor"] td, [data-testid="stDataEditor"] th {{ font-size: 0.88em !important; padding: 8px 6px !important; }} [data-testid="stButton"] > button {{ padding: 10px 14px !important; min-height: 40px !important; }} [data-testid="stNumberInput"] input {{ font-size: 1em !important; min-height: 40px !important; }} .mint-table td {{ padding: 9px 8px !important; font-size: 0.82em !important; }} .mint-table th {{ padding: 7px 8px !important; font-size: 0.68em !important; }}</style>""", unsafe_allow_html=True)
        new_goal = st.number_input("🎯 목표 금액 (USD)", min_value=1000.0, max_value=100_000_000.0, value=st.session_state.goal_usd, step=1000.0, format="%.0f", key="goal_input")
        if new_goal != st.session_state.goal_usd: st.session_state.goal_usd = new_goal; st.rerun()
        st.markdown(_goal_tracker_html(), unsafe_allow_html=True); st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        st.markdown(_regime_card_html(horizontal=False), unsafe_allow_html=True)
        with st.container(border=True): st.markdown(_sl("Position Input"), unsafe_allow_html=True); _pf_editor(400)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        with st.container(border=True): st.markdown(_sl("Live Prices"), unsafe_allow_html=True); st.markdown(_lp_build(), unsafe_allow_html=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if not is_toss:
            with st.container(border=True):
                st.markdown(_sl("Quick Orders"), unsafe_allow_html=True); _sells, _buys = _sells_buys(); _mqo1, _mqo2 = st.columns(2)
                with _mqo1: _qo_build(_mqo1, "🔴  SELL", _sells, "#DC2626", "rgba(220,38,38,0.03)")
                with _mqo2: _qo_build(_mqo2, "🟢  BUY", _buys, "#059669", "rgba(5,150,105,0.03)")
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True); _target_weights_block(); st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        _pie_charts()
        if not is_toss:
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            st.markdown(apply_theme(f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;"><div style="width:2px;height:14px;background:{main_color};flex-shrink:0;"></div><span style="font-family:DM Mono,monospace;font-size:0.62em;font-weight:600;color:{tc_heading};letter-spacing:0.18em;text-transform:uppercase;">Rebalancing</span><div style="flex:1;height:1px;background:rgba(0,0,0,0.09);"></div></div>'), unsafe_allow_html=True)
            _rebalancing_matrix(is_mobile=True)

# ==========================================
# 라우팅 3. 12-Pack Radar
# ==========================================
elif page == "🍫 12-Pack Radar":
    df_view  = df.iloc[-120:]
    qqq_rsi, qqq_dd = last_row['QQQ_RSI'], last_row['QQQ_DD']
    
    # CNN 공식 Fear & Greed Index (실패 시 자체 계산값으로 폴백)
    _cnn_fg = fetch_cnn_fear_greed()
    if _cnn_fg['ok'] and _cnn_fg['score'] is not None:
        fg_score = _cnn_fg['score']
        fg_source = "CNN"
        fg_rating = _cnn_fg['rating']
        fg_prev = _cnn_fg['prev_close']
        fg_week = _cnn_fg['week_ago']
        fg_month = _cnn_fg['month_ago']
    else:
        _vix_score = max(0, min(100, 100 - (last_row['^VIX'] - 12) / 23 * 100))
        _rsi_score = max(0, min(100, qqq_rsi))
        _mom_score = max(0, min(100, 50 + (last_row['QQQ'] / last_row['QQQ_MA200'] - 1) * 250))
        _crd_score = max(0, min(100, 50 + (last_row['HYG_IEF_Ratio'] / last_row['HYG_IEF_MA50'] - 1) * 500))
        fg_score = (_vix_score + _rsi_score + _mom_score + _crd_score) / 4
        fg_source = "Proxy"
        fg_rating = "fear" if fg_score < 30 else ("greed" if fg_score > 70 else "neutral")
        fg_prev = fg_week = fg_month = fg_score

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

    if risk_cnt >= 3: radar_status, radar_msg, radar_color = "극단적 위험 구간 (Risk-Off)", "시스템 리스크를 강하게 경고하고 있습니다. 모든 레버리지를 해제하고 현금/달러 비중을 최대로 늘려야 합니다.", "#DC2626"
    elif warn_cnt >= 4 or risk_cnt >= 1: radar_status, radar_msg, radar_color = "변동성 주의 (Warning)", "시장 곳곳에서 균열이 감지됩니다. 신규 매수를 보류하고 보수적인 관망 자세를 유지하세요.", "#D97706"
    else: radar_status, radar_msg, radar_color = "안정적 순항 (Safe)", "매크로 지표가 안정적입니다. AMLS 알고리즘 비중에 맞춰 추세 추종 전략을 전개하세요.", main_color

    total_signals = risk_cnt + warn_cnt + safe_cnt
    risk_pct = int(risk_cnt / total_signals * 100) if total_signals else 0
    warn_pct = int(warn_cnt / total_signals * 100) if total_signals else 0
    safe_pct = int(safe_cnt / total_signals * 100) if total_signals else 0

    st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);border-left:3px solid {radar_color};padding:14px 20px;margin-bottom:12px;"><div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap;"><div style="flex:3;min-width:260px;"><div style="font-family:DM Mono,monospace;font-size:0.57em;color:#9494A0;letter-spacing:0.18em;text-transform:uppercase;margin-bottom:4px;">Macro Signal Status</div><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.2em;font-weight:700;letter-spacing:-0.3px;color:{radar_color};line-height:1.1;margin-bottom:8px;">{radar_status}</div><div style="font-family:DM Sans,sans-serif;font-size:0.82em;color:#4A4A57;line-height:1.6;">{radar_msg}</div></div><div style="flex:1;min-width:180px;"><div style="display:flex;gap:6px;margin-bottom:8px;"><div style="flex:1;border-top:2px solid #DC2626;padding:8px 6px;background:rgba(220,38,38,0.04);"><div style="font-family:DM Mono,monospace;font-size:1.5em;color:#DC2626;line-height:1;">{risk_cnt}</div><div style="font-family:DM Mono,monospace;font-size:0.57em;color:#9494A0;letter-spacing:0.14em;text-transform:uppercase;">Risk</div></div><div style="flex:1;border-top:2px solid #D97706;padding:8px 6px;background:rgba(217,119,6,0.04);"><div style="font-family:DM Mono,monospace;font-size:1.5em;color:#D97706;line-height:1;">{warn_cnt}</div><div style="font-family:DM Mono,monospace;font-size:0.57em;color:#9494A0;letter-spacing:0.14em;text-transform:uppercase;">Warn</div></div><div style="flex:1;border-top:2px solid {main_color};padding:8px 6px;background:rgba({r_c},{g_c},{b_c},0.04);"><div style="font-family:DM Mono,monospace;font-size:1.5em;color:{main_color};line-height:1;">{safe_cnt}</div><div style="font-family:DM Mono,monospace;font-size:0.57em;color:#9494A0;letter-spacing:0.14em;text-transform:uppercase;">Safe</div></div></div><div style="height:4px;background:rgba(0,0,0,0.07);display:flex;overflow:hidden;"><div style="width:{risk_pct}%;background:#DC2626;"></div><div style="width:{warn_pct}%;background:#D97706;"></div><div style="width:{safe_pct}%;background:{main_color};"></div></div><div style="display:flex;justify-content:space-between;font-family:DM Mono,monospace;font-size:0.58em;color:#9494A0;margin-top:3px;"><span>{risk_pct}% risk</span><span>{warn_pct}% warn</span><span>{safe_pct}% safe</span></div></div></div></div>'), unsafe_allow_html=True)

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
            st.markdown(apply_theme(r_head(1, "DCA · RSI", b1, "https://kr.tradingview.com/chart/?symbol=NASDAQ:QQQ", "QQQ RSI 지표. 30↓ 투매→매수기회, 70↑ 과열→진입중단.")), unsafe_allow_html=True)
            fig1=go.Figure(); fig1.add_trace(go.Scatter(x=df_view.index, y=df_view['QQQ_RSI'], line=dict(color=line_c, width=1.8))); fig1.add_hline(y=70, line_dash='dot', line_color='#B0B0BE', line_width=1); fig1.add_hline(y=30, line_dash='dot', line_color=rsi_low_c, line_width=1); fig1.update_layout(**radar_layout, showlegend=False); fig1.update_xaxes(**_ax_r); fig1.update_yaxes(range=[10,90], **_ax_r); st.plotly_chart(fig1, use_container_width=True)
    with row1[1]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(2, "Drawdown", b2, "https://kr.tradingview.com/chart/?symbol=NASDAQ:QQQ", "QQQ 고점 대비 하락률. -20% 돌파시 약세장 진입 경고.")), unsafe_allow_html=True)
            fig2=go.Figure(); fig2.add_trace(go.Scatter(x=df_view.index, y=df_view['QQQ_DD'], fill='tozeroy', fillcolor='rgba(220,38,38,0.07)', line=dict(color='#DC2626', width=1.8))); fig2.update_layout(**radar_layout, showlegend=False); fig2.update_xaxes(**_ax_r); fig2.update_yaxes(tickformat='.0%', **_ax_r); st.plotly_chart(fig2, use_container_width=True)
    with row1[2]:
        with st.container(border=True):
            _fg_title = f"Fear & Greed · {fg_source}" + (f" ({fg_rating})" if fg_source == "CNN" else "")
            _fg_desc = f"CNN 공식 지수. 전일 {fg_prev:.0f} · 1주전 {fg_week:.0f} · 1개월전 {fg_month:.0f}" if fg_source == "CNN" else "공포 탐욕 지수 (자체 계산 · CNN API 실패)"
            st.markdown(apply_theme(r_head(3, _fg_title, b3, "https://edition.cnn.com/markets/fear-and-greed", _fg_desc)), unsafe_allow_html=True)
            fig3=go.Figure(go.Indicator(mode="gauge+number", value=fg_score, domain={'x':[0,1],'y':[0,1]}, gauge={'axis':{'range':[0,100],'tickcolor':t_color},'bar':{'color':line_c,'thickness':0.2},'steps':gauge_steps,'borderwidth':0})); fig3.update_layout(height=200, margin=dict(l=15,r=15,t=10,b=10), paper_bgcolor=b_color, font=dict(family="DM Mono", color=t_color)); st.plotly_chart(fig3, use_container_width=True)
    with row1[3]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(4, "Sector 1M", b4, "https://finviz.com/map.ashx?t=sec", "방어주(유틸/필수소비) 강세시 경기침체 대비 시그널.")), unsafe_allow_html=True)
            fig4=go.Figure(go.Bar(x=sec_df['수익률'], y=sec_df['섹터'], orientation='h', marker_color=[dash_c if v<0 else line_c for v in sec_df['수익률']], marker_line_width=0)); fig4.update_layout(**radar_layout, showlegend=False); fig4.update_xaxes(**_ax_r); fig4.update_yaxes(**_ax_r); st.plotly_chart(fig4, use_container_width=True)

    row2 = st.columns(4)
    with row2[0]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(5, "Credit Spread", b5, "https://fred.stlouisfed.org/series/BAMLH0A0HYM2", "하이일드 채권이 국채 대비 약세면 스마트머니 이탈 중.")), unsafe_allow_html=True)
            fig5=go.Figure(); fig5.add_trace(go.Scatter(x=df_view.index, y=df_view['HYG_IEF_Ratio'], line=dict(color=line_c, width=1.8))); fig5.add_trace(go.Scatter(x=df_view.index, y=df_view['HYG_IEF_MA50'], line=dict(color=dash_c, dash='dot', width=1.1))); fig5.update_layout(**radar_layout, showlegend=False); fig5.update_xaxes(**_ax_r); fig5.update_yaxes(**_ax_r); st.plotly_chart(fig5, use_container_width=True)
    with row2[1]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(6, "Mkt Breadth", b6, "https://kr.tradingview.com/chart/?symbol=NASDAQ:QQQE", "괴리 발생시 소수 대형주만 끌어올리는 가짜 상승 경고.")), unsafe_allow_html=True)
            fig6=go.Figure(); fig6.add_trace(go.Scatter(x=df_view.index, y=df_view['QQQ_20d_Ret'], name='QQQ', line=dict(color=line_c, width=1.8))); fig6.add_trace(go.Scatter(x=df_view.index, y=df_view['QQQE_20d_Ret'], name='QQQE', line=dict(color=dash_c, dash='dot', width=1.1))); fig6.update_layout(**radar_layout, showlegend=False); fig6.update_xaxes(**_ax_r); fig6.update_yaxes(tickformat='.0%', **_ax_r); st.plotly_chart(fig6, use_container_width=True)
    with row2[2]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(7, "Gold / Equity", b7, "https://kr.tradingview.com/chart/?symbol=AMEX:GLD", "금이 상대 강세면 기관의 Risk-Off 전환, 구조적 리스크.")), unsafe_allow_html=True)
            fig7=go.Figure(); fig7.add_trace(go.Scatter(x=df_view.index, y=df_view['GLD_SPY_Ratio'], line=dict(color=line_c, width=1.8))); fig7.add_trace(go.Scatter(x=df_view.index, y=df_view['GLD_SPY_MA50'], line=dict(color=dash_c, dash='dot', width=1.1))); fig7.update_layout(**radar_layout, showlegend=False); fig7.update_xaxes(**_ax_r); fig7.update_yaxes(**_ax_r); st.plotly_chart(fig7, use_container_width=True)
    with row2[3]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(8, "USD (UUP)", b8, "https://kr.tradingview.com/chart/?symbol=AMEX:UUP", "달러지수. 50일선 돌파시 기술주 강한 하방압력 경고.")), unsafe_allow_html=True)
            fig8=go.Figure(); fig8.add_trace(go.Scatter(x=df_view.index, y=df_view['UUP'], line=dict(color=line_c, width=1.8))); fig8.add_trace(go.Scatter(x=df_view.index, y=df_view['UUP_MA50'], line=dict(color=dash_c, dash='dot', width=1.1))); fig8.update_layout(**radar_layout, showlegend=False); fig8.update_xaxes(**_ax_r); fig8.update_yaxes(**_ax_r); st.plotly_chart(fig8, use_container_width=True)

    row3 = st.columns(4)
    with row3[0]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(9, "10Y Yield", b9, "https://kr.tradingview.com/chart/?symbol=TVC:US10Y", "미 10년물 금리. 상승시 성장주 역풍, 레버리지 주의.")), unsafe_allow_html=True)
            fig9=go.Figure(); fig9.add_trace(go.Scatter(x=df_view.index, y=df_view['^TNX'], line=dict(color=line_c, width=1.8))); fig9.add_trace(go.Scatter(x=df_view.index, y=df_view['TNX_MA50'], line=dict(color=dash_c, dash='dot', width=1.1))); fig9.update_layout(**radar_layout, showlegend=False); fig9.update_xaxes(**_ax_r); fig9.update_yaxes(**_ax_r); st.plotly_chart(fig9, use_container_width=True)
    with row3[1]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(10, "Bitcoin", b10, "https://kr.tradingview.com/chart/?symbol=BINANCE:BTCUSD", "비트코인. 50일선 하향시 글로벌 유동성 가뭄 선행 경고.")), unsafe_allow_html=True)
            fig10=go.Figure(); fig10.add_trace(go.Scatter(x=df_view.index, y=df_view['BTC-USD'], line=dict(color=line_c, width=1.8))); fig10.add_trace(go.Scatter(x=df_view.index, y=df_view['BTC_MA50'], line=dict(color=dash_c, dash='dot', width=1.1))); fig10.update_layout(**radar_layout, showlegend=False); fig10.update_xaxes(**_ax_r); fig10.update_yaxes(**_ax_r); st.plotly_chart(fig10, use_container_width=True)
    with row3[2]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(11, "Russell/SP500", b11, "https://kr.tradingview.com/chart/?symbol=AMEX:IWM", "IWM/SPY 비율. 중소형주 상대약세시 시장 내부 균열.")), unsafe_allow_html=True)
            fig11=go.Figure(); fig11.add_trace(go.Scatter(x=df_view.index, y=df_view['IWM_SPY_Ratio'], line=dict(color=line_c, width=1.8))); fig11.add_trace(go.Scatter(x=df_view.index, y=df_view['IWM_SPY_MA50'], line=dict(color=dash_c, dash='dot', width=1.1))); fig11.update_layout(**radar_layout, showlegend=False); fig11.update_xaxes(**_ax_r); fig11.update_yaxes(**_ax_r); st.plotly_chart(fig11, use_container_width=True)
    with row3[3]:
        with st.container(border=True):
            st.markdown(apply_theme(r_head(12, "VIX Trend", b12, "https://kr.tradingview.com/chart/?symbol=CBOE:VIX", "VIX 추세. 50일선 돌파시 변동성 확장 국면 및 패닉.")), unsafe_allow_html=True)
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
                genai.configure(api_key=os.environ.get("GEMINI_API_KEY", st.secrets.get("GEMINI_API_KEY", "")))
                _valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                if not _valid_models: st.error("활성화된 모델이 없습니다.")
                else:
                    _target_model = next((m for m in _valid_models if 'gemini-1.5-flash' in m), _valid_models[0])
                    _model = genai.GenerativeModel(_target_model.replace('models/', ''))
                    _prompt = f"너는 월스트리트 퀀트 애널리스트야. AMLS V5 시스템의 12개 매크로 신호를 분석해서 투자의견을 내줘.\n[현재 레짐] R{curr_regime} — {regime_info[curr_regime][1]}\n[신호 요약] Risk {risk_cnt}개 / Warn {warn_cnt}개 / Safe {safe_cnt}개\n[12개 실시간 신호]\n1. QQQ RSI: {qqq_rsi:.1f}\n2. QQQ 고점대비 낙폭: {qqq_dd*100:.1f}%\n3. CNN Fear&Greed: {fg_score:.0f}\n4. 주도섹터: {top_sec} / 약세섹터: {bot_sec}\n5. 신용스프레드 HYG/IEF: {'위험' if last_row['HYG_IEF_Ratio']<last_row['HYG_IEF_MA50'] else '안전'}\n6. 시장폭: {'좁아짐' if (last_row['QQQ_20d_Ret']>0 and last_row['QQQE_20d_Ret']<0) else '넓음'}\n7. 금/주식 비율: {'금강세' if last_row['GLD_SPY_Ratio']>last_row['GLD_SPY_MA50'] else '주식강세'}\n8. 달러: {'강세' if last_row['UUP']>last_row['UUP_MA50'] else '약세'}\n9. 미10년물금리 {last_row['^TNX']:.2f}%: {'상승' if last_row['^TNX']>last_row['TNX_MA50'] else '하락'}\n10. 비트코인: {'위험' if last_row['BTC-USD']<last_row['BTC_MA50'] else '안전'}\n11. 러셀2000/S&P500: {'약세' if last_row['IWM_SPY_Ratio']<last_row['IWM_SPY_MA50'] else '강세'}\n12. VIX {last_row['^VIX']:.1f}: {'확장' if last_row['^VIX']>last_row['VIX_MA50'] else '축소'}\n아래 3개 섹션으로 한국어로 작성해:\n**① 시장 환경 진단**\n**② 핵심 리스크 & 기회 요인**\n**③ AMLS 전략 투자의견**"
                    with st.spinner("AI 분석 중..."): _response = _model.generate_content(_prompt)
                    st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.11);border-left:4px solid {main_color};padding:20px 24px;"><div style="font-family:DM Mono,monospace;font-size:0.56em;color:{tc_label};letter-spacing:0.16em;text-transform:uppercase;margin-bottom:12px;">AI Quant Analysis  ·  {last_update_time}</div><div style="font-family:DM Sans,sans-serif;font-size:0.88em;color:{tc_body};line-height:1.8;">{_response.text}</div></div>'), unsafe_allow_html=True)
            except Exception as _e: st.error(f"🚨 API 오류: {str(_e)}")
        else:
            st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);border-left:3px solid rgba(0,0,0,0.12);padding:24px 26px;"><div style="font-family:DM Mono,monospace;font-size:0.58em;color:{tc_label};letter-spacing:0.14em;text-transform:uppercase;margin-bottom:12px;">How It Works</div><div style="font-family:DM Sans,sans-serif;font-size:0.86em;color:{tc_muted};line-height:1.75;">버튼을 누르면 Google Gemini AI가 위 12개 지표를 종합 분석합니다.</div><div style="margin-top:16px;padding:10px 14px;background:rgba({r_c},{g_c},{b_c},0.07);border-left:2px solid {main_color};"><span style="font-family:DM Mono,monospace;font-size:0.68em;color:{tc_body};">현재 레짐: <b style="color:{main_color};">R{curr_regime}</b>  ·  Risk <b style="color:#DC2626;">{risk_cnt}</b>  Warn <b style="color:#D97706;">{warn_cnt}</b>  Safe <b style="color:{main_color};">{safe_cnt}</b></span></div></div>'), unsafe_allow_html=True)

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
                daily_ret = bt_df[['QQQ','TQQQ','SOXL','USD','QLD','SSO','SPYG','SMH','GLD']].pct_change().fillna(0)
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

                res_df = pd.DataFrame({'V5': hist_o, 'QQQ': hist_q, 'QLD': hist_qld, 'TQQQ': hist_tqqq, 'Invested': invested}, index=bt_df.index)
                days = (res_df.index[-1] - res_df.index[0]).days
                def calc_m(s, i_s): return (s.iloc[-1]/i_s.iloc[-1]-1), ((s.iloc[-1]/i_s.iloc[-1])**(365.25/days)-1 if days>0 else 0), (((s/s.cummax())-1).min())
                
                ret_o, cagr_o, mdd_o = calc_m(res_df['V5'], res_df['Invested'])
                ret_q, cagr_q, mdd_q = calc_m(res_df['QQQ'], res_df['Invested'])
                ret_t, cagr_t, mdd_t = calc_m(res_df['TQQQ'], res_df['Invested'])

                mc1, mc2, mc3 = st.columns(3)
                def _mc_html(t, r, c, m, main=False): return f'<div style="background:{"rgba("+str(r_c)+","+str(g_c)+","+str(b_c)+",0.06)" if main else "#FFFFFF"};border:1px solid rgba(0,0,0,0.08);border-top:2px solid {"rgba("+str(r_c)+","+str(g_c)+","+str(b_c)+",0.55)" if main else "rgba(0,0,0,0.12)"};border-radius:14px;padding:16px 18px;"><div style="font-size:0.62em;color:#4A5568;margin-bottom:6px;">{t}</div><div style="font-size:1.6em;color:#0F172A;margin-bottom:6px;">CAGR {c*100:.1f}%</div><div style="font-size:0.72em;color:#4A5568;">누적 <b style="color:{"#059669" if r>=0 else "#EF4444"};">{r*100:.1f}%</b>  MDD <b style="color:#EF4444;">{m*100:.1f}%</b></div></div>'
                with mc1: st.markdown(_mc_html("✦ AMLS V5", ret_o, cagr_o, mdd_o, True), unsafe_allow_html=True)
                with mc2: st.markdown(_mc_html("QQQ", ret_q, cagr_q, mdd_q), unsafe_allow_html=True)
                with mc3: st.markdown(_mc_html("TQQQ", ret_t, cagr_t, mdd_t), unsafe_allow_html=True)

                fig_eq = go.Figure()
                fig_eq.add_trace(go.Scatter(x=res_df.index, y=res_df['QQQ'], name='QQQ', line=dict(color='#CBD5E1', width=1.2, dash='dot')))
                fig_eq.add_trace(go.Scatter(x=res_df.index, y=res_df['TQQQ'], name='TQQQ', line=dict(color='#EF4444', width=1.2, dash='dash')))
                fig_eq.add_trace(go.Scatter(x=res_df.index, y=res_df['V5'], name='AMLS', line=dict(color=main_color, width=3)))
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
                        genai.configure(api_key=os.environ.get("GEMINI_API_KEY", st.secrets.get("GEMINI_API_KEY", "")))
                        _valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                        if not _valid_models: st.error("활성화된 모델이 없습니다.")
                        else:
                            _target_model = next((m for m in _valid_models if 'gemini-1.5-flash' in m), _valid_models[0])
                            _model = genai.GenerativeModel(_target_model.replace('models/',''))
                            _res = _model.generate_content("다음 뉴스를 섹터별, 리스크 요소, 최종 투자 스탠스로 나누어 요약해.\n" + "\n".join(headlines_for_ai))
                            st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.12);border-left:3px solid {main_color};padding:20px 22px;margin-top:12px;"><div style="font-family:DM Mono,monospace;font-size:0.58em;color:#9494A0;letter-spacing:0.16em;text-transform:uppercase;margin-bottom:10px;">AI Summary</div><div style="font-family:DM Sans,sans-serif;font-size:0.9em;color:{tc_body};line-height:1.75;">{_res.text}</div></div>'), unsafe_allow_html=True)
            except Exception as _e: st.error(f"🚨 오류: {str(_e)}")
        else: st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.10);border-left:3px solid rgba(0,0,0,0.15);padding:20px 22px;margin-top:12px;"><div style="font-family:DM Mono,monospace;font-size:0.6em;color:#9494A0;letter-spacing:0.14em;text-transform:uppercase;margin-bottom:10px;">How It Works</div><div style="font-family:DM Sans,sans-serif;font-size:0.85em;color:{tc_muted};line-height:1.7;">버튼을 누르면 AI가 최신 뉴스를 3단계로 요약합니다.</div></div>'), unsafe_allow_html=True)
    with nr:
        for idx, item in enumerate(news_items):
            st.markdown(f'<div style="display:flex;gap:14px;padding:12px 0;border-bottom:1px solid rgba(0,0,0,0.07);"><div style="font-family:DM Mono,monospace;font-size:0.75em;color:{main_color if idx<3 else "#9494A0"};font-weight:600;">{idx+1:02d}</div><div><a href="{item["link"]}" target="_blank" style="text-decoration:none;"><div style="color:{tc_body};">{item["title"]}</div></a><div style="font-size:0.65em;color:#9494A0;margin-top:4px;">{item["date"]}</div></div></div>', unsafe_allow_html=True)

# ==========================================
# 추가 페이지 1: 🤖 AI Quant Assistant
# ==========================================
elif page == "🤖 AI Quant Assistant":
    st.markdown(apply_theme("""<div style="display:flex;align-items:center;gap:16px;margin-bottom:20px;"><div><h2 style="font-family:'Plus Jakarta Sans';font-size:1.7em;color:#0F172A;margin:0;">🤖 AI Quant Assistant</h2></div></div>"""), unsafe_allow_html=True)
    st.info("현재 시장 데이터와 AMLS 알고리즘을 바탕으로 Gemini AI에게 전략적 조언을 구합니다.")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])
        
    if prompt := st.chat_input("질문을 입력하세요 (예: 현재 레짐에서 현금 비중을 어떻게 할까?)"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            try:
                import google.generativeai as genai
                genai.configure(api_key=os.environ.get("GEMINI_API_KEY", st.secrets.get("GEMINI_API_KEY", "")))
                valid = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                target = next((m for m in valid if 'gemini-1.5-flash' in m), valid[0]) if valid else None
                model = genai.GenerativeModel(target.replace('models/',''))
                context = f"""너는 AMLS V5 전략의 전담 퀀트 어드바이저야. 아래 전략 명세를 완벽히 숙지하고 모든 답변에 반영해.

[AMLS V5 전략 개요]
AMLS(Adaptive Multi-Leverage Strategy)는 시장 레짐을 4단계로 구분하고, 레짐에 따라 레버리지 ETF 비중을 동적으로 조절하는 규칙 기반 퀀트 전략이다.

[레짐 판정 로직]
- R4 PANIC: VIX > 40 → 즉시 전환
- R3 BEAR: QQQ < 200MA 또는 (QQQ DD < -10% AND HYG/IEF < HYG/IEF MA20)
- R1 BULL: QQQ ≥ 200MA AND 50MA ≥ 200MA AND VIX MA20 < 22 AND HYG/IEF ≥ HYG/IEF MA50
- R2 CORRECTION: 위 조건 모두 불충족 시

[비대칭 지연 규칙]
- 상향(위험 증가): R3→R4, R2→R3 등은 즉시 반영
- R3→R2: 즉시 전환 (1차 회복)
- R2→R1: 5일 연속 R1 조건 충족 시 승격
- 하향(안전 회복)은 신중하게, 상향(위험)은 즉각 대응

[V5 자산 배분표]
R1 BULL: TQQQ 30%, SOXL/USD 20%, QLD 20%, SSO 15%, SHV 10%, SPYG 5%
R2 CORR: TQQQ 15%, QLD 30%, SSO 25%, USD 10%, SHV 15%, SPYG 5%
R3 BEAR: SHV 50%, CASH 35%, QQQ 15%
R4 PANIC: SHV 50%, CASH 40%, QQQ 10%

[반도체 게이트 (SOXL 스위치)]
SMH > 50MA AND (3M 수익률 > 5% OR 1M 수익률 > 10%) AND RSI > 50 → SOXL 투입
조건 미충족 시 → USD(달러 방어)로 대체

[V5 핵심 변경사항 (V4.5 대비)]
1. GLD → SHV: 금을 단기국채(이자 주는 현금)로 대체. 2022년 금-주식 동조화 문제 해결.
2. SPY → SPYG: S&P500 Growth로 변경. 낮은 단가 + 기술주 비중 확대.
3. SHV 선택 이유: QQQ 상관관계 ≈ 0, 변동성 ≈ 0, 연 4-5% 이자 수익, 원금 손실 사실상 불가.

[FEO(First Entry Override) 규칙]
R3 상황에서 F&G < 15(극단적 공포) 시 → R2 배분으로 선진입
진입 후 QQQ가 20일 내 15%+ 추가 하락 → R3 배분으로 전환
20일 내 추가 하락 없으면 → R2 유지

[현재 실시간 상황]
레짐: R{curr_regime} ({regime_info[curr_regime][1]})
VIX: {vix_close:.1f} (MA20: {vix_ma20:.1f})
Fear & Greed (CNN): {fetch_cnn_fear_greed().get('score') or 'N/A'} ({fetch_cnn_fear_greed().get('rating') or 'unknown'})
QQQ: ${qqq_close:.2f} (200MA: ${qqq_ma200:.2f}, 이격도: {(qqq_close/qqq_ma200-1)*100:+.1f}%)
SMH 반도체: RSI {smh_rsi:.1f}, 1M {smh_1m*100:+.1f}%
SOXL 게이트: {'APPROVED (SOXL 투입)' if smh_cond else 'DENIED (USD 방어)'}
레짐 위원회: {regime_committee_msg}

[답변 원칙]
- 모든 조언은 AMLS V5 규칙에 근거해야 한다. 개인 의견이 아닌 시스템 판단을 우선한다.
- "지금 사야 할까?" 류 질문에는 현재 레짐과 배분표를 기준으로 구체적 비중을 제시한다.
- 전략 외 종목 추천은 하지 않는다. AMLS 유니버스(TQQQ, SOXL, QLD, SSO, SPYG, SHV, QQQ, CASH) 내에서만 답변한다.
- 한국어로 답변하되, 핵심 수치는 정확히 포함한다."""
                
                with st.spinner("🤖 AI가 시장 데이터를 기반으로 분석 중입니다..."):
                    response = model.generate_content(f"{context}\n질문: {prompt}")
                
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"API 연결 오류: {e}")

# ==========================================
# 추가 페이지 2: 🎛️ Parameter Lab
# ==========================================
elif page == "🎛️ Parameter Lab":
    st.markdown(apply_theme("""<div style="display:flex;align-items:center;gap:16px;margin-bottom:20px;"><div><h2 style="font-family:'Plus Jakarta Sans';font-size:1.7em;color:#0F172A;margin:0;">🎛️ Parameter Lab</h2></div></div>"""), unsafe_allow_html=True)
    st.markdown("알고리즘의 판단 기준 임계치를 직접 수정하여 전략의 민감도를 조절합니다.")
    with st.container(border=True):
        st.session_state.param_vix_limit = st.slider("VIX Panic Threshold (R4 진입 기준)", 20.0, 60.0, st.session_state.param_vix_limit)
        st.session_state.param_ma_long = st.number_input("Long-term MA (기준 이동평균선)", 100, 300, st.session_state.param_ma_long)
        st.session_state.param_ma_short = st.number_input("Short-term MA (추세 확인용)", 20, 100, st.session_state.param_ma_short)
    st.warning("⚠️ 파라미터 변경 시 메인 대시보드의 레짐 판정 로직이 즉시 변경됩니다. (현재 VIX 한계치 연동 완료)")

# ==========================================
# 추가 페이지 3: 📝 Trade Journal
# ==========================================
elif page == "📝 Trade Journal":
    st.markdown(apply_theme("""<div style="display:flex;align-items:center;gap:16px;margin-bottom:20px;"><div><h2 style="font-family:'Plus Jakarta Sans';font-size:1.7em;color:#0F172A;margin:0;">📝 Trade Journal</h2></div></div>"""), unsafe_allow_html=True)
    with st.expander("➕ 새 매매 기록 작성", expanded=False):
        c1, c2 = st.columns(2)
        date = c1.date_input("매매일자")
        asset = c2.selectbox("종목", ASSET_LIST)
        action = c1.radio("액션", ["BUY", "SELL"], horizontal=True)
        reason = st.text_area("매매 사유 (당시 레짐, 시장 상황 등)")
        if st.button("기록 저장"):
            st.session_state.trade_log.append({"날짜": str(date), "종목": asset, "구분": action, "사유": reason})
            save_trade_log_to_disk()
            st.success("매매 일지가 저장되었습니다.")
            st.rerun()
            
    if st.session_state.trade_log:
        _tl_df = pd.DataFrame(st.session_state.trade_log)
        st.dataframe(_tl_df, use_container_width=True, hide_index=True)
        with st.expander("🗑 개별 기록 삭제"):
            _del_idx = st.number_input("삭제할 행 번호 (0부터)", min_value=0, max_value=max(len(st.session_state.trade_log)-1, 0), value=0, step=1)
            if st.button("선택 행 삭제", key="del_tl"):
                if 0 <= _del_idx < len(st.session_state.trade_log):
                    st.session_state.trade_log.pop(_del_idx)
                    save_trade_log_to_disk()
                    st.success("삭제됨")
                    st.rerun()
    else:
        st.info("아직 기록된 매매 내역이 없습니다.")

_ls_save_all()
