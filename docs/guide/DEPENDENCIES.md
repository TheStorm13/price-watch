# Зависимости и повторяемая установка

[К содержанию](README.md)

Поддерживаемая локальная сборка проверена на Linux x86_64 с Python 3.14,
Node 26 и Rust 1.99. При другом Python или другой платформе Python lock нужно
создать и проверить отдельно. Версии прямых пакетов проверены на путях desktop,
worker, CLI, числового Ozon JSON и браузерных E2E; подтверждённых
неиспользуемых прямых пакетов не найдено.

## Обычная установка

Из корня репозитория:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
.venv/bin/python -m pip check
npm --prefix frontend ci
cargo test --locked --manifest-path frontend/src-tauri/Cargo.toml
npm --prefix frontend run desktop:build
```

`requirements.in` задаёт прямые Python-зависимости и проверенные границы
совместимости. `requirements.txt` содержит точные версии всех зависимостей и
SHA-256 их архивов. `frontend/package.json` содержит точные прямые версии,
`package-lock.json` фиксирует транзитивные; `npm ci` отвергает расхождение
manifest и lock. `Cargo.toml` задаёт совместимые прямые версии, `Cargo.lock`
фиксирует транзитивные; Cargo-команды с `--locked` отвергают устаревший lock.

## Обновление версий

После изменения прямых Python-зависимостей в `requirements.in` на той же
целевой платформе создайте отдельную среду для `pip-tools==7.6.2` и
пересоберите lock:

```bash
python3.14 -m venv /tmp/price-watch-lock-venv
/tmp/price-watch-lock-venv/bin/python -m pip install 'pip-tools==7.6.2'
/tmp/price-watch-lock-venv/bin/pip-compile --generate-hashes --resolver=backtracking --output-file=requirements.txt requirements.in
```

Просмотрите изменения версий и хешей. Для проверки согласованности входа и
lock в чистом checkout используйте следующий блок: если `requirements.in`
изменён без обновления lock, он остановится до установки.

```bash
set -e
/tmp/price-watch-lock-venv/bin/pip-compile --quiet --generate-hashes --resolver=backtracking --output-file=requirements.txt requirements.in
git diff --exit-code -- requirements.txt
.venv/bin/python -m pip install --require-hashes -r requirements.txt
.venv/bin/python -m pip check
```

После изменения npm-зависимостей обновите `package-lock.json` через npm,
выполните чистый `npm ci`. После изменения Rust-зависимостей обновите
`Cargo.lock` через Cargo и выполните `cargo test --locked`. Затем проверьте
frontend unit-тесты, браузерные E2E, desktop build и изолированный запуск
локальных служб. Команды проверок перечислены в
[тестировании](TESTING_AND_TROUBLESHOOTING.md).

Релизный архив включает оба Python-файла. Пакет AUR использует системные
Python-пакеты Arch и не запускает pip поверх них; локальный Python lock служит
для разработки и сборок вне системного менеджера пакетов.


Уведомления о целевой цене используют `@tauri-apps/plugin-notification` и
`tauri-plugin-notification` 2.8.1. Оба lockfile обновлены, остальные прежние
Cargo-версии сохранены. Плагин зарегистрирован в Rust и разрешён capability
`notification:default`; пользователь включает доставку отдельно и разрешает её
в ОС. Текущий change проверяет Cargo metadata/fetch с `--locked`, без native-
сборки; ручная доставка ОС и работа из трея требуют desktop-проверки пользователем.
