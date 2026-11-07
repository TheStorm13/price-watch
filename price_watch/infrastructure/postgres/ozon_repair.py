"""Explicit maintenance for confirmed, pre-discovery Ozon family splits."""
from sqlalchemy import text

from .repository_common import _RUN_CREATION_LOCK
from .variant_membership import OZON_MEMBERSHIP_LOCK


def merge_ozon_cards(connection, pairs):
    """Move variants and observations before deleting empty containers.

    Caller owns a transaction and a backup. No automatic collection-time merge.
    Historical run targets retain their original identities, just as on deletion.
    """
    pairs = list(pairs)
    ids = [value for pair in pairs for value in pair]
    if not pairs or len(ids) != len(set(ids)):
        raise ValueError('Нужны непересекающиеся пары source/target')
    connection.execute(_RUN_CREATION_LOCK)
    connection.execute(OZON_MEMBERSHIP_LOCK)
    if connection.scalar(text("SELECT count(*) FROM collection_runs WHERE status IN ('queued','running','waiting_for_user')")):
        raise ValueError('Дождитесь завершения всех запусков перед исправлением')
    connection.execute(text('SET CONSTRAINTS history_variant_fk DEFERRED'))
    counts = tuple(connection.execute(text('SELECT (SELECT count(*) FROM card_variants), (SELECT count(*) FROM price_history)')).one())
    for source, target in pairs:
        rows = connection.execute(text('SELECT id,marketplace,group_id,tags,deals_enabled,primary_variant_id FROM marketplace_cards WHERE id IN (:source,:target) ORDER BY id FOR UPDATE'),
                                  dict(source=source, target=target)).mappings().all()
        by_id = {row['id']: row for row in rows}
        if len(rows) != 2 or any(row['marketplace'] != 'ozon' for row in rows):
            raise ValueError('Обе карточки должны существовать и принадлежать Ozon')
        old, kept = by_id[source], by_id[target]
        if any(old[key] != kept[key] for key in ('group_id', 'tags', 'deals_enabled')):
            raise ValueError(f'Настройки карточек {source} и {target} различаются')
        params = dict(source=source, target=target, primary=old['primary_variant_id'])
        connection.execute(text('UPDATE marketplace_cards SET primary_variant_id=NULL WHERE id=:source'), params)
        connection.execute(text('UPDATE card_variants SET card_id=:target, tracking_enabled=tracking_enabled OR id=:primary WHERE card_id=:source'), params)
        connection.execute(text('UPDATE price_history SET card_id=:target WHERE card_id=:source'), params)
        if connection.scalar(text('SELECT count(*) FROM card_variants WHERE card_id=:source'), params):
            raise RuntimeError('Карточка всё ещё содержит варианты')
        connection.execute(text('DELETE FROM marketplace_cards WHERE id=:source'), params)
    connection.execute(text('SET CONSTRAINTS history_variant_fk IMMEDIATE'))
    after = tuple(connection.execute(text('SELECT (SELECT count(*) FROM card_variants), (SELECT count(*) FROM price_history)')).one())
    if after != counts:
        raise RuntimeError(f'Изменилось число вариантов или наблюдений: {counts} -> {after}')
    return dict(variants=after[0], observations=after[1], cards_removed=len(pairs))
