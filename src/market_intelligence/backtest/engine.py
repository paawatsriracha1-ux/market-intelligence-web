from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
import pandas as pd

@dataclass
class BacktestConfig:
    initial_cash: float = 1_000_000
    fast_ema: int = 20
    slow_ema: int = 50
    rsi_entry: float = 50
    rsi_exit: float = 45
    volume_ratio_min: float = 1.0
    risk_pct: float = 1.0
    max_alloc_pct: float = 20.0
    atr_stop_multiple: float = 2.0
    reward_risk: float = 2.0
    commission_bps: float = 15.0
    slippage_bps: float = 5.0
    market: str = "US"

def _metrics(equity, trades, initial):
    if equity.empty: return {}
    rets = equity.pct_change().replace([np.inf,-np.inf],np.nan).dropna()
    sharpe = rets.mean()/rets.std()*math.sqrt(252) if len(rets)>2 and rets.std()>0 else 0.0
    dd = equity/equity.cummax()-1
    wins = trades[trades["pnl"]>0] if not trades.empty else trades
    losses = trades[trades["pnl"]<0] if not trades.empty else trades
    gross_win = wins["pnl"].sum() if len(wins) else 0.0
    gross_loss = abs(losses["pnl"].sum()) if len(losses) else 0.0
    return {
        "final_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1]/initial-1)*100),
        "max_drawdown_pct": float(dd.min()*100),
        "sharpe": float(sharpe), "trades": int(len(trades)),
        "win_rate_pct": float((len(wins)/len(trades)*100) if len(trades) else 0),
        "profit_factor": float(gross_win/gross_loss if gross_loss>0 else (999.0 if gross_win>0 else 0.0))}

def run_backtest(df: pd.DataFrame, cfg: BacktestConfig | None = None):
    cfg = cfg or BacktestConfig()
    d = df.copy().sort_values("Date").reset_index(drop=True)
    if len(d) < max(cfg.slow_ema,60): raise ValueError("Not enough data for backtest")
    d["FAST"], d["SLOW"] = d["Close"].ewm(span=cfg.fast_ema,adjust=False).mean(), d["Close"].ewm(span=cfg.slow_ema,adjust=False).mean()
    cash, qty, entry, stop, target, entry_fee, entry_date = cfg.initial_cash,0,0.,0.,0.,0.,None
    trades, equity_rows = [], []
    for i in range(1,len(d)):
        prev, bar = d.iloc[i-1], d.iloc[i]
        if qty == 0:
            enter = prev["FAST"]>prev["SLOW"] and prev["RSI14"]>=cfg.rsi_entry and (pd.isna(prev["VOL_RATIO"]) or prev["VOL_RATIO"]>=cfg.volume_ratio_min)
            if enter:
                px = float(bar["Open"])*(1+cfg.slippage_bps/10000)
                atr = max(float(prev["ATR14"]),px*.005)
                stop_candidate = px-cfg.atr_stop_multiple*atr
                risk_ps = max(px-stop_candidate,px*.001)
                q = max(0,min(math.floor((cash*cfg.risk_pct/100)/risk_ps),math.floor((cash*cfg.max_alloc_pct/100)/px)))
                if cfg.market.upper()=="TH": q=(q//100)*100
                gross, fee = q*px, q*px*cfg.commission_bps/10000
                if q>0 and gross+fee<=cash:
                    qty,entry,stop,target,entry_date,entry_fee = q,px,stop_candidate,px+cfg.reward_risk*(px-stop_candidate),bar["Date"],fee
                    cash -= gross+fee
        else:
            reason=exit_px=None
            if float(bar["Low"])<=stop: reason,exit_px="STOP",stop*(1-cfg.slippage_bps/10000)
            elif float(bar["High"])>=target: reason,exit_px="TARGET",target*(1-cfg.slippage_bps/10000)
            elif prev["FAST"]<prev["SLOW"] or prev["RSI14"]<cfg.rsi_exit: reason,exit_px="RULE",float(bar["Open"])*(1-cfg.slippage_bps/10000)
            if reason:
                fee=qty*exit_px*cfg.commission_bps/10000
                cash += qty*exit_px-fee
                trades.append({"entry_date":entry_date,"exit_date":bar["Date"],"entry":entry,"exit":exit_px,"qty":qty,"pnl":(exit_px-entry)*qty-entry_fee-fee,"reason":reason})
                qty,entry,stop,target=0,0.,0.,0.
        equity_rows.append({"Date":bar["Date"],"Equity":cash+qty*float(bar["Close"])})
    if qty>0:
        bar=d.iloc[-1]; exit_px=float(bar["Close"])*(1-cfg.slippage_bps/10000); fee=qty*exit_px*cfg.commission_bps/10000
        cash += qty*exit_px-fee
        trades.append({"entry_date":entry_date,"exit_date":bar["Date"],"entry":entry,"exit":exit_px,"qty":qty,"pnl":(exit_px-entry)*qty-entry_fee-fee,"reason":"END"})
        if equity_rows: equity_rows[-1]["Equity"]=cash
    eq, tr = pd.DataFrame(equity_rows), pd.DataFrame(trades)
    return {"equity":eq,"trades":tr,"metrics":_metrics(eq["Equity"] if not eq.empty else pd.Series(dtype=float),tr,cfg.initial_cash)}
