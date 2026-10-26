# Отделение правил приложения от PostgreSQL — ARCH-03

## Запрос и состояние

- 2026-10-26: после архитектурного анализа пользователь выбрал пункт 4 — бизнес-правила и границы PostgreSQL. Выбран vibe-flow.
- Исходная ревизия `89650808a3ee3402ae31205cb72ca641cc4b2b21`; рабочее дерево перед подготовкой было чистым.
- Состояние: реализация принята; финализация завершена. План и проект ADR одобрены пользователем 2026-10-26 сообщением «Да»; после изменения разрешений пользователь подтвердил «Продолжи».

## План

[OpenSpec proposal](../../openspec/changes/archive/2026-10-26-separate-business-rules-from-postgres/proposal.md), [design](../../openspec/changes/archive/2026-10-26-separate-business-rules-from-postgres/design.md), [tasks](../../openspec/changes/archive/2026-10-26-separate-business-rules-from-postgres/tasks.md), [проект ADR 0007](../adr/0007-application-rules-and-persistence-boundaries.md).

Чистые domain rules; CatalogService над одним согласованным набором входов; небольшие порты; композиция PostgreSQL-адаптеров вместо наследования; целый атомарный writer результата в RunRepository. Решение о due run выполняется под advisory lock. Без изменения product rules/HTTP/JSON/БД, новых зависимостей и compatibility wrappers.

## Согласования

- Gate 1: получено явное одобрение proposal/design/ADR (2026-10-26).
- Gate 2: пользователь принял реализацию и результаты отдельным сообщением «Да» 2026-10-26.
- Коммиты/архивирование — только после приёмки по vibe-flow; публикация не запрошена.

## Исследование и проверки

- Переиспользованы подтверждённые текущим исходным кодом findings предыдущего анализа; дополнительно проверены API composition/routes, общие ошибки, transfer transactions, все импорты заменяемых классов в tests/scripts и benchmark.
- Проверены действующие specs каталога, групп, выгодности, расписания и исполнения. Поведенческих дельт нет; явно используется skip_specs.
- Repowise MCP ранее вернул устаревший обзор с прежней привязкой проекта. Локальные `repowise update ... --index-only --no-workspace --no-agents` и `repowise risk --path ... --target ...` не вернули результат и были прерваны (exit 130); обновление индекса и оценка риска не подтверждены. До реализации повторить адресную оценку по текущему репозиторию. Выводы плана основаны на current source/CodeGraph, ADR и specs, а не на устаревших индексных оценках.
- `openspec status`: все planning artifacts готовы, specs явно skipped. `openspec validate separate-business-rules-from-postgres --strict`: passed. Проверка ссылок/путей и whitespace planning files выполняется отдельно; приложение не тестировалось.
- Тесты приложения, PostgreSQL и benchmark на стадии планирования не запускались; план проверок и пороги определены в design/tasks. Пользовательские данные не использовались.

## Следующее действие

Оба review завершены. Актуальная документация обновлена, ADR 0007 принят, change архивирован с 17/17 задачами; дельт specs нет. Результат фиксируется коммитом принятой задачи без push/merge.

## Реализация 2026-10-26

- Отдельный кластер `/tmp/pw-arch03-pg/data`, порт 55439, роль arch03, UTF8 БД price_watch_rel_test. Изначальная SQL_ASCII тестовая БД пересоздана до baseline; пользовательские БД не используются.
- Baseline PostgreSQL: 39 tests passed (4.2 s), `/tmp/arch03-baseline-tests.log`.
- Чистые правила: 4 unit tests passed, `python -m unittest tests.test_application_rules -v`.

- Локальный index-only update завершился; Repowise MCP/первый CLI risk ещё возвращали commit 9f3876d, поэтому их исторические оценки не использованы. Повторные local update/risk выполняются после рефакторинга.
- Полный Python-набор на disposable TEST_DATABASE_URL: 148 tests passed (13.375 s). После локальной правки continue на общий pure predicate целевой набор правил/каталога/reliability/import boundaries: 25 tests passed (1.789 s).
- Frontend `npm --prefix frontend run lint`: passed; `npm --prefix frontend test`: 15 files / 60 tests passed.
- Browser plugin/skill отсутствует; demo E2E запущен существующим Playwright-скриптом. Frontend/Rust исходники не менялись.
- Изолированный live desktop smoke: retry после общей ошибки, цена 100.10 в настоящем WebView, восстановление каталога после перезапуска дочернего API — passed. Root `/tmp/pw-rel-native-1cm6fc3r`, лог `/tmp/arch03-native.log`; screenshots `/tmp/price-watch-rel-native-{start,before,after}.png`. Это fake Ozon в отдельных XDG/профиле/БД, не проверка живого маркетплейса.

- Итоговые проверки и performance: [verification](separate-business-rules-from-postgres/verification.md). Финальный Python: 149 passed; E2E: 39 passed; Rust: 8 passed / 3 ignored; release build passed. Все performance-пороги пройдены, canonical HTTP-каталог на 5000 cards идентичен baseline.

- Повторный smoke после release build: passed, `/tmp/arch03-native-final.log`, root `/tmp/pw-rel-native-udid5b01`. Тестовый PostgreSQL штатно остановлен после проверок. После явной приёмки задача 4.5 отмечена выполненной; архивирование завершено, изменение подготовлено к коммиту.

## Финализация

- 2026-10-26: явная приёмка реализации получена. Обновлены architecture overview, guide/ARCHITECTURE, guide/DATA_AND_API, testing guide, ARCH-03 и ADR index.
- ADR 0007 — Accepted. OpenSpec: 17/17 задач, skip_specs; change находится в `openspec/changes/archive/2026-10-26-separate-business-rules-from-postgres`. Основные specs не менялись.
- После проверки staged diff все изменения принятой задачи фиксируются одним коммитом; hash проверяется через git log и сообщается пользователю. Push/merge не выполняются.
