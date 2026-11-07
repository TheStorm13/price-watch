"""The outer retry is bounded, cancellable and independent of marketplace I/O."""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from marketplace_connector.application.retry import fetch_with_retry
from marketplace_connector.application.product_service import ConnectorRegistry, ProductService
from marketplace_connector.domain.errors import ProductNotFound, RateLimited, MarketplaceSchemaChanged


class ProductRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_outer_policy_applies_to_all_marketplaces(self):
        for marketplace in ('ozon', 'aliexpress', 'wildberries'):
            with self.subTest(marketplace=marketplace):
                connector = type('Connector', (), {'marketplace': marketplace})()
                connector.get_product = AsyncMock(side_effect=[RuntimeError('first'), 'snapshot'])
                connector.collection_session = lambda: None
                service = ProductService(ConnectorRegistry([connector]))
                with patch('marketplace_connector.application.retry.sleep', new_callable=AsyncMock) as sleep:
                    self.assertEqual(await service.get_product(marketplace, '123'), 'snapshot')
                self.assertEqual(connector.get_product.await_count, 2)
                sleep.assert_awaited_once_with(1)

    async def test_success_does_not_sleep_or_repeat(self):
        fetch = AsyncMock(return_value='snapshot')
        with patch('marketplace_connector.application.retry.sleep', new_callable=AsyncMock) as sleep:
            self.assertEqual(await fetch_with_retry(fetch), 'snapshot')
        self.assertEqual(fetch.await_count, 1)
        sleep.assert_not_awaited()

    async def test_schema_failure_can_succeed_on_second_call(self):
        fetch = AsyncMock(side_effect=[MarketplaceSchemaChanged('temporary response'), 'snapshot'])
        with patch('marketplace_connector.application.retry.sleep', new_callable=AsyncMock) as sleep:
            self.assertEqual(await fetch_with_retry(fetch), 'snapshot')
        sleep.assert_awaited_once_with(1.0)
        self.assertEqual(fetch.await_count, 2)

    async def test_retry_after_changes_only_the_delay(self):
        for after, expected in [(None, 1), (0, 1), (.2, 1), (4, 4), (float('nan'), 1)]:
            with self.subTest(after=after):
                fetch = AsyncMock(side_effect=[RateLimited('429', retry_after=after), 'snapshot'])
                with patch('marketplace_connector.application.retry.sleep', new_callable=AsyncMock) as sleep:
                    self.assertEqual(await fetch_with_retry(fetch), 'snapshot')
                sleep.assert_awaited_once_with(expected)

    async def test_only_two_calls_and_final_error_keeps_first_cause(self):
        first, final = RuntimeError('first'), RuntimeError('final')
        fetch = AsyncMock(side_effect=[first, final, 'must not happen'])
        with patch('marketplace_connector.application.retry.sleep', new_callable=AsyncMock):
            with self.assertRaisesRegex(RuntimeError, 'final') as caught:
                await fetch_with_retry(fetch)
        self.assertIs(caught.exception.__cause__, first)
        self.assertEqual(fetch.await_count, 2)

    async def test_confirmed_absence_is_not_retried(self):
        fetch = AsyncMock(side_effect=ProductNotFound('absent'))
        with patch('marketplace_connector.application.retry.sleep', new_callable=AsyncMock) as sleep:
            with self.assertRaises(ProductNotFound):
                await fetch_with_retry(fetch)
        self.assertEqual(fetch.await_count, 1)
        sleep.assert_not_awaited()

    async def test_cancelled_request_is_not_retried(self):
        fetch = AsyncMock(side_effect=asyncio.CancelledError())
        with patch('marketplace_connector.application.retry.sleep', new_callable=AsyncMock) as sleep:
            with self.assertRaises(asyncio.CancelledError):
                await fetch_with_retry(fetch)
        self.assertEqual(fetch.await_count, 1)
        sleep.assert_not_awaited()

    async def test_cancelling_delay_does_not_send_second_request(self):
        sleeping = asyncio.Event()
        async def sleep(delay):
            sleeping.set()
            await asyncio.Event().wait()
        fetch = AsyncMock(side_effect=RuntimeError('first'))
        with patch('marketplace_connector.application.retry.sleep', side_effect=sleep):
            task = asyncio.create_task(fetch_with_retry(fetch))
            await asyncio.wait_for(sleeping.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(fetch.await_count, 1)

    async def test_real_default_delay_is_one_second(self):
        fetch = AsyncMock(side_effect=[RuntimeError('temporary'), 'ok'])
        before = asyncio.get_running_loop().time()
        self.assertEqual(await fetch_with_retry(fetch), 'ok')
        self.assertGreaterEqual(asyncio.get_running_loop().time() - before, 1)
