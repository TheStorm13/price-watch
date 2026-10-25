#!/usr/bin/env bash
set -euo pipefail

project_dir="$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"
cd "$project_dir"
local_dir="release/aur-local"
latest_link="$local_dir/price-watch-bin-latest.pkg.tar.zst"

# A failed build must not leave a previous package looking like this run's result.
if [[ -L "$latest_link" ]]; then
  rm -- "$latest_link"
elif [[ -e "$latest_link" ]]; then
  echo "Ожидалась символическая ссылка: $latest_link" >&2
  exit 1
fi

if ! command -v makepkg >/dev/null 2>&1; then
  echo 'Не найден makepkg: установите пакетный инструментарий Arch' >&2
  exit 1
fi

packaging/make-linux-release.sh

version="$(sed -n 's/^version = "\([^"]*\)"/\1/p' frontend/src-tauri/Cargo.toml | head -n 1)"
archive_name="price-watch-${version}-linux-x86_64.tar.gz"
archive="release/$archive_name"
checksum="$(sha256sum "$archive" | cut -d ' ' -f 1)"
mkdir -p "$local_dir"

python3 - "$version" "$checksum" "$archive_name" "$local_dir" <<'PY'
from pathlib import Path
import re
import sys

version, checksum, archive_name, local_dir = sys.argv[1:]
destination = Path(local_dir)
recipe = Path("packaging/aur/PKGBUILD").read_text()
updates = {
    r"^pkgver=.*$": f"pkgver={version}",
    r"^source=.*$": 'source=("${_archive}")',
    r"^sha256sums=.*$": f"sha256sums=('{checksum}')",
}
for pattern, replacement in updates.items():
    recipe, count = re.subn(pattern, replacement, recipe, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"Ожидалась одна строка {pattern} в PKGBUILD, найдено: {count}")
(destination / "PKGBUILD").write_text(recipe)
link = destination / archive_name
if link.is_symlink():
    link.unlink()
elif link.exists():
    raise SystemExit(f"Файл {link} уже существует; не заменяю его")
link.symlink_to(Path("..") / archive_name)
PY

cd "$local_dir"
makepkg --printsrcinfo > .SRCINFO
makepkg --verifysource --force
makepkg --cleanbuild --force
package_name="price-watch-bin-${version}-1-x86_64.pkg.tar.zst"
package_binary="$(mktemp)"
trap 'rm -f -- "$package_binary"' EXIT
bsdtar -xOf "$package_name" usr/bin/price-watch > "$package_binary"
source_build_id="$(readelf -n "$project_dir/frontend/src-tauri/target/release/price-watch" | sed -n 's/.*Build ID: //p' | head -n 1)"
package_build_id="$(readelf -n "$package_binary" | sed -n 's/.*Build ID: //p' | head -n 1)"
if [[ -z "$source_build_id" || "$source_build_id" != "$package_build_id" ]]; then
  echo 'Бинарник в пакете не совпадает с только что собранным Tauri-бинарником' >&2
  exit 1
fi
ln -sfn -- "$package_name" price-watch-bin-latest.pkg.tar.zst
echo "Локальный пакет: $local_dir/price-watch-bin-latest.pkg.tar.zst"
