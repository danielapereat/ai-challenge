from decimal import Decimal
from app.config import FX_RATES_TO_USD


def convert_to_usd(amount: Decimal, currency: str) -> Decimal:
    """Convert an amount to USD using approximate FX rates."""
    rate = FX_RATES_TO_USD.get(currency.upper(), Decimal("1.0"))
    return amount * rate


def convert_currency(amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
    """Convert between currencies using USD as intermediate."""
    if from_currency == to_currency:
        return amount

    # Convert to USD first
    usd_amount = convert_to_usd(amount, from_currency)

    # Convert from USD to target currency
    to_rate = FX_RATES_TO_USD.get(to_currency.upper(), Decimal("1.0"))
    if to_rate == Decimal("0"):
        return usd_amount

    return usd_amount / to_rate
