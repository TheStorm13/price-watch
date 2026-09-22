"""Marketplace-independent product snapshot entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple, Union


class Availability(str, Enum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    UNKNOWN = "unknown"


def _immutable_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True)
class ProductRef:
    marketplace: str
    external_id: str

    def __post_init__(self) -> None:
        if not self.marketplace.strip():
            raise ValueError("marketplace не должен быть пустым")
        if not self.external_id.strip():
            raise ValueError("external_id не должен быть пустым")


@dataclass(frozen=True)
class Rating:
    value: Decimal
    scale: Decimal = Decimal("5")
    reviews_count: int = 0

    def __post_init__(self) -> None:
        value = self.value if isinstance(self.value, Decimal) else Decimal(str(self.value))
        scale = self.scale if isinstance(self.scale, Decimal) else Decimal(str(self.scale))
        if scale <= 0 or value < 0 or value > scale:
            raise ValueError("Рейтинг должен находиться в пределах шкалы")
        if self.reviews_count < 0:
            raise ValueError("Количество отзывов не может быть отрицательным")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "scale", scale)


@dataclass(frozen=True)
class Seller:
    external_id: Optional[str]
    name: str
    rating: Optional[Rating] = None


@dataclass(frozen=True)
class Attribute:
    name: str
    values: Tuple[str, ...]
    group: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", tuple(self.values))
        if not self.name.strip() or not self.values:
            raise ValueError("Характеристика должна иметь имя и хотя бы одно значение")


@dataclass(frozen=True)
class ProductVariant:
    ref: ProductRef
    title: str
    url: str
    availability: Availability
    selected: bool = False
    options: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", _immutable_mapping(self.options))


@dataclass(frozen=True)
class ProductSnapshot:
    ref: ProductRef
    title: str
    url: str
    availability: Availability
    price: Optional[Union[int, float]] = None
    seller: Optional[Seller] = None
    rating: Optional[Rating] = None
    attributes: Tuple[Attribute, ...] = ()
    description: str = ""
    variants: Tuple[ProductVariant, ...] = ()
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    extensions: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("Название продукта не должно быть пустым")
        if self.collected_at.tzinfo is None:
            raise ValueError("collected_at должен содержать часовой пояс")
        if isinstance(self.price, bool) or (
            self.price is not None and self.price < 0
        ):
            raise ValueError("Цена должна быть неотрицательным числом или null")
        variants = tuple(self.variants)
        refs = [variant.ref for variant in variants]
        if len(refs) != len(set(refs)):
            raise ValueError("Варианты продукта должны быть уникальны")
        object.__setattr__(self, "attributes", tuple(self.attributes))
        object.__setattr__(self, "variants", variants)
        object.__setattr__(self, "extensions", _immutable_mapping(self.extensions))
