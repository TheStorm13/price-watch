from typing import Annotated

from fastapi import APIRouter, Query

from ..dependencies import RepositoryDep
from ..errors import ApiProblem
from ..schemas import RunCreate, RunResponse
from ...infrastructure.postgres.repository import ConnectorNotAvailable, NoCards


router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=list[RunResponse])
async def list_runs(
    repository: RepositoryDep,
    page: int = 1,
    page_size: Annotated[int, Query(alias="pageSize")] = 50,
):
    if page < 1 or not 1 <= page_size <= 200:
        raise ApiProblem(422, "invalid_pagination", "Некорректная пагинация")
    return [RunResponse.from_domain(item, include_errors=False) for item in await repository.list_runs(page, page_size)]


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: int, repository: RepositoryDep, include_errors: Annotated[bool, Query(alias="includeErrors")] = True):
    run = await repository.get_run(run_id)
    if run is None:
        raise ApiProblem(404, "run_not_found", "Запуск не найден")
    return RunResponse.from_domain(run, include_errors=include_errors)


@router.post("", response_model=RunResponse, status_code=202)
async def create_run(payload: RunCreate, repository: RepositoryDep):
    try:
        run = await repository.create_queued_run(payload.card_id)
    except LookupError as exc:
        raise ApiProblem(404, "card_not_found", str(exc)) from exc
    except NoCards as exc:
        raise ApiProblem(409, "no_cards", str(exc)) from exc
    except ConnectorNotAvailable as exc:
        raise ApiProblem(409, "connector_not_available", str(exc)) from exc
    return RunResponse.from_domain(run)


@router.post("/{run_id}/continue", response_model=RunResponse)
async def continue_run(run_id: int, repository: RepositoryDep):
    try:
        run = await repository.continue_run(run_id)
    except ValueError as exc:
        raise ApiProblem(409, "run_not_waiting", str(exc)) from exc
    if run is None:
        raise ApiProblem(404, "run_not_found", "Запуск не найден")
    return RunResponse.from_domain(run)


@router.post("/{run_id}/retry", response_model=RunResponse, status_code=202)
async def retry_run(run_id: int, repository: RepositoryDep):
    try:
        run = await repository.create_retry_run(run_id)
    except LookupError as exc:
        raise ApiProblem(404, "run_not_found", str(exc)) from exc
    except ValueError as exc:
        raise ApiProblem(409, "retry_not_available", str(exc)) from exc
    return RunResponse.from_domain(run)
