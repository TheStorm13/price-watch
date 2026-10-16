#!/usr/bin/env bash
set -euo pipefail

project_dir="$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"
cd "$project_dir"

if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
  echo 'Релизный архив поддерживается только для Linux x86_64' >&2
  exit 1
fi
if [[ -n $(git status --porcelain) ]]; then
  echo 'Сначала закоммитьте изменения: архив должен соответствовать одному коммиту' >&2
  exit 1
fi

version="$(sed -n 's/^version = "\([^"]*\)"/\1/p' frontend/src-tauri/Cargo.toml | head -n 1)"
if [[ -z "$version" ]]; then
  echo 'Не найдена версия приложения в frontend/src-tauri/Cargo.toml' >&2
  exit 1
fi

npm --prefix frontend ci
npm --prefix frontend run desktop:build

archive_name="price-watch-${version}-linux-x86_64"
staging="$(mktemp -d)"
trap 'rm -rf -- "$staging"' EXIT
mkdir -p "$staging/$archive_name" release
git archive HEAD -- main.py alembic.ini requirements.txt marketplace_connector \
  ozon_article_json price_analyzer | tar -xf - -C "$staging/$archive_name"
install -m755 frontend/src-tauri/target/release/price-watch-desktop \
  "$staging/$archive_name/price-watch-desktop"
install -m644 packaging/aur/price-watch.desktop \
  "$staging/$archive_name/price-watch.desktop"
install -m644 frontend/src-tauri/icons/icon.png \
  "$staging/$archive_name/price-watch.png"

tar --sort=name --mtime='@0' --owner=0 --group=0 --numeric-owner \
  -czf "release/$archive_name.tar.gz" -C "$staging" "$archive_name"
sha256sum "release/$archive_name.tar.gz" > "release/$archive_name.tar.gz.sha256"
echo "Создан release/$archive_name.tar.gz"
