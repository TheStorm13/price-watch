# Task: Последовательный сбор маркетплейсов с отдельными пулами по 100 запросов

## Goal and acceptance criteria

Убрать накладывающиеся ограничения товаров и запросов, сохранив специфику Ozon, AliExpress и Wildberries. Пользователь выбрал последовательный запуск маркетплейсов и отдельный асинхронный request pool каждого с `max_in_flight_requests = 100`. Это единственный численный предел параллельности; плановое M стартов в секунду запрещено. Число 100 — стартовая настройка, не измеренный оптимум. Подробный план ниже подготовлен для первого review gate; production пока не меняется.

Критерии и соответствующие проверки:

- В одном collection run одновременно выполняется только один маркетплейс. Следующий начинается после завершения/отмены и дренирования запросов предыдущего. Проверка событий этапов и отсутствия перекрытия на смешанном synthetic run.
- Каждый коннектор ограничивает свои управляемые HTTP-запросы числом 100, включая вспомогательные запросы и повторные попытки. Барьерный browser test: первые 100 допущены, 101-й ждёт; одно завершение допускает следующий без искусственной паузы. Browser connection scheduling не гарантирует 100 физических соединений или стартов на проводе.
- Нет дополнительного card semaphore, token bucket, starts_per_second, min-interval или скрытого пула целых get_product. Проверка consumers и поведения при насыщении. Bootstrap/profile/recovery locks сохраняются по назначению.
- Слот удерживается до полного тела/подтверждённого прекращения I/O и освобождается ровно один раз; ожидание очереди не расходует HTTP timeout. Проверки body streaming, redirect, cancel, failure, retry и teardown.
- Ошибки отдельных целей сохраняются без потери успешных результатов. Изолированная фатальная ошибка площадки завершает её этап и позволяет перейти к следующей; отмена всего run, LeaseLost и потеря общего Chrome прекращают весь run. Проверки переходов и отсутствия запросов после отмены.
- Синтетические 1000+ целей обрабатываются без зависаний, потери/дублирования результатов и превышения лимита. Это не обещание постоянной памяти при произвольной очереди и не live нагрузочный тест чужой площадки.
- Сохраняются SKU/размер, native wallet price WB, Decimal, варианты, история, selective tracking, lease/heartbeat, конечные retry budgets и server-directed Retry-After. Проверки текущих контрактов и disposable DB интеграции.
- Политика применяется к queued desktop/API/worker, direct main.py collect, standalone clients и numeric/raw Ozon без DATABASE_URL. Новых UI/ENV настроек, автоматического N и миграций данных нет.

## Current system and evidence

- `price_watch/application/collection_service.py:23-66`: открывает collection_session всех площадок, создаёт задачи всех целей; Semaphore(8) для Ozon и общий Semaphore(5) для остальных; сохраняет каждый результат по завершении и запрашивает новые pending targets. Последовательных этапов пока нет.
- `marketplace_connector/application/product_service.py:43-52`: параметр limit оборачивает весь connector.get_product; fetch_with_retry даёт внешний retry. Этот card-level предел не равен числу HTTP-запросов.
- `marketplace_connector/connectors/builder.py` передаёт клиентам один ChromeSession. `marketplace_connector/browser/session.py` управляет persistent Chrome, reference counting и challenge_lock. Для последовательных этапов общий процесс/профиль можно сохранить без глобального HTTP dispatcher.
- Ozon client/transport и `marketplace_connector/application/collection_policy.py`: concurrency=8, starts_per_second=None, общий browser fetch для composer/product/modal. Ценовой/identity контракт сохраняется; действующая политика описана в [ADR0014](../../../docs/adr/0014-ozon-unpaced-async-concurrency.md).
- Ali client/transport: production defaults concurrency=1, starts_per_second=5; experimental None/None и finite unpaced. Product identity — productId:skuId. Condition admission, cooldown/recovery и outer evaluation timeout требуют аккуратного разделения.
- `marketplace_connector/connectors/wildberries/transport.py`: _lock сериализует fetch; _article/_counts/_errors/_fatal/_cancelled относятся к текущей цели, _dispatch/_next_start задают 3 старта/с. Page routing/response hooks учитывают detail/grade и native retries.
- `marketplace_connector/connectors/wildberries/runtime.js`: native SDK и кошелёк, shared profile/cache, helper без AbortSignal. Сейчас timeout/metadata timeout может закрыть общую страницу. Просто снять lock нельзя; контракт [ADR0009](../../../docs/adr/0009-wildberries-size-and-wallet-price.md) сохраняется.
- `price_watch/cli.py` содержит direct/worker factories; numeric/raw Ozon — `marketplace_connector/connectors/ozon/cli.py`. Изменение только CollectionService не охватит эти пути.
- [Открытый Ali-эксперимент](../experiment-aliexpress-unpaced-concurrency/spec.md): 40/40 успешных SKU без лимита; два N=8 запуска дали восемь evaluation timeouts и 32 неотправленных запроса. Причина не установлена; смена архитектуры не доказывает исправления.
- На исходном HEAD bd376b4 CodeGraph complete, pending=0/mismatch=null; локальный Repowise checkpoint актуален. Repowise MCP get_why продолжает читать 9f3876d и не находит ADR0014: его ответ не является доказательством актуальной архитектуры. План опирается на текущий source и проверенные контракты.

## Agreed solution

**Согласовано направление: по 100 запросов у каждой площадки, площадки последовательно, без планового rate limit. Пользователь запросил сформировать изменения; одобрение детального плана и реализация ещё впереди.** [Proposed ADR0015](../../../docs/adr/0015-shared-request-dispatcher.md). Существующий task slug сохранён, чтобы не создавать вторую задачу; прежний глобальный dispatcher/routing план заменён этим решением.

### Оркестрация этапов

CollectionService группирует замороженные цели по marketplace и выполняет непустые группы в стабильном порядке ozon → aliexpress → wildberries. Внутри группы все цели могут иметь async tasks; единственный численный предел находится на HTTP-уровне транспорта. Результаты сохраняются по as_completed, без ожидания конца группы и накопления всех response bodies.

После группы сервис проверяет pending targets. Появившиеся при discovery цели текущей площадки обрабатываются до перехода к следующей; pending цели ранее завершённой площадки обрабатываются следующим последовательным проходом. Сохраняются правила frozen targets/selective tracking; данные и run payload не меняются. Перед переходом нужно завершить дочерние HTTP/response tasks, а не только родительские get_product. Пустые группы не запускают bootstrap.

ChromeSession удерживается на время run, чтобы release отдельного коннектора не перезапускал Chrome между этапами. Подготовка collection_session выполняется только для активного маркетплейса; заранее bootstrap остальных не запускается. Используется существующий стабильный профиль ~/.local/share/price-watch/chrome-profile без клонирования, очистки или смены cookies. Между этапами нет обязательного restart или паузы; правило закрыть Chrome и ждать 10 s относится к отдельным live экспериментальным попыткам.

Ошибка цели обрабатывается как сейчас. При фатальном сбое только активной площадки отменяются и дренируются её задачи, оставшиеся цели получают явную ошибку; затем стартует следующая площадка. Pending sweep не должен бесконечно запускать уже остановленный этап. При challenge новые запросы этой площадки не запускаются; ручная проверка/восстановление остаётся в пределах существующей конечной политики. Если safe teardown не подтверждён, утрачен общий browser/profile, отменён run или потеряна lease, дальнейшие этапы не запускаются. Heartbeat и сохранённые результаты остаются под текущим RunExecutor/RunExecutionStore.

### Request pools и единая настройка

В `marketplace_connector/application/collection_policy.py` заменить OZON_CONCURRENCY на одну production настройку `max_in_flight_requests` со значением 100 (константа согласно стилю модуля). Клиенты принимают одноимённый положительный параметр с этим default; тестовый override меняет этот же предел. У каждого экземпляра транспорта свои pending/in_flight state и очередь. Во время последовательного run суммарно активен один pool; это не системный лимит между независимыми процессами/профилями.

Ozon и Ali допускают каждую fetch-операцию перед отправкой через существующий browser bridge. Один слот охватывает fetch и полное чтение тела/abort. Product/modal requests получают слоты независимо; get_product не удерживает родительский permit при ожидании вложенного запроса. Retry снова получает слот, backoff/recovery/parser/mapper его не занимают. Убрать Condition/token bucket старого admission, заменить единственным request-pool механизмом; recovery/cooldown coordination сохранить отдельно от численного лимита. Небольшой общий helper permit lifecycle допустим при реальном совпадении кода, но глобальный scheduler на ChromeSession не нужен.

Не вводить общие BrowserContext routes, отключение HTTP cache или bypass Service Worker ради унификации. WB интегрируется через собственные native request hooks. Общим является контракт допуска, а не обязательный идентичный адаптер. Перенаправление — одна активная операция до финального тела; native retry — новая фактическая попытка, которую учитывает pool. Фоновая статика/пользовательский browsing не входят в бюджет управляемого сбора.

### Изменения коннекторов

- **Ozon:** заменить concurrency=8 на max_in_flight_requests=100, удалить starts_per_second/token bucket и дублирующие gates; composer/product/modal и retries используют один локальный pool. Сохранить aspects, parser/mapper, timeout/abort и coordinated recovery.
- **Ali:** production переводится с 1 и 5/с на 100 без pacing, как Ozon и WB; удалить старые concurrency/None/starts_per_second интерфейсы. Проверить очередь, timeout после admission и освобождение слотов на новой реализации. По явному решению пользователя диагностика прежнего N=8 сбоя и специальный повтор этого эксперимента исключены из задачи и перенесены в [backlog](../../../docs/BACKLOG.md#таймауты-aliexpress-в-эксперименте-с-n8). Это не утверждение, что прежняя ошибка исправлена.
- **WB:** изолировать per-target/per-request state и сетевые callbacks, убрать общий current article; common profile/wallet bootstrap выполнять single-flight. Каждый управляемый native helper/retry учитывается локальным pool через существующие hooks. Shared SDK/cache проверить на перекрёстное влияние; не заменять pricing pipeline или кошелёк raw price/fixed discount.
- **WB cancellation:** отмена цели прекращает только её I/O и не закрывает страницу соседей; shared bootstrap не отменяется отдельным waiter. Helpers без AbortSignal требуют проверенного механизма прекращения/дренирования. Если safe parallel native runtime не удаётся обеспечить в рамках задачи, остановиться с блокером; не маскировать проблему сериализующим товарным lock или неполным учётом запросов.

HTTP timeout начинается после допуска и включает тело ответа. Ожидание очереди измеряется отдельно; outer Python/JS timer не должен превращать его в timeout отправленного запроса. Отмена pending удаляет его без отправки; active освобождает permit только после подтверждённого завершения I/O. Существующие конечные retries, Retry-After и single-flight recovery сохраняются; это обработка ошибок, не плановое M стартов/с. При recovery выдача новых запросов текущей площадки приостанавливается до безопасного восстановления.

### Потребители, данные и документация

Удалить Semaphore(8)/Semaphore(5), MAX_CONCURRENT_OTHER_CARDS и limit из ProductService; мигрировать callers, builder, standalone, queued/direct и numeric/raw пути. Действующие experiment/benchmark CLI перевести на новый параметр, сохранив пригодность frozen datasets для проверки; устаревшие интерфейсы и fallback не оставлять. Исторические отчёты/измерения и старые ADR не переписывать. Автоматически не закрывать Ali experiment или другие задачи.

Новых зависимостей, миграций, изменений product/price/API моделей и UI не требуется. Обновить затронутые architecture/collection-run-execution docs, marketplace guides, TESTING_AND_TROUBLESHOOTING и принятый ADR до приёмки. ADR0015 заменит только concurrency/rate политику старых ADR. BACKLOG изменяется только после приёмки соответствующей задачи.

## Implementation and verification plan

- [x] Проверить текущую оркестрацию, transport constraints и consumers; заменить прежний глобальный план на последовательные этапы с локальными пулами 100 и обновить proposed ADR.
- [ ] Получить явное одобрение этого детального плана и ADR перед изменением production.
- [ ] Реализовать per-transport pool lifecycle и перевести Ozon/Ali; удалить прежние concurrency/rate интерфейсы. Проверить 100/101, full body, timeout после admission, retries, отмену, recovery и product/modal для новой реализации; диагностика прежнего Ali N=8 отложена в backlog.
- [ ] Изолировать WB state, native hooks/retries и индивидуальную отмену; только после проверки убрать общий fetch lock и rate gate. Проверить разные товары/размеры, wallet/cache, native fan-out и отмену без влияния на соседей.
- [ ] Перевести CollectionService на последовательные этапы, удержание ChromeSession и incremental persistence; удалить card semaphores/limit. Проверить порядок и неперекрытие, discovery/pending sweep, stage failure→next stage, run cancellation/LeaseLost, пустой run и teardown.
- [ ] Мигрировать builder, standalone, queued/direct/numeric/raw и действующие scripts; проверить synthetic mixed run 1000+ целей без потерь/дублей и превышения 100, CLI imports/numeric без DATABASE_URL, identity/price/retry регрессии и применимые lint/type checks.
- [ ] Проверить DB contracts на отдельном disposable TEST_DATABASE_URL: API/worker/direct, lease/heartbeat, cancellation, одна история на цель и selective tracking. Если окружение недоступно, указать непроверенное, не подменять mocks.
- [ ] Выполнить ограниченные live smoke Ozon/Ali/WB и последовательный mixed run без пользовательской БД на существующем профиле; сохранить исходы/peak/queue/HTTP timings. Не отправлять 1000 live целей. Между отдельными попытками закрывать собственный Chrome и ждать 10 s; при challenge/отказе доступа остановить live серию и обсудить продолжение.
- [ ] Обновить permanent docs, проверить staged diff, commit и refresh CodeGraph/Repowise; представить проверенный результат на приёмку с реальными ограничениями. После явной приёмки — архивирование/сжатие spec, completion commit и refresh согласно vibe-flow; старый Ali experiment остаётся отдельным.

## Execution state

2026-11-08: пользователь выбрал последовательные маркетплейсы с отдельными пулами 100 и запросил план. Дополнительно подтвердил 100 для всех коннекторов и поручил отложить прежнюю ошибку Ali N=8: она записана в docs/BACKLOG.md и исключена из текущего объёма диагностики; общие проверки корректности нового пула сохраняются. Spec и proposed ADR переработаны на исходном bd376b4; глобальный dispatcher, round-robin и общий browser interception исключены. Детальный план ожидает review gate. Production, тесты приложения, live profile и БД не изменялись; новых live прогонов нет. Следующий шаг — согласование сформированных изменений. Планирование не является приёмкой реализации и не закрывает текущий Ali experiment.
