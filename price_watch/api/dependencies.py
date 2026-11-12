from typing import Annotated
from fastapi import Depends, Request
from ..application.catalog_service import CatalogService
from ..ports.purchase import PurchaseSettingsStore
from ..ports.thumbnails import ThumbnailReader
from ..ports.catalog_storage import CardStore, HistoryReader, GroupStore, TransferStore
from ..ports.runs import RunQueueStore, RunChallengeStore


def get_cards(request: Request) -> CardStore:
    return request.app.state.services.cards


CardDep = Annotated[CardStore, Depends(get_cards)]


def get_history(request: Request) -> HistoryReader:
    return request.app.state.services.history


HistoryDep = Annotated[HistoryReader, Depends(get_history)]


def get_groups(request: Request) -> GroupStore:
    return request.app.state.services.groups


GroupDep = Annotated[GroupStore, Depends(get_groups)]


def get_transfer(request: Request) -> TransferStore:
    return request.app.state.services.transfer


TransferDep = Annotated[TransferStore, Depends(get_transfer)]


def get_runs(request: Request) -> RunQueueStore:
    return request.app.state.services.runs


RunDep = Annotated[RunQueueStore, Depends(get_runs)]


def get_challenges(request: Request) -> RunChallengeStore:
    return request.app.state.services.challenges


ChallengeDep = Annotated[RunChallengeStore, Depends(get_challenges)]


def get_catalog(request: Request) -> CatalogService:
    return request.app.state.services.catalog


CatalogDep = Annotated[CatalogService, Depends(get_catalog)]


def get_thumbnails(request: Request) -> ThumbnailReader:
    return request.app.state.thumbnails


ThumbnailDep = Annotated[ThumbnailReader, Depends(get_thumbnails)]


def get_purchase(request: Request) -> PurchaseSettingsStore:
    return request.app.state.services.purchase


PurchaseDep = Annotated[PurchaseSettingsStore, Depends(get_purchase)]
