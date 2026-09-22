"""Errors exposed consistently by every marketplace connector."""

from typing import Optional


class ConnectorError(Exception):
    """Base class for expected connector failures."""


class InvalidProductId(ConnectorError, ValueError):
    pass


class ProductNotFound(ConnectorError):
    pass


class AuthenticationRequired(ConnectorError):
    pass


class ChallengeRequired(ConnectorError):
    pass


class RateLimited(ConnectorError):
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class MarketplaceUnavailable(ConnectorError):
    pass


class MarketplaceSchemaChanged(ConnectorError):
    pass


class UnknownMarketplace(ConnectorError):
    pass
