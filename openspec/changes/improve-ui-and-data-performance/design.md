# Design

## Context

Объём и мотивация — в proposal.md. CodeGraph подтвердил текущие CardsPage, CollectionProvider, queries, PriceChart, runs/history/transfer adapters и actual Rust/Python log paths. Repowise MCP всё ещё возвращает индекс `9f3876d9ba3f` и прежние названия: его risk не считается текущим доказательством. Критические выводы основаны на текущем source, а не на старых risk scores.

Предыдущие API baseline/after из separate-business-rules-from-postgres не являются замером UI: на 5000 карточек HTTP p95 after был 661.7 мс idle и 737.5 мс writer, 3 SQL. Перемерить на том же текущем HEAD, а не сравнивать новый результат с другим окружением. Первичный development UI diagnostic сохранён в workflow record и доказывает линейный DOM.

## Goals / Non-Goals

**Goals:** bounded DOM и отзывчивые взаимодействия при 5000 карточек, включая одну большую группу; атомарные ошибки без переписывания массива; компактное чтение прогресса; ограниченные журналы непрерывно работающих процессов; меньше лишних данных и памяти в экспорте/истории.

**Non-Goals:** ускорение Ozon; новые правила цен/выгодности; снижение точности денег; прореживание/удаление истории; перестройка runtime вне необходимого владения логами; server pagination и streaming export как неподтверждённая смена контрактов. Эти два последних варианта не объявляются реализованными или ненужными: если измерения потребуют их, потребуется новый план.

## Decisions

Конкретное решение, альтернативы и миграция описаны в [ADR 0010](../../../docs/adr/0010-bounded-ui-diagnostics-and-logs.md), пока Proposed:

1. Сохранить snapshot API; виртуализировать плоские записи списка и визуальные ряды сетки, включая участников больших групп. `@tanstack/react-virtual` — единственная предлагаемая новая зависимость, с фиксацией версии и lockfile. Измерять высоты, resize, стабильные ключи и позицию возврата. Вынести модель и memo boundaries; сохранить доступность, focus pinning и владельца открытых overlays.
2. Разделить команды/стабильные признаки сбора и динамический прогресс. Потребитель команд не получает обновлений счётчиков. Существующие completion refresh и DealNotifications сохраняются. Не заменять polling на новый push-протокол. Отдельно оценить стоимость recent-runs polling: компактная проекция исключает чтение ошибок без изменения интервала обнаружения фонового запуска.
3. Отдельная append-only таблица диагностики с индексом `(run_id,id)`, транзакционным переносом всех старых payload и удалением старого столбца. Компактность довести через API → port → adapter → SQL; отбрасывание errors только при сериализации не считается выполнением.
4. Единая size/age log policy через управляемые pipes, без бесконечных очередей и внешней службы. Охватить native API/PG/Xvfb, worker, ручной Chrome и общий ChromeSession. Предел — 10 MiB × 4 файла на поток; 14 дней для архивов. Тесты используют уменьшенные лимиты и управляемое время.
5. Экспорт и history/chart выбирают точные столбцы, группируют через Map/dict и сохраняют прежние transaction/JSON contracts. Не менять import merge/compaction. PriceChart сохраняет все точки и разрывы наличия, min/max сравниваются точно, renderer memoized. Formatter cache хранит только фиксированные Intl formatter instances, не бесконечные значения дат.

## Verification and acceptance

- UI fixture: 100/1000/5000 карточек, без групп; смешанные группы; одна группа на 5000. Список/сетка, открытые/закрытые группы, 4000 selected в редакторе. Отдельные release browser и Tauri WebView результаты. 5 warmups + 30 samples, p50/p95, DOM, long tasks, память где доступна, ошибки console. Development diagnostic не входит в приёмочные p95.
- p95 input/selection/sort/view/group-search ≤200 мс. Там, где baseline >200 мс, также улучшение ≥30%. В фиксированном viewport 5000 и 1000 должны отличаться не более чем на 20% по rendered catalog nodes (overscan/focus pinning ограничены); полной snapshot model это условие не касается. Последняя карточка доступна; повторяющиеся IDs/пропуски отсутствуют.
- Profiler/instrumentation: 30 обновлений только progress не коммитят неизменившееся представление каталога. Изменение реальных данных и terminal status обновляет каталог и уведомления.
- API catalog: scripts/benchmark_catalog.py на disposable `price_watch_rel_test`, одинаковые fixtures и isolation. p95 ≤max(1.20×baseline,baseline+50 мс), RSS ≤1.20×baseline, writer throughput ≥0.80×baseline, 3 SQL. Использовать прямой ASGI benchmark, не mock.
- Errors: 0/100/1000/5000 payload одинаковой длины, success/failure/recovery, duplicate delivery, lost lease, concurrent retry. Проверить SQL columns и отсутствие обращения к errors table на compact reads. Замеры добавления по квартилям, время всей серии и прогресс p95; не объявлять отсутствие квадратичности по одному короткому запуску.
- Export: 100/1000/5000 cards ×100 history, с реалистичным крупным snapshot в БД. Сравнить canonical JSON v2, Decimal, порядок, группы, concurrent write snapshot. RSS/время до/после; целевой RSS для большого экспорта ≤0.75×baseline, время ≤1.10×baseline. Если порог не пройден, исправить или согласовать новый контракт; не закрывать PERF-05 формально.
- Logs: активная бесконечная запись stdout+stderr, длинная строка, restart во время rotation, age cleanup без новых записей, файловая ошибка и остановка. Проверить bounded disk/RSS/threads/descriptors и читаемую свежую диагностику. Не тестировать на пользовательских логах.
- Existing Python, frontend unit/E2E/lint, Rust tests, desktop build; isolated native smoke. CLI imports `main.py --help`, collect help и numeric JSON path без DATABASE_URL; реальный marketplace fetch не нужен для проверки неизменности маршрута, network smoke отдельно обозначается.

## Migration Plan

До изменения схемы завершить/остановить owned services и создать штатную резервную копию. Alembic 0017 последовательно создаёт новую таблицу, копирует с ordinality, проверяет полноту/порядок/содержимое и удаляет старое поле атомарно. SQL миграции обязан отказать до изменений при активном writer, включая heartbeat/worker; старый бинарник после upgrade запускать нельзя. Автоматический runtime restart уже должен использовать новую версию writers.

Сбой транзакции миграции оставляет старую схему и данные. После успешного upgrade используется только новая схема; legacy writer/dual-read не сохраняются. Возврат через восстановление backup — отдельная явно разрешаемая операция, не скрытая ветка приложения. Тесты pre-upgrade revisions продолжают проверять собственную историческую схему.

## Risks / Trade-offs

- Полный каталог остаётся O(N) по payload/parse/model → измерять отдельно и документировать результат, не обещать бесконечную масштабируемость.
- Virtualization может нарушить table/grid/focus/scroll → test матрица выше и native smoke обязательны.
- Блокировка writers при переносе → upgrade только на остановленных службах; тест отказа и сохранности.
- Pipe drainer может зависнуть из-за потомка, удерживающего fd → проверка bounded shutdown и явного владения процессами/дескрипторами.
- DI/IPC/dynamic paths могут отсутствовать в графе → проверить current source, Tauri invoke и native execution отдельно.

Архитектурная реализация начинается после принятия предложенного ADR; broad разрешение пользователя записано отдельно и не подменяет принятие конкретной миграции/архитектуры.
