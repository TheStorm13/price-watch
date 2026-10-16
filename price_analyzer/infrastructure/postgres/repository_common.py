"""Shared SQL and record-to-domain mappings."""

from __future__ import annotations

from sqlalchemy import text

from ...domain.models import CollectionRun, MarketplaceCard
from .models import CollectionRunRecord, MarketplaceCardRecord


_RUN_CREATION_LOCK = text("SELECT pg_advisory_xact_lock(578612391)")


def _card(record: MarketplaceCardRecord) -> MarketplaceCard:
    return MarketplaceCard(
        id=record.id,
        marketplace=record.marketplace,
        external_id=record.external_id,
        title=record.title,
        url=record.url,
        image_url=record.image_url,
        group_id=record.group_id,
        tags=tuple(record.tags),
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
        target_card_ids=tuple(record.target_card_ids) if record.target_card_ids is not None else None,
        errors=tuple(record.errors or []),
        retry_of_run_id=record.retry_of_run_id,
    )


class CardAlreadyExists(ValueError):
    pass


class CardInActiveRun(ValueError):
    pass


class NoCards(ValueError):
    pass


class ConnectorNotAvailable(ValueError):
    pass


class ImportDuringRun(ValueError):
    pass
