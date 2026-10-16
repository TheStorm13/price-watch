# Релиз Linux и пакет AUR

[К содержанию](README.md)

Пакет `price-watch-bin` содержит
готовый Tauri бинарник, Python код приложения, ярлык и иконку. Зависимости Python,
PostgreSQL, Xvfb и Google Chrome устанавливаются пакетным менеджером Arch.
Пользовательские данные находятся в каталогах XDG и не входят в пакет.

## Локальный пакет без публикации

Версия приложения задаётся в одном месте: `frontend/src-tauri/Cargo.toml`,
в поле `package.version`. Tauri использует её, когда `version` отсутствует
в `tauri.conf.json`; приватному npm-пакету интерфейса отдельная версия не
нужна. `Cargo.lock` обновляется Cargo автоматически и не редактируется вручную.

Для следующей версии измените только поле `package.version` в `Cargo.toml`,
затем выполните:

```bash
cargo check --manifest-path frontend/src-tauri/Cargo.toml
git add frontend/src-tauri/Cargo.toml frontend/src-tauri/Cargo.lock
git commit -m "build: prepare next version"
```

`Cargo.lock` обновляется Cargo автоматически. Скрипт сборки требует чистого
рабочего дерева, чтобы Python-код в архиве соответствовал тому же коммиту,
что и бинарник.

На Arch Linux x86_64 соберите локальный пакет:

```bash
packaging/build-local-aur.sh
```

Скрипт создаёт архив в `release/`, копирует рецепт в
`release/aur-local/PKGBUILD`, подставляет версию и SHA-256 и собирает пакет
через `makepkg`. Он не отправляет ничего в GitHub или AUR. Готовый файл
`release/aur-local/price-watch-bin-VERSION-1-x86_64.pkg.tar.zst` можно
установить командой `sudo pacman -U путь-к-файлу`. Для `makepkg` должны быть
установлены зависимости из рецепта, включая `google-chrome`.

## Подготовка публичного релиза в будущем

Из чистого рабочего дерева на Linux x86_64 выполните:

```bash
packaging/make-linux-release.sh
```

Скрипт читает версию из Cargo, устанавливает фиксированные npm зависимости,
собирает desktop бинарник и создаёт
`release/price-watch-VERSION-linux-x86_64.tar.gz` и файл SHA-256 рядом. Он берёт
Python код из текущего коммита; `.env`, профили Chrome, базы и логи в архив
не попадают. Для следующего релиза обновите версию только в `Cargo.toml`.

После проверки архива создайте тег `vVERSION` на том же коммите, отправьте тег
в GitHub и загрузите архив в GitHub Releases. URL архива указан в
`packaging/aur/PKGBUILD`.

## Публикация рецепта AUR в будущем

Публичный `packaging/aur/PKGBUILD` пока указывает на опубликованный архив
`0.1.1`. При следующей публикации обновите `pkgver`, `pkgrel` и
`sha256sums` для нового GitHub Release. Затем в каталоге `packaging/aur`
выполните:

```bash
makepkg --printsrcinfo > .SRCINFO
makepkg --verifysource
makepkg
```

Обычный `makepkg` требует установленных зависимостей, включая `google-chrome`
из AUR. Рецепт AUR публикуется отдельно от основного репозитория: в AUR нужно
отправлять только `PKGBUILD` и `.SRCINFO`, без собранного архива и готового
`.pkg.tar.zst`. Исходный код проекта пока не имеет лицензии; `license=('unknown')`
в рецепте фиксирует этот факт, не выдавая его за MIT.

После установки приложение запускается командой `price-watch` или через меню.
Код лежит в `/usr/lib/price-watch`, пользовательские данные остаются в
`~/.local/share/price-watch` и `~/.local/state/price-watch`. Удаление или
обновление пакета не должно удалять базу и профиль Chrome.
