"""Transport bookkeeping must also work with synchronously completed tasks."""
import asyncio
import unittest
from marketplace_connector.connectors.wildberries.transport import WildberriesTransport


class WildberriesTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_drain_removes_completed_snapshot_without_waiting_for_callbacks(self):
        transport=WildberriesTransport(None,None)
        completed=asyncio.get_running_loop().create_future()
        completed.set_result(None)
        transport._responses.add(completed)
        await transport._drain()
        self.assertEqual(transport._responses,set())
