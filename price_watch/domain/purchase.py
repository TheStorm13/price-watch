"""Personal purchase conditions; independent from factual savings/deal selection."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
import re


@dataclass(frozen=True)
class PurchaseSettings:
    small_range_tolerance: Decimal | None = None
    historical_savings_share: Decimal | None = None
    target_notifications_enabled: bool = False
    instance_id: str = ""


def validate_money(value, *, allow_zero=False):
    if value is None:
        return None
    if not isinstance(value, (str, Decimal)):
        raise ValueError("Укажите сумму десятичной строкой")
    if isinstance(value, str) and not re.fullmatch(r'[0-9]+(?:\.[0-9]{1,2})?', value):
        raise ValueError('Укажите сумму десятичной строкой с точностью до копеек')
    result = Decimal(value)
    if (not result.is_finite() or result < 0 or (not allow_zero and result == 0)
            or result >= 10**12 or result.as_tuple().exponent < -2):
        raise ValueError("Сумма должна быть положительной, меньше 1 трлн, с точностью до копеек")
    return result


def assess_purchase(*, evaluated_at: datetime, history_started_at: datetime | None,
                    price: Decimal | None, availability: str | None,
                    minimum: Decimal | None, maximum: Decimal | None,
                    average: Decimal | None, target: Decimal | None,
                    settings: PurchaseSettings) -> dict:
    eligible = history_started_at is not None and evaluated_at - history_started_at > timedelta(days=30)
    matches = []
    threshold = None
    with localcontext() as ctx:
        ctx.prec = 60
        if average is not None and minimum is not None and average > minimum and settings.historical_savings_share is not None:
            threshold = average - settings.historical_savings_share / 100 * (average - minimum)
        if availability == 'in_stock' and price is not None:
            if (eligible and settings.small_range_tolerance is not None and minimum is not None
                    and maximum is not None and maximum - minimum <= settings.small_range_tolerance):
                matches.append('small_range')
            if target is not None and price <= target:
                matches.append('target_price')
            if eligible and threshold is not None and price <= threshold:
                matches.append('historical_savings_share')
    return dict(evaluated_at=evaluated_at, history_started_at=history_started_at,
                history_eligible=eligible, is_match=bool(matches), matches=matches,
                current_price=price, minimum_price=minimum, maximum_price=maximum,
                average_price=average, target_price=target,
                small_range_tolerance=settings.small_range_tolerance,
                historical_savings_share=settings.historical_savings_share,
                threshold=threshold)
