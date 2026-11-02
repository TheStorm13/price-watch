"""Entities owned by the price-watch, independently of persistence."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from marketplace_connector.domain.models import ProductRef


@dataclass(frozen=True)
class TrackedCard:
    id: int
    ref: ProductRef
    title: Optional[str]
    url: Optional[str]
    deals_enabled: bool
    created_at: datetime
    updated_at: datetime
    image_url: Optional[str] = None
    group_id: Optional[int] = None
    tags: tuple[str, ...] = ()
    variant_id: int | None = None
    primary_variant_id: int | None = None
    last_collected_at: datetime | None = None


@dataclass(frozen=True)
class PriceHistoryPoint:
    id: int
    card_id: int
    collection_run_id: Optional[int]
    price: Optional[Decimal]
    availability: str
    observed_at: datetime
    variant_id: int | None = None


@dataclass(frozen=True)
class PriceStatistics:
    card_id: int
    days: int
    average_price: Optional[Decimal]
    minimum_price: Optional[Decimal]
    maximum_price: Optional[Decimal]
    observations_count: int
    observed_days: int


@dataclass(frozen=True)
class TrackedCardOverview:
    card: TrackedCard
    current_price: Optional[Decimal]
    current_availability: Optional[str]
    last_observed_at: Optional[datetime]


@dataclass(frozen=True)
class CollectionSummary:
    run_id: int
    status: str
    total_count: int
    success_count: int
    failure_count: int


@dataclass(frozen=True)
class CollectionRun:
    id: int
    status: str
    total_count: int
    success_count: int
    failure_count: int
    requested_card_id: Optional[int]
    current_card_id: Optional[int]
    current_marketplace: Optional[str]
    current_external_id: Optional[str]
    challenge_type: Optional[str]
    challenge_message: Optional[str]
    started_at: datetime
    finished_at: Optional[datetime]
    errors: tuple[dict[str, Any], ...] = ()
    retry_of_run_id: Optional[int] = None
    owner_token: Optional[str] = None
    targets_complete: bool = True
    retryable_count: int = 0
    diagnostics_status: str = 'complete'

    @property
    def lease(self) -> "RunLease":
        if self.owner_token is None:
            raise LeaseLost(f"Запуск {self.id} не принадлежит исполнителю")
        return RunLease(self.id, self.owner_token)


@dataclass(frozen=True)
class RunLease:
    run_id: int
    owner_token: str


class LeaseLost(RuntimeError):
    """The run is no longer active or belongs to another execution attempt."""
