"""Forward-only WB migration on a private schema of the disposable test DB."""
import os
import unittest
from unittest.mock import patch
from alembic import command
from sqlalchemy import text
from tests.migration_support import migration_schema


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'),'requires disposable TEST_DATABASE_URL')
class WildberriesMigrationTests(unittest.TestCase):
    def seed(self,db):
        with db.engine.begin() as c:
            c.execute(text("INSERT INTO product_groups(name) VALUES ('preserved')"))
            c.execute(text("""INSERT INTO marketplace_cards(marketplace,external_id,url,title,tags,group_id,deals_enabled)
                VALUES ('wildberries','1','https://www.wildberries.ru/catalog/1/detail.aspx?size=2','keep','{tag}',1,false),
                       ('wildberries','3',NULL,'legacy','{}',NULL,true),
                       ('wildberries','4','https://www.wildberries.ru/catalog/4/detail.aspx?size=5&size=6','ambiguous','{}',NULL,true),
                       ('ozon','7',NULL,'other','{}',NULL,true)"""))
            c.execute(text("INSERT INTO collection_runs(status,total_count) VALUES ('completed',1)"))
            c.execute(text("INSERT INTO collection_run_targets(run_id,card_id,position,status) VALUES (1,1,0,'succeeded')"))
            c.execute(text("""INSERT INTO price_history(card_id,price,availability,observed_at,snapshot)
                VALUES (1,123,'in_stock',now(),'{"keep":"old-json"}'),(2,456,'in_stock',now(),'{"keep":"legacy"}')"""))

    def test_preserves_everything_except_resolved_external_id(self):
        with migration_schema('0015_aliexpress_sku') as (db,config):
            self.seed(db)
            with db.engine.connect() as c:
                before=[dict(r) for r in c.execute(text('SELECT * FROM marketplace_cards ORDER BY id')).mappings()]
                targets=c.execute(text('SELECT * FROM collection_run_targets')).all()
                history=c.execute(text('SELECT * FROM price_history ORDER BY id')).all()
            with patch('logging.config.fileConfig'):
                command.upgrade(config,'0016_wildberries_size')
            with db.engine.connect() as c:
                after=[dict(r) for r in c.execute(text('SELECT * FROM marketplace_cards ORDER BY id')).mappings()]
                self.assertEqual(c.execute(text('SELECT * FROM price_history ORDER BY id')).all(),history)
                self.assertEqual(c.execute(text('SELECT * FROM collection_run_targets')).all(),targets)
            before[0]['external_id']='1:2'
            self.assertEqual(after,before)

    def test_conflict_or_active_run_aborts_without_changes(self):
        for active in [False,True]:
            with self.subTest(active=active), migration_schema('0015_aliexpress_sku') as (db,config):
                self.seed(db)
                with db.engine.begin() as c:
                    if active:c.execute(text("INSERT INTO collection_runs(status,total_count) VALUES ('queued',0)"))
                    else:c.execute(text("INSERT INTO marketplace_cards(marketplace,external_id) VALUES ('wildberries','1:2')"))
                    before=c.execute(text('SELECT * FROM marketplace_cards ORDER BY id')).all()
                with self.assertRaises(RuntimeError), patch('logging.config.fileConfig'):
                    command.upgrade(config,'0016_wildberries_size')
                with db.engine.connect() as c:
                    self.assertEqual(c.execute(text('SELECT * FROM marketplace_cards ORDER BY id')).all(),before)
                    self.assertEqual(c.scalar(text('SELECT version_num FROM alembic_version')),'0015_aliexpress_sku')
