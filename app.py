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
