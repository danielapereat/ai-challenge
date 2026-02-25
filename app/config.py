from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from decimal import Decimal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://reconciliation:reconciliation@localhost:5432/reconciliation",
        description="Database connection URL"
    )

    # Matching configuration
    AMOUNT_TOLERANCE_PERCENT: Decimal = Field(default=Decimal("5.0"), gt=0, le=100)
    SETTLEMENT_WINDOW_HOURS: int = Field(default=72, gt=0)
    CHARGEBACK_WINDOW_DAYS: int = Field(default=90, gt=0)
    REFUND_WINDOW_DAYS: int = Field(default=30, gt=0)
    MIN_CONFIDENCE_FOR_AUTO_MATCH: int = Field(default=80, ge=0, le=100)
    CURRENCY_FX_TOLERANCE_PERCENT: Decimal = Field(default=Decimal("10.0"), gt=0, le=100)
    ORPHAN_THRESHOLD_DAYS: int = Field(default=7, gt=0)

    # AI Analysis Configuration
    ANTHROPIC_API_KEY: str = Field(default="", description="Anthropic API key")
    CLAUDE_MODEL: str = Field(default="claude-sonnet-4-20250514", description="Claude model version")
    AI_ANALYSIS_ENABLED: bool = Field(default=True, description="Enable AI analysis features")
    AI_MAX_TOKENS: int = Field(default=1024, ge=1, le=4096)
    AI_TEMPERATURE: float = Field(default=0.3, ge=0.0, le=2.0, description="Temperature for AI responses")


settings = Settings()


# Currency conversion rates (approximate, for demo purposes)
FX_RATES_TO_USD = {
    "USD": Decimal("1.0"),
    "MXN": Decimal("0.058"),
    "COP": Decimal("0.00025"),
    "BRL": Decimal("0.20"),
}
