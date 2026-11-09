# Проверки и диагностика

[К содержанию](README.md)

## Локальные службы

Регрессии продолжений Ozon и владения SKU: `tests.test_ozon_aspects` проверяет
сокращённые реальные структуры `aspectModalInfo`/`webAspectsModal`, сохранение
точной цены, ошибки продолжения, numeric/raw без БД. `tests.test_ozon_ownership`
с отдельным disposable `TEST_DATABASE_URL` проверяет queued/direct сбор,
ограничения прямого SQL и конкуренции, остановку миграции при дубликатах и
транзакционный перенос вариантов вместе с историей.

Исправление старых разделённых семейств выполняется отдельно от миграции и
обычного сбора: после резервной копии, без активных запусков, с проверкой настроек.
`ozon_repair.merge_ozon_cards` переносит варианты и наблюдения перед удалением
пустой карточки; исторические run targets сохраняют исходную идентичность.
Новый backend и миграцию `0021` устанавливайте вместе: старый backend не заполняет
обязательное поле площадки варианта. До обновления приложения локальное исправление
семейств может выполняться без применения `0021`; составной `history_variant_fk`
должен разрешать отложенную проверку в транзакции переноса.

После запуска desktop логи находятся в
`$XDG_STATE_HOME/price-watch/` (обычно `~/.local/state/price-watch/`):
`postgres.log`, `api.log`, `xvfb.log` и `desktop-worker.log`.
Сообщение об ошибке запуска указывает соответствующий файл.
У каждой службы один файл до 10 MiB без архивов: он очищается перед новым запуском
и при заполнении. После сбоя файл остаётся до следующего запуска, поэтому нужный
вывод следует сохранить до перезапуска. Chrome пишет `chrome.log` внутри профиля
по той же политике, в том числе в числовом JSON-режиме без БД.

Панель сбора хранит только небольшую выборку ошибок последнего созданного запуска.
Создание следующего очищает прежние подробности; счётчики и повтор сохраняются.
Если обновление остановлено миграцией `0017`, завершите активный сбор или
восстановите его прежним worker до остановки writers и повторного обновления.
API слушает свободный локальный порт и требует секрет, который Tauri передаёт
интерфейсу. Фиксированного адреса для ручного `curl` нет.

## Автоматические проверки

### HTTP request pools

Ozon, AliExpress и WB используют отдельные `max_in_flight_requests=100`.
Площадки выполняются последовательно в общем Chrome, без card semaphore и
планового ограничения стартов/с. Слот держится до полного тела/abort, очередь
не входит в HTTP timeout. Политика — [ADR0015](../adr/0015-shared-request-dispatcher.md).
Проверки без live площадок:

```bash
.venv/bin/python -m unittest tests.test_ozon_json_transport tests.test_aliexpress_transport tests.test_transport_retry_preparation tests.test_collection_service -q
.venv/bin/python -m unittest tests.test_request_pools_browser tests.test_wildberries_browser tests.test_shared_browser -q
```

Browser tests используют временные профили и синтетические ответы. Они проверяют
100/101, полные тела, индивидуальную отмену, native helpers и wallet/size contracts;
это не доказательство устойчивости живых площадок при нагрузке.

Стенд Ozon теперь принимает только фиксированные HTTP pool sizes, без pacing
и отдельного пула карточек. Исторические измерения A/B/C/D остаются в docs/tasks
и OpenSpec; их режимы удалены из действующего CLI.

```bash
.venv/bin/python -m experiments.parallel_ozon --articles-file /tmp/ozon-skus.json --order 100 --output /tmp/ozon-pool100.json
```

Для live используйте существующий стабильный Chrome профиль
`~/.local/share/price-watch/chrome-profile` (`--profile-dir` для другого существующего
пути). Не создавать, сбрасывать или клонировать его, не экспортировать cookies.
Между отдельными попытками завершайте собственный Chrome, проверяйте освобождение
профиля и ждите 10 секунд. Challenge/401/403/429 останавливает серию; следующая
попытка требует обсуждения. Между этапами одной последовательной сборки restart
и пауза не нужны. Ограниченные smoke не подтверждают длительную устойчивость.

Проверки дополнительного повтора сбора (без живых площадок):

```bash
.venv/bin/python -m unittest tests.test_product_retry tests.test_collection_service tests.test_transport_retry_preparation tests.test_price_watch_cli -v
```

Они покрывают один внешний повтор поверх внутренних попыток, задержку 1 секунду,
`Retry-After`, отмену, потерю lease, освобождение лимита на паузе, итоговые
счётчики, диагностику обеих попыток и отсутствие нового fetch при сбое записи.
Проверки PostgreSQL по-прежнему требуют отдельную `TEST_DATABASE_URL`.

```bash
.venv/bin/python -m unittest discover -s tests -v
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run test:e2e
cargo test --locked --manifest-path frontend/src-tauri/Cargo.toml
npm --prefix frontend run desktop:build
```

Интеграционный тест PostgreSQL запускается только с `TEST_DATABASE_URL`,
указывающим на **отдельную тестовую базу**. Создайте её на доступном
PostgreSQL и запустите:

```bash
TEST_DATABASE_URL='postgresql://user:password@localhost:5432/price_watch_test' \
  .venv/bin/python -m unittest tests.test_postgres_integration -v
```

Тест применяет миграции и изменяет данные этой базы. Не указывайте здесь
рабочую базу приложения. Браузерные E2E тесты сами запускают Vite в тестовом режиме
с mock API; они проверяют интерфейс, но не живые desktop-службы и Ozon.

## Автоматические проверки интерфейса

```bash
npm --prefix frontend run test:e2e
```

Mock E2E проверяет поведение и геометрию: отсутствие перекрытий и
горизонтального переполнения, доступность действий и прокрутки, размеры текста,
положение панелей и переключение состояний. Проверки охватывают каталог,
список и сетку, группы, формы, детали товара и панель сбора на desktop-ширинах.
Ручное сравнение скриншотов и обновление PNG-эталонов не требуются.

При падении Playwright сохраняет скриншот и trace в каталоге результатов.
Это диагностические материалы: причину ошибки определяют по упавшей проверке,
сообщению и trace. Набор не создаёт PNG при каждом успешном шаге.

Mock E2E не проверяет живые Tauri WebView, API, worker и маркетплейсы.
Для desktop-служб используйте отдельный изолированный native smoke.

## Эксперимент AliExpress с HTTP pool

Стенд запускает один DB-free пакет из 40 уникальных `productId:skuId` через async
задачи. По умолчанию `max_in_flight_requests=100`; `--max-in-flight-requests N`
меняет только HTTP-пул, без pacing и card semaphore.

```bash
.venv/bin/python -m unittest tests.test_aliexpress_dispatch_experiment tests.test_aliexpress_transport -q
.venv/bin/python -m experiments.parallel_aliexpress --articles-file /tmp/ali-skus.json --max-in-flight-requests 100 --output /tmp/ali-pool100.json
```

Frozen articles можно взять из сохранённого отчёта. При новом discovery доступны
`--seed-product-ids 1005007620335204 1005008127103020 1005003918845337 1005013177457618`.
Количество SKU и различных product ID указывается отдельно; это не одинаковые
выборки независимых товаров. Discovery и подготовка исключены из batch timings.
HTTP 401/403/429, HTML/маркер проверки или неверный адрес останавливает стенд
до recovery/retry. Соседние задачи отменяются и дренируются. Общие правила профиля,
закрытия Chrome и 10-секундной паузы описаны выше.

Отчёт содержит выбранный HTTP-предел, исходы, gate/network timings, safe stop reason,
peak fetch evaluations и retries; не содержит cookies, bodies и заголовки.
Перекрытие fetch evaluations не равно числу физических сетевых соединений.
Исторические два сбоя Ali N=8 не считаются исправленными этой миграцией:
[отложенная диагностика](../BACKLOG.md#таймауты-aliexpress-в-эксперименте-с-n8).

## Проверки JSON-транспорта Ozon, AliExpress и WB

```bash
.venv/bin/python -m unittest tests.test_ozon_json_transport tests.test_ozon_fetch_browser tests.test_async_ozon tests.test_profile_lifecycle tests.test_aliexpress_parser tests.test_aliexpress_transport tests.test_shared_browser tests.test_wildberries_identity tests.test_wildberries_mapper tests.test_wildberries_transport tests.test_wildberries_browser -v
```

Детерминированные тесты проверяют пять одновременных запросов, общий cooldown,
ограниченное восстановление, классификацию ошибок и независимую отмену.
`test_ozon_fetch_browser` запускает настоящий `fetch` в системном Google Chrome,
но перехватывает запросы синтетическими ответами. Он использует временный
профиль, не обращается к Ozon и не открывает профиль пользователя. Без
установленного Google Chrome браузерные проверки пропускаются. Lifecycle-тесты
проверяют сохранение синтетической cookie после штатного закрытия и перезапуска.
Для этих тестов нужны локальные сокеты и возможность запустить Chrome.
Живая проверка Ozon отдельно зависит от работающей сессии; сохранение cookies
и личных данных в фикстуры не требуется.

Дополнительные регрессии lifecycle и однократного parsing:

```bash
.venv/bin/python -m unittest tests.test_connector_pipeline tests.test_product_retry tests.test_ozon_aspects tests.test_wildberries_transport tests.test_wildberries_browser -v
```

Они проверяют строгий raw, Decimal/SKU и время цены, один parse/map на ответ,
фатальную ошибку Ozon discovery на пути до RunExecutor, отказ от сверхбюджетного
Retry-After, зависшие WB profile helpers, ограниченное ожидание renderer,
повтор временного bootstrap, перекрывающиеся поколения wallet и их очистку.
Synthetic Chrome также проверяет очередь profile HTTP дольше request_timeout:
очередь не становится таймаутом запроса или bootstrap. Это локальные проверки;
они не доказывают совместимость с будущими версиями native SDK площадки.

## Типовые проблемы

| Симптом | Что проверить |
| --- | --- |
| `./price-watch` сообщает, что приложение не собрано | Запустить `npm --prefix frontend run desktop:build` |
| Не найден Python или Python модули | Создать `.venv` и установить `requirements.txt` с `--require-hashes` |
| PostgreSQL не стартует | Открыть `postgres.log`; проверить установленную версию и права на каталог `$XDG_DATA_HOME/price-watch/postgres` |
| API не отвечает | Открыть `api.log`; проверить ошибки миграций и запуска Python |
| Нет Chrome | Проверить `google-chrome-stable --version` |
| Скрытый дисплей недоступен | Открыть `xvfb.log`; проверить установку `Xvfb` и `xauth` |
| Ozon или AliExpress запросил проверку при фоновом сборе | После завершения запуска открыть Chrome кнопкой, пройти проверку и повторить сбор |
| WB/Ali: ошибка обнаружения вариантов | Повторите сбор после проверки доступа в Chrome. Достаточно артикула; SKU находятся автоматически, старая история сохраняется отдельно |
| Карточка Ozon не обновилась | Открыть `desktop-worker.log`; у закончившегося SKU доступные фото и варианты собираются без цены. Если Ozon больше не возвращает метаданные карточки, восстановить их из поиска нельзя |
| Ozon: `VariantDiscoveryIncomplete` | Точная цена сохраняется. Проверьте сообщение о лимите 500 SKU, конфликте владельца или неизвестном продолжении; для получения цен известных соседей включите их отслеживание и запустите сбор. Retry обновляет только неуспешные точные SKU |

Тесты семейств Ozon используют production parser/mapper/executor и отдельную
disposable `TEST_DATABASE_URL`: `.venv/bin/python -m unittest tests.test_ozon_variants -v`.
Mock E2E `frontend/e2e/ozon-variants.spec.ts` проверяет UI импорта/параметров/главного,
но не live Ozon, API, worker или БД. Правила и ограничения: [Ozon](OZON.md).

## Проверка надёжности и каталога

Чистые правила выгодности, выбора представителя и расписания, сборка каталога
из материализованных входов и границы импортов проверяются без БД:

```bash
.venv/bin/python -m unittest tests.test_application_rules tests.test_catalog_service tests.test_dependency_boundaries -v
```

Результаты ARCH-03, сравнение с исходным HTTP-каталогом и baseline/after:
[отчёт проверки](../tasks/separate-business-rules-from-postgres/verification.md).

`tests.test_run_reliability`, `tests.test_reliability_migration` и
`tests.test_group_metrics_integration` тоже требуют отдельной disposable
`TEST_DATABASE_URL`. Миграционный тест создаёт частную схему и удаляет только
её. Полный Python-набор с этой переменной включает все PostgreSQL-проверки.

`scripts/benchmark_catalog.py --mode after --output /tmp/catalog-after.json`
запускается через `.venv/bin/python` с `TEST_DATABASE_URL` и требует БД с именем
`price_watch_rel_test`: harness сбрасывает её фикстуры. S/M/L: 100/1000/5000
карточек и по 100 точек истории на карточку; пять прогревов, 30 измерений.
Сравнение включает ASGI HTTP-сериализацию, SQL, выборочный RSS и скорость записи.

После release-сборки изолированный live smoke с fake connector:

```bash
dbus-run-session -- xvfb-run -a -s '-screen 0 1440x1000x24' \
  python scripts/smoke_reliability_desktop.py
```

Нужны system Python с gi/Atspi и ImageMagick. Скрипт создаёт собственные
временные XDG/БД/профили, нажимает повтор через настоящий WebView и перезапускает
только свой дочерний API. Он не проверяет текущий Ozon или реальную CAPTCHA.
Результаты принятого REL-блока: [отчёт и снимки](../tasks/harden-collection-reliability/verification.md).

Для смешанного native smoke с синтетическими Ozon/Ali карточками задайте
`PRICE_SMOKE_ALI=1` перед той же командой. `tests.test_aliexpress_migration`
и `tests.test_aliexpress_integration` требуют disposable TEST_DATABASE_URL;
создают и удаляют только свои приватные схемы. Полная проверка Ali, native и
отдельный live результат: [отчёт](../tasks/add-aliexpress-connector/verification.md).

Для WB PostgreSQL-проверок используйте `tests.test_wildberries_migration` и
`tests.test_wildberries_integration` с disposable TEST_DATABASE_URL. Native
smoke только WB: `PRICE_SMOKE_WB=1 PRICE_SMOKE_ONLY_WB=1`; смешанный Ozon/Ali/WB:
`PRICE_SMOKE_WB=1 PRICE_SMOKE_ALI=1` перед той же командой desktop smoke.
[Отчёт WB](../tasks/add-wildberries-connector/verification.md).


## Проверка производительности

Результаты PERF-02/03/04/05, окружение, ограничения и сырые before/after:
[отчёт](../tasks/improve-ui-and-data-performance/verification.md).
Release Chromium p95 и функциональный native smoke приведены отдельно.

Для UI соберите отдельный mock release с `VITE_E2E_TEST_MODE=true`, поднимите
loopback preview и выполните `node scripts/benchmark_ui.mjs <URL> <output.json>`.
Harness использует 100/1000/5000 in-memory карточек, 5 прогревов и 30 измерений.
Для воспроизводимых замеров после sidebar-переработки (команды из корня):

```sh
cd frontend
VITE_E2E_TEST_MODE=true npx vite build --outDir /tmp/price-watch-ui-before
npx vite preview --outDir /tmp/price-watch-ui-before --host 127.0.0.1 --port 5177 --strictPort
```

В другом терминале из корня:

```sh
node --test scripts/benchmark_ui_metrics.test.mjs
node scripts/benchmark_ui.mjs http://127.0.0.1:5177 /tmp/price-watch-ui-before.json
```

До правок runtime сохраните исходники и baseline; после правок соберите отдельный
`/tmp/price-watch-ui-after`, поднимите preview на 5178 и выполните:

```sh
node scripts/benchmark_ui.mjs http://127.0.0.1:5178 /tmp/price-watch-ui-after.json --baseline=/tmp/price-watch-ui-before.json
```

Обе сборки должны использовать одинаковые обновлённые benchmark и mock fixture.
Стенд использует `dataset=varied`, seed 42, 100/1000/5000 товаров, plain/mixed/group,
5 прогревов и 30 замеров каждого действия, оба направления семи колонок и поиск
при сортировке названий. Отчёт содержит p50/p95, DOM, доступную heap-память,
long tasks, параметры окружения и пороги для каждого действия. Время включает
автоматизацию, реальные DOM-события и ожидание двух кадров/отложенных результатов;
это release Chromium mock, не измерение native WebView. Нет данных памяти — null.
Код выхода 1 означает ошибки приложения или превышение p95: 200 мс, либо снижение
минимум на 30%, если соответствующий baseline >200 мс. Рост относительно baseline
показывается отдельно даже при прохождении порога. `--resume` продолжает тот же
прерванный запуск; для новой сборки/окружения нужен новый отчёт. Сравнение требует
совпадения браузера, машины и параметров данных. Не запускать параллельно сборки
и другие тяжёлые проверки во время измерений. Артефакты хранить вне репозитория.

Desktop production build не содержит performance fixture.

`scripts/benchmark_diagnostics_export.py --schema perf_<name> --case
export|errors|history --size <N>` запускается через `.venv/bin/python`, требует
отдельную `TEST_DATABASE_URL` с именем БД `price_watch_rel_test` и очищает только
выбранную приватную `perf_*` схему. `--source-root` задаёт before/after исходники.
`scripts/benchmark_process_log.py` проверяет память, один ограниченный журнал и
освобождение fd/потока на синтетическом выводе без доступа к пользовательским файлам.

Для native smoke большого каталога:

```bash
PRICE_SMOKE_CATALOG_SIZE=5000 dbus-run-session -- xvfb-run -a -s '-screen 0 1440x1000x24' python scripts/smoke_reliability_desktop.py
```

Нужны также libXtst/libX11. Ввод выполняется только на приватном Xvfb теста;
дополнительные карточки не включаются в сбор.

## Миниатюры списка

```bash
.venv/bin/python -m unittest tests.test_thumbnails tests.test_api tests.test_dependency_boundaries -q
npm --prefix frontend test -- src/components/product/CatalogThumbnail.test.tsx src/api/client.test.ts src/app/App.test.tsx
npm --prefix frontend run test:e2e -- thumbnails.spec.ts
.venv/bin/python -m scripts.benchmark_thumbnails
```

Python использует синтетические JPEG и временные каталоги: рецепт/пиксели,
повторное чтение и перезапуск, смена URL, условные ответы 304, неизменное тело,
дедупликация, лимит двух операций, отмена, ошибки и ограничения источника,
авторизация и текущий главный вариант. E2E проверяет обычные/вложенные строки
68 × 68 с PNG 153 × 204 при DPR 1/2 и оригиналы в сетке/деталях.
Это mock UI, не live CDN и не проверка Tauri WebView.

Benchmark генерирует 100 разных JPEG 1800 × 2400, читает их с локального диска
и сравнивает холодный кэш с новым экземпляром сервиса на готовом кэше.
Он сообщает wall/CPU, число загрузок/преобразований и PNG-байты. Сетевой задержки
в измерении нет; результат не предсказывает время загрузки из маркетплейсов.
