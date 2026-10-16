from fastapi import APIRouter, Response, status

from ..dependencies import RepositoryDep
from ..errors import ApiProblem
from ..schemas import GroupInput, GroupResponse

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("", response_model=list[GroupResponse])
async def list_groups(repository: RepositoryDep):
    return await repository.list_groups()


@router.post("", response_model=GroupResponse, status_code=201)
async def create_group(payload: GroupInput, repository: RepositoryDep):
    try:
        group_id = await repository.create_group(payload.name, payload.card_ids)
    except ValueError as exc:
        raise ApiProblem(422, "invalid_group", str(exc)) from exc
    return next(group for group in await repository.list_groups() if group["id"] == group_id)


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(group_id: int, payload: GroupInput, repository: RepositoryDep):
    try:
        updated = await repository.update_group(group_id, payload.name, payload.card_ids)
    except ValueError as exc:
        raise ApiProblem(422, "invalid_group", str(exc)) from exc
    if not updated:
        raise ApiProblem(404, "group_not_found", "Группа не найдена")
    return next(group for group in await repository.list_groups() if group["id"] == group_id)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: int, repository: RepositoryDep):
    if not await repository.delete_group(group_id):
        raise ApiProblem(404, "group_not_found", "Группа не найдена")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
