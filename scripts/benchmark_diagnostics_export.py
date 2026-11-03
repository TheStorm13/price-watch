"""Synthetic resource measurements in a private schema of the disposable DB."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

parser=argparse.ArgumentParser()
parser.add_argument('--source-root',default=str(Path(__file__).resolve().parents[1]))
parser.add_argument('--schema',required=True)
parser.add_argument('--case',choices=['export','errors','history'],required=True)
parser.add_argument('--size',type=int,required=True)
args=parser.parse_args()
if not args.schema.startswith('perf_') or not args.schema.replace('_','').isalnum():
    raise RuntimeError('Only a private perf_* schema is allowed')
sys.path.insert(0,args.source_root)
from sqlalchemy import text
from sqlalchemy.engine import make_url
from price_watch.infrastructure.postgres import Database, AsyncDatabase, MigrationRunner
from price_watch.bootstrap import create_postgres_stores

url=os.environ['TEST_DATABASE_URL']
with Database(url) as db:
    with db.engine.begin() as c:
        if c.scalar(text('SELECT current_database()'))!='price_watch_rel_test':
            raise RuntimeError('Only disposable price_watch_rel_test is allowed')
        c.execute(text(f'CREATE SCHEMA IF NOT EXISTS {args.schema}'))
scoped=str(make_url(Database._normalize_url(url)).update_query_dict({'options':'-csearch_path='+args.schema}))
with Database(scoped) as db:
    MigrationRunner(db).apply()


async def main():
    db=await AsyncDatabase(scoped).open()
    try:
        async with db.session() as s,s.begin():
            await s.execute(text('TRUNCATE marketplace_cards,product_groups,collection_runs RESTART IDENTITY CASCADE'))
            cards = 1 if args.case == 'history' else max(1,args.size)
            await s.execute(text("INSERT INTO product_groups(id,name) OVERRIDING SYSTEM VALUE SELECT i,'Group '||i FROM generate_series(1,:n) i"),{'n':max(1,cards//10)})
            await s.execute(text("""INSERT INTO marketplace_cards(id,marketplace,external_id,group_id,created_at,updated_at)
                OVERRIDING SYSTEM VALUE SELECT i,'ozon',i::text,CASE WHEN i%2=0 THEN (i-1)/10+1 END,
                '2026-10-01'::timestamptz,'2026-10-01'::timestamptz FROM generate_series(1,:n) i"""),{'n':cards})
            await s.execute(text("INSERT INTO card_variants(id,card_id,external_id,product_title,updated_at) SELECT id,id,external_id,'Product '||id,updated_at FROM marketplace_cards"))
            await s.execute(text("UPDATE marketplace_cards SET primary_variant_id=id"))
            if args.case=='export':
                await s.execute(text("""INSERT INTO price_history(card_id,variant_id,price,availability,observed_at,snapshot)
                    SELECT i,i,100+j%10,'in_stock','2026-10-01'::timestamptz+j*interval '1 hour',
                    jsonb_build_object('raw',repeat('x',1024))
                    FROM generate_series(1,:n) i CROSS JOIN generate_series(1,100) j"""),{'n':args.size})
            elif args.case=='history':
                await s.execute(text("""INSERT INTO price_history(card_id,variant_id,price,availability,observed_at,snapshot)
                    SELECT 1,1,CASE WHEN j%10=0 THEN NULL ELSE 100+j%10 END,
                    CASE WHEN j%10=0 THEN 'out_of_stock' ELSE 'in_stock' END,
                    '2026-10-01'::timestamptz+j*interval '1 second',jsonb_build_object('raw',repeat('x',1024))
                    FROM generate_series(1,:n) j"""),{'n':args.size})
        stores=create_postgres_stores(db)
        if args.case=='export':
            start=time.perf_counter()
            document=await stores.transfer.export_cards()
            elapsed=time.perf_counter()-start
            digest=hashlib.sha256(json.dumps(document,sort_keys=True,default=str).encode()).hexdigest()
            result={'case':'export','size':args.size,'seconds':elapsed,'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'sha256':digest}
        elif args.case=='history':
            samples=[]
            for _ in range(35):
                start=time.perf_counter()
                points=await stores.history.get_chart_points(1,3650)
                samples.append((time.perf_counter()-start)*1000)
            assert len(points)==args.size
            digest=hashlib.sha256(repr(points).encode()).hexdigest()
            result={'case':'history','size':args.size,'p95Ms':sorted(samples[5:])[28],
                'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'sha256':digest}
        else:
            run=await stores.runs.start_direct_run()
            cards=await stores.runs.cards_for_run(run.id)
            samples=[]
            for card in cards[:args.size]:
                start=time.perf_counter()
                await stores.runs.record_card_error(run.lease,card,{'cardId':card.id,'marketplace':'ozon',
                    'externalId':card.ref.external_id,'message':'Synthetic failure','traceback':'x'*512,
                    'at':'2026-10-01T00:00:00+00:00','type':'Synthetic'})
                samples.append((time.perf_counter()-start)*1000)
            reads=[]
            for _ in range(35):
                start=time.perf_counter()
                # Older code had no compact projection; its API discarded errors after reading.
                if Path(args.source_root).resolve()==Path(__file__).resolve().parents[1]:
                    await stores.runs.get_run(run.id,include_errors=False)
                else:
                    await stores.runs.get_run(run.id)
                reads.append((time.perf_counter()-start)*1000)
            async with db.session() as s:
                payload=await s.execute(text('SELECT jsonb_array_length(errors),octet_length(errors::text),failure_count FROM collection_runs WHERE id=:id'),{'id':run.id})
                count,bytes_,failures=payload.one()
            quartiles=[]
            for part in range(4):
                xs=samples[len(samples)*part//4:len(samples)*(part+1)//4]
                quartiles.append({'meanMs':sum(xs)/len(xs) if xs else 0,'p95Ms':sorted(xs)[max(0,int(len(xs)*.95)-1)] if xs else 0})
            result={'case':'errors','size':args.size,'totalMs':sum(samples),'quartiles':quartiles,
                'compactReadP95Ms':sorted(reads[5:])[28],'storedErrors':count,'storedBytes':bytes_,'failureCount':failures}
        print(json.dumps(result))
    finally:
        await db.close()

asyncio.run(main())
