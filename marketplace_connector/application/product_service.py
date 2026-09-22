"""Connector registration and marketplace-independent product lookup."""

from typing import Dict, Iterable

from ..domain.errors import UnknownMarketplace
from ..domain.models import ProductSnapshot
from ..ports.connector import MarketplaceConnector


class ConnectorRegistry:
    def __init__(self, connectors: Iterable[MarketplaceConnector] = ()):
        self._connectors: Dict[str, MarketplaceConnector] = {}
        for connector in connectors:
            self.register(connector)

    def register(self, connector: MarketplaceConnector) -> None:
        marketplace = connector.marketplace.strip().lower()
        if not marketplace:
            raise ValueError("marketplace коннектора не должен быть пустым")
        if marketplace in self._connectors:
            raise ValueError(f"Коннектор уже зарегистрирован: {marketplace}")
        self._connectors[marketplace] = connector

    def get(self, marketplace: str) -> MarketplaceConnector:
        key = marketplace.strip().lower()
        try:
            return self._connectors[key]
        except KeyError as exc:
            raise UnknownMarketplace(f"Неизвестный маркетплейс: {marketplace}") from exc


class ProductService:
    def __init__(self, registry: ConnectorRegistry):
        self._registry = registry

    def get_product(self, marketplace: str, external_id: str) -> ProductSnapshot:
        return self._registry.get(marketplace).get_product(external_id)
