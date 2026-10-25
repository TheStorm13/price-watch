#!/usr/bin/env python3
"""Entry point for price-watch and the single-product Ozon command."""

import sys

try:
    from marketplace_connector.connectors.ozon.cli import main as ozon_main
    from price_watch.cli import main as price_watch_main
except ModuleNotFoundError as exc:
    if exc.name in {"playwright", "sqlalchemy", "fastapi"}:
        raise SystemExit(
            f"Не установлен пакет {exc.name}. Выполните: "
            "pip install -r requirements.txt"
        ) from exc
    raise


if __name__ == "__main__":
    # Preserve the `python main.py <ozon_id>` invocation.
    if len(sys.argv) > 1 and sys.argv[1].strip().isdigit():
        raise SystemExit(ozon_main())
    raise SystemExit(price_watch_main())
