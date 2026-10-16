"""Persistence port used by application services."""

from typing import Iterable, Optional, Protocol

from marketplace_connector.domain.models import ProductSnapshot

from ..domain.models import CollectionRun, MarketplaceCard


class PriceAnalyzerRepository(Protocol):
    async def delete_card(self, card_id: int) -> bool:
        ...

    async def list_collection_cards(
        self, card_id: Optional[int] = None
    ) -> Iterable[MarketplaceCard]:
        ...

    async def start_run(self, total_count: int) -> int:
        ...

    async def save_observation(
        self, card: MarketplaceCard, run_id: int, snapshot: ProductSnapshot
    ) -> None:
        ...

    async def finish_run(
        self,
        run_id: int,
        status: str,
        success_count: int,
        failure_count: int,
    ) -> None:
        ...

    async def claim_next_run(self, worker_id: str) -> Optional[CollectionRun]:
        ...

    async def cards_for_run(self, run: CollectionRun) -> Iterable[MarketplaceCard]:
        ...

    async def set_run_current(self, run_id: int, card: MarketplaceCard) -> None:
        ...

    async def update_run_progress(
        self, run_id: int, success_count: int, failure_count: int
    ) -> None:
        ...

    async def record_run_error(
        self, run_id: int, error: dict, success_count: int | None = None,
        failure_count: int | None = None,
    ) -> None:
        ...
