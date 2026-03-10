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
REQUIRED_TICKERS = ["TQQQ", "QLD", "QQQ", "SOXL", "USD", "SSO", "GLD", "CASH"]

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"theme": "아이패드 테마"}

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
            "AMLS v4.3": {  
                "portfolio": [{"티커 (Ticker)": t, "수량 (주/달러)": 0.0, "평균 단가 ($)": 0.0, "매입 환율": 0.0, "태그": "코어"} for t in REQUIRED_TICKERS],
                "history": [], "first_entry_date": None, "journal_text": "", "target_seed": 10000.0, "seed_history": {}, "target_portfolio_value": 100000.0,
                "layout_order": ["🎯 목표 달성률", "📊 실시간 요약", "⚡ 시스템 분석관", "💼 포트폴리오 & 리밸런싱", "📈 목표 달성률 추이", "📝 매매 일지"]
            }
        }
    st.session_state['accounts'] = loaded

needs_save = False
if "기본 계좌 (AMLS)" in st.session_state['accounts']:
    st.session_state['accounts']["AMLS v4.3"] = st.session_state['accounts'].pop("기본 계좌 (AMLS)")
    needs_save = True

for acc_name, acc_data in st.session_state['accounts'].items():
    if "seed_history" not in acc_data: acc_data["seed_history"] = {}; needs_save = True
    if "target_portfolio_value" not in acc_data: acc_data["target_portfolio_value"] = 100000.0; needs_save = True
    if "layout_order" not in acc_data: 
        acc_data["layout_order"] = ["🎯 목표 달성률", "📊 실시간 요약", "⚡ 시스템 분석관", "💼 포트폴리오 & 리밸런싱", "📈 목표 달성률 추이", "📝 매매 일지"]
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
# [2] 동적 테마 엔진
# =====================================================================
current_theme = st.session_state['settings'].get("theme", "아이패드 테마")

if current_theme == "애플 테마":
    BASE_TEXT_COLOR = "#1d1d1f"; TEXT_SUB = "#8e8e93"
    PANEL_BG = "rgba(255,255,255,0.65)"; PANEL_BORDER = "1px solid rgba(255,255,255,0.5)"; PANEL_RADIUS = "16px"
    WIDGET_THEME = "light"
    C_UP = "#34c759"; C_DOWN = "#ff3b30"; C_WARN = "#ff9500"; C_SAFE = "#007aff"
    BASE_CHART_COLORS = {'TQQQ':'#ff3b30', 'SOXL':'#af52de', 'USD':'#5856d6', 'QLD':'#ff9500', 'SSO':'#ffcc00', 'QQQ':'#007aff', 'GLD':'#34c759', 'CASH':'#8e8e93'}

elif current_theme == "아이패드 테마":
    BASE_TEXT_COLOR = "#1C1C1E"; TEXT_SUB = "#8E8E93"
    PANEL_BG = "#FFFFFF"; PANEL_BORDER = "none"; PANEL_RADIUS = "24px"
    WIDGET_THEME = "light"
    C_UP = "#34C759"; C_DOWN = "#FF3B30"; C_WARN = "#FF9500"; C_SAFE = "#007AFF"
    BASE_CHART_COLORS = {'TQQQ':'#FF3B30', 'SOXL':'#AF52DE', 'USD':'#5856D6', 'QLD':'#FF9500', 'SSO':'#FFCC00', 'QQQ':'#007AFF', 'GLD':'#34C759', 'CASH':'#8E8E93'}

elif current_theme == "갤럭시 탭 테마":
    BASE_TEXT_COLOR = "#FAFAFA"; TEXT_SUB = "#A0A0A0"
    PANEL_BG = "#1C1C1E"; PANEL_BORDER = "none"; PANEL_RADIUS = "28px"
    WIDGET_THEME = "dark"
    C_UP = "#23D079"; C_DOWN = "#E94C3D"; C_WARN = "#F4B33E"; C_SAFE = "#3E91FF"
    BASE_CHART_COLORS = {'TQQQ':'#E94C3D', 'SOXL':'#9D4EDD', 'USD':'#3E91FF', 'QLD':'#F4B33E', 'SSO':'#F39C12', 'QQQ':'#3E91FF', 'GLD':'#F1C40F', 'CASH':'#A0A0A0'}

elif current_theme == "엑셀 테마":
    BASE_TEXT_COLOR = "#333333"; TEXT_SUB = "#666666"
    PANEL_BG = "#FFFFFF"; PANEL_BORDER = "1px solid #D4D4D4"; PANEL_RADIUS = "0px"
    WIDGET_THEME = "light"
    C_UP = "#107C41"; C_DOWN = "#C00000"; C_WARN = "#FFB900"; C_SAFE = "#0078D4"
    BASE_CHART_COLORS = {'TQQQ':'#C00000', 'SOXL':'#800080', 'USD':'#0078D4', 'QLD':'#FFB900', 'SSO':'#E36C09', 'QQQ':'#0078D4', 'GLD':'#FFC000', 'CASH':'#7F7F7F'}

elif current_theme in ["1930년대 타자기 테마", "1920년대 타자기 테마"]:
    BASE_TEXT_COLOR = "#2c2a25"; TEXT_SUB = "#555555"
    PANEL_BG = "#dfd7c5"; PANEL_BORDER = "2px solid #2c2a25"; PANEL_RADIUS = "0px"
    WIDGET_THEME = "light"
    C_UP = "#000080"; C_DOWN = "#8b0000"; C_WARN = "#b8860b"; C_SAFE = "#006400"
    BASE_CHART_COLORS = {'TQQQ':'#8b0000', 'SOXL':'#556b2f', 'USD':'#8fbc8f', 'QLD':'#b8860b', 'SSO':'#cd853f', 'QQQ':'#000080', 'GLD':'#daa520', 'CASH':'#2f4f4f'}

elif current_theme == "카페 테마":
    BASE_TEXT_COLOR = "#5D4A44"; TEXT_SUB = "#A89B96"
    PANEL_BG = "#FFFFFF"; PANEL_BORDER = "2px solid #FFF0E5"; PANEL_RADIUS = "20px"
    WIDGET_THEME = "light"
    C_UP = "#FFB7B2"; C_DOWN = "#A1C9F1"; C_WARN = "#FFDAC1"; C_SAFE = "#B5EAD7"
    BASE_CHART_COLORS = {'TQQQ':'#FF9AA2', 'SOXL':'#C7CEEA', 'USD':'#E2F0CB', 'QLD':'#FFDAC1', 'SSO':'#FFB7B2', 'QQQ':'#A1C9F1', 'GLD':'#FCEBB6', 'CASH':'#B5EAD7'}

elif current_theme == "2000년대 구글 감성 테마":
    BASE_TEXT_COLOR = "#000000"; TEXT_SUB = "#666666"
    PANEL_BG = "#F8F9FA"; PANEL_BORDER = "1px solid #CCCCCC"; PANEL_RADIUS = "0px"
    WIDGET_THEME = "light"
    C_UP = "#34A853"; C_DOWN = "#EA4335"; C_WARN = "#FBBC05"; C_SAFE = "#4285F4"
    BASE_CHART_COLORS = {'TQQQ':'#EA4335', 'SOXL':'#990099', 'USD':'#660099', 'QLD':'#FBBC05', 'SSO':'#F68B1F', 'QQQ':'#4285F4', 'GLD':'#F4B400', 'CASH':'#34A853'}

elif current_theme == "월스트리트 저널 테마":
    BASE_TEXT_COLOR = "#1A1A1A"; TEXT_SUB = "#555555"
    PANEL_BG = "#FFFFFF"; PANEL_BORDER = "1px solid #1A1A1A"; PANEL_RADIUS = "0px"
    WIDGET_THEME = "light"
    C_UP = "#006400"; C_DOWN = "#8B0000"; C_WARN = "#B8860B"; C_SAFE = "#000080"
    BASE_CHART_COLORS = {'TQQQ':'#8B0000', 'SOXL':'#556b2f', 'USD':'#2F4F4F', 'QLD':'#B8860B', 'SSO':'#DAA520', 'QQQ':'#000080', 'GLD':'#BDB76B', 'CASH':'#696969'}

else:
    BASE_TEXT_COLOR = "#1C1C1E"; TEXT_SUB = "#8E8E93"
    PANEL_BG = "#FFFFFF"; PANEL_BORDER = "none"; PANEL_RADIUS = "24px"
    WIDGET_THEME = "light"
    C_UP = "#34C759"; C_DOWN = "#FF3B30"; C_WARN = "#FF9500"; C_SAFE = "#007AFF"
    BASE_CHART_COLORS = {'TQQQ':'#FF3B30', 'SOXL':'#AF52DE', 'USD':'#5856D6', 'QLD':'#FF9500', 'SSO':'#FFCC00', 'QQQ':'#007AFF', 'GLD':'#34C759', 'CASH':'#8E8E93'}

# 데이터 강제 주입 로직 (에러 방지)
if "text_color" not in st.session_state['settings']: st.session_state['settings']["text_color"] = BASE_TEXT_COLOR
if "chart_colors" not in st.session_state['settings']: st.session_state['settings']["chart_colors"] = BASE_CHART_COLORS.copy()
for tkr in REQUIRED_TICKERS:
    if tkr not in st.session_state['settings']["chart_colors"]:
        st.session_state['settings']["chart_colors"][tkr] = BASE_CHART_COLORS.get(tkr, "#888888")

TEXT_COLOR = st.session_state['settings']["text_color"]
COLOR_PALETTE = st.session_state['settings']["chart_colors"]

# --- Plotly 레이아웃 설정 ---
if current_theme in ["1930년대 타자기 테마", "월스트리트 저널 테마"]:
    THEME_LAYOUT = dict(template="simple_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_COLOR, size=13), margin=dict(l=0, r=0, t=30, b=0))
elif current_theme in ["갤럭시 탭 테마"]:
    THEME_LAYOUT = dict(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_COLOR, size=13), margin=dict(l=0, r=0, t=30, b=0), xaxis=dict(showgrid=True, gridcolor='#333', zerolinecolor='#444'), yaxis=dict(showgrid=True, gridcolor='#333', zerolinecolor='#444'))
elif current_theme == "엑셀 테마":
    THEME_LAYOUT = dict(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_COLOR, size=13), margin=dict(l=0, r=0, t=30, b=0), xaxis=dict(showgrid=True, gridcolor='#E1DFDD', zerolinecolor='#8A8886'), yaxis=dict(showgrid=True, gridcolor='#E1DFDD', zerolinecolor='#8A8886'))
else:
    THEME_LAYOUT = dict(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_COLOR, size=13), margin=dict(l=0, r=0, t=30, b=0), xaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.05)'), yaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.05)'))


def apply_custom_css():
    css_base = ""
    css_panel = f".info-panel {{ background: {PANEL_BG}; border: {PANEL_BORDER}; border-radius: {PANEL_RADIUS}; padding: 16px; height: 100%; box-shadow: 0 4px 12px rgba(0,0,0,0.03); }}"
    
    if current_theme == "애플 테마":
        css_base = f"""
        @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
        .stApp {{ background: radial-gradient(circle at 15% 50%, rgba(240, 244, 255, 1), rgba(255, 255, 255, 0)), radial-gradient(circle at 85% 30%, rgba(230, 240, 255, 1), rgba(255, 255, 255, 0)); background-color: #f5f5f7; font-family: 'Pretendard', sans-serif; color: {TEXT_COLOR}; letter-spacing: -0.01em; }}
        div[data-testid="stVerticalBlockBorderWrapper"] > div, .st-emotion-cache-1104k38, .st-emotion-cache-16txtl3 {{ background: rgba(255, 255, 255, 0.65); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.5); border-radius: 20px; box-shadow: 0 4px 24px -1px rgba(0, 0, 0, 0.06); padding: 1.5rem; transition: transform 0.2s ease, box-shadow 0.2s ease; }}
        .stButton>button {{ background-color: rgba(255, 255, 255, 0.8); color: #007aff; border: 1px solid rgba(0, 122, 255, 0.3); border-radius: 12px; font-weight: 600; padding: 0.5rem 1rem; backdrop-filter: blur(10px); transition: all 0.2s; }}
        .stButton>button:hover {{ background-color: #007aff; color: #ffffff; transform: scale(1.02); }}
        input, textarea, select, div[data-baseweb="select"] > div {{ background-color: rgba(255, 255, 255, 0.5); backdrop-filter: blur(10px); color: {TEXT_COLOR}; border: 1px solid rgba(0,0,0,0.1); border-radius: 12px; }}
        [data-testid="stDataFrame"] {{ border-radius: 16px; border: 1px solid rgba(0,0,0,0.05); background: rgba(255, 255, 255, 0.5); }}
        [data-testid="stSidebar"] {{ background: rgba(245, 245, 247, 0.7); backdrop-filter: blur(20px); border-right: 1px solid rgba(0,0,0,0.05); }}
        button[data-baseweb="tab"][aria-selected="true"] {{ color: #1d1d1f; border-bottom-color: #1d1d1f; border-bottom-width: 2px; }}
        .sidebar-link {{ display: flex; align-items: center; padding: 8px 12px; margin-bottom: 4px; border-radius: 10px; text-decoration: none !important; color: {TEXT_COLOR}; font-weight: 600; font-size: 0.95rem; transition: background-color 0.2s, transform 0.1s; }}
        .sidebar-link:hover {{ background-color: rgba(0,0,0,0.05); transform: translateX(2px); }}
        """
        
    elif current_theme == "아이패드 테마":
        css_base = f"""
        .stApp, html, body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #F2F2F7 !important; color: {TEXT_COLOR} !important; }}
        div[data-testid="stVerticalBlockBorderWrapper"] > div, .st-emotion-cache-1104k38, .st-emotion-cache-16txtl3 {{ background-color: {PANEL_BG} !important; border: {PANEL_BORDER} !important; border-radius: {PANEL_RADIUS} !important; box-shadow: 0 4px 20px rgba(0,0,0,0.05) !important; padding: 1.5rem !important; }}
        .stButton>button {{ background-color: #F2F2F7 !important; color: #007aff !important; border: none !important; border-radius: 12px !important; font-weight: 600 !important; padding: 0.5rem 1rem !important; transition: all 0.2s; }}
        .stButton>button:hover {{ background-color: #007aff !important; color: #ffffff !important; }}
        input, textarea, select, div[data-baseweb="select"] > div {{ background-color: #F2F2F7 !important; color: {TEXT_COLOR} !important; border: none !important; border-radius: 10px !important; }}
        [data-testid="stDataFrame"] {{ border-radius: 16px !important; border: 1px solid #E5E5EA !important; }}
        [data-testid="stSidebar"] {{ background-color: #FFFFFF !important; border-right: 1px solid #E5E5EA !important; }}
        button[data-baseweb="tab"][aria-selected="true"] {{ color: #1d1d1f !important; border-bottom-color: #1d1d1f !important; border-bottom-width: 2px !important; }}
        .sidebar-link {{ display: flex; align-items: center; padding: 8px 12px; margin-bottom: 4px; border-radius: 10px; text-decoration: none !important; color: {TEXT_COLOR} !important; font-weight: 600; font-size: 0.95rem; transition: background-color 0.2s; }}
        .sidebar-link:hover {{ background-color: #F2F2F7; }}
        """
        css_panel = f".info-panel {{ background: {PANEL_BG}; border: {PANEL_BORDER}; border-radius: {PANEL_RADIUS}; padding: 16px; height: 100%; box-shadow: 0 4px 20px rgba(0,0,0,0.05); }}"

    elif current_theme == "갤럭시 탭 테마":
        css_base = f"""
        [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{ background-color: transparent !important; }}
        .stApp, html, body {{ font-family: 'Pretendard', sans-serif; background-color: #000000 !important; color: {TEXT_COLOR} !important; }}
        div[data-testid="stVerticalBlockBorderWrapper"] > div, .st-emotion-cache-1104k38, .st-emotion-cache-16txtl3 {{ background-color: {PANEL_BG} !important; border: {PANEL_BORDER} !important; border-radius: {PANEL_RADIUS} !important; padding: 1.5rem !important; box-shadow: none !important; }}
        .stButton>button {{ background-color: #333333 !important; color: #FAFAFA !important; border: none !important; border-radius: 20px !important; font-weight: 600 !important; padding: 0.5rem 1rem !important; transition: all 0.2s; }}
        .stButton>button:hover {{ background-color: #3E91FF !important; color: #ffffff !important; }}
        input, textarea, select, div[data-baseweb="select"] > div {{ background-color: #2C2C2E !important; color: {TEXT_COLOR} !important; border: none !important; border-radius: 14px !important; }}
        [data-testid="stDataFrame"] {{ border-radius: 20px !important; border: none !important; background-color: #1C1C1E !important; }}
        [data-testid="stSidebar"] {{ background-color: #151515 !important; border-right: 1px solid #333333 !important; }}
        button[data-baseweb="tab"] {{ color: #A0A0A0 !important; }}
        button[data-baseweb="tab"][aria-selected="true"] {{ color: #3E91FF !important; border-bottom-color: #3E91FF !important; border-bottom-width: 2px !important; }}
        .sidebar-link {{ display: flex; align-items: center; padding: 8px 12px; margin-bottom: 4px; border-radius: 14px; text-decoration: none !important; color: {TEXT_COLOR} !important; font-weight: 600; font-size: 0.95rem; transition: background-color 0.2s; }}
        .sidebar-link:hover {{ background-color: #333333; }}
        """
        css_panel = f".info-panel {{ background: {PANEL_BG}; border: {PANEL_BORDER}; border-radius: {PANEL_RADIUS}; padding: 16px; height: 100%; box-shadow: none; }}"

    elif current_theme == "엑셀 테마":
        css_base = f"""
        .stApp, html, body {{ font-family: 'Calibri', 'Malgun Gothic', sans-serif; background-color: #F3F2F1 !important; color: {TEXT_COLOR} !important; }}
        div[data-testid="stVerticalBlockBorderWrapper"] > div, .st-emotion-cache-1104k38, .st-emotion-cache-16txtl3 {{ background-color: {PANEL_BG} !important; border: {PANEL_BORDER} !important; border-top: 3px solid #107C41 !important; border-radius: {PANEL_RADIUS} !important; padding: 1.5rem !important; box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important; }}
        .stButton>button {{ background-color: #E1DFDD !important; color: #333333 !important; border: 1px solid #8A8886 !important; border-radius: 2px !important; font-weight: normal !important; padding: 0.3rem 0.8rem !important; }}
        .stButton>button:hover {{ background-color: #C8C6C4 !important; }}
        input, textarea, select, div[data-baseweb="select"] > div {{ background-color: #FFFFFF !important; color: {TEXT_COLOR} !important; border: 1px solid #8A8886 !important; border-radius: 0px !important; }}
        [data-testid="stDataFrame"] {{ border-radius: 0px !important; border: 1px solid #D4D4D4 !important; }}
        [data-testid="stSidebar"] {{ background-color: #FFFFFF !important; border-right: 1px solid #D4D4D4 !important; }}
        button[data-baseweb="tab"] {{ color: #666666 !important; font-weight: normal !important; }}
        button[data-baseweb="tab"][aria-selected="true"] {{ color: #107C41 !important; border-bottom-color: #107C41 !important; border-bottom-width: 2px !important; font-weight: bold !important; }}
        .sidebar-link {{ display: flex; align-items: center; padding: 6px 8px; margin-bottom: 2px; text-decoration: none !important; color: #0078D4 !important; font-family: 'Calibri', sans-serif; font-size: 0.95rem; border-bottom: 1px solid transparent; }}
        .sidebar-link:hover {{ border-bottom: 1px solid #0078D4; background-color: #F3F2F1; }}
        """
        css_panel = f".info-panel {{ background: {PANEL_BG}; border: {PANEL_BORDER}; border-top: 3px solid #107C41 !important; border-radius: {PANEL_RADIUS}; padding: 16px; height: 100%; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}"

    elif current_theme in ["1930년대 타자기 테마", "1920년대 타자기 테마"]:
        css_base = f"""
        @import url('https://fonts.googleapis.com/css2?family=Special+Elite&display=swap');
        [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{ background-color: transparent !important; }}
        .stApp, html, body {{ font-family: 'Special Elite', 'Courier New', monospace !important; background-color: #e4dccc !important; color: {TEXT_COLOR} !important; }}
        div[data-testid="stVerticalBlockBorderWrapper"] > div, .st-emotion-cache-1104k38, .st-emotion-cache-16txtl3 {{ background-color: #dfd7c5 !important; border: 2px solid {TEXT_COLOR} !important; border-radius: 0px !important; box-shadow: 4px 4px 0px {TEXT_COLOR} !important; padding: 1.5rem !important; }}
        .stButton>button {{ background-color: #d1c7b3 !important; color: {TEXT_COLOR} !important; border: 2px solid {TEXT_COLOR} !important; border-radius: 0px !important; box-shadow: 2px 2px 0px {TEXT_COLOR} !important; font-weight: bold !important; text-transform: uppercase; transition: all 0.1s; }}
        .stButton>button:active {{ box-shadow: 0px 0px 0px {TEXT_COLOR} !important; transform: translateY(2px) translateX(2px); }}
        input, textarea, select, div[data-baseweb="select"] > div {{ background-color: #f0e9d8 !important; color: {TEXT_COLOR} !important; border: 1px dashed {TEXT_COLOR} !important; border-radius: 0px !important; font-family: 'Special Elite', monospace !important; }}
        [data-testid="stDataFrame"] {{ border: 1px solid {TEXT_COLOR} !important; background-color: #f0e9d8 !important; border-radius: 0px !important; }}
        [data-testid="stSidebar"] {{ background-color: #d1c7b3 !important; border-right: 3px double {TEXT_COLOR} !important; }}
        button[data-baseweb="tab"][aria-selected="true"] {{ color: {TEXT_COLOR} !important; border-bottom-color: {TEXT_COLOR} !important; border-bottom-width: 3px !important; font-weight: bold !important; }}
        .sidebar-link {{ display: flex; align-items: center; padding: 8px 12px; margin-bottom: 4px; border: 1px solid transparent; border-radius: 0px; text-decoration: none !important; color: {TEXT_COLOR} !important; font-weight: bold; font-size: 0.95rem; transition: background-color 0.2s; }}
        .sidebar-link:hover {{ background-color: rgba(0,0,0,0.1); border: 1px dashed {TEXT_COLOR}; }}
        """
        css_panel = f".info-panel {{ background: #dfd7c5; border: 2px solid {TEXT_COLOR}; border-radius: 0px; padding: 16px; height: 100%; box-shadow: 4px 4px 0px {TEXT_COLOR}; }}"
    
    elif current_theme == "카페 테마":
        css_base = f"""
        @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
        .stApp, html, body {{ font-family: 'Pretendard', sans-serif; background-color: #FFFBF0; color: {TEXT_COLOR}; letter-spacing: -0.01em; }}
        div[data-testid="stVerticalBlockBorderWrapper"] > div, .st-emotion-cache-1104k38, .st-emotion-cache-16txtl3 {{ background-color: #FFFFFF; border: 2px solid #FFF0E5; border-radius: 24px; box-shadow: 0 8px 20px rgba(210, 190, 175, 0.15); padding: 1.5rem; transition: transform 0.2s ease, box-shadow 0.2s ease; }}
        .stButton>button {{ background-color: #FFB7B2; color: #FFFFFF; border: none; border-radius: 16px; font-weight: 700; padding: 0.6rem 1.2rem; box-shadow: 0 4px 0 #F29F9A; transition: all 0.2s; }}
        .stButton>button:hover {{ background-color: #FFC4C0; transform: translateY(2px); box-shadow: 0 2px 0 #F29F9A; }}
        input, textarea, select, div[data-baseweb="select"] > div {{ background-color: #FAFAFA; color: {TEXT_COLOR}; border: 2px solid #EAE3D9; border-radius: 12px; }}
        [data-testid="stDataFrame"] {{ border-radius: 16px; border: 2px solid #FFF0E5; }}
        [data-testid="stSidebar"] {{ background-color: #FFF6EC; border-right: 2px dashed #EAE3D9; }}
        button[data-baseweb="tab"][aria-selected="true"] {{ color: #FF9B94; border-bottom-color: #FF9B94; border-bottom-width: 3px; font-weight: bold; }}
        .sidebar-link {{ display: flex; align-items: center; padding: 8px 12px; margin-bottom: 4px; border-radius: 10px; text-decoration: none !important; color: {TEXT_COLOR} !important; font-weight: 700; font-size: 0.95rem; transition: background-color 0.2s, transform 0.1s; }}
        .sidebar-link:hover {{ background-color: #FFF0E5; transform: translateX(4px); }}
        """
        css_panel = f".info-panel {{ background: {PANEL_BG}; border: {PANEL_BORDER}; border-radius: {PANEL_RADIUS}; padding: 16px; height: 100%; box-shadow: 0 4px 12px rgba(210,190,175,0.1); }}"
    
    elif current_theme == "2000년대 구글 감성 테마":
        css_base = f"""
        .stApp, html, body {{ font-family: Arial, Tahoma, sans-serif; background-color: #FFFFFF; color: {TEXT_COLOR}; }}
        div[data-testid="stVerticalBlockBorderWrapper"] > div, .st-emotion-cache-1104k38, .st-emotion-cache-16txtl3 {{ background-color: #FFFFFF; border: 1px solid #CCCCCC; border-radius: 0px; box-shadow: none; padding: 1.5rem; }}
        .stButton>button {{ background-color: #F0F0F0; color: #000000; border: 1px solid #707070; border-radius: 2px; font-weight: normal; padding: 0.3rem 0.8rem; }}
        .stButton>button:hover {{ background-color: #E0E0E0; border: 1px solid #333333; }}
        input, textarea, select, div[data-baseweb="select"] > div {{ background-color: #FFFFFF; color: #000000; border: 1px solid #999999; border-radius: 0px; font-family: Arial, sans-serif; }}
        [data-testid="stDataFrame"] {{ border-radius: 0px; border: 1px solid #999999; }}
        [data-testid="stSidebar"] {{ background-color: #F8F9FA; border-right: 1px solid #CCCCCC; }}
        button[data-baseweb="tab"] {{ color: #0000EE; text-decoration: underline; font-weight: normal; }}
        button[data-baseweb="tab"][aria-selected="true"] {{ color: {TEXT_COLOR}; text-decoration: none; border-bottom: none; font-weight: bold; }}
        .sidebar-link {{ display: flex; align-items: center; padding: 6px 8px; margin-bottom: 2px; text-decoration: underline !important; color: #0000EE !important; font-family: Arial, sans-serif; font-size: 0.9rem; }}
        .sidebar-link:hover {{ color: #FF0000 !important; }}
        .sidebar-link span {{ display: none; }}
        """
        css_panel = f".info-panel {{ background: {PANEL_BG}; border: {PANEL_BORDER}; border-radius: {PANEL_RADIUS}; padding: 16px; height: 100%; }}"
    
    elif current_theme == "월스트리트 저널 테마":
        css_base = f"""
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&display=swap');
        [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{ background-color: transparent !important; }}
        .stApp, html, body {{ font-family: 'Playfair Display', serif; background-color: #F4F4F0 !important; color: {TEXT_COLOR}; }}
        div[data-testid="stVerticalBlockBorderWrapper"] > div, .st-emotion-cache-1104k38, .st-emotion-cache-16txtl3 {{ background-color: #FFFFFF; border: 1px solid #000000; border-radius: 0px; padding: 1.5rem; box-shadow: 3px 3px 0px rgba(0,0,0,0.1); border-top: 4px solid #000000; }}
        .stButton>button {{ background-color: #000000; color: #FFFFFF; border: none; border-radius: 0px; font-weight: bold; font-family: 'Arial', sans-serif; text-transform: uppercase; }}
        .stButton>button:hover {{ background-color: #333333; }}
        input, textarea, select, div[data-baseweb="select"] > div {{ background-color: #FFFFFF; color: {TEXT_COLOR}; border: 1px solid #000000; border-radius: 0px; font-family: 'Arial', sans-serif; }}
        [data-testid="stDataFrame"] {{ border-radius: 0px; border: 1px solid #000000; }}
        [data-testid="stSidebar"] {{ background-color: #EBEBEB; border-right: 2px solid #000000; }}
        button[data-baseweb="tab"][aria-selected="true"] {{ color: #000000; border-bottom: 3px solid #000000; font-weight: bold; }}
        .sidebar-link {{ display: flex; align-items: center; padding: 8px 12px; margin-bottom: 4px; text-decoration: none !important; color: #000000 !important; font-weight: bold; font-size: 0.95rem; border-bottom: 1px dotted #CCC; }}
        .sidebar-link:hover {{ background-color: #DDDDDD; }}
        """

    st.markdown(f"""
    <style>
    {css_base}
    div[data-testid="stMetricValue"] > div, div[data-testid="stMetricDelta"] > div, p, span, label, .stMarkdown {{ white-space: normal !important; word-break: keep-all !important; overflow-wrap: break-word !important; }}
    div[data-testid="stMetricValue"] {{ font-weight: bold; font-size: 1.8rem; color: {TEXT_COLOR}; }}
    .info-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px; }}
    @media (max-width: 800px) {{ .info-grid {{ grid-template-columns: 1fr; }} }}
    {css_panel}
    </style>
    """, unsafe_allow_html=True)

apply_custom_css()


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
    
    actual_regime_v4 = []; actual_regime_v4_3 = []
    current_v4 = 3; current_v4_3 = 3
    pend_v4 = None; pend_v4_3 = None
    cnt_v4 = 0; cnt_v4_3 = 0

    for i in range(len(df)):
        tr = df['Target_Regime'].iloc[i]
        if tr > current_v4: current_v4 = tr; pend_v4 = None; cnt_v4 = 0; actual_regime_v4.append(current_v4)
        elif tr < current_v4:
            if tr == pend_v4:
                cnt_v4 += 1
                if cnt_v4 >= 5: current_v4 = tr; pend_v4 = None; cnt_v4 = 0; actual_regime_v4.append(current_v4)
                else: actual_regime_v4.append(current_v4)
            else: pend_v4 = tr; cnt_v4 = 1; actual_regime_v4.append(current_v4)
        else: pend_v4 = None; cnt_v4 = 0; actual_regime_v4.append(current_v4)
        
        if tr > current_v4_3: current_v4_3 = tr; pend_v4_3 = None; cnt_v4_3 = 0; actual_regime_v4_3.append(current_v4_3)
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
        w = {t: 0.0 for t in data.columns}; semi = 'SOXL' if use_soxl else 'USD'
        if regime == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'] = 0.30, 0.20, 0.20, 0.15, 0.10
        elif regime == 2: w['QLD'], w['SSO'], w['GLD'], w['QQQ'], w['USD'] = 0.25, 0.20, 0.20, 0.15, 0.10
        elif regime == 3: w['GLD'], w['QQQ'], w['SPY'] = 0.35, 0.20, 0.10
        elif regime == 4: w['GLD'], w['QQQ'] = 0.50, 0.10
        return w

    def get_v4_3_weights(regime, use_soxl):
        w = {t: 0.0 for t in data.columns}; semi = 'SOXL' if use_soxl else 'USD'
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
        days_since_v4 += 1; days_since_v4_3 += 1
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
        if rebal_v4: weights_v4 = get_v4_weights(sig_r_v4, use_soxl); days_since_v4 = 0

        sig_r_v4_3 = df['Signal_Regime_v4_3'].iloc[i]
        rebal_v4_3 = False
        if sig_r_v4_3 != df['Signal_Regime_v4_3'].iloc[i-1] or i == 1: rebal_v4_3 = True
        elif rebal_freq == "월 1회" and today.month != yesterday.month: rebal_v4_3 = True
        elif "주 1회" in rebal_freq and days_since_v4_3 >= 5: rebal_v4_3 = True
        elif "2주 1회" in rebal_freq and days_since_v4_3 >= 10: rebal_v4_3 = True
        elif "3주 1회" in rebal_freq and days_since_v4_3 >= 15: rebal_v4_3 = True
        if rebal_v4_3:
            weights_v4_3 = get_v4_3_weights(sig_r_v4_3, use_soxl)
            log_type = "레짐 전환" if sig_r_v4_3 != df['Signal_Regime_v4_3'].iloc[i-1] else f"정기 ({rebal_freq.split(' ')[0]})"
            semi_target = "SOXL" if use_soxl and sig_r_v4_3 == 1 else ("USD" if sig_r_v4_3 in [1, 2] else "-")
            logs.append({"날짜": today.strftime('%Y-%m-%d'), "유형": log_type, "국면": f"R{int(sig_r_v4_3)}", "반도체": semi_target, "평가액": ports['AMLS v4.3']})
            days_since_v4_3 = 0

    for s in ports: df[f'{s}_Value'] = hists[s]
    inv_arr = [init_cap]; curr_inv = init_cap
    for i in range(1, len(df)):
        if df.index[i].month != df.index[i-1].month: curr_inv += monthly_cont
        inv_arr.append(curr_inv)
    df['Invested'] = inv_arr
    return df, logs, data.columns


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
            st.markdown("##### 🗺️ S&P 500 히트맵")
            components.html(f"""<div style="border-radius: {PANEL_RADIUS}; overflow: hidden; height: 100%;">
<iframe src="https://www.tradingview.com/embed-widget-stock-heatmap/?locale=kr#%7B%22dataSource%22%3A%22SPX500%22%2C%22blockSize%22%3A%22market_cap_basic%22%2C%22blockColor%22%3A%22change%22%2C%22grouping%22%3A%22sector%22%2C%22colorTheme%22%3A%22{WIDGET_THEME}%22%7D" width="100%" height="450" frameborder="0"></iframe>
</div>""", height=460)


# =====================================================================
# [5] 페이지 구성: AMLS 백테스트
# =====================================================================
def page_amls_backtest():
    st.title("🦅 전략 시뮬레이터")

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

    strats = ['AMLS v4.3', 'QQQ', 'QLD', 'TQQQ']
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

        st.markdown("#### 🥧 국면별 비중")
        c1, c2, c3, c4 = st.columns(4)
        def get_w(reg):
            if reg == 1: return {'TQQQ':30, 'SOXL/USD':20, 'QLD':20, 'SSO':15, 'GLD':10, 'CASH':5}
            elif reg == 2: return {'QLD':30, 'SSO':25, 'GLD':20, 'USD':10, 'QQQ':5, 'CASH':10}
            elif reg == 3: return {'GLD':50, 'CASH':35, 'QQQ':15}
            elif reg == 4: return {'GLD':50, 'CASH':40, 'QQQ':10}
        
        for i, col in enumerate([c1, c2, c3, c4]):
            r = i+1; w = {k:v for k,v in get_w(r).items() if v>0}
            fig_p = go.Figure(go.Pie(labels=list(w.keys()), values=list(w.values()), hole=0.5, marker=dict(colors=[COLOR_PALETTE.get(k.split('/')[0], '#888') for k in w.keys()])))
            cust_p = THEME_LAYOUT.copy(); cust_p.update(title=f"R{r}", title_x=0.5, height=250, margin=dict(t=40,b=10,l=10,r=10), showlegend=False)
            fig_p.update_layout(**cust_p)
            fig_p.update_traces(textinfo='label+percent', textposition='inside', textfont=dict(color="#ffffff" if current_theme in ["1930년대 타자기 테마", "월스트리트 저널 테마", "블룸버그 터미널 테마"] else TEXT_COLOR, size=11))
            col.plotly_chart(fig_p, use_container_width=True)

    with tab2:
        st.markdown("#### 📈 자산 곡선")
        use_log = st.checkbox("Y축 로그 스케일", value=False)
        fig_eq = go.Figure()
        
        fig_eq.add_trace(go.Scatter(x=df.index, y=df['AMLS v4.3_Value'], name='AMLS v4.3', line=dict(color=C_UP, width=3)))
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
# [6] 페이지 구성: 내 포트폴리오 관리 (목표 달성률 궤적 추적 차트 추가)
# =====================================================================
def make_portfolio_page(acc_name):
    def page_func():
        st.title(f"💼 {acc_name}")
        
        curr_acc_data = st.session_state['accounts'][acc_name]
        
        # 기존 "📈 성장 곡선"을 "📈 목표 달성률 추이"로 마이그레이션
        DEFAULT_LAYOUT = ["🎯 목표 달성률", "📊 실시간 요약", "⚡ 시스템 분석관", "💼 포트폴리오 & 리밸런싱", "📈 목표 달성률 추이", "📝 매매 일지"]
        current_layout = curr_acc_data.get("layout_order", [])
        
        if "💼 기입표" in current_layout: current_layout[current_layout.index("💼 기입표")] = "💼 포트폴리오 & 리밸런싱"
        if "🍩 자산 배분 & 지침" in current_layout: current_layout.remove("🍩 자산 배분 & 지침")
        if "🍩 배분 및 지침" in current_layout: current_layout.remove("🍩 배분 및 지침")
        if "📈 성장 곡선" in current_layout: current_layout[current_layout.index("📈 성장 곡선")] = "📈 목표 달성률 추이"
            
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
            TICKERS = ['QQQ', 'TQQQ', 'SOXL', 'USD', 'QLD', 'SSO', 'SPY', 'SMH', 'GLD', '^VIX']
            data = yf.download(TICKERS, start=datetime.today()-timedelta(days=400), progress=False)['Close'].ffill()
            today = data.iloc[-1]; yesterday = data.iloc[-2]
            
            ma200_s = data['QQQ'].rolling(200).mean()
            ma50_s = data['QQQ'].rolling(50).mean()
            smh_ma50_s = data['SMH'].rolling(50).mean()
            smh_3m_ret_s = data['SMH'].pct_change(63)
            smh_rsi_s = ta.rsi(data['SMH'], length=14)
            
            # 1. 쌩 타겟 레짐 계산
            target_regimes = []
            for i in range(len(data)):
                v = data['^VIX'].iloc[i]; q = data['QQQ'].iloc[i]; m200 = ma200_s.iloc[i]; m50 = ma50_s.iloc[i]
                if pd.isna(m200): target_regimes.append(2); continue
                if v > 40: target_regimes.append(4)
                elif q < m200: target_regimes.append(3)
                elif q >= m200 and m50 >= m200 and v < 25: target_regimes.append(1)
                else: target_regimes.append(2)
                
            # 2. AMLS v4.3 5일 대기 로직 적용
            current_v4_3 = 3; pend_v4_3 = None; cnt_v4_3 = 0; actual_regime_v4_3 = []
            for tr in target_regimes:
                if tr > current_v4_3: 
                    current_v4_3 = tr; pend_v4_3 = None; cnt_v4_3 = 0; actual_regime_v4_3.append(current_v4_3)
                elif tr < current_v4_3:
                    if tr == pend_v4_3:
                        cnt_v4_3 += 1
                        if cnt_v4_3 >= 5: current_v4_3 = tr; pend_v4_3 = None; cnt_v4_3 = 0; actual_regime_v4_3.append(current_v4_3)
                        else: actual_regime_v4_3.append(current_v4_3 - 1)
                    else: 
                        pend_v4_3 = tr; cnt_v4_3 = 1; actual_regime_v4_3.append(current_v4_3 - 1)
                else: 
                    pend_v4_3 = None; cnt_v4_3 = 0; actual_regime_v4_3.append(current_v4_3)
                    
            applied_series = pd.Series(actual_regime_v4_3, index=data.index).shift(1).bfill()
            applied_reg = int(applied_series.iloc[-1])
            target_reg = int(target_regimes[-1])
            
            # 🔥 5일 대기 여부 판독
            is_waiting = (pend_v4_3 is not None and target_reg < current_v4_3)

            # 🔥 현재 적용중인 레짐 체류 일수 계산
            current_reg = applied_series.iloc[-1]
            regime_duration = 0
            for i in range(len(applied_series)-1, -1, -1):
                if applied_series.iloc[i] == current_reg: regime_duration += 1
                else: break

            try:
                fx_data = yf.download('USDKRW=X', period='5d', progress=False)['Close'].ffill()
                current_usdkrw = float(fx_data.iloc[:, 0].iloc[-1] if isinstance(fx_data, pd.DataFrame) else fx_data.iloc[-1])
            except: current_usdkrw = 0.0

            return {
                'regime': applied_reg, 'target_regime': target_reg, 'is_waiting': is_waiting, 'wait_days': cnt_v4_3,
                'regime_duration': regime_duration,
                'vix': today['^VIX'], 'qqq': today['QQQ'], 'ma200': ma200_s.iloc[-1], 'ma50': ma50_s.iloc[-1],
                'smh': today['SMH'], 'smh_ma50': smh_ma50_s.iloc[-1], 'smh_3m_ret': smh_3m_ret_s.iloc[-1], 'smh_rsi': smh_rsi_s.iloc[-1],
                'prices': today.to_dict(), 'prev_prices': yesterday.to_dict(), 'date': data.index[-1], 'usdkrw': current_usdkrw
            }

        @st.cache_data(ttl=60)
        def get_realtime_prices():
            RT_TICKERS = ['QQQ', 'TQQQ', 'SOXL', 'USD', 'QLD', 'SSO', 'SPY', 'SMH', 'GLD', '^VIX', 'USDKRW=X']
            try:
                rt = yf.download(RT_TICKERS, period='1d', interval='5m', prepost=True, progress=False)['Close']
                if rt.empty: return None
                return rt.ffill().iloc[-1].to_dict()
            except: return None

        with st.spinner("AI 엔진 동기화 중..."): 
            ms = get_market_status()
            rt_prices = get_realtime_prices()

        if rt_prices:
            for k, v in rt_prices.items():
                if k in ms['prices'] and pd.notna(v): ms['prices'][k] = v
            if pd.notna(rt_prices.get('^VIX', None)): ms['vix'] = rt_prices['^VIX']
            if pd.notna(rt_prices.get('QQQ', None)): ms['qqq'] = rt_prices['QQQ']
            if pd.notna(rt_prices.get('SMH', None)): ms['smh'] = rt_prices['SMH']
            if pd.notna(rt_prices.get('USDKRW=X', None)): ms['usdkrw'] = rt_prices['USDKRW=X']
            
            # 실시간 타겟 레짐 업데이트
            vix_rt, qqq_rt = ms['vix'], ms['qqq']
            if vix_rt > 40: rt_tgt = 4
            elif qqq_rt < ms['ma200']: rt_tgt = 3
            elif qqq_rt >= ms['ma200'] and ms['ma50'] >= ms['ma200'] and vix_rt < 25: rt_tgt = 1
            else: rt_tgt = 2
            
            ms['target_regime'] = rt_tgt
            
            # 패닉(하향)은 5일 대기 없이 즉각 적용
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
        asset_vals = {}
        
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

        daily_diff = total_val_now - total_val_yest
        daily_diff_pct = (daily_diff / total_val_yest * 100) if total_val_yest > 0 else 0.0

        st.session_state['accounts'][acc_name]["target_seed"] = auto_seed
        rebal_base = total_val_now if total_val_now > 0 else auto_seed

        # 매일 자동 스냅샷 기록 (목표 달성률 궤적 추적용)
        today_str = datetime.now().strftime("%Y-%m-%d")
        history_changed = False
        last_seed = curr_acc_data["seed_history"].get(today_str, {}).get("seed")
        last_equity = curr_acc_data["seed_history"].get(today_str, {}).get("equity")
        if total_val_now > 0 or auto_seed > 0:
            if last_seed != auto_seed or last_equity != total_val_now:
                curr_acc_data["seed_history"][today_str] = {"seed": auto_seed, "equity": total_val_now}
                history_changed = True
        if history_changed: save_accounts_data(st.session_state['accounts'])


        # -------------------------------------------------------------
        # 레이아웃 편집기 UI
        # -------------------------------------------------------------
        with st.expander("🛠️ 화면 레이아웃 편집 (위아래로 순서 변경)"):
            for i, block_name in enumerate(current_layout):
                c_name, c_up, c_dn = st.columns([6, 1, 1])
                c_name.markdown(f"<div style='padding-top:5px; font-weight:bold;'>{i+1}. {block_name}</div>", unsafe_allow_html=True)
                if c_up.button("▲ 올리기", key=f"up_{i}_{acc_name}") and i > 0:
                    current_layout[i], current_layout[i-1] = current_layout[i-1], current_layout[i]
                    curr_acc_data["layout_order"] = current_layout
                    save_accounts_data(st.session_state['accounts']); st.rerun()
                if c_dn.button("▼ 내리기", key=f"dn_{i}_{acc_name}") and i < len(current_layout)-1:
                    current_layout[i], current_layout[i+1] = current_layout[i+1], current_layout[i]
                    curr_acc_data["layout_order"] = current_layout
                    save_accounts_data(st.session_state['accounts']); st.rerun()

        st.write("")

        # -------------------------------------------------------------
        # 동적 레이아웃 렌더링 루프
        # -------------------------------------------------------------
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
                    pb_bg = "rgba(0,0,0,0.1)" if WIDGET_THEME=="light" else "rgba(255,255,255,0.1)"
                    st.markdown(f"""<div class='info-panel'>
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
                
                col_group, col_ai = st.columns([3, 1])
                
                with col_group:
                    pn_col = C_UP if daily_diff > 0 else (C_DOWN if daily_diff < 0 else TEXT_COLOR)
                    pn_ico = "▲" if daily_diff > 0 else ("▼" if daily_diff < 0 else "-")
                    
                    st.markdown(f"""<div class='info-panel' style='display:flex; justify-content:space-around; align-items:center; text-align:center;'>
<div style='flex:1; border-right:1px dashed rgba(150,150,150,0.4);'>
<div style='font-size:0.85rem; font-weight:bold; opacity:0.8; color:{TEXT_COLOR};'>💰 총 평가액 (Total)</div>
<div style='font-size:1.6rem; font-weight:bold; margin-top:5px; color:{TEXT_COLOR};'>${total_val_now:,.0f}</div>
</div>
<div style='flex:1; border-right:1px dashed rgba(150,150,150,0.4);'>
<div style='font-size:0.85rem; font-weight:bold; opacity:0.8; color:{TEXT_COLOR};'>일간 손익 (Daily)</div>
<div style='color:{pn_col}; font-size:1.6rem; font-weight:bold; margin-top:5px;'>{pn_ico} {abs(daily_diff_pct):.2f}%</div>
<div style='color:{pn_col}; font-size:0.8rem;'>({daily_diff:+.0f} $)</div>
</div>
<div style='flex:1;'>
<div style='font-size:0.85rem; font-weight:bold; opacity:0.8; color:{TEXT_COLOR};'>👑 포트폴리오 MVP</div>
<div style='font-size:1.6rem; font-weight:bold; margin-top:5px; color:{TEXT_COLOR};'>{best_ticker}</div>
<div style='font-size:0.8rem; font-weight:bold; color:{TEXT_COLOR};'>수익률 {best_ret:+.1f}%</div>
</div>
</div>""", unsafe_allow_html=True)

                with col_ai:
                    app_reg = ms['regime']
                    st.markdown(f"""<div class='info-panel' style='text-align:center; display:flex; flex-direction:column; justify-content:center;'>
<div style='font-size:0.85rem; font-weight:bold; opacity:0.8; color:{TEXT_COLOR};'>AI 전략 국면</div>
<div style='font-size:1.6rem; font-weight:bold; margin-top:5px; color:{TEXT_COLOR};'>Regime {app_reg}</div>
</div>""", unsafe_allow_html=True)
                st.write("")
                
            elif block == "⚡ 시스템 분석관":
                st.markdown("#### ⚡ 실시간 시스템 분석관 요약")
                app_reg = ms['regime']
                tgt_reg = ms['target_regime']
                is_wait = ms['is_waiting']
                wait_d = ms['wait_days']
                dur = ms['regime_duration']
                
                vix_c = ms['vix']; qqq_c = ms['qqq']; ma200_c = ms['ma200']; smh_c = ms['smh']; smh_ma50_c = ms['smh_ma50']
                
                s_stat = f"<span style='color:{C_UP}; font-weight:bold;'>돌파</span>" if smh_c > smh_ma50_c else f"<span style='color:{C_DOWN}; font-weight:bold;'>붕괴</span>"
                r_stat = f"<span style='color:{C_UP}; font-weight:bold;'>통과</span>" if ms['smh_3m_ret'] > 0.05 else f"<span style='color:{C_DOWN}; font-weight:bold;'>미달</span>"
                rsi_stat = f"<span style='color:{C_UP}; font-weight:bold;'>통과</span>" if ms['smh_rsi'] > 50 else f"<span style='color:{C_DOWN}; font-weight:bold;'>미달</span>"
                soxl_res = f"<span style='color:{C_UP}; font-weight:bold;'>SOXL 편입 승인</span>" if (smh_c > smh_ma50_c and ms['smh_3m_ret'] > 0.05 and ms['smh_rsi'] > 50) else f"<span style='color:{C_WARN}; font-weight:bold;'>USD(2X) 방어 유지</span>"

                # 🔥 5일 대기 메시지
                wait_msg = ""
                if is_wait and tgt_reg < app_reg:
                    wait_msg = f"<div style='margin-top:10px; padding:10px; background-color:rgba(255,193,7,0.15); border-left:4px solid #ffc107; border-radius:4px;'><span style='color:#ff9800; font-weight:bold;'>⏳ 상향 전환 검증 진행 중 ({wait_d}/5일차)</span><br>현재 시장 지표는 <b>[R{tgt_reg}]</b> 조건을 충족했으나, 휩쏘(속임수)를 피하기 위해 5일 연속 체류를 확인하고 있습니다. 대기 기간 동안은 보수적으로 <b>[R{app_reg}]</b> 비중을 유지합니다.</div>"
                elif tgt_reg > app_reg:
                    wait_msg = f"<div style='margin-top:10px; padding:10px; background-color:rgba(231,76,60,0.15); border-left:4px solid #e74c3c; border-radius:4px;'><span style='color:#e74c3c; font-weight:bold;'>🚨 하락 전환 주의 발동</span><br>현재 시장 지표가 <b>[R{tgt_reg}]</b> 악화 조건을 터치했습니다. 오늘 종가가 이대로 마감되면 내일 아침 즉시 대기 없이 하향 전환됩니다.</div>"

                # 🔥 AI 브리핑 문구 + 체류 일수 표기 추가
                dur_text = f"<br><span style='color:{C_SAFE}; font-weight:bold;'>⏱️ 현재 R{app_reg} 체류 기간: {dur}일째</span>"
                
                if app_reg == 1:
                    reg_t = f"<span style='color:{C_UP}; font-weight:bold;'>[R1: 완벽한 강세장]</span>"
                    reg_d = f"VIX({vix_c:.1f}) 안정권 및 나스닥({qqq_c:.0f}) 정배열 유지. 하방 리스크가 제한적이므로 3배 레버리지를 가동해 상승분을 캡처하십시오.{dur_text}{wait_msg}"
                elif app_reg == 2:
                    reg_t = f"<span style='color:{C_WARN}; font-weight:bold;'>[R2: 조정/경계]</span>"
                    reg_d = f"장기 추세는 유효하나 VIX({vix_c:.1f})가 상승했거나 단기 모멘텀이 약화되었습니다. 과도한 레버리지를 2배수 이하로 축소하십시오.{dur_text}{wait_msg}"
                elif app_reg == 3:
                    reg_t = f"<span style='color:{C_DOWN}; font-weight:bold;'>[R3: 장기 하락장]</span>"
                    reg_d = f"나스닥({qqq_c:.0f})이 200일선({ma200_c:.0f})을 하향 이탈했습니다. 하락 추세가 컨펌되었으니 레버리지 청산 후 GLD로 방어하십시오.{dur_text}{wait_msg}"
                else:
                    reg_t = f"<span style='color:{C_DOWN}; font-weight:bold;'>[R4: 시스템 패닉]</span>"
                    reg_d = f"VIX({vix_c:.1f}) 40 돌파. 시장이 이성을 상실한 시스템 리스크 구간입니다. 주식을 전량 매도하고 안전자산으로 대피하십시오.{dur_text}{wait_msg}"

                st.markdown(f"""<div class='info-grid'>
<div class='info-panel'>
<div style='font-weight:bold; margin-bottom:8px; border-bottom:1px solid currentColor; padding-bottom:4px; opacity:0.8;'>⚡ SOXL 진입 판독기</div>
<div style='font-size:0.85rem; line-height:1.6;'>
• <b>50MA 추세:</b> {s_stat} (현재 ${smh_c:.1f} / 기준 ${smh_ma50_c:.1f})<br>
• <b>3M 모멘텀:</b> {r_stat} (누적 {ms['smh_3m_ret']*100:+.1f}% / 기준 +5%)<br>
• <b>RSI(14) 지수:</b> {rsi_stat} (현재 {ms['smh_rsi']:.1f} / 기준 50)<br>
<div style='margin-top:6px; padding-top:6px; border-top:1px dashed currentColor; opacity:0.9;'>
<b>결론:</b> {soxl_res}
</div>
</div>
</div>
<div class='info-panel' style='grid-column: span 2;'>
<div style='font-weight:bold; margin-bottom:8px; border-bottom:1px solid currentColor; padding-bottom:4px; opacity:0.8;'>🤖 AI 전략 분석관 Report</div>
<div style='font-size:0.85rem; line-height:1.6;'>
• <b>상태:</b> {reg_t}<br>
<span style='opacity:0.9;'>{reg_d}</span>
</div>
</div>
</div>""", unsafe_allow_html=True)
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
                            fig = go.Figure(go.Pie(labels=list(asset_vals.keys()), values=list(asset_vals.values()), hole=0.6, marker=dict(colors=[st.session_state['settings']['chart_colors'].get(k, '#888') for k in asset_vals.keys()])))
                            cust_p2 = THEME_LAYOUT.copy()
                            cust_p2.update(height=280, showlegend=False, margin=dict(t=10, b=10, l=10, r=10), annotations=[dict(text=f"100%", x=0.5, y=0.5, showarrow=False, font=dict(color=TEXT_COLOR, size=16))])
                            fig.update_layout(**cust_p2)
                            fig.update_traces(textposition='inside', textinfo='percent+label', textfont_size=13, textfont_color="#fff" if current_theme in ["1930년대 타자기 테마", "월스트리트 저널 테마"] else TEXT_COLOR)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.markdown("<div style='height: 280px; display: flex; align-items: center; justify-content: center; color: #888;'>자산을 입력해 주세요.</div>", unsafe_allow_html=True)
                
                # 🔥 기계적 리밸런싱 지침 (+1.5주 톨러런스 적용)
                st.write("")
                st.markdown("#### ⚖️ 기계적 리밸런싱 지침 (Tolerance: ±1.5주)")
                with st.container(border=True):
                    status_d = []
                    smh_cond = (ms['smh'] > ms['smh_ma50']) and (ms['smh_3m_ret'] > 0.05) and (ms['smh_rsi'] > 50)
                    def get_w_local(reg, usx):
                        w = {t: 0.0 for t in REQUIRED_TICKERS}; semi = 'SOXL' if usx else 'USD'
                        if reg == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'], w['CASH'] = 0.30, 0.20, 0.20, 0.15, 0.10, 0.05
                        elif reg == 2: w['QLD'], w['SSO'], w['GLD'], w['USD'], w['QQQ'], w['CASH'] = 0.30, 0.25, 0.20, 0.10, 0.05, 0.10
                        elif reg == 3: w['GLD'], w['CASH'], w['QQQ'] = 0.50, 0.35, 0.15
                        elif reg == 4: w['GLD'], w['CASH'], w['QQQ'] = 0.50, 0.40, 0.10
                        return {k: v for k, v in w.items() if v > 0}
                        
                    target_w_dict = get_w_local(ms['regime'], smh_cond)
                    
                    # 운용 시드 직접 입력 받기
                    target_seed = st.number_input("운용 시드 설정 ($)", value=float(curr_acc_data.get("target_seed", 10000.0)), step=1000.0, key=f"seed_{acc_name}")
                    if target_seed != curr_acc_data.get("target_seed"):
                        st.session_state['accounts'][acc_name]["target_seed"] = target_seed
                        save_accounts_data(st.session_state['accounts'])

                    all_tkrs = set([t for t in asset_vals.keys()] + list(target_w_dict.keys()))
                    for tkr in all_tkrs:
                        tkr = tkr.upper()
                        my_v = asset_vals.get(tkr, 0.0); my_w = (my_v / total_val_now * 100) if total_val_now > 0 else 0.0
                        tw = target_w_dict.get(tkr, 0.0)
                        
                        # 목표 자산 금액 계산 (운용 시드 기준)
                        tv = target_seed * tw
                        diff = tv - my_v
                        cp = live_prices.get(tkr, 0.0)
                        
                        # 주식 수 및 톨러런스(±1.5주) 계산
                        if tkr != "CASH" and cp > 0:
                            shares_to_trade = abs(diff) / cp
                            action_suffix = f" (약 {shares_to_trade:.1f}주)"
                            
                            # 1.5주 이하 차이는 '유지'로 판정하여 잦은 매매 방지
                            if shares_to_trade <= 1.5: action = "유지 (적정)"
                            elif diff > 0: action = f"매수 ${diff:,.0f}{action_suffix}"
                            else: action = f"매도 ${abs(diff):,.0f}{action_suffix}"
                            
                        elif tkr == "CASH":
                            # 현금은 $50 이하 차이를 유지로 판별
                            if abs(diff) < 50: action = "유지 (적정)"
                            elif diff > 0: action = f"추가 ${diff:,.0f}"
                            else: action = f"인출 ${abs(diff):,.0f}"
                        else: action = "유지 (적정)"
                        
                        if my_v > 0 or tw > 0: 
                            status_d.append({"종목": tkr, "목표비중": f"{tw*100:.1f}%", "현재비중": f"{my_w:.1f}%", "목표액": f"${tv:,.0f}", "현재액": f"${my_v:,.0f}", "리밸런싱 액션": action})
                            
                    if status_d:
                        status_df = pd.DataFrame(status_d).sort_values("목표비중", ascending=False)
                        
                        # 차트 그리기
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

            # 🔥 목표 달성률 추이 그래프 (새로 적용됨)
            elif block == "📈 목표 달성률 추이":
                st.markdown("#### 📈 목표 달성률 추이")
                hist_dict = curr_acc_data.get("seed_history", {})
                target_val = curr_acc_data.get("target_portfolio_value", 100000.0)
                
                if hist_dict and target_val > 0:
                    with st.container(border=True):
                        hist_df = pd.DataFrame.from_dict(hist_dict, orient='index')
                        hist_df.index = pd.to_datetime(hist_df.index)
                        hist_df = hist_df.sort_index()

                        # 목표 달성률(%) 계산
                        hist_df['achieve_pct'] = (hist_df['equity'] / target_val) * 100

                        fig_achieve = go.Figure()
                        fig_achieve.add_trace(go.Scatter(
                            x=hist_df.index, y=hist_df['achieve_pct'], 
                            name="달성률", mode='lines+markers',
                            line=dict(color=C_UP, width=3), 
                            marker=dict(size=6),
                            fill='tozeroy', fillcolor='rgba(0,0,0,0)'
                        ))
                        # 100% 도달 선
                        fig_achieve.add_hline(y=100, line_dash="dash", line_color=C_DOWN, annotation_text="목표 달성 (100%)", annotation_position="top left")
                        
                        cust_s = THEME_LAYOUT.copy()
                        cust_s.update(height=350, hovermode="x unified", yaxis=dict(showgrid=True, ticksuffix="%"))
                        fig_achieve.update_layout(**cust_s)
                        st.plotly_chart(fig_achieve, use_container_width=True)
                        st.caption("💡 앱에 접속하실 때마다(혹은 아침에 확인하실 때) 자동으로 해당 날짜의 총 평가액을 스냅샷으로 저장하고, 설정된 목표 금액 대비 달성률(%) 궤적을 추적합니다.")
                else:
                    st.info("아직 충분한 자산 기록이 없거나 목표 금액이 설정되지 않았습니다.")
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
            st.session_state['accounts'][new_acc] = {"portfolio": [{"티커 (Ticker)": t, "수량 (주/달러)": 0.0, "평균 단가 ($)": 0.0, "매입 환율": 0.0, "태그": "코어"} for t in REQUIRED_TICKERS], "history": [{"Date": datetime.now().strftime("%Y-%m-%d"), "Log": "계좌 개설"}], "target_seed": 10000.0, "seed_history": {}, "target_portfolio_value": 100000.0, "layout_order": ["🎯 목표 달성률", "📊 실시간 요약", "⚡ 시스템 분석관", "💼 포트폴리오 & 리밸런싱", "📈 목표 달성률 추이", "📝 매매 일지"]}
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
    st.markdown("### 🏷️ 버전: v4.3")
    st.table(pd.DataFrame({"우선순위": ["1", "2", "3", "4"], "조건": ["VIX > 40", "QQQ < 200일선", "정배열 & VIX < 25", "그 외 조건"], "레짐": ["R4 (위기)", "R3 (약세)", "R1 (강세)", "R2 (보통)"]}))


# =====================================================================
# [7] 사이드바 설정 및 네비게이션
# =====================================================================

st.sidebar.markdown("---")
st.sidebar.markdown("### 🎨 테마 설정")
theme_list = ["애플 테마", "아이패드 테마", "갤럭시 탭 테마", "1930년대 타자기 테마", "카페 테마", "2000년대 구글 감성 테마", "월스트리트 저널 테마", "엑셀 테마"]
selected_theme = st.sidebar.selectbox("테마를 선택하세요", theme_list, index=theme_list.index(current_theme))
if selected_theme != current_theme:
    st.session_state['settings']['theme'] = selected_theme
    save_settings(st.session_state['settings']); st.rerun()

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

with st.sidebar.expander("🎨 테마 색상 커스텀"):
    st.markdown("**기본 텍스트**")
    new_text_color = st.color_picker("색상", st.session_state['settings']['text_color'])
    if new_text_color != st.session_state['settings']['text_color']:
        st.session_state['settings']['text_color'] = new_text_color
        save_settings(st.session_state['settings']); st.rerun()
        
    st.markdown("---")
    st.markdown("📈 **파이 차트 조각**")
    for tkr in st.session_state['settings']['chart_colors']:
        new_c = st.color_picker(f"{tkr}", st.session_state['settings']['chart_colors'][tkr])
        if new_c != st.session_state['settings']['chart_colors'][tkr]:
            st.session_state['settings']['chart_colors'][tkr] = new_c
            save_settings(st.session_state['settings']); st.rerun()

with st.sidebar.expander("💾 백업 및 복구"):
    st.download_button("📥 백업 다운로드", data=json.dumps(st.session_state['accounts']), file_name="amls_backup.json")
    up_f = st.file_uploader("📤 복구 업로드", type=['json'])
    if up_f and st.button("⚠️ 복구 실행"):
        st.session_state['accounts'] = json.load(up_f)
        save_accounts_data(st.session_state['accounts']); st.rerun()

pages = {
    "시스템": [st.Page(page_market_dashboard, title="마켓 터미널", icon="🌐"), st.Page(page_amls_backtest, title="백테스트 엔진", icon="🦅")],
    "포트폴리오": [],
    "설정": [st.Page(page_strategy_specification, title="전략 명세서", icon="📜"), st.Page(page_manage_accounts, title="계좌 관리", icon="⚙️")]
}

for name in st.session_state['accounts'].keys():
    pages["포트폴리오"].append(st.Page(make_portfolio_page(name), title=name, icon="💼"))

pg = st.navigation(pages)
pg.run()
