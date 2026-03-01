import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')

# --- 페이지 기본 설정 ---
st.set_page_config(page_title="AMLS v4 통합 대시보드", layout="wide", initial_sidebar_state="expanded")
st.title("🛡️ AMLS v4 실전 퀀트 대시보드 (Final Edition)")

# --- 사이드바 설정 (사용자 입력) ---
st.sidebar.header("⚙️ 백테스트 설정")
st.sidebar.markdown("이곳에서 설정값을 바꾸면 대시보드가 실시간으로 다시 계산됩니다.")
BACKTEST_START = st.sidebar.date_input("시작일", datetime(2018, 1, 1))
BACKTEST_END = st.sidebar.date_input("종료일", datetime.today())
INITIAL_CAPITAL = st.sidebar.number_input("초기 자본금 ($)", value=10000, step=1000)
MONTHLY_CONTRIBUTION = st.sidebar.number_input("매월 추가 적립금 ($)", value=2000, step=500)

# --- 전역 변수 및 공통 함수 설정 (캐시 에러 방지) ---
TICKERS = ['QQQ', 'TQQQ', 'SOXL', 'USD', 'QLD', 'SSO', 'SPY', 'SMH', 'GLD', '^VIX']

def get_v4_weights(regime, use_soxl):
    w = {t: 0.0 for t in TICKERS}
    semi = 'SOXL' if use_soxl else 'USD'
    if regime == 1: w['TQQQ'], w[semi], w['QLD'], w['SSO'], w['GLD'] = 0.30, 0.20, 0.20, 0.15, 0.10
    elif regime == 2: w['QLD'], w['SSO'], w['GLD'], w['QQQ'], w['USD'] = 0.25, 0.20, 0.20, 0.15, 0.10
    elif regime == 3: w['GLD'], w['QQQ'], w['SPY'] = 0.35, 0.20, 0.10
    elif regime == 4: w['GLD'], w['QQQ'] = 0.50, 0.10
    return w

# --- 데이터 수집 및 연산 (캐싱 적용) ---
@st.cache_data(ttl=3600)
def load_and_calculate_data(start, end, init_cap, monthly_cont):
    start_str = (start - timedelta(days=400)).strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")
    
    try:
        data = yf.download(TICKERS, start=start_str, end=end_str, progress=False, auto_adjust=True)['Close']
    except:
        data = yf.download(TICKERS, start=start_str, end=end_str, progress=False)['Close']
    
    data = data.ffill().dropna(subset=['QQQ', '^VIX'])
    
    df = pd.DataFrame(index=data.index)
    for t in data.columns: df[t] = data[t]
    
    df['QQQ_MA50'] = df['QQQ'].rolling(window=50).mean()
    df['QQQ_MA200'] = df['QQQ'].rolling(window=200).mean()
    df['QQQ_RSI'] = ta.rsi(df['QQQ'], length=14)
    
    df['SMH_MA50'] = df['SMH'].rolling(window=50).mean()
    df['SMH_3M_Ret'] = df['SMH'].pct_change(periods=63)
    df['SMH_RSI'] = ta.rsi(df['SMH'], length=14)
    
    df = df.dropna(subset=['QQQ_MA200', 'SMH_RSI'])
    df = df.loc[pd.to_datetime(start):]
    daily_returns = df[data.columns].pct_change().fillna(0)

    def get_target_regime(row):
        vix, qqq, ma200, ma50 = row['^VIX'], row['QQQ'], row['QQQ_MA200'], row['QQQ_MA50']
        if vix > 40: return 4
        if qqq < ma200: return 3
        if qqq >= ma200 and ma50 >= ma200 and vix < 25: return 1
        return 2

    df['Target_Regime'] = df.apply(get_target_regime, axis=1)

    current_regime = 3 
    pending_regime = None
    confirm_count = 0
    actual_regime_list = []
    
    for i in range(len(df)):
        new_regime = df['Target_Regime'].iloc[i]
        if new_regime > current_regime: 
            current_regime = new_regime; pending_regime = None; confirm_count = 0
        elif new_regime < current_regime: 
            if new_regime == pending_regime:
                confirm_count += 1
