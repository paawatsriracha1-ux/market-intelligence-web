import streamlit as st, plotly.express as px
from market_intelligence.services import analyze_symbol
from market_intelligence.backtest.engine import BacktestConfig,run_backtest
st.title('🧪 Backtest'); a,b,c=st.columns(3); market=a.selectbox('Market',['TH','US']); symbol=b.text_input('Symbol','SNC' if market=='TH' else 'AAPL'); period=c.selectbox('History',['2y','5y','10y','max'],index=1)
a,b,c,d=st.columns(4); fast=a.number_input('Fast EMA',5,100,20); slow=b.number_input('Slow EMA',20,300,50); rsi=c.number_input('RSI entry',20.,80.,50.); vol=d.number_input('Min volume ratio',0.,5.,1.,step=.1)
a,b,c,d=st.columns(4); risk=a.number_input('Risk %',.1,10.,1.,step=.1); rr=b.number_input('Reward/Risk',.5,10.,2.,step=.1); comm=c.number_input('Commission bps',0.,100.,15.); slip=d.number_input('Slippage bps',0.,100.,5.)
if st.button('Run backtest',type='primary'):
 try:
  df,_=analyze_symbol(symbol,market,period=period); r=run_backtest(df,BacktestConfig(fast_ema=int(fast),slow_ema=int(slow),rsi_entry=rsi,volume_ratio_min=vol,risk_pct=risk,reward_risk=rr,commission_bps=comm,slippage_bps=slip,market=market)); m=r['metrics']
  for col,(k,l) in zip(st.columns(6),[('total_return_pct','Return %'),('max_drawdown_pct','Max DD %'),('sharpe','Sharpe'),('trades','Trades'),('win_rate_pct','Win rate %'),('profit_factor','Profit factor')]): col.metric(l,f"{m.get(k,0):.2f}" if isinstance(m.get(k,0),float) else m.get(k,0))
  st.plotly_chart(px.line(r['equity'],x='Date',y='Equity',title='Equity curve'),width="stretch"); st.dataframe(r['trades'],width="stretch",hide_index=True)
 except Exception as e: st.error(str(e))
