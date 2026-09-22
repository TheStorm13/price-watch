"""SQLAlchemy persistence for cards, collection runs and price history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func, literal_column, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from marketplace_connector.domain.models import ProductSnapshot
from marketplace_connector.serialization.product_json import snapshot_to_dict

from ...domain.models import (
    CardOverview,
    CollectionRun,
    MarketplaceCard,
    PriceHistoryPoint,
    PriceStatistics,
)
from .database import Database
from .models import CollectionRunRecord, MarketplaceCardRecord, PriceHistoryRecord


def _card(record: MarketplaceCardRecord) -> MarketplaceCard:
    return MarketplaceCard(
        id=record.id,
        marketplace=record.marketplace,
        external_id=record.external_id,
        title=record.title,
        url=record.url,
        is_active=record.is_active,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _run(record: CollectionRunRecord) -> CollectionRun:
    return CollectionRun(
        id=record.id,
        status=record.status,
        total_count=record.total_count,
        success_count=record.success_count,
        failure_count=record.failure_count,
        requested_card_id=record.requested_card_id,
        current_card_id=record.current_card_id,
        current_marketplace=record.current_marketplace,
        current_external_id=record.current_external_id,
        challenge_type=record.challenge_type,
        challenge_message=record.challenge_message,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


class CardAlreadyExists(ValueError):
    pass


class PostgresPriceAnalyzerRepository:
    def __init__(self, database: Database):
        self._database = database

    def add_card(
        self,
        marketplace: str,
        external_id: str,
        title: Optional[str] = None,
        url: Optional[str] = None,
    ) -> MarketplaceCard:
        marketplace = marketplace.strip().lower()
        external_id = external_id.strip()
        if not marketplace or not external_id:
            raise ValueError("marketplace и external_id обязательны")
        record = MarketplaceCardRecord(
            marketplace=marketplace,
            external_id=external_id,
            title=title,
            url=url,
        )
        try:
            with self._database.session() as session, session.begin():
                session.add(record)
                session.flush()
        except IntegrityError as exc:
            raise CardAlreadyExists("Такая карточка уже добавлена") from exc
        return _card(record)

    def update_card(
        self,
        card_id: int,
        *,
        title: Optional[str] = None,
        url: Optional[str] = None,
        is_active: Optional[bool] = None,
        update_title: bool = False,
        update_url: bool = False,
    ) -> Optional[MarketplaceCard]:
        with self._database.session() as session, session.begin():
            record = session.get(MarketplaceCardRecord, card_id)
            if record is None:
                return None
            if update_title:
                record.title = title
            if update_url:
                record.url = url
            if is_active is not None:
                record.is_active = is_active
            record.updated_at = datetime.now(timezone.utc)
        return _card(record)

    def delete_card(self, card_id: int) -> bool:
        with self._database.session() as session, session.begin():
            record = session.get(MarketplaceCardRecord, card_id)
            if record is None:
                return False
            session.delete(record)
        return True

    def _overview_statement(self):
        latest_id = (
            select(PriceHistoryRecord.id)
            .where(PriceHistoryRecord.card_id == MarketplaceCardRecord.id)
            .order_by(PriceHistoryRecord.observed_at.desc())
            .limit(1)
            .correlate(MarketplaceCardRecord)
            .scalar_subquery()
        )
        latest = aliased(PriceHistoryRecord)
        return select(MarketplaceCardRecord, latest).outerjoin(latest, latest.id == latest_id)

    def list_cards(self, include_inactive: bool = False) -> List[CardOverview]:
        statement = self._overview_statement()
        if not include_inactive:
            statement = statement.where(MarketplaceCardRecord.is_active.is_(True))
        statement = statement.order_by(MarketplaceCardRecord.is_active.desc(), MarketplaceCardRecord.id)
        with self._database.session() as session:
            rows = session.execute(statement).all()
        return [
            CardOverview(
                card=_card(card),
                current_price=latest.price if latest else None,
                current_availability=latest.availability if latest else None,
                last_observed_at=latest.observed_at if latest else None,
            )
            for card, latest in rows
        ]

    def get_card(self, card_id: int) -> Optional[CardOverview]:
        with self._database.session() as session:
            row = session.execute(
                self._overview_statement().where(MarketplaceCardRecord.id == card_id)
            ).first()
        if row is None:
            return None
        card, latest = row
        return CardOverview(
            card=_card(card),
            current_price=latest.price if latest else None,
            current_availability=latest.availability if latest else None,
            last_observed_at=latest.observed_at if latest else None,
        )

    def list_active_cards(self, card_id: Optional[int] = None) -> List[MarketplaceCard]:
        statement = select(MarketplaceCardRecord).where(MarketplaceCardRecord.is_active.is_(True))
        if card_id is not None:
            statement = statement.where(MarketplaceCardRecord.id == card_id)
        statement = statement.order_by(MarketplaceCardRecord.marketplace, MarketplaceCardRecord.id)
        with self._database.session() as session:
            records = session.scalars(statement).all()
        return [_card(record) for record in records]

    def start_run(self, total_count: int) -> int:
        record = CollectionRunRecord(status="running", total_count=total_count)
        with self._database.session() as session, session.begin():
            session.add(record)
            session.flush()
        return record.id

    def create_queued_run(self, card_id: Optional[int] = None) -> CollectionRun:
        cards = self.list_active_cards(card_id)
        if card_id is not None and not cards:
            raise LookupError(f"Активная карточка не найдена: {card_id}")
        record = CollectionRunRecord(
            status="queued",
            total_count=len(cards),
            requested_card_id=card_id,
        )
        with self._database.session() as session, session.begin():
            session.add(record)
            session.flush()
        return _run(record)

    def claim_next_run(self, worker_id: str) -> Optional[CollectionRun]:
        # The row lock is held only while changing queue state, never during Playwright I/O.
        with self._database.session() as session, session.begin():
            statement = (
                select(CollectionRunRecord)
                .where(CollectionRunRecord.status == "queued")
                .order_by(CollectionRunRecord.started_at, CollectionRunRecord.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            record = session.scalar(statement)
            if record is None:
                return None
            record.status = "running"
            record.worker_id = worker_id
            record.heartbeat_at = datetime.now(timezone.utc)
            session.flush()
            return _run(record)

    def set_run_current(self, run_id: int, card: MarketplaceCard) -> None:
        with self._database.session() as session, session.begin():
            record = session.get(CollectionRunRecord, run_id)
            if record is None:
                raise LookupError(f"Запуск не найден: {run_id}")
            record.current_card_id = card.id
            record.current_marketplace = card.marketplace
            record.current_external_id = card.external_id
            record.heartbeat_at = datetime.now(timezone.utc)

    def update_run_progress(self, run_id: int, success_count: int, failure_count: int) -> None:
        with self._database.session() as session, session.begin():
            record = session.get(CollectionRunRecord, run_id)
            if record is None:
                raise LookupError(f"Запуск не найден: {run_id}")
            record.success_count = success_count
            record.failure_count = failure_count
            record.heartbeat_at = datetime.now(timezone.utc)

    def set_run_waiting(self, run_id: int, challenge_type: str, message: str) -> None:
        with self._database.session() as session, session.begin():
            record = session.get(CollectionRunRecord, run_id)
            if record is None:
                raise LookupError(f"Запуск не найден: {run_id}")
            record.status = "waiting_for_user"
            record.challenge_type = challenge_type
            record.challenge_message = message
            record.heartbeat_at = datetime.now(timezone.utc)

    def continue_run(self, run_id: int) -> Optional[CollectionRun]:
        with self._database.session() as session, session.begin():
            record = session.get(CollectionRunRecord, run_id)
            if record is None:
                return None
            if record.status != "waiting_for_user":
                raise ValueError("Запуск не ожидает действий пользователя")
            record.status = "running"
            record.challenge_type = None
            record.challenge_message = None
            record.heartbeat_at = datetime.now(timezone.utc)
        return _run(record)

    def get_run_status(self, run_id: int) -> Optional[str]:
        with self._database.session() as session:
            return session.scalar(
                select(CollectionRunRecord.status).where(CollectionRunRecord.id == run_id)
            )

    def save_observation(self, card: MarketplaceCard, run_id: int, snapshot: ProductSnapshot) -> None:
        price = Decimal(str(snapshot.price)) if snapshot.price is not None else None
        with self._database.session() as session, session.begin():
            card_record = session.get(MarketplaceCardRecord, card.id)
            if card_record is None:
                raise LookupError(f"Карточка не найдена: {card.id}")
            card_record.title = snapshot.title
            card_record.url = snapshot.url or None
            card_record.updated_at = datetime.now(timezone.utc)
            session.add(
                PriceHistoryRecord(
                    card_id=card.id,
                    collection_run_id=run_id,
                    price=price,
                    availability=snapshot.availability.value,
                    observed_at=snapshot.collected_at,
                    snapshot=snapshot_to_dict(snapshot),
                )
            )

    def finish_run(self, run_id: int, status: str, success_count: int, failure_count: int) -> None:
        with self._database.session() as session, session.begin():
            record = session.get(CollectionRunRecord, run_id)
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

    @staticmethod
    def _cutoff(days: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=days)

    def get_history(
        self, card_id: int, days: int, page: int = 1, page_size: int = 50
    ) -> List[PriceHistoryPoint]:
        if days <= 0 or page <= 0 or not 1 <= page_size <= 200:
            raise ValueError("Некорректные параметры истории")
        statement = (
            select(PriceHistoryRecord)
            .where(
                PriceHistoryRecord.card_id == card_id,
                PriceHistoryRecord.observed_at >= self._cutoff(days),
            )
            .order_by(PriceHistoryRecord.observed_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        with self._database.session() as session:
            records = session.scalars(statement).all()
        return [
            PriceHistoryPoint(
                id=record.id,
                card_id=record.card_id,
                collection_run_id=record.collection_run_id,
                price=record.price,
                availability=record.availability,
                observed_at=record.observed_at,
            )
            for record in records
        ]

    def count_history(self, card_id: int, days: int) -> int:
        with self._database.session() as session:
            return int(session.scalar(
                select(func.count()).select_from(PriceHistoryRecord).where(
                    PriceHistoryRecord.card_id == card_id,
                    PriceHistoryRecord.observed_at >= self._cutoff(days),
                )
            ) or 0)

    def get_statistics(self, card_id: int, days: int) -> PriceStatistics:
        if days <= 0:
            raise ValueError("days должен быть положительным")
        observed_day = func.date_trunc(
            literal_column("'day'"), PriceHistoryRecord.observed_at
        )
        daily = (
            select(
                observed_day.label("observed_day"),
                func.avg(PriceHistoryRecord.price).label("daily_average"),
                func.min(PriceHistoryRecord.price).label("daily_minimum"),
                func.max(PriceHistoryRecord.price).label("daily_maximum"),
                func.count().label("observations_count"),
            )
            .where(
                PriceHistoryRecord.card_id == card_id,
                PriceHistoryRecord.observed_at >= self._cutoff(days),
                PriceHistoryRecord.availability == "in_stock",
                PriceHistoryRecord.price.is_not(None),
            )
            .group_by(observed_day)
            .subquery()
        )
        with self._database.session() as session:
            row = session.execute(select(
                func.avg(daily.c.daily_average),
                func.min(daily.c.daily_minimum),
                func.max(daily.c.daily_maximum),
                func.coalesce(func.sum(daily.c.observations_count), 0),
                func.count(),
            )).one()
        return PriceStatistics(
            card_id=card_id,
            days=days,
            average_price=row[0],
            minimum_price=row[1],
            maximum_price=row[2],
            observations_count=int(row[3]),
            observed_days=int(row[4]),
        )

    def get_run(self, run_id: int) -> Optional[CollectionRun]:
        with self._database.session() as session:
            record = session.get(CollectionRunRecord, run_id)
            return _run(record) if record else None

    def list_runs(self, page: int = 1, page_size: int = 50) -> List[CollectionRun]:
        statement = (
            select(CollectionRunRecord)
            .order_by(CollectionRunRecord.started_at.desc(), CollectionRunRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        with self._database.session() as session:
            return [_run(record) for record in session.scalars(statement).all()]

    def get_last_run(self):
        runs = self.list_runs(page=1, page_size=1)
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
