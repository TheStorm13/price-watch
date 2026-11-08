# Task: Исправить lifecycle, обработку ошибок и повторный парсинг коннекторов

## Goal and acceptance criteria

Исправить все находки ревью текущих Ozon, AliExpress и Wildberries, кроме
дублирования транспортов Ozon/Ali: пользователь явно считает его допустимым.
Сохранить отдельные реализации площадок, HTTP-пулы по 100, последовательные
стадии Ozon → Ali → WB и отсутствие планового ограничения стартов/с.

Критерии результата и проверки:

1. `UnsafeBrowserTeardown` при загрузке аспектов Ozon выходит до сборщика,
   прекращает прогон и не превращается в успешную карточку с discovery warning.
   Проверка: регрессия аспектов и интеграция с остановкой CollectionService.
   Обычный отказ необязательной модалки сохраняет уже полученную цену.
2. Незавершающиеся native Promise подготовки WB (`getXinfo`, `getUserGrade`,
   `setDiscountForUnAuth`) не оставляют сбор висеть. Проверка: synthetic Chrome
   с зависшим каждым helper; отсутствие новых запросов после остановки,
   завершение всех waiters, сохранение рабочего shared bootstrap при отмене
   только одного waiter. Очередь HTTP вне request timeout проверяется отдельно.
3. После временного сбоя bootstrap WB следующий разрешённый application retry
   создаёт новую страницу/задачу; параллельные waiters одного bootstrap получают
   его исходный результат. Проверка: сбой → успех, общий concurrent bootstrap,
   очистка частично созданной страницы, отмена и закрытие.
4. Большой/бесконечный Retry-After завершает попытку ошибкой без sleep и без
   преждевременного повторного HTTP. Допустимый Retry-After соблюдается.
   Проверка границ бюджета, HTTP-date, отсутствующего/некорректного заголовка,
   NaN/Infinity и отмены ожидания; не добавлять RPS-планировщик.
5. Для одного товарного ответа Ozon/Ali нет повторного JSON-декодирования,
   product parsing и полного mapping в следующих слоях. Проверка: наблюдение
   вызовов на реальном adapter path вместе с проверкой результата; Decimal,
   точная SKU identity, цены, варианты и collected_at не меняются. Отдельные
   ответы модалок остаются отдельными документами.
6. WB освобождает состояния поколений кошелька после завершения всех их
   потребителей и response inspections. Проверка: много последовательных и
   перекрывающихся поколений, поздний ответ старого поколения, отмена/recovery;
   число удерживаемых состояний зависит от живой работы, а не всех прошлых SKU.
7. WB принимает решения о доступе/recovery по структурированному HTTP status,
   а не подстрокам exception message. Проверка: 401/403/498, 429, 5xx, изменение
   текста ошибки без изменения поведения; ограниченное recovery сохраняется.
8. Неиспользуемый keyword `validate` удалён из Ozon raw API и всех callers.
   Raw-режим остаётся строго проверяемым и возвращает исходный текст без
   модификации, не запускает discovery модалок. Проверка raw CLI без БД,
   malformed JSON/schema, отсутствующий товар и неизменность вывода.

Изменений пользовательских данных, миграций БД и новых зависимостей нет.
Прежний Ali N=8 эксперимент и его backlog-диагностика не входят в эту задачу.

## Current system and evidence

База: HEAD `8d14aad`, реализация pool=100 — `804f742`. Рабочее дерево перед
планированием чистое. Предыдущая задача `shared-request-dispatcher` находится
на приёмке; эта задача не означает её принятия или архивирования.

Проверенные источники:

- [Ozon aspects](../../../marketplace_connector/connectors/ozon/aspects.py):
  `complete_aspects` ловит все Exception в загрузке модалки и внешнем цикле.
- [WB runtime](../../../marketplace_connector/connectors/wildberries/runtime.js):
  deadline цикла не прерывает зависший `await getXinfo`; wallet helpers также
  ожидаются без watchdog. `waitNative` применяется только к товару/метаданным.
- [WB transport](../../../marketplace_connector/connectors/wildberries/transport.py):
  `_bootstrap` не сбрасывается после ошибки, `_profiles` только пополняется,
  `_route`/`_fetch_article` ищут HTTP-коды в тексте исключений.
- [Application retry](../../../marketplace_connector/application/retry.py):
  допускает `sleep(inf)` и не различает превышение retry budget и разрешённую
  паузу. Транспортные `max_retry_wait=30` не защищают внешний retry.
- [Ozon transport](../../../marketplace_connector/connectors/ozon/json_transport.py),
  [client](../../../marketplace_connector/connectors/ozon/async_client.py),
  [connector](../../../marketplace_connector/connectors/ozon/connector.py):
  один ответ повторно парсится в трёх слоях; mapper вызывается до и после клиента.
- [Ali transport](../../../marketplace_connector/connectors/aliexpress/json_transport.py),
  [connector](../../../marketplace_connector/connectors/aliexpress/connector.py):
  повторные parser/mapper. Ozon `fetch_raw_text_async(validate=...)` игнорирует flag.

В уже выполненном ревью 42 существующих теста прошли. Четыре временных
воспроизведения подтвердили поглощение Unsafe, запрос sleep(inf), один
new_page на два неудачных WB fetch и зависший WB после 10× request_timeout.
Browser reproduction использовало отдельный временный профиль и synthetic
storefront без запросов к площадке. Повторять эти воспроизведения до исправления
не требуется: оформить устойчивые регрессионные проверки с исправлением.
Численного benchmark повторного парсинга нет; обещания прироста скорости нет.

Repowise live-git review предыдущего изменения указало на сложность WB bridge;
его MCP history/test map отстаёт от локального индекса, поэтому выводы о дефектах
основаны на текущем source и воспроизведениях, а не оценках сложности.

## Agreed solution

Статус: план явно согласован пользователем 2026-11-08: «Качественно подойди
к изменениям. Я даю добро». Объединение Ozon/Ali исключено. Реализация начата;
приёмка результата остаётся отдельным human gate.

### Ошибки и retry

В обоих catch-слоях `complete_aspects` немедленно пробрасывать
`UnsafeBrowserTeardown`; CancelledError продолжает выходить наружу. Ошибки
необязательного discovery остаются локальными предупреждениями.

Добавить структурированный признак возможности application retry в RateLimited
(например `retry_allowed`, default true) и конечный бюджет внешнего ожидания
30 секунд. Транспорты помечают превышение своего max_retry_wait как non-retryable;
внешний retry не теряет этот признак. Дополнительно внешний слой отклоняет
положительную Infinity и конечное ожидание >30с независимо от источника ошибки.
Не сокращать серверную паузу до 30с с последующим ранним запросом: при превышении
бюджета сразу вернуть исходную ошибку. NaN/отсутствующий/некорректный заголовок
используют существующую конечную fallback-паузу; отрицательное ожидание не
создаёт отрицательный sleep. Допустимое ожидание сохраняет минимум 1с и одну
application retry. Число transport attempts и остальные типы retry не менять.
Мигрировать все producers RateLimited, включая WB/эксперименты, при необходимости.

В WB завести adapter-private HTTP error с числовым `status`, совместимый с
существующей категорией MarketplaceUnavailable. `_route` и `_fetch_article`
используют status; текст остаётся только диагностикой. 429 сохраняет RateLimited.

### WB bootstrap и владение состояниями

Shared wallet bootstrap получает watchdog незавершившегося native runtime.
Он измеряет время без принадлежащего bootstrap queued/active HTTP; ожидание
слота не расходует HTTP timeout. HTTP timeout по-прежнему начинается после
admission и покрывает body. Не ставить простой общий wall-clock timeout на
весь fetch или wallet: это вернуло бы ошибку таймаута очереди.

Watchdog должен охватывать каждый потенциально незавершающийся helper, а не
только внешний цикл. При невозможности подтвердить завершение native работы
остановить собственную WB-страницу и пробросить UnsafeBrowserTeardown; не
освобождать несуществующее владение и не продолжать сбор с неизвестным I/O.
Отмена одного waiter отсоединяет только его, shared bootstrap нужен остальным.
Предусмотреть ограниченную реакцию на потерю/неотзывчивость page evaluation,
не вводя deadline на HTTP queue; использовать существующие abort/close механизмы.

Временный сбой `_start` нормализуется в MarketplaceUnavailable; частично
созданная страница закрывается с корректной очисткой handlers/state. После
завершившейся временной ошибки следующий fetch может atomically заменить
bootstrap task. Не сбрасывать выполняющуюся задачу, CancelledError при закрытии,
schema/fatal errors и не создавать бесконечный bootstrap retry loop.

Поколения wallet имеют явное владение: bootstrap и ожидающие его article
evaluations удерживают нужное состояние до завершения inspections. Привязать
article к поколению при join bootstrap (до ожидания результата), чтобы поздний
потребитель не получил состояние нового профиля по fallback. Удалять поколение
после освобождения последнего потребителя и завершения его response tasks;
чистить при навигации/закрытии. Не удалять предыдущий профиль просто при
появлении следующего. Новый handler возврата/отмены освобождает reference в finally.

### Единственный разбор товарного ответа Ozon/Ali

Оставить отдельные transport/client/parser/mapper для каждой площадки.
Перенести владение product parsing и mapping в один adapter pipeline:
transport выполняет HTTP/access/content-type checks и отдаёт исходный текст;
adapter декодирует и строго проверяет документ один раз, строит ProductData,
для Ozon завершает aspects и затем один раз строит MarketplaceCard.

Внутренние response-модели переработать под этот pipeline: исходный raw_text,
received_at и проверенные данные/итоговая card передаются между слоями без
повторного разбора. Connector возвращает готовую card. Выбрать минимальную
форму без параллельных устаревших полей/веток и мигрировать все fake clients.
Для raw API использовать тот же validation pipeline без discovery; вернуть
оригинальный raw_text. Подтверждённый ProductNotFound сохраняет различие:
raw Ozon может вернуть валидный документ отсутствующего товара, product path
поднимает ProductNotFound. Не выкидывать строгую проверку consumed widgets,
non-finite JSON numbers, SKU/валюты/цены ради сокращения числа вызовов.

Время collected_at фиксируется один раз после получения товарного body;
ожидание аспектов не меняет время цены. Decimal и native WB price не менять.
Удалить no-op `validate` и все его передачи; compatibility adapter не нужен.

Это исправления внутри существующей архитектуры, без нового общего транспортного
слоя, dispatcher или ADR. Сохраняются общий Chrome owner, native WB SDK,
пулы100 и stage ordering. Ключевые риски: очистить wallet generation слишком
рано, превратить watchdog в queue timeout, ослабить raw validation при переносе.
Регрессионные проверки ниже прямо покрывают эти случаи.

Постоянная документация: обновить соответствующие разделы
`docs/guide/OZON.md`, `ALIEXPRESS.md`, `WILDBERRIES.md`,
`TESTING_AND_TROUBLESHOOTING.md` и контракт ошибок/retry в применимых
`openspec/specs/collection-run-execution/spec.md`/`docs/guide/ARCHITECTURE.md`.
Обновлять только реально затронутые разделы. Старые ADR/отчёты не переписывать.
BACKLOG не использовать для параллельного task tracking и не закрывать Ali N=8.

## Implementation and verification plan

- [x] Исправить propagation Unsafe в Ozon и конечный budget application retry;
  обновить RateLimited producers, включая сверхбюджетные WB ответы. Проверить
  аспекты, product retry, Retry-After границы и остановку всего run при Unsafe.
- [x] Исправить WB bootstrap: watchdog native helpers, контролируемый повтор
  временного старта, cleanup и отмена. Проверить synthetic browser зависания
  каждого helper, partial startup, один отменённый waiter и живого соседа,
  HTTP queue wait за пределами HTTP timeout, отсутствие orphan requests.
- [x] Заменить WB string matching на typed HTTP errors и добавить безопасное
  освобождение wallet generations. Проверить recovery once, persistent refusal,
  текст ошибки, перекрывающиеся поколения, delayed body и очистку после серии.
- [x] Перестроить отдельно Ozon/Ali pipeline под однократный parse/map;
  мигрировать response models, client/connector, raw paths, эксперименты и
  test doubles. Удалить validate. Проверить точные Decimal/SKU/цены/время,
  raw byte-for-byte output, schema errors, Ozon variants и ProductNotFound.
- [x] Проверить затронутые execution paths: queued CollectionService/RunExecutor
  (desktop/API/worker), `main.py collect`, числовой Ozon JSON/raw CLI без
  DATABASE_URL и оба CLI imports. Запустить релевантные существующие transport,
  browser, mapper/parser, retries, variants и orchestration tests; pool100/101,
  stage ordering и отмену сохранить. Если нужна DB-проверка persistence,
  использовать только disposable TEST_DATABASE_URL. Не тестировать user DB.
- [ ] Обновить затронутые постоянные документы, проверить diff, compile/checks
  по конфигурации проекта и strict OpenSpec validation. Зафиксировать результат
  коммитом, обновить CodeGraph/Repowise и настроенные страницы, представить
  конкретный результат на приёмку. Live smoke не является обязательным для этих
  локальных дефектов; если потребуется для runtime integration — только текущий
  стабильный профиль, закрывать свой Chrome и пауза ≥10с между попытками,
  остановиться на первом access refusal/CAPTCHA. Не утверждать live проверку,
  если выполнены только synthetic tests.

## Execution state

План согласован 2026-11-08. Реализованы ошибки/retry, WB bootstrap/поколения,
структурированные HTTP errors и pipeline Ozon/Ali. Объединения транспортов нет.

Проверено на текущих изменениях:
- 106 adapter/parser/mapper/CLI/variant tests: OK, 11 DB-зависимых пропусков.
- 34 WB transport/browser tests: OK, включая зависания каждого profile helper,
  renderer probe, bootstrap retry, wallet queue вне timeout, pin/release поколений.
- 27 shared-browser/pipeline/identity/mapper tests: OK. Включены один decode/parse/map
  на pipeline, строгий raw, ProductNotFound, время цены и Ozon Unsafe до RunExecutor.
- Отдельная серия execution/browser/experiment: 65 прошли, один старый caller
  нового response API найден в shared browser test, исправлен и перепроверен
  в серии 27 выше. Ошибка запуска несуществующего test_aliexpress_mapper исправлена
  выбором существующих модулей. Фактических сбоев продукта в этих двух случаях нет.

Сохранён standalone parser Ozon для текста с префиксом, покрытый существующим
тестом. HTTP pipeline использует строгий parse_json: один JSON decode, затем
parse Mapping; это сохраняет прежний полезный parser contract без ослабления raw.
Renderer probe разделён между evaluations и кэшируется на 0.5с, чтобы 100 задач
не создавали 100 одинаковых ping. Закрытие WB страницы ограничено 2с;
неподтверждённое закрытие даёт UnsafeBrowserTeardown.

DB-проверка: 73 tests OK (postgreSQL integration, Ali/WB integration,
run reliability, variant tracking, Ozon ownership и Ozon variants) на собственном
временном кластере `/tmp/pw-connector-fix-db-332v5ouu`; pg_ctl fast stop успешен.
Рабочая БД и профиль пользователя не использовались.
Финальная серия после review-коррекций: 61 tests OK (pipeline, retries, Ozon
aspects, WB transport/browser), включая невалидные aspect rows и потерю renderer
probe без orphan evaluation. Изменённый shared browser caller проверен в серии 27.
compileall, node --check обоих WB scripts, импорты обоих CLI без DATABASE_URL,
git diff --check и strict OpenSpec validation успешны. Отдельных Python lint/type
checks в проекте не настроено; frontend не менялся. Live-проверок не было.
Repowise live diff findings рассмотрены: warnings о сложности WB/retry не
доказывают дефект, критичные переходы покрыты перечисленными проверками;
устаревшее MCP предложение про frontend lockfile к этому diff не относится.
Обновлены пять guides и постоянный collection-run-execution contract.
Остаются коммит/refresh индексов и страниц, затем presentation на приёмку.
Приёмка и архивирование не состоялись.
