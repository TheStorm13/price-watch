import json
import os
import unittest
from uuid import uuid4
from unittest.mock import patch
from alembic import command
from sqlalchemy import text
from sqlalchemy.engine import make_url
from price_watch.infrastructure.postgres import Database, MigrationRunner


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'TEST_DATABASE_URL не задан')
class DiagnosticsMigrationTests(unittest.TestCase):
    def setUp(self):
        config = patch('logging.config.fileConfig')
        config.start()
        self.addCleanup(config.stop)

    def test_latest_only_normalization_preserves_targets_counts_and_history(self):
        schema='diag_migration_'+uuid4().hex
        base=Database(os.environ['TEST_DATABASE_URL'])
        with base.engine.begin() as c: c.execute(text(f'CREATE SCHEMA {schema}'))
        scoped=make_url(base.url).update_query_dict({'options':'-csearch_path='+schema})
        db=Database(str(scoped))
        try:
            config=MigrationRunner(db)._config()
            command.upgrade(config,'0016_wildberries_size')
            with db.engine.begin() as c:
                c.execute(text("INSERT INTO marketplace_cards(marketplace,external_id) VALUES ('ozon','1')"))
                c.execute(text("INSERT INTO collection_runs(status,total_count,failure_count,errors) VALUES ('failed',1,1,'[{\"message\":\"old\"}]')"))
                errors=[{'cardId':1,'message':str(i),'traceback':'🔥'*10000} for i in range(30)]+[{'cardId':None,'message':'terminal'}]
                c.execute(text("INSERT INTO collection_runs(status,total_count,failure_count,errors) VALUES ('failed',30,30,CAST(:e AS jsonb))"),{'e':json.dumps(errors)})
                c.execute(text("INSERT INTO collection_run_targets(run_id,card_id,position,status) VALUES (1,1,0,'failed'),(2,1,0,'failed')"))
                c.execute(text("INSERT INTO price_history(card_id,price,availability,observed_at,snapshot) VALUES (1,100,'in_stock',now(),CAST(:snapshot AS jsonb))"), {'snapshot':json.dumps({'keep':1})})
                history=c.execute(text('SELECT * FROM price_history')).all()
                targets=c.execute(text('SELECT * FROM collection_run_targets ORDER BY run_id')).all()
            command.upgrade(config,'0017_bounded_diagnostics')
            with db.engine.connect() as c:
                self.assertEqual(c.execute(text('SELECT * FROM price_history')).all(),history)
                self.assertEqual(c.execute(text('SELECT * FROM collection_run_targets ORDER BY run_id')).all(),targets)
                rows=c.execute(text('SELECT id,failure_count,errors,diagnostics_status,octet_length(errors::text) FROM collection_runs ORDER BY id')).all()
                self.assertEqual((rows[0].failure_count,rows[0].errors,rows[0].diagnostics_status),(1,[],'expired'))
                self.assertEqual((rows[1].failure_count,len(rows[1].errors),rows[1].diagnostics_status),(30,20,'limited'))
                self.assertEqual(rows[1].errors[-1]['message'],'terminal')
                self.assertLessEqual(rows[1][4],128*1024)
                self.assertEqual(c.scalar(text('SELECT count(*) FROM marketplace_cards')),1)
        finally:
            db.close()
            with base.engine.begin() as c: c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
            base.close()

    def test_active_owner_rejects_upgrade_without_partial_schema_changes(self):
        schema='diag_reject_'+uuid4().hex
        base=Database(os.environ['TEST_DATABASE_URL'])
        with base.engine.begin() as c: c.execute(text(f'CREATE SCHEMA {schema}'))
        db=Database(str(make_url(base.url).update_query_dict({'options':'-csearch_path='+schema})))
        try:
            config=MigrationRunner(db)._config()
            command.upgrade(config,'0016_wildberries_size')
            with db.engine.begin() as c:
                c.execute(text("INSERT INTO collection_runs(status,worker_id,errors) VALUES ('running','owner','[{\"message\":\"keep\"}]')"))
            with self.assertRaisesRegex(RuntimeError,'Остановите сбор'): command.upgrade(config,'0017_bounded_diagnostics')
            with db.engine.connect() as c:
                self.assertEqual(c.scalar(text('SELECT version_num FROM alembic_version')),'0016_wildberries_size')
                self.assertEqual(c.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_schema=:s AND column_name='diagnostics_status'"),{'s':schema}),0)
                self.assertEqual(c.scalar(text('SELECT errors FROM collection_runs')),[{'message':'keep'}])
        finally:
            db.close()
            with base.engine.begin() as c: c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
            base.close()
