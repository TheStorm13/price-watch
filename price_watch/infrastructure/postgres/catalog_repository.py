"""Materialize catalog inputs under one read-only PostgreSQL snapshot."""
from sqlalchemy import select
from ...application.catalog_models import CatalogInputs, CatalogCardInput, CardMetrics, GroupMetadata
from ...domain.models import TrackedCardOverview
from .database import AsyncDatabase
from .models import ProductGroupRecord, MarketplaceCardRecord
from .repository_common import _tracked_card
from .queries import overview_statement, card_price_metric_rows


class PostgresCatalogReader:
    def __init__(self, database: AsyncDatabase):
        self._database = database

    async def read_catalog(self) -> CatalogInputs:
        async with self._database.session() as session, session.begin():
            await session.connection(execution_options={
                'isolation_level': 'REPEATABLE READ', 'postgresql_readonly': True})
            groups = (await session.scalars(select(ProductGroupRecord).order_by(ProductGroupRecord.id))).all()
            rows = (await session.execute(overview_statement().order_by(
                MarketplaceCardRecord.deals_enabled.desc(), MarketplaceCardRecord.id))).all()
            metrics = {metric.id: metric for metric in await card_price_metric_rows(session)}
            return CatalogInputs(
                cards=tuple(CatalogCardInput(
                    overview=TrackedCardOverview(_tracked_card(record, variant, last_collected_at=variant.updated_at if variant else None), latest.price if latest else None,
                        latest.availability if latest else None, latest.observed_at if latest else None),
                    metrics=CardMetrics(metrics[record.id].minimum_price, metrics[record.id].average_price,
                                        metrics[record.id].baseline_days),
                    last_collection_run_id=latest.collection_run_id if latest else None,
                ) for record, latest, variant in rows),
                groups=tuple(GroupMetadata(group.id, group.name, tuple(group.tags)) for group in groups),
            )
