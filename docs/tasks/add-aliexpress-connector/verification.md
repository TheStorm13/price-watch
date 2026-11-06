# Проверка реализации

Пользователь одобрил план 2026-10-26. Пользовательская БД не открывалась и не мигрировалась.

## Реализация и данные

AliExpress external_id — строка productId:skuId. Форма принимает два поля или
заполняет их из полной https://aliexpress.ru/item/…html?sku_id=… ссылки.
Короткие ali.click и международная витрина не поддерживаются.
API/CLI/store/import требуют пару. Изменение URL не может менять SKU.
Импорт старых product-only записей отклоняется; формат transfer остаётся v2.

Миграция 0015 меняет только external_id однозначных старых ссылок; card IDs,
история, настройки, updated_at и исторические snapshots не меняются. Без SKU
карточка остаётся прежней; при сборе ошибка «Не указан SKU» записывается только
в данные цели запуска. Конфликт идентичностей или активный сбор прерывает
миграцию атомарно. Проверено в приватных схемах временного PostgreSQL.

ChromeSession владеет процессом/CDP/профилем и считает acquire/release. Фабрика
создаёт один объект на запуск. У Ozon и Ali независимые transports/pages;
последний release штатно закрывает Chrome. Rust closer использует новый общий
модуль; старый Ozon lifecycle удалён. Общий lock согласует ручные проверки.

Ali получает JSON из главной страницы через productData. Только выбранный SKU;
одна точная RUB-цена coupon → activity → regular; isCouponAssigned=false не
исключает coupon. Повреждённая выбранная цена не маскируется. Купоны не получаем.
Необязательные отсутствующие поля пусты, имя продавца null.

При видимой CAPTCHA пользователь проходит её в Chrome, затем нажимает
«Проверка пройдена». При скрытом/headless сборе ошибка сообщает открыть Chrome
приложения и повторить сбор после ручной проверки. UI заголовок нейтральный.

## Выполненные проверки

- Первичный общий Python run с disposable TEST_DATABASE_URL: 166 passed.
- Отдельные migration tests: 2 passed (3 приватные схемы, сохранение и rollback).
- API/store/transfer: 2 passed; разные SKU, дубликат, URL mismatch, import roundtrip,
  старая карточка без изменений, корректный сосед получает 77648.00.
- Chrome synthetic mixed-owner/fetch + parser/transport: 15 passed на промежуточном наборе.
- CLI imports Ozon numeric и price_watch без DATABASE_URL, builder shared identity: passed.
- Frontend промежуточно: lint passed, 62 unit tests passed.
- cargo check passed; cargo test: 8 passed, 3 ignored (имеющиеся platform tests).
- Desktop release build passed. Финальные результаты приведены ниже.

## Live без БД

Текущий профиль, новый shared builder, обе площадки в одном сеансе:
- Headless: Ali SKU 1005009868651525:12000061135122688 → 77648.00 RUB/in_stock;
  Ozon потребовал проверку и получил ожидаемую ошибку доступа. Ali завершился.
- Повтор в видимом Chrome: Ali тот же SKU → 77648.00 RUB/in_stock;
  Ozon 1604900984 → 838.00 RUB/in_stock. Ручного подтверждения не потребовалось.
- Оба сеанса завершены штатно; cookies и тела проверок не сохранялись в репозиторий.

## Анализ рисков

Repowise working-tree risk выполнен на текущем HEAD c534565, но исторический
индекс остаётся старым. Рекомендован полный набор. Замечания complexity к новым
mapper/parser устранены разделением валидации и отображения на небольшие функции.
Длинный конструктор клиента сохраняет явные настройки browser/transport, как у
Ozon; глобального singleton и скрытого process ownership нет. Migration выполняет
полный preflight до UPDATE; исключение не меняет пользовательские данные.

Остаются внешние риски недокументированной ручки Ali и CAPTCHA/региональной цены.
Demo E2E не подтверждает живые службы; native и live результаты приводятся отдельно.

## Финальная проверка

- `TEST_DATABASE_URL=… .venv/bin/python -m unittest discover -s tests -q`:
  **175 passed**, без пропусков (18.303 s). Использован собственный PostgreSQL
  `/tmp/price-watch-ali-test-pg`, port 55439, disposable `price_watch_rel_test`.
- После исправления export/import границы: `tests.test_aliexpress_integration`
  и `tests.test_api` — **20 passed**, затем повторён полный набор 175 passed.
- `npm --prefix frontend run lint`: passed.
- `npm --prefix frontend test`: **63 passed** в 16 файлах.
- `cargo check --locked --manifest-path frontend/src-tauri/Cargo.toml`: passed.
- `cargo test --locked --manifest-path frontend/src-tauri/Cargo.toml`:
  **8 passed, 3 ignored**, пропуски — существующие platform tests.
- `npm --prefix frontend run desktop:build`: release build passed.
- `PRICE_SMOKE_ALI=1 dbus-run-session -- xvfb-run -a -s '-screen 0 1440x1000x24'
  python scripts/smoke_reliability_desktop.py`: passed — run-level failure/retry,
  Ozon + Ali persisted prices, API restart/catalog восстановлен в настоящем WebView.
  Все данные, БД и XDG находятся в `/tmp/pw-rel-native-aiyqrq11`; fake connectors,
  этот тест не проверяет живой сайт. Снимок `/tmp/price-watch-rel-native-after.png`
  просмотрен: обе карточки и цены читаемы, нет перекрытий или error overlay.
- Live (видимый Chrome, текущий профиль, без БД): Ozon 838.00, Ali 77648.00 RUB;
  **1 Ali productData request, 0 product navigations**, profile lock released=true.
  Очищенный результат: live-summary.json. Ни cookie, ни CAPTCHA payload не сохранены.
- `git diff --check` и `openspec validate add-aliexpress-connector --strict`: passed.

При diff review найден и исправлен запрет экспорта старых Ali-карточек:
структурный TransferDocument сохраняет historical refs, ImportDocument требует SKU.
Нет fallback сбора или импорта старой product-only идентичности.

Browser plugin not available: UI тесты используют штатный Playwright проекта.
Проверяемый путь: /cards → AliExpress → полная ссылка → productId/skuId строки →
создание отдельной карточки. Native viewport 1440×1000; demo E2E содержит
размеры 1024/1536 и компактные layouts. В demo имеется прежнее предупреждение
React Router о HydrateFallback, без framework overlay; оно не относится к Ali.

Повторный Repowise review: замечание к сложности import_cards закрыто выделением
проверки входных данных до транзакции. Замечание к длинному конструктору Ali
рассмотрено: его параметры явно повторяют browser/transport policy Ozon, это
сознательный выбор API, без нового конфигурационного слоя. Исторические выводы
индекса не используются как доказательство актуальной безопасности.

- Финальный demo E2E: **40 passed (2.3m)**. После добавления снимка формы
  повторён отдельный Ali сценарий: **1 passed (4.5s)**. Снимок
  `/tmp/price-watch-ali-add-card.png` просмотрен: два строковых ID и заполнение
  ссылки корректны; footer доступен, остальные поля доступны прокруткой.
- Усиленный shared browser test запускает одновременно настоящий synthetic
  Ozon fetch и пять Ali fetch, отменяет один Ali, подтверждает успех Ozon и
  разные pages. `tests.test_shared_browser`: **5 passed** после уточнения теста.
- Повторный risk analysis: critical findings нет. Единственное high — явно
  рассмотренная длина конструктора нового Ali client. Package manifest/lock
  не менялись; stale-index предположение об их изменении не подтверждено diff.
- Временный PostgreSQL остановлен. Live Chrome закрыт, профиль освобождён.

## Изменённые области для review

- marketplace_connector/connectors/aliexpress: identity, transport/client,
  models/parser/mapper/connector; очищенная fixture и целевые тесты.
- marketplace_connector/browser и ozon/async_client: общий lifecycle;
  frontend/src-tauri/src/lib.rs: новый import closer.
- connectors/builder, price_watch/cli.py и domain/marketplaces.py: смешанный сбор.
- API schemas/routes, postgres cards/transfer repositories и migration 0015:
  точная SKU identity, безопасные старые записи, export/import границы.
- AddCardDrawer, CardsPage, CardDetailsPage и ActiveCollectionPanel: ввод SKU,
  доступный сбор Ali, нейтральная ручная проверка; mock API и UI tests.
- scripts/smoke_reliability_desktop.py: обновлённая фабрика и опция смешанного smoke.
- OpenSpec, ADR 0008, workflow research/evidence. Руководства ещё не финализированы.

Реализация представляется на второе review. Приёмки пользователя пока нет;
sync/archive и task-only commits выполняются только после неё.

## Приёмка

2026-10-26: «Да, сделай коммиты». Реализация принята; руководства и ADR
финализированы, два delta specs синхронизированы, OpenSpec change архивирован.
`openspec validate --specs --strict`: 15 passed. Приложение после приёмки
не менялось; повторное исполнение уже прошедших runtime tests не требовалось.
