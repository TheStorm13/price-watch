"""Fetch concurrently; persist each target's result atomically under its lease."""
import asyncio
import logging
import traceback
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from marketplace_connector.domain.errors import ProductNotFound
from marketplace_connector.domain.models import Availability, ProductRef, ProductSnapshot
from ..domain.models import LeaseLost
from ..ports.repository import PriceAnalyzerRepository

logger = logging.getLogger(__name__)
MAX_CONCURRENT_CARDS = 5


class CollectionService:
    def __init__(self, repository: PriceAnalyzerRepository, connectors):
        self._repository = repository
        self._connectors = connectors

    async def execute(self, lease, cards):
        async with AsyncExitStack() as sessions:
            for marketplace in dict.fromkeys(card.marketplace for card in cards):
                await sessions.enter_async_context(self._connectors.get(marketplace).collection_session())
            limit = asyncio.Semaphore(MAX_CONCURRENT_CARDS)

            async def fetch(card):
                async with limit:
                    try:
                        snapshot = await self._connectors.get(card.marketplace).get_product(card.external_id)
                    except ProductNotFound:
                        snapshot = ProductSnapshot(ref=ProductRef(card.marketplace, card.external_id),
                            title=card.title if card.title and card.title.strip() else f'Товар {card.external_id}',
                            url=card.url or '', availability=Availability.OUT_OF_STOCK,
                            collected_at=datetime.now(timezone.utc))
                    except Exception as exc:
                        return card, None, exc, traceback.format_exc()
                    return card, snapshot, None, None

            if len(cards) == 1:
                await self._repository.set_run_current(lease, cards[0])
            tasks = [asyncio.create_task(fetch(card)) for card in cards]
            try:
                for completed in asyncio.as_completed(tasks):
                    card, snapshot, error, diagnostic = await completed
                    try:
                        if error is not None:
                            raise error
                        await self._repository.save_result(lease, card, snapshot)
                    except LeaseLost:
                        raise
                    except Exception as exc:
                        await self._repository.record_card_error(lease, card, {
                            'cardId': card.id, 'marketplace': card.marketplace, 'externalId': card.external_id,
                            'at': datetime.now(timezone.utc).isoformat(), 'type': type(exc).__name__,
                            'message': str(exc), 'traceback': diagnostic or traceback.format_exc()})
                        logger.error('Не удалось обновить карточку %s: %s', card.id, exc)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
