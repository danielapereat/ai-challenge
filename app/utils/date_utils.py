from datetime import datetime, date, timedelta


def days_between(date1: date | datetime, date2: date | datetime) -> int:
    """Calculate absolute number of days between two dates."""
    if isinstance(date1, datetime):
        date1 = date1.date()
    if isinstance(date2, datetime):
        date2 = date2.date()

    return abs((date2 - date1).days)


def hours_between(dt1: datetime, dt2: datetime) -> float:
    """Calculate absolute number of hours between two datetimes."""
    diff = abs((dt2 - dt1).total_seconds())
    return diff / 3600
