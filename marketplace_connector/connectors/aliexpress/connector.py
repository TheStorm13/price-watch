"""AliExpress implementation of the marketplace connector port."""


class AliExpressConnector:
    marketplace = 'aliexpress'

    def __init__(self, client):
        self._client = client

    def collection_session(self):
        return self._client.collection_session()

    async def get_product(self, external_id):
        return (await self._client.fetch_product_async(external_id)).card
