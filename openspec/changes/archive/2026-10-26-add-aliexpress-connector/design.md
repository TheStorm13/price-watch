# Design

## Context

См. proposal.md, ADR 0008 и docs/workflow-runs/add-aliexpress-connector/research.md.
CodeGraph показал текущий исходник: ConnectorRegistry/get_product принимает
только external_id; CollectionService открывает сессии всех площадок через
AsyncExitStack и собирает до пяти карточек. Chrome/CDP lifecycle сейчас в
AsyncOzonClient. Rust prepare_collection закрывает ручной браузер, а closer
импортирует Ozon profile_lifecycle. В UI challenge panel жёстко назван Ozon.
DB external_id — Text с уникальностью marketplace/external_id, не numeric.

## Goals / Non-Goals

**Goals:** стабильная идентичность SKU, одна точная цена, работа через текущий
профиль и общий контракт; mixed-run без конкуренции процессов за профиль.

**Non-Goals:** международная витрина .com, Choice channel, резолвинг ali.click,
поиск, минимальная цена между вариантами, получение купонов, расчёт полной
стоимости заказа, обогащение отсутствующих полей через документы карточек.
Прямой полный URL .ru из probe поддерживается. Новый числовой autodetect Ali
и новый standalone CLI не нужны: database-free lookup доступен через adapter /
ProductService, оба существующих CLI imports и numeric Ozon сохраняются.

## Decisions

### Идентичность и ввод

Выбранные альтернативы и причины — ADR 0008. Ввести AliExpressRef/parser пары
`productId:skuId`, обе части — ASCII decimal strings без преобразования в JS
number. Одна каноническая проверка на Python-границах API, CLI, transfer и store.
UI использует поле productId, отдельный обязательный skuId и заполнение из
полной .ru-ссылки. Отсутствующий/повторяющийся/конфликтующий sku_id отклоняется.
URL при создании/редактировании не может ссылаться на другую пару; при пустом
URL каноническая ссылка строится из ref. Новых настроек цен нет.

### Browser session и фабрики

Выделить `marketplace_connector/browser/session.py` и `profile_lifecycle.py`.
Перенести туда процесс, профиль, CDP connect(no_defaults), normal close, platform,
virtual display и проверку блокировок. Обновить Rust closer, Python imports,
тесты и packaging. Старые реализации/реэкспорты в ozon удалить.
Сеанс с refcount и session lock создаёт общая фабрика CLI/worker для запуска;
обоим клиентам передаётся тот же объект. Standalone клиенты создают его сами.
Ресурсы товарного транспорта остаются у соответствующего адаптера. Последний
release закрывает Chrome, ошибка acquire не оставляет ложное владение.

У Ozon сохраняются текущие composer fetch, cardPrice, raw, concurrency=5,
отмена отдельного запроса и bounded recovery. Выделять единый parser/универсальный
marketplace transport не нужно. Общий challenge lock согласует только ручное
участие между площадками, не блокируя обычные запросы.

### AliExpress adapter

Создать connectors/aliexpress/{client,json_transport,models,parser,mapper,
connector,identity}.py. Одна lazy storefront page `https://aliexpress.ru/`.
Fetch productData с credentials include, productId/sourceId=0/sku_id из ref;
канал Choice не угадывать. Проверять HTTP/content-type и data, id, activeSkuId,
единственность выбранной строки в priceList. JSON decode с parse_float=Decimal.
Параметры передавать через encode, а не конкатенацию пользовательского URL.

Пределы клиента: до 5 параллельных fetch, 5 стартов/сек с burst 5, timeout 30 с,
до 3 HTTP-попыток и до 30 с retry wait. Это клиентская политика, не официальный
лимит AliExpress. 429 с Retry-After задаёт общий cooldown. CAPTCHA/HTML-маркеры
классифицировать до обычной обработки 429. Одна согласованная recovery после
drain активных Ali fetch; повторный отказ завершает ошибкой. У каждого fetch
свой AbortController; отмена не закрывает соседнюю страницу или другой adapter.

В видимом Chrome CAPTCHA → challenge handler → ручная проверка → подтверждение
→ повторная проверка доступа и ограниченный retry. В hidden/headless режиме
инструкция открыть Chrome приложения после освобождения профиля и повторить
сбор. Это сохраняет существующий продуктовый путь Ozon. Challenge panel получает
нейтральный заголовок, сообщение содержит площадку; heartbeat остаётся активен.

### Mapping

Только выбранная строка SKU: priceWithCoupon.amount → activityAmount → amount.
Отсутствие/null пропускается, корректный 0 сохраняется. Присутствующая сумма
без корректных cents или RUB — SchemaChanged; если при in_stock отсутствуют
все три цены, это ошибка схемы без записи. Decimal(cents)/100 и общий money
normalizer. Дополнительные цены не копировать в extensions/snapshot.

availQuantity>0 → in_stock, 0 → out_of_stock/price=null; отсутствующее значение
→ unknown, повреждённое → schema error. Неизвестный itemStatus не трактовать
как удалённый товар. В этом этапе не вводить ProductNotFound для неподтверждённых
Ali-состояний. Отсутствующий запрошенный SKU — schema error.

name/gallery/rating/reviews/characteristics/description берутся из productData.
Варианты имеют отдельные ref productId:skuId и canonical URL; options используют
displayName, иначе name, без исправления противоречивых данных площадки.
Имя продавца не приходит в проверенной ручке: seller=null, без отдельного
запроса карточки ради имени. Недостающие общие поля остаются пустыми.

### Execution и persistence

Обе фабрики price_watch/cli.py используют общий builder и shared session.
AliExpress удалить из PENDING_CONNECTOR_MARKETPLACES: тогда existing queue,
schedule, retry и direct collect используют тот же путь. Проверить фильтры в
store и API, импорт/export/group membership, идентичность save_result.
Lease, атомарность, отсутствие дублей истории и локальные настройки сохраняются.
Старая AliExpress-карточка без SKU не исключается молча из целей: get_product
возвращает ошибку «Не указан SKU» до сетевого запроса. CollectionService
фиксирует ошибку цели и продолжает остальные. save_result не вызывается;
поля карточки, её updated_at, цена и история остаются прежними. Ошибка
записывается только в данные запуска, не превращается в out_of_stock.

## Migration Plan

Data-only Alembic revision: preflight до UPDATE; без активного сбора.
Перевести numeric AliExpress из сохранённых .ru URL с совпадающим item ID и
единственным sku_id. Уже канонические пары проверять, остальные площадки не
менять. Карточки без однозначного SKU пропускать, не менять ни одного их поля
и не блокировать переход. При конфликте преобразуемых идентичностей — остановить
миграцию до изменений; автоматического выбора/слияния нет. Пропущенные карточки
при следующем сборе получают индивидуальную ошибку «Не указан SKU».
Card IDs, FK, history и исторические JSON не менять; snapshots/run diagnostics
остаются историческими, новые операции используют канонические ref.
Transfer v2 с product-only AliExpress отклоняется с понятной диагностикой;
не добавлять legacy import fallback. Пользовательская БД не открывалась.

Сначала проверяется disposable migration, затем новая версия целиком; старые
реализации не сохраняются как rollback. При проблемах исправлять вперёд,
пользовательские данные не удалять. Применение к рабочей БД — отдельное действие.

## Risks / Trade-offs

- Недокументированная схема → строгая валидация, очищенные fixtures и явные ошибки.
- Shared lifecycle затрагивает Ozon → synthetic mixed-session и существующие
  browser/profile/raw/numeric regression checks, затем повторный live smoke.
- Невозможно определить старый SKU → карточка остаётся прежней, сбор фиксирует
  индивидуальную ошибку и продолжает остальные цели.
- Имя seller недоступно в JSON → null в общем контракте; не возвращать выдуманное имя.
- Регион/купон зависят от сессии → использовать профиль, не сбрасывать cookies;
  цена соответствует ответу сайта, не гарантии финальной суммы оплаты.
- Repowise MCP сообщил старый commit; bounded index-only update дошёл до persist,
  но прерван timeout 20 с. Freshness MCP не подтверждена; решения сверены с source.

## Verification

Fixture parser/mapper: три уровня цены, null/missing/zero/malformed/currency,
sku mismatch/missing/duplicate, per-SKU stock, optional fields, exact decimals.
Transport: no product goto, overlap/cancel/cooldown/recovery/CAPTCHA. Browser:
один запуск Chrome для Ozon+Ali, независимые страницы, shared challenge и normal
shutdown с synthetic cookie. Store/API/transfer: разные SKU, дубликаты и URL
validation, migration all-or-nothing, сохранение историй и настроек.
Python suite; disposable TEST_DATABASE_URL; frontend lint/unit/demo E2E/build;
Rust cargo check/tests и desktop build для переноса closer. Изолированный
native smoke проверяет контракты, live Ali и Ozon отдельно — настоящий транспорт.
