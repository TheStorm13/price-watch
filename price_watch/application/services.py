"""Typed dependencies assembled at startup and injected individually into routes."""
from dataclasses import dataclass
from ..ports.purchase import PurchaseSettingsStore
from .catalog_service import CatalogService
from ..ports.catalog_storage import CardStore, HistoryReader, GroupStore, TransferStore
from ..ports.runs import RunQueueStore, RunChallengeStore


@dataclass(frozen=True)
class ApiServices:
    cards: CardStore
    history: HistoryReader
    groups: GroupStore
    transfer: TransferStore
    runs: RunQueueStore
    challenges: RunChallengeStore
    catalog: CatalogService
    purchase: PurchaseSettingsStore
