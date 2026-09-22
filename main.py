#!/usr/bin/env python3
"""Entry point for the price analyzer and the legacy one-card Ozon command."""

import sys

try:
    from ozon_article_json.cli import main as legacy_ozon_main
    from price_analyzer.cli import main as analyzer_main
except ModuleNotFoundError as exc:
    if exc.name in {"playwright", "sqlalchemy", "fastapi"}:
        raise SystemExit(
            f"Не установлен пакет {exc.name}. Выполните: "
            "pip install -r article_json_parser/requirements.txt"
        ) from exc
    raise


if __name__ == "__main__":
    # Preserve the original `python main.py <ozon_id>` invocation.
    if len(sys.argv) > 1 and sys.argv[1].strip().isdigit():
        raise SystemExit(legacy_ozon_main())
    raise SystemExit(analyzer_main())
