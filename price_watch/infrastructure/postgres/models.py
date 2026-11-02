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
    ForeignKeyConstraint,
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


class ProductGroupRecord(Base):
    __tablename__ = "product_groups"
    __table_args__ = (CheckConstraint("btrim(name) <> ''", name="product_groups_name_not_blank"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MarketplaceCardRecord(Base):
    __tablename__ = "marketplace_cards"
    __table_args__ = (
        ForeignKeyConstraint(["id", "primary_variant_id"], ["card_variants.card_id", "card_variants.id"], name="card_primary_variant_owner_fk", deferrable=True, initially="DEFERRED", use_alter=True),
        UniqueConstraint("marketplace", "external_id", name="marketplace_cards_marketplace_external_unique"),
        CheckConstraint("btrim(marketplace) <> ''", name="marketplace_cards_marketplace_not_blank"),
        CheckConstraint("btrim(external_id) <> ''", name="marketplace_cards_external_id_not_blank"),
        CheckConstraint("cardinality(tags) <= 2", name="marketplace_cards_tags_limit"),
        Index(
            "marketplace_cards_deals_enabled_idx",
            "marketplace",
            "id",
            postgresql_where=text("deals_enabled = true"),
        ),
    )

    primary_variant_id: Mapped[int | None] = mapped_column(BigInteger)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    marketplace: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))
    group_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("product_groups.id", ondelete="SET NULL"), index=True)
    deals_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    history: Mapped[list["PriceHistoryRecord"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CardVariantRecord(Base):
    __tablename__ = "card_variants"
    __table_args__ = (
        UniqueConstraint("card_id", "external_id", name="card_variants_identity_unique"),
        UniqueConstraint("card_id", "id", name="card_variants_owner_unique"),
        CheckConstraint("btrim(external_id) <> ''", name="card_variants_identity_not_blank"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("marketplace_cards.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    url: Mapped[str | None] = mapped_column(Text)
    options: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
        CheckConstraint("diagnostics_status IN ('complete','limited','expired')", name='run_diagnostics_status_check'),
        CheckConstraint('jsonb_array_length(errors)<=20 AND octet_length(errors::text)<=131072', name='run_diagnostics_size_check'),
        Index("collection_runs_diagnostics_current_idx", "id", postgresql_where=text("diagnostics_status <> 'expired'")),
        Index("collection_runs_requested_card_idx", "requested_card_id"),
        Index("collection_runs_current_card_idx", "current_card_id"),
        Index("collection_runs_retry_of_unique", "retry_of_run_id", unique=True,
              postgresql_where=text("retry_of_run_id is not null")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'queued'"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_full_collection: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    requested_card_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("marketplace_cards.id", ondelete="SET NULL")
    )
    retry_of_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("collection_runs.id", ondelete="SET NULL")
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
    targets_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), deferred=True, deferred_raiseload=True)
    diagnostics_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'complete'"))


class CollectionRunTargetRecord(Base):
    __tablename__ = "collection_run_targets"
    __table_args__ = (
        CheckConstraint("status in ('pending', 'succeeded', 'failed', 'unknown')", name="run_target_status_check"),
        UniqueConstraint("run_id", "position", name="run_target_position_unique"),
        Index("run_targets_card_idx", "card_id", "run_id"),
    )
    run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("collection_runs.id", ondelete="CASCADE"), primary_key=True)
    # Keep the original target identity after a card is deleted.
    card_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    variant_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'pending'"))


class PriceHistoryRecord(Base):
    __tablename__ = "price_history"
    __table_args__ = (
        ForeignKeyConstraint(["card_id", "variant_id"], ["card_variants.card_id", "card_variants.id"], name="history_variant_fk", ondelete="CASCADE"),
        CheckConstraint("price is null or price >= 0", name="price_history_price_check"),
        CheckConstraint("availability <> 'out_of_stock' or price is null",
                        name="price_history_unavailable_price_check"),
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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("marketplace_cards.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    collection_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("collection_runs.id", ondelete="SET NULL")
    )
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    availability: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    card: Mapped[MarketplaceCardRecord] = relationship(back_populates="history")
