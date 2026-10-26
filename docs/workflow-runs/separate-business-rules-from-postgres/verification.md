# ARCH-03 — проверка реализации

Дата: 2026-10-26. Исходная ревизия: `89650808a3ee3402ae31205cb72ca641cc4b2b21`; after — принятое изменение ARCH-03. План и реализация одобрены пользователем отдельными сообщениями 2026-10-26. Документация и ADR финализированы после приёмки; change архивирован с 17/17 выполненными задачами.

## Что изменилось

- Чистые [правила каталога](../../../price_watch/domain/catalog_rules.py) и [политика времени](../../../price_watch/domain/collection_policy.py).
- [CatalogService](../../../price_watch/application/catalog_service.py) строит проекции из типизированных materialized inputs; [PostgreSQL reader](../../../price_watch/infrastructure/postgres/catalog_repository.py) читает их в одном REPEATABLE READ снимке.
- Явная [сборка зависимостей](../../../price_watch/bootstrap.py) и consumer-specific ports вместо двух универсальных repository-контрактов/фасада. API routes, worker и application не импортируют конкретный PostgreSQL; это закреплено AST-проверкой импортов.
- `save_result` целиком принадлежит [RunRepository](../../../price_watch/infrastructure/postgres/runs_repository.py). Lease, lock order, атомарность и идемпотентность сохранены; история — отдельный reader. Общие SQL statements переиспользуются через queries.
- Переведены API/CLI/worker, challenge handler, tests/subprocess fixtures, benchmark и desktop smoke. Старые фасад/Protocol/exports удалены без совместимых обёрток.
- Схемы БД/Alembic, данные, MarketplaceCard/TrackedCard, формулы/фильтры, HTTP/JSON, frontend и Rust-контракты не менялись. Внутренние Python imports и аргумент инъекции `create_app(services=...)` изменились.

## Изоляция данных

Создан частный PostgreSQL 18.6: `/tmp/pw-arch03-pg/data`, loopback port 55439, роль `arch03`, UTF8 БД `price_watch_rel_test`. Использовался только `TEST_DATABASE_URL` этого кластера. Пользовательские БД, профиль Chrome и XDG-каталоги не использовались.

Первоначальный тестовый кластер создал SQL_ASCII БД, несовместимую с ожидаемыми строками psycopg; только эта пустая тестовая БД пересоздана с UTF8 до baseline. После benchmark его синтетические fixtures сброшены перед окончательным полным набором: попытка запуска тестов на наполненной benchmark-БД закономерно конфликтовала с test fixture IDs и не считается результатом проверки.

## Выполненные проверки

| Проверка | Результат |
| --- | --- |
| Baseline: PostgreSQL/reliability/groups/migration | 39 passed, 4.200 s |
| Финальный `TEST_DATABASE_URL=… .venv/bin/python -m unittest discover -s tests -v` | 149 passed, 13.222 s; без skips |
| `npm --prefix frontend run lint` | Passed, TypeScript |
| `npm --prefix frontend test` | 15 files, 60 tests passed |
| `npm --prefix frontend run test:e2e` | 39 passed, 2.3 min; Playwright mock API |
| `cargo test --locked --manifest-path frontend/src-tauri/Cargo.toml` | 8 passed, 3 ignored; main/doc targets — 0 tests |
| `npm --prefix frontend run desktop:build` | Passed, release executable создан |
| Isolated native smoke, fake connector | Retry после общей ошибки, запись 100.10 из настоящего WebView и восстановление каталога после restart API passed, включая повтор на новой release-сборке |
| `git diff --check` | Passed |
| `openspec validate separate-business-rules-from-postgres --strict` | Passed; specs явно skipped, поведение не меняется |

Полный Python-набор включает прямой CLI с fake connector, queued API/worker, numeric JSON без DATABASE_URL и оба CLI imports, raw output, Decimal, import/preview/export, lease loss, rollback и retry. Добавлены unit-проверки правил и CatalogService без БД, concurrent due, инъекция clock/policy для continue/recovery, сборка проекции после закрытия DB-сессии и проверка направлений imports. Отдельно проверено закрытие DB при ошибке настройки сервисов на startup.

Три Rust native integration tests остаются штатно ignored; их нельзя считать пройденными. Успешный отдельный desktop smoke не является выполнением этих трёх тестов. Browser plugin/skill не предоставлен, поэтому использован существующий Playwright script. E2E выдаёт существующее предупреждение React Router о HydrateFallback; UI в этой задаче не менялся. Живой Ozon/реальная CAPTCHA не проверялись.

## Сравнение производительности

Одинаковая команда до и после: `TEST_DATABASE_URL=… .venv/bin/python scripts/benchmark_catalog.py --mode after --output <baseline|after>.json`. В обоих случаях `--mode after` означает текущий `/api/catalog`, а не сравнение с удалёнными endpoint. S/M/L: 100/1000/5000 карточек и по 100 точек истории; 5 прогревов + 30 измерений. Во время after-замеров frontend/native checks и индексирование уже завершены.

[Baseline](baseline.json), [after](after.json), [машинное сравнение порогов](comparison.json).

| Набор | HTTP p95, мс до → после | SQL | RSS | Записей/сек |
| --- | --- | --- | --- | --- |
| S idle | 18.8 → 16.5 | 3 | +0.3% | — |
| S writer | 22.6 → 23.7 | 3 | +0.1% | +6.1% |
| M idle | 172.7 → 155.7 | 3 | −2.9% | — |
| M writer | 189.3 → 176.0 | 3 | −1.1% | +7.2% |
| L idle | 746.0 → 661.7 | 3 | −5.2% | — |
| L writer | 824.4 → 737.5 | 3 | +4.0% | +13.1% |

Все пороги пройдены: p95 ≤ max(1.20 × baseline, baseline + 50 мс), RSS ≤ 1.20 × baseline, write-throughput ≥ 0.80 × baseline, ровно 3 SQL независимо от числа карточек. Это локальные синтетические замеры, не обещание такого же ускорения на любых данных.

## Равенство HTTP-контракта

Исходный Python-код извлечён из HEAD во временный `/tmp/pw-arch03-baseline-source`, вне рабочего дерева. Старая и новая версии по очереди прочитали одну и ту же тестовую БД без записи через ASGI `/api/catalog`. Ответы приведены к canonical JSON (sorted keys), `cmp` подтвердил полное совпадение, включая Decimal-строки, все поля и порядок элементов массивов.

- 5000 cards, 500 groups, 5000 deals.
- Одинаковый SHA-256: `7cbac4c947a0516838587ecbd7a89575b4df676762c69cd7b06f74ccab8e5089`.
- Полные 5MB ответы оставлены в `/tmp/arch03-catalog-{before,after}.json`, не добавляются в репозиторий.

## Индексные инструменты и ограничения

CodeGraph/current source использовались для навигации и проверки путей. Локальные Repowise index-only update до/после завершились, однако MCP и CLI risk продолжили выдавать старый indexed commit `9f3876d` и не разрешили новые файлы bootstrap/catalog service. Поэтому актуальная индексная оценка риска недоступна и не выдаётся за подтверждённую. Проверка затронутых путей опирается на текущие imports/source, полный тестовый набор, controlled races, desktop smoke и baseline/after.

Финальный native root: `/tmp/pw-rel-native-udid5b01`; лог `/tmp/arch03-native-final.log`. Все три проверки smoke — true. Тестовый кластер после проверок штатно остановлен; fixtures остаются только в `/tmp`.

## Приёмка

Пользователь явно принял реализацию и результаты 2026-10-26. Обновлены затронутые актуальные руководства и ARCH-03, ADR 0007 — Accepted. Change архивирован в `openspec/changes/archive/2026-10-26-separate-business-rules-from-postgres`, 17/17 задач выполнены; дельт specs нет. Изменения принятой задачи фиксируются коммитом после проверки staged diff; push/merge не запрошены.
