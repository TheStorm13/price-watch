"""Durable single-host collection worker."""

import logging
import os
import socket
import time
from typing import Callable

from marketplace_connector.application.product_service import ConnectorRegistry

from ..application.collection_service import CollectionService
from ..domain.models import CollectionRun
from ..infrastructure.postgres.repository import PostgresPriceAnalyzerRepository


logger = logging.getLogger(__name__)
ConnectorFactory = Callable[[CollectionRun], ConnectorRegistry]


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

    def run_once(self) -> bool:
        run = self._repository.claim_next_run(self._worker_id)
        if run is None:
            return False
        logger.info("Запуск %s взят worker=%s", run.id, self._worker_id)
        try:
            service = CollectionService(
                self._repository,
                self._connector_factory(run),
            )
            service.execute_run(run.id, run.requested_card_id)
        except Exception:
            logger.exception("Worker не смог выполнить запуск %s", run.id)
            current = self._repository.get_run(run.id)
            if current and current.status not in {
                "completed", "completed_with_errors", "failed"
            }:
                self._repository.finish_run(
                    run.id,
                    "failed",
                    current.success_count,
                    current.failure_count,
                )
        return True

    def run_forever(self) -> None:
        logger.info("Worker запущен: %s", self._worker_id)
        while True:
            if not self.run_once():
                time.sleep(self._poll_interval)
