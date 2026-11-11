from datetime import datetime
from decimal import Decimal
from typing import Literal

from marketplace_connector.application.card_identity import validate_card_identity, validate_variant_identity

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, field_serializer, model_validator

from ..domain.models import TrackedCardOverview, CollectionRun, PriceHistoryPoint, PriceStatistics


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    @field_serializer("price", "current_price", "minimum_price", "maximum_price",
                      "average_price", "savings", when_used="json", check_fields=False)
    def serialize_decimal(self, value, info):
        if isinstance(value, Decimal):
            if info.field_name in {"price", "current_price", "minimum_price", "maximum_price"}:
                return format(value, ".2f")
            return format(value, "f").rstrip("0").rstrip(".") if "." in format(value, "f") else format(value, "f")
        return value


def normalize_tags(tags: list[str]) -> list[str]:
    normalized = [tag.strip() for tag in tags]
    if any(not tag or len(tag) > 40 for tag in normalized):
        raise ValueError("Тег должен содержать от 1 до 40 символов")
    if len({tag.casefold() for tag in normalized}) != len(normalized):
        raise ValueError("Теги не должны повторяться")
    return normalized


class CardCreate(ApiModel):
    marketplace: str
    external_id: str
    title: str | None = None
    url: HttpUrl | None = None
    tags: list[str] = Field(default_factory=list, max_length=2)

    _normalize_tags = field_validator("tags")(normalize_tags)

    @field_validator("marketplace")
    @classmethod
    def validate_marketplace(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"ozon", "wildberries", "aliexpress", "yandex-market"}:
            raise ValueError("Неизвестный маркетплейс")
        return normalized

    @model_validator(mode="after")
    def validate_ref(self):
        if self.marketplace not in ("aliexpress", "wildberries") and (not self.external_id.strip().isascii() or not self.external_id.strip().isdigit()):
            raise ValueError("ID карточки должен состоять из цифр")
        self.external_id, url = validate_card_identity(self.marketplace, self.external_id, str(self.url) if self.url else None)
        if url:
            self.url = HttpUrl(url)
        return self


class CardUpdate(ApiModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")
    title: str | None = None
    url: HttpUrl | None = None
    deals_enabled: bool | None = None
    primary_variant_id: int | None = Field(default=None, ge=1)
    group_id: int | None = Field(default=None, ge=1)
    tags: list[str] | None = Field(default=None, max_length=2)

    _normalize_tags = field_validator("tags")(normalize_tags)


class GroupInput(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    card_ids: list[int] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    _normalize_tags = field_validator("tags")(normalize_tags)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Укажите название группы")
        return value


class TransferHistoryPoint(ApiModel):
    price: Decimal | None
    availability: Literal["in_stock", "out_of_stock", "unknown"]
    observed_at: datetime

    @field_validator("price", mode="before", json_schema_input_type=str | None)
    @classmethod
    def require_decimal_string(cls, value):
        if value is not None and not isinstance(value, (str, Decimal)):
            raise ValueError("Цена должна быть десятичной строкой или null")
        return value

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


class VariantTrackingUpdate(ApiModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")
    enabled: bool
    variant_id: int | None = Field(default=None, ge=1)


class TransferVariant(ApiModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")
    external_id: str
    tracking_enabled: bool = False
    title: str = ""
    url: str | None = None
    image_url: str | None = None
    product_title: str | None = None
    options: dict[str, str] = Field(default_factory=dict)
    updated_at: datetime | None = None
    history: list[TransferHistoryPoint] = Field(default_factory=list)


class TransferCard(ApiModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")
    marketplace: str
    external_id: str
    title: str | None
    url: str | None
    image_url: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=2)
    _normalize_tags = field_validator("tags")(normalize_tags)
    deals_enabled: bool
    created_at: datetime
    primary_external_id: str
    variants: list[TransferVariant] = Field(min_length=1)

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


class TransferGroupMember(ApiModel):
    marketplace: str
    external_id: str


class TransferGroup(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    cards: list[TransferGroupMember]
    tags: list[str] = Field(default_factory=list)
    _normalize_tags = field_validator("tags")(normalize_tags)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Название группы не может быть пустым")
        return value


class TransferDocument(ApiModel):
    version: Literal[3]
    cards: list[TransferCard]
    groups: list[TransferGroup] = Field(default_factory=list)

    @field_validator("cards")
    @classmethod
    def validate_cards(cls, cards: list[TransferCard]) -> list[TransferCard]:
        keys = [(card.marketplace.lower(), card.external_id) for card in cards]
        if len(keys) != len(set(keys)):
            raise ValueError("В файле есть повторяющиеся карточки")
        return cards

    @model_validator(mode="after")
    def validate_groups(self):
        available = {(card.marketplace.lower(), card.external_id) for card in self.cards}
        assigned = set()
        for group in self.groups:
            for member in group.cards:
                key = (member.marketplace.lower(), member.external_id)
                if key not in available:
                    raise ValueError("Группа содержит карточку вне файла")
                if key in assigned:
                    raise ValueError("Карточка указана в нескольких группах")
                assigned.add(key)
        return self


class ImportDocument(TransferDocument):
    """Only the explicit product/variant transfer v3 schema is accepted."""

    @field_validator("cards")
    @classmethod
    def validate_identities(cls, cards: list[TransferCard]) -> list[TransferCard]:
        ozon_members = set()
        for card in cards:
            refs = set()
            for variant in card.variants:
                variant.external_id, variant.url = validate_variant_identity(card.marketplace, card.external_id, variant.external_id, variant.url)
                if variant.external_id in refs:
                    raise ValueError("Вариант повторяется или принадлежит другому товару")
                if card.marketplace.lower() == 'ozon':
                    if variant.external_id in ozon_members:
                        raise ValueError('Вариант Ozon указан в нескольких карточках')
                    ozon_members.add(variant.external_id)
                refs.add(variant.external_id)
            if card.primary_external_id not in refs:
                raise ValueError("Главный вариант отсутствует в товаре")
            if card.marketplace.lower() == 'ozon' and card.external_id not in refs:
                raise ValueError('Исходный SKU Ozon отсутствует в товаре')
        return cards


class ImportSummary(ApiModel):
    cards_added: int = 0
    cards_merged: int = 0
    observations_added: int = 0
    observations_removed: int = 0
    observations_skipped: int = 0
    groups_added: int = 0


class CardResponse(ApiModel):
    id: int
    marketplace: str
    external_id: str
    title: str | None
    url: str | None
    image_url: str | None
    options: dict[str, str] = Field(default_factory=dict)
    tags: list[str]
    deals_enabled: bool
    group_id: int | None = None
    primary_variant_id: int | None = None
    last_collected_at: datetime | None = None
    current_price: Decimal | None
    minimum_price: Decimal | None = None
    average_price: Decimal | None = None
    current_availability: str | None
    last_observed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_overview(
        cls, overview: TrackedCardOverview, *, minimum_price=None, average_price=None
    ) -> "CardResponse":
        card = overview.card
        return cls(
            id=card.id,
            primary_variant_id=card.primary_variant_id,
            last_collected_at=card.last_collected_at,
            marketplace=card.ref.marketplace,
            external_id=card.ref.external_id,
            title=card.title,
            url=card.url,
            image_url=card.image_url,
            options=card.options,
            tags=list(card.tags),
            deals_enabled=card.deals_enabled,
            group_id=card.group_id,
            current_price=overview.current_price,
            minimum_price=minimum_price,
            average_price=average_price,
            current_availability=overview.current_availability,
            last_observed_at=overview.last_observed_at,
            created_at=card.created_at,
            updated_at=card.updated_at,
        )


class VariantResponse(ApiModel):
    tracking_enabled: bool
    is_tracked: bool
    id: int
    card_id: int
    external_id: str
    title: str
    url: str | None
    image_url: str | None
    product_title: str | None
    options: dict[str, str]
    current_price: Decimal | None
    current_availability: str | None
    last_observed_at: datetime | None
    updated_at: datetime | None


class GroupResponse(ApiModel):
    id: int
    name: str
    tags: list[str]
    card_ids: list[int]
    current_price: Decimal | None
    minimum_price: Decimal | None
    representative_card_id: int | None
    representative_card: CardResponse | None
    savings: Decimal | None
    baseline_days: int
    is_deal: bool
    has_member_deals: bool


class HistoryPointResponse(ApiModel):
    variant_id: int | None = None
    id: int
    card_id: int
    collection_run_id: int | None
    price: Decimal | None
    availability: str
    observed_at: datetime

    @classmethod
    def from_domain(cls, point: PriceHistoryPoint) -> "HistoryPointResponse":
        return cls(**point.__dict__)


class StatisticsResponse(ApiModel):
    card_id: int
    window_start: datetime
    window_end: datetime
    average_price: Decimal | None
    minimum_price: Decimal | None
    maximum_price: Decimal | None
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
    average_price: Decimal
    savings: Decimal
    baseline_days: int
    last_collection_run_id: int | None



class CatalogResponse(ApiModel):
    cards: list[CardResponse]
    groups: list[GroupResponse]
    deals: list[DealResponse]


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
    retryable_count: int = 0
    retry_scope_incomplete: bool = False
    diagnostics_status: str = 'complete'

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
            diagnostics_status=run.diagnostics_status,
            retry_of_run_id=run.retry_of_run_id,
            retryable_count=run.retryable_count,
            retry_scope_incomplete=not run.targets_complete,
        )


class RunCreate(ApiModel):
    card_id: int | None = Field(default=None, ge=1)
