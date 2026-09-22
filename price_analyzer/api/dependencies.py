from typing import Annotated

from fastapi import Depends, Request

from ..infrastructure.postgres.repository import PostgresPriceAnalyzerRepository


async def get_repository(request: Request) -> PostgresPriceAnalyzerRepository:
    return request.app.state.repository


RepositoryDep = Annotated[PostgresPriceAnalyzerRepository, Depends(get_repository)]
