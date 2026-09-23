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
    StatisticsResponse,
)
from ...domain.models import CardOverview
from ...infrastructure.postgres.repository import CardAlreadyExists, CardInActiveRun


router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/{card_id}/chart", response_model=ChartResponse)
async def get_chart(card_id: int, repository: RepositoryDep, days: int = 30):
    if days not in {7, 30, 90}:
        raise ApiProblem(422, "invalid_chart_query", "Некорректный период графика")
    if repository.get_card(card_id) is None:
        raise ApiProblem(404, "card_not_found", "Карточка не найдена")
    return ChartResponse(points=[HistoryPointResponse.from_domain(point)
                                 for point in repository.get_chart_points(card_id, days)])


@router.get("", response_model=list[CardResponse])
async def list_cards(repository: RepositoryDep):
    return [CardResponse.from_overview(item) for item in repository.list_cards(include_inactive=True)]


@router.post("", response_model=CardResponse, status_code=201)
async def create_card(payload: CardCreate, repository: RepositoryDep):
    try:
        card = repository.add_card(
            payload.marketplace,
            payload.external_id,
            payload.title,
            str(payload.url) if payload.url else None,
        )
    except CardAlreadyExists as exc:
        raise ApiProblem(409, "card_already_exists", str(exc), "externalId") from exc
    return CardResponse.from_overview(CardOverview(card, None, None, None))


@router.get("/{card_id}", response_model=CardResponse)
async def get_card(card_id: int, repository: RepositoryDep):
    overview = repository.get_card(card_id)
    if overview is None:
        raise ApiProblem(404, "card_not_found", "Карточка не найдена")
    return CardResponse.from_overview(overview)


@router.patch("/{card_id}", response_model=CardResponse)
async def update_card(card_id: int, payload: CardUpdate, repository: RepositoryDep):
    fields = payload.model_fields_set
    card = repository.update_card(
        card_id,
        title=payload.title,
        url=str(payload.url) if payload.url else None,
        is_active=payload.is_active if "is_active" in fields else None,
        update_title="title" in fields,
        update_url="url" in fields,
    )
    if card is None:
        raise ApiProblem(404, "card_not_found", "Карточка не найдена")
    overview = repository.get_card(card_id)
    return CardResponse.from_overview(overview)


@router.delete(
    "/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_card(card_id: int, repository: RepositoryDep) -> Response:
    try:
        deleted = repository.delete_card(card_id)
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
    overview = repository.get_card(card_id)
    if overview is None:
        raise ApiProblem(404, "card_not_found", "Карточка не найдена")
    history = repository.get_history(card_id, days, page, page_size)
    return HistoryResponse(
        card=CardResponse.from_overview(overview),
        statistics=StatisticsResponse.from_domain(repository.get_statistics(card_id, days)),
        history=[HistoryPointResponse.from_domain(item) for item in history],
        page=page,
        page_size=page_size,
        total_count=repository.count_history(card_id, days),
    )
