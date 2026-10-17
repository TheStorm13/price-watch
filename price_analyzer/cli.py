"""Command-line interface for cards, collection runs and price history."""

import argparse
import asyncio
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Iterable, Optional, Sequence

from marketplace_connector import ConnectorRegistry
from marketplace_connector.connectors.ozon import AsyncOzonClient, OzonConnector

from .application.collection_service import CollectionService
from .infrastructure.postgres import (
    AsyncDatabase,
    Database,
    MigrationRunner,
    PostgresPriceAnalyzerRepository,
)
from .worker import CollectionWorker, DatabaseChallengeHandler


logger = logging.getLogger(__name__)
PROJECT_DIR = Path(__file__).resolve().parent.parent


class TerminalChallengeHandler:
    async def handle_async(self, marketplace: str, message: str) -> None:
        print(message, file=sys.stderr, end="", flush=True)
        await asyncio.to_thread(input)


def _json_default(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    raise TypeError(f"Не поддерживается JSON-сериализация {type(value)!r}")


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=_json_default))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Анализатор цен маркетплейсов")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL DSN; по умолчанию используется DATABASE_URL",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    database = commands.add_parser("db", help="операции с базой данных")
    database_commands = database.add_subparsers(dest="db_command", required=True)
    database_commands.add_parser("migrate", help="применить SQL-миграции")

    card = commands.add_parser("card", help="управление карточками")
    card_commands = card.add_subparsers(dest="card_command", required=True)
    add_card = card_commands.add_parser("add", help="добавить карточку")
    add_card.add_argument("--marketplace", required=True)
    add_card.add_argument("--external-id", required=True)
    add_card.add_argument("--title")
    add_card.add_argument("--url")
    list_cards = card_commands.add_parser("list", help="показать карточки")
    list_cards.add_argument("--all", action="store_true", help="устаревший параметр: все карточки выводятся по умолчанию")

    collect = commands.add_parser("collect", help="собрать текущие цены")
    collect.add_argument("--card-id", type=int)
    collect.add_argument(
        "--profile-dir",
        type=Path,
        default=PROJECT_DIR / ".playwright-profile",
    )
    collect.add_argument("--chrome-binary", type=Path)
    collect.add_argument("--headless", action="store_true", help="собирать без окна Chrome")
    collect.add_argument(
        "--chrome-platform",
        choices=("x11", "wayland", "auto"),
        default="x11",
        help="графическая платформа Chrome (по умолчанию: x11)",
    )
    collect.add_argument(
        "--browser-channel",
        choices=("chrome", "chromium"),
        default="chrome",
        help="канал Playwright (chrome или chromium)",
    )

    api = commands.add_parser("api", help="запустить HTTP API")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=8000)

    worker = commands.add_parser("worker", help="запустить worker очереди")
    worker.add_argument("--once", action="store_true", help="обработать не более одного запуска")
    worker.add_argument(
        "--profile-dir",
        type=Path,
        default=PROJECT_DIR / ".playwright-profile",
    )
    worker.add_argument("--chrome-binary", type=Path)
    worker.add_argument("--headless", action="store_true", help="собирать без окна Chrome")
    worker.add_argument("--virtual-display", action="store_true", help="собирать в скрытом Xvfb")
    worker.add_argument(
        "--chrome-platform",
        choices=("x11", "wayland", "auto"),
        default="x11",
    )
    worker.add_argument(
        "--browser-channel",
        choices=("chrome", "chromium"),
        default="chrome",
        help="канал Playwright (chrome или chromium)",
    )

    history = commands.add_parser("history", help="история и статистика цены")
    history.add_argument("--card-id", type=int, required=True)
    history.add_argument("--days", type=int, default=30)

    run = commands.add_parser("run", help="информация о запусках")
    run_commands = run.add_subparsers(dest="run_command", required=True)
    run_commands.add_parser("last", help="последний запуск")
    return parser


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
        force=True,
    )
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def _build_connectors(
    args: argparse.Namespace, marketplaces: Iterable[str]
) -> ConnectorRegistry:
    connectors = []
    if "ozon" in set(marketplaces):
        client = AsyncOzonClient(
            profile_dir=args.profile_dir,
            challenge_handler=TerminalChallengeHandler(),
            chrome_binary=args.chrome_binary,
            chrome_platform=args.chrome_platform,
            browser_channel=args.browser_channel,
            headless=args.headless,
        )
        connectors.append(OzonConnector(client))
    return ConnectorRegistry(connectors)


async def _execute(args: argparse.Namespace, database: AsyncDatabase) -> int:
    repository = PostgresPriceAnalyzerRepository(database)

    if args.command == "card" and args.card_command == "add":
        card = await repository.add_card(
            args.marketplace, args.external_id, args.title, args.url
        )
        _print_json(asdict(card))
        return 0

    if args.command == "card" and args.card_command == "list":
        cards = [
            {
                **asdict(item.card),
                "current_price": item.current_price,
                "current_availability": item.current_availability,
                "last_observed_at": item.last_observed_at,
            }
            for item in await repository.list_cards()
        ]
        _print_json(cards)
        return 0

    if args.command == "collect":
        cards = await repository.list_collection_cards(args.card_id)
        connectors = _build_connectors(
            args, (card.marketplace for card in cards)
        )
        summary = await CollectionService(repository, connectors).collect(args.card_id)
        _print_json(asdict(summary))
        return 0 if summary.failure_count == 0 else 2

    if args.command == "worker":
        repository = PostgresPriceAnalyzerRepository(database)

        async def connector_factory(run):
            cards = await repository.cards_for_run(run)
            marketplaces = {card.marketplace for card in cards}
            connectors = []
            if "ozon" in marketplaces:
                connectors.append(
                    OzonConnector(
                        AsyncOzonClient(
                            profile_dir=args.profile_dir,
                            challenge_handler=DatabaseChallengeHandler(
                                repository, run.id
                            ),
                            chrome_binary=args.chrome_binary,
                            chrome_platform=args.chrome_platform,
                            browser_channel=args.browser_channel,
                            headless=args.headless,
                            virtual_display=args.virtual_display,
                        )
                    )
                )
            return ConnectorRegistry(connectors)

        worker = CollectionWorker(repository, connector_factory)
        if args.once:
            await worker.run_once()
        else:
            await worker.run_forever()
        return 0

    if args.command == "history":
        history = [asdict(item) for item in await repository.get_history(args.card_id, args.days)]
        statistics = asdict(await repository.get_statistics(args.card_id, args.days))
        _print_json({"statistics": statistics, "history": history})
        return 0

    if args.command == "run" and args.run_command == "last":
        _print_json(await repository.get_last_run())
        return 0

    raise RuntimeError("Неизвестная команда")


async def _execute_with_database(args: argparse.Namespace) -> int:
    database = await AsyncDatabase(args.database_url).open()
    try:
        return await _execute(args, database)
    finally:
        await database.close()


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.log_level)
    if not args.database_url:
        logger.error("Задайте DATABASE_URL или передайте --database-url")
        return 2
    if args.command == "api":
        import uvicorn

        from .api import create_app

        uvicorn.run(create_app(args.database_url), host=args.host, port=args.port)
        return 0
    try:
        if args.command == "db" and args.db_command == "migrate":
            with Database(args.database_url) as database:
                applied = MigrationRunner(database).apply()
            _print_json({"applied": applied})
            return 0
        return asyncio.run(_execute_with_database(args))
    except KeyboardInterrupt:
        logger.warning("Остановлено пользователем")
        return 130
    except Exception:
        logger.exception("Команда завершилась ошибкой")
        return 1
