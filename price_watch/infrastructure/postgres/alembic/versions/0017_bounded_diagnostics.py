"""Retain a bounded diagnostic sample of the latest-created run only."""
import json
from alembic import op
import sqlalchemy as sa

revision = '0017_bounded_diagnostics'
down_revision = '0016_wildberries_size'
branch_labels = None
depends_on = None


def _sample(error):
    # Frozen normalization for this historical migration.
    result = {'cardId': error.get('cardId') if isinstance(error.get('cardId'), (int, type(None))) else None}
    shortened = False
    for key, limit in {'marketplace': 64, 'externalId': 512, 'at': 64, 'type': 128,
                       'message': 1024, 'traceback': 4096}.items():
        value = error.get(key)
        if value is None:
            result[key] = None
        else:
            data = str(value).encode('utf-8')
            shortened |= len(data) > limit
            result[key] = data[:limit].decode('utf-8', errors='ignore')
    for key in ('traceback', 'message', 'externalId', 'type', 'at', 'marketplace'):
        while len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > 6000 and result[key]:
            result[key] = result[key][:len(result[key]) // 2]
            shortened = True
    if len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > 6000:
        result['cardId'] = None
        shortened = True
    return result, shortened


def upgrade():
    c = op.get_bind()
    c.execute(sa.text('SELECT pg_advisory_xact_lock(578612391)'))
    c.execute(sa.text('SELECT pg_advisory_xact_lock(578612392)'))
    # Deployment stops services; this table lock also excludes old binaries
    # which do not yet participate in the shared diagnostic guard.
    c.execute(sa.text('LOCK TABLE collection_runs IN ACCESS EXCLUSIVE MODE'))
    if c.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM collection_runs WHERE worker_id IS NOT NULL AND status IN ('running','waiting_for_user'))")):
        raise RuntimeError('Остановите сбор и завершите активный запуск перед обновлением диагностики')
    op.add_column('collection_runs', sa.Column('diagnostics_status', sa.String(16), nullable=False, server_default='complete'))
    latest = c.execute(sa.text('SELECT id,errors FROM collection_runs ORDER BY id DESC LIMIT 1')).first()
    c.execute(sa.text("UPDATE collection_runs SET errors='[]'::jsonb, diagnostics_status='expired'"))
    if latest:
        original = latest.errors or []
        chosen = original[:20]
        general = next((e for e in reversed(original) if e.get('cardId') is None), None)
        if general is not None and len(original) > 20:
            chosen = original[:19] + [general]
        bounded = [_sample(e) for e in chosen]
        payload = [e for e, _ in bounded]
        status = 'limited' if len(original)>20 or any(short for _, short in bounded) else 'complete'
        c.execute(sa.text('UPDATE collection_runs SET errors=CAST(:e AS jsonb),diagnostics_status=:s WHERE id=:id'),
                  {'e':json.dumps(payload, ensure_ascii=False), 's':status, 'id':latest.id})
    op.create_index('collection_runs_diagnostics_current_idx', 'collection_runs', ['id'], postgresql_where=sa.text("diagnostics_status <> 'expired'"))
    op.create_check_constraint('run_diagnostics_status_check', 'collection_runs', "diagnostics_status IN ('complete','limited','expired')")
    op.create_check_constraint('run_diagnostics_size_check', 'collection_runs', "jsonb_array_length(errors)<=20 AND octet_length(errors::text)<=131072")


def downgrade():
    op.drop_index('collection_runs_diagnostics_current_idx', table_name='collection_runs')
    op.drop_constraint('run_diagnostics_size_check', 'collection_runs')
    op.drop_constraint('run_diagnostics_status_check', 'collection_runs')
    op.drop_column('collection_runs', 'diagnostics_status')
