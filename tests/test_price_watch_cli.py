import unittest
import json
import os
import subprocess
import sys

from price_watch.cli import build_parser


class PriceWatchCliTests(unittest.TestCase):
    def test_numeric_json_mode_without_database_and_both_cli_imports(self):
        script = '''
import runpy, sys
from unittest.mock import AsyncMock, patch
from marketplace_connector import Availability, ProductRef, MarketplaceCard
from marketplace_connector.connectors.ozon.cli import main as numeric_main, TerminalChallengeHandler
from price_watch.cli import main as price_watch_main
snapshot = MarketplaceCard(ref=ProductRef('ozon','123'), title='Isolated CLI',
    url='', price=100, availability=Availability.IN_STOCK)
with patch('marketplace_connector.connectors.ozon.cli.AsyncOzonClient'), patch(
    'marketplace_connector.connectors.ozon.cli.ProductService.get_product', new=AsyncMock(return_value=snapshot)):
    sys.argv = ['main.py', '123']
    runpy.run_path('main.py', run_name='__main__')
'''
        environment = {key: value for key, value in os.environ.items() if key != 'DATABASE_URL'}
        result = subprocess.run([sys.executable, '-c', script], env=environment,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['title'], 'Isolated CLI')

    def test_terminal_verification_waits_for_input(self):
        import asyncio
        from unittest.mock import patch
        from marketplace_connector.connectors.ozon.cli import TerminalChallengeHandler
        with patch('builtins.input', return_value='') as answer, patch('sys.stderr'):
            asyncio.run(TerminalChallengeHandler().handle_async('ozon', 'Complete verification'))
        answer.assert_called_once_with()

    def test_parses_add_card_command(self):
        args = build_parser().parse_args(
            ["card", "add", "--marketplace", "ozon", "--external-id", "123"]
        )

        self.assertEqual(args.command, "card")
        self.assertEqual(args.card_command, "add")
        self.assertEqual(args.marketplace, "ozon")
        self.assertEqual(args.external_id, "123")

    def test_parses_history_period(self):
        args = build_parser().parse_args(
            ["history", "--card-id", "7", "--days", "45"]
        )

        self.assertEqual(args.card_id, 7)
        self.assertEqual(args.days, 45)

    def test_parses_api_and_worker_commands(self):
        api = build_parser().parse_args(["api", "--port", "9000"])
        worker = build_parser().parse_args(
            ["worker", "--once", "--browser-channel", "chromium"]
        )

        self.assertEqual(api.port, 9000)
        self.assertTrue(worker.once)
        self.assertEqual(worker.browser_channel, "chromium")



@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'TEST_DATABASE_URL не задан')
class CliCollectionIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_cli_and_queued_worker_save_the_same_decimal_contract(self):
        from uuid import uuid4
        from decimal import Decimal
        from contextlib import asynccontextmanager
        from httpx import ASGITransport, AsyncClient
        from marketplace_connector import Availability, ConnectorRegistry, MarketplaceCard, ProductRef
        from price_watch.api import create_app
        from price_watch.infrastructure.postgres import AsyncDatabase, Database, MigrationRunner, PostgresPriceWatchRepository
        from price_watch.worker import CollectionWorker
        from sqlalchemy import delete
        from price_watch.infrastructure.postgres.models import CollectionRunRecord
        url = os.environ['TEST_DATABASE_URL']
        with Database(url) as db:
            MigrationRunner(db).apply()
        environment = {**os.environ, 'DATABASE_URL': url}
        external_id = str(uuid4().int)
        added = subprocess.run([sys.executable, 'main.py', 'card', 'add', '--marketplace', 'ozon',
                                '--external-id', external_id, '--title', 'Local title'],
                               env=environment, capture_output=True, text=True, timeout=20)
        self.assertEqual(added.returncode, 0, added.stderr)
        card_data = json.loads(added.stdout)
        self.assertEqual(card_data['external_id'], external_id)
        self.assertNotIn('ref', card_data)
        card_id = card_data['id']
        database = await AsyncDatabase(url).open()
        repo = PostgresPriceWatchRepository(database)
        runs = []
        try:
            script = '''
import asyncio,runpy,sys
from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import patch
from marketplace_connector import Availability,ConnectorRegistry,MarketplaceCard,ProductRef
class Connector:
    marketplace='ozon'
    @asynccontextmanager
    async def collection_session(self): yield
    async def get_product(self, external_id):
        return MarketplaceCard(ProductRef('ozon',external_id),'Marketplace title','',Availability.IN_STOCK,price=Decimal('12.345'))
with patch('price_watch.cli._build_connectors', return_value=ConnectorRegistry([Connector()])):
    sys.argv=['main.py','collect','--card-id',sys.argv[1]]
    runpy.run_path('main.py',run_name='__main__')
'''
            direct = subprocess.run([sys.executable, '-c', script, str(card_id)], env=environment,
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(direct.returncode, 0, direct.stderr)
            summary = json.loads(direct.stdout)
            runs.append(summary['run_id'])
            self.assertEqual((summary['success_count'], summary['failure_count']), (1, 0))
            self.assertEqual((await repo.get_card(card_id)).current_price, Decimal('12.35'))
            app = create_app(repository=repo)
            app.state.repository = repo
            async with AsyncClient(transport=ASGITransport(app=app), base_url='http://isolated') as client:
                response = await client.post('/api/runs', json={'cardId': card_id})
                self.assertEqual(response.status_code, 202)
                runs.append(response.json()['id'])
                class Connector:
                    marketplace = 'ozon'
                    @asynccontextmanager
                    async def collection_session(self): yield
                    async def get_product(self, external_id):
                        return MarketplaceCard(ProductRef('ozon', external_id), 'Changed marketplace title', '',
                                               Availability.IN_STOCK, price=Decimal('12.345'))
                async def factory(run): return ConnectorRegistry([Connector()])
                self.assertTrue(await CollectionWorker(repo, factory).run_once())
                card = (await client.get(f'/api/cards/{card_id}')).json()
                self.assertEqual(card['currentPrice'], '12.35')
                self.assertEqual(card['title'], 'Local title')
                self.assertEqual(await repo.count_history(card_id, 30), 1)
        finally:
            async with database.session() as session, session.begin():
                await session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id.in_(runs)))
            await repo.delete_card(card_id)
            await database.close()


if __name__ == "__main__":
    unittest.main()
