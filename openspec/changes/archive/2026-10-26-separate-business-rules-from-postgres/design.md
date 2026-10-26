# Design

## Context

Мотивация и границы — в [proposal](proposal.md). Исходная ревизия: `8965080`; до подготовки плана дерево было чистым. Текущее устройство подтверждено CodeGraph и исходниками:

- `infrastructure/postgres/catalog_repository.py:get_catalog` читает группы, последние состояния и метрики тремя SQL-запросами в REPEATABLE READ, затем в Python определяет deals и представителя.
- `runs_repository.py:create_due_run` под `_RUN_CREATION_LOCK` проверяет активные запуски, время последнего полного запуска и 6 часов. `stale_cutoff` читает окружение и время прямо в инфраструктуре; worker импортирует эту функцию.
- `repository.py` объединяет шесть областей множественным наследованием. `HistoryRepository.save_result` вызывает `_begin_result` из RunRepository и `_overview_statement` из CardRepository через `self`.
- API dependencies и DatabaseChallengeHandler называют конкретный PostgreSQL-класс; CLI, tests и benchmark создают его напрямую. Текущий Protocol описывает только часть исполнения.
- `get_statistics` в деталях считает среднюю за период; каталог считает среднюю предыдущих точек, исключая последнюю. Эти показатели намеренно различаются и не объединяются рефакторингом.

Обязательны ADR 0004–0006, действующие specs `catalog-snapshot`, `deal-selection`, `group-card-metrics`, `scheduled-collection`, `collection-run-execution`. Поведение не меняется, поэтому specs пропущены явно, а не заменены архитектурными требованиями.

## Goals / Non-Goals

**Goals:** чистые проверяемые правила; типизированные границы без ORM/HTTP; явное владение транзакциями и зависимостями; полный перевод потребителей без совместимых обёрток.

**Non-Goals:** новые формулы средних, фильтры групп, времена последней проверки, настройки расписания, новые коннекторы, фабрика Ozon (ARCH-04), новый desktop supervisor (ARCH-01), хранение ошибок (PERF-03), пагинация и оптимизация транспорта. CRUD и import/merge не переписываются ради симметрии; существующий чистый `domain/history_merge.py` переиспользуется.

## Decisions

### 1. Чистые правила в домене, проекция каталога в application

Предлагаемые модули:

- `domain/catalog_rules.py`: оценка выгодности и выбор представителя. Входы — типизированные значения с Decimal; без SQLAlchemy, Pydantic, HTTP, окружения и системного времени.
- `domain/collection_policy.py`: неизменяемая политика полного сбора (6 часов) и lease timeout; функции получают `now` явно. Timeout сохраняет нынешнее `max(15, RUN_STALE_SECONDS)`, default 30 секунд. Конфигурация читается в точках сборки; динамической настройки через UI нет.
- `application/catalog_service.py`: преобразование согласованных входов в cards/groups/deals с общими правилами. Вычисляет deals один раз и использует тот же результат для представителя и `has_member_deals`.
- `application/catalog_models.py`: типизированные входы и выходы проекции. `CatalogInputs` содержит локальные карточки с последним состоянием, SQL-метрики по ID и метаданные групп; типы не содержат ORM Row/Record и объектов с ленивой загрузкой. API-сериализация остаётся в schemas/HTTP-границе.

Сохранить точные условия: `deals_enabled`, последнее состояние in_stock с ценой, `baseline_days >= 1`, известная средняя и строгое `price < average`; сортировка deals по убыванию savings и ID. Ноль — допустимая цена; не заменять `is not None` проверкой truthiness. Средние не округлять до сравнения.

Представитель выбирается из полного состава: минимальная известная цена независимо от наличия, затем меньший ID; если цен нет — меньший ID, если состав пуст — None. Все товарные метрики принадлежат представителю; выгодность других участников влияет только на отдельный признак. Фильтры остаются во frontend и не участвуют в выборе.

Альтернатива: вынести только пару функций и оставить проекцию в PostgreSQL-классе. Меньше diff, но application по-прежнему не владеет каталогом. Альтернатива: перенести всю агрегацию истории в Python. Не выбрана: лишние данные, память и риск N+1.

### 2. Адаптер читает один снимок; application не делает дополнительных запросов

PostgreSQL CatalogReader возвращает полностью материализованный `CatalogInputs` из одной read-only REPEATABLE READ транзакции. Число запросов остаётся три для текущей реализации независимо от числа карточек. После закрытия транзакции CatalogService синхронно собирает все проекции из этих данных.

`get_catalog` как метод PostgreSQL-фасада удаляется. `/api/catalog` и ответы мутаций групп используют один CatalogService. Чтение карточки/истории/графика сохраняет прежнюю семантику; CatalogService не подменяет статистику за выбранный период. Уведомления получают прежний HTTP-каталог и прежние `lastCollectionRunId`.

Альтернатива: CatalogService последовательно вызывает отдельные readers cards/groups/metrics. Не выбрана: раздельные транзакции могут смешать версии, общий UoW на уровне API был бы лишней сложностью.

### 3. Политика расписания выполняется под транзакционной защитой

RunRepository получает чистую CollectionPolicy и UTC clock через конструктор. В `create_due_run` порядок сохраняется: transaction → advisory lock → чтение текущих активных запусков и последнего полного запуска → решение чистой политики → выбор целей и создание одного queued запуска → commit.

В application/worker не переносится последовательность «прочитать → решить → записать» с отдельными транзакциями. Порт очереди предоставляет атомарную операцию `create_due_run`, а не открывает SQL-сессию вызывающему коду. Вызов чистого правила из адаптера допустим: правило принадлежит домену, а гарантия конкурентности — PostgreSQL.

Устаревание определяется той же политикой с явно заданным временем, используется одинаково для recovery и continue. Сохранить строгую границу `< cutoff`, fallback heartbeat → started_at, текущие статусы и ownerless recovery. Прямой запуск продолжает recovery до создания, worker — до расписания. Heartbeat 5 секунд, polling и частота проверки расписания не меняются. `stale_cutoff`, его импорт из worker и прежние вызовы в RunRepository удаляются.

Источник отсчёта остаётся существующий `started_at`: сейчас он записывается при создании queued запуска и не меняется при claim. Не вводить здесь новое время фактического старта. Ошибочный полный запуск переносит срок, одиночный и retry — нет. Политика не хранит состояние и не читает БД.

### 4. Порты по потребителям; один адаптер может реализовать несколько портов

Предлагаемые контракты в `ports`:

| Порт | Потребитель и ответственность |
| --- | --- |
| `RunExecutionStore` | Executor/CollectionService: direct start, targets, heartbeat, current, save success/error, finish/fail |
| `RunQueueStore` | Worker и API runs: recovery, due/queued/retry creation, claim, get/list |
| `RunChallengeStore` | Challenge handler и continue: waiting, owned status, continue |
| `CatalogReader` | CatalogService: один согласованный набор входов |
| `CardStore` | API/CLI: создание, изменение, удаление и чтение карточек |
| `HistoryReader` | API/CLI: история, график, statistics, count |
| `GroupStore` | API groups: изменение метаданных и состава |
| `TransferStore` | API import/export: существующий атомарный контракт |

Описать только реально вызываемые операции с аргументами/результатами; не создавать сервис-обёртку для каждой операции. Один RunRepository реализует execution/queue/challenge. Общие исключения (`NoCards`, `ConnectorNotAvailable`, `CardAlreadyExists`, `CardInActiveRun`, `ImportDuringRun`) переносятся из PostgreSQL в независимый `domain/errors.py`; HTTP-маппинг кодов/сообщений сохраняется.

Точки сборки (`api/app.py`, CLI/bootstrap) создают PostgreSQL-адаптеры с явными зависимостями. Для API `ApiServices` — типизированный набор зависимостей на границе запуска; routes получают отдельные зависимости из dependencies, не ищут сервисы в контейнере самостоятельно. Подмена `create_app(repository=...)` в тестах переводится на новую инъекцию `services`; это Python-breaking изменение, не HTTP. Executor, worker и challenge handler получают нужные порты напрямую и не импортируют bootstrap/SQLAlchemy/PostgreSQL.

Альтернативы: один огромный Protocol закрепляет прежнее смешение; generic Repository/UoW framework добавляет абстракции без потребителя. Обе не выбраны.

### 5. Композиция областей вместо наследования; writer результата остаётся целым

Удалить PostgresPriceWatchRepository. CardRepository, RunRepository, HistoryRepository, GroupRepository, TransferRepository и CatalogReader становятся самостоятельно создаваемыми адаптерами с явным `AsyncDatabase`. Сборка создаёт конкретные адаптеры, не проксирует их методы через новый универсальный фасад.

Общие statement-builder для последнего состояния и SQL-агрегаций — явные функции в PostgreSQL-модуле queries, переиспользуемые адаптерами. Это инфраструктурные функции, не порты и не сервисы. Не дублировать SQL из-за удаления наследования.

`save_result` перемещается из HistoryRepository в RunRepository: запись относится к результату цели запуска, а не к независимой операции истории. RunRepository владеет всей транзакцией `_begin_result` → проверка ref → блокировка карточки → обновление метаданных → условная история. История становится reader. Отдельный ResultWriter-класс не нужен, пока нет самостоятельного потребителя.

Неизменны lock order run → target → card, SQL проверки lease, статус pending, условное обновление счётчиков и rollback всей транзакции при ошибке. Неизменная цена всё равно фиксирует succeeded без новой истории. Не вызывать самостоятельно коммитящие методы CardRepository/HistoryRepository из writer. Transaction import/export и блокировка запрета импорта во время запуска также остаются целыми.

## Risks / Trade-offs

- [Потеря атомарности при разделении классов] → writer результата целиком в одном адаптере, integration rollback/lease/races до и после.
- [Расхождение rules и SQL-метрик] → SQL готовит те же Decimal-агрегаты; fixtures покрывают дроби, ноль, None, один день базы и равенство цены средней.
- [ORM за границей транзакции] → материализация в типизированные inputs и тест построения проекции после закрытия чтения.
- [Незамеченные потребители удалённого фасада] → CodeGraph references плюс адресный поиск импортов в tests/scripts/exports; обновить fake repositories и benchmark/smoke.
- [Увеличение числа типов] → только перечисленные используемые порты, одна CatalogService, без UoW framework, DI-библиотеки и повторных forwarding layers.
- [Регрессия скорости] → baseline/after на одной disposable БД, прежняя агрегация и три SQL-запроса, критерии ниже.

## Migration Plan

1. Зафиксировать baseline HTTP-каталога, бизнес-результатов и исполнения на синтетических данных. Исторические отчёты не заменяют новый baseline.
2. Ввести правила и чистые тесты, затем CatalogInputs/Service и reader.
3. Выделить policy/clock и порты; заменить наследование и перенести writer как одну операцию.
4. Перевести все точки сборки, API, CLI, worker, challenge handler, tests и scripts; удалить заменённый фасад, общий Protocol, старые импорты/exports. Промежуточные состояния не выпускать.
5. Пройти проверки, представить результат пользователю. Только после явной приёмки обновить актуальные архитектурные docs и ARCH-03, принять ADR, архивировать change и создать коммит(ы) по vibe-flow. Исторические ADR не переписывать.

Схема/ревизия Alembic, JSONB snapshots, история и пользовательские настройки не мигрируются. Смешанные версии Python-пакетов не поддерживаются; при установке законченного изменения перезапустить API/worker/desktop вместе. Откат через сохранение старого кода или параллельных адаптеров не проектируется; при дефекте исправлять новый путь.

## Verification and acceptance

- Unit: deal eligibility (Decimal, 0, None, equality, availability, enabled, baseline); representative (empty, null/ties, unknown availability); schedule (нет полного запуска, 6 часов − ε / ровно / + ε, active, failed full, single/retry); timeout (default/minimum, граница, heartbeat fallback).
- Existing Python: `tests.test_collection_service`, `tests.test_api`, `tests.test_decimal_contract`, `tests.test_price_watch_cli`, `tests.test_connector_contract`, history merge и связанные fixtures. Проверка импортов обоих CLI и numeric JSON без DATABASE_URL; Ozon заменён детерминированным fake.
- Disposable PostgreSQL: полный существующий набор `test_postgres_integration`, `test_run_reliability`, `test_group_metrics_integration`, `test_reliability_migration`; сохранить проверки writer между чтениями каталога, конкурентных due/retry, lease loss, rollback и неизменной цены. Дополнить только отсутствующие сценарии новых границ.
- Матрица режимов: API queued → worker, direct collect без worker, numeric JSON без БД; challenge wait/continue и heartbeat; import preview/import/export. Сетевой I/O коннектора остаётся вне транзакций.
- Baseline/after: `scripts/benchmark_catalog.py --mode after` на S/M/L до изменения и после, в одной среде, без записи и с записью. Harness требует отдельную disposable `price_watch_rel_test` и сбрасывает только её синтетические fixtures; существующие пользовательские БД не использовать. До запуска убедиться, что TEST_DATABASE_URL указывает именно на созданную для задачи БД.
- Приёмка performance: одинаковый payload/Decimal-значения на фиксированных данных; три SQL-запроса каталога без роста от числа карточек; p95 ≤ max(1.20 × новый baseline, baseline + 50 мс), peak RSS ≤ 1.20 × baseline, write-throughput ≥ 0.80 × baseline. Сравнивать записи с одинаковой изменяемостью состояния. Превышение блокирует приёмку, а не объясняется рефакторингом.
- Поиск запрещённых зависимостей: domain не импортирует infrastructure/API, application/worker не импортируют PostgreSQL/HTTP, routes не импортируют concrete repository. Исключения только в точках сборки API/CLI и явно инфраструктурных harness.
- Frontend typecheck/unit и существующий demo E2E проверяют сохранение HTTP-контракта. Изолированный live desktop smoke с fake connector проверяет wiring Tauri → API → worker → disposable БД; demo E2E не считается его заменой. Rust tests/build нужны, если миграция Python packaging/wiring затронет desktop-сборку.

На стадии планирования эти проверки не запускались. Невозможность выполнить необходимую интеграцию или benchmark должна быть явно представлена на review и не считается пройденной проверкой.
