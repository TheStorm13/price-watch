"""Materialized catalog data and projections, without ORM or HTTP models."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import TypedDict

from ..domain.models import TrackedCardOverview
from ..domain.purchase import PurchaseSettings


@dataclass(frozen=True)
class CardMetrics:
    minimum_price: Decimal | None
    average_price: Decimal | None
    baseline_days: int
    maximum_price: Decimal | None = None
    history_started_at: datetime | None = None


@dataclass(frozen=True)
class CatalogCardInput:
    overview: TrackedCardOverview
    metrics: CardMetrics
    last_collection_run_id: int | None


@dataclass(frozen=True)
class GroupMetadata:
    id: int
    name: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class CatalogInputs:
    cards: tuple[CatalogCardInput, ...]
    groups: tuple[GroupMetadata, ...]
    settings: PurchaseSettings = field(default_factory=PurchaseSettings)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CatalogCard(TypedDict):
    target_price: Decimal | None
    purchase_assessment: dict
    last_collection_run_id: int | None
    primary_variant_id: int | None
    last_collected_at: datetime | None
    id: int
    marketplace: str
    external_id: str
    title: str | None
    url: str | None
    image_url: str | None
    deals_enabled: bool
    group_id: int | None
    tags: tuple[str, ...]
    created_at: datetime
    updated_at: datetime
    current_price: Decimal | None
    current_availability: str | None
    last_observed_at: datetime | None
    minimum_price: Decimal | None
    average_price: Decimal | None


class CatalogDeal(TypedDict):
    card: CatalogCard
    average_price: Decimal
    savings: Decimal
    baseline_days: int
    last_collection_run_id: int | None


class CatalogGroup(TypedDict):
    id: int
    name: str
    tags: list[str]
    card_ids: list[int]
    representative_card_id: int | None
    representative_card: CatalogCard | None
    current_price: Decimal | None
    minimum_price: Decimal | None
    savings: Decimal | None
    baseline_days: int
    is_deal: bool
    has_member_deals: bool


class CatalogSnapshot(TypedDict):
    instance_id: str
    cards: list[CatalogCard]
    groups: list[CatalogGroup]
    deals: list[CatalogDeal]
