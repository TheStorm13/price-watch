#!/usr/bin/env bash
set -euo pipefail

project_dir="$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"
cd "$project_dir"

if ! command -v makepkg >/dev/null 2>&1; then
  echo 'Не найден makepkg: установите пакетный инструментарий Arch' >&2
  exit 1
fi

packaging/make-linux-release.sh

version="$(sed -n 's/^version = "\([^"]*\)"/\1/p' frontend/src-tauri/Cargo.toml | head -n 1)"
archive_name="price-watch-${version}-linux-x86_64.tar.gz"
archive="release/$archive_name"
checksum="$(sha256sum "$archive" | cut -d ' ' -f 1)"
local_dir="release/aur-local"
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
makepkg --verifysource
makepkg --force
echo "Локальный пакет: $local_dir/price-watch-bin-${version}-1-x86_64.pkg.tar.zst"
