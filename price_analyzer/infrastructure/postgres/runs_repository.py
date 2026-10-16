"""Durable collection queue and run state."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select, update

from ...domain.models import CollectionRun, MarketplaceCard
from .models import CollectionRunRecord, MarketplaceCardRecord
from .repository_common import NoActiveCards, _RUN_CREATION_LOCK, _card, _run


class RunRepository:
    async def start_run(self, total_count: int) -> int:
        record = CollectionRunRecord(status="running", total_count=total_count,
                                     is_full_collection=True)
        async with self._database.session() as session, session.begin():
            session.add(record)
            await session.flush()
        return record.id

    async def create_queued_run(self, card_id: Optional[int] = None) -> CollectionRun:
        async with self._database.session() as session, session.begin():
            await session.execute(_RUN_CREATION_LOCK)
            statement = select(MarketplaceCardRecord).where(MarketplaceCardRecord.is_active.is_(True))
            if card_id is not None:
                statement = statement.where(MarketplaceCardRecord.id == card_id)
            cards = (await session.scalars(statement.order_by(MarketplaceCardRecord.marketplace, MarketplaceCardRecord.id).with_for_update(read=True))).all()
            if not cards:
                if card_id is not None:
                    raise LookupError(f"Активная карточка не найдена: {card_id}")
                raise NoActiveCards("Нет активных карточек для сбора")
            record = CollectionRunRecord(
                status="queued", total_count=len(cards), requested_card_id=card_id,
                is_full_collection=card_id is None,
                target_card_ids=[card.id for card in cards],
            )
            session.add(record)
            await session.flush()
        return _run(record)

    async def create_due_run(self, now: datetime | None = None) -> Optional[CollectionRun]:
        """Queue all active cards once every 12 hours while a worker is alive."""
        now = now or datetime.now(timezone.utc)
        async with self._database.session() as session, session.begin():
            await session.execute(_RUN_CREATION_LOCK)
            active_run = (await session.scalar(select(CollectionRunRecord.id).where(
                CollectionRunRecord.status.in_(("queued", "running", "waiting_for_user")),
            ).limit(1)))
            if active_run is not None:
                return None
            last_started = (await session.scalar(select(CollectionRunRecord.started_at).where(
                CollectionRunRecord.is_full_collection.is_(True),
            ).order_by(
                CollectionRunRecord.started_at.desc(), CollectionRunRecord.id.desc()
            ).limit(1)))
            if last_started is not None and now - last_started < timedelta(hours=12):
                return None
            cards = (await session.scalars(select(MarketplaceCardRecord).where(
                MarketplaceCardRecord.is_active.is_(True)
            ).order_by(MarketplaceCardRecord.marketplace, MarketplaceCardRecord.id))).all()
            if not cards:
                return None
            record = CollectionRunRecord(status="queued", total_count=len(cards),
                                         is_full_collection=True,
                                         target_card_ids=[card.id for card in cards], started_at=now)
            session.add(record)
            await session.flush()
            return _run(record)

    async def create_retry_run(self, source_run_id: int) -> CollectionRun:
        async with self._database.session() as session, session.begin():
            await session.execute(_RUN_CREATION_LOCK)
            source = (await session.get(CollectionRunRecord, source_run_id, with_for_update=True))
            if source is None:
                raise LookupError("Запуск не найден")
            if source.status not in ("completed_with_errors", "failed"):
                raise ValueError("Повтор доступен только после завершения с ошибками")
            if (await session.scalar(select(CollectionRunRecord.id).where(
                CollectionRunRecord.retry_of_run_id == source_run_id
            ).limit(1))) is not None:
                raise ValueError("Повтор для этого запуска уже создан")
            failed_ids = list(dict.fromkeys(error.get("cardId") for error in source.errors or []
                                            if isinstance(error.get("cardId"), int)))
            if not failed_ids:
                raise ValueError("В запуске нет карточек с ошибками для повтора")
            cards = (await session.scalars(select(MarketplaceCardRecord).where(
                MarketplaceCardRecord.id.in_(failed_ids), MarketplaceCardRecord.is_active.is_(True)
            ))).all()
            available = {card.id for card in cards}
            targets = [card_id for card_id in failed_ids if card_id in available]
            if not targets:
                raise ValueError("Карточки с ошибками удалены или отключены")
            record = CollectionRunRecord(status="queued", total_count=len(targets),
                                         is_full_collection=False,
                                         target_card_ids=targets, retry_of_run_id=source_run_id)
            session.add(record)
            await session.flush()
            return _run(record)

    async def cards_for_run(self, run: CollectionRun) -> List[MarketplaceCard]:
        if run.target_card_ids is None:
            return await self.list_active_cards(run.requested_card_id)
        async with self._database.session() as session:
            records = (await session.scalars(select(MarketplaceCardRecord).where(MarketplaceCardRecord.id.in_(run.target_card_ids)))).all()
        by_id = {record.id: _card(record) for record in records}
        return [by_id[card_id] for card_id in run.target_card_ids if card_id in by_id]

    async def claim_next_run(self, worker_id: str) -> Optional[CollectionRun]:
        # The row lock is held only while changing queue state, never during Playwright I/O.
        async with self._database.session() as session, session.begin():
            statement = (
                select(CollectionRunRecord)
                .where(CollectionRunRecord.status == "queued")
                .order_by(CollectionRunRecord.started_at, CollectionRunRecord.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            record = (await session.scalar(statement))
            if record is None:
                return None
            record.status = "running"
            record.worker_id = worker_id
            record.heartbeat_at = datetime.now(timezone.utc)
            await session.flush()
            return _run(record)

    async def set_run_current(self, run_id: int, card: MarketplaceCard) -> None:
        async with self._database.session() as session, session.begin():
            record = (await session.get(CollectionRunRecord, run_id))
            if record is None:
                raise LookupError(f"Запуск не найден: {run_id}")
            record.current_card_id = card.id
            record.current_marketplace = card.marketplace
            record.current_external_id = card.external_id
            record.heartbeat_at = datetime.now(timezone.utc)

    async def update_run_progress(self, run_id: int, success_count: int, failure_count: int) -> None:
        async with self._database.session() as session, session.begin():
            record = (await session.get(CollectionRunRecord, run_id))
            if record is None:
                raise LookupError(f"Запуск не найден: {run_id}")
            record.success_count = success_count
            record.failure_count = failure_count
            record.heartbeat_at = datetime.now(timezone.utc)

    async def record_run_error(self, run_id: int, error: dict, success_count: int | None = None, failure_count: int | None = None) -> None:
        async with self._database.session() as session, session.begin():
            record = (await session.get(CollectionRunRecord, run_id, with_for_update=True))
            if record is None:
                raise LookupError(f"Запуск не найден: {run_id}")
            record.errors = [*(record.errors or []), error]
            if success_count is not None:
                record.success_count = success_count
            if failure_count is not None:
                record.failure_count = failure_count
            record.heartbeat_at = datetime.now(timezone.utc)

    async def touch_run(self, run_id: int, worker_id: str) -> None:
        async with self._database.session() as session, session.begin():
            await session.execute(update(CollectionRunRecord).where(
                CollectionRunRecord.id == run_id,
                CollectionRunRecord.worker_id == worker_id,
                CollectionRunRecord.status.in_(("running", "waiting_for_user")),
            ).values(heartbeat_at=datetime.now(timezone.utc)))

    async def fail_stale_runs(self, older_than: datetime) -> int:
        async with self._database.session() as session, session.begin():
            records = (await session.scalars(select(CollectionRunRecord).where(
                CollectionRunRecord.status.in_(("running", "waiting_for_user")),
                CollectionRunRecord.worker_id.is_not(None),
                CollectionRunRecord.heartbeat_at < older_than,
            ).with_for_update(skip_locked=True))).all()
            for record in records:
                record.errors = [*(record.errors or []), {
                    "cardId": None, "marketplace": None, "externalId": None,
                    "at": datetime.now(timezone.utc).isoformat(),
                    "type": "WorkerStopped", "message": "Worker перестал отвечать",
                    "traceback": "",
                }]
                record.status = "failed"
                record.finished_at = datetime.now(timezone.utc)
                record.worker_id = None
                record.heartbeat_at = None
                record.current_card_id = None
                record.current_marketplace = None
                record.current_external_id = None
                record.challenge_type = None
                record.challenge_message = None
            return len(records)

    async def set_run_waiting(self, run_id: int, challenge_type: str, message: str) -> None:
        async with self._database.session() as session, session.begin():
            record = (await session.get(CollectionRunRecord, run_id))
            if record is None:
                raise LookupError(f"Запуск не найден: {run_id}")
            record.status = "waiting_for_user"
            record.challenge_type = challenge_type
            record.challenge_message = message
            record.heartbeat_at = datetime.now(timezone.utc)

    async def continue_run(self, run_id: int) -> Optional[CollectionRun]:
        async with self._database.session() as session, session.begin():
            record = (await session.get(CollectionRunRecord, run_id))
            if record is None:
                return None
            if record.status != "waiting_for_user":
                raise ValueError("Запуск не ожидает действий пользователя")
            record.status = "running"
            record.challenge_type = None
            record.challenge_message = None
            record.heartbeat_at = datetime.now(timezone.utc)
        return _run(record)

    async def get_run_status(self, run_id: int) -> Optional[str]:
        async with self._database.session() as session:
            return (await session.scalar(
                select(CollectionRunRecord.status).where(CollectionRunRecord.id == run_id)
            ))

    async def finish_run(self, run_id: int, status: str, success_count: int, failure_count: int) -> None:
        async with self._database.session() as session, session.begin():
            record = (await session.get(CollectionRunRecord, run_id))
            if record is None:
                raise LookupError(f"Запуск не найден: {run_id}")
            record.status = status
            record.success_count = success_count
            record.failure_count = failure_count
            record.finished_at = datetime.now(timezone.utc)
            record.current_card_id = None
            record.current_marketplace = None
            record.current_external_id = None
            record.challenge_type = None
            record.challenge_message = None
            record.worker_id = None
            record.heartbeat_at = None

    async def get_run(self, run_id: int) -> Optional[CollectionRun]:
        async with self._database.session() as session:
            record = (await session.get(CollectionRunRecord, run_id))
            return _run(record) if record else None

    async def list_runs(self, page: int = 1, page_size: int = 50) -> List[CollectionRun]:
        statement = (
            select(CollectionRunRecord)
            .order_by(CollectionRunRecord.started_at.desc(), CollectionRunRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        async with self._database.session() as session:
            return [_run(record) for record in (await session.scalars(statement)).all()]

    async def get_last_run(self):
        runs = await self.list_runs(page=1, page_size=1)
        if not runs:
            return None
        record = runs[0]
        return {
            "id": record.id,
            "status": record.status,
            "started_at": record.started_at,
            "finished_at": record.finished_at,
            "total_count": record.total_count,
            "success_count": record.success_count,
            "failure_count": record.failure_count,
        }
