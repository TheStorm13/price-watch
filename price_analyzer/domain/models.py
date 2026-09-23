"""Entities owned by the price analyzer, independently of persistence."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional


@dataclass(frozen=True)
class MarketplaceCard:
    id: int
    marketplace: str
    external_id: str
    title: Optional[str]
    url: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class PriceHistoryPoint:
    id: int
    card_id: int
    collection_run_id: Optional[int]
    price: Optional[Decimal]
    availability: str
    observed_at: datetime


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
class CardOverview:
    card: MarketplaceCard
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
    target_card_ids: Optional[tuple[int, ...]] = None
    errors: tuple[dict[str, Any], ...] = ()
