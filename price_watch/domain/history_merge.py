"""Merge exported and local price changes in chronological order."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class HistoryEvent:
    observed_at: datetime
    price: Decimal | None
    availability: str
    source: str
    source_id: int

    def __post_init__(self) -> None:
        if self.availability == "out_of_stock":
            object.__setattr__(self, "price", None)


class ConflictingObservation(ValueError):
    pass


def merge_history(events: list[HistoryEvent]) -> list[HistoryEvent]:
    ordered = sorted(events, key=lambda item: (
        item.observed_at, 0 if item.source == "local" else 1, item.source_id,
    ))
    result: list[HistoryEvent] = []
    last_at: datetime | None = None
    last_at_state: tuple[Decimal | None, str] | None = None
    for event in ordered:
        state = (event.price, event.availability)
        if last_at == event.observed_at:
            if last_at_state != state:
                raise ConflictingObservation(
                    f"Разные цены или наличие для одного времени: {event.observed_at.isoformat()}"
                )
            continue
        last_at = event.observed_at
        last_at_state = state
        if result and (result[-1].price, result[-1].availability) == state:
            continue
        result.append(event)
    return result
