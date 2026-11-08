"""Fetch concurrently; persist each target's result atomically under its lease."""
import asyncio
import logging
import traceback
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from marketplace_connector.domain.errors import ProductNotFound, UnsafeBrowserTeardown
from marketplace_connector.domain.models import Availability, ProductRef, MarketplaceCard
from marketplace_connector.application.product_service import ProductService
from ..domain.models import LeaseLost
from ..ports.runs import RunExecutionStore

logger = logging.getLogger(__name__)
MARKETPLACE_ORDER = ('ozon', 'aliexpress', 'wildberries')


class CollectionService:
    def __init__(self, repository: RunExecutionStore, connectors):
        self._repository = repository
        self._connectors = connectors

    async def execute(self, lease, cards):
        if not cards:
            return
        async with self._connectors.run_session():
            products = ProductService(self._connectors)

            async def fetch(card):
                try:
                    snapshot = await products.get_product(card.ref.marketplace, card.ref.external_id)
                except UnsafeBrowserTeardown:
                    raise
                except ProductNotFound:
                    snapshot = MarketplaceCard(ref=ProductRef(card.ref.marketplace, card.ref.external_id),
                        title=card.title if card.title and card.title.strip() else f'Товар {card.ref.external_id}',
                        url=card.url or '', availability=Availability.OUT_OF_STOCK,
                        collected_at=datetime.now(timezone.utc))
                except Exception as exc:
                    return card, None, exc, traceback.format_exc()
                return card, snapshot, None, None

            async def batch(cards):
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
                        except (LeaseLost, UnsafeBrowserTeardown):
                            raise
                        except Exception as exc:
                            await self._repository.record_card_error(lease, card, {
                                'cardId': card.id, 'variantId': card.variant_id, 'marketplace': card.ref.marketplace, 'externalId': card.ref.external_id,
                                'at': datetime.now(timezone.utc).isoformat(), 'type': type(exc).__name__,
                                'message': str(exc), 'traceback': diagnostic or traceback.format_exc()})
                            logger.error('Не удалось обновить карточку %s: %s', card.id, exc)
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)

            failed_stages = set()
            while cards:
                order = sorted({card.ref.marketplace for card in cards},
                    key=lambda m: (MARKETPLACE_ORDER.index(m) if m in MARKETPLACE_ORDER else len(MARKETPLACE_ORDER), m))
                for marketplace in order:
                    group = [card for card in cards if card.ref.marketplace == marketplace]
                    if marketplace in failed_stages:
                        continue
                    async with AsyncExitStack() as stage:
                        try:
                            await stage.enter_async_context(self._connectors.get(marketplace).collection_session())
                        except (LeaseLost, UnsafeBrowserTeardown):
                            raise
                        except Exception as exc:
                            failed_stages.add(marketplace)
                            for card in group:
                                await self._repository.record_card_error(lease, card, {
                                    'cardId': card.id, 'variantId': card.variant_id,
                                    'marketplace': marketplace, 'externalId': card.ref.external_id,
                                    'at': datetime.now(timezone.utc).isoformat(),
                                    'type': type(exc).__name__, 'message': str(exc),
                                    'traceback': traceback.format_exc()})
                            continue
                        while group:
                            await batch(group)
                            cards = await self._repository.cards_for_run(lease.run_id, pending_only=True)
                            group = [card for card in cards if card.ref.marketplace == marketplace]
                cards = await self._repository.cards_for_run(lease.run_id, pending_only=True)
                cards = [card for card in cards if card.ref.marketplace not in failed_stages]
