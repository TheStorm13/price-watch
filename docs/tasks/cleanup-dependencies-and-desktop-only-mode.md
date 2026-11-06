# Очистка зависимостей и удаление live web-режима

- Фаза: завершено; план и реализация приняты пользователем.
- OpenSpec: `openspec/changes/archive/2026-10-20-cleanup-dependencies-and-desktop-only-mode/`.
- ADR: `docs/adr/0002-desktop-only-live-ui.md` (Accepted; desktop как единственный live UI).
- Существующее изменение `background-price-tracking` и его локальные правки не трогать; реализацию строить на актуальном дереве.

## Установленное состояние

- Tauri вызывает `dev:desktop`/`build:desktop`. Обычные `dev`/`build` и Vite proxy предоставляют отдельный live web-путь на FastAPI с портом 8000.
- `dev:e2e` даёт mock UI для 22 Playwright E2E без PostgreSQL. Пользователь решил сохранить его как основное автоматическое покрытие интерфейса.
- В `frontend/package.json` есть `latest`; npm и Cargo lockfiles сохранены в Git. В `requirements.txt` только широкие прямые диапазоны. AUR использует системные Python пакеты.
- Локальный первичный снимок размера (не сопоставимый build baseline): `frontend/dist` 804 KiB, desktop binary 18 MiB, `frontend/node_modules` 262 MiB, `.venv` 266 MiB. При реализации измерить заново по одинаковой процедуре.
- Версии текущего окружения: Python 3.14.8, Node 26.11.1, npm 12.2.1, Cargo 1.99.1.

## План и следующий шаг

План, спецификации и задачи OpenSpec охватили аудит и фиксацию зависимостей,
измерения и удаление только live web-режима. Браузерный E2E и mock API
сохранены; Tauri E2E — отдельная будущая задача. Реализация принята,
затронутая документация обновлена, спецификации синхронизированы, изменение
архивировано.

## Переименование тестового режима

- Команда `dev:e2e`, флаг `VITE_E2E_TEST_MODE`, подпись «Тестовые данные» и документация обновлены; mock API и 22 браузерных E2E сохранены.
- Проверено: frontend lint, Vitest (18 тестов), браузерный E2E (22 теста), `build:desktop` и `desktop:build` прошли 2026-10-20.
- 2026-10-20: пользователь принял переименование тестового режима. Эта отдельная правка завершена.
- 2026-10-20: пользователь напомнил, что исходная задача остаётся открытой; OpenSpec change пересмотрен с сохранением браузерного E2E. До одобрения пересмотренного плана реализацию не начинать.
- 2026-10-20: уточнено, что обязательный замер касается размера сборки до и после очистки. Runtime-профилирование нужно только при конкретной проблеме производительности перед её оптимизацией; общий performance-рефакторинг не входит в план.
- 2026-10-20: пользователь попросил ограничиться обдумыванием точечного исправления при найденной проблеме, собрать до/после, проверить и начать работу. Это явное одобрение пересмотренного плана. Следующий шаг: реализация по `tasks.md`, проверки после каждого этапа, затем Gate 2 — приёмка результата до архивирования.

## Сопоставимый замер до изменений

Окружение: Linux x86_64, Python 3.14.8, pip 26.2.1, Node 26.11.1, npm 12.2.1, Cargo/rustc 1.99.1. Команда сборки: `npm --prefix frontend run desktop:build` (Tauri `--no-bundle`, профиль release). Для чистой установки до и после: `npm --prefix frontend ci`; Rust использует `cargo test --locked`, Python после введения lock — `pip install --require-hashes -r requirements.txt` в новой venv. Существовавшие до правок `node_modules` и `.venv` не переустанавливались для замера размера.

Размеры в байтах: сумма файлов `frontend/dist` — **811704**; `frontend/src-tauri/target/release/price-watch-desktop` — **18646336**; локальный архив — **4945013**. Архив собирался командой `python /tmp/price-watch-size-snapshot.py /tmp/price-watch-size-before.tar.gz`: все отслеживаемые и неигнорируемые текущие файлы из путей релизного `git archive`, текущий бинарник, `.desktop` и иконка; `tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -czf`. Этот же скрипт и команда применяются после изменений. Поскольку дерево содержит незакоммиченные изменения, это эквивалентный локальный staging, а не официальный архив из `HEAD`.

## Аудит прямых зависимостей

Каждая строка ниже проверена по исходным импортам, конфигурации Tauri/Vite, тестам и AUR. Решение «оставить» означает, что удаление нарушит указанный путь; неподтверждённых кандидатов на удаление нет.

| Экосистема | Пакет | Потребитель и решение |
|---|---|---|
| Python | alembic | миграции API/desktop; оставить |
| Python | fastapi | локальный API desktop и CLI; оставить |
| Python | httpx | API-тесты, CLI и HTTP-клиент; оставить |
| Python | playwright | Ozon Chrome collector и numeric JSON; оставить |
| Python | psycopg[binary] | синхронный и асинхронный PostgreSQL; оставить |
| Python | pydantic | схемы API; оставить |
| Python | sqlalchemy | хранилище и миграции; оставить |
| Python | uvicorn | `main.py api` и desktop-служба; оставить |
| Rust | tauri-build | build.rs; оставить |
| Rust | dotenvy | конфигурация desktop-служб; оставить |
| Rust | libc | сигнализация/блокировка Linux процессов; оставить |
| Rust | serde | IPC payload; оставить |
| Rust | tauri | desktop shell и tray; оставить |
| Rust | tauri-plugin-autostart | автозапуск; оставить |
| Rust | tauri-plugin-dialog | системные диалоги; оставить |
| Rust | tauri-plugin-opener | открытие ссылок; оставить |
| Rust | tauri-plugin-single-instance | единственный экземпляр; оставить |
| npm runtime | @tanstack/react-query | запросы и кеш UI; оставить |
| npm runtime | @tauri-apps/api | IPC desktop; оставить |
| npm runtime | @tauri-apps/plugin-opener | открытие товара; оставить |
| npm runtime | lucide-react | иконки UI; оставить |
| npm runtime | react | компоненты; оставить |
| npm runtime | react-dom | рендеринг; оставить |
| npm runtime | react-router-dom | маршруты; оставить |
| npm runtime | recharts | график цен; оставить |
| npm dev | @playwright/test | браузерные E2E; оставить |
| npm dev | @tauri-apps/cli | desktop dev/build; оставить |
| npm dev | @testing-library/jest-dom | DOM assertions; оставить |
| npm dev | @testing-library/react | unit UI; оставить |
| npm dev | @testing-library/user-event | unit UI interaction; оставить |
| npm dev | @types/node | TypeScript Node config; оставить |
| npm dev | @types/react | TypeScript React; оставить |
| npm dev | @types/react-dom | TypeScript ReactDOM; оставить |
| npm dev | @vitejs/plugin-react | Vite React build; оставить |
| npm dev | jsdom | Vitest DOM environment; оставить |
| npm dev | typescript | typecheck/build; оставить |
| npm dev | vite | desktop/E2E bundler; оставить |
| npm dev | vitest | unit runner/config; оставить |

`psycopg`, `httpx` и `playwright` также используются в тестах/сборке; AUR перечисляет соответствующие системные Python-пакеты. Отдельные CLI (`api`, `collect`, worker) и numeric Ozon JSON сохраняются по решению пользователя.

## После удаления live web

- Frontend: `lint` прошёл, Vitest 19/19, Playwright 22/22, `desktop:build` прошёл.
- Python: `unittest discover` 83 теста, 20 PostgreSQL integration пропущены из-за отсутствия `TEST_DATABASE_URL`. API auth/CORS, worker и CLI входят в выполненные unit-тесты.
- `main.py api --help`, `collect --help`, `worker --help`, импорт обоих CLI без `DATABASE_URL` и маршрутизация numeric ID без БД прошли. Реальный сбор товара и работа с рабочей базой не запускались.
- Изолированный Rust smoke `starts_native_worker_without_opening_chrome` запустил PostgreSQL, API и worker в `/tmp/price-watch-smoke.*`; готовность API проверяется внутри теста. Отдельный запуск GUI-бинарника завершился сразу, поскольку уже работает экземпляр `price-watch-desktop --background` (single-instance). Его не останавливаем. Desktop-сборка и проверка нативных служб выполнены.

## npm и Rust после фиксации версий

- `package.json`: все 21 прямые версии зафиксированы по установленным и проверенным пакетам из `package-lock.json`; ни один пакет не удалён без доказательства неиспользования. `npm ci`, lint, Vitest 19/19, Playwright 22/22, `desktop:build` прошли.
- `Cargo.toml`: прямые версии уточнены по `cargo tree --locked --depth 1`; все 9 crates нужны. `cargo test --locked`: 7 пройдено, 2 интеграционных ignored; `cargo build --release --locked` и изолированный native smoke прошли. Текущий размер после этих этапов: assets 811700 байт, binary 18431264 байта; итоговые размеры будут получены после Python lock и повторной одинаковой сборки.

## Python lock

`requirements.in` содержит 8 прямых зависимостей с проверенными совместимыми границами. `requirements.txt` сгенерирован `pip-tools==7.6.2` для Linux x86_64/Python 3.14 командой из `requirements.in`, включает точные версии и SHA-256 всех транзитивных пакетов. Чистая `/tmp/price-watch-check-venv`: `pip install --require-hashes -r requirements.txt` и `pip check` прошли; повторная генерация дала тот же SHA-256 lock-файла. Python suite из новой venv: 83 теста, 20 PostgreSQL integration пропущены без `TEST_DATABASE_URL`; оба CLI импортируются и команды `api`, `collect`, `worker` разбираются без `DATABASE_URL`. Native smoke с новой venv поднял PostgreSQL/API/worker и проверил готовность API. Реальный сбор товара не запускался.

## Итоговая проверка и размер

Повторная команда `npm --prefix frontend run desktop:build` и тот же `/tmp/price-watch-size-snapshot.py` с выходом `/tmp/price-watch-size-after.tar.gz`. Условия и состав архива те же, что до изменений; добавился новый `requirements.in`, а `requirements.txt` теперь содержит транзитивный lock с хешами.

| Артефакт | До, байт | После, байт | Разница |
|---|---:|---:|---:|
| `frontend/dist`, сумма файлов | 811704 | 811700 | −4 |
| release desktop binary | 18646336 | 18646328 | −8 |
| локальный `tar.gz` | 4945013 | 4968189 | +23176 (+0,47%) |

В `tar -tzf` проверены `main.py`, binary, `requirements.in` и хешированный `requirements.txt`. `bash -n` для релизного скрипта и PKGBUILD, `makepkg --printsrcinfo`, фактическая функция `package()` на локальном staging с обоими requirements, а также её запуск на варианте без `requirements.in` прошли. Релизный скрипт с `git archive HEAD` не запускался: его собственное условие требует чистое дерево и зафиксированный коммит. Тестовый staging повторяет его состав с текущими изменениями.

Последний прогон: browser E2E 22/22, `desktop:build`, Python unit/API/CLI 83 (20 PostgreSQL integration пропущены), clean hash install и `pip check`, Rust `cargo test --locked` 7/7 (+2 ignored) и изолированный native smoke — прошли. Прямой CLI сбор живого товара и GUI запуск под другим instance не проверялись: для первого нужны внешний сайт/браузер и тестовая база, второму мешает уже запущенный экземпляр приложения. Runtime-узкое место в этих проверках не выявлено; оптимизацию производительности не добавляли.

## Финальный обзор перед Gate 2

- Статический поиск не находит Vite 5173, demo-флага и plain web `dev`/`build`/`preview` в frontend runtime и CORS. Тест дополнен проверкой, что preflight со старым web origin отклоняется, тогда как Tauri origin разрешён; Python suite повторно прошёл.
- Desktop API token, local service startup и API маршруты сохранены; новый frontend guard запрещает live запросы без desktop-конфигурации. Mock-backed `dev:e2e`, 22 Playwright сценария, worker, CLI и numeric dispatcher остаются доступны.
- Модели БД, миграции и операции с историей цен этим изменением не менялись. Существующие правки `background-price-tracking` в общем дереве сохранены. `git diff --check` и `openspec validate --strict` прошли.
- Общая release команда с `git archive HEAD` доступна после коммита в чистом дереве; текущий эквивалентный архив и фактическая функция AUR `package()` проверены. Реальные PostgreSQL integration и внешний сбор не запускались без отдельного тестового источника.
- 2026-10-20: пользователь принял реализацию (Gate 2). Затронутые README/гайды и ADR обновлены, устаревшая команда plain `npm run build` удалена из инструкций, обе основные спецификации синхронизированы и прошли `openspec validate --specs`, OpenSpec change архивирован.
