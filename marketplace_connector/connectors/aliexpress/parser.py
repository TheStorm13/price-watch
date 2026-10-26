"""Validate productData and select exactly one price of the requested SKU."""
import json
import re
from datetime import datetime, timezone
from decimal import Decimal

from ...domain.errors import MarketplaceSchemaChanged
from ...domain.models import Availability
from ...domain.money import normalize_price
from .identity import AliExpressRef
from .models import AliExpressProductData


def _reject_constant(value):
    raise ValueError('Non-finite JSON number')


def stock(row):
    value = row.get('availQuantity')
    if value is None:
        return Availability.UNKNOWN
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not re.fullmatch(r'[0-9]+', str(value)):
        raise MarketplaceSchemaChanged('Некорректный остаток SKU AliExpress')
    return Availability.IN_STOCK if int(value) > 0 else Availability.OUT_OF_STOCK


def selected_price(row):
    coupon = row.get('priceWithCoupon')
    if coupon is not None and not isinstance(coupon, dict):
        raise MarketplaceSchemaChanged('Некорректная купонная цена AliExpress')
    for amount in [(coupon or {}).get('amount'), row.get('activityAmount'), row.get('amount')]:
        if amount is None:
            continue
        if not isinstance(amount, dict) or amount.get('currency') != 'RUB':
            raise MarketplaceSchemaChanged('Цена AliExpress должна содержать сумму в RUB')
        cents = amount.get('cents')
        if isinstance(cents, bool) or not isinstance(cents, (str, int)) or not re.fullmatch(r'[0-9]+', str(cents)):
            raise MarketplaceSchemaChanged('Некорректные cents цены AliExpress')
        try:
            return normalize_price(Decimal(str(cents)) / 100)
        except (ValueError, ArithmeticError) as exc:
            raise MarketplaceSchemaChanged('Некорректная сумма AliExpress') from exc
    return None


def _decode(raw_text):
    payload = json.loads(raw_text, parse_float=Decimal, parse_constant=_reject_constant) if isinstance(raw_text, str) else raw_text
    data = payload['data']
    if not isinstance(data, dict):
        raise ValueError('data')
    return data


def _selected_sku(data, ref):
    if data.get('id') != ref.product_id or data.get('activeSkuId') != ref.sku_id:
        raise ValueError('identity mismatch')
    rows = data['skuInfo']['priceList']
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError('priceList')
    ids = [row.get('skuId') for row in rows]
    if any(not isinstance(sku, str) or not re.fullmatch(r'[0-9]+', sku) for sku in ids):
        raise ValueError('invalid SKU')
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate SKU')
    return next(row for row in rows if row['skuId'] == ref.sku_id)


class AliExpressProductParser:
    @staticmethod
    def parse(raw_text, *, expected_external_id, collected_at=None):
        ref = AliExpressRef.parse(expected_external_id)
        try:
            data = _decode(raw_text)
            selected = _selected_sku(data, ref)
            if not isinstance(data.get('name'), str) or not data['name'].strip():
                raise ValueError('name')
            availability = stock(selected)
            price = None if availability == Availability.OUT_OF_STOCK else selected_price(selected)
            if availability == Availability.IN_STOCK and price is None:
                raise MarketplaceSchemaChanged('Нет цены доступного SKU AliExpress')
            return AliExpressProductData(ref, data, selected, price, availability,
                                         collected_at or datetime.now(timezone.utc))
        except (KeyError, TypeError, ValueError, StopIteration) as exc:
            raise MarketplaceSchemaChanged('Изменилась структура productData или идентичность SKU AliExpress') from exc
