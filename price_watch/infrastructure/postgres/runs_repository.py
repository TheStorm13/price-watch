"""Durable targets, owned execution, recovery and retries."""
from dataclasses import replace
from datetime import datetime
import json
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.orm import undefer
from ...domain.diagnostics import bounded_error, MAX_ERRORS

from ...domain.models import RunLease, LeaseLost, TrackedCard
from ...domain.collection_policy import CollectionPolicy
from ...domain.errors import ConnectorNotAvailable, NoCards
from ...ports.runs import Clock
from marketplace_connector.domain.models import MarketplaceCard
from marketplace_connector.serialization.product_json import card_to_dict
from .database import AsyncDatabase
from .queries import overview_statement
from ...domain.marketplaces import PENDING_CONNECTOR_MARKETPLACES
from .models import CollectionRunRecord, CollectionRunTargetRecord, MarketplaceCardRecord, PriceHistoryRecord
from .repository_common import _RUN_CREATION_LOCK, _tracked_card, _run

_DIAGNOSTIC_LOCK = text('SELECT pg_advisory_xact_lock_shared(578612392)')
_DIAGNOSTIC_CREATION_LOCK = text('SELECT pg_advisory_xact_lock(578612392)')
ACTIVE = ('running', 'waiting_for_user')
RETRY_STATUSES = ('failed', 'pending', 'unknown')


class RunRepository:
    def __init__(self, database: AsyncDatabase, policy: CollectionPolicy, clock: Clock):
        self._database = database
        self._policy = policy
        self._clock = clock

    async def save_result(self, lease, card: TrackedCard, snapshot: MarketplaceCard) -> None:
        price = snapshot.price
        availability = snapshot.availability.value
        async with self._database.session() as session, session.begin():
            if not await self._begin_result(session, lease, card.id, 'succeeded'):
                return
            if (snapshot.ref.marketplace, snapshot.ref.external_id) != (card.ref.marketplace, card.ref.external_id):
                raise ValueError("Коннектор вернул другую карточку")
            # Browser I/O finished before taking run -> target -> card locks.
            row = (await session.execute(overview_statement().where(
                MarketplaceCardRecord.id == card.id).with_for_update(of=MarketplaceCardRecord))).first()
            if row is None:
                raise LookupError(f"Карточка не найдена: {card.id}")
            card_record, latest = row
            if not card_record.title or not card_record.title.strip():
                card_record.title = snapshot.title
            if snapshot.url:
                card_record.url = snapshot.url
            card_record.image_url = snapshot.image_url or card_record.image_url
            card_record.updated_at = self._clock()
            if latest is not None and (latest.price, latest.availability) == (price, availability):
                return
            session.add(
                PriceHistoryRecord(
                    card_id=card.id,
                    collection_run_id=lease.run_id,
                    price=price,
                    availability=availability,
                    observed_at=snapshot.collected_at,
                    snapshot=card_to_dict(snapshot),
                )
            )

    async def _create_run(self, session, cards, *, card_id=None, full=False, owner=None, retry_of=None, now=None):
        await session.execute(_DIAGNOSTIC_CREATION_LOCK)
        # All creators already own the exclusive creation lock. Expiry and the
        # new record commit together; old writers take its shared counterpart.
        await session.execute(text("UPDATE collection_runs SET errors='[]'::jsonb, diagnostics_status='expired' WHERE diagnostics_status <> 'expired'"))
        record = CollectionRunRecord(status='running' if owner else 'queued', total_count=len(cards),
            requested_card_id=card_id, is_full_collection=full, retry_of_run_id=retry_of,
            worker_id=owner, heartbeat_at=self._clock() if owner else None,
            targets_complete=True, started_at=now or self._clock())
        session.add(record)
        await session.flush()
        session.add_all([CollectionRunTargetRecord(run_id=record.id, card_id=c.id, position=i)
                         for i, c in enumerate(cards)])
        await session.flush()
        return _run(record)

    async def _select_targets(self, session, card_id=None):
        query = select(MarketplaceCardRecord)
        if card_id is not None:
            query = query.where(MarketplaceCardRecord.id == card_id)
        else:
            query = query.where(MarketplaceCardRecord.marketplace.notin_(PENDING_CONNECTOR_MARKETPLACES))
        cards = (await session.scalars(query.order_by(MarketplaceCardRecord.marketplace, MarketplaceCardRecord.id)
                                      .with_for_update(read=True))).all()
        if not cards:
            if card_id is not None:
                raise LookupError(f'Карточка не найдена: {card_id}')
            raise NoCards('Нет карточек для сбора')
        if any(c.marketplace in PENDING_CONNECTOR_MARKETPLACES for c in cards):
            raise ConnectorNotAvailable('Для этого маркетплейса коннектор ещё не подключён')
        return cards

    async def create_queued_run(self, card_id=None):
        async with self._database.session() as s, s.begin():
            await s.execute(_RUN_CREATION_LOCK)
            await s.execute(_DIAGNOSTIC_CREATION_LOCK)
            return await self._create_run(s, await self._select_targets(s, card_id), card_id=card_id, full=card_id is None)

    async def start_direct_run(self, card_id=None):
        await self.fail_stale_runs()
        async with self._database.session() as s, s.begin():
            await s.execute(_RUN_CREATION_LOCK)
            await s.execute(_DIAGNOSTIC_CREATION_LOCK)
            return await self._create_run(s, await self._select_targets(s, card_id), card_id=card_id,
                                          full=card_id is None, owner=uuid4().hex)

    async def create_due_run(self, now=None):
        async with self._database.session() as s, s.begin():
            await s.execute(_RUN_CREATION_LOCK)
            await s.execute(_DIAGNOSTIC_CREATION_LOCK)
            now = now or self._clock()
            if await s.scalar(select(CollectionRunRecord.id).where(
                CollectionRunRecord.status.in_(('queued', *ACTIVE))).limit(1)) is not None:
                return None
            last = await s.scalar(select(func.max(CollectionRunRecord.started_at)).where(
                CollectionRunRecord.is_full_collection.is_(True)))
            if not self._policy.full_collection_due(now=now, last_started_at=last, has_active=False):
                return None
            try:
                cards = await self._select_targets(s)
            except NoCards:
                return None
            return await self._create_run(s, cards, full=True, now=now)

    def _retry_targets(self, source_id):
        return select(MarketplaceCardRecord).join(CollectionRunTargetRecord,
            CollectionRunTargetRecord.card_id == MarketplaceCardRecord.id).where(
            CollectionRunTargetRecord.run_id == source_id,
            CollectionRunTargetRecord.status.in_(RETRY_STATUSES),
            MarketplaceCardRecord.marketplace.notin_(PENDING_CONNECTOR_MARKETPLACES))

    async def create_retry_run(self, source_run_id):
        async with self._database.session() as s, s.begin():
            await s.execute(_RUN_CREATION_LOCK)
            await s.execute(_DIAGNOSTIC_CREATION_LOCK)
            source = await s.get(CollectionRunRecord, source_run_id, with_for_update=True)
            if source is None:
                raise LookupError('Запуск не найден')
            if source.status not in ('failed', 'completed_with_errors'):
                raise ValueError('Повтор доступен только после завершения с ошибками')
            if await s.scalar(select(CollectionRunRecord.id).where(CollectionRunRecord.retry_of_run_id == source_run_id).limit(1)):
                raise ValueError('Повтор для этого запуска уже создан')
            cards = (await s.scalars(self._retry_targets(source_run_id).order_by(CollectionRunTargetRecord.position)
                                    .with_for_update(read=True, of=MarketplaceCardRecord))).all()
            if not cards:
                raise ValueError('Нет доступных карточек для повтора')
            return await self._create_run(s, cards, retry_of=source_run_id)

    async def cards_for_run(self, run_id):
        async with self._database.session() as s:
            records = (await s.scalars(select(MarketplaceCardRecord).join(CollectionRunTargetRecord,
                CollectionRunTargetRecord.card_id == MarketplaceCardRecord.id).where(
                CollectionRunTargetRecord.run_id == run_id,
                MarketplaceCardRecord.marketplace.notin_(PENDING_CONNECTOR_MARKETPLACES))
                .order_by(CollectionRunTargetRecord.position))).all()
            return [_tracked_card(c) for c in records]

    async def claim_next_run(self):
        async with self._database.session() as s, s.begin():
            record = await s.scalar(select(CollectionRunRecord).where(CollectionRunRecord.status == 'queued')
                .order_by(CollectionRunRecord.started_at, CollectionRunRecord.id).with_for_update(skip_locked=True).limit(1))
            if record is None:
                return None
            record.status = 'running'
            record.worker_id = uuid4().hex
            record.heartbeat_at = self._clock()
            await s.flush()
            return _run(record)

    async def _locked_run(self, session, lease: RunLease):
        record = await session.get(CollectionRunRecord, lease.run_id, with_for_update=True)
        if record is None or record.status not in ACTIVE or record.worker_id != lease.owner_token:
            raise LeaseLost(f'Владение запуском {lease.run_id} потеряно')
        record.heartbeat_at = self._clock()
        return record

    async def set_run_current(self, lease, card):
        async with self._database.session() as s, s.begin():
            record = await self._locked_run(s, lease)
            target = await s.get(CollectionRunTargetRecord, (lease.run_id, card.id))
            if target is None:
                raise ValueError('Карточка не входит в запуск')
            record.current_card_id, record.current_marketplace, record.current_external_id = card.id, card.ref.marketplace, card.ref.external_id

    async def _begin_result(self, session, lease, card_id, status, error=None):
        # Creation locks cards before expiring the old run; all result writers
        # take the shared guard first to keep that path out of run/card deadlocks.
        await session.execute(_DIAGNOSTIC_LOCK)
        # Lock order is explicit: shared creation guard, owned run -> pending target -> card (in save_result).
        # Updating target, counters and heartbeat together avoids extra round trips.
        row = (await session.execute(text("""
            WITH owned AS MATERIALIZED (
                SELECT id FROM collection_runs WHERE id=:run_id AND worker_id=:owner
                  AND status IN ('running','waiting_for_user') FOR UPDATE
            ), changed AS (
                UPDATE collection_run_targets SET status=:status
                WHERE run_id=(SELECT id FROM owned) AND card_id=:card_id AND status='pending'
                RETURNING card_id
            ), progress AS (
                UPDATE collection_runs SET heartbeat_at=now(),
                  success_count=success_count+CASE WHEN :status='succeeded' THEN (SELECT count(*) FROM changed) ELSE 0 END,
                  failure_count=failure_count+CASE WHEN :status='failed' THEN (SELECT count(*) FROM changed) ELSE 0 END
                WHERE id=(SELECT id FROM owned) RETURNING id
            )
            SELECT EXISTS(SELECT 1 FROM owned) AS owned,
                   EXISTS(SELECT 1 FROM changed) AS changed,
                   EXISTS(SELECT 1 FROM collection_run_targets WHERE run_id=:run_id AND card_id=:card_id) AS target_exists
        """), {'run_id': lease.run_id, 'owner': lease.owner_token, 'card_id': card_id,
                'status': status})).one()
        if not row.owned:
            raise LeaseLost(f'Владение запуском {lease.run_id} потеряно')
        if not row.target_exists:
            raise ValueError('Карточка не входит в запуск')
        if row.changed and error is not None:
            await self._append_error(session, lease.run_id, error)
        return row.changed

    async def _append_error(self, session, run_id, error, *, general=False):
        payload, shortened = bounded_error(error)
        await session.execute(text("""
            UPDATE collection_runs SET
              errors=CASE
                WHEN jsonb_array_length(errors)<:max_errors THEN errors || CAST(:error AS jsonb)
                WHEN :general THEN (SELECT coalesce(jsonb_agg(value ORDER BY ord), '[]'::jsonb)
                  FROM jsonb_array_elements(errors) WITH ORDINALITY AS e(value,ord) WHERE ord<=:reserved) || CAST(:error AS jsonb)
                ELSE errors END,
              diagnostics_status=CASE WHEN :shortened OR jsonb_array_length(errors)>=:max_errors
                OR diagnostics_status='limited' THEN 'limited' ELSE 'complete' END
            WHERE id=:run_id AND diagnostics_status<>'expired'
              AND (diagnostics_status<>'limited' OR jsonb_array_length(errors)<:max_errors OR :general)
        """), {'run_id': run_id, 'error': json.dumps([payload], ensure_ascii=False),
                 'shortened': shortened, 'general': general, 'max_errors': MAX_ERRORS, 'reserved': MAX_ERRORS-1})

    async def record_card_error(self, lease, card, error):
        async with self._database.session() as s, s.begin():
            await self._begin_result(s, lease, card.id, 'failed', error)

    async def touch_run(self, lease):
        try:
            async with self._database.session() as s, s.begin():
                await self._locked_run(s, lease)
            return True
        except LeaseLost:
            return False

    def _finish(self, record, status):
        record.status = status
        record.finished_at = self._clock()
        record.current_card_id = record.current_marketplace = record.current_external_id = None
        record.challenge_type = record.challenge_message = None
        record.worker_id = record.heartbeat_at = None

    async def fail_stale_runs(self, older_than: datetime | None = None):
        older_than = older_than if older_than is not None else self._policy.stale_cutoff(self._clock())
        async with self._database.session() as s, s.begin():
            await s.execute(_DIAGNOSTIC_LOCK)
            rows = (await s.scalars(select(CollectionRunRecord).where(CollectionRunRecord.status.in_(ACTIVE),
                func.coalesce(CollectionRunRecord.heartbeat_at, CollectionRunRecord.started_at) < older_than)
                .with_for_update(skip_locked=True))).all()
            for record in rows:
                if record.diagnostics_status != 'expired':
                    await self._append_error(s, record.id, {'cardId': None, 'marketplace': None, 'externalId': None,
                        'at': self._clock().isoformat(), 'type': 'WorkerStopped',
                        'message': 'Исполнитель перестал отвечать', 'traceback': ''}, general=True)
                self._finish(record, 'failed')
            return len(rows)

    async def set_run_waiting(self, lease, challenge_type, message):
        async with self._database.session() as s, s.begin():
            record = await self._locked_run(s, lease)
            record.status, record.challenge_type, record.challenge_message = 'waiting_for_user', challenge_type, message

    async def continue_run(self, run_id):
        async with self._database.session() as s, s.begin():
            record = await s.get(CollectionRunRecord, run_id, with_for_update=True)
            if record is None:
                return None
            if (record.status != 'waiting_for_user' or not record.worker_id or
                not record.heartbeat_at or self._policy.is_stale(now=self._clock(),
                    heartbeat_at=record.heartbeat_at, started_at=record.started_at)):
                raise ValueError('Запуск не ожидает действий действующего исполнителя')
            record.status, record.challenge_type, record.challenge_message = 'running', None, None
            return _run(record)

    async def get_owned_status(self, lease):
        async with self._database.session() as s, s.begin():
            return (await self._locked_run(s, lease)).status

    async def finish_run(self, lease):
        async with self._database.session() as s, s.begin():
            record = await self._locked_run(s, lease)
            if not record.targets_complete or record.success_count+record.failure_count != record.total_count:
                raise ValueError('Не все цели запуска обработаны')
            self._finish(record, 'completed_with_errors' if record.failure_count else 'completed')
            await s.flush()
            return _run(record)

    async def fail_run(self, lease, error):
        async with self._database.session() as s, s.begin():
            await s.execute(_DIAGNOSTIC_LOCK)
            record = await self._locked_run(s, lease)
            await self._append_error(s, record.id, error, general=True)
            self._finish(record, 'failed')

    async def _run_views(self, session, records, *, include_errors=False):
        ids = [r.id for r in records if r.status in ('failed', 'completed_with_errors')]
        counts = {}
        if ids:
            children = select(CollectionRunRecord.retry_of_run_id).where(CollectionRunRecord.retry_of_run_id.is_not(None))
            rows = await session.execute(select(CollectionRunTargetRecord.run_id, func.count()).join(
                MarketplaceCardRecord, MarketplaceCardRecord.id == CollectionRunTargetRecord.card_id).where(
                CollectionRunTargetRecord.run_id.in_(ids), CollectionRunTargetRecord.status.in_(RETRY_STATUSES),
                MarketplaceCardRecord.marketplace.notin_(PENDING_CONNECTOR_MARKETPLACES),
                CollectionRunTargetRecord.run_id.notin_(children)).group_by(CollectionRunTargetRecord.run_id))
            counts = dict(rows.all())
        return [replace(_run(r, errors=r.errors if include_errors else ()), retryable_count=counts.get(r.id, 0)) for r in records]

    async def get_run(self, run_id, include_errors=True):
        async with self._database.session() as s:
            statement = select(CollectionRunRecord).where(CollectionRunRecord.id == run_id)
            if include_errors:
                statement = statement.options(undefer(CollectionRunRecord.errors))
            record = await s.scalar(statement)
            return (await self._run_views(s, [record], include_errors=include_errors))[0] if record else None

    async def list_runs(self, page=1, page_size=50):
        async with self._database.session() as s:
            rows = (await s.scalars(select(CollectionRunRecord).order_by(CollectionRunRecord.started_at.desc(),
                CollectionRunRecord.id.desc()).offset((page-1)*page_size).limit(page_size))).all()
            return await self._run_views(s, rows)

    async def get_last_run(self):
        runs = await self.list_runs(page_size=1)
        if not runs:
            return None
        record = runs[0]
        return {key: getattr(record, key) for key in ('id','status','started_at','finished_at','total_count','success_count','failure_count')}
