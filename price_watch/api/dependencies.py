from typing import Annotated

from fastapi import Depends, Request

from ..infrastructure.postgres.repository import PostgresPriceWatchRepository


async def get_repository(request: Request) -> PostgresPriceWatchRepository:
    return request.app.state.repository


RepositoryDep = Annotated[PostgresPriceWatchRepository, Depends(get_repository)]
