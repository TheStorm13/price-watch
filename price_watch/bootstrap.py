"""Composition root: configure concrete storage and expose explicit dependencies."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os

from .infrastructure.postgres.purchase_repository import PurchaseRepository
from .application.catalog_service import CatalogService
from .application.services import ApiServices
from .domain.collection_policy import CollectionPolicy
from .ports.runs import Clock
from .infrastructure.postgres.database import AsyncDatabase
from .infrastructure.postgres.cards_repository import CardRepository
from .infrastructure.postgres.runs_repository import RunRepository
from .infrastructure.postgres.history_repository import HistoryRepository
from .infrastructure.postgres.groups_repository import GroupRepository
from .infrastructure.postgres.transfer_repository import TransferRepository
from .infrastructure.postgres.catalog_repository import PostgresCatalogReader


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class PostgresStores:
    cards: CardRepository
    runs: RunRepository
    history: HistoryRepository
    groups: GroupRepository
    transfer: TransferRepository
    catalog: CatalogService
    purchase: PurchaseRepository

    @property
    def api(self) -> ApiServices:
        return ApiServices(self.cards, self.history, self.groups, self.transfer,
                           self.runs, self.runs, self.catalog, self.purchase)


def create_postgres_stores(database: AsyncDatabase, *, policy: CollectionPolicy | None = None,
                           clock: Clock = utc_now) -> PostgresStores:
    if policy is None:
        policy = CollectionPolicy(stale_after=timedelta(seconds=float(os.environ.get('RUN_STALE_SECONDS', '30'))))
    runs = RunRepository(database, policy, clock)
    return PostgresStores(CardRepository(database, runs), runs,
                          HistoryRepository(database), GroupRepository(database), TransferRepository(database),
                          CatalogService(PostgresCatalogReader(database)), PurchaseRepository(database))
