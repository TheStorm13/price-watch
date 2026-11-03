"""Map validated AliExpress data to the common single-price card."""
from decimal import Decimal, InvalidOperation
from ...domain.models import MarketplaceCard, ProductRef, ProductVariant, Rating, Attribute
from ...domain.errors import MarketplaceSchemaChanged
from .identity import AliExpressRef
from .parser import stock


def _variants(data, ref):
    sku_info = data['skuInfo']
    properties = {}
    for prop in sku_info.get('propertyList') or []:
        for value in prop.get('values') or []:
            properties[value['id']] = (prop['name'], value.get('displayName') or value.get('name') or '', value.get('imageMainUrl') or value.get('imagePreviewUrl'))
    for row in sku_info['priceList']:
        variant_ref = AliExpressRef(ref.product_id, row['skuId'])
        values = [properties[key] for key in (row.get('skuPropIds') or '').split(',') if key in properties]
        options = {name: value for name, value, _ in values}
        image = next((url for _, _, url in values if url), None) or _image(data)
        yield ProductVariant(
            ref=ProductRef('aliexpress', variant_ref.external_id), title=data['name'], url=variant_ref.url,
            availability=stock(row), selected=variant_ref == ref, options=options, image_url=image)


def _rating(data):
    rating_data = data.get('rating') or {}
    if rating_data.get('middle') is None:
        return None
    return Rating(Decimal(str(rating_data['middle'])), reviews_count=int(data.get('reviews') or 0))


def _image(data):
    return next((item.get('imageUrl') for item in (data.get('gallery') or [])
                 if isinstance(item, dict) and item.get('imageUrl')), None)


def _attributes(data):
    return tuple(Attribute(item['name'], tuple(str(v) for v in item['values']))
                 for item in (data.get('characteristics') or []) if item.get('name') and item.get('values'))


class AliExpressMapper:
    @staticmethod
    def to_card(product):
        data, ref = product.data, product.ref
        try:
            variants = tuple(_variants(data, ref))
            image = next((v.image_url for v in variants if v.selected), None) or _image(data)
            return MarketplaceCard(
                ref=ProductRef('aliexpress', ref.external_id), title=data['name'], url=ref.url,
                availability=product.availability, price=product.price, image_url=image, rating=_rating(data),
                attributes=_attributes(data), description=data.get('description') or '', variants=variants,
                collected_at=product.collected_at)
        except (TypeError, ValueError, KeyError, AttributeError, InvalidOperation) as exc:
            raise MarketplaceSchemaChanged('Изменились поля карточки AliExpress') from exc
