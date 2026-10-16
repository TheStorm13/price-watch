"""PostgreSQL repository facade composed from focused persistence areas."""

from .database import AsyncDatabase
from .repository_common import (
    CardAlreadyExists, CardInActiveRun, NoCards, ImportDuringRun,
)
from .cards_repository import CardRepository
from .runs_repository import RunRepository
from .history_repository import HistoryRepository
from .transfer_repository import TransferRepository
from .deals_repository import DealRepository


class PostgresPriceAnalyzerRepository(
    CardRepository, RunRepository, HistoryRepository, TransferRepository, DealRepository,
):
    def __init__(self, database: AsyncDatabase):
        self._database = database
