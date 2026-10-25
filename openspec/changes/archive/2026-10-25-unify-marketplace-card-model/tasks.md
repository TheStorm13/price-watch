# Tasks

## 1. Общий товар, запись отслеживания и точность цены

- [x] 1.1 После одобрения полного плана записать исходный diff и baseline проверок в workflow run; воспроизвести CLI terminal confirmation с timeout и указать результат, не захватывая чужие изменения.
- [x] 1.2 Заменить ProductSnapshot на MarketplaceCard в marketplace_connector/domain, добавить нормализацию Decimal в domain/money.py; тестами проверить дробную цену, округление, диапазон, float/bool/NaN/infinity, out_of_stock, timezone и уникальность вариантов.
- [x] 1.3 Заменить локальный MarketplaceCard на TrackedCard с ref и CardOverview на TrackedCardOverview; обновить ORM→domain mapping и потребителей идентичности. Проверить сохранение ID/настроек и создание записи до первого сбора; зафиксировать таблицу полей в workflow run.

## 2. Специфические данные Ozon и преобразование

- [x] 2.1 Добавить connectors/ozon/models.py и parser.py с OzonProductData и разбором используемых полей; перенести helper из mapper. Fixtures должны подтвердить извлечение SKU/cardPrice/gallery/seller/review/characteristics/aspects/SEO без потери полей.
- [x] 2.2 Перевести OzonMapper на OzonProductData→MarketplaceCard, OzonConnector — на parser→mapper. Проверить cardPrice-only, mismatch SKU, отсутствующий товар, unknown, строковый false и прежний приоритет изображения.
- [x] 2.3 Исключить float-декодирование и двойной разбор transport/widget/SEO JSON; перевести RawMarketplaceResponse в Ozon-ответ, удалить неиспользуемый общий raw-тип. Проверить денежные JSON literals и неизменность raw_text; описать границу parser/mapper в docstrings.
- [x] 2.4 Обновить MarketplaceConnector, registry/service и экспорты. Два тестовых коннектора с разной входной структурой должны вернуть один MarketplaceCard; у общего домена не должно быть импортов Ozon/price_watch/ORM.

## 3. Сбор и PostgreSQL

- [x] 3.1 Перевести CollectionService, RunExecutor, repository port и фабрики CLI/worker на TrackedCard и MarketplaceCard; тестами подтвердить cancellation, heartbeat/lease loss, общую и индивидуальную ошибки и ProductNotFound.
- [x] 3.2 Перевести save_result на Decimal и новый товарный сериализатор без изменения транзакционных границ. На disposable TEST_DATABASE_URL проверить idempotence, unchanged success, mismatch, rollback, stale owner и concurrent retry существующими reliability/integration tests.
- [x] 3.3 На disposable БД проверить работу существующих ID, групп, тегов и NUMERIC(14,2), version 1.0/пустых JSONB snapshots и новых записей 2.0. Подтвердить отсутствие schema migration и переписи исторических данных, сохранить результаты и описание PG mapping в workflow run.

## 4. JSON, API и CLI

- [x] 4.1 Заменить snapshot_to_* на card_to_* и обновить product.schema.json для 2.0, строковых цен и image_url. Проверить вывод по схеме для полного/частичного/недоступного товара и сохранение всех полей ProductSnapshot.
- [x] 4.2 Перевести Card/Group/History/Statistics/DealResponse и CLI JSON на Decimal-строки; до coercion проверять строковые цены импорта v2. API-тестами подтвердить каждый денежный путь, null, точную среднюю и export→preview→import roundtrip; записать breaking contract в workflow run.
- [x] 4.3 Перенести числовой CLI в connectors/ozon/cli.py и обновить main.py и вычисление профиля по умолчанию. Проверить оба импорта и main.py <id> без DATABASE_URL, normalized/raw/output и терминальное подтверждение с fake transport/input.
- [x] 4.4 Удалить ozon_article_json, старые модели, parser/normalizer facade и заменённые экспорты; обновить scripts и packaging/make-linux-release.sh, packaging/aur/PKGBUILD и другие найденные потребители. Поиск должен подтвердить отсутствие действующих legacy-импортов, а release manifest — наличие нового CLI и отсутствие удалённого пакета.

## 5. Frontend и локальные данные

- [x] 5.1 Ввести DecimalString и TrackedCardView, перевести client/queries/mock API и fixtures на строки. Обновить mockPriceMetrics и mock-арифметику выгодности, групп, статистики и импорта точными тестовыми операциями из design. Проверить TypeScript и API/mock parity на конечных дробных средних; изменение структуры денег описать в типах/docstrings.
- [x] 5.2 Добавить utils/money.ts для точного сравнения и форматирования без универсальной decimal-арифметики; тестами проверить 9.90/10.00, равенство разных scale, null в обоих направлениях, большой диапазон, перенос разряда при округлении и дробные средние.
- [x] 5.3 Перевести каталог, группы, детали и график: number только для координат, точные строки для экстремумов/подписей/tooltip. Unit/mock E2E должны подтвердить сортировку списка/плитки, представителя группы, фильтры и исходную цену tooltip.
- [x] 5.4 Однократно мигрировать notification storage на новый формат; тестами проверить сохранение pending/watermark, отсутствие ложного события из-за формата цены, повтор после ошибки и повреждённую цену без потери очереди. Описать новую версию storage в workflow run.

## 6. Сквозная проверка реализации

- [x] 6.1 Выполнить релевантный Python-набор и PostgreSQL reliability/migration/group metrics tests только с disposable TEST_DATABASE_URL; сохранить команды, итоги, skips и ограничения, отдельно подтвердить queued API/worker и direct collect с fake connector.
- [x] 6.2 Выполнить npm --prefix frontend run lint, npm --prefix frontend test и npm --prefix frontend run test:e2e; зафиксировать результаты и подтверждение сохранения каталога при ошибке обновления.
- [x] 6.3 Выполнить Rust tests, desktop build и изолированный live smoke с fake connector, обновив его под строковые цены. Подтвердить Tauri→API→worker→PG и числовой CLI без БД; недоступные проверки явно отметить.
- [x] 6.4 Сравнить SQL count и p95 каталога с baseline на одинаковых синтетических данных; подтвердить REPEATABLE READ, отсутствие N+1 и порог max(1.20×baseline, baseline+50 мс).
- [x] 6.5 Проверить итоговый diff, контракты и удаление заменённого кода; представить пользователю изменения и результаты для явного принятия. Принятие отметить в workflow run; до него задача не завершена.

## Workflow follow-up

- После принятия обновить только актуальные docs/architecture/overview.md,
  docs/guide/ARCHITECTURE.md, DATA_AND_API.md, RUNNING.md, PACKAGING.md и README
  в затронутых местах; проверить пути и команды, старые ADR не переписывать.
- Принять ADR 0005, синхронизировать новые specs и архивировать change согласно
  соответствующим skill; проверить валидацию и результат архивации.
- Обновить запись align-project-and-module-names: решение о моделях и перенос
  CLI закрываются этим change; остальные переименования не объявлять выполненными.
- Проверить staged diff, создать коммиты только принятой задачи с тестами,
  документацией и OpenSpec; проверить хеши и сообщить их. Не push/merge.
