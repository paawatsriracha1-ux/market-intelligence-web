import streamlit as st, pandas as pd
from market_intelligence.services import analyze_symbol
from market_intelligence.backtest.engine import BacktestConfig,run_backtest
st.title('⚙️ Strategy Lab'); market=st.selectbox('Market',['TH','US']); symbol=st.text_input('Symbol','SNC' if market=='TH' else 'AAPL'); period=st.selectbox('History',['5y','10y','max'])
fasts=st.multiselect('Fast EMA candidates',[5,10,15,20,25,30,40,50],default=[10,20]); slows=st.multiselect('Slow EMA candidates',[30,40,50,75,100,150,200],default=[50,100])
if st.button('Run Strategy Lab',type='primary'):
 try:
  df,_=analyze_symbol(symbol,market,period=period); rows=[]
  for f in fasts:
   for s in slows:
    if f<s: rows.append({'fast':f,'slow':s,**run_backtest(df,BacktestConfig(fast_ema=f,slow_ema=s,market=market))['metrics']})
  out=pd.DataFrame(rows); st.dataframe(out.sort_values(['sharpe','total_return_pct'],ascending=False) if not out.empty else out,width="stretch",hide_index=True)
 except Exception as e: st.error(str(e))
