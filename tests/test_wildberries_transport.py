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

    async def test_temporary_bootstrap_failure_cleans_page_and_can_restart(self):
        from unittest.mock import AsyncMock, MagicMock
        from playwright.async_api import Error
        from marketplace_connector.domain.errors import MarketplaceUnavailable
        first, second = MagicMock(), MagicMock()
        for page in (first, second):
            page.close = AsyncMock()
            page.expose_function = AsyncMock()
            page.add_init_script = AsyncMock()
            page.route = AsyncMock()
        context = MagicMock(new_page=AsyncMock(side_effect=[first, second]))
        entered, release = asyncio.Event(), asyncio.Event()
        async def prepare(page):
            if page is first:
                entered.set()
                await release.wait()
                raise Error('temporary navigation')
        transport = WildberriesTransport(context, prepare)
        transport._fetch_article = AsyncMock(return_value={'ok': True})
        try:
            tasks = [asyncio.create_task(transport.fetch(str(i))) for i in (1001, 1002)]
            await entered.wait()
            release.set()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            self.assertTrue(all(isinstance(r, MarketplaceUnavailable) for r in results), results)
            first.close.assert_awaited_once()
            self.assertEqual(context.new_page.await_count, 1)
            self.assertEqual(await transport.fetch('1003'), {'ok': True})
            self.assertEqual(context.new_page.await_count, 2)
        finally:
            await transport.close()

    async def test_profile_generation_lives_through_waiters_and_response_inspections(self):
        transport = WildberriesTransport(None, None)
        old = transport._new_wallet()
        transport._join_wallet('request', old)
        transport._finish_wallet(old)
        current = transport._new_wallet()
        inspection = asyncio.get_running_loop().create_future()
        transport._profiles[old].responses.add(inspection)
        transport._release_wallet('request')
        self.assertIn(old, transport._profiles)
        inspection.set_result(None)
        transport._profiles[old].responses.clear()
        transport._inspection_done(inspection)
        self.assertEqual(set(transport._profiles), {current})
        transport._finish_wallet(current)
        for _ in range(100):
            generation = transport._new_wallet()
            transport._finish_wallet(generation)
        self.assertEqual(len(transport._profiles), 1)

    async def test_access_status_does_not_depend_on_exception_message(self):
        from unittest.mock import AsyncMock, MagicMock
        from marketplace_connector.connectors.wildberries.transport import ArticleState, WildberriesHttpError
        for status in (401, 403, 498, 500):
            transport = WildberriesTransport(None, None)
            error = WildberriesHttpError(status)
            error.args = ('different diagnostic wording',)
            state = ArticleState(errors={'detail': error})
            transport._articles['1001'] = state
            route = MagicMock()
            route.request.url = 'https://www.wildberries.ru/cards/v4/detail?nm=1001'
            route.abort, route.fallback = AsyncMock(), AsyncMock()
            await transport._route(route)
            self.assertEqual(route.abort.await_count, int(status != 500))

    async def test_unresponsive_renderer_is_bounded_without_queue_deadline(self):
        from unittest.mock import AsyncMock, MagicMock
        from marketplace_connector.domain.errors import UnsafeBrowserTeardown
        async def never(): await asyncio.Event().wait()
        transport = WildberriesTransport(None, None)
        transport.page = MagicMock()
        async def evaluate(*_): await never()
        transport.page.evaluate = evaluate
        evaluation = asyncio.create_task(never())
        with self.assertRaises(UnsafeBrowserTeardown):
            await asyncio.wait_for(transport._wait_evaluation(evaluation), 4)
        self.assertTrue(evaluation.cancelled())

    async def test_failed_renderer_probe_cannot_leave_evaluation_running(self):
        from unittest.mock import AsyncMock, MagicMock
        from playwright.async_api import Error
        from marketplace_connector.domain.errors import UnsafeBrowserTeardown
        transport = WildberriesTransport(None, None)
        transport.page = MagicMock(evaluate=AsyncMock(side_effect=Error('channel lost')))
        evaluation = asyncio.create_task(asyncio.Event().wait())
        with self.assertRaises(UnsafeBrowserTeardown):
            await asyncio.wait_for(transport._wait_evaluation(evaluation), 2)
        self.assertTrue(evaluation.cancelled())
