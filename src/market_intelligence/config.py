from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    db_path: str = os.getenv("APP_DB_PATH", "data/market_intelligence.db")
    default_paper_cash: float = float(os.getenv("DEFAULT_PAPER_CASH", "1000000"))
    default_risk_pct: float = float(os.getenv("DEFAULT_RISK_PCT", "1.0"))

settings = Settings()
