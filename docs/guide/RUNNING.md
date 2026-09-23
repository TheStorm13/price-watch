# Запуск и режимы работы

[К содержанию](README.md)

Команды ниже выполняются из корня репозитория, если не указано иное. Основной
режим — Tauri на Linux. Нужны запущенный Docker с Compose, Python, Node.js/npm,
Rust и установленный системный Google Chrome. Chrome открывается только во время
сбора товара, а не сразу при открытии приложения.

## Первый desktop запуск

```bash
cp -n .env.example .env
python -m venv .venv
.venv/bin/pip install -r requirements.txt
npm --prefix frontend install
npm --prefix frontend run desktop:build
./price-watch
```

`./price-watch` запускает файл
`frontend/src-tauri/target/release/price-watch-desktop`. Скрипт сам его не
собирает: после изменения Rust или frontend кода повторите `desktop:build`.
Скрипт сборки вызывает `tauri build --no-bundle`, а в конфигурации Tauri
`bundle.active` равно `false`. AppImage не нужен и не создаётся.

Во время запуска Tauri читает корневой `.env`, останавливает контейнерные
`worker` и `frontend`, поднимает через Compose `db`, `migrate`, `api`, `logs` и
`desktop-worker-logs`, дожидается API на `127.0.0.1:8000`, затем запускает
`.venv/bin/python main.py worker` на хосте. Окно приложения показывает ошибку и
кнопку повторения, если этот старт не удался.

После закрытия Tauri локальный worker завершается. Контейнеры PostgreSQL, API
и логов остаются работать. Для остановки контейнеров с сохранением данных:

```bash
docker compose down
```

`docker compose down --volumes` удаляет том PostgreSQL с историей цен, а также
профиль контейнерного браузера и данные Dozzle. Для обычной остановки эта
команда не нужна.

## Разработка desktop приложения

```bash
npm --prefix frontend run desktop
```

Команда запускает Tauri и Vite на `127.0.0.1:1420` с обновлением интерфейса.
В debug режиме Tauri выполняет `docker compose up --build`; release бинарник
при обычном `./price-watch` Docker образы автоматически не пересобирает. После
изменения Python API или миграций сначала обновите контейнеры:

```bash
docker compose up --build -d db migrate api logs desktop-worker-logs
```

После этого запустите `./price-watch` повторно. Изменения Python worker
подхватываются при новом запуске Tauri, потому что worker работает из локальной
`.venv`, а не из Docker образа.

## Дополнительный web режим

Для запуска в браузере, включая контейнерный Chromium с noVNC:

```bash
docker compose up --build -d
```

| Адрес | Назначение |
| --- | --- |
| `http://127.0.0.1:5173` | Web интерфейс |
| `http://127.0.0.1:8000/docs` | Swagger API |
| `http://127.0.0.1:6080/vnc.html` | Окно контейнерного Chromium |
| `http://127.0.0.1:8080` | Логи Dozzle |

Этот режим использует контейнерные `frontend` и `worker`. Следующий запуск
Tauri остановит их и вернётся к локальному worker с системным Chrome.

## CLI без интерфейса

Для команд с БД передайте `DATABASE_URL` через окружение или параметр
`--database-url`. При настройках из `.env.example`:

```bash
set -a
source .env
set +a
.venv/bin/python main.py db migrate
.venv/bin/python main.py card add --marketplace ozon --external-id 4465694803
.venv/bin/python main.py card list
.venv/bin/python main.py collect --card-id 1
.venv/bin/python main.py history --card-id 1 --days 30
.venv/bin/python main.py run last
```

Число после `--card-id` — внутренний ID карточки из `card list`, а не артикул
Ozon. `collect` работает синхронно и ждёт подтверждение антибот-проверки в
терминале. Совместимый одиночный вызов без PostgreSQL:

```bash
.venv/bin/python main.py 4465694803
```

Артикулы в примерах демонстрационные: доступность товара на Ozon может
измениться.
