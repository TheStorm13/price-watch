"""Durable single-host collection worker."""

import asyncio
import logging
import os
import socket
import time
from datetime import datetime, timedelta, timezone
import traceback
from typing import Awaitable, Callable

from marketplace_connector.application.product_service import ConnectorRegistry

from ..application.collection_service import CollectionService
from ..domain.models import CollectionRun
from ..infrastructure.postgres.repository import PostgresPriceAnalyzerRepository


logger = logging.getLogger(__name__)
ConnectorFactory = Callable[[CollectionRun], Awaitable[ConnectorRegistry]]


class CollectionWorker:
    def __init__(
        self,
        repository: PostgresPriceAnalyzerRepository,
        connector_factory: ConnectorFactory,
        worker_id: str | None = None,
        poll_interval: float = 1.0,
    ):
        self._repository = repository
        self._connector_factory = connector_factory
        self._worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
        self._poll_interval = poll_interval
        self._last_recovery = 0.0
        self._last_schedule_check = 0.0
        self._stale_after_seconds = max(15.0, float(os.environ.get("RUN_STALE_SECONDS", "30")))

    async def _heartbeat(self, run_id: int, stop: asyncio.Event) -> None:
        while True:
            try:
                await asyncio.wait_for(stop.wait(), timeout=5)
                return
            except TimeoutError:
                pass
            try:
                await self._repository.touch_run(run_id, self._worker_id)
            except Exception:
                logger.exception("Не удалось обновить heartbeat запуска %s", run_id)

    async def run_once(self) -> bool:
        if time.monotonic() - self._last_recovery >= 5:
            await self._repository.fail_stale_runs(datetime.now(timezone.utc) - timedelta(seconds=self._stale_after_seconds))
            self._last_recovery = time.monotonic()
        if time.monotonic() - self._last_schedule_check >= 60:
            try:
                scheduled = await self._repository.create_due_run()
                if scheduled:
                    logger.info("Автоматический сбор поставлен в очередь: %s", scheduled.id)
            except Exception:
                logger.exception("Не удалось проверить расписание сбора")
            self._last_schedule_check = time.monotonic()
        run = await self._repository.claim_next_run(self._worker_id)
        if run is None:
            return False
        logger.info("Запуск %s взят worker=%s", run.id, self._worker_id)
        stop_heartbeat = asyncio.Event()
        heartbeat = asyncio.create_task(self._heartbeat(run.id, stop_heartbeat))
        try:
            service = CollectionService(
                self._repository,
                await self._connector_factory(run),
            )
            await service.execute_run(run)
        except Exception as exc:
            logger.exception("Worker не смог выполнить запуск %s", run.id)
            current = await self._repository.get_run(run.id)
            if current and current.status not in {
                "completed", "completed_with_errors", "failed"
            }:
                await self._repository.record_run_error(run.id, {
                    "cardId": None, "marketplace": None, "externalId": None,
                    "at": datetime.now(timezone.utc).isoformat(),
                    "type": type(exc).__name__, "message": str(exc),
                    "traceback": traceback.format_exc(),
                })
                await self._repository.finish_run(
                    run.id,
                    "failed",
                    current.success_count,
                    current.failure_count,
                )
        finally:
            stop_heartbeat.set()
            await heartbeat
        return True

    async def run_forever(self) -> None:
        logger.info("Worker запущен: %s", self._worker_id)
        while True:
            if not await self.run_once():
                await asyncio.sleep(self._poll_interval)
