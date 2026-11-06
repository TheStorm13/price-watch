# Коннектор AliExpress

## Задание и порядок

Пользователь выбрал `$vibe-flow`: изучить Ozon, выполнить пробный запрос карточки
AliExpress, согласовать полученные данные и затем перейти к реализации.
Код приложения до согласования плана не менять. Второе review — принятие
проверенной реализации; затем документация, sync/archive и task-only commit.

## Исследование Ozon (2026-10-26)

Исходный HEAD: `c534565`. Уже имеется постороннее изменение `docs/BACKLOG.md`;
не включать его в изменения этой задачи.

- `marketplace_connector/ports/connector.py`: async `get_product(external_id)`
  возвращает `MarketplaceCard`; `collection_session` управляет ресурсами сбора.
- `connectors/ozon/connector.py`: client → response → parser → mapper → card.
- `connectors/ozon/async_client.py` и `json_transport.py`: сессия системного
  Chrome/CDP, общая storefront page, JSON fetch без навигации к каждой карточке,
  ограничение запросов, cooldown, восстановление и отдельная отмена запросов.
- `domain/models.py`: общие ref/title/url/availability, точная Decimal price,
  image/seller/rating/attributes/description/variants/collected_at/extensions.
  OUT_OF_STOCK обнуляет текущую цену; варианты обязаны иметь уникальные ref.
- `price_watch/cli.py`: отдельные фабрики для прямого collect и worker регистрируют
  только Ozon. Обе потребуют проверки при подключении AliExpress.
- `price_watch/domain/marketplaces.py`: AliExpress пока в списке площадок без
  коннектора. UI/API уже допускают его карточки; отображение Ali имеется.
- Предыдущее исследование транспорта:
  `openspec/changes/archive/2026-10-26-ozon-session-json-transport/research.md`.
  Результаты Ozon не являются доказательством доступности или схемы AliExpress.

CodeGraph запросы выполнены с явным projectPath текущего репозитория, source
получен с диска. Repowise get_why не нашёл rationale и сообщил старый индекс
`9f3876d9ba3f`; его выводы не используются как текущая архитектурная проверка.
Repowise get_risk повторно сообщил старый commit и выделил lifecycle Ozon как
hotspot. Bounded `repowise update --index-only --working-tree --no-agents
--no-workspace --progress json` дошёл до persist, но завершён timeout 20 с;
актуальность MCP не подтверждена, критические выводы сверены с source.

## Текущее состояние

Пользователь предоставил товар `1005009868651525`, короткую ссылку
`https://ali.click/mtipo1n` и карточку на aliexpress.ru с
`sku_id=12000061135122688`. Проверяется российская витрина.

Выполнены прямой HTTP GET и открытие карточки в системном Chrome, сначала со
свежим временным профилем, затем с профилем price-watch. В обоих случаях исходный
документ HTTP 200 содержит редирект на `_____tmd_____/punish`; страница проверки
возвращает HTTP 429. Наблюдавшиеся JSON относятся к CAPTCHA, не к товару.
Дальнейшие успешные результаты приведены ниже. Пользователь уточнил: CAPTCHA должен пройти пользователь. Для
реализации требуется ручное прохождение и возобновление сбора после проверки.

CUA вернул пустой список браузеров, web open не смог открыть карточку. Для
сетевой диагностики используется временный `/tmp/price_watch_ali_probe.py` с
Playwright; документация network responses получена через Context7. Скрипт
оставляет открытое окно до 10 минут для ручной проверки, затем исследует ответы.
Секреты/cookies в отчёт не включать; полный HTML проверки не является fixture.

OpenSpec-план создан: `openspec/changes/add-aliexpress-connector/`;
ADR: `docs/adr/0008-aliexpress-sku-and-shared-browser.md` (Proposed).
Приложение и пользовательская БД не изменялись; application tests пока не запускались.

## Итоговое состояние

Пользователь принял реализацию 2026-10-26: «Да, сделай коммиты».
Проверки пройдены, руководства обновлены, ADR 0008 Accepted. Требования
синхронизированы в основные спецификации; change перемещён в
`openspec/changes/archive/2026-10-26-add-aliexpress-connector/`.
Коммит реализации: `28e3a99`. Документация и архив фиксируются отдельным
коммитом; итоговые хеши проверяются перед ответом. docs/BACKLOG.md исключён; push не выполняется.
Подробности: [verification](add-aliexpress-connector/verification.md).

## Успешный probe после ручной CAPTCHA

Пользователь подтвердил «Вот теперь прошло» после перехода на штатный внешний
Chrome/CDP lifecycle Ozon. Найден и проверен GET
`/aer-jsonapi/v1/bx/pdp/web/productData?productId=1005009868651525&sourceId=0&sku_id=12000061135122688`.
HTTP 200, application/json, 23 257 символов. С отдельной главной страницы той же
сессии три fetch (указанный SKU, второй SKU, без sku_id) вернули HTTP 200;
product navigations = 0. БД не использовалась.

Детали: `add-aliexpress-connector/research.md`; очищенная сводка ответа:
`add-aliexpress-connector/probe-summary.json`.
Акционная цена 79 316 RUB, с купоном 77 648 RUB (isCouponAssigned=false),
зачёркнутая 122 312 RUB. Два SKU, каждый availQuantity=1. Рейтинг 4.8,
22 отзыва, characteristics=[], seller OP Pioneer Store. Seller name/url
доступны в bootstrap; productData содержит sellerId, но storeUrl=null.

Пользователь согласовал правило цены: **одна** цена по приоритету
`priceWithCoupon.amount` → `activityAmount` → `amount`. Не хранить/отображать
другие цены отдельно. Не требовать isCouponAssigned=true и не получать купон
автоматически. Для probe выбранная цена 77 648.00 RUB. Это согласование
семантики цены, не одобрение всей реализации.

Пользователь выбрал «Конкретного SKU». План: canonical external_id productId:skuId,
раздельная история вариантов, общий Chrome session для Ozon/Ali и раздельные
storefront pages; одна цена, ручная CAPTCHA, safe data-only migration старых
AliExpress-записей только при однозначном SKU. ProductData optional fields
не обогащаются через карточки; seller=null при отсутствии имени.
Plan review и принятие реализации ещё не пройдены.

Уточнение пользователя: «Старые ali карточки если не имеет skuid то просто
ошибка, карточку не трогай». План/спецификация/ADR/tasks приведены к этому
правилу: миграция пропускает карточку без SKU без изменений; сбор записывает
ошибку «Не указан SKU» для этой цели до запроса/save_result. Ни поля карточки,
ни updated_at, ни цена/история не меняются; корректные соседние цели продолжают
сбор. Это уточнение требования, не одобрение всего плана или реализации.

## Проверка плана

Все четыре planning artifacts созданы: proposal, два delta specs, design,
tasks. `openspec status --change add-aliexpress-connector --json` подтверждает
isPlanningComplete=true; это только готовность плана, не реализация.
`openspec validate add-aliexpress-connector --strict` прошёл.
`git diff --check` прошёл; новые task-файлы отдельно проверяются на whitespace.
Application tests не запускались, код приложения и рабочая БД не менялись.
Следующее действие — первое human review плана и Proposed ADR 0008.

## Одобрение реализации

2026-10-26 пользователь: «Приступай к реализации». План и ADR 0008 одобрены
с уточнением: старые карточки без SKU получают индивидуальную ошибку и остаются
неизменными. Второе review ещё не пройдено. Выполняются задачи OpenSpec.

## Реализация готова к review (2026-10-26)

16/16 задач реализации и проверки выполнены. Python 175, frontend unit 63,
demo E2E 40; Rust 8 passed/3 ignored; desktop build, isolated native mixed smoke,
live Ozon+Ali, OpenSpec strict и diff whitespace passed. Живой Ali 77648.00 RUB,
Ozon 838.00 RUB; 1 productData, 0 product navigations, профиль освобождён.
Подробности, изменённые области, команды и риски: [verification](add-aliexpress-connector/verification.md).

Следующее действие — явная приёмка пользователем. Затем обновить затронутые
руководства, принять ADR, sync/archive OpenSpec и создать task-only Git commit(s).
docs/BACKLOG.md не включать. Пользовательская БД не менялась. Коммитов пока нет.

## Приёмка и финализация

2026-10-26 пользователь: «Да, сделай коммиты». Оба review gate пройдены.
Обновлены только документы затронутых областей; добавлено руководство
`docs/guide/ALIEXPRESS.md`, ADR 0008 принят. Синхронизированы две capabilities
(8 новых requirements); `openspec validate --specs --strict`: 15 passed.
Все 16 задач выполнены, change архивирован без предупреждений.
Рабочая БД не открывалась и не мигрировалась. Посторонний docs/BACKLOG.md сохранён.
