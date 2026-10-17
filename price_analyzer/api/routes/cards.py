from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from ..dependencies import RepositoryDep
from ..errors import ApiProblem
from ..schemas import (
    CardCreate,
    CardResponse,
    CardUpdate,
    HistoryPointResponse,
    HistoryResponse,
    ChartResponse,
    DealResponse,
    StatisticsResponse,
    TransferDocument,
    ImportSummary,
)
from ...domain.models import CardOverview
from ...domain.history_merge import ConflictingObservation
from ...infrastructure.postgres.repository import CardAlreadyExists, CardInActiveRun, ImportDuringRun


router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/deals", response_model=list[DealResponse])
async def list_deals(repository: RepositoryDep):
    return [DealResponse.from_domain(deal) for deal in await repository.list_deals()]


@router.get("/{card_id}/chart", response_model=ChartResponse)
async def get_chart(card_id: int, repository: RepositoryDep, days: int = 30):
    if days not in {7, 30, 90}:
        raise ApiProblem(422, "invalid_chart_query", "Некорректный период графика")
    if await repository.get_card(card_id) is None:
        raise ApiProblem(404, "card_not_found", "Карточка не найдена")
    return ChartResponse(points=[HistoryPointResponse.from_domain(point)
                                 for point in await repository.get_chart_points(card_id, days)])


@router.get("", response_model=list[CardResponse])
async def list_cards(repository: RepositoryDep):
    cards = await repository.list_cards()
    metrics = await repository.list_card_price_metrics()
    result = []
    for item in cards:
        minimum, average = metrics.get(item.card.id, (None, None))
        result.append(CardResponse.from_overview(
            item, minimum_price=minimum, average_price=average,
        ))
    return result


@router.get("/export", response_model=TransferDocument)
async def export_cards(repository: RepositoryDep):
    return await repository.export_cards()


async def _import_cards(payload: TransferDocument, repository: RepositoryDep, preview: bool):
    try:
        data = payload.model_dump()
        if payload.groups:
            return await repository.import_cards(data["cards"], groups=data["groups"], preview=preview)
        return await repository.import_cards(data["cards"], preview=preview)
    except ConflictingObservation as exc:
        raise ApiProblem(409, "conflicting_observation", str(exc)) from exc
    except ImportDuringRun as exc:
        raise ApiProblem(409, "import_during_run", str(exc)) from exc


@router.post("/import/preview", response_model=ImportSummary)
async def preview_import(payload: TransferDocument, repository: RepositoryDep):
    return await _import_cards(payload, repository, preview=True)


@router.post("/import", response_model=ImportSummary)
async def import_cards(payload: TransferDocument, repository: RepositoryDep):
    return await _import_cards(payload, repository, preview=False)


@router.post("", response_model=CardResponse, status_code=201)
async def create_card(payload: CardCreate, repository: RepositoryDep):
    try:
        card = await repository.add_card(
            payload.marketplace,
            payload.external_id,
            payload.title,
            str(payload.url) if payload.url else None,
            payload.tags,
        )
    except CardAlreadyExists as exc:
        raise ApiProblem(409, "card_already_exists", str(exc), "externalId") from exc
    return CardResponse.from_overview(CardOverview(card, None, None, None))


@router.get("/{card_id}", response_model=CardResponse)
async def get_card(card_id: int, repository: RepositoryDep):
    overview = await repository.get_card(card_id)
    if overview is None:
        raise ApiProblem(404, "card_not_found", "Карточка не найдена")
    return CardResponse.from_overview(overview)


@router.patch("/{card_id}", response_model=CardResponse)
async def update_card(card_id: int, payload: CardUpdate, repository: RepositoryDep):
    fields = payload.model_fields_set
    try:
        card = await repository.update_card(
            card_id,
            title=payload.title,
            url=str(payload.url) if payload.url else None,
            deals_enabled=payload.deals_enabled if "deals_enabled" in fields else None,
            update_title="title" in fields,
            update_url="url" in fields,
            group_id=payload.group_id,
            update_group="group_id" in fields,
            tags=payload.tags,
        )
    except ValueError as exc:
        raise ApiProblem(422, "invalid_group", str(exc), "groupId") from exc
    if card is None:
        raise ApiProblem(404, "card_not_found", "Карточка не найдена")
    overview = await repository.get_card(card_id)
    return CardResponse.from_overview(overview)


@router.delete(
    "/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_card(card_id: int, repository: RepositoryDep) -> Response:
    try:
        deleted = await repository.delete_card(card_id)
    except CardInActiveRun as exc:
        raise ApiProblem(409, "card_in_active_run", str(exc)) from exc
    if not deleted:
        raise ApiProblem(404, "card_not_found", "Карточка не найдена")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{card_id}/history", response_model=HistoryResponse)
async def get_history(
    card_id: int,
    repository: RepositoryDep,
    days: int = 30,
    page: int = 1,
    page_size: Annotated[int, Query(alias="pageSize")] = 50,
):
    if days not in {7, 30, 90} or page < 1 or not 1 <= page_size <= 200:
        raise ApiProblem(422, "invalid_history_query", "Некорректные параметры истории")
    overview = await repository.get_card(card_id)
    if overview is None:
        raise ApiProblem(404, "card_not_found", "Карточка не найдена")
    history = await repository.get_history(card_id, days, page, page_size)
    return HistoryResponse(
        card=CardResponse.from_overview(overview),
        statistics=StatisticsResponse.from_domain(await repository.get_statistics(card_id, days)),
        history=[HistoryPointResponse.from_domain(item) for item in history],
        page=page,
        page_size=page_size,
        total_count=await repository.count_history(card_id, days),
    )
