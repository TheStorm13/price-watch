"""Run under a private D-Bus/Xvfb session. All services and data belong to this test."""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
bus_lines=subprocess.check_output(['dbus-daemon','--config-file=/usr/share/defaults/at-spi2/accessibility.conf','--fork','--print-address=1','--print-pid=1'],text=True).splitlines()
os.environ['AT_SPI_BUS_ADDRESS']=bus_lines[0]
os.environ['DBUS_SESSION_BUS_ADDRESS']=bus_lines[0]
print('private bus ready',flush=True)
registry=subprocess.Popen(['/usr/lib/at-spi2-registryd'], env={**os.environ,'DBUS_SESSION_BUS_ADDRESS':bus_lines[0]})
import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi

repo = Path(__file__).resolve().parents[1]
root = Path(tempfile.mkdtemp(prefix='pw-rel-native-'))
project = root/'project'
project.mkdir()
(project/'.venv').symlink_to(repo/'.venv')
wrapper = '''
import asyncio,os,sys
from decimal import Decimal
from pathlib import Path
sys.path.insert(0, REPO)
from price_watch import cli
from price_watch.bootstrap import create_postgres_stores
from price_watch.infrastructure.postgres import Database,AsyncDatabase,MigrationRunner
from marketplace_connector import ProductRef,MarketplaceCard,Availability
from contextlib import asynccontextmanager
if sys.argv[1]=='api':
    with Database(os.environ['DATABASE_URL']) as db:
        MigrationRunner(db).apply()
    async def seed():
        db=await AsyncDatabase(os.environ['DATABASE_URL']).open()
        repo=create_postgres_stores(db)
        if not await repo.cards.list_collection_cards():
            await repo.cards.add_card('ozon','123',title='Изолированный тест REL')
            if os.environ.get('PRICE_SMOKE_ALI'):
                await repo.cards.add_card('aliexpress','1005009868651525:12000061135122688',title='Изолированный Ali SKU')
        await db.close()
    asyncio.run(seed())
if sys.argv[1]=='worker':
    class FakeClient:
        def __init__(self,**kwargs): pass
    class FakeConnector:
        marketplace='ozon'
        def __init__(self,client): pass
        @asynccontextmanager
        async def collection_session(self):
            marker=Path(os.environ['PRICE_REL_SMOKE_MARKER'])
            if not marker.exists():
                marker.write_text('failed once')
                raise RuntimeError('Synthetic browser startup failure')
            yield
        async def get_product(self,external_id):
            return MarketplaceCard(ref=ProductRef(self.marketplace,external_id),title='Synthetic',url='',
                price=Decimal('77648.00' if self.marketplace=='aliexpress' else '100.10'),availability=Availability.IN_STOCK)
    from marketplace_connector.connectors import builder
    builder.AsyncOzonClient=FakeClient
    builder.OzonConnector=FakeConnector
    class FakeAliConnector(FakeConnector):
        marketplace='aliexpress'
    builder.AsyncAliExpressClient=FakeClient
    builder.AliExpressConnector=FakeAliConnector
raise SystemExit(cli.main())
'''.replace('REPO', repr(str(repo)))
(project/'main.py').write_text(wrapper)
env = os.environ.copy()
for name, directory in [('XDG_DATA_HOME','data'),('XDG_CONFIG_HOME','config'),('XDG_STATE_HOME','state'),('XDG_RUNTIME_DIR','runtime')]:
    path = root/directory
    path.mkdir(mode=0o700)
    env[name] = str(path)
env.update(PRICE_WATCH_PROJECT_DIR=str(project), PRICE_REL_SMOKE_MARKER=str(root/'failed-once'),
           NO_AT_BRIDGE='0', GTK_A11Y='always', WEBKIT_DISABLE_COMPOSITING_MODE='1')
log = (root/'desktop.log').open('w')
process = subprocess.Popen([str(repo/'frontend/src-tauri/target/release/price-watch')],
    env=env, stdout=log, stderr=log, start_new_session=True)


def nodes():
    result=[]
    def visit(node, depth=0):
        if depth>30: return
        try:
            name=node.get_name()
            if name: result.append((name,node))
            for i in range(node.get_child_count()): visit(node.get_child_at_index(i),depth+1)
        except Exception: pass
    visit(Atspi.get_desktop(0))
    return result


def wait_for(predicate, timeout=50):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if process.poll() is not None:
            raise RuntimeError('Desktop exited: '+(root/'desktop.log').read_text()[-3000:])
        current=nodes()
        value=predicate(current)
        if value: return value
        time.sleep(.2)
    raise RuntimeError('UI timeout: '+repr([name for name,_ in nodes()])[-5000:]+' log='+str(root/'desktop.log'))


def api_process():
    for path in Path('/proc').iterdir():
        if not path.name.isdigit(): continue
        try:
            status=(path/'status').read_text()
            ppid=int(next(line.split()[1] for line in status.splitlines() if line.startswith('PPid:')))
            args=(path/'cmdline').read_bytes().decode().split('\0')
            if ppid==process.pid and 'api' in args: return int(path.name),args
        except (OSError,StopIteration): pass

def api_pid():
    found=api_process()
    return found[0] if found else None

def wait_price():
    from urllib.request import urlopen, Request
    end=time.monotonic()+40
    while time.monotonic()<end:
        try:
            pid,args=api_process()
            api_environment=dict(item.split("=",1) for item in Path(f"/proc/{pid}/environ").read_bytes().decode().split("\0") if "=" in item)
            port=args[args.index('--port')+1]
            request=Request('http://127.0.0.1:'+port+'/api/catalog',headers={'X-Price-Watch-Token':api_environment['PRICE_WATCH_API_TOKEN']})
            with urlopen(request,timeout=1) as response:
                catalog=json.load(response)
            prices={card['marketplace']:card['currentPrice'] for card in catalog['cards']}
            if prices.get('ozon')=='100.10' and (not os.environ.get('PRICE_SMOKE_ALI') or prices.get('aliexpress')=='77648.00'): return
        except Exception: pass
        time.sleep(.2)
    raise RuntimeError('Private API price timeout')


report={'root':str(root),'pid':process.pid,'checks':{}}
try:
    subprocess.run(['import','-window','root','/tmp/price-watch-rel-native-start.png'],check=True)
    button=wait_for(lambda items: next((node for name,node in items if name=='Повторить ошибки и оставшиеся'),None))
    report['checks']['run_level_failure_retry_visible']=True
    subprocess.run(['import','-window','root','/tmp/price-watch-rel-native-before.png'],check=True)
    action=button.get_action_iface()
    if not action or not action.do_action(0): raise RuntimeError('Retry action failed')
    wait_price()
    wait_for(lambda items: items and not any(name=='Состояние обновления цен' for name,_ in items))
    report['checks']['retry_saved_price_in_real_webview']=True
    old=api_pid()
    if old is None: raise RuntimeError('Private API PID not found')
    os.kill(old,signal.SIGTERM)
    end=time.monotonic()+40
    while time.monotonic()<end and api_pid() in (None,old): time.sleep(.2)
    new=api_pid()
    if new in (None,old): raise RuntimeError('API did not restart')
    wait_price()
    wait_for(lambda items: items and not any('Не удалось обновить каталог' in name for name,_ in items))
    report['checks']['api_restart_catalog_restored']=True
    subprocess.run(['import','-window','root','/tmp/price-watch-rel-native-after.png'],check=True)
    report['names']=[name for name,_ in nodes()]
    print(json.dumps(report,ensure_ascii=False),flush=True)
finally:
    try: os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError: pass
    try: process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid,signal.SIGKILL)
        process.wait()
    # The group is owned solely by this test; stop any surviving native children.
    try: os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError: pass
    log.close()
    registry.terminate()
    registry.wait(timeout=5)
    os.kill(int(bus_lines[1]),signal.SIGTERM)
