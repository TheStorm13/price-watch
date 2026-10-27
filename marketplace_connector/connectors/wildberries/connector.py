"""Wildberries implementation of the marketplace connector port."""
from .mapper import WildberriesMapper


class WildberriesConnector:
    marketplace = 'wildberries'

    def __init__(self, client):
        self._client = client

    def collection_session(self):
        return self._client.collection_session()

    async def get_product(self, external_id):
        return WildberriesMapper.to_card(await self._client.fetch_product_async(external_id), external_id)
