"""Bridge an interactive browser challenge to durable run state."""

import asyncio

from ..infrastructure.postgres.repository import PostgresPriceAnalyzerRepository


class DatabaseChallengeHandler:
    def __init__(
        self,
        repository: PostgresPriceAnalyzerRepository,
        lease,
        poll_interval: float = 0.5,
    ):
        self._repository = repository
        self._lease = lease
        self._poll_interval = poll_interval

    async def handle_async(self, marketplace: str, message: str) -> None:
        await self._repository.set_run_waiting(
            self._lease,
            challenge_type="browser_verification",
            message=message,
        )
        while True:
            status = await self._repository.get_owned_status(self._lease)
            if status == "running":
                return
            if status != "waiting_for_user":
                raise RuntimeError(
                    f"Запуск {self._lease.run_id} больше не ожидает проверку: {status}"
                )
            await asyncio.sleep(self._poll_interval)
