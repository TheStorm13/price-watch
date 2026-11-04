# Tasks

## 1. Аспекты и точная идентичность

- [x] 1.1 После согласования плана и ADR сохранить обезличенную fixture графа 2936650207, проверить 12 достижимых SKU, цикл, недоступный сосед и объединение цвета/размера тестами parser/mapper.
- [x] 1.2 Реализовать политику членства Ozon и валидацию точной ссылки; проверить отдельными тестами разные артикулы одного семейства, чужую площадку и несовпадение ссылки/SKU. Обновить документацию товарного контракта.
- [x] 1.3 До изменения механизма обхода проверить ещё одноаспектный товар и товар с большим списком на признаки продолжения; записать evidence. Если обнаружена новая обязательная операция, пересогласовать дизайн до её реализации.

## 2. Добавление и исполнение сбора

- [x] 2.1 Заменить ограничение discovery WB/Ali на явные правила площадок, добавить Ozon в существующий цикл целей. На disposable TEST_DATABASE_URL проверить 12 точных запросов за запуск, атомарный totalCount, циклы, повторное обнаружение и stale lease.
- [x] 2.2 Обеспечить согласованную блокировку владельца SKU в add/discovery/import; проверить конкурентное добавление/обнаружение, явный конфликт двух существующих карточек и отсутствие потери истории. При необходимости forward-only ограничения проверить preflight и сохранность ID на disposable БД.
- [x] 2.3 Реализовать предел обхода и явный результат неполноты; проверить лимит, ошибку соседа, сохранение успешных результатов, точный retry без повтора успешных SKU и расширение нового обычного запуска. Обновить руководство диагностики.
- [x] 2.4 Проверить queued API/worker, расписание и direct CLI через production application paths с fixture-коннектором; подтвердить одну браузерную сессию и ограничение параллелизма существующими транспортными тестами.

## 3. Transfer, API, CLI и интерфейс

- [x] 3.1 Обновить все валидаторы transfer для членства Ozon; проверить round-trip 12 SKU, повторный импорт без дубликатов, конфликт владельца и старую одиночную карточку без переноса истории. Обновить описание экспорта/импорта.
- [x] 3.2 Проверить API вариантов, выбор главного, параметры/фото и график независимых историй; проверить обновление метаданных при прежней цене без лишней точки. Добавить frontend fixtures/tests и затронутые mock E2E.
- [x] 3.3 Обновить подсказки добавления/редактирования и CLI add/list для исходного артикула и главного SKU; проверить точное поведение при повторном добавлении известного варианта и документированные команды на disposable БД.
- [x] 3.4 Проверить оба CLI-импорта без DATABASE_URL и numeric нормализованный/raw режимы: один точный снимок, полные параметры текущего SKU, без скрытого полного обхода и без зависимости от БД. Обновить руководство режима.

## 4. Интеграционная проверка и оценка

- [x] 4.1 Выполнить релевантные Python integration suites на disposable TEST_DATABASE_URL, frontend tests/lint и затронутые mock E2E; проверить diff, текущий Repowise risk и реальные Tauri/API пути. Сохранить результаты и ограничения в workflow record.
- [x] 4.2 Проверить живой Ozon отдельно от mock UI на 2936650207 без пользовательской БД; сравнить множество и параметры с исследованием, явно отразить изменение ассортимента/блокировку, если они возникли.
- [ ] 4.3 Создать и проверить коммиты всех относящихся к задаче изменений, представить хеши, файлы, проверки и риски; дождаться явной приёмки пользователя.

## Workflow follow-up

- После приёмки синхронизировать delta specs, архивировать change, обновить только затронутую документацию и закоммитить follow-up. Не push/merge без отдельного разрешения.

## 5. Approved selective tracking refinement
- [x] 5.1 Update planning and document approved revised policy.
- [x] 5.2 Migrate default-off preferences and discovery run purpose; preserve existing data and frozen targets.
- [x] 5.3 Atomically queue initial full discovery on creation; filter ordinary collection and preserve retry semantics across all three marketplaces.
- [x] 5.4 Implement individual/bulk API, transfer, desktop/mock UI and creation feedback.
- [x] 5.5 Verify migrations, history preservation, initial discovery, ordinary selection, primary change, toggles, queue/worker/direct and numeric modes; run relevant frontend/backend checks.
- [ ] 5.6 Commit implementation and present evidence for user evaluation; await acceptance before archive.
