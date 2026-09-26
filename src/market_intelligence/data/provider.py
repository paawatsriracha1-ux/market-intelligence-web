from __future__ import annotations
import threading
import time
import pandas as pd

def normalize_symbol(symbol: str, market: str) -> str:
    s = symbol.strip().upper()
    if market.strip().upper() == "TH" and not s.endswith(".BK"):
        s += ".BK"
    return s

class YFinanceProvider:
    """Yahoo Finance market-data provider with a small in-process TTL cache.

    The cache reduces repeated network calls caused by Streamlit reruns.
    """
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = int(ttl_seconds)
        self._cache: dict[tuple, tuple[float, pd.DataFrame]] = {}
        self._lock = threading.Lock()

    def _cache_get(self, key):
        now = time.time()
        with self._lock:
            item = self._cache.get(key)
            if not item:
                return None
            created, frame = item
            if now - created > self.ttl_seconds:
                self._cache.pop(key, None)
                return None
            return frame.copy(deep=True)

    def _cache_put(self, key, frame):
        with self._lock:
            self._cache[key] = (time.time(), frame.copy(deep=True))

    def clear_cache(self):
        with self._lock:
            self._cache.clear()

    def fetch(self, symbol, market="US", period="2y", interval="1d") -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError("yfinance is not installed. Run pip install -r requirements.txt") from exc

        ticker = normalize_symbol(symbol, market)
        key = (ticker, str(period), str(interval))
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        try:
            df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
        except Exception as exc:
            raise RuntimeError(f"Market-data request failed for {ticker}: {exc}") from exc

        if df is None or df.empty:
            raise ValueError(f"No market data returned for {ticker}")
        df = df.reset_index()
        date_col = "Datetime" if "Datetime" in df.columns else "Date"
        df = df.rename(columns={date_col: "Date"})
        required = ["Date", "Open", "High", "Low", "Close", "Volume"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing market-data columns: {missing}")
        out = df[required].copy()
        out["Date"] = pd.to_datetime(out["Date"], utc=True, errors="coerce").dt.tz_convert(None)
        for c in required[1:]:
            out[c] = pd.to_numeric(out[c], errors="coerce")
        out = out.dropna(subset=required[:5]).sort_values("Date").reset_index(drop=True)
        if out.empty:
            raise ValueError(f"Market data for {ticker} became empty after validation")
        self._cache_put(key, out)
        return out.copy(deep=True)
