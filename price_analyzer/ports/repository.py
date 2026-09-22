"""Persistence port used by application services."""

from typing import Iterable, Optional, Protocol

from marketplace_connector.domain.models import ProductSnapshot

from ..domain.models import CollectionRun, MarketplaceCard


class PriceAnalyzerRepository(Protocol):
    def delete_card(self, card_id: int) -> bool:
        ...

    def list_active_cards(
        self, card_id: Optional[int] = None
    ) -> Iterable[MarketplaceCard]:
        ...

    def start_run(self, total_count: int) -> int:
        ...

    def save_observation(
        self, card: MarketplaceCard, run_id: int, snapshot: ProductSnapshot
    ) -> None:
        ...

    def finish_run(
        self,
        run_id: int,
        status: str,
        success_count: int,
        failure_count: int,
    ) -> None:
        ...

    def claim_next_run(self, worker_id: str) -> Optional[CollectionRun]:
        ...

    def set_run_current(self, run_id: int, card: MarketplaceCard) -> None:
        ...

    def update_run_progress(
        self, run_id: int, success_count: int, failure_count: int
    ) -> None:
        ...
