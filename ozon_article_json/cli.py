"""CLI for the Ozon implementation of the common product connector."""

import argparse
import asyncio
import logging
from pathlib import Path
import sys
from typing import Optional, Sequence

from marketplace_connector.application.product_service import ConnectorRegistry, ProductService
from marketplace_connector.connectors.ozon import AsyncOzonClient, OzonConnector
from marketplace_connector.serialization.product_json import snapshot_to_json


PROJECT_DIR = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)


class TerminalChallengeHandler:
    def handle(self, marketplace: str, message: str) -> None:
        print(message, file=sys.stderr, end="", flush=True)
        input()

    async def handle_async(self, marketplace: str, message: str) -> None:
        print(message, file=sys.stderr, end="", flush=True)
        await asyncio.to_thread(input)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Получить унифицированный снимок товара Ozon.")
    parser.add_argument("article", help="числовой идентификатор товара Ozon")
    parser.add_argument("--output", type=Path, help="также сохранить JSON в файл")
    parser.add_argument("--raw", action="store_true", help="вывести исходный ответ")
    parser.add_argument(
        "--profile-dir",
        type=Path,
        default=PROJECT_DIR / ".playwright-profile",
        help="каталог постоянного профиля Chrome",
    )
    parser.add_argument("--chrome-binary", type=Path, help="путь к Chrome/Chromium")
    parser.add_argument(
        "--chrome-platform",
        choices=("x11", "wayland", "auto"),
        default="x11",
        help="графическая платформа Chrome (по умолчанию: x11)",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    return parser


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format=(
            "%(asctime)s.%(msecs)03d %(levelname)-8s "
            "%(name)s:%(lineno)d [%(threadName)s] %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
        force=True,
    )
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.log_level)
    logger.info("Старт: marketplace=ozon, external_id=%s", args.article)

    try:
        client = AsyncOzonClient(
            args.profile_dir,
            challenge_handler=TerminalChallengeHandler(),
            chrome_binary=args.chrome_binary,
            chrome_platform=args.chrome_platform,
        )
        if args.raw:
            output_text = client.fetch_product(args.article).raw_text
        else:
            service = ProductService(ConnectorRegistry([OzonConnector(client)]))
            snapshot = service.get_product("ozon", args.article)
            output_text = snapshot_to_json(snapshot)
            logger.info(
                "Снимок нормализован: attributes=%s, variants=%s",
                len(snapshot.attributes),
                len(snapshot.variants),
            )

        if args.output:
            output_path = args.output.expanduser().resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output_text + "\n", encoding="utf-8")
            logger.info("JSON сохранён: %s", output_path)

        print(output_text)
        logger.info("Готово")
        return 0
    except KeyboardInterrupt:
        logger.warning("Остановлено пользователем")
        return 130
    except Exception:
        logger.exception("Не удалось получить снимок товара")
        return 1
