"""Storefront article with optional exact size, safe for the WB runtime."""
from dataclasses import dataclass
import re
from urllib.parse import parse_qs, urlsplit

from ...domain.errors import InvalidProductId

MAX_SAFE_INTEGER = 2**53 - 1


@dataclass(frozen=True)
class WildberriesRef:
    nm_id: str
    option_id: str | None = None

    def __post_init__(self):
        for value in (self.nm_id,) + ((self.option_id,) if self.option_id is not None else ()):
            if (not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*", value)
                    or len(value) > 16 or int(value) > MAX_SAFE_INTEGER):
                raise InvalidProductId("WB: ID должен быть положительным числом ASCII в безопасном диапазоне")

    @property
    def external_id(self):
        return f"{self.nm_id}:{self.option_id}" if self.option_id is not None else self.nm_id

    @property
    def url(self):
        return f"https://www.wildberries.ru/catalog/{self.nm_id}/detail.aspx" + (f"?size={self.option_id}" if self.option_id is not None else "")

    @classmethod
    def parse(cls, value):
        if not isinstance(value, str):
            raise InvalidProductId("WB ID должен быть строкой nmId или nmId:optionId")
        parts = value.strip().split(":")
        if len(parts) not in (1, 2):
            raise InvalidProductId("WB ID должен иметь формат nmId или nmId:optionId")
        return cls(*parts)

    @classmethod
    def from_url(cls, value):
        location = urlsplit(value)
        match = re.fullmatch(r"/catalog/([0-9]+)/detail\.aspx", location.path)
        if (location.scheme != "https" or location.netloc not in ("www.wildberries.ru", "wildberries.ru")
                or not match or location.fragment):
            raise InvalidProductId("Используйте полную ссылку на товар Wildberries")
        sizes = parse_qs(location.query, keep_blank_values=True).get("size", [])
        if len(sizes) > 1:
            raise InvalidProductId("Ссылка WB должна содержать единственный size")
        return cls(match[1], sizes[0] if sizes else None)
