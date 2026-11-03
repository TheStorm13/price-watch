"""Validate identities at application boundaries, independently of persistence."""
from ..connectors.aliexpress.identity import AliExpressRef
from ..connectors.wildberries.identity import WildberriesRef
from ..domain.errors import InvalidProductId


def validate_card_identity(marketplace: str, external_id: str, url: str | None = None) -> tuple[str, str | None]:
    external_id = external_id.strip()
    ref_type = {"aliexpress": AliExpressRef, "wildberries": WildberriesRef}.get(marketplace.strip().lower())
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
