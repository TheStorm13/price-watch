"""One persistent settings row, shared with consistent catalog snapshots."""
from sqlalchemy import select
from ...domain.purchase import PurchaseSettings
from .models import PurchaseSettingsRecord
from .database import AsyncDatabase


def settings_view(record: PurchaseSettingsRecord) -> PurchaseSettings:
    return PurchaseSettings(record.small_range_tolerance, record.historical_savings_share,
                            record.target_notifications_enabled, record.instance_id)


class PurchaseRepository:
    def __init__(self, database: AsyncDatabase):
        self._database = database

    async def get_settings(self) -> PurchaseSettings:
        async with self._database.session() as session:
            return settings_view(await session.get(PurchaseSettingsRecord, 1))

    async def update_settings(self, changes: dict) -> PurchaseSettings:
        async with self._database.session() as session, session.begin():
            record = await session.scalar(select(PurchaseSettingsRecord).where(PurchaseSettingsRecord.id == 1).with_for_update())
            for key, value in changes.items():
                setattr(record, key, value)
            await session.flush()
            return settings_view(record)
