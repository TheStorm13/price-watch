"""Durable single-host queue; execution lifecycle is shared with direct CLI."""
import asyncio
import logging
import time
from typing import Awaitable, Callable
from marketplace_connector.application.product_service import ConnectorRegistry
from ..application.run_executor import RunExecutor
from ..domain.models import CollectionRun
from ..ports.runs import RunQueueStore, RunExecutionStore

logger = logging.getLogger(__name__)
ConnectorFactory = Callable[[CollectionRun], Awaitable[ConnectorRegistry]]


class CollectionWorker:
    def __init__(self, queue: RunQueueStore, connector_factory: ConnectorFactory, *,
                 execution: RunExecutionStore, poll_interval=1.0):
        self._queue = queue
        self._executor = RunExecutor(execution, connector_factory)
        self._poll_interval = poll_interval
        self._last_recovery = self._last_schedule_check = float('-inf')

    async def run_once(self):
        if time.monotonic()-self._last_recovery >= 5:
            await self._queue.fail_stale_runs()
            self._last_recovery = time.monotonic()
        if time.monotonic()-self._last_schedule_check >= 60:
            try:
                await self._queue.create_due_run()
            except Exception:
                logger.exception('Не удалось проверить расписание сбора')
            self._last_schedule_check = time.monotonic()
        run = await self._queue.claim_next_run()
        if run is None:
            return False
        try:
            await self._executor.execute(run)
        except Exception:
            logger.exception('Не удалось выполнить запуск %s', run.id)
        return True

    async def run_forever(self):
        while True:
            if not await self.run_once():
                await asyncio.sleep(self._poll_interval)
