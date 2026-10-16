from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from ..domain.models import CardOverview, CollectionRun, Deal, PriceHistoryPoint, PriceStatistics


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CardCreate(ApiModel):
    marketplace: str
    external_id: str
    title: str | None = None
    url: HttpUrl | None = None

    @field_validator("marketplace")
    @classmethod
    def validate_marketplace(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized != "ozon":
            raise ValueError("В этой версии доступен только Ozon")
        return normalized

    @field_validator("external_id")
    @classmethod
    def validate_external_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.isascii() or not normalized.isdigit():
            raise ValueError("Ozon ID должен состоять из цифр")
        return normalized


class CardUpdate(ApiModel):
    title: str | None = None
    url: HttpUrl | None = None
    is_active: bool | None = None
    is_archived: bool | None = None


class TransferHistoryPoint(ApiModel):
    price: Decimal | None
    availability: Literal["in_stock", "out_of_stock", "unknown"]
    observed_at: datetime

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or value < 0 or value.as_tuple().exponent < -2 or value >= 10**12):
            raise ValueError("Некорректная цена в истории")
        return value

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Время наблюдения должно содержать часовой пояс")
        return value


class TransferCard(ApiModel):
    marketplace: str
    external_id: str
    title: str | None
    url: str | None
    image_url: str | None = None
    is_active: bool
    is_archived: bool = False
    created_at: datetime
    history: list[TransferHistoryPoint]

    @field_validator("marketplace", "external_id")
    @classmethod
    def validate_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Маркетплейс и артикул обязательны")
        return normalized

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Дата добавления должна содержать часовой пояс")
        return value


class TransferDocument(ApiModel):
    version: Literal[1]
    cards: list[TransferCard]

    @field_validator("cards")
    @classmethod
    def validate_cards(cls, cards: list[TransferCard]) -> list[TransferCard]:
        keys = [(card.marketplace.lower(), card.external_id) for card in cards]
        if len(keys) != len(set(keys)):
            raise ValueError("В файле есть повторяющиеся карточки")
        return cards


class ImportSummary(ApiModel):
    cards_added: int = 0
    cards_merged: int = 0
    observations_added: int = 0
    observations_removed: int = 0
    observations_skipped: int = 0


class CardResponse(ApiModel):
    id: int
    marketplace: str
    external_id: str
    title: str | None
    url: str | None
    image_url: str | None
    is_active: bool
    is_archived: bool
    current_price: float | None
    current_availability: str | None
    last_observed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_overview(cls, overview: CardOverview) -> "CardResponse":
        card = overview.card
        return cls(
            id=card.id,
            marketplace=card.marketplace,
            external_id=card.external_id,
            title=card.title,
            url=card.url,
            image_url=card.image_url,
            is_active=card.is_active,
            is_archived=card.is_archived,
            current_price=overview.current_price,
            current_availability=overview.current_availability,
            last_observed_at=overview.last_observed_at,
            created_at=card.created_at,
            updated_at=card.updated_at,
        )


class HistoryPointResponse(ApiModel):
    id: int
    card_id: int
    collection_run_id: int | None
    price: float | None
    availability: str
    observed_at: datetime

    @classmethod
    def from_domain(cls, point: PriceHistoryPoint) -> "HistoryPointResponse":
        return cls(**point.__dict__)


class StatisticsResponse(ApiModel):
    card_id: int
    days: int
    average_price: float | None
    minimum_price: float | None
    maximum_price: float | None
    observations_count: int
    observed_days: int

    @classmethod
    def from_domain(cls, statistics: PriceStatistics) -> "StatisticsResponse":
        return cls(**statistics.__dict__)


class HistoryResponse(ApiModel):
    card: CardResponse
    statistics: StatisticsResponse
    history: list[HistoryPointResponse]
    page: int
    page_size: int
    total_count: int


class ChartResponse(ApiModel):
    points: list[HistoryPointResponse]


class DealResponse(ApiModel):
    card: CardResponse
    average_price: float
    savings: float
    baseline_days: int
    last_collection_run_id: int | None

    @classmethod
    def from_domain(cls, deal: Deal) -> "DealResponse":
        return cls(card=CardResponse.from_overview(deal.card), average_price=deal.average_price,
                   savings=deal.savings, baseline_days=deal.baseline_days,
                   last_collection_run_id=deal.last_collection_run_id)


class RunCurrentResponse(ApiModel):
    card_id: int
    marketplace: str
    external_id: str


class ChallengeResponse(ApiModel):
    type: str
    message: str


class RunResponse(ApiModel):
    id: int
    status: str
    total_count: int
    success_count: int
    failure_count: int
    current: RunCurrentResponse | None
    challenge: ChallengeResponse | None
    started_at: datetime
    finished_at: datetime | None
    errors: list[dict] | None = None
    retry_of_run_id: int | None = None

    @classmethod
    def from_domain(cls, run: CollectionRun, include_errors: bool = True) -> "RunResponse":
        current = None
        if run.current_card_id and run.current_marketplace and run.current_external_id:
            current = RunCurrentResponse(
                card_id=run.current_card_id,
                marketplace=run.current_marketplace,
                external_id=run.current_external_id,
            )
        challenge = None
        if run.challenge_type and run.challenge_message:
            challenge = ChallengeResponse(type=run.challenge_type, message=run.challenge_message)
        return cls(
            id=run.id,
            status=run.status,
            total_count=run.total_count,
            success_count=run.success_count,
            failure_count=run.failure_count,
            current=current,
            challenge=challenge,
            started_at=run.started_at,
            finished_at=run.finished_at,
            errors=list(run.errors) if include_errors else None,
            retry_of_run_id=run.retry_of_run_id,
        )


class RunCreate(ApiModel):
    card_id: int | None = Field(default=None, ge=1)
