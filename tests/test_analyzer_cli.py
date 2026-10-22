import unittest
import json
import os
import subprocess
import sys

from price_analyzer.cli import build_parser


class AnalyzerCliTests(unittest.TestCase):
    def test_numeric_json_mode_without_database_and_both_cli_imports(self):
        script = '''
import runpy, sys
from unittest.mock import AsyncMock, patch
from marketplace_connector import Availability, ProductRef, ProductSnapshot
from ozon_article_json.cli import main as numeric_main, TerminalChallengeHandler
from price_analyzer.cli import main as analyzer_main
snapshot = ProductSnapshot(ref=ProductRef('ozon','123'), title='Isolated CLI',
    url='', price=100, availability=Availability.IN_STOCK)
with patch('ozon_article_json.cli.AsyncOzonClient'), patch(
    'ozon_article_json.cli.ProductService.get_product', new=AsyncMock(return_value=snapshot)):
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
        from ozon_article_json.cli import TerminalChallengeHandler
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


if __name__ == "__main__":
    unittest.main()
