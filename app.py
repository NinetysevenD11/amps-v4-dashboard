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

# ==========================================
# localStorage 영속화 레이어
# ==========================================
_LS_KEYS = {
    "amls_portfolio":  None,
    "amls_goal":       None,
    "amls_layout":     None,
    "amls_theme":      None,
    "amls_dispmode":   None,
}

_LS_SCRIPT = """
<script>
(function() {
    function pushToST() {
        var keys = ["amls_portfolio","amls_goal","amls_layout","amls_theme","amls_dispmode"];
        var out = {};
        keys.forEach(function(k){
            var v = localStorage.getItem(k);
            if (v) out[k] = v;
        });
        window.parent.postMessage({type:"streamlit:setComponentValue", value: JSON.stringify(out)}, "*");
    }
    window.addEventListener("message", function(e) {
        if (e.data && e.data.type === "amls_save") {
            try {
                var d = e.data.payload;
                Object.keys(d).forEach(function(k){ localStorage.setItem(k, d[k]); });
            } catch(err) {}
        }
    });
    pushToST();
})();
</script>
"""

def _ls_save_all():
    _layout = json.dumps({
        "display_mode": st.session_state.display_mode,
        "lc_lr_split":  st.session_state.lc_lr_split,
        "lc_delta_wt":  st.session_state.lc_delta_wt,
        "lc_editor_h":  st.session_state.lc_editor_h,
        "lc_goal_inp":  st.session_state.lc_goal_inp,
        "lc_pie_h":     st.session_state.lc_pie_h,
        "lc_pie_split": st.session_state.lc_pie_split,
        "lc_bar_h":     st.session_state.lc_bar_h,
        "lc_show_lp":   st.session_state.lc_show_lp,
        "lc_show_qo":   st.session_state.lc_show_qo,
        "lc_show_reg":  st.session_state.lc_show_reg,
    })
    _theme = json.dumps({
        "main_color": st.session_state.main_color,
        "bg_color":   st.session_state.bg_color,
        "tc_heading": st.session_state.tc_heading,
        "tc_body":    st.session_state.tc_body,
        "tc_muted":   st.session_state.tc_muted,
        "tc_label":   st.session_state.tc_label,
        "tc_data":    st.session_state.tc_data,
        "tc_sidebar": st.session_state.tc_sidebar,
    })
    _pf   = json.dumps(st.session_state.portfolio)
    _goal = str(st.session_state.goal_usd)
    _dm   = st.session_state.display_mode
    def _esc(s): return s.replace("\\", "\\\\").replace("`", "\\`")
    st.markdown(f"""<script>
    (function(){{
        try {{
            var p = {{
                amls_portfolio: `{_esc(_pf)}`,
                amls_goal:      `{_esc(_goal)}`,
                amls_layout:    `{_esc(_layout)}`,
                amls_theme:     `{_esc(_theme)}`,
                amls_dispmode:  `{_esc(_dm)}`
            }};
            Object.keys(p).forEach(function(k){{ localStorage.setItem(k, p[k]); }});
        }} catch(e) {{}}
    }})();
    </script>""", unsafe_allow_html=True)

def _ls_load():
    if st.session_state._ls_loaded:
        return
    _qp = st.query_params.to_dict()
    st.markdown("""<script>
    (function(){
        var keys = ["amls_portfolio","amls_goal","amls_layout","amls_theme","amls_dispmode"];
        var changed = false;
        var params = new URLSearchParams(window.location.search);
        keys.forEach(function(k){
            var v = localStorage.getItem(k);
            if (v && !params.has(k)) {
                params.set(k, encodeURIComponent(v));
                changed = true;
            }
        });
        if (changed) {
            var newUrl = window.location.pathname + "?" + params.toString();
            window.history.replaceState(null, "", newUrl);
            window.location.reload();
        }
    })();
    </script>""", unsafe_allow_html=True)
    st.session_state._ls_loaded = True

def _restore_from_qp():
    _qp = st.query_params.to_dict()
    _changed = False
    if "amls_portfolio" in _qp:
        try:
            _pf = json.loads(_qp["amls_portfolio"])
            if 'portfolio' not in st.session_state or not any(
                st.session_state.portfolio[a]['shares'] for a in ASSET_LIST if a != 'CASH'
            ):
                for k, v in _pf.items():
                    st.session_state.portfolio[k] = v
                _changed = True
        except: pass
    if "amls_goal" in _qp:
        try:
            _g = float(_qp["amls_goal"])
            if st.session_state.goal_usd == 100000.0:
                st.session_state.goal_usd = _g
                _changed = True
        except: pass
    if "amls_layout" in _qp:
        try:
            _lay = json.loads(_qp["amls_layout"])
            _lc_defaults = {
                "display_mode": "PC", "lc_lr_split": 38, "lc_delta_wt": 52,
                "lc_editor_h": 355,   "lc_goal_inp": 22, "lc_pie_h": 200,
                "lc_pie_split": 50,   "lc_bar_h": 185,   "lc_show_lp": True,
                "lc_show_qo": True,   "lc_show_reg": True,
            }
            for _k, _dv in _lc_defaults.items():
                if _k in _lay:
                    _cur = getattr(st.session_state, _k)
                    _new = _lay[_k]
                    if isinstance(_dv, bool): _new = bool(_new)
                    elif isinstance(_dv, int): _new = int(_new)
                    if _cur == _dv and _cur != _new:
                        setattr(st.session_state, _k, _new)
                        _changed = True
        except: pass
    if "amls_theme" in _qp:
        try:
            _th = json.loads(_qp["amls_theme"])
            for _k in ["main_color","bg_color","tc_heading","tc_body",
                       "tc_muted","tc_label","tc_data","tc_sidebar"]:
                if _k in _th and getattr(st.session_state, _k) == {
                    "main_color":"#10B981","bg_color":"#F7F6F2","tc_heading":"#111118",
                    "tc_body":"#2D2D2D","tc_muted":"#6B6B7A","tc_label":"#9494A0",
                    "tc_data":"#111118","tc_sidebar":"#2D2D2D"
                }.get(_k):
                    setattr(st.session_state, _k, _th[_k])
                    _changed = True
        except: pass
    if "amls_dispmode" in _qp:
        _dm = _qp["amls_dispmode"]
        if _dm in ("PC","Tablet","Mobile") and st.session_state.display_mode == "PC":
            st.session_state.display_mode = _dm
    if any(k in _qp for k in ["amls_portfolio","amls_goal","amls_layout","amls_theme","amls_dispmode"]):
        for _k in ["amls_portfolio","amls_goal","amls_layout","amls_theme","amls_dispmode"]:
            if _k in st.query_params:
                del st.query_params[_k]
        if _changed:
            st.rerun()

_restore_from_qp()

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

if 'rebal_snapshot' not in st.session_state:
    st.session_state.rebal_snapshot = None
if 'rebal_ts'       not in st.session_state:
    st.session_state.rebal_ts = ""

sanitize_portfolio()

def save_portfolio_to_disk():
    try:
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump(st.session_state.portfolio, f)
    except: pass
    st.session_state['_needs_ls_save'] = True

@st.cache_data(ttl=300, show_spinner=False)
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

@st.cache_data(ttl=20)
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

@st.cache_data(ttl=1800)
def fetch_macro_news():
    headlines_for_ai, news_items = [], []
    queries = [
        "Wall Street stock market",
        "Federal Reserve interest rate",
        "S&P 500 Nasdaq earnings",
    ]
    seen_titles = set()
    for q in queries:
        try:
            search_query = urllib.parse.quote(q)
            url = f"https://news.google.com/rss/search?q={search_query}+when:1d&hl=en&gl=US&ceid=US:en"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            root = ET.fromstring(urllib.request.urlopen(req, timeout=8).read())
            for item in root.findall('.//item')[:6]:
                t = item.find('title').text
                l = item.find('link').text
                d = item.find('pubDate').text
                if t and t not in seen_titles:
                    seen_titles.add(t)
                    headlines_for_ai.append(t)
                    news_items.append({"title": t, "link": l, "date": d[:-4]})
        except:
            pass
    return headlines_for_ai[:15], news_items[:15]

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
        end   = datetime.now()
        start = end - timedelta(days=5)
        raw = yf.download(all_t, start=start.strftime('%Y-%m-%d'),
                          end=end.strftime('%Y-%m-%d'),
                          progress=False, auto_adjust=True)['Close']
        if isinstance(raw, pd.Series):
            raw = raw.to_frame(name=all_t[0])
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

# ── RT 주입 후 레짐 판단 지표 재계산 (마지막 행만) ──
_n = len(df)
if 'QQQ' in rt_injected:
    df.at[last_index, 'QQQ_MA200']  = df['QQQ'].iloc[-200:].mean() if _n >= 200 else df['QQQ'].mean()
    df.at[last_index, 'QQQ_MA50']   = df['QQQ'].iloc[-50:].mean()  if _n >= 50  else df['QQQ'].mean()
    df.at[last_index, 'QQQ_MA20']   = df['QQQ'].iloc[-20:].mean()  if _n >= 20  else df['QQQ'].mean()
    _high52 = df['QQQ'].iloc[-252:].max() if _n >= 252 else df['QQQ'].max()
    df.at[last_index, 'QQQ_High52'] = _high52
    df.at[last_index, 'QQQ_DD']     = (df.at[last_index, 'QQQ'] / _high52) - 1
if 'TQQQ' in rt_injected:
    df.at[last_index, 'TQQQ_MA200'] = df['TQQQ'].iloc[-200:].mean() if _n >= 200 else df['TQQQ'].mean()
if '^VIX' in rt_injected:
    df.at[last_index, 'VIX_MA5']  = df['^VIX'].iloc[-5:].mean()
    df.at[last_index, 'VIX_MA20'] = df['^VIX'].iloc[-20:].mean() if _n >= 20 else df['^VIX'].mean()
    df.at[last_index, 'VIX_MA50'] = df['^VIX'].iloc[-50:].mean() if _n >= 50 else df['^VIX'].mean()
if 'SMH' in rt_injected:
    df.at[last_index, 'SMH_MA50']  = df['SMH'].iloc[-50:].mean() if _n >= 50 else df['SMH'].mean()
    if _n >= 63: df.at[last_index, 'SMH_3M_Ret'] = df['SMH'].iloc[-1] / df['SMH'].iloc[-63] - 1
    if _n >= 21: df.at[last_index, 'SMH_1M_Ret'] = df['SMH'].iloc[-1] / df['SMH'].iloc[-21] - 1
if 'HYG' in rt_injected or 'IEF' in rt_injected:
    _hyg = df.at[last_index, 'HYG']; _ief = df.at[last_index, 'IEF']
    if _ief > 0:
        df.at[last_index, 'HYG_IEF_Ratio'] = _hyg / _ief
        _ratio_s = df['HYG'] / df['IEF']
        df.at[last_index, 'HYG_IEF_MA20'] = _ratio_s.iloc[-20:].mean() if _n >= 20 else _ratio_s.mean()
        df.at[last_index, 'HYG_IEF_MA50'] = _ratio_s.iloc[-50:].mean() if _n >= 50 else _ratio_s.mean()
if 'GLD' in rt_injected or 'SPY' in rt_injected:
    _gld = df.at[last_index, 'GLD']; _spy = df.at[last_index, 'SPY']
    if _spy > 0:
        df.at[last_index, 'GLD_SPY_Ratio'] = _gld / _spy
        _gr = df['GLD'] / df['SPY']
        df.at[last_index, 'GLD_SPY_MA50'] = _gr.iloc[-50:].mean() if _n >= 50 else _gr.mean()
if 'UUP' in rt_injected:
    df.at[last_index, 'UUP_MA50'] = df['UUP'].iloc[-50:].mean() if _n >= 50 else df['UUP'].mean()
if '^TNX' in rt_injected:
    df.at[last_index, 'TNX_MA50'] = df['^TNX'].iloc[-50:].mean() if _n >= 50 else df['^TNX'].mean()
if 'BTC-USD' in rt_injected:
    df.at[last_index, 'BTC_MA50'] = df['BTC-USD'].iloc[-50:].mean() if _n >= 50 else df['BTC-USD'].mean()
if 'IWM' in rt_injected or 'SPY' in rt_injected:
    _iwm = df.at[last_index, 'IWM']; _spy2 = df.at[last_index, 'SPY']
    if _spy2 > 0:
        df.at[last_index, 'IWM_SPY_Ratio'] = _iwm / _spy2
        _ir = df['IWM'] / df['SPY']
        df.at[last_index, 'IWM_SPY_MA50'] = _ir.iloc[-50:].mean() if _n >= 50 else _ir.mean()

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
