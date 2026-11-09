# Архитектурные решения

Здесь хранятся ADR для значимых решений, подтверждённых кодом и
согласованных с владельцем проекта.

- [ADR 0001: Фоновый жизненный цикл desktop-приложения](0001-background-desktop-lifecycle.md) — Accepted.
- [ADR 0002: Desktop как единственный live-интерфейс](0002-desktop-only-live-ui.md) — Accepted.

- [ADR 0004: Владение сбором, результаты целей и снимок каталога](0004-collection-reliability-and-catalog-snapshot.md) — Accepted.

- [ADR 0005: Общий товар, запись отслеживания и точные цены](0005-marketplace-card-and-tracking-record.md) — Accepted.

- [ADR 0006: Ozon JSON через общую страницу браузерной сессии](0006-ozon-session-json-transport.md) — Accepted.

- [ADR 0007: Правила приложения и явные границы хранения](0007-application-rules-and-persistence-boundaries.md) — Accepted.

- [ADR 0008: AliExpress SKU и общий Chrome-сеанс](0008-aliexpress-sku-and-shared-browser.md) — Accepted.

- [ADR 0012: Семейство Ozon с самостоятельными артикулами вариантов](0012-ozon-variant-family.md) — Accepted (design), реализация на приёмке.

Наблюдаемое устройство системы описано в
[обзоре архитектуры](../architecture/overview.md); обзор не заменяет запись
о мотивах выбора и рассмотренных альтернативах.

При изменении решения новый ADR должен ссылаться на прежний и объяснять,
что именно его заменяет. Исторические записи не переписываются.

- [ADR 0013: Selective recurring variant tracking](0013-selective-variant-tracking.md) — initial full discovery, default-off preferences and frozen ordinary targets.

- [ADR 0014: Асинхронный Ozon без планового лимита частоты](0014-ozon-unpaced-async-concurrency.md) — историческое решение Ozon N=8; concurrency policy заменена ADR0015.

- [ADR 0015: Последовательные маркетплейсы с отдельными request pools](0015-shared-request-dispatcher.md) — Accepted (design), последовательные этапы и отдельные HTTP pools 100.

- [ADR 0016: Кэшированные миниатюры списка в локальном API](0016-cached-product-thumbnails.md) — Accepted, Lanczos 204 px и восстанавливаемый дисковый кэш.
