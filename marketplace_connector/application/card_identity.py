"""Validate identities at application boundaries, independently of persistence."""
from ..connectors.aliexpress.identity import AliExpressRef
from ..connectors.wildberries.identity import WildberriesRef
from ..connectors.yandex_market.identity import YandexMarketRef
from ..domain.errors import InvalidProductId
from ..connectors.ozon.identity import validate_ozon_identity


def validate_card_identity(marketplace: str, external_id: str, url: str | None = None) -> tuple[str, str | None]:
    external_id = external_id.strip()
    if marketplace.strip().lower() == 'ozon':
        return validate_ozon_identity(external_id, url)
    ref_type = {"aliexpress": AliExpressRef, "wildberries": WildberriesRef, "yandex-market": YandexMarketRef}.get(marketplace.strip().lower())
    if ref_type:
        ref = ref_type.parse(external_id)
        if url:
            linked = ref_type.from_url(url)
            if linked.external_id.split(':')[0] != ref.external_id.split(':')[0] or (
                    ':' in linked.external_id and ':' in ref.external_id and linked != ref):
                raise InvalidProductId("Ссылка не соответствует товару и выбранному варианту карточки")
        return ref.external_id, url or ref.url
    if not external_id:
        raise InvalidProductId("ID карточки обязателен")
    return external_id, url


def validate_variant_identity(marketplace: str, article: str, external_id: str,
                              url: str | None = None) -> tuple[str, str | None]:
    """Validate a declared member; Ozon membership is established by the caller.

    Discovery supplies storefront edges; transfer supplies saved membership.
    Neither may infer an Ozon family from numeric prefixes or product titles.
    """
    ref, url = validate_card_identity(marketplace, external_id, url)
    if marketplace.lower() == 'ozon':
        validate_ozon_identity(article)
    elif marketplace.lower() == 'yandex-market':
        YandexMarketRef.parse(article)
    elif (ref.split(':')[0] if marketplace.lower() in ('aliexpress', 'wildberries') else ref) != article:
        raise InvalidProductId('Вариант принадлежит другому товару')
    return ref, url
