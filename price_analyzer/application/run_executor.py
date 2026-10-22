"""One owned lifecycle for direct CLI and queued worker execution."""
import asyncio
import logging
import traceback
from datetime import datetime, timezone
from ..domain.models import LeaseLost, CollectionSummary
from .collection_service import CollectionService

logger = logging.getLogger(__name__)


class RunExecutor:
    def __init__(self, repository, connector_factory, heartbeat_interval=5):
        self.repository = repository
        self.connector_factory = connector_factory
        self.heartbeat_interval = heartbeat_interval

    async def collect(self, card_id=None):
        run = await self.repository.start_direct_run(card_id)
        return await self.execute(run)

    async def _heartbeat(self, lease):
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            try:
                if not await self.repository.touch_run(lease):
                    raise LeaseLost(f'Владение запуском {lease.run_id} потеряно')
            except LeaseLost:
                raise
            except Exception:
                logger.exception('Не удалось обновить heartbeat %s', lease.run_id)

    async def _work(self, run):
        if not run.targets_complete:
            raise ValueError('Состав целей запуска известен не полностью; повторите известные цели или создайте новый сбор')
        cards = await self.repository.cards_for_run(run.id)
        if len(cards) != run.total_count:
            raise ValueError('Одна или несколько целей запуска недоступны')
        connectors = await self.connector_factory(run)
        await CollectionService(self.repository, connectors).execute(run.lease, cards)
        finished = await self.repository.finish_run(run.lease)
        return CollectionSummary(finished.id, finished.status, finished.total_count,
                                 finished.success_count, finished.failure_count)

    async def execute(self, run):
        lease = run.lease
        work = asyncio.create_task(self._work(run))
        heartbeat = asyncio.create_task(self._heartbeat(lease))
        try:
            done, _ = await asyncio.wait((work, heartbeat), return_when=asyncio.FIRST_COMPLETED)
            if heartbeat in done:
                await heartbeat
            return await work
        except LeaseLost:
            raise
        except BaseException as exc:
            # Stop I/O before marking failed; successful concurrent results already committed stay durable.
            work.cancel()
            await asyncio.gather(work, return_exceptions=True)
            try:
                await self.repository.fail_run(lease, {'cardId': None, 'marketplace': None, 'externalId': None,
                    'at': datetime.now(timezone.utc).isoformat(), 'type': type(exc).__name__,
                    'message': str(exc), 'traceback': traceback.format_exc()})
            except LeaseLost:
                pass
            raise
        finally:
            work.cancel()
            heartbeat.cancel()
            await asyncio.gather(work, heartbeat, return_exceptions=True)
