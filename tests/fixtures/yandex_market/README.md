# Yandex Market storefront capture

Captured 2026-11-10 through the authenticated Price Watch Chrome profile, starting
from SKU 5355099814. The complete declared size/color graph contains 64 SKUs.
Only public product/offer/price/promo fields and filter links are retained. User
objects are replaced by a synthetic `isAuth=true`; tracking, analytics keys,
account identifiers, cookies and HTML are omitted. Identical promo dictionaries
are stored once in `shared_promos`; `promo_fixture` restores the original group.
Tests render these collections and controls as synthetic Apiary HTML. They test
the parser and graph contract, not the availability of a future live promotion.

`external_article.json` is a public-field capture of article 6019174271 from the
same authenticated profile on 2026-11-10. Its internal market SKU is 6249927249;
it has stock and delivery but no size selector. The selected card's structured
control declares ten linked entries, including other product models. Only target
article IDs and selection are kept from that control; analytics and account data
are omitted. Expected price is 3398 less one HOME11 discount of 10%: 3058.20.
