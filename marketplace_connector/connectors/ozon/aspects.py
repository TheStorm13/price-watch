"""Resolve the observed Ozon aspect modal without replacing exact SKU data."""
from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

from ...domain.errors import MarketplaceSchemaChanged
from .mapper import OzonMapper
from .parser import OzonProductParser

MAX_VARIANTS = 500


def modal_link(value, article):
    if not isinstance(value, str):
        raise MarketplaceSchemaChanged('В продолжении вариантов Ozon отсутствует link')
    url = urlsplit(value)
    query = parse_qs(url.query)
    if (url.scheme or url.netloc or url.fragment or url.path != '/modal/aspectsNew'
            or query.get('product_id') != [article]
            or query.get('from_sku') != [article]):
        raise MarketplaceSchemaChanged('Продолжение вариантов Ozon относится к другому товару или адресу')
    return value


def modal_aspects(raw):
    payload = OzonProductParser._decode_document(raw)
    widgets = payload.get('widgetStates')
    if not isinstance(widgets, dict):
        raise MarketplaceSchemaChanged('В модальном ответе Ozon отсутствует widgetStates')
    names = [key for key in widgets if key.startswith('webAspectsModal-')]
    if len(names) != 1:
        raise MarketplaceSchemaChanged('В ответе Ozon отсутствует однозначный webAspectsModal')
    result = OzonProductParser._widget(widgets, names[0])
    if set(result) - {'aspects', 'lexemes', 'currentVariant', 'ringSizeTacticRs', 'cellTrackingInfo',
                      'sliceTrackingInfo', 'modalType', 'trackingInfo', 'searchInfo', 'submitInfo'}:
        raise MarketplaceSchemaChanged('Модальный список Ozon содержит неизвестное продолжение')
    # Validate the consumed structures, including SKU/link identity.
    list(OzonMapper._variants(result, ''))
    if not isinstance(result.get('aspects'), list):
        raise MarketplaceSchemaChanged('В модальном ответе Ozon отсутствуют аспекты')
    if len({v.ref.external_id for v in OzonMapper._variants(result, '')}) > MAX_VARIANTS:
        raise MarketplaceSchemaChanged('Список вариантов Ozon превышает предел 500 SKU')
    return result


def _continuation(info, article):
    if not isinstance(info, dict) or set(info) - {'trackingInfo', 'realNumberOfVariants', 'link', 'linkText'}:
        raise MarketplaceSchemaChanged('Неизвестная структура aspectModalInfo Ozon')
    if not set(info) - {'trackingInfo'}:
        return None
    link = modal_link(info.get('link'), article)
    count = info.get('realNumberOfVariants')
    if not isinstance(count, (str, int)) or isinstance(count, bool) or not str(count).isascii() or not str(count).isdigit():
        raise MarketplaceSchemaChanged('В продолжении Ozon отсутствует корректное число вариантов')
    count = int(count)
    if not 0 < count <= MAX_VARIANTS:
        raise MarketplaceSchemaChanged('Число вариантов Ozon вне предела 1..500')
    return link, count


def _merged_variants(aspect, modal, count):
    matches = [row for row in modal['aspects'] if row.get('aspectKey') == aspect.get('aspectKey')]
    if len(matches) != 1:
        raise MarketplaceSchemaChanged('Модальный список Ozon не содержит нужный аспект')
    expanded = matches[0]
    if 'index' in expanded and expanded.get('index') != aspect.get('index'):
        raise MarketplaceSchemaChanged('Индекс аспекта Ozon не совпадает')
    if expanded.get('aspectModalInfo') or OzonMapper._discovery_status({'aspects': [expanded]}):
        raise MarketplaceSchemaChanged('Модальный список Ozon содержит неподдерживаемое продолжение')
    ids = {str(v['sku']) for v in expanded['variants']}
    inline = {str(v['sku']) for v in aspect.get('variants', [])}
    if len(ids) != count or not inline <= ids:
        raise MarketplaceSchemaChanged('Модальный список Ozon неполон или противоречит исходному списку')
    # Keep exact selected options and metadata from the product response.
    original = {str(v['sku']): v for v in aspect.get('variants', [])}
    return [original.get(str(v['sku']), v) for v in expanded['variants']]


async def complete_aspects(aspects, article, fetch_modal):
    result = deepcopy(aspects)
    errors = []
    fetched = {}
    for aspect in result.get('aspects', []):
        info = aspect.get('aspectModalInfo')
        if info is None:
            continue
        try:
            continuation = _continuation(info, article)
            if continuation is None:
                aspect.pop('aspectModalInfo')
                continue
            link, count = continuation
            if link not in fetched:
                try:
                    fetched[link] = modal_aspects(await fetch_modal(link))
                except Exception as exc:
                    fetched[link] = exc
            modal = fetched[link]
            if isinstance(modal, Exception):
                raise modal
            aspect['variants'] = _merged_variants(aspect, modal, count)
            aspect.pop('aspectModalInfo')
        except Exception as exc:
            errors.append(f"Ozon {article}, аспект {aspect.get('aspectKey')}: {type(exc).__name__}: {exc}")
    return result, '; '.join(errors) or None
