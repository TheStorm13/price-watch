# Запуск приложения

[К содержанию](README.md)

Команды выполняются из корня репозитория. Для desktop нужны системные
`postgresql`, `xorg-server-xvfb`, `xorg-xauth`, Google Chrome, Python,
Node.js/npm и Rust. Локальные PostgreSQL, API, Xvfb и worker запускаются
вместе с приложением и завершаются при его закрытии.

## Первый запуск

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
npm --prefix frontend install
npm --prefix frontend run desktop:build
./price-watch
```

`./price-watch` запускает готовый Tauri бинарник из
`frontend/src-tauri/target/release/price-watch-desktop`. После изменения Rust
или интерфейса повторите `desktop:build`; после изменения Python перезапустите
приложение. AppImage не создаётся. При установке готового пакета из релиза
сборка из исходников не требуется.

База, профиль Chrome и логи находятся в пользовательских каталогах XDG;
подробности приведены в [описании локальных служб](NATIVE_DESKTOP.md).
Кнопка «Открыть Chrome» запускает видимый браузер. Перед ручным или
автоматическим сбором приложение закрывает его, а worker запускает Chrome
с тем же профилем на скрытом дисплее.

## Разработка desktop приложения

```bash
npm --prefix frontend run desktop
```

Команда запускает Tauri и Vite на `127.0.0.1:1420` с обновлением интерфейса.
Для разработки интерфейса без базы используйте
`npm --prefix frontend run dev:demo`.

## CLI без интерфейса

Прямым командам с БД нужен отдельный доступный PostgreSQL. Создайте базу
самостоятельно и передайте её адрес через `DATABASE_URL` или
`--database-url`. Эти команды не запускают локальные службы Tauri.

```bash
export DATABASE_URL='postgresql://user:password@localhost:5432/price_watch'
.venv/bin/python main.py db migrate
.venv/bin/python main.py card add --marketplace ozon --external-id 4465694803
.venv/bin/python main.py card list
.venv/bin/python main.py collect --card-id 1
.venv/bin/python main.py history --card-id 1 --days 30
.venv/bin/python main.py run last
```

Число после `--card-id` — внутренний ID карточки из `card list`.
Команда `collect` ждёт завершения сбора и подтверждения проверки Ozon в
терминале. Одиночный вызов без PostgreSQL:

```bash
.venv/bin/python main.py 4465694803
```

Доступность демонстрационных артикулов на Ozon может измениться.
