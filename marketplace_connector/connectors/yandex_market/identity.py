"""Exact Market SKU identity, independent of parent product and seller offer."""
from dataclasses import dataclass
import re
from urllib.parse import urlsplit

from ...domain.errors import InvalidProductId


@dataclass(frozen=True)
class YandexMarketRef:
    external_id: str

    def __post_init__(self):
        if not isinstance(self.external_id, str) or not re.fullmatch(r'[1-9][0-9]{0,19}', self.external_id):
            raise InvalidProductId('Яндекс Маркет: SKU должен состоять из цифр ASCII')

    @property
    def url(self):
        return f'https://market.yandex.ru/card/tovar/{self.external_id}'

    @classmethod
    def parse(cls, value):
        if not isinstance(value, str):
            raise InvalidProductId('Яндекс Маркет: SKU должен быть строкой')
        return cls(value.strip())

    @classmethod
    def from_url(cls, value):
        location = urlsplit(value)
        match = re.fullmatch(r'/card/[^/]+/([0-9]+)/?', location.path)
        if (location.scheme != 'https' or location.netloc != 'market.yandex.ru'
                or not match or location.fragment):
            raise InvalidProductId('Используйте полную ссылку market.yandex.ru/card/…/SKU')
        return cls(match[1])
