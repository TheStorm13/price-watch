# Yandex Market storefront capture

Captured 2026-11-10 through the authenticated Price Watch Chrome profile, starting
from SKU 5355099814. The complete declared size/color graph contains 64 SKUs.
Only public product/offer/price/promo fields and filter links are retained. User
objects are replaced by a synthetic `isAuth=true`; tracking, analytics keys,
account identifiers, cookies and HTML are omitted. Identical promo dictionaries
are stored once in `shared_promos`; `promo_fixture` restores the original group.
Tests render these collections and controls as synthetic Apiary HTML. They test
the parser and graph contract, not the availability of a future live promotion.
