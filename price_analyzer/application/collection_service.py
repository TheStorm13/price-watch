"""Orchestrate connector calls without holding database transactions open."""

import logging
import traceback
from datetime import datetime, timezone
from typing import Optional

from marketplace_connector.application.product_service import ConnectorRegistry

from ..domain.models import CollectionRun, CollectionSummary
from ..ports.repository import PriceAnalyzerRepository


logger = logging.getLogger(__name__)


class CollectionService:
    def __init__(
        self,
        repository: PriceAnalyzerRepository,
        connectors: ConnectorRegistry,
    ):
        self._repository = repository
        self._connectors = connectors

    def collect(self, card_id: Optional[int] = None) -> CollectionSummary:
        cards = list(self._repository.list_active_cards(card_id))
        if card_id is not None and not cards:
            raise LookupError(f"Активная карточка не найдена: {card_id}")
        run_id = self._repository.start_run(len(cards))
        return self._collect_cards(run_id, cards, report_progress=False)

    def execute_run(self, run: CollectionRun) -> CollectionSummary:
        """Execute a run already claimed by the durable worker queue."""
        cards = self._repository.cards_for_run(run)
        return self._collect_cards(run.id, cards, report_progress=True)

    def _collect_cards(self, run_id, cards, report_progress: bool) -> CollectionSummary:
        success_count = 0
        failure_count = 0

        try:
            for card in cards:
                if report_progress:
                    self._repository.set_run_current(run_id, card)
                try:
                    connector = self._connectors.get(card.marketplace)
                    snapshot = connector.get_product(card.external_id)
                    if snapshot.ref.marketplace != card.marketplace:
                        raise ValueError("Коннектор вернул другой маркетплейс")
                    if snapshot.ref.external_id != card.external_id:
                        raise ValueError("Коннектор вернул другую карточку")
                    self._repository.save_observation(card, run_id, snapshot)
                except Exception as exc:
                    failure_count += 1
                    self._repository.record_run_error(run_id, {
                        "cardId": card.id, "marketplace": card.marketplace,
                        "externalId": card.external_id,
                        "at": datetime.now(timezone.utc).isoformat(),
                        "type": type(exc).__name__, "message": str(exc),
                        "traceback": traceback.format_exc(),
                    }, success_count, failure_count)
                    logger.exception(
                        "Не удалось обновить карточку: card_id=%s marketplace=%s external_id=%s",
                        card.id,
                        card.marketplace,
                        card.external_id,
                    )
                else:
                    success_count += 1
                    if report_progress:
                        self._repository.update_run_progress(run_id, success_count, failure_count)

            status = "completed" if failure_count == 0 else "completed_with_errors"
            self._repository.finish_run(
                run_id, status, success_count, failure_count
            )
            return CollectionSummary(
                run_id=run_id,
                status=status,
                total_count=len(cards),
                success_count=success_count,
                failure_count=failure_count,
            )
        except BaseException as exc:
            self._repository.record_run_error(run_id, {
                "cardId": None, "marketplace": None, "externalId": None,
                "at": datetime.now(timezone.utc).isoformat(),
                "type": type(exc).__name__, "message": str(exc),
                "traceback": traceback.format_exc(),
            }, success_count, failure_count)
            self._repository.finish_run(
                run_id, "failed", success_count, failure_count
            )
            raise
