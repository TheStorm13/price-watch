# Исправления коннекторов Ozon, AliExpress и Wildberries

Принято пользователем 2026-11-08: «все отлично» в ответ на представление
реализации `94e8e9c` и проверки `f6164b5`. Все шесть пунктов плана выполнены
и проверены до архивации. Полная исследовательская спека и checklist сохранены
в Git на `f6164b5`.

Исправлены зависания, обработка фатальных ошибок и повторный разбор ответов:

- Ozon пробрасывает UnsafeBrowserTeardown из загрузки аспектов до RunExecutor
  и прекращает весь запуск. Обычные ошибки необязательного discovery сохраняют
  валидную цену с явной диагностикой неполного списка вариантов.
- Application retry не ждёт больше 30 секунд и учитывает структурированный
  `RateLimited.retry_allowed`. При превышении бюджета транспорта или приложения
  возвращается ошибка без повторного запроса; серверная пауза не сокращается.
- WB контролирует завершение getXinfo/getUserGrade/setDiscountForUnAuth.
  Watchdog измеряет простой native helper без его queued/active HTTP: очередь
  не расходует request_timeout. Зависший helper или потеря контроля renderer
  приводит к UnsafeBrowserTeardown и остановке собственной страницы.
- Временный сбой bootstrap WB очищает частично созданную страницу; следующая
  разрешённая попытка создаёт новый bootstrap. Отмена одного waiter не отменяет
  shared bootstrap остальных.
- Article evaluations WB удерживают своё поколение wallet до завершения
  response inspections. Старые поколения освобождаются после bootstrap,
  последнего потребителя и inspections; текущее хранится до смены или закрытия.
  Ошибка старого поколения не заменяется успехом нового. Доступ и recovery
  определяются числовым HTTP status, а не текстом исключения.
- Ozon/Ali выполняют строгий product parsing и полный mapping один раз в
  клиентском pipeline. Response содержит raw_text и готовую MarketplaceCard;
  connector не разбирает ответ повторно. Неиспользуемый keyword validate удалён.

Сохранены отдельные транспорты Ozon/Ali по явному решению пользователя,
асинхронные HTTP-пулы по 100, последовательность Ozon → Ali → WB, отсутствие
планового ограничения стартов/с, точные SKU/Decimal-цены и native WB SDK.
Миграций БД и новых зависимостей нет.

Для raw Ozon сохранена строгая проверка исходного HTTP JSON без discovery и
изменения текста. Валидный search redirect отсутствующего товара возвращается
в raw, а product API поднимает ProductNotFound. Standalone parser текста с
префиксом сохранён отдельно от строгого parse_json HTTP-пути. Время цены
фиксируется после товарного body и не сдвигается ожиданием аспектов.
Renderer probe разделён между evaluations с кэшем 0.5с, чтобы не создавать ping
от каждой из 100 задач; неподтверждённое закрытие страницы после 2с фатально.

Проверки реализации:

- Финальная серия: 61 regression test без ошибок — pipeline, retries, Ozon
  aspects, WB transport/browser, включая зависания каждого profile helper,
  очередь wallet HTTP дольше request_timeout, перекрытие поколений и cleanup,
  ошибки renderer без orphan evaluation и Unsafe на пути до RunExecutor.
- 73 DB integration tests без ошибок — PostgreSQL, Ali/WB integration, run
  reliability, variant tracking, Ozon ownership и Ozon variants. Использован
  отдельный временный кластер, затем штатно остановлен. Рабочая БД не трогалась.
- Дополнительно прошли adapter/parser/mapper/CLI и shared browser/identity
  проверки; оба CLI импортируются без DATABASE_URL. Успешны compileall,
  node --check WB scripts, git diff --check, проверка относительных ссылок
  изменённых документов и strict OpenSpec validation перед архивацией.

Браузерные проверки использовали временные профили и synthetic storefronts.
Live-площадки не проверялись; тесты не доказывают длительную устойчивость при
100 in-flight или совместимость с будущими версиями native SDK. Frontend не
менялся. Прежний эксперимент Ali N=8 и остальные открытые задачи не закрыты.

Постоянные контракты и руководства:
[collection-run-execution](../../../specs/collection-run-execution/spec.md),
[архитектура](../../../../docs/guide/ARCHITECTURE.md),
[Ozon](../../../../docs/guide/OZON.md),
[AliExpress](../../../../docs/guide/ALIEXPRESS.md),
[Wildberries](../../../../docs/guide/WILDBERRIES.md),
[проверки](../../../../docs/guide/TESTING_AND_TROUBLESHOOTING.md).
