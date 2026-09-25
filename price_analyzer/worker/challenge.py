"""Bridge an interactive browser challenge to durable run state."""

import asyncio
import time

from ..infrastructure.postgres.repository import PostgresPriceAnalyzerRepository


class DatabaseChallengeHandler:
    def __init__(
        self,
        repository: PostgresPriceAnalyzerRepository,
        run_id: int,
        poll_interval: float = 0.5,
    ):
        self._repository = repository
        self._run_id = run_id
        self._poll_interval = poll_interval

    def handle(self, marketplace: str, message: str) -> None:
        self._repository.set_run_waiting(
            self._run_id,
            challenge_type="browser_verification",
            message=message,
        )
        while True:
            status = self._repository.get_run_status(self._run_id)
            if status == "running":
                return
            if status not in {"waiting_for_user"}:
                raise RuntimeError(
                    f"Запуск {self._run_id} больше не ожидает проверку: {status}"
                )
            time.sleep(self._poll_interval)

    async def handle_async(self, marketplace: str, message: str) -> None:
        self._repository.set_run_waiting(
            self._run_id,
            challenge_type="browser_verification",
            message=message,
        )
        while True:
            status = self._repository.get_run_status(self._run_id)
            if status == "running":
                return
            if status != "waiting_for_user":
                raise RuntimeError(
                    f"Запуск {self._run_id} больше не ожидает проверку: {status}"
                )
            await asyncio.sleep(self._poll_interval)
