"""Calendar window shared by all price metrics; no observation writes."""
from calendar import monthrange
from datetime import datetime, timezone


def price_window(as_of: datetime | None = None) -> tuple[datetime, datetime]:
    end = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
    year = end.year - 2
    start = end.replace(year=year, day=min(end.day, monthrange(year, end.month)[1]))
    return start, end
