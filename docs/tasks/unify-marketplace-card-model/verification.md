# Проверка единого MarketplaceCard

Статус: реализация принята пользователем 2026-10-25 запросом коммитов всех
изменений и чистого дерева. Руководства обновлены, ADR принят, specs
синхронизированы, change архивирован. Рабочее дерево содержит
предшествующие изменения, поэтому HEAD 9f3876d не описывает проверенную версию.

## Изменения

| Область | Результат |
| --- | --- |
| Общий домен | MarketplaceCard вместо ProductSnapshot; Decimal-цена и прежние товарные поля, без локального ID и настроек |
| Отслеживание | TrackedCard с ProductRef; TrackedCardOverview для локальной записи и текущих метрик |
| Ozon | OzonResponse → OzonProductParser → OzonProductData/OzonPrice → OzonMapper.to_card → MarketplaceCard |
| PostgreSQL | Прежние таблицы, ID, FK, NUMERIC и транзакции; новые JSONB snapshots 2.0, старые документы без переписи |
| API/CLI | Десятичные строки денег; товарный JSON 2.0; v2 import/export со строками; строгий отказ числовому вводу цены |
| CLI/packaging | Одиночный CLI в marketplace_connector/connectors/ozon/cli.py, оба main импортируются; ozon_article_json и заменённые facade удалены |
| Frontend | TrackedCardView, DecimalString, точные сравнения/форматирование и диапазон; number только для геометрии графика |
| Mock | Точные рациональные средние и BigInt-арифметика тестового стенда; сериализация периодической средней до 20 знаков |
| Уведомления | Однократная миграция storage v1→v2 с сохранением pending/watermark, включая повреждённый документ цен |

Прежние правила названия, наличия, cardPrice, выбора изображения, групп,
выгодности, dedup истории, lease и retry сохранены. Схема Alembic и файлы
ревизий сверены с исходным состоянием задачи: изменений нет.

## Автоматические проверки

- Python: `TEST_DATABASE_URL=<disposable> .venv/bin/python -m unittest discover -s tests -v`.
  Полный набор: 113 тестов, включая PostgreSQL, reliability, миграцию и группы.
  После уточнения OpenAPI-схемы строкового импорта дополнительно прошли
  22 теста API и денежного контракта.
  Есть отдельный запуск реального main.py collect с fake connector и queued
  POST /api/runs → CollectionWorker на disposable БД: цена 12.345 → 12.35,
  локальное название сохранено, повторный успех не добавляет историю.
- `npm --prefix frontend test`: 60 тестов, 15 файлов.
- `npm --prefix frontend run lint`: TypeScript пройден.
- `npm --prefix frontend run test:e2e`: 39 сценариев пройдены.
  Новый сценарий импортирует строковые 9.90/10.00, проверяет порядок списка
  и плитки и точную цену tooltip. В самом сценарии нет pageerror/console.error.
  В общем стенде сохраняется прежнее предупреждение React Router HydrateFallback.
- `cargo test --locked --manifest-path frontend/src-tauri/Cargo.toml`:
  8 passed, 3 ignored с явными требованиями native-среды.
- `npm --prefix frontend run desktop:build`: release binary собран.
- Изолированный `dbus-run-session -- xvfb-run ... python scripts/smoke_reliability_desktop.py`:
  реальный Tauri/WebView → API → worker → отдельный PG; общий сбой, повтор,
  Decimal 100.10 и восстановление каталога после перезапуска API пройдены.
  На снимке настоящего WebView проверено отображение 100,10 ₽.
- JSON Schema 2020-12: схема и три состояния наличия проверены jsonschema
  с FormatChecker. Валидатор установлен только в /tmp, зависимости проекта
  не менялись. Контракт image_url совпадает с фактическим выводом.
- `compileall`, `git diff --check`, `openspec validate ... --strict`, синтаксис
  shell packaging и статический состав release-источников проверены.

Первоначальный CLI-test зависал в sandbox при завершении asyncio executor;
после снятия sandbox он проходит без изменения обработки терминального ввода.
У Rust был старый generated cache с абсолютным путём article_json_parser:
пересобраны только соответствующие Cargo-пакеты, исходники Rust задачи не менялись.
Браузерный plugin/skill отсутствует; использован существующий Playwright workflow.
Во время промежуточного прогона правка frontend вызвала Vite HMR и ошибки
контекста; финальные 39 сценариев выполнены на новом сервере без правки исходников.

## Производительность каталога

Одинаковый harness, 5 прогревов и 30 измерений, ASGI HTTP с сериализацией,
100/1000/5000 карточек и 100 точек на карточку. БД исключительно disposable,
сервер PostgreSQL в /tmp с локальным Unix socket. Порог: p95 не выше
max(1.20×baseline, baseline+50 мс), без роста числа SQL-запросов.

| Набор | p95 baseline, мс | p95 after, мс | SQL after | Порог |
| --- | ---: | ---: | ---: | --- |
| S_idle | 18.1 | 23.5 | 3 | Пройден |
| S_writer | 22.8 | 21.6 | 3 | Пройден |
| M_idle | 219.6 | 178.4 | 3 | Пройден |
| M_writer | 177.9 | 197.3 | 3 | Пройден |
| L_idle | 683.3 | 726.4 | 3 | Пройден |
| L_writer | 1613.6 | 796.9 | 3 | Пройден |

Исходные данные: [baseline](catalog-baseline.json), [after](catalog-after.json).

Первый after замер пересекался с другими проверками и показывал снижение
write-throughput L. Сериализация API ограничена денежными полями вместо
wildcard для всех полей. Дополнительно выполнен последовательный повтор L
без параллельных проверок: [baseline L](catalog-l-baseline.json),
[after L](catalog-l-after.json). p95 под записью 737.9→785.7 мс (+6.5%),
write-throughput 163.6→155.5 карточки/с (−5.0%). Порог p95 пройден.
Это synthetic-проверка, а не измерение текущего Ozon.

## Ревью и ограничения

CodeGraph продолжает отказывать по изменённым файлам. Repowise обновлён;
get_change_risk выполнен, его вывод review_required рассмотрен вручную.
Он считает текущий price_watch новым деревом из-за прежнего незакоммиченного
переименования; находки сложности catalog/import относятся к существующим
алгоритмам. Ozon mapper проверен по прежним fixtures и новым Decimal-тестам;
в новую задачу ARCH-03 не добавлялся.

Настоящий сетевой ответ Ozon в этой реализации не запрашивался. Mock E2E не
является проверкой живых служб; для них выполнен отдельный native smoke.
Полный release-архив не выпускался: скрипт требует чистого закоммиченного дерева.
Проверены desktop binary, синтаксис скриптов, пути источников и новый CLI;
новых внешних runtime-зависимостей нет.

В исходном дереве price_watch не отслеживался Git, а price_analyzer уже был
удалён. Пользователь отдельно разрешил включить в коммиты все текущие изменения,
в том числе исходный перенос пакета и предшествующие правки. До этого
разрешения staging и коммиты не выполнялись. Временный
PostgreSQL остановлен после проверок; пользовательские службы не затрагивались.
