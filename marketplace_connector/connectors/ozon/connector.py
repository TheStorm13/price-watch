"""Ozon implementation of the common marketplace connector port."""

from __future__ import annotations

from .client import OzonClient
from .mapper import OzonMapper
from ...domain.models import ProductSnapshot


class OzonConnector:
    marketplace = "ozon"

    def __init__(self, client: OzonClient, mapper: OzonMapper | None = None):
        self._client = client
        self._mapper = mapper or OzonMapper()

    def get_product(self, external_id: str) -> ProductSnapshot:
        response = self._client.fetch_product(external_id)
        return self._mapper.to_snapshot(
            response.payload,
            expected_external_id=response.external_id,
            collected_at=response.received_at,
        )
