"""Ozon implementation of the common marketplace connector port."""
from .async_client import AsyncOzonClient
from ...domain.models import MarketplaceCard


class OzonConnector:
    marketplace = 'ozon'

    def __init__(self, client: AsyncOzonClient):
        self._client = client

    def collection_session(self):
        return self._client.collection_session()

    async def get_product(self, external_id: str) -> MarketplaceCard:
        return (await self._client.fetch_product_async(external_id)).card
