# Task: Общий диспетчер запросов Ozon, AliExpress и Wildberries

## Goal and acceptance criteria

Ввести одну точку управления конкурентными запросами всех поддерживаемых коннекторов. Пользователь согласовал названия и стартовую настройку: `max_in_flight_requests = 100`, фиксированную на время сбора; `in_flight_requests` и `pending_requests` — изменяемое состояние. Плановые ограничения M стартов в секунду запрещены. Требуется план общей переработки; реализация ещё не согласована.

Критерии и проверки:

- Один dispatcher на ChromeSession, один общий лимит 100 для смешанного запуска, а не по 100 на площадку. Барьерный браузерный тест блокирует ответы и доказывает: первые 100 управляемых запросов допущены, 101-й ожидает; после одного завершения допускается один следующий без плановой паузы.
- Все управляемые товарные HTTP-запросы, вспомогательные JSON-запросы и повторы трёх коннекторов проходят через эту точку. Нативные запросы WB тоже учитываются. Проверка сетевыми событиями реального Chrome на синтетических ответах, не только mock Page.evaluate.
- Нет старых card-level семафоров, per-connector concurrency gates, token bucket, starts_per_second, min-interval, fallback к прежним лимитам или второго независимого размера пула. Проверка imports/consumers и тесты смешанной очереди.
- Слот удерживается до полного тела ответа/подтверждённого прекращения I/O, освобождается ровно один раз. Нет утечек при отмене, ошибке, redirect, 429, recovery или закрытии. Проверки насыщенной очереди и teardown.
- Сохраняются точная идентичность SKU/размера, цены/наличие/варианты, конечные retry budgets, server-directed Retry-After, profile ownership и сохранность истории. Проверки существующих контрактов и disposable DB интеграции.
- Синтетический сбор 1000+ целей завершается без зависаний, дублей результатов и превышения 100 активных запросов. Очередь конечных lightweight задач допустима; постоянное потребление памяти для произвольно большой очереди не обещается. Live-проверки не превращать в нагрузочный тест 1000 запросов к чужой площадке.
- Desktop/API/worker, direct `main.py collect`, numeric/raw Ozon без DATABASE_URL и standalone clients используют одинаковую политику. Новые пользовательские UI/ENV-настройки, миграции данных и автоматический подбор N не входят в задачу.

## Current system and evidence

- `marketplace_connector/connectors/builder.py:11`: один ChromeSession передаётся трём клиентам, подходящая граница владения общим диспетчером. Standalone Ozon/Ali/WB самостоятельно создают ChromeSession того же типа.
- `marketplace_connector/browser/session.py:55-92,161-193`: acquire/release reference counting, открытие одного BrowserContext, ожидание завершения собственного Chrome. Profile lock и общий challenge_lock защищают владение, а не пропускную способность.
- `price_watch/application/collection_service.py:23`: создаются задачи всех целей; Ozon Semaphore(8), общий Semaphore(5) для остальных. `marketplace_connector/application/product_service.py:43` принимает limit и удерживает его вокруг вызова коннектора. Внешний retry освобождает этот слот на время backoff.
- Ozon client/JSON transport: concurrency=8, starts_per_second=None, общая страница и браузерный fetch; запросы composer/product/modal делят локальный счётчик. Политика в `marketplace_connector/application/collection_policy.py` и [ADR0014](../../../docs/adr/0014-ozon-unpaced-async-concurrency.md).
- Ali client/JSON transport: defaults 1 и 5/с, experimental None/None и finite concurrency без pacing; аналогичные Condition, active counter, cooldown/recovery. Полный external_id productId:skuId остаётся обязательным для exact collection.
- `marketplace_connector/connectors/wildberries/transport.py:50-215`: `_lock` сериализует fetch, `_article/_counts/_errors/_fatal/_cancelled` общие для текущей цели; `_dispatch/_next_start` ограничивают старты 3/с; page.route/response hooks учитывают detail/grade и native retries. Снять lock без изоляции состояния нельзя.
- `marketplace_connector/connectors/wildberries/runtime.js`: runtime витрины подтверждает профиль/валюту/условия кошелька и вызывает getXnmProducts, getUserGrade, optional metadata. Некоторые helper не принимают AbortSignal; текущий timeout/metadata timeout может закрыть общую WB страницу. Для конкурентного WB это затронет соседние цели. Ценовой контракт [ADR0009](../../../docs/adr/0009-wildberries-size-and-wallet-price.md) сохраняется.
- `marketplace_connector/application/retry.py`: один внешний retry; внутренние попытки транспортов сохранены ранее в [centralize-collection-retries](../centralize-collection-retries/spec.md). Перестройка retry policy не входит в эту задачу, меняется только допуск каждой фактической попытки.
- Direct/worker factories — `price_watch/cli.py:153-209`; numeric/raw — `marketplace_connector/connectors/ozon/cli.py:67`. Изменение только CollectionService не охватит standalone/numeric пути.
- [Ali-эксперимент](../experiment-aliexpress-unpaced-concurrency/spec.md): два успешных unbounded batch 40 SKU и повторяемые таймауты первых восьми fetch при N=8. Перезапуск Chrome/пауза 10 s не устранили сбой. Причина не установлена. Старая задача остаётся открытой; новый dispatcher не объявляется доказанным исправлением без проверки.
- CodeGraph current source/status актуальны на исходном dd06bca, pending=0/mismatch=null. Локальный Repowise checkpoint актуален; MCP get_risk опирается на 9f3876d и не разрешает три из четырёх запрошенных путей. Это ограничение оценки, не положительный вывод о риске; план основан на текущем source и контрактах.

## Agreed solution

**Согласованы требования: одна настройка max_in_flight_requests=100, отсутствие M стартов/с, применение ко всем коннекторам. Ниже — предлагаемый технический план, ожидающий одобрения.** Архитектурное решение: [proposed ADR0015](../../../docs/adr/0015-shared-request-dispatcher.md).

### Владение и интерфейсы

Добавить `marketplace_connector/browser/request_dispatcher.py`. ChromeSession создаёт и закрывает один RequestDispatcher с `max_in_flight_requests=100` по умолчанию (одна точка определения production значения). Никакого singleton на процесс/все профили: другие процессы/независимые сеансы не координируются; общий профиль по-прежнему защищён ownership lock. Тестовый override — тот же единственный параметр, не второй лимит.

Интерфейс dispatcher: регистрация управляемой страницы/endpoint predicates, постановка PendingRequest, допуск в I/O, завершение/отмена и close. PendingRequest содержит internal request_id, marketplace, operation kind, request/context association и completion; URL/token/body не попадают в диагностику. Состояние: `pending_requests`, `in_flight_requests`, peak, queue_wait, outcomes. Это счётчики/очередь, не отдельные настройки. Очереди площадок обслуживаются round-robin, внутри FIFO; без отдельных квот. Уже выполняемые запросы не вытесняются — одна зависшая площадка может занимать общие слоты до timeout.

Слот не резервируется вокруг connector.get_product или целого native SDK вызова WB: одна цель может инициировать несколько HTTP-запросов. Диспетчер допускает именно управляемые HTTP-операции, без вложенного acquire того же бюджета. Parser/mapper, ожидание retry, recovery и ручной проверки не держат сетевой слот. Запрос повтора снова встаёт в общую очередь. Во время site-specific cooldown запросы этой площадки не блокируют очередь остальных.

### Общая граница браузерного I/O

Предпочтён BrowserContext-level admission через routing и события жизненного цикла запросов: запрос ожидает допуска перед continue/fallback; requestfinished/requestfailed освобождают учёт после тела/ошибки. Одна операция получает permit ровно один раз. Redirect chain передаёт тот же permit до финального ответа; подконтрольный redirect не может уйти в сеть в обход учёта. Прежние page-level gates/handlers должны быть встроены в эту цепочку, а не обходить context dispatcher через route.continue_. Cached/coalesced SDK results без сетевого запроса не занимают HTTP слот.

Граница: JSON/API-запросы коннекторов и необходимые runtime helper, включая WB detail/grade/metadata и native retries. Навигация/bootstrap страницы, JS/CSS/images/телеметрия Chrome не считаются товарными запросами и не должны запираться за товарной очередью. Не обещать ограничение всех пакетов/сокетов браузера.

Routing выключает HTTP cache, а Service Worker способен перехватить запрос до routing. До внедрения проверяется браузерный прототип: scoped bypass Service Worker через CDP на страницах сбора, без unregister/очистки профиля/cookies/нового профиля; после закрытия страницы эта настройка не переносится в обычный браузер. Это осознанное изменение сетевого caching, оно может изменить время прогонов. Если native WB/profile или контролируемые запросы несовместимы с таким admission, остановиться и согласовать другой механизм; не обходить бюджет и не подменять цену/профиль. Нельзя объявлять прототип доказанным заранее.

Документация проверена через Context7: [Request lifecycle](https://playwright.dev/python/docs/api/class-request), [BrowserContext route](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-route); scoped bypass описан в [CDP Network protocol](https://github.com/ChromeDevTools/devtools-protocol/blob/master/pdl/domains/Network.pdl). Page routes приоритетнее context routes; response означает заголовки, requestfinished — завершение тела. HTTP 4xx/5xx тоже заканчиваются requestfinished. Эти случаи входят в прототип и тесты.

### Переработка коннекторов

- **Ozon:** убрать локальные concurrency/rate параметры, Condition admission и OZON_CONCURRENCY; composer/product/modal и повторы регистрируются у общего диспетчера. Сохранить parser/mapper/aspects, таймаут/abort, один coordinated recovery страницы. Один счётчик активных операций для безопасного recovery допустим как состояние, не новый числовой лимит.
- **Ali:** убрать те же локальные gates, pacing и старые экспериментальные None/finite режимы конструктора. Сохранить точный SKU, общий bootstrap и проверку доступа. Разделить в диагностике очередь, выполнение JS и наблюдаемый HTTP. Установленный сбой N=8 не воспроизводить ещё раз без новой диагностической цели; локализовать по сохранённым данным и браузерным тестам, проверить N=8/100 на новой реализации.
- **WB:** вынести `_article/_counts/_errors/_fatal/_cancelled` в per-target/per-request context, использовать реестр по internal request_id и конкретному Browser Request, не один глобальный current article. Общую подготовку профиля/кошелька выполнять single-flight; ожидание bootstrap не равно лимиту товаров. Native retries/helper requests учитываются по одному в dispatcher. Сохранить runtime витрины и актуальную кошелёчную скидку, Decimal, nmId:optionId. Не вводить raw HTTP adapter, фиксированный процент или fallback на обычную цену при ошибке условий.
- **Отмена WB:** убрать закрытие общей страницы в ответ на timeout/metadata timeout одной цели. Для helpers без AbortSignal нужны управляемый per-request abort/адаптация browser bridge и привязка к target context. Отмена ждёт прекращения собственного I/O, соседи продолжают работу. Shared grade bootstrap не отменяется одним из его waiters. Если изолировать конкретный native путь невозможно, это блокер для конкурентного WB, а не основание оставить тихую сериализацию или завершать соседей.

### Время, ошибки и сохранение результатов

Время очереди измеряется отдельно. Таймаут HTTP-операции стартует после допуска к I/O; локальные JS/Python outer timeout не должны истекать только из-за ожидания 1000 целей в очереди. Потребуется согласовать admission notification между routing и runtime, перенести существующие setTimeout/wait_for к правильной фазе. Bootstrap/runtime-readiness имеют свои конечные таймауты. Тело ответа входит в сетевой timeout. Отмена queued запроса удаляет его без отправки; отмена active не освобождает permit до завершения abort.

Сохранить server-directed Retry-After, finite retry budgets и single-flight recovery по площадке. Это обработка отказов, не M стартов/с. Recovery приостанавливает новые запросы своей площадки, ждёт завершения/abort её active I/O и не закрывает страницы других площадок. Очередь других площадок продолжает работать. Shared challenge_lock остаётся для ручных проверок.

CollectionService/Products: убрать Semaphore(8)/Semaphore(5), OZON_CONCURRENCY/MAX_CONCURRENT_OTHER_CARDS и limit-параметр ProductService с миграцией всех callers. Цели запуска по-прежнему заморожены; сохранение успешного результата, lease/heartbeat/cancellation, точная история и selective tracking сохраняются. Не хранить все большие ответы до конца batch: результаты обрабатывать/сохранять по завершении. Для 1000 целей допустимы лёгкие ожидающие контексты; второй независимый queue capacity/card-worker knob не вводится. Дополнительная задача потокового источника требуется только при доказанной проблеме памяти, не включается скрыто.

Полностью мигрировать builder, standalone clients, queued API/worker, direct collect, numeric/raw Ozon без DB, тесты и работающие экспериментальные CLI. Удалить устаревшие интерфейсы/config/tests numeric pacing; старые scripts либо переводятся на max_in_flight_requests, либо удаляются при наличии единого действующего benchmark. Архивные JSON/исторические ADR не переписываются, compatibility shims/fallback на старые лимиты не остаются. В experiment spec хранится ссылка на новый план, а не его копия.

Документы до приёмки: architecture overview/guide, collection-run-execution contract при затронутом execution, marketplace guides и TESTING_AND_TROUBLESHOOTING. Новый ADR supersedes только политику admission/rate из ADR0006/0009/0014; ценовые и identity решения остаются. Данных/моделей/API payload изменений нет, DB migrations не требуются. Backlog обновляется только после приёмки соответствующих задач.

## Implementation and verification plan

- [x] Проверить текущее владение Chrome, двойные gates, WB runtime/state/cancellation, affected consumers и ограничения browser routing; подготовить spec и proposed ADR.
- [ ] Получить явное одобрение этого технического плана и ADR, включая browser routing/cache/SW последствия и общий бюджет 100 на все площадки.
- [ ] Сначала подтвердить browser admission прототипом на локальных синтетических страницах: 100/101, полное тело, redirects, failure, Service Worker/cache, queue time отдельно от timeout. Не менять native runtime/profile semantics молча; при несовместимости согласовать поправку.
- [ ] Реализовать RequestDispatcher, round-robin очередь и ChromeSession lifecycle; проверить mixed 100, cancellation/close, отсутствие утечек permits и вложенного acquire.
- [ ] Перевести Ozon и Ali на dispatcher; удалить прежние gates/config и проверить product/modal, exact SKU, retry/recovery, независимую отмену, N=8/100 browser regressions с фазовой диагностикой.
- [ ] Переработать WB contexts/runtime hooks/abort, убрать сериализующий lock/rate gate после изоляции; проверить несколько одновременных товаров/размеров, grade/cache updates, native retry accounting, cancel одного без влияния на соседей.
- [ ] Убрать card semaphores/limit из ProductService/CollectionService, мигрировать builder, direct/queued/numeric/raw и действующие benchmark CLI; проверить 1000+ синтетических целей и смешанный сбор на общем бюджете 100 без потери результатов.
- [ ] Выполнить focused Python/browser checks, CLI imports без DATABASE_URL и disposable TEST_DATABASE_URL интеграции: API/worker/direct, lease/cancel, одна запись истории на цель, selective tracking. Линт/type checks — только применимые к затронутым файлам; без лишнего frontend redesign/E2E demo как доказательства live.
- [ ] Выполнить ограниченные live smoke Ozon/Ali/WB и mixed run без пользовательской БД, с существующим стабильным профилем. Сохранить реальные выборки/исходы/метрики; между попытками закрывать собственный Chrome, подтверждать освобождение профиля и ждать 10 s. При challenge/отказе доступа остановить серию и обсудить продолжение.
- [ ] Обновить постоянные docs/ADR статус по факту, проверить diff и контракты, commit и refresh CodeGraph/Repowise/pages; представить результат на приёмку, указав реальную область проверки и остаточные риски.
- [ ] После явной приёмки архивировать/сжать эту задачу по vibe-flow, обновить только соответствующий backlog, commit и refresh. Старый Ali-эксперимент не закрывать автоматически.

## Execution state

2026-11-08: создана новая planning-only задача на исходном HEAD dd06bca. Согласованы общий max_in_flight_requests=100 и запрет планового rate limiting; подробный технический план и ADR ещё не одобрены. Исходники изучены, текущие локальные индексы проверены, библиотечные контракты сверены с первичными docs через Context7/CDP protocol. Новых live-запросов, прототипа, изменения production кода и тестовых прогонов приложения в этой задаче нет. Следующий шаг — review плана. Ни старые задачи, ни этот план не считаются принятыми по готовности артефактов.
