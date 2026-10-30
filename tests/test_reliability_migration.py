"""Upgrade checks in a private schema of an explicitly disposable database."""
import os
import unittest
from uuid import uuid4
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from price_watch.infrastructure.postgres import Database, MigrationRunner


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'TEST_DATABASE_URL не задан')
class ReliabilityMigrationTests(unittest.TestCase):
    def test_upgrade_preserves_known_targets_history_errors_and_uncertainty(self):
        schema = 'rel_migration_' + uuid4().hex
        base = Database(os.environ['TEST_DATABASE_URL'])
        with base.engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA {schema}'))
        url = make_url(base.url).update_query_dict({'options': '-csearch_path='+schema})
        db = Database(str(url))
        try:
            config = MigrationRunner(db)._config()
            command.upgrade(config, '0013_deals_enabled')
            with db.engine.begin() as c:
                c.execute(text("INSERT INTO marketplace_cards(marketplace,external_id) VALUES ('ozon','1'),('ozon','2'),('ozon','3')"))
                c.execute(text("""INSERT INTO collection_runs(status,total_count,success_count,failure_count,target_card_ids,errors)
                    VALUES ('failed',3,1,1,ARRAY[1,2,3], '[{"cardId": 2,"message":"bad"}]'),
                           ('failed',4,0,0,NULL,'[{"cardId": 1,"message":"known only"}]'),
                           ('queued',2,0,0,ARRAY[2,3],'[]'),
                           ('running',1,0,0,NULL,'[]'),
                           ('failed',1,0,1,NULL,'[{"cardId": 9223372036854775807},{"cardId": 9223372036854775808}]')"""))
                c.execute(text("UPDATE collection_runs SET requested_card_id=3 WHERE id=4"))
                c.execute(text("""INSERT INTO price_history(card_id,collection_run_id,price,availability,observed_at,snapshot)
                    VALUES (1,1,100,'in_stock',now(),'{"keep":"snapshot"}')"""))
                history = c.execute(text('SELECT * FROM price_history')).all()
                errors = c.execute(text('SELECT id,errors FROM collection_runs ORDER BY id')).all()
            command.upgrade(config, '0014_run_target_results')
            with db.engine.connect() as c:
                self.assertEqual(c.execute(text('SELECT * FROM price_history')).all(), history)
                self.assertEqual(c.execute(text('SELECT id,errors FROM collection_runs ORDER BY id')).all(), errors)
                targets = c.execute(text('SELECT run_id,card_id,status FROM collection_run_targets ORDER BY run_id,position')).all()
                self.assertEqual(targets, [(1,1,'unknown'),(1,2,'failed'),(1,3,'unknown'),
                                           (2,1,'failed'),(3,2,'pending'),(3,3,'pending'),(4,3,'unknown'),
                                           (5,9223372036854775807,'failed')])
                self.assertEqual(c.execute(text('SELECT targets_complete FROM collection_runs ORDER BY id')).scalars().all(),
                                 [True, False, True, True, False])
                self.assertEqual(c.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_schema=:s AND table_name='collection_runs' AND column_name='target_card_ids'"), {'s': schema}), 0)
                self.assertEqual(c.scalar(text('SELECT count(*) FROM marketplace_cards')), 3)
        finally:
            db.close()
            with base.engine.begin() as c:
                c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
            base.close()
