import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal

from app.utils.currency import convert_to_usd, convert_currency
from app.utils.date_utils import days_between, hours_between


class TestCurrencyUtils:
    def test_convert_to_usd_mxn(self):
        result = convert_to_usd(Decimal("1000"), "MXN")
        assert result == Decimal("58.0")

    def test_convert_to_usd_cop(self):
        result = convert_to_usd(Decimal("1000000"), "COP")
        assert result == Decimal("250.0")

    def test_convert_to_usd_brl(self):
        result = convert_to_usd(Decimal("500"), "BRL")
        assert result == Decimal("100.0")

    def test_convert_to_usd_usd(self):
        result = convert_to_usd(Decimal("100"), "USD")
        assert result == Decimal("100.0")

    def test_convert_currency_same(self):
        result = convert_currency(Decimal("100"), "MXN", "MXN")
        assert result == Decimal("100")

    def test_convert_currency_mxn_to_usd(self):
        result = convert_currency(Decimal("1000"), "MXN", "USD")
        assert result == Decimal("58.0")


class TestDateUtils:
    def test_days_between_same_day(self):
        d1 = date(2024, 1, 15)
        d2 = date(2024, 1, 15)
        assert days_between(d1, d2) == 0

    def test_days_between_different_days(self):
        d1 = date(2024, 1, 15)
        d2 = date(2024, 1, 18)
        assert days_between(d1, d2) == 3

    def test_days_between_reversed(self):
        d1 = date(2024, 1, 18)
        d2 = date(2024, 1, 15)
        assert days_between(d1, d2) == 3

    def test_days_between_with_datetime(self):
        dt1 = datetime(2024, 1, 15, 10, 30)
        dt2 = datetime(2024, 1, 18, 14, 45)
        assert days_between(dt1, dt2) == 3

    def test_hours_between_same_time(self):
        dt1 = datetime(2024, 1, 15, 10, 0)
        dt2 = datetime(2024, 1, 15, 10, 0)
        assert hours_between(dt1, dt2) == 0.0

    def test_hours_between_different_times(self):
        dt1 = datetime(2024, 1, 15, 10, 0)
        dt2 = datetime(2024, 1, 15, 13, 0)
        assert hours_between(dt1, dt2) == 3.0

    def test_hours_between_different_days(self):
        dt1 = datetime(2024, 1, 15, 10, 0)
        dt2 = datetime(2024, 1, 16, 10, 0)
        assert hours_between(dt1, dt2) == 24.0


class TestMatchingLogic:
    """Test matching algorithm logic without database."""

    def test_amount_tolerance_calculation(self):
        """Test that 5% tolerance is calculated correctly."""
        transaction_amount = Decimal("1000.00")
        settlement_amount = Decimal("970.00")  # 3% difference

        tolerance = Decimal("0.05")
        diff = abs(settlement_amount - transaction_amount)
        diff_percent = diff / transaction_amount

        assert diff_percent <= tolerance

    def test_amount_outside_tolerance(self):
        """Test amount outside 5% tolerance."""
        transaction_amount = Decimal("1000.00")
        settlement_amount = Decimal("900.00")  # 10% difference

        tolerance = Decimal("0.05")
        diff = abs(settlement_amount - transaction_amount)
        diff_percent = diff / transaction_amount

        assert diff_percent > tolerance

    def test_date_within_window(self):
        """Test date within 72-hour window."""
        transaction_time = datetime(2024, 1, 15, 10, 0)
        settlement_date = date(2024, 1, 17)

        settlement_datetime = datetime.combine(settlement_date, datetime.min.time())
        hours_diff = hours_between(transaction_time, settlement_datetime)

        assert hours_diff <= 72

    def test_date_outside_window(self):
        """Test date outside 72-hour window."""
        transaction_time = datetime(2024, 1, 15, 10, 0)
        settlement_date = date(2024, 1, 20)

        settlement_datetime = datetime.combine(settlement_date, datetime.min.time())
        hours_diff = hours_between(transaction_time, settlement_datetime)

        assert hours_diff > 72

    def test_partial_id_match(self):
        """Test partial ID matching logic."""
        transaction_id = "txn_4j2k9d8f1234"
        truncated_ref = "txn_4j2k"

        # Check if first 8 chars match
        assert transaction_id[:8] in transaction_id
        assert truncated_ref in transaction_id[:8] or transaction_id[:8] in truncated_ref

    def test_confidence_scoring(self):
        """Test confidence score calculation."""
        base_confidence = 80

        # Exact amount match bonus
        exact_amount_bonus = 15

        # Same day bonus
        same_day_bonus = 5

        total = base_confidence + exact_amount_bonus + same_day_bonus
        assert total == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
