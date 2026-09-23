"""SQLAlchemy persistence models; domain entities stay ORM-independent."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class MarketplaceCardRecord(Base):
    __tablename__ = "marketplace_cards"
    __table_args__ = (
        UniqueConstraint("marketplace", "external_id", name="marketplace_cards_marketplace_external_unique"),
        CheckConstraint("btrim(marketplace) <> ''", name="marketplace_cards_marketplace_not_blank"),
        CheckConstraint("btrim(external_id) <> ''", name="marketplace_cards_external_id_not_blank"),
        Index(
            "marketplace_cards_active_idx",
            "marketplace",
            "id",
            postgresql_where=text("is_active = true"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    marketplace: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    history: Mapped[list["PriceHistoryRecord"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CollectionRunRecord(Base):
    __tablename__ = "collection_runs"
    __table_args__ = (
        CheckConstraint(
            "status in ('queued', 'running', 'waiting_for_user', 'completed', 'completed_with_errors', 'failed')",
            name="collection_runs_status_check",
        ),
        CheckConstraint(
            "total_count >= 0 and success_count >= 0 and failure_count >= 0 "
            "and success_count + failure_count <= total_count",
            name="collection_runs_counts_check",
        ),
        Index(
            "collection_runs_queue_idx",
            "started_at",
            postgresql_where=text("status = 'queued'"),
        ),
        Index("collection_runs_requested_card_idx", "requested_card_id"),
        Index("collection_runs_current_card_idx", "current_card_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'queued'"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    requested_card_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("marketplace_cards.id", ondelete="SET NULL")
    )
    current_card_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("marketplace_cards.id", ondelete="SET NULL")
    )
    current_marketplace: Mapped[str | None] = mapped_column(Text)
    current_external_id: Mapped[str | None] = mapped_column(Text)
    challenge_type: Mapped[str | None] = mapped_column(String(64))
    challenge_message: Mapped[str | None] = mapped_column(Text)
    worker_id: Mapped[str | None] = mapped_column(String(128))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_card_ids: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger))
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))


class PriceHistoryRecord(Base):
    __tablename__ = "price_history"
    __table_args__ = (
        CheckConstraint("price is null or price >= 0", name="price_history_price_check"),
        CheckConstraint(
            "availability in ('in_stock', 'out_of_stock', 'unknown')",
            name="price_history_availability_check",
        ),
        Index(
            "price_history_card_observed_idx",
            "card_id",
            text("observed_at desc"),
            postgresql_include=["price", "availability"],
        ),
        Index(
            "price_history_collection_run_idx",
            "collection_run_id",
            postgresql_where=text("collection_run_id is not null"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    card_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("marketplace_cards.id", ondelete="CASCADE"), nullable=False
    )
    collection_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("collection_runs.id", ondelete="SET NULL")
    )
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    availability: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    card: Mapped[MarketplaceCardRecord] = relationship(back_populates="history")
