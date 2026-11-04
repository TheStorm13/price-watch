"""Explicit fixtures for tests independent of creation's asynchronous refresh."""
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from price_watch.application.run_executor import RunExecutor
from price_watch.infrastructure.postgres.repository_common import _RUN_CREATION_LOCK
from price_watch.infrastructure.postgres.runs_repository import _DIAGNOSTIC_CREATION_LOCK


def manual_queue(testcase):
    """Seed persistence without introducing unrelated pending creation jobs.

    Actual automatic creation/queue behavior is exercised by test_variant_tracking.
    """
    guard = patch('price_watch.infrastructure.postgres.runs_repository.RunRepository.enqueue_initial', new=AsyncMock())
    guard.start()
    testcase.addCleanup(guard.stop)


class InitialDiscoveryExecutor(RunExecutor):
    """Run family-discovery regression fixtures explicitly as initial refreshes."""
    async def collect(self, card_id=None):
        async with self.repository._database.session() as s, s.begin():
            await s.execute(_RUN_CREATION_LOCK)
            await s.execute(_DIAGNOSTIC_CREATION_LOCK)
            cards = await self.repository._select_targets(s, card_id, discover_all=True)
            run = await self.repository._create_run(s, cards, card_id=card_id,
                discover_all=True, owner=uuid4().hex)
        return await self.execute(run)
