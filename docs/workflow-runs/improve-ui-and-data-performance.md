# Производительность UI и рост данных

## Объём и разрешение

2026-10-29 пользователь после исследования разрешил: «Все задачи кроме ускорения озон можно брать в работу. Вперед», затем «Продолжи» после прерывания. Объём: PERF-02/03/04/05, связанная часть ARCH-02 и пять предложенных улучшений UI. Самостоятельные ARCH-01/04/05 не были предложены как задачи производительности и в этот change не добавлены. Ускорение Ozon исключено явно.

2026-10-30 пользователь ответил «да», затем до реализации попросил подождать и объяснить таблицу/журналы. После объяснения уточнил, что нужна только небольшая диагностика, хранить все ошибки и архивы журналов не нужно. Это отменяет прежний выбор таблицы и архивирования. Следующим сообщением пользователь уточнил хранение ошибок строго только последнего запуска; исключение для других активных или последнего завершённого отменено. Обновление planning artifacts выполняется по прямому уточнению пользователя; [ADR 0010](../adr/0010-bounded-ui-diagnostics-and-logs.md) остаётся Proposed для пересмотренного решения. После уточнения «только последний запуск» пользователь 2026-10-30 дал команду «Дейсвуй»: пересмотренный план и ADR разрешены к реализации. Пользовательские данные для проверок не используются. Отдельная приёмка будущей реализации ещё не получена.

## План

[OpenSpec proposal](../../openspec/changes/archive/2026-10-30-improve-ui-and-data-performance/proposal.md), [design](../../openspec/changes/archive/2026-10-30-improve-ui-and-data-performance/design.md), [tasks](../../openspec/changes/archive/2026-10-30-improve-ui-and-data-performance/tasks.md).

1. Release baseline UI/API/error/export на изолированных данных.
2. Стабильные команды сбора отдельно от прогресса; модель каталога и memo boundaries; виртуализация списка, сетки, больших групп и редактора групп.
3. Переиспользование Intl, подготовка графика без повторных сортировок и лишних повторных вычислений, точная SQL-проекция истории.
4. Ошибки — ограниченная выборка в существующем поле: до 20 примеров/128 KiB суммарно только у последнего созданного запуска (максимальный ID), независимо от статуса. Создание следующего, включая queued/retry, атомарно очищает ошибки всех предыдущих. Поздние результаты/завершение старого запуска не восстанавливают диагностику; rollback создания сохраняет прежний набор. Точные счётчики и цели повтора независимы от выборки; compact reads не выбирают errors. Статусы complete/limited/expired проходят в UI. Отдельной таблицы нет.
5. Один журнал до 10 MiB на службу, без архивов: очистка при заполнении и перед новым запуском; после сбоя файл доступен до следующего запуска. Rust/Python pipes охватывают общий ChromeSession и numeric mode.
6. Экспорт только нужных полей истории и индекс состава групп; сравнение canonical JSON и памяти.
7. Общие проверки, native WebView, отдельная приёмка; затем документы/backlog/spec sync/archive и task commits без push.

## Исследование и ограничения инструментов

CodeGraph вернул текущий source для UI, queries, adapters и Rust/Python logging. Repowise local state соответствует HEAD `49c0473db4432eb777910b83c7146a157d250802`, но MCP overview/risk возвращает `9f3876d9ba3f`, возраст 5 дней, старые пути `price_analyzer`. Это уже наблюдалось в предыдущем workflow; индексные оценки не считаются текущим доказательством. Критические утверждения проверены по current source. Новый индекс не создавался, model-backed generation не запускалась.

Context7: React memo/context/deferred rendering, TanStack Query referential identity/structural sharing, TanStack Virtual variable measurement/rangeExtractor/scroll restoration. Это документация выбора подхода, не доказательство работы будущего кода.

Browser plugin not available (нет browser skill/runtime в каталоге). Использован установленный Playwright Chromium, viewport 1440×1000, локальный mock fixture http://127.0.0.1:5175/cards. Node v26.12.1. Production desktop сборка из предыдущего исследовательского шага прошла; после неё application source не менялся.

## Выполненный UI diagnostic

Временный harness `/tmp/pw-ui-baseline.mjs`; raw `/tmp/pw-ui-baseline.json`, screenshot `/tmp/pw-ui-baseline.png`. Harness импортирует существующий mockApi/queryClient через Vite, создаёт только in-memory каталог из шаблона карточки с новыми ID, без групп/картинок/deals. До установки синтетики дожидается загрузки исходного fixture. Полный query snapshot заменяется одной операцией; БД, пользовательские XDG и Chrome profile не используются.

Один sample на размер, development-сборка, последовательный запуск. Mount — от setQueryData до двух requestAnimationFrame; selection/search — wall clock Playwright action с ожиданием результата. Они включают автоматизацию, доступность target и планирование кадра; это не чистое CPU-time и не production p95. Время взаимодействия нельзя переносить в продуктовые обещания. Число DOM-узлов — после полного mount.

| Карточки | Mount, мс | DOM-узлы | Строки tbody | Выбор, мс | Поиск, мс |
| --- | --- | --- | --- | --- | --- |
| 100 | 1093.7 | 2853 | 100 | 1066.7 | 1498.3 |
| 1000 | 6605.2 | 27153 | 1000 | 3823.3 | 3671.1 |
| 5000 | 35307.3 | 135153 | 5000 | 13284.6 | 13476.3 |

Выбор проверял появление панели массовых действий. Поиск `Тестовый товар 4999` проверял сокращение tbody до ≤1 строки (на меньших наборах ожидается пустой результат). В каждом новом page открывалось исходное fixture; прежний выбор не переносился. В трёх успешных samples `pageerror` отсутствовали. Полная console warning/visual/mobile/native матрица не выполнялась; screenshot сделан уже после поиска, не является доказательством большого каталога.

Первый запуск harness ошибочно выбрал первый checkbox страницы (фильтр выгодных), затем ожидание панели выбора истекло. Он не входит в результаты. Селектор исправлен на checkbox внутри tbody; успешная серия выполнена заново целиком.

Вывод, который подтверждён: DOM и число строк линейно растут с каталогом; на данном dev fixture полный большой каталог дорог. Проценты ускорения будущей реализации, production p95, API latency, native CPU/RSS и качество виртуализации ещё не измерены.

## Проверки на этапе планирования (историческое состояние)

- `openspec validate improve-ui-and-data-performance --strict` — passed.
- `openspec status --change improve-ui-and-data-performance` — 4/4 planning artifacts complete; это не завершение реализации.
- Development mock diagnostic — 3/3 sizes завершены, pageerror нет; ограничения выше.
- Python/Rust/frontend regression suites и новые release/backend benchmarks ещё не запускались: application implementation пока отсутствует.
- Пользовательские данные и профили не затрагивались. Схема БД не менялась. Backlog не закрывался, main specs не синхронизировались, change не архивировался.

## Следующее действие

Пересмотрены proposal/design/tasks, два delta-specs, Proposed ADR и этот record по уточнению 2026-10-30. Дополнительно зафиксировано в артефактах строгое правило единственного последнего созданного запуска; выбор по статусу или времени завершения не применяется. Остальные UI/export решения сохранены. Разрешение продолжить с уточнённой политикой получено 2026-10-30 («Дейсвуй»); реализация начата. После него использовать openspec-apply-change improve-ui-and-data-performance и не возвращаться к отменённым таблице/архивам. Очистка старых диагностических подробностей входит в новую политику, но фактические операции с пользовательской БД сейчас не выполняются. Перед финальным завершением реализации обязательна отдельная приёмка по vibe-flow.


## Реализация: текущий checkpoint (2026-10-30)

- Команда пользователя «Дейсвуй» принята как одобрение пересмотренного плана. ADR принят для реализации; отдельная приёмка результата ещё предстоит.
- Внесены bounded latest-only diagnostics + Alembic 0017 + компактные SQL-чтения; точная projection export/history; отдельные контексты прогресса/команд; memo-компоненты каталога; виртуализация списка/сетки/больших групп/редактора; Intl и chart preparation; bounded Rust/Python process logs. Новая таблица ошибок и архивы не создаются.
- Приватная БД: `postgresql:///price_watch_rel_test?host=/tmp/pw-performance-pg/socket&port=55479`, кластер `/tmp/pw-performance-pg/data`. Создана специально для задачи. Только TEST_DATABASE_URL; пользовательская БД не использовалась. Воспроизводимые backend benchmarks используют собственные `perf_*` схемы.
- Baseline source worktree `/tmp/pw-performance-before`, commit `799064b`; не содержит implementation changes. Release mock baseline `/tmp/pw-ui-before`, сервер 127.0.0.1:5176; harness `scripts/benchmark_ui.mjs`, результаты `/tmp/pw-ui-before.json`. Измерения ещё выполняются; release after build в `/tmp/pw-ui-after`. Итоговые сравнительные замеры выполнять без параллельных тяжёлых проверок.
- Уже прошли: 38 исходных PostgreSQL checks; 8 новых diagnostic/process-log checks; 73 frontend unit; lint; 10 Rust passed/3 ignored; desktop release build; изолированный native smoke (ошибка общего запуска → retry → цена 100.10 в реальном WebView → restart API → восстановление каталога).
- Новые large-catalog E2E: 6 passed для plain/mixed/group 5000, bounded DOM/последних карточек/resize, сохранения 4999 скрытых участников, progress DOM isolation и возврата из details. Дополнительно добавлены overlay/focus и Tab-boundary проверки; полная E2E серия ещё выполняется.
- Найдена и исправлена гонка блокировок: guard диагностики должен быть отдельным shared/exclusive advisory key 578612392, не ключом import/run creation 578612391. Creators берут оба exclusive до card/run locks; writers берут shared diagnostic guard до run/target/card locks. Проверка reaper во время атомарного результата и обе migration проверки повторно прошли (3 tests).
- Первый full Python run был прерван при обнаружении этой блокировки. После него в собственной test DB остались fixtures; следующая серия корректно выявила загрязнение (7 failures/2 errors, не считается результатом приёмки). Новые migration test fixtures также отключали logging других тестов через Alembic fileConfig: их logging config теперь изолирована patch, как в существующих migration tests. Собственная public test schema очищена, полный набор запущен заново. В новых migration tests исправлен bind JSON вместо literal с `:1`.
- Обновлены E2E selectors для новых визуальных строк сетки, без ослабления проверок порядка/групп/цен/ширины. Native smoke результаты `/tmp/pw-native-smoke.log`; Rust `/tmp/pw-rust-tests.log`, build `/tmp/pw-desktop-build.log`; текущие Python/E2E `/tmp/pw-python-check.log`, `/tmp/pw-e2e-check.log`.
- До закрытия нужны: полные актуальные checks, baseline/after resource measurements, review diff/contracts/migration, документационные draft, проверка OpenSpec progress. Backlog/main specs/archive не менялись. Коммит реализации и окончательные документы — с учётом второй review gate vibe-flow; push/merge не разрешены.

## Release measurements and final regression checkpoint

Raw release UI before/after, export/error resources and catalog measurements are
retained under [implementation verification draft](improve-ui-and-data-performance/verification.md).
All nine browser cases pass p95≤200 ms, ≥30% improvement where baseline>200 ms and
bounded DOM for 1000/5000. Large export uses 21.3% of baseline peak RSS and 40.7% of
its time, identical canonical hashes. At 5000 failures exact count remains 5000,
stored samples stop at20; compact read p95 26.78→1.79 ms. Native retry/API-restart
smoke repeated successfully after Rust safety changes. Full Python219 passed;
eight updated diagnostic checks and new export concurrent-writer check passed.
Rust11 passed/3ignored; frontend73 passed before two additional chart tests.

Full E2E first final attempt:57 passed/1failed. Subsequent targeted repeat was
invalidated by editing Rust through cargo fmt while Vite was watching the frontend
root: the first page reloaded and lost its imported in-memory fixture, while both
following repeats passed. No timeout was widened and checks were not relaxed.
The test now also waits for the async menu to close after changing participation.
The current full58-test run starts after UI measurements with source edits frozen.

Catalog first comparison passes SQL3/RSS/throughput budgets, but L_writer p95
1039.7 ms vs766.4 exceeds its target. A controlled sequential L-only repeat is
queued after regression/native checks to distinguish variance; this criterion is
not marked passed yet. Additional native5000, history10000, final chart checks and
release rebuild remain. No main-guide/backlog/spec/archive changes or implementation
completion commit has been made; explicit implementation acceptance is pending.


## Реализация готова к приёмке (2026-10-30)

Полный [отчёт и сырые замеры](improve-ui-and-data-performance/verification.md)
обновлены. Финальные E2E58 passed; frontend75 passed и расширенная diagnostics
проверка4 passed; Python full219 passed, затем9 diagnostics/migration,23 reliability/
diagnostics и concurrent-export проверка passed после соответствующих последних
правок. Rust11 passed плюс отдельно3 opt-in native passed. Lint, desktop release
build, OpenSpec strict и diff whitespace passed. Native5000:11 исходных checkbox,
последняя карточка через поиск, checked grid, retry, API recovery passed. Служебные
журналы ограничены, архивов нет;512 MiB stress не оставил потоков/дескрипторов.

Контрольная L-пара без параллельных тяжёлых процессов прошла все catalog budgets:
idle p95 603.17→681.15 ms; writer767.34→696.65 ms, throughput159.87→159.24 cards/s.
History10000 p95 123.77→66.35 ms, совпадающий hash. Предыдущий шумный outlier и
промежуточный запуск с ошибочным ожиданием процесса сохранены как ограничения,
а не спрятаны за итоговым числом. Native p95 не измерен; browser p95 не переносится
на WebView. Проверки native harness потребовали исправить fixture, ввод и
accessibility role, не приложение; итоговый успешный run сохранён отдельно.

Дополнительно обнаружен PostgreSQL jsonb запрет U+0000: bounded_error заменяет
его, ставит limited и сохраняет точный результат цели; реальный DB regression
passed. Reaper пропускает payload update для expired диагностики. Repowise local
working-tree update прошёл, но MCP metadata осталась старой; critical claims
проверены по current source и runtime tests.

Следующий шаг: представить реализацию пользователю и дождаться отдельной приёмки.
После неё опубликовать подготовленные релевантные документы, обновить backlog,
sync/archive OpenSpec, проверить staged diff и создать task commits. До приёмки
реализация не объявляется окончательно завершённой; push/merge не выполняются.

После проверок остановлены только созданные для задачи preview5176/5177 и
PostgreSQL `/tmp/pw-performance-pg/data`; сырые результаты сохранены в отчёте.
Baseline worktree799064b и временные приватные fixtures оставлены для воспроизведения.


## Приёмка и закрытие (2026-10-30)

Пользователь ответил «да» на конкретный итог реализации и отчёт. Второй gate
vibe-flow пройден, включая явно указанные границы замеров: release Chromium p95
и отдельный функциональный native smoke. ADR0010 Accepted; релевантные API/data,
architecture, UI и testing guides опубликованы. Из backlog удалены PERF-02–05 и
ARCH-02, остальные задачи и ускорение Ozon сохранены. Пять main specs синхронизированы
с сохранением Purpose и остальных требований; все23 задачи закрыты.
Change перемещён в `openspec/changes/archive/2026-10-30-improve-ui-and-data-performance`.
Финальная проверка документации, ссылок, staged diff и task commit завершают работу;
push и merge не выполняются. Пользовательская БД не мигрировалась.
