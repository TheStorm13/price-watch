"""Normalized entities returned by the article parser."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Seller:
    id: str = ""
    name: str = ""
    rating: Optional[float] = None


@dataclass(frozen=True)
class ProductVariant:
    article: str
    name: str = ""
    option: str = ""
    url: str = ""
    available: bool = False
    price: Optional[int] = None
    original_price: Optional[int] = None
    selected: bool = False


@dataclass(frozen=True)
class ProductCard:
    article: str
    name: str = ""
    available: bool = False
    card_price: Optional[int] = None
    url: str = ""
    rating: Optional[float] = None
    reviews_count: int = 0
    seller: Seller = field(default_factory=Seller)
    characteristics: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    variants: List[ProductVariant] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
