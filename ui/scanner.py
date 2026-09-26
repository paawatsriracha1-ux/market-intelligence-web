import streamlit as st
from market_intelligence.services import scan_symbols
st.title('🧭 Market Scanner'); market=st.selectbox('Market',['TH','US'])
default='SNC,PTT,ADVANC,CPALL,DELTA,KBANK,SCB,GULF' if market=='TH' else 'AAPL,MSFT,NVDA,AMZN,META,GOOGL,TSLA,AMD'
text=st.text_area('Symbols (comma separated)',default)
if st.button('Scan',type='primary'): st.dataframe(scan_symbols([s.strip() for s in text.split(',') if s.strip()],market),width="stretch",hide_index=True)
