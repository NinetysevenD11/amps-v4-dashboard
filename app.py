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
            if 'portfolio' not in st.session_state or not any(st.session_state.portfolio[a]['shares'] for a in ASSET_LIST if a != 'CASH'):
                for k, v in _pf.items(): st.session_state.portfolio[k] = v
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
            _lc_defaults = {"display_mode": "PC", "lc_lr_split": 38, "lc_delta_wt": 52, "lc_editor_h": 355, "lc_goal_inp": 22, "lc_pie_h": 200, "lc_pie_split": 50, "lc_bar_h": 185, "lc_show_lp": True, "lc_show_qo": True, "lc_show_reg": True}
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
            for _k in ["main_color","bg_color","tc_heading","tc_body","tc_muted","tc_label","tc_data","tc_sidebar"]:
                if _k in _th and getattr(st.session_state, _k) == {"main_color":"#10B981","bg_color":"#F7F6F2","tc_heading":"#111118","tc_body":"#2D2D2D","tc_muted":"#6B6B7A","tc_label":"#9
