"""Ozon implementation of the common marketplace connector port."""

from __future__ import annotations

from .async_client import AsyncOzonClient
from .mapper import OzonMapper
from ...domain.models import ProductSnapshot


class OzonConnector:
    marketplace = "ozon"

    def __init__(self, client: AsyncOzonClient, mapper: OzonMapper | None = None):
        self._client = client
        self._mapper = mapper or OzonMapper()

    def collection_session(self):
        return self._client.collection_session()

    async def get_product(self, external_id: str) -> ProductSnapshot:
        response = await self._client.fetch_product_async(external_id)
        return self._mapper.to_snapshot(
            response.payload,
            expected_external_id=response.external_id,
            collected_at=response.received_at,
        )
