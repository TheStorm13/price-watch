"""Read-only comparison of sequential and concurrent Ozon tabs.

Run from the repository root:
    .venv/bin/python -m experiments.parallel_ozon 4465694803 4545459627

This experiment does not write to PostgreSQL or change the production collector.
It stops on an anti-bot page instead of waiting for a user confirmation.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import time
from contextlib import suppress
from pathlib import Path

from playwright.async_api import async_playwright

from marketplace_connector.connectors.ozon.client import OzonClient
from marketplace_connector.connectors.ozon.mapper import OzonMapper


async def fetch_one(context, article: str) -> dict:
    started = time.perf_counter()
    page = await context.new_page()
    try:
        await page.goto(
            OzonClient.PRODUCT_URL.format(article=article),
            wait_until="domcontentloaded",
            timeout=60_000,
        )
        page_text = "\n".join((await page.title(), await page.locator("body").inner_text(timeout=5_000)))
        if OzonClient._is_antibot_text(page_text):
            raise RuntimeError("Ozon запросил проверку на странице товара")

        response = await asyncio.wait_for(
            page.evaluate(
                """async (url) => {
                    const response = await fetch(url, {
                        credentials: 'include',
                        headers: {'accept': 'application/json, text/plain, */*'}
                    });
                    return {status: response.status, text: await response.text()};
                }""",
                OzonClient.API_URL.format(article=article),
            ),
            timeout=30,
        )
        raw_text = response.get("text", "")
        if OzonClient._is_antibot_text(raw_text):
            raise RuntimeError("Ozon запросил проверку в JSON-ответе")
        OzonClient._validate_json_text(raw_text)
        snapshot = OzonMapper.to_snapshot(json.loads(raw_text), expected_external_id=article)
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
    finally:
        with suppress(Exception):
            await page.close()


async def run_batch(context, articles: list[str], parallel: bool, concurrency: int) -> dict:
    started = time.perf_counter()
    if parallel:
        limit = asyncio.Semaphore(concurrency)

        async def bounded_fetch(article: str) -> dict:
            async with limit:
                return await fetch_one(context, article)

        results = await asyncio.gather(*(bounded_fetch(article) for article in articles))
    else:
        results = [await fetch_one(context, article) for article in articles]
    return {
        "mode": "parallel" if parallel else "sequential",
        "seconds": round(time.perf_counter() - started, 3),
        "results": results,
    }


async def run(args) -> list[dict]:
    client = OzonClient(args.profile_dir, headless=args.headless)
    client.profile_dir.mkdir(parents=True, exist_ok=True)
    client._cleanup_stale_profile_locks()
    process = None
    browser = None
    async with async_playwright() as playwright:
        executable = client._find_chrome_executable(playwright)
        port = client._reserve_debug_port()
        chrome_args = [
            str(executable),
            f"--remote-debugging-port={port}",
            "--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={client.profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",
            "--ozone-platform=x11",
        ]
        if args.headless:
            chrome_args.append("--headless=new")
        chrome_args.append("about:blank")
        try:
            with (client.profile_dir / "chrome.log").open("ab") as chrome_log:
                process = subprocess.Popen(
                    chrome_args,
                    stdout=chrome_log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            client._wait_for_debug_port(process, port)
            browser = await playwright.chromium.connect_over_cdp(
                f"http://127.0.0.1:{port}",
                timeout=10_000,
                is_local=True,
                no_defaults=True,
            )
            if not browser.contexts:
                raise RuntimeError("Chrome не создал основной профиль")
            context = browser.contexts[0]
            batches = []
            modes = (True, False) if args.parallel_first else (False, True)
            for parallel in modes:
                batch = await run_batch(context, args.articles, parallel, args.concurrency)
                batches.append(batch)
                print(json.dumps(batch, ensure_ascii=False), flush=True)
                if any(not result["ok"] for result in batch["results"]):
                    break
            return batches
        finally:
            if browser is not None:
                with suppress(Exception):
                    await browser.close()
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("articles", nargs="+", help="Ozon article IDs to compare")
    parser.add_argument("--profile-dir", type=Path, default=Path(".playwright-profile"))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--parallel-first", action="store_true")
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args()
    if len(args.articles) < 2:
        parser.error("Передайте минимум два артикула")
    if args.concurrency < 1:
        parser.error("--concurrency должен быть положительным")
    args.articles = [OzonClient.normalize_product_id(article) for article in args.articles]
    batches = asyncio.run(run(args))
    return 0 if len(batches) == 2 and all(result["ok"] for batch in batches for result in batch["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
