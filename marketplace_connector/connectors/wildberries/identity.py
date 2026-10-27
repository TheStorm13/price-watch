"""Exact storefront article/size identity, safe to pass to the WB runtime."""
from dataclasses import dataclass
import re
from urllib.parse import parse_qs, urlsplit

from ...domain.errors import InvalidProductId

MAX_SAFE_INTEGER = 2**53 - 1


@dataclass(frozen=True)
class WildberriesRef:
    nm_id: str
    option_id: str

    def __post_init__(self):
        for value in (self.nm_id, self.option_id):
            if (not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*", value)
                    or len(value) > 16 or int(value) > MAX_SAFE_INTEGER):
                raise InvalidProductId("WB: ID должен быть положительным числом ASCII в безопасном диапазоне")

    @property
    def external_id(self):
        return f"{self.nm_id}:{self.option_id}"

    @property
    def url(self):
        return f"https://www.wildberries.ru/catalog/{self.nm_id}/detail.aspx?size={self.option_id}"

    @classmethod
    def parse(cls, value):
        if not isinstance(value, str):
            raise InvalidProductId("WB ID должен быть строкой nmId:optionId")
        parts = value.strip().split(":")
        if len(parts) == 1:
            raise InvalidProductId("Не указан размер WB")
        if len(parts) != 2:
            raise InvalidProductId("WB ID должен иметь формат nmId:optionId")
        return cls(*parts)

    @classmethod
    def from_url(cls, value):
        location = urlsplit(value)
        match = re.fullmatch(r"/catalog/([0-9]+)/detail\.aspx", location.path)
        if (location.scheme != "https" or location.netloc not in ("www.wildberries.ru", "wildberries.ru")
                or not match or location.fragment):
            raise InvalidProductId("Используйте полную ссылку Wildberries с выбранным размером")
        sizes = parse_qs(location.query, keep_blank_values=True).get("size", [])
        if len(sizes) != 1:
            raise InvalidProductId("Ссылка WB должна содержать единственный size")
        return cls(match[1], sizes[0])
