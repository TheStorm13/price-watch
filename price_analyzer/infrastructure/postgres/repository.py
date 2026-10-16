"""PostgreSQL repository facade composed from focused persistence areas."""

from .database import AsyncDatabase
from .repository_common import (
    CardAlreadyExists, CardInActiveRun, NoCards, ConnectorNotAvailable, ImportDuringRun,
)
from .cards_repository import CardRepository
from .runs_repository import RunRepository
from .history_repository import HistoryRepository
from .transfer_repository import TransferRepository
from .deals_repository import DealRepository
from .groups_repository import GroupRepository


class PostgresPriceAnalyzerRepository(
    CardRepository, RunRepository, HistoryRepository, TransferRepository, DealRepository, GroupRepository,
):
    def __init__(self, database: AsyncDatabase):
        self._database = database
