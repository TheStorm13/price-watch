# Релиз Linux и пакет AUR

[К содержанию](README.md)

Нативный desktop режим не требует Docker. Пакет `price-watch-bin` содержит
готовый Tauri бинарник, Python код приложения, ярлык и иконку. Зависимости Python,
PostgreSQL, Xvfb и Google Chrome устанавливаются пакетным менеджером Arch.
Пользовательские данные находятся в каталогах XDG и не входят в пакет.

## Подготовка релиза

Из чистого рабочего дерева на Linux x86_64 выполните:

```bash
packaging/make-linux-release.sh
```

Скрипт проверяет совпадение версий Tauri и Cargo, устанавливает фиксированные
npm зависимости, собирает desktop бинарник и создаёт
`release/price-watch-VERSION-linux-x86_64.tar.gz` и файл SHA-256 рядом. Он берёт
Python код из текущего коммита; `.env`, профили Chrome, базы и логи в архив
не попадают. Для следующего релиза обновите версии в `tauri.conf.json`,
`Cargo.toml` и `frontend/package.json`.

После проверки архива создайте тег `vVERSION` на том же коммите, отправьте тег
в GitHub и загрузите архив в GitHub Releases. URL архива указан в
`packaging/aur/PKGBUILD`.

## Обновление AUR

Для каждого нового архива обновите `pkgver`, `pkgrel` и `sha256sums` в
`packaging/aur/PKGBUILD`. Затем в каталоге `packaging/aur` выполните:

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
