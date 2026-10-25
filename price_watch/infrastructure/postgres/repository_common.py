"""Shared SQL and record-to-domain mappings."""

from __future__ import annotations

from sqlalchemy import text

from marketplace_connector.domain.models import ProductRef

from ...domain.models import CollectionRun, TrackedCard
from .models import CollectionRunRecord, MarketplaceCardRecord


_RUN_CREATION_LOCK = text("SELECT pg_advisory_xact_lock(578612391)")


def _tracked_card(record: MarketplaceCardRecord) -> TrackedCard:
    return TrackedCard(
        id=record.id,
        ref=ProductRef(record.marketplace, record.external_id),
        title=record.title,
        url=record.url,
        image_url=record.image_url,
        group_id=record.group_id,
        tags=tuple(record.tags),
        deals_enabled=record.deals_enabled,
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
        errors=tuple(record.errors or []),
        retry_of_run_id=record.retry_of_run_id,
        owner_token=record.worker_id,
        targets_complete=record.targets_complete,
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
