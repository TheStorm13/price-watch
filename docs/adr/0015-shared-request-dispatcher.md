# ADR 0015: Единый dispatcher управляемых браузерных запросов

- Статус: **Proposed**, ожидает согласования технического решения.
- Дата: 2026-11-08.
- Рабочий контекст, критерии и план: [shared-request-dispatcher](../../openspec/changes/shared-request-dispatcher/spec.md).
- При принятии заменяет только локальную политику admission/rate из [ADR0006](0006-ozon-session-json-transport.md), [ADR0009](0009-wildberries-size-and-wallet-price.md), [ADR0014](0014-ozon-unpaced-async-concurrency.md). Эти ADR сохраняют исторический текст и ценовые/идентификационные контракты.

## Контекст

Товарные Semaphore и локальные transport limits регулируют одну нагрузку на разных
уровнях. Ali/WB делят общий card semaphore, что связывает независимые площадки.
Standalone/numeric пути обходят этот уровень. Native runtime WB может порождать
несколько HTTP-запросов на вызов адаптера, поэтому лимит вызовов get_product
не задаёт общий максимум HTTP-запросов.

Пользователь выбрал одну фиксированную на время запуска настройку
`max_in_flight_requests = 100`, запретил плановое ограничение стартов в секунду
и запросил перенос на все коннекторы. Число 100 — выбранное стартовое значение,
не измеренная ёмкость площадок/Chrome и не доказанный оптимум.

## Рассмотренные варианты

1. Оставить семафоры товаров и добавить общий request semaphore: сохраняет
   несколько накладывающихся лимитов и обходы standalone consumers.
2. Независимые пулы каждого коннектора: суммарная нагрузка растёт с числом
   площадок, остаются несколько настроек; не соответствует выбранной модели.
3. Общий пул целых connector.get_product: не учитывает fan-out/native retries
   и допускает удержание слота при ожидании вложенного запроса того же пула.
4. **Один dispatcher фактического управляемого browser HTTP I/O на ChromeSession:**
   охватывает direct fetch и native WB helper; требует переработки browser hooks
   и изоляции состояния WB. Рекомендуется этот вариант.

## Предлагаемое решение

ChromeSession владеет RequestDispatcher с одной настройкой 100. Его очередь
площадок обслуживается round-robin, без отдельных числовых квот. Pending записи
и счётчик active — состояние, а не дополнительные пределы. Permit охватывает
передачу запроса и полное тело ответа до finish/fail/abort, включая redirect chain;
не охватывает очередь, parser/mapper, retry backoff, recovery или manual challenge.

Предпочтён context-level browser routing admission с requestfinished/requestfailed
для полного I/O lifecycle; только управляемые API/native helper, без статики,
bootstrap навигации и постороннего browser traffic. Реальная работоспособность
подтверждается браузерным прототипом до миграции коннекторов. Для управляемых
страниц scoped bypass Service Worker не меняет сохранённый профиль; routing
отключает HTTP cache. Совместимость runtime/profile и корректность timeout,
redirects, native retry accounting являются обязательными условиями внедрения,
а не предположением о доказанной прозрачности interception.

Убираются card semaphores, local transport concurrency gates, token buckets,
starts_per_second и старые интерфейсы/режимы. Сохраняются таймауты, конечные
retry budgets, server-directed Retry-After и блокировки bootstrap/recovery/profile
ownership. WB разделяет per-target/per-request state и обеспечивает индивидуальную
отмену без закрытия общей страницы. Native pricing/profile и identity не заменяются.

## Последствия и границы

- Общий потолок 100 предсказуем при увеличении конечной очереди до 1000+ целей;
  память произвольно большой очереди этим пределом автоматически не ограничена.
- Медленная площадка может занимать общие active слоты; round-robin не вытесняет
  уже отправленные запросы. Нужны конечные таймауты и корректный cleanup.
- Queue wait отделяется от HTTP timeout; нельзя освобождать permit, пока
  отменённое I/O продолжается, либо занимать permit вокруг родительской операции,
  которая ожидает дочерний запрос того же пула.
- Browser routing меняет caching; производительность сравнивается с учётом этого.
  CAPTCHA, недокументированный native runtime и внешняя сеть остаются зависимостями.
- Все consumers мигрируются вместе, старые реализации/fallback не сохраняются.
  Миграций данных нет; история, SKU, цены и API payload не меняются.
- Старый Ali N=8 timeout не объявляется устранённым архитектурным решением:
  нужна проверка нового выполнения и диагностическое разделение queue/JS/network.
