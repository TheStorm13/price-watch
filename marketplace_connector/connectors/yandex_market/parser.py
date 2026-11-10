"""Decode Apiary patches and explicitly declared variant controls, never script code."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
import json
from urllib.parse import urljoin

from ...domain.errors import AuthenticationRequired, MarketplaceSchemaChanged
from ...domain.models import Availability, MarketplaceCard, ProductRef, Rating, Seller
from .identity import YandexMarketRef
from .pricing import select_price


class StorefrontHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.collections = {}
        self.edges = []
        self.groups = []
        self._frames = False
        self._buffer = []
        self._stack = []
        self.discovery_error = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'noframes':
            self._frames = True
            self._buffer = []
        group = self._stack[-1][1] if self._stack else None
        if attrs.get('data-zone-name') == 'filter':
            try:
                declared = json.loads(attrs.get('data-zone-data', '{}'))['numValues']
                if not isinstance(declared, int) or isinstance(declared, bool) or declared < 1:
                    raise ValueError('count')
            except (ValueError, KeyError, TypeError):
                declared = None
                self.discovery_error = 'Маркет: неизвестная полнота списка вариантов'
            group = {'declared': declared, 'values': []}
            self.groups.append(group)
        if attrs.get('data-zone-name') == 'filterValue':
            edge = {key: attrs.get(key) for key in ('filterid', 'value', 'pagehref')}
            if group is None or not all(isinstance(v, str) and v for v in edge.values()):
                self.discovery_error = 'Маркет: неполный контрол вариантов'
            else:
                group['values'].append(edge)
                self.edges.append(edge)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self._stack.append((tag, group))

    def handle_endtag(self, tag):
        if tag == 'noframes' and self._frames:
            self._frames = False
            try:
                patch = json.loads(''.join(self._buffer), parse_float=Decimal)
                for name, values in patch.get('collections', {}).items():
                    if isinstance(values, dict):
                        self.collections.setdefault(name, {}).update(values)
            except (ValueError, AttributeError):
                # Apiary also contains non-collection noframes payloads.
                pass
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                del self._stack[index:]
                break

    def handle_data(self, data):
        if self._frames:
            self._buffer.append(data)

    def finish(self):
        for group in self.groups:
            if group['declared'] != len(group['values']):
                self.discovery_error = 'Маркет: список вариантов содержит скрытое продолжение'
        return self


@dataclass(frozen=True)
class ParsedProduct:
    card: MarketplaceCard
    parent_id: str
    edges: tuple[str, ...]
    options: dict[str, str]
    discovery_error: str | None
    links_may_include_other_models: bool = False


def parse_product(html, external_id, *, now=None):
    ref = YandexMarketRef.parse(external_id)
    parsed = StorefrontHTML()
    parsed.feed(html)
    collections = parsed.collections
    users = collections.get('currentUser', {}).values()
    if not any(user.get('isAuth') is True for user in users):
        raise AuthenticationRequired('Войдите в Яндекс Маркет через Chrome приложения и повторите сбор')
    try:
        matches = []
        for key, meta in collections['productCardMeta'].items():
            compose = collections.get('compose', {}).get(key, {})
            if str(compose.get('oskuId', compose.get('skuId'))) == ref.external_id:
                matches.append((key, meta))
        if len(matches) != 1:
            raise ValueError('SKU mismatch')
        key, meta = matches[0]
        compose = collections['compose'][key]
        market_sku = str(compose['skuId'])
        if market_sku != str(meta['marketSku']) or str(compose['productId']) != str(meta['productId']):
            raise ValueError('compose mismatch')
        options = [b for b in collections.get('buyOption', {}).values()
                   if str(b.get('skuId')) == market_sku and b.get('offerId') == compose['offerId']]
        if len(options) != 1:
            raise ValueError('offer missing or ambiguous')
        buy = options[0]
        if str(buy['productId']) != str(meta['productId']) or str(buy['businessId']) != str(compose['businessId']):
            raise ValueError('offer mismatch')
        maximum = buy['maximum']
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 0:
            raise ValueError('stock')
        if not all(isinstance(buy[name], bool) for name in ('hasAnySize', 'hasAnyDelivery')):
            raise ValueError('availability flags')
        # hasAnySize describes the size selector; non-clothing offers can have
        # no sizes while still having stock and delivery for this exact offer.
        available = buy['hasAnyDelivery'] is True and maximum > 0
        availability = Availability.IN_STOCK if available else Availability.OUT_OF_STOCK
        observed_at = now or datetime.now(timezone.utc)
        price, detail = select_price(collections['price'][key], buy, collections.get('shopPromoCodeFull', {}), now=observed_at) if available else (None, {})
        detail.update(sku_id=ref.external_id, market_sku_id=market_sku, product_id=str(meta['productId']),
                      offer_id=compose['offerId'], business_id=str(compose['businessId']))
        title = meta['skuTitle']
        if not isinstance(title, str) or not title.strip():
            raise ValueError('title')
        slug = compose.get('oskuSlug', meta['slug'])
        url = f"https://market.yandex.ru/card/{slug}/{ref.external_id}"
        if YandexMarketRef.from_url(url) != ref:
            raise ValueError('canonical')
        rating = Rating(meta['rating'], reviews_count=meta.get('ratingCount', 0)) if 'rating' in meta else None
        card = MarketplaceCard(ProductRef('yandex-market', ref.external_id), title, url, availability, price,
            image_url=meta.get('image'), seller=Seller(str(buy['businessId']), buy['businessName']),
            rating=rating, description=meta.get('description', ''), collected_at=observed_at,
            extensions={'yandex_market': detail})
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise MarketplaceSchemaChanged('Маркет: отсутствуют или не соответствуют SKU данные карточки') from exc
    edges = []
    selected = {}
    related_models = False
    jump_list = collections.get('jumpListShort', {}).get(key)
    if jump_list is not None and not parsed.edges:
        try:
            # This is the selected card's control, not recommendation snippets.
            groups = [group for group in parsed.groups if not group['values']]
            snippets = jump_list['snippets']
            if len(groups) != 1 or len(snippets) != groups[0]['declared']:
                raise ValueError('incomplete jump list')
            selected_ids = []
            for snippet in snippets:
                payload = snippet['productPayload']
                target = payload['targetLinkParams']
                offer = payload['offerParams']
                neighbor = YandexMarketRef.parse(offer['oskuId'])
                if (snippet['type'] != 'JUMP_LIST_SHORT' or target['targetPage'] != 'OSKU_CARD'
                        or str(target['offerLinkParams']['oskuId']) != neighbor.external_id
                        or str(snippet['snippetId']) != neighbor.external_id):
                    raise ValueError('jump target mismatch')
                if (payload.get('jumpList') or {}).get('isSelected') is True:
                    selected_ids.append(neighbor.external_id)
                edges.append(neighbor.external_id)
            if selected_ids != [ref.external_id] or len(set(edges)) != len(snippets):
                raise ValueError('jump selection mismatch')
            transition = jump_list.get('showAllTransition')
            if transition and (transition['type'] != 'jumpListPopup'
                               or str(transition['params']['oskuId']) != ref.external_id):
                raise ValueError('unknown jump continuation')
            groups[0]['values'] = edges.copy()
            related_models = True
        except (KeyError, TypeError, ValueError, AttributeError):
            edges.clear()
            parsed.discovery_error = 'Маркет: неполный структурированный список вариантов'
    for edge in parsed.edges:
        if edge['pagehref'] == '#':
            if edge['filterid'] in selected:
                parsed.discovery_error = 'Маркет: неоднозначное выбранное значение варианта'
            selected[edge['filterid']] = edge['value']
        else:
            try:
                neighbor = YandexMarketRef.from_url(urljoin('https://market.yandex.ru', edge['pagehref']))
                edges.append(neighbor.external_id)
            except ValueError:
                parsed.discovery_error = 'Маркет: неизвестная ссылка продолжения вариантов'
    names = {'14871214': 'Цвет', '74155816': 'Размер'}
    selected = {names.get(k, f'Параметр {k}'): v for k, v in selected.items()}
    parsed.finish()
    return ParsedProduct(card, str(meta['productId']), tuple(dict.fromkeys(edges)), selected,
                         parsed.discovery_error, links_may_include_other_models=related_models)
