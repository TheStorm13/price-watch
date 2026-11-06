# Проверки и диагностика

[К содержанию](README.md)

## Локальные службы

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
