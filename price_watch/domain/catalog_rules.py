"""Catalog decisions over prepared values, independent of storage and transport."""
from decimal import Decimal
from typing import Iterable


def deal_savings(*, enabled: bool, price: Decimal | None, availability: str | None,
                 average: Decimal | None) -> Decimal | None:
    if (enabled and availability == 'in_stock' and price is not None
            and average is not None and price < average):
        return average - price
    return None


def representative_id(prices: Iterable[tuple[int, Decimal | None]]) -> int | None:
    candidate = min(prices, key=lambda item: (
        item[1] is None, item[1] if item[1] is not None else Decimal(0), item[0]), default=None)
    return candidate[0] if candidate is not None else None
