"""Materialized catalog data and projections, without ORM or HTTP models."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TypedDict

from ..domain.models import TrackedCardOverview


@dataclass(frozen=True)
class CardMetrics:
    minimum_price: Decimal | None
    average_price: Decimal | None
    baseline_days: int


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


class CatalogCard(TypedDict):
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
    cards: list[CatalogCard]
    groups: list[CatalogGroup]
    deals: list[CatalogDeal]
