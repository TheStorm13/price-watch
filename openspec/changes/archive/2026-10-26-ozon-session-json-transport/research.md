# Исследование Ozon: текущий поток и проверка ручки

Дата: 2026-10-26. Код price-watch: `03009fb`. Локальный референс:
`~/DevProjects/ozon-researcher/.local/ozon-mcp`, commit `414b3470ee6dd6f3197598b2c3c640d5d1601ef3`.
Путь, первоначально указанный как `ozon-researche`, отсутствует; найден `ozon-researcher`.
Внешний референс: https://github.com/SZhukovWork/ozon-mcp .

## Текущий поток

1. [Desktop CollectionProvider](../../../../frontend/src/features/collection/CollectionProvider.tsx) вызывает Tauri `prepare_collection` перед запуском/повтором API-сбора. [Rust prepare_collection](../../../../frontend/src-tauri/src/lib.rs) штатно закрывает ручной Chrome приложения, освобождая профиль.
2. [CLI](../../../../price_watch/cli.py) создаёт OzonConnector/AsyncOzonClient и для `collect`, и для worker. [Worker](../../../../price_watch/worker/worker.py) забирает запуск из очереди и вызывает [RunExecutor](../../../../price_watch/application/run_executor.py). Heartbeat и lease продолжают действовать во время ожиданий. [CollectionService](../../../../price_watch/application/collection_service.py) открывает общую collection_session и ограничивает одновременные цели числом 5.
3. [AsyncOzonClient](../../../../marketplace_connector/connectors/ozon/async_client.py) запускает системный Chrome с постоянным user-data-dir и локальным CDP, получает основной контекст. В desktop-сборе используется Xvfb; профиль хранит авторизацию и выбранный адрес/регион. Отдельного API изменения региона в коннекторе нет.
4. Для каждого товара fetch_raw_text_async создаёт вкладку, делает goto `/product/{sku}/`, проверяет DOM/title на антибот, затем evaluate(fetch(API_URL, credentials: include)). То есть товарные данные уже берутся из JSON, а не DOM. DOM используется для проверки доступа. Запрос пока не имеет AbortController, HTTP-статус не проверяется при непустом теле, нет общей частотной паузы или Retry-After. finally закрывает вкладку.
5. [Connector](../../../../marketplace_connector/connectors/ozon/connector.py) передаёт OzonResponse.raw_text в [parser](../../../../marketplace_connector/connectors/ozon/parser.py), затем [mapper](../../../../marketplace_connector/connectors/ozon/mapper.py) создаёт [MarketplaceCard](../../../../marketplace_connector/domain/models.py). JSON-дроби читаются как Decimal. Ошибка несоответствия SKU/названия — MarketplaceSchemaChanged.
6. CollectionService превращает только ProductNotFound в успешный out_of_stock без цены; остальные ошибки сохраняет как ошибки цели. Поэтому транспорт не должен бросать ProductNotFound для 403, пустого тела или общего 404. Результаты/история пишутся прежним репозиторием под lease.
7. [Числовой CLI](../../../../marketplace_connector/connectors/ozon/cli.py) использует тот же коннектор через ProductService, а raw вызывает клиент напрямую. [main.py](../../../../main.py) импортирует оба CLI, числовой режим не требует DATABASE_URL.
8. Закрытие ресурсов: существующий [profile_lifecycle](../../../../marketplace_connector/connectors/ozon/profile_lifecycle.py) вызывает CDP Browser.close; клиент ждёт завершения процесса и только при зависании применяет аварийное завершение. Это сохраняется.

Поиска по Ozon и загрузки списка/текстов отзывов в рабочем коннекторе нет. Поиск в UI относится к локальному каталогу. Наличие review score не означает отдельную операцию reviews.

## Соответствие полей

Во всех строках текущий источник уже является JSON composer. Предлагаемый транспорт возвращает тот же документ; менять значения и приоритеты источников не требуется.

| Поле MarketplaceCard | Текущий источник и приоритет | Источник после миграции |
| --- | --- | --- |
| ref.marketplace | константа ozon | без изменения |
| ref.external_id | pageInfo.analyticsInfo.sku → webStickyProducts.sku → seo Product.sku → запрошенный SKU; проверка совпадения | те же поля page/json/v2 |
| title | webProductHeading.title → webStickyProducts.name → seo Product.name | те же поля |
| url | seo.link canonical → seo Product.offers.url | те же поля |
| price | только webPrice.cardPrice; Decimal, normalize_price, null для out_of_stock | то же cardPrice, без подмены обычной/старой ценой |
| availability | явно заданный webPrice.isAvailable → seo Product.offers.availability → unknown | без изменения трактовки |
| image_url | первая корректная HTTPS-картинка webGallery (images/gallery/items) → seo Product.image → webAspects выбранного SKU data.coverImage | без изменения |
| seller.external_id | число из webStickyProducts.seller.link → webCurrentSeller.header.badge.subscribed.common.action.params.sellerId | без изменения |
| seller.name | webStickyProducts.seller.name | без изменения; отсутствие продавца допустимо |
| seller.rating | webCurrentSeller.rating.title.text | без изменения, Rating Decimal со шкалой 5 |
| rating.value | webReviewProductScore.totalScore → seo Product.aggregateRating.ratingValue | тот же общий рейтинг; не подменять webSingleProductScore |
| rating.reviews_count | webReviewProductScore.reviewsCount → seo Product.aggregateRating.reviewCount → 0 | без изменения |
| attributes | webShortCharacteristics.characteristics: title.textRs[].content и values[].text | тот же короткий набор, без обогащения полными характеристиками |
| description | seo.script application/ld+json, @type Product, description → пустая строка | тот же JSON, не DOM и не расширенное описание второй страницы |
| variants | webAspects: sku/link/data.title/data.searchableText/availability; уникальность ref, selected по текущему SKU | те же варианты, без запроса модального окна всех вариантов |
| collected_at | OzonResponse.received_at, UTC aware | локальное время успешного получения ответа |
| extensions | пустое отображение по умолчанию | без изменения |

## Реальная операция и условия

- Bootstrap: `GET https://www.ozon.ru/`, один owned page в основном контексте существующего профиля.
- Товар: `GET https://www.ozon.ru/api/composer-api.bx/page/json/v2?url=%2Fproduct%2F1604900984%2F`.
- Параметр url — целиком percent-encoded внутренний путь `/product/{sku}/`, метод GET, тела нет. В проверке не использовался старый дополнительный `__rr=1`.
- Выполнение: evaluate async JavaScript fetch, `credentials: include`, accept application/json. Cookies/сессионные токены обслуживает сам Chrome. Перенос в HTTP-клиент не проверялся и не предлагается.
- Нужна действующая Ozon-сессия именно этого браузера. Авторизация/регион из price-watch профиля сохраняются; новый регион программно не задаётся. Никакие адреса/координаты/токены из ответа не выгружаются.
- У этой операции нет обхода страниц результатов: один документ на SKU. Варианты из webAspects — существующее бизнес-поведение, а не обещание всех возможных вариантов. Пагинация search/reviews не нужна, поскольку соответствующих операций в приложении нет.
- Успех: подходящий HTTP-статус, JSON object, widgetStates object и товарные данные, проходящие существующую проверку идентичности/названия. Значения некоторых необязательных полей могут отсутствовать по контракту.
- Отсутствие товара: прежнее точное свидетельство parser — pageType search, URL `/search/?product_id=<запрошенный SKU>`, отсутствие товарных heading/price. Пустой документ, произвольный search и общий 404 недостаточны.
- Ошибки: access status/redirect, HTML, блокирующий JSON вместо composer, таймаут, malformed JSON и изменение схемы различаются; 429 требует cooldown/Retry-After. Наблюдались 200 и 403; остальные ветки будут проверяться детерминированными тестами, а не объявляться наблюдавшимися.

## Наблюдения Network и результат

В доступных CUA-поверхностях браузеров не оказалось, поэтому проверка выполнена Playwright/CDP через существующий браузерный слой. Пользователь явно разрешил профиль price-watch. Временный скрипт подключается к уже открытому Chrome этого профиля, если его CDP endpoint совпадает с DevToolsActivePort; иначе запускает его штатным клиентом. Существующие вкладки не закрывает. БД не открывает. Данные ответа остаются в памяти, наружу выводятся только технические признаки и количества.

- Свежий временный профиль системного Chrome: главная 403, ручка 403 application/json с ключами блокировки incidentId/supportURL/timeoutSec/blockURL; значения не сохранялись.
- Профиль price-watch: главная 200; ручка 200 application/json; размер текста около 204 тысяч символов. Получены webProductHeading, webPrice, webStickyProducts, webCurrentSeller, webReviewProductScore, webShortCharacteristics, webAspects, webGallery и seo.
- Существующие parser/mapper вернули правильный SKU, непустые название/цену, in_stock, продавца/рейтинг/картинку/описание, 5 характеристик и 13 вариантов.
- Никакого goto на `/product/` в проверке не было. После домашней страницы выполнен ровно один явный товарный GET page/json/v2.
- Network главной дополнительно показал GET `_action/v2/shellHorizontalMenuGetChildV1`, GET `_action/summaryV2`, POST `_action/v2/getSearchTapTags`, POST widget/json/v2, POST `_action/v2/addressBookBarTooltip`, все 200. Это фоновые запросы главной; в новый клиент эти операции не добавляются, их тела/персональные данные не копируются. Нужные товарные поля пришли одним GET.
- Проверка системного Chrome с профилем была достаточной; запрошенная дополнительная проверка свежего Chromium из референса прервана пользователем и успешной не объявляется.
- Дополнительный пример по запросу пользователя: SKU 1634943359 получен тем же способом, HTTP 200, без открытия карточки. Существующий mapper вернул цену cardPrice 604.00, in_stock, 5 характеристик и 13 вариантов; нормализованный товар сохранён в `/tmp/ozon-product-1634943359.json`. Параллельная группа из пяти запросов пока не проверялась.

## Зафиксированное требование параллелизма

Пользователь явно потребовал сохранить асинхронное выполнение с параллелизмом **5 по умолчанию**. Референс сериализует запросы, но эту часть мы не переносим. Общая страница должна поддерживать до пяти независимых in-flight fetch; шестой ждёт. Начальная локальная частотная политика — 5 стартов в секунду с burst 5, без секундной паузы между каждым запросом. Retry-After задаёт общий cooldown; восстановление выполняется single-flight после завершения активных запросов, отмена отдельной задачи затрагивает только её fetch. Это план, а не уже проверенные свойства реализации.

## Референс и отличие от него

Прочитаны browser.py (долгоживущая страница, fetch/AbortController, сериализация, min_interval, session challenge, регион), client.py (page/url encoding, валидация, повторы, детали товара/widget/action, search/reviews), parse.py (composer widget decoding, prices, product mapping и location). Референс подтверждает исходную идею, а работающий price-watch профиль подтверждает нужный маршрут и существующие поля. Мы не переносим его режим региональных setters, дополнительные операции, browser-state.json или другую семантику цен/рейтингов.

CodeGraph вернул текущий исходный код. Repowise MCP дал историю lifecycle и риски async_client, но сообщил индекс старого commit `9f3876d9ba3f` и не разрешил новый parser.py; его результаты используются как исторические подсказки, критические выводы проверены текущим исходником. Обновление локального индекса без генерации документации (persisted docs_enabled=false) и команда status зависли без итогового результата и были остановлены; обновлённость MCP-индекса не подтверждена. Перед применением можно повторить ограниченное index-only обновление; автоматическая model-backed генерация не требуется.

## Проверки реализации

Транспорт: shared page/no product goto; пять одновременных запросов начинают работу до завершения любого, шестой ждёт; общий bootstrap без гонок; proper URL/credentials; HTTP 403 JSON; HTML/invalid JSON/wrong root/widgetStates; unrelated/mismatched SKU; 429 Retry-After numeric/date/invalid/long plus shared cooldown при конкурирующих ответах; transient 5xx/timeout; retries используют общий лимит 5; single-flight recovery дожидается активных запросов; отмена отдельного fetch не прерывает соседние; cancellation during backoff/challenge; normal resource closure and reentry. Сравнение скорости старого/нового транспорта — при одинаковом параллелизме 5.

Контракты: test_normalizer, test_decimal_contract (включая точный raw), test_connector_contract, test_price_watch_cli (оба импорта, database-free numeric, direct/queued contract), test_collection_service, test_profile_lifecycle. Затем полный Python suite; отдельно сообщить пропущенные PostgreSQL/live тесты. Интеграционные БД — только disposable TEST_DATABASE_URL, пользовательскую БД не использовать. Повторить live на профиле с несколькими fetch и технической сводкой без персональных данных, измерить время и число навигаций. Demo frontend E2E не проверяет Ozon и не считается доказательством транспорта.

## Проверка реализованного транспорта

2026-10-26: в разрешённом профиле price-watch выполнен live batch из пяти разных SKU (1604900984, 1634943359, 1607687714, 1641499399, 1607686851). Network зафиксировал 5 одновременно выполнявшихся product fetch, 1 home navigation и 0 product navigations. Новый пакет — 0.809 с; baseline из Git HEAD с product goto при том же параллелизме 5 — 2.971 с и 5 product navigations. Публичные поля каждого результата, кроме времени получения, совпали. Повторный fetch в том же сеансе — 0.160 с; новый сеанс с тем же профилем — 0.407 с. Время старта Chrome не включено; порядок/кэш не рандомизированы, это наблюдение одного запуска, а не гарантия ускорения.

Полный отчёт о synthetic/browser/profile/CLI/collection проверках и ограничениях сохранён в [workflow record](../../../../docs/workflow-runs/ozon-session-json-transport.md). Сырые ответы, cookies и персональные сведения не сохранялись. БД не использовалась. Старый транспорт был загружен только во временный benchmark-процесс и в production-коде не сохранён.
