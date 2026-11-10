"""Marketplace port for the authenticated Market client."""
class YandexMarketConnector:
    marketplace = 'yandex-market'

    def __init__(self, client):
        self._client = client

    def collection_session(self):
        return self._client.collection_session()

    async def get_product(self, external_id):
        return await self._client.fetch_product_async(external_id)
