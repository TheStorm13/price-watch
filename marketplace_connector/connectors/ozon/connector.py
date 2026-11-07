"""Ozon implementation of the common marketplace connector port."""

from __future__ import annotations

from dataclasses import replace

from .async_client import AsyncOzonClient
from .mapper import OzonMapper
from .parser import OzonProductParser
from ...domain.models import MarketplaceCard


class OzonConnector:
    marketplace = "ozon"

    def __init__(self, client: AsyncOzonClient, mapper: OzonMapper | None = None):
        self._client = client
        self._mapper = mapper or OzonMapper()

    def collection_session(self):
        return self._client.collection_session()

    async def get_product(self, external_id: str) -> MarketplaceCard:
        response = await self._client.fetch_product_async(external_id)
        data = OzonProductParser.parse(
            response.raw_text,
            expected_external_id=response.external_id,
            collected_at=response.received_at,
        )
        if response.aspects is not None:
            data = replace(data, aspects=response.aspects, discovery_error=response.discovery_error)
        return self._mapper.to_card(data)
