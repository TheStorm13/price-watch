# Проверки и диагностика

[К содержанию](README.md)

## Локальные службы

После запуска desktop логи находятся в
`$XDG_STATE_HOME/price-watch/` (обычно `~/.local/state/price-watch/`):
`postgres.log`, `api.log`, `xvfb.log` и `desktop-worker.log`.
Сообщение об ошибке запуска указывает соответствующий файл.
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
| WB: «Не указан размер WB» | Старая карточка сохранена; добавьте конкретный вариант по полной ссылке с size |
| AliExpress: «Не указан SKU» | Старая карточка сохранена без изменений; для нового отслеживания добавьте конкретный SKU по полной ссылке |
| Карточка Ozon не обновилась | Открыть `desktop-worker.log`; исчезнувший товар может вести на страницу предложений |

## Проверка надёжности и каталога

Чистые правила выгодности, выбора представителя и расписания, сборка каталога
из материализованных входов и границы импортов проверяются без БД:

```bash
.venv/bin/python -m unittest tests.test_application_rules tests.test_catalog_service tests.test_dependency_boundaries -v
```

Результаты ARCH-03, сравнение с исходным HTTP-каталогом и baseline/after:
[отчёт проверки](../workflow-runs/separate-business-rules-from-postgres/verification.md).

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
Результаты принятого REL-блока: [отчёт и снимки](../workflow-runs/harden-collection-reliability/verification.md).

Для смешанного native smoke с синтетическими Ozon/Ali карточками задайте
`PRICE_SMOKE_ALI=1` перед той же командой. `tests.test_aliexpress_migration`
и `tests.test_aliexpress_integration` требуют disposable TEST_DATABASE_URL;
создают и удаляют только свои приватные схемы. Полная проверка Ali, native и
отдельный live результат: [отчёт](../workflow-runs/add-aliexpress-connector/verification.md).

Для WB PostgreSQL-проверок используйте `tests.test_wildberries_migration` и
`tests.test_wildberries_integration` с disposable TEST_DATABASE_URL. Native
smoke только WB: `PRICE_SMOKE_WB=1 PRICE_SMOKE_ONLY_WB=1`; смешанный Ozon/Ali/WB:
`PRICE_SMOKE_WB=1 PRICE_SMOKE_ALI=1` перед той же командой desktop smoke.
[Отчёт WB](../workflow-runs/add-wildberries-connector/verification.md).
