import pandas as pd
from ..storage import Storage
from ..services import analyze_symbol

def mark_to_market(storage=None):
    storage=storage or Storage(); rows=[]
    for p in storage.get_portfolio():
        try:
            df,_=analyze_symbol(p["symbol"],p["market"],period="1mo"); last=float(df.iloc[-1]["Close"])
            value,cost=p["qty"]*last,p["qty"]*p["avg_price"]
            rows.append({**p,"last":last,"market_value":value,"cost":cost,"unrealized_pnl":value-cost,"return_pct":(last/p["avg_price"]-1)*100})
        except Exception as exc: rows.append({**p,"error":str(exc)})
    return pd.DataFrame(rows)
