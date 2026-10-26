"""AliExpress implementation of the marketplace connector port."""
from .parser import AliExpressProductParser
from .mapper import AliExpressMapper


class AliExpressConnector:
    marketplace = 'aliexpress'

    def __init__(self, client):
        self._client = client

    def collection_session(self):
        return self._client.collection_session()

    async def get_product(self, external_id):
        response = await self._client.fetch_product_async(external_id)
        return AliExpressMapper.to_card(AliExpressProductParser.parse(
            response.raw_text, expected_external_id=response.external_id, collected_at=response.received_at))
