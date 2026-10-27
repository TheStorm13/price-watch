"""Validate the runtime envelope and map only one exact-size price."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from ...domain.errors import MarketplaceSchemaChanged
from ...domain.models import Attribute, Availability, MarketplaceCard, ProductRef, ProductVariant, Rating, Seller
from .identity import WildberriesRef


def schema(message):
    return MarketplaceSchemaChanged(f'WB: {message}')


def amount(value, *, integer=False):
    if not isinstance(value, str):
        raise schema('сумма должна быть точной строкой')
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise schema('повреждена сумма') from exc
    if not result.is_finite() or result < 0 or (integer and result != result.to_integral_value()):
        raise schema('повреждена сумма')
    if integer and result > 2**53 - 1:
        raise schema('сумма вне безопасного диапазона')
    return result


def availability(size):
    stocks = size.get('stocks')
    if stocks is None:
        return Availability.UNKNOWN
    if not isinstance(stocks, list):
        raise schema('повреждены остатки размера')
    quantities = []
    for stock in stocks:
        qty = stock.get('qty') if isinstance(stock, dict) else None
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 0:
            raise schema('повреждён остаток размера')
        quantities.append(qty)
    return Availability.IN_STOCK if any(quantities) else Availability.OUT_OF_STOCK


def parse_product(payload, ref):
    if not isinstance(payload, dict) or payload.get('currency') != 'RUB' or payload.get('walletReady') is not True:
        raise schema('не подтверждены валюта или условия кошелька')
    product = payload.get('product')
    if not isinstance(product, dict) or product.get('id') != ref.nm_id:
        raise schema('ответ другого товара')
    sizes = product.get('sizes')
    if not isinstance(sizes, list) or not sizes or any(not isinstance(s, dict) for s in sizes):
        raise schema('отсутствуют размеры')
    ids = [s.get('optionId') for s in sizes]
    if any(not isinstance(value, str) for value in ids) or len(set(ids)) != len(ids) or ref.option_id not in ids:
        raise schema('выбранный размер отсутствует или дублируется')
    return product, sizes, sizes[ids.index(ref.option_id)]

def map_variants(sizes, ref):
    variants = []
    for size in sizes:
        try:
            variant_ref = WildberriesRef(ref.nm_id, size['optionId'])
        except (ValueError, TypeError) as exc:
            raise schema('повреждён ID размера') from exc
        label = size.get('name') or size.get('origName') or variant_ref.option_id
        variants.append(ProductVariant(ProductRef('wildberries', variant_ref.external_id), str(label),
            variant_ref.url, availability(size), variant_ref == ref, {'Размер': str(label)}))
    return tuple(variants)

def selected_price(size, stock):
    price = None
    raw_price = size.get('price')
    if raw_price is not None:
        if not isinstance(raw_price, dict):
            raise schema('повреждена цена размера')
        ordinary = amount(raw_price.get('priceToShow'), integer=True) / 100
        discount = amount(raw_price.get('paymentDiscountAmount'))
        if discount > ordinary:
            raise schema('скидка превышает цену')
        price = ordinary - discount
        if price != price.quantize(Decimal('.01')):
            raise schema('цена содержит доли копейки')
    elif stock != Availability.OUT_OF_STOCK:
        raise schema('отсутствует цена выбранного размера')
    return price

def map_rating(product):
    rating = None
    if product.get('reviewRating') is not None:
        try:
            rating = Rating(Decimal(str(product['reviewRating'])), reviews_count=product.get('feedbacks') or 0)
            if not rating.value.is_finite():
                raise ValueError()
        except (ValueError, InvalidOperation, TypeError) as exc:
            raise schema('повреждён рейтинг') from exc
    return rating

def map_metadata(payload):
    metadata = payload.get('metadata') or {}
    if not isinstance(metadata, dict) or not isinstance(metadata.get('options') or [], list):
        raise schema('повреждены характеристики')
    attributes = tuple(Attribute(o['name'], (str(o['value']),)) for o in (metadata.get('options') or [])
                       if isinstance(o, dict) and o.get('name') and o.get('value') is not None)
    return attributes, metadata.get("description") or ""


class WildberriesMapper:
    @staticmethod
    def to_card(payload, external_id, *, collected_at=None):
        ref = WildberriesRef.parse(external_id)
        product, sizes, size = parse_product(payload, ref)
        name = product.get('name')
        if not isinstance(name, str) or not name.strip():
            raise schema('отсутствует название')
        seller = None
        if product.get('supplier'):
            supplier_id = str(product['supplierId']) if product.get('supplierId') else None
            seller = Seller(supplier_id, product['supplier'])
        attributes, description = map_metadata(payload)
        stock = availability(size)
        return MarketplaceCard(
            ProductRef('wildberries', ref.external_id), name, ref.url, stock, selected_price(size, stock),
            seller=seller, rating=map_rating(product), variants=map_variants(sizes, ref),
            attributes=attributes, description=description,
            collected_at=collected_at or datetime.now(timezone.utc))
