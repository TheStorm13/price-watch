# Tasks

Реализация начинается только после явного одобрения proposal/design/ADR. Каждый этап включает собственные проверки; текущие команды и результаты записываются в workflow-run. Актуальные пользовательские/архитектурные руководства обновляются после приёмки реализации согласно vibe-flow.

## 1. Baseline и независимые правила

- [x] 1.1 На созданной для задачи disposable TEST_DATABASE_URL зафиксировать baseline действующих PostgreSQL-тестов и S/M/L benchmark текущего `/api/catalog` в режиме `after` с записью и без; сохранить команды, ревизию, payload, SQL, p95, RSS и write-throughput в отчёте. Проверка: отчёт не использует пользовательские данные и содержит пригодные для сравнения результаты.
- [x] 1.2 Выделить `domain/catalog_rules.py` с Decimal-оценкой выгодности и выбором представителя; добавить unit-тесты на equality/0/None, availability, enabled, baseline, пустые группы и ties. Проверка: новый набор проходит без БД/SQLAlchemy и совпадает с существующими fixtures групп/выгодности.
- [x] 1.3 Выделить `domain/collection_policy.py` с шестичасовым сроком и lease timeout; добавить unit-тесты границ срока/устаревания, активных запусков, default/minimum timeout. Проверка: тесты используют фиксированное now без sleep/окружения и подтверждают прежние строгие сравнения.

## 2. Согласованные входы и сборка каталога

- [x] 2.1 Ввести типизированные `CatalogInputs`, выходную проекцию и порт CatalogReader; PostgreSQL читает полностью материализованные данные за три запроса в одной read-only REPEATABLE READ транзакции. Проверка: нет ORM за портом; integration writer между частями чтения не смешивает версии.
- [x] 2.2 Создать CatalogService, использующий чистые rules и один набор deals для карточек/групп; добавить unit fixtures Decimal, empty groups и метрик представителя. Проверка: одинаковые порядок, поля, None, savings, baseline и lastCollectionRunId с baseline.
- [x] 2.3 Перевести `/api/catalog` и ответы мутаций групп на CatalogService; адаптировать API schemas для новой типизированной проекции без изменения JSON. Проверка: `tests.test_api`, `tests.test_decimal_contract`, `tests.test_group_metrics_integration` и каталоговый integration проходят; статистика details остаётся отдельной.

## 3. Порты и явная композиция хранения

- [x] 3.1 Описать RunExecutionStore, RunQueueStore, RunChallengeStore, CardStore, HistoryReader, GroupStore, TransferStore с используемыми операциями; перенести общие ошибки в domain и обновить HTTP mapping. Проверка: существующие ошибки API сохраняют status/code/message, порты и ошибки не импортируют infrastructure/HTTP.
- [x] 3.2 Сделать PostgreSQL-области самостоятельными adapters с явным AsyncDatabase; переиспользовать named SQL helpers вместо наследуемых методов. Проверка: constructors/queries работают отдельно, отсутствуют cross-mixin `self` calls и дублирование запросов latest/metrics.
- [x] 3.3 Перенести `save_result` целиком в RunRepository вместе с использованием `_begin_result`; HistoryRepository оставить reader. Проверка: integration rollback, неверный ref, duplicate delivery, lease loss и успех без новой истории сохраняют атомарность, счётчики и порядок блокировок.
- [x] 3.4 Подключить policy/clock к RunRepository; решение due оставить под advisory lock, recovery/continue использовать одну политику; убрать stale_cutoff из infrastructure и импорт worker. Проверка: concurrent due, граница 6 часов, failed full, single/retry, stale ownerless и живой waiting проходят на disposable БД.
- [x] 3.5 Собрать ApiServices и CLI/worker dependencies явно; перевести executor, collection service и DatabaseChallengeHandler на порты. Проверка: `tests.test_collection_service`, API, challenge/reliability и CLI-наборы проходят, application/worker не импортируют concrete PostgreSQL.
- [x] 3.6 Перевести все tests/fakes, subprocess fixtures, `scripts/benchmark_catalog.py`, `scripts/smoke_reliability_desktop.py` и package exports; удалить PostgresPriceWatchRepository и прежний PriceWatchRepository. Проверка: адресный поиск не находит старые runtime-импорты/definitions, tests/scripts используют новую сборку без compatibility facade.

## 4. Проверки сквозных сценариев и review

- [x] 4.1 Запустить полный Python-набор с отдельным disposable TEST_DATABASE_URL, включая PostgreSQL/reliability/group/migration; явно записать skips/failures. Проверка: подтверждены queued API → worker, direct collect, challenge wait/continue, retry, lease/rollback и import preview/import/export.
- [x] 4.2 Проверить imports обоих CLI и numeric JSON без DATABASE_URL с детерминированным fake Ozon; проверить packaging затронутых Python-модулей. Проверка: режим не создаёт БД и сохраняет нормализованный JSON/raw-контракт.
- [x] 4.3 Повторить S/M/L benchmark в том же окружении и сравнить с 1.1: три запроса без N+1, идентичные данные, p95/RSS/write-throughput в пределах design. Проверка: отчёт с числами и pass/fail для каждого набора/режима, превышение блокирует приёмку.
- [x] 4.4 Выполнить frontend typecheck/unit и demo E2E, изолированный live desktop smoke с fake connector и временными XDG/БД; при изменении packaging/wiring собрать desktop и выполнить Rust checks. Проверка: HTTP-контракт и реальный Tauri → API → worker путь подтверждены отдельно; невозможные проверки явно обозначены.
- [x] 4.5 Проверить diff, направления imports и отсутствие заменённых путей; представить пользователю изменённые файлы, результаты, performance и риски. Проверка: получена отдельная явная приёмка реализации перед завершением workflow.

## Workflow follow-up

- После явной приёмки обновить только затронутые `docs/architecture/overview.md`, `docs/guide/ARCHITECTURE.md`, `docs/guide/DATA_AND_API.md`, testing guide при изменении команд; отметить ARCH-03, принять ADR 0007 и добавить его в ADR index. Проверить соответствие текущему коду и ссылки.
- Дельт specs нет (`skip_specs: true`); не переписывать действующие требования ради рефакторинга. Архивировать change после review, проверить архив и обновить workflow-run.
- Проверить staged diff, создать один или несколько коммитов принятой задачи с tests/docs/OpenSpec, убедиться в наличии коммитов и сообщить hashes. Не push/merge.
