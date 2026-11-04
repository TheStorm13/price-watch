"""Exact storefront SKU; Ozon does not encode family membership in its ID."""
import re
from urllib.parse import urlsplit

from ...domain.errors import InvalidProductId


def validate_ozon_identity(external_id: str, url: str | None = None) -> tuple[str, str]:
    if not re.fullmatch(r'[0-9]+', external_id):
        raise InvalidProductId('Артикул Ozon должен состоять из цифр ASCII')
    if url:
        parsed = urlsplit(url)
        match = re.fullmatch(r'/product/(?:[^/]*-)?([0-9]+)/?', parsed.path)
        if (parsed.scheme != 'https' or parsed.netloc not in ('ozon.ru', 'www.ozon.ru')
                or not match or match[1] != external_id or parsed.fragment):
            raise InvalidProductId('Ссылка Ozon не соответствует артикулу выбранного варианта')
    return external_id, url or f'https://www.ozon.ru/product/{external_id}/'
