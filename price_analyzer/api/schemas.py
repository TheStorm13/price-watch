from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from ..domain.models import CardOverview, CollectionRun, PriceHistoryPoint, PriceStatistics


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


class CardResponse(ApiModel):
    id: int
    marketplace: str
    external_id: str
    title: str | None
    url: str | None
    is_active: bool
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
            is_active=card.is_active,
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
        )


class RunCreate(ApiModel):
    card_id: int | None = Field(default=None, ge=1)
