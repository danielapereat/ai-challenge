from pydantic_settings import BaseSettings
from decimal import Decimal


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://reconciliation:reconciliation@localhost:5432/reconciliation"

    # Matching configuration
    AMOUNT_TOLERANCE_PERCENT: Decimal = Decimal("5.0")
    SETTLEMENT_WINDOW_HOURS: int = 72
    CHARGEBACK_WINDOW_DAYS: int = 90
    REFUND_WINDOW_DAYS: int = 30
    MIN_CONFIDENCE_FOR_AUTO_MATCH: int = 80
    CURRENCY_FX_TOLERANCE_PERCENT: Decimal = Decimal("10.0")
    ORPHAN_THRESHOLD_DAYS: int = 7

    class Config:
        env_file = ".env"


settings = Settings()


# Currency conversion rates (approximate, for demo purposes)
FX_RATES_TO_USD = {
    "USD": Decimal("1.0"),
    "MXN": Decimal("0.058"),
    "COP": Decimal("0.00025"),
    "BRL": Decimal("0.20"),
}
