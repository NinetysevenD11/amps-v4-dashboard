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
st.set_page_config(page_title="AMLS V4.5 FINANCE STRATEGY", layout="wide", page_icon="🌿", initial_sidebar_state="expanded")

# --- [Session State Initialization] ---
defaults = {
    'display_mode': 'PC', 'lc_lr_split': 38, 'lc_delta_wt': 52, 'lc_editor_h': 355, 'lc_goal_inp': 22,
    'lc_pie_h': 200, 'lc_pie_split': 50, 'lc_bar_h': 185, 'lc_show_lp': True, 'lc_show_qo': True, 'lc_show_reg': True,
    'main_color': '#10B981', 'bg_color': '#F7F6F2', 'tc_heading': '#111118', 'tc_body': '#2D2D2D',
    'tc_muted': '#6B6B7A', 'tc_label': '#9494A0', 'tc_data': '#111118', 'tc_sidebar': '#2D2D2D',
    '_ls_loaded': False, 'rebal_locked': False, 'rebal_plan': None, 'param_vix_limit': 40.0,
    'param_ma_long': 200, 'param_ma_short': 50, 'trade_log': [], 'messages': [], 'use_custom_weights': False,
    'goal_usd': 100000.0
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

if 'custom_weights' not in st.session_state:
    st.session_state.custom_weights = {
        "R1": {'TQQQ':30, 'SOXL':20, 'USD':0, 'QLD':20, 'SSO':15, 'SPYG':5, 'QQQ':0, 'GLD':10, 'CASH':0},
        "R2": {'TQQQ':15, 'SOXL':0, 'USD':10, 'QLD':30, 'SSO':25, 'SPYG':5, 'QQQ':0, 'GLD':15, 'CASH':0},
        "R3": {'TQQQ':0, 'SOXL':0, 'USD':0, 'QLD':0, 'SSO':0, 'SPYG':0, 'QQQ':15, 'GLD':50, 'CASH':35},
        "R4": {'TQQQ':0, 'SOXL':0, 'USD':0, 'QLD':0, 'SSO':0, 'SPYG':0, 'QQQ':10, 'GLD':50, 'CASH':40}
    }

# --- [Constants] ---
SECTOR_TICKERS = ['XLK','XLV','XLF','XLY','XLC','XLI','XLP','XLE','XLU','XLRE','XLB']
CORE_TICKERS   = ['QQQ','TQQQ','SOXL','USD','QLD','SSO','SPYG','SMH','GLD','^VIX','HYG','IEF','QQQE','UUP','^TNX','BTC-USD','IWM']
TICKERS        = CORE_TICKERS + SECTOR_TICKERS
ASSET_LIST     = ['TQQQ','SOXL','USD','QLD','SSO','SPYG','QQQ','GLD','CASH']

# --- [Portfolio Management & Storage] ---
def sanitize_portfolio(pf):
    for a in ASSET_LIST:
        if a not in pf: pf[a] = {'shares': 0.0, 'avg_price': 1.0 if a == 'CASH' else 0.0, 'fx': 1350.0}

def save_portfolio_to_disk():
    for f, k in [('portfolio_autosave.json', 'portfolio'), ('portfolio_isa_autosave.json', 'portfolio_isa'), ('portfolio_toss_autosave.json', 'portfolio_toss')]:
        with open(f, 'w') as out: json.dump(st.session_state[k], out)
    st.session_state['_needs_ls_save'] = True

for key, file in [('portfolio', 'portfolio_autosave.json'), ('portfolio_isa', 'portfolio_isa_autosave.json'), ('portfolio_toss', 'portfolio_toss_autosave.json')]:
    if key not in st.session_state:
        st.session_state[key] = {a: {'shares':0.0, 'avg_price':0.0, 'fx':1350.0} for a in ASSET_LIST}
        if os.path.exists(file):
            with open(file, 'r') as f: st.session_state[key].update(json.load(f))
    sanitize_portfolio(st.session_state[key])

# --- [Helper Functions] ---
def hex_to_rgb(hex_col): 
    h = hex_col.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

main_color, bg_color = st.session_state.main_color, st.session_state.bg_color
tc_heading, tc_body, tc_label = st.session_state.tc_heading, st.session_state.tc_body, st.session_state.tc_label
tc_muted, tc_data, tc_sidebar = st.session_state.tc_muted, st.session_state.tc_data, st.session_state.tc_sidebar
r_c, g_c, b_c = hex_to_rgb(main_color)

def apply_theme(text):
    if not isinstance(text, str): return text
    return text.replace("#10B981", main_color).replace("16, 185, 129", f"{r_c}, {g_c}, {b_c}")

# --- [Data Fetching] ---
@st.cache_data(ttl=3600, show_spinner=False)
def load_data():
    try:
        data = yf.download(TICKERS, start=(datetime.now() - timedelta(days=900)).strftime("%Y-%m-%d"), progress=False, auto_adjust=True)['Close']
        df = data.ffill().bfill()
        df['QQQ_MA200'], df['QQQ_MA50'], df['VIX_MA20'], df['VIX_MA50'] = df['QQQ'].rolling(200).mean(), df['QQQ'].rolling(50).mean(), df['^VIX'].rolling(20).mean(), df['^VIX'].rolling(50).mean()
        df['SMH_MA50'], df['SMH_RSI'] = df['SMH'].rolling(50).mean(), ta.rsi(df['SMH'], length=14)
        df['SMH_1M_Ret'], df['SMH_3M_Ret'] = df['SMH'].pct_change(21), df['SMH'].pct_change(63)
        df['HYG_IEF_Ratio'] = df['HYG'] / df['IEF']
        df['HYG_IEF_MA20'], df['HYG_IEF_MA50'] = df['HYG_IEF_Ratio'].rolling(20).mean(), df['HYG_IEF_Ratio'].rolling(50).mean()
        df['QQQ_High52'] = df['QQQ'].rolling(252).max()
        df['QQQ_DD'], df['QQQ_RSI'] = (df['QQQ'] / df['QQQ_High52']) - 1, ta.rsi(df['QQQ'], length=14)
        df['UUP_MA50'], df['TNX_MA50'], df['BTC_MA50'] = df['UUP'].rolling(50).mean(), df['^TNX'].rolling(50).mean(), df['BTC-USD'].rolling(50).mean()
        df['GLD_SPY_Ratio'], df['IWM_SPY_Ratio'] = df['GLD'] / df['SPYG'], df['IWM'] / df['SPYG']
        df['GLD_SPY_MA50'], df['IWM_SPY_MA50'] = df['GLD_SPY_Ratio'].rolling(50).mean(), df['IWM_SPY_Ratio'].rolling(50).mean()
        df['QQQ_20d_Ret'], df['QQQE_20d_Ret'] = df['QQQ'].pct_change(20), df['QQQE'].pct_change(20)
        for s in SECTOR_TICKERS: df[f'{s}_1M'] = df[s].pct_change(21)
        return df.dropna()
    except: return None

def get_target_v45(row):
    if row['^VIX'] > st.session_state.param_vix_limit: return 4
    if row['QQQ'] < row['QQQ_MA200'] or (row['QQQ_DD'] < -0.10 and row['HYG_IEF_Ratio'] < row['HYG_IEF_MA20']): return 3
    if row['QQQ'] >= row['QQQ_MA200'] and row['QQQ_MA50'] >= row['QQQ_MA200'] and row['VIX_MA20'] < 22 and row['HYG_IEF_Ratio'] >= row['HYG_IEF_MA50']: return 1
    return 2

def apply_asymmetric_delay(targets):
    res, hist_curr, pend, cnt = [], 3, None, 0
    for t in targets:
        if t > hist_curr: hist_curr, pend, cnt = t, None, 0
        elif t < hist_curr:
            if hist_curr == 3 and t <= 2: 
                hist_curr = 2
                if t == 1: pend, cnt = 1, 1
            else:
                if t == pend:
                    cnt += 1
                    if cnt >= 5: hist_curr, pend, cnt = t, None, 0
                else: pend, cnt = t, 1
        else: pend, cnt = None, 0
        res.append(hist_curr)
    return pd.Series(res, index=targets.index).shift(1).bfill()

# --- [Main Data Logic] ---
df = load_data()
if df is None: st.error("Data Load Failed"); st.stop()

@st.cache_data(ttl=15)
def fetch_realtime_prices():
    prices = {}
    try:
        batch = yf.download(REALTIME_TICKERS, period="2d", interval="1m", prepost=True, progress=False)['Close'].ffill()
        for t in REALTIME_TICKERS: prices[t] = float(batch[t].iloc[-1])
    except: pass
    return prices, (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")

REALTIME_TICKERS = TICKERS + ['USDKRW=X']
rt_prices, last_update_time = fetch_realtime_prices()
last_row = df.iloc[-1].copy()
for t, p in rt_prices.items(): 
    if t in last_row.index: last_row[t] = p

live_regime = get_target_v45(last_row)
df['Target'] = df.apply(get_target_v45, axis=1)
df['Regime'] = apply_asymmetric_delay(df['Target'])
hist_regime = int(df.iloc[-1]['Regime'])
curr_regime = live_regime if live_regime > hist_regime else (2 if hist_regime==3 and live_regime<=2 else hist_regime)

regime_info = {1:("R1 BULL","풀 가동"), 2:("R2 CORR","방어 진입"), 3:("R3 BEAR","대피"), 4:("R4 PANIC","최대 방어")}
smh_cond = (last_row['SMH'] > last_row['SMH_MA50']) and (last_row['SMH_3M_Ret'] > 0.05 or last_row['SMH_1M_Ret'] > 0.10) and (last_row['SMH_RSI'] > 50)
rt_label = f"⬤ LIVE {len(rt_prices)} feeds"

# --- [Sidebar] ---
st.sidebar.markdown(apply_theme(f"""<div style="padding:22px 20px 16px;background:{bg_color};border-bottom:1px solid rgba(0,0,0,0.09);"><div style="font-family:'DM Mono';font-size:0.52em;color:{tc_label};letter-spacing:0.26em;text-transform:uppercase;margin-bottom:8px;">Quantitative Engine</div><div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:1.65em;font-weight:800;color:{tc_heading};letter-spacing:-1px;line-height:1;margin-bottom:14px;">AMLS <span style="color:#10B981;">V4.5</span></div><div style="display:flex;align-items:center;justify-content:space-between;"><div class="live-pulse" style="display:inline-flex;align-items:center;gap:5px;font-family:'DM Mono';font-size:0.6em;color:#059669;padding:3px 10px;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);letter-spacing:0.06em;">{rt_label}</div><div style="font-family:'DM Mono';font-size:0.58em;color:{tc_label};letter-spacing:0.04em;">R{curr_regime} · {regime_info[curr_regime][1]}</div></div></div>"""), unsafe_allow_html=True)
page = st.sidebar.radio("MENU", ["📊 Dashboard", "💼 Portfolio", "🤖 AI Quant Assistant", "🎛️ Parameter Lab", "📝 Trade Journal", "🍫 12-Pack Radar", "📈 Backtest Lab", "📰 Macro News"], label_visibility="collapsed")

# --- [Page: Portfolio Logic] ---
if page == "💼 Portfolio":
    st.markdown('<div style="margin-bottom:12px;">', unsafe_allow_html=True)
    acc_choice = st.radio("📂 계좌 선택", ["🟦 일반 계좌", "🟩 ISA 계좌", "🧪 TOSS 장기투자"], horizontal=True, label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)
    
    is_toss = "TOSS" in acc_choice
    active_pf = st.session_state.portfolio if "일반" in acc_choice else (st.session_state.portfolio_isa if "ISA" in acc_choice else st.session_state.portfolio_toss)
    target_assets = list(active_pf.keys()) if is_toss else ASSET_LIST

    current_prices = {t: (rt_prices.get(t, last_row.get(t, 1.0)) if t != 'CASH' else 1.0) for t in target_assets}
    if is_toss:
        for t in target_assets:
            if t not in rt_prices and t not in df.columns: current_prices[t] = active_pf[t].get('cur_price', 0.0)

    cur_fx = rt_prices.get('USDKRW=X', 1350.0)
    curr_vals = {a: active_pf[a]['shares'] * current_prices[a] for a in target_assets}
    total_val_usd, invested_cost = sum(curr_vals.values()), sum(active_pf[a]['shares'] * active_pf[a]['avg_price'] for a in target_assets if a != 'CASH')
    total_val_krw, pnl_usd = total_val_usd * cur_fx, total_val_usd - invested_cost
    pnl_pct = (pnl_usd / invested_cost * 100) if invested_cost > 0 else 0.0

    def _kv(label, val, color, sub=""):
        return f'<div style="display:flex;flex-direction:column;padding:0 20px;border-right:1px solid rgba(0,0,0,0.08);min-width:115px;"><span style="font-family:DM Mono,monospace;font-size:0.53em;color:{tc_label};letter-spacing:0.2em;text-transform:uppercase;margin-bottom:3px;">{label}</span><span style="font-family:DM Mono,monospace;font-size:1.0em;font-weight:700;color:{color};line-height:1.2;">{val}</span><span style="font-family:DM Mono,monospace;font-size:0.6em;color:{tc_muted};">{sub}</span></div>'

    st.markdown(apply_theme(f'<div style="background:#FAFAF7;border:1px solid rgba(0,0,0,0.11);border-left:4px solid {main_color};padding:13px 0;margin-bottom:14px;display:flex;align-items:center;overflow-x:auto;"><div style="padding:0 20px 0 16px;border-right:1px solid rgba(0,0,0,0.08);"><div style="font-size:0.52em;color:{tc_label};text-transform:uppercase;">AMLS V4.5</div><div style="font-size:1.1em;font-weight:800;">Portfolio</div></div>{_kv("Total NAV", f"${total_val_usd:,.2f}", tc_heading, f"₩{total_val_krw:,.0f}")}{_kv("P & L", f"{pnl_pct:+.2f}%", "#059669" if pnl_pct >= 0 else "#DC2626", f"${pnl_usd:,.0f}")}{_kv("Regime", f"R{curr_regime}", main_color, regime_info[curr_regime][1])}</div>'), unsafe_allow_html=True)

    def _pf_editor(height=355):
        edata = []
        for a in target_assets:
            shares, avg_p, cur_p = active_pf[a]['shares'], active_pf[a]['avg_price'], current_prices[a]
            ret_pct = ((cur_p / avg_p) - 1) * 100 if a != 'CASH' and avg_p > 0 else 0.0
            edata.append({"Asset": a, "Shares": shares, "Avg($)": avg_p, "Current($)": cur_p, "Ret(%)": ret_pct})
        
        df_edit = st.data_editor(pd.DataFrame(edata), disabled=["Ret(%)"] if is_toss else ["Asset", "Current($)", "Ret(%)"], hide_index=True, num_rows="dynamic" if is_toss else "fixed", use_container_width=True, height=height)
        
        if not pd.DataFrame(edata).equals(df_edit):
            new_pf = {}
            for _, row in df_edit.iterrows():
                asset = str(row["Asset"]).strip()
                if asset:
                    new_pf[asset] = {'shares': float(row["Shares"]), 'avg_price': float(row["Avg($)"]), 'cur_price': float(row["Current($)"]) if is_toss else 0.0}
            active_pf.clear()
            active_pf.update(new_pf)
            save_portfolio_to_disk(); st.rerun()

    def _pie_charts():
        c1, c2 = st.columns(2)
        with c1:
            v = [curr_vals[a] for a in target_assets if curr_vals[a] > 0]
            if sum(v) > 0:
                fig = go.Figure(go.Pie(labels=[a for a in target_assets if curr_vals[a] > 0], values=v, hole=.5))
                fig.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.info("장기 투자 계좌는 전략적 비중 제한이 없으며 꾸준한 우상향을 목표로 합니다." if is_toss else "AMLS 레짐에 따른 최적 비중을 준수하세요.")

    if st.session_state.display_mode == "PC":
        col_l, col_r = st.columns([1, 1])
        with col_l:
            with st.container(border=True): 
                st.markdown("### 📝 Position Input")
                _pf_editor(500)
        with col_r:
            _pie_charts()
            if not is_toss:
                st.markdown("---")
                st.markdown("### 📊 Rebalancing Plan")
                # (여기에 리밸런싱 매트릭스 함수 호출)

# --- [Other Routing & Logic] ---
# (Dashboard, Radar 등 나머지 페이지들은 구조에 맞춰 간단히 정리 가능)

elif page == "📊 Dashboard":
    st.write("Dashboard Content (Cleaned)")

elif page == "🍫 12-Pack Radar":
    st.write("Radar Content (Cleaned)")

_ls_save_all()
