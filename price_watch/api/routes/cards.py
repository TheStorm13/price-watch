from typing import Annotated

from marketplace_connector.domain.errors import InvalidProductId

from fastapi import APIRouter, Query, Response, status

from ..dependencies import CardDep, HistoryDep, TransferDep
from ..errors import ApiProblem
from ..schemas import (
    CardCreate,
    CardResponse,
    CardUpdate,
    VariantResponse,
    HistoryPointResponse,
    HistoryResponse,
    ChartResponse,
    StatisticsResponse,
    TransferDocument,
    ImportDocument,
    ImportSummary,
)
from ...domain.models import TrackedCardOverview
from ...domain.history_merge import ConflictingObservation
from ...domain.errors import CardAlreadyExists, CardInActiveRun, ImportDuringRun


router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/{card_id}/chart", response_model=ChartResponse)
async def get_chart(card_id: int, cards: CardDep, history: HistoryDep, days: int = 30):
    if days not in {7, 30, 90}:
        raise ApiProblem(422, "invalid_chart_query", "Некорректный период графика")
    if await cards.get_card(card_id) is None:
        raise ApiProblem(404, "card_not_found", "Карточка не найдена")
    return ChartResponse(points=[HistoryPointResponse.from_domain(point)
                                 for point in await history.get_chart_points(card_id, days)])


@router.get("/export", response_model=TransferDocument)
async def export_cards(transfer: TransferDep):
    return await transfer.export_cards()


async def _import_cards(payload: ImportDocument, transfer: TransferDep, preview: bool):
    try:
        data = payload.model_dump()
        if payload.groups:
            return await transfer.import_cards(data["cards"], groups=data["groups"], preview=preview)
        return await transfer.import_cards(data["cards"], preview=preview)
    except ConflictingObservation as exc:
        raise ApiProblem(409, "conflicting_observation", str(exc)) from exc
    except ImportDuringRun as exc:
        raise ApiProblem(409, "import_during_run", str(exc)) from exc


@router.post("/import/preview", response_model=ImportSummary)
async def preview_import(payload: ImportDocument, transfer: TransferDep):
    return await _import_cards(payload, transfer, preview=True)


@router.post("/import", response_model=ImportSummary)
async def import_cards(payload: ImportDocument, transfer: TransferDep):
    return await _import_cards(payload, transfer, preview=False)


@router.post("", response_model=CardResponse, status_code=201)
async def create_card(payload: CardCreate, cards: CardDep):
    try:
        card = await cards.add_card(
            payload.marketplace,
            payload.external_id,
            payload.title,
            str(payload.url) if payload.url else None,
            payload.tags,
        )
    except CardAlreadyExists as exc:
        raise ApiProblem(409, "card_already_exists", str(exc), "externalId") from exc
    return CardResponse.from_overview(await cards.get_card(card.id))


@router.get("/{card_id}", response_model=CardResponse)
async def get_card(card_id: int, cards: CardDep):
    overview = await cards.get_card(card_id)
    if overview is None:
        raise ApiProblem(404, "card_not_found", "Карточка не найдена")
    return CardResponse.from_overview(overview)


@router.get("/{card_id}/variants", response_model=list[VariantResponse])
async def get_variants(card_id: int, cards: CardDep):
    if await cards.get_card(card_id) is None:
        raise ApiProblem(404, "card_not_found", "Карточка не найдена")
    return await cards.get_variants(card_id)


@router.patch("/{card_id}", response_model=CardResponse)
async def update_card(card_id: int, payload: CardUpdate, cards: CardDep):
    fields = payload.model_fields_set
    try:
        card = await cards.update_card(
            card_id,
            title=payload.title,
            url=str(payload.url) if payload.url else None,
            deals_enabled=payload.deals_enabled if "deals_enabled" in fields else None,
            update_title="title" in fields,
            update_url="url" in fields,
            group_id=payload.group_id,
            update_group="group_id" in fields,
            tags=payload.tags,
            primary_variant_id=payload.primary_variant_id,
        )
    except InvalidProductId as exc:
        raise ApiProblem(422, "invalid_card_url", str(exc), "url") from exc
    except ValueError as exc:
        raise ApiProblem(422, "invalid_card_update", str(exc), "primaryVariantId" if "primary_variant_id" in fields else "groupId") from exc
    if card is None:
        raise ApiProblem(404, "card_not_found", "Карточка не найдена")
    overview = await cards.get_card(card_id)
    return CardResponse.from_overview(overview)


@router.delete(
    "/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_card(card_id: int, cards: CardDep) -> Response:
    try:
        deleted = await cards.delete_card(card_id)
    except CardInActiveRun as exc:
        raise ApiProblem(409, "card_in_active_run", str(exc)) from exc
    if not deleted:
        raise ApiProblem(404, "card_not_found", "Карточка не найдена")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{card_id}/history", response_model=HistoryResponse)
async def get_history(
    card_id: int,
    cards: CardDep, history: HistoryDep,
    days: int = 30,
    page: int = 1,
    page_size: Annotated[int, Query(alias="pageSize")] = 50,
    variant_id: Annotated[int | None, Query(alias="variantId", ge=1)] = None,
):
    if days not in {7, 30, 90} or page < 1 or not 1 <= page_size <= 200:
        raise ApiProblem(422, "invalid_history_query", "Некорректные параметры истории")
    overview = await cards.get_card(card_id)
    if overview is None:
        raise ApiProblem(404, "card_not_found", "Карточка не найдена")
    if variant_id is not None and variant_id not in {v['id'] for v in await cards.get_variants(card_id)}:
        raise ApiProblem(422, "invalid_variant", "Вариант не принадлежит этому товару", "variantId")
    options = {"variant_id": variant_id} if variant_id is not None else {}
    points = await history.get_history(card_id, days, page, page_size, **options)
    return HistoryResponse(
        card=CardResponse.from_overview(overview),
        statistics=StatisticsResponse.from_domain(await history.get_statistics(card_id, days, **options)),
        history=[HistoryPointResponse.from_domain(item) for item in points],
        page=page,
        page_size=page_size,
        total_count=await history.count_history(card_id, days, **options),
    )
