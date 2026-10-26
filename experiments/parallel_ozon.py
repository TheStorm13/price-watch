"""Read-only comparison of sequential and concurrent Ozon JSON requests.

Run from the repository root:
    .venv/bin/python -m experiments.parallel_ozon 4465694803 4545459627

This experiment does not write to PostgreSQL or change the production collector.
It stops on an anti-bot page instead of waiting for a user confirmation.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from marketplace_connector.connectors.ozon.async_client import AsyncOzonClient
from marketplace_connector.connectors.ozon.connector import OzonConnector


async def fetch_one(connector, article: str) -> dict:
    started = time.perf_counter()
    try:
        snapshot = await connector.get_product(article)
        return {
            "article": article,
            "ok": True,
            "seconds": round(time.perf_counter() - started, 3),
            "availability": snapshot.availability.value,
        }
    except Exception as exc:
        return {
            "article": article,
            "ok": False,
            "seconds": round(time.perf_counter() - started, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }


async def run_batch(connector, articles: list[str], parallel: bool, concurrency: int) -> dict:
    started = time.perf_counter()
    if parallel:
        limit = asyncio.Semaphore(concurrency)

        async def bounded_fetch(article: str) -> dict:
            async with limit:
                return await fetch_one(connector, article)

        results = await asyncio.gather(*(bounded_fetch(article) for article in articles))
    else:
        results = [await fetch_one(connector, article) for article in articles]
    return {
        "mode": "parallel" if parallel else "sequential",
        "seconds": round(time.perf_counter() - started, 3),
        "results": results,
    }


async def run(args) -> list[dict]:
    client = AsyncOzonClient(args.profile_dir, headless=args.headless, concurrency=args.concurrency)
    connector = OzonConnector(client)
    batches = []
    modes = (True, False) if args.parallel_first else (False, True)
    async with client.collection_session():
        for parallel in modes:
            batch = await run_batch(connector, args.articles, parallel, args.concurrency)
            batches.append(batch)
            print(json.dumps(batch, ensure_ascii=False), flush=True)
            if any(not result["ok"] for result in batch["results"]):
                break
    return batches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("articles", nargs="+", help="Ozon article IDs to compare")
    parser.add_argument("--profile-dir", type=Path, default=Path(".playwright-profile"))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--parallel-first", action="store_true")
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()
    if len(args.articles) < 2:
        parser.error("Передайте минимум два артикула")
    if args.concurrency < 1:
        parser.error("--concurrency должен быть положительным")
    args.articles = [AsyncOzonClient.normalize_product_id(article) for article in args.articles]
    batches = asyncio.run(run(args))
    return 0 if len(batches) == 2 and all(result["ok"] for batch in batches for result in batch["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
