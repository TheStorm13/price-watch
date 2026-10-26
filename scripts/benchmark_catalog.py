"""Reproducible catalog benchmark; requires a dedicated disposable test database."""
import argparse
import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
import json
import math
import os
from pathlib import Path
import platform
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from marketplace_connector import ConnectorRegistry, ProductRef, MarketplaceCard, Availability
from price_watch.api import create_app
from price_watch.application.run_executor import RunExecutor
from price_watch.bootstrap import create_postgres_stores
from price_watch.infrastructure.postgres import AsyncDatabase, Database, MigrationRunner

queries = ContextVar('benchmark_queries', default=None)
SIZES = {'S': 100, 'M': 1000, 'L': 5000}


def rss():
    return int(next(line.split()[1] for line in Path('/proc/self/status').read_text().splitlines()
                    if line.startswith('VmRSS:'))) * 1024


async def seed(db, count):
    async with db.session() as session, session.begin():
        # Refuse to reset anything outside the explicitly supplied disposable DB.
        name = await session.scalar(text('select current_database()'))
        if name != 'price_watch_rel_test':
            raise RuntimeError('Benchmark requires database named price_watch_rel_test')
        await session.execute(text('TRUNCATE marketplace_cards, product_groups, collection_runs RESTART IDENTITY CASCADE'))
        await session.execute(text("INSERT INTO product_groups(id,name) OVERRIDING SYSTEM VALUE SELECT i, 'Group '||i FROM generate_series(1,:n) i"), {'n': max(1, count//10)})
        await session.execute(text("""INSERT INTO marketplace_cards(id,marketplace,external_id,title,group_id) OVERRIDING SYSTEM VALUE
            SELECT i,'ozon',i::text,'Product '||i,CASE WHEN i%2=0 THEN (i-1)/10+1 END
            FROM generate_series(1,:n) i"""), {'n': count})
        await session.execute(text("""INSERT INTO price_history(card_id,price,availability,observed_at,snapshot)
            SELECT i,100+(j%10), 'in_stock', '2026-10-01'::timestamptz+j*interval '1 hour','{}'::jsonb
            FROM generate_series(1,:n) i CROSS JOIN generate_series(1,100) j"""), {'n': count})
    async with db.session() as session:
        await session.execute(text('ANALYZE marketplace_cards'))
        await session.execute(text('ANALYZE price_history'))
        await session.commit()


class SyntheticConnector:
    marketplace = 'ozon'
    @asynccontextmanager
    async def collection_session(self):
        yield

    async def get_product(self, external_id):
        await asyncio.sleep(.01)
        return MarketplaceCard(ref=ProductRef('ozon', external_id), title='Product '+external_id,
                               url='', price=95, availability=Availability.IN_STOCK)


async def measure(db, mode, writing, rounds):
    repository = create_postgres_stores(db)
    app = create_app(services=repository.api, api_token='benchmark')

    stop = asyncio.Event()
    writes = 0
    write_seconds = 0

    async def writer():
        nonlocal writes, write_seconds
        while not stop.is_set():
            started = time.perf_counter()
            async def factory(run):
                return ConnectorRegistry([SyntheticConnector()])
            summary = await RunExecutor(repository.runs, factory).collect()
            writes += summary.success_count
            write_seconds += time.perf_counter() - started

    task = asyncio.create_task(writer()) if writing else None
    samples, sql_counts, sql_seconds = [], [], []
    peak = rss()
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://benchmark',
                           headers={'X-Price-Watch-Token': 'benchmark'}) as client:
        for i in range(rounds + 5):
            sql = []
            token = queries.set(sql)
            start = time.perf_counter()
            responses = [await client.get('/api/catalog')]
            duration = (time.perf_counter()-start)*1000
            queries.reset(token)
            for response in responses:
                response.raise_for_status()
            peak = max(peak, rss())
            if i >= 5:
                samples.append(duration)
                sql_counts.append(len(sql))
                sql_seconds.append(sum(sql)*1000)
        payload = sum(len(r.content) for r in responses)
    stop.set()
    if task:
        await task
    values = sorted(samples)
    return {'p50_ms': values[len(values)//2], 'p95_ms': values[math.ceil(len(values)*.95)-1],
            'sql_count': max(sql_counts), 'sql_ms_mean': sum(sql_seconds)/len(sql_seconds),
            'payload_bytes': payload, 'peak_rss_bytes': peak,
            'write_cards_per_second': writes/write_seconds if write_seconds else None,
            'rounds': rounds}


async def main(args):
    url = os.environ['TEST_DATABASE_URL']
    with Database(url) as db:
        MigrationRunner(db).apply()
    db = await AsyncDatabase(url).open()
    def before(conn, cursor, statement, parameters, context, executemany):
        context.benchmark_started = time.perf_counter()
    def after(conn, cursor, statement, parameters, context, executemany):
        sql = queries.get()
        if sql is not None:
            sql.append(time.perf_counter()-context.benchmark_started)
    event.listen(db.engine.sync_engine, 'before_cursor_execute', before)
    event.listen(db.engine.sync_engine, 'after_cursor_execute', after)
    result = {'mode': args.mode, 'environment': {'python': platform.python_version(),
               'platform': platform.platform(), 'transport': 'HTTP ASGI (serialization included)'}, 'results': {}}
    try:
        for label, count in SIZES.items():
            for writing in [False, True]:
                await seed(db, count)
                key = label + ('_writer' if writing else '_idle')
                result['results'][key] = await measure(db, args.mode, writing, args.rounds)
                result['results'][key].update(cards=count, history=count*100)
                Path(args.output).write_text(json.dumps(result, indent=2))
                print(key, json.dumps(result['results'][key]), flush=True)
    finally:
        await db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['after'], required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--rounds', type=int, default=30)
    asyncio.run(main(parser.parse_args()))
