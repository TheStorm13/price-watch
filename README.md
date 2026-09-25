# Marketplace Price Analyzer

Приложение хранит карточки маркетплейсов в PostgreSQL, получает актуальное
состояние через унифицированные коннекторы и накапливает историю цен. Сейчас
реализован интерактивный коннектор Ozon; цена Ozon берётся только из
`cardPrice`.

Подробности: [спецификация](docs/SPECIFICATION.md) и
[план реализации](docs/IMPLEMENTATION_PLAN.md). Найденные задачи для следующих
версий записаны в [будущих доработках](docs/FUTURE_CHANGES.md).

Руководство по текущему коду, запуску и известным ограничениям находится в
[docs/guide](docs/guide/README.md).

Web-интерфейс находится в каталоге `frontend` и по умолчанию работает с
реальным FastAPI backend. Команда `npm run dev:demo` оставлена только для
изолированной разработки интерфейса без PostgreSQL.

### Desktop-запуск

Основной режим для одного ПК — Tauri-приложение. Запуск из корня проекта:

```bash
./price-watch
```

Это единственная команда: приложение само поднимает через Docker Compose
PostgreSQL, миграции, API и Dozzle, после чего запускает локальный Playwright
worker. При сборе Chrome работает без всплывающего окна. Кнопка «Открыть Chrome»
в боковой панели сразу открывает три вкладки: Ozon, Wildberries и AliExpress в отдельном профиле
`.playwright-profile` для входа и проверки сайтов. Перед сбором приложение закрывает
ручное окно, затем запускает Chrome с тем же профилем на скрытом дисплее Xvfb.
Авторизация сохраняется, рабочие вкладки не появляются на экране. Во время сбора
кнопка недоступна. При закрытии Tauri локальный worker и открытый через приложение
Chrome завершаются; PostgreSQL и API остаются запущены для
быстрого следующего старта.

Пересобрать desktop-бинарник после изменения исходников:

```bash
npm --prefix frontend install
npm --prefix frontend run desktop:build
```

Сборка создаёт исполняемый файл Tauri `frontend/src-tauri/target/release/price-watch-desktop`.
Команда использует `--no-bundle`: AppImage и другие установочные пакеты не собираются.
`./price-watch` запускает именно этот файл. Для desktop worker требуется установленный
Google Chrome; скрытый дисплей Xvfb запускается в отдельном контейнере Docker.
Chromium из Docker применяется только в web-режиме.

Для разработки с hot reload используется:

```bash
npm --prefix frontend run desktop
```

Логи доступны в Dozzle по адресу <http://127.0.0.1:8080>. Локальный worker
передаёт туда вывод через сервис `desktop-worker-logs`; исходный файл находится
в `output/desktop-worker.log`.

### Web-запуск через Docker Compose

```bash
cp -n .env.example .env
docker compose up --build -d
```

Этот альтернативный режим оставлен для запуска приложения в браузере. Compose:

- поднимает PostgreSQL;
- применяет Alembic-миграции отдельным сервисом `migrate`;
- запускает FastAPI и worker;
- собирает React и отдаёт его через Nginx;
- запускает Playwright Chromium в виртуальном дисплее с noVNC;
- показывает логи всех контейнеров проекта через Dozzle.

Проверить состояние и посмотреть логи:

```bash
docker compose ps -a
docker compose logs -f api worker
```

Откройте:

- приложение: <http://127.0.0.1:5173>;
- Swagger: <http://127.0.0.1:8000/docs>;
- Chromium worker: <http://127.0.0.1:6080/vnc.html?autoconnect=true&resize=scale>;
- логи приложения: <http://127.0.0.1:8080>.

При запуске сбора вкладка Chromium больше не открывается автоматически.
Если Ozon запросит проверку, откройте Chromium кнопкой в панели проверки,
пройдите её и нажмите «Проверка пройдена». Профиль Chromium хранится в Docker
volume и не теряется при обычном перезапуске.

Остановить приложение с сохранением данных:

```bash
docker compose down
```

Команда `docker compose down --volumes` дополнительно удалит базу, профиль
Chromium и настройки Dozzle, поэтому используйте её только для полного сброса.

## Локальная разработка без полной контейнеризации

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

При локальном запуске Playwright использует установленный Google Chrome через
канал `chrome`, поэтому отдельная команда `playwright install-deps` на Arch
Linux не нужна. В Docker используется Chromium из зафиксированного образа
Playwright 1.63.0.

Скопируйте настройки локального окружения и экспортируйте их для CLI:

```bash
cp .env.example .env
set -a
source .env
set +a
```

Для локальной разработки можно поднять только PostgreSQL 18:

```bash
docker compose up -d db
docker compose ps
```

Примените миграции:

```bash
.venv/bin/python main.py db migrate
```

Команда повторяемая: уже применённые миграции будут пропущены.

Остановить PostgreSQL, сохранив данные:

```bash
docker compose down
```

Удалить контейнер вместе с локальной базой можно явно командой
`docker compose down --volumes`. Она необратимо удаляет историю цен.

## Работа с карточками

Одна карточка принадлежит одному маркетплейсу. Одинаковый физический товар на
разных площадках добавляется отдельными карточками.

```bash
.venv/bin/python main.py card add \
  --marketplace ozon \
  --external-id 1604900984

.venv/bin/python main.py card list
```

## Сбор цен

Собрать все активные карточки:

```bash
.venv/bin/python main.py collect
```

Собрать одну карточку:

```bash
.venv/bin/python main.py collect --card-id 1
```

Прямой CLI-сбор по умолчанию откроет обычный видимый Chrome с отдельным профилем
`.playwright-profile`, после чего Playwright подключится к нему по CDP. Для CLI
доступен флаг `--headless`. Desktop worker вместо headless запускает обычный
Chrome на скрытом дисплее Xvfb, используя тот же профиль. Коннектор
сначала дожидается завершения проверки на странице товара и только затем получает
JSON через `fetch` из той же вкладки. Если фоновый desktop сбор встретит проверку Ozon, он завершит
карточку с подсказкой открыть Chrome, пройти проверку и повторить сбор. При прямом
CLI-сборе подтверждение остаётся в терминале.
В одном Chrome приложение обрабатывает до пяти карточек Ozon одновременно,
открывая отдельную вкладку для каждой. Результаты и ошибки сохраняются по
карточкам; запись в PostgreSQL выполняется последовательно.

По умолчанию Chrome запускается через X11/XWayland, поскольку нативный Wayland
может падать при старте на некоторых конфигурациях Linux. Режим можно изменить
через `--chrome-platform wayland` или `--chrome-platform auto`.

При необходимости задайте исполняемый файл Chrome:

```bash
.venv/bin/python main.py collect \
  --chrome-binary /usr/bin/google-chrome-stable
```

Ошибка одной карточки записывается в лог, увеличивает `failure_count` запуска и
не останавливает остальные карточки. Отдельной таблицы попыток нет.

## История и запуски

```bash
.venv/bin/python main.py history --card-id 1 --days 30
.venv/bin/python main.py run last
```

Команда `history` возвращает наблюдения и статистику. Средняя цена рассчитывается
как среднее дневных средних только для доступных товаров с известной ценой.
Интерфейс отдельно показывает середину диапазона между минимумом и максимумом.
История хранит первую и последнюю точки каждого плато одинаковой цены и наличия;
внутренние точки удаляются при обновлении. Миграция удаляет такие точки и из
старой истории. График строится по сохранённым изменениям выбранного периода,
а вертикальная ось начинается с нуля.
Ошибки по товарам и полный traceback доступны в деталях запуска.

## Унифицированный контракт коннектора

Каждый коннектор возвращает `marketplace_connector.ProductSnapshot`:

```json
{
  "schema_version": "1.0",
  "ref": {"marketplace": "ozon", "external_id": "1604900984"},
  "title": "Название товара",
  "availability": "in_stock",
  "price": 577,
  "collected_at": "2026-09-21T12:00:00+00:00"
}
```

Формальная схема расположена в
`marketplace_connector/serialization/product.schema.json`. Новый маркетплейс
реализует один порт:

```python
class MarketplaceConnector(Protocol):
    marketplace: str

    def get_product(self, external_id: str) -> ProductSnapshot:
        ...
```

## Совместимый одиночный запуск Ozon

Старый сценарий без PostgreSQL сохранён:

```bash
.venv/bin/python main.py 1604900984
.venv/bin/python main.py 1604900984 --raw > raw-ozon.json
```

## Тесты

Unit-тесты не требуют PostgreSQL или браузера:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Frontend-проверки:

```bash
cd frontend
npm test
npm run test:e2e
npm run build
```

Интеграционный тест репозитория запускается только с явно заданной отдельной
тестовой базой:

```bash
docker compose exec db createdb -U price_analyzer price_analyzer_test
export TEST_DATABASE_URL='postgresql://price_analyzer:price_analyzer@localhost:5432/price_analyzer_test'
.venv/bin/python -m unittest tests.test_postgres_integration -v
```
