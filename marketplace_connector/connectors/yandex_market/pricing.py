"""Choose one offer-bound promo applied independently to the card price."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from ...domain.errors import MarketplaceSchemaChanged

CENT = Decimal('0.01')


def money(value):
    try:
        if not isinstance(value, dict) or value.get('currency') not in ('RUR', 'RUB'):
            raise ValueError('currency')
        raw = value['value']
        if isinstance(raw, bool):
            raise ValueError('boolean')
        amount = Decimal(str(raw))
        if not amount.is_finite() or amount < 0:
            raise ValueError('amount')
        return amount
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise MarketplaceSchemaChanged('Маркет: повреждена цена RUB') from exc


def select_price(price, buy, promos, *, now=None):
    now = now or datetime.now(timezone.utc)
    main = price.get('mainPrice', {})
    base = money(main.get('price'))
    if main.get('subtype') == 'ya-card':
        card = base
        regulars = [money(p.get('price')) for p in price.get('oldPrices', []) if p.get('type') == 'regular']
        if len(regulars) != 1:
            raise MarketplaceSchemaChanged('Маркет: отсутствует обычная цена')
        regular = regulars[0]
    elif main.get('type') == 'regular':
        card, regular = None, base
    else:
        raise MarketplaceSchemaChanged('Маркет: неизвестное основание основной цены')
    if regular != money(buy.get('price')):
        raise MarketplaceSchemaChanged('Маркет: цена не соответствует выбранному offer')
    excluded = []
    candidates = [(base, '', None)]
    for link in buy.get('promos', []):
        if link.get('type') != 'promo-code':
            continue
        promo = promos.get(link.get('shopPromoId'))
        code = link.get('promoCode')
        reason = None
        try:
            if buy.get('minimum') != 1:
                raise ValueError('single_unit_unavailable')
            if not promo or not isinstance(code, str) or promo.get('promoCode') != code:
                raise ValueError('missing_offer_promo')
            conditions = promo.get('conditions')
            if not isinstance(conditions, dict):
                raise ValueError('missing_conditions')
            if set(conditions) - {'orderMinPrice', 'orderMaxPrice', 'orderMaxDiscount', 'bindOnlyOnce'}:
                raise ValueError('unknown_conditions')
            if conditions.get('bindOnlyOnce', False) is not False:
                raise ValueError('account_restriction_unverified')
            if 'startDate' in promo:
                start = datetime.fromisoformat(promo['startDate'].replace('Z', '+00:00'))
                if start.tzinfo is None or start > now:
                    raise ValueError('not_started')
            end = datetime.fromisoformat(promo['endDate'].replace('Z', '+00:00'))
            if end.tzinfo is None or end <= now:
                raise ValueError('expired')
            if 'orderMinPrice' in conditions and base < money(conditions['orderMinPrice']):
                raise ValueError('below_minimum')
            if 'orderMaxPrice' in conditions and base > money(conditions['orderMaxPrice']):
                raise ValueError('above_maximum')
            discount = promo['discount']
            kind = discount['type']
            if kind == 'percent':
                percent = Decimal(str(discount['percent']))
                if not percent.is_finite() or not 0 < percent <= 100:
                    raise ValueError('invalid_percent')
                amount = base * percent / 100
                size = str(percent)
            elif kind == 'absolute':
                amount = money(discount.get('absolute'))
                # The API clips absolute to regular_price - 1. The declared
                # discount cannot be recovered from that clipped value.
                if amount >= regular - 1:
                    raise ValueError('clipped_absolute_unverified')
                size = str(amount)
            else:
                raise ValueError('unknown_discount_type')
            if 'orderMaxDiscount' in conditions:
                amount = min(amount, money(conditions['orderMaxDiscount']))
            final = (base - amount).quantize(CENT, rounding=ROUND_HALF_UP)
            if final < 1:
                raise ValueError('minimum_price_unverified')
            detail = {'promo_code': code, 'discount_type': kind, 'discount_value': size,
                      'expires_at': end.isoformat(), 'conditions': {
                          k: str(money(v)) if isinstance(v, dict) else v for k, v in conditions.items()}}
            candidates.append((final, code, detail))
        except (ValueError, KeyError, TypeError, InvalidOperation, MarketplaceSchemaChanged) as exc:
            reason = str(exc)
        if reason:
            excluded.append({'promo_code': code, 'reason': reason})
    final, _, selected = min(candidates, key=lambda c: (c[0], c[1]))
    source = 'card' if card is not None else 'regular'
    detail = dict(regular_price=str(regular), card_price=str(card) if card is not None else None,
                  base_price=str(base), final_price=str(final), price_source=source + ('_promo' if selected else ''),
                  promo_code=None, calculation_basis='card_plus_single_promo', verification='calculated',
                  excluded_promos=excluded)
    if selected:
        detail.update(selected)
    return final, detail
