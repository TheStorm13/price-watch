import unittest

from price_analyzer.cli import build_parser


class AnalyzerCliTests(unittest.TestCase):
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
