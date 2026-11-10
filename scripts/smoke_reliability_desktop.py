"""Run under a private D-Bus/Xvfb session. All services and data belong to this test."""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import ctypes
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
    gate=os.environ.get('PRICE_SMOKE_STARTUP_GATE')
    if gate:
        import time
        while not Path(gate).exists(): time.sleep(.1)
    if os.environ.get('PRICE_SMOKE_STARTUP_FAIL') and Path(os.environ['PRICE_SMOKE_STARTUP_FAIL']).exists():
        raise RuntimeError('Synthetic startup failure')
    with Database(os.environ['DATABASE_URL']) as db:
        MigrationRunner(db).apply()
    async def seed():
        db=await AsyncDatabase(os.environ['DATABASE_URL']).open()
        repo=create_postgres_stores(db)
        if not await repo.cards.list_collection_cards():
            if not os.environ.get('PRICE_SMOKE_ONLY_WB'):
                await repo.cards.add_card('ozon','123',title='Изолированный тест REL')
            if os.environ.get('PRICE_SMOKE_WB'):
                await repo.cards.add_card('wildberries','179224846:296499716',title='Изолированный WB размер')
            if os.environ.get('PRICE_SMOKE_ALI'):
                await repo.cards.add_card('aliexpress','1005009868651525:12000061135122688',title='Изолированный Ali SKU')
            count=int(os.environ.get('PRICE_SMOKE_CATALOG_SIZE','0'))
            if count:
                if count not in (1000,5000): raise ValueError('Unsupported smoke catalog size')
                from sqlalchemy import text
                async with db.session() as session,session.begin():
                    await session.execute(text("""INSERT INTO marketplace_cards(marketplace,external_id)
                        SELECT 'yandex-market',i::text
                        FROM generate_series(1,:count) i"""),{'count':count})
                    await session.execute(text("INSERT INTO card_variants(card_id,marketplace,external_id,product_title) SELECT id,marketplace,external_id,'Нативный товар '||lpad(external_id,5,'0') FROM marketplace_cards WHERE primary_variant_id IS NULL"))
                    await session.execute(text("UPDATE marketplace_cards c SET primary_variant_id=v.id FROM card_variants v WHERE v.card_id=c.id AND c.primary_variant_id IS NULL"))
        await db.close()
    try:
        asyncio.run(seed())
    except Exception:
        import traceback
        Path(__file__).with_name('seed-error.log').write_text(traceback.format_exc())
        raise
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
                price=Decimal('1024.00' if self.marketplace=='wildberries' else '77648.00' if self.marketplace=='aliexpress' else '100.10'),availability=Availability.IN_STOCK)
    from marketplace_connector.connectors import builder
    builder.AsyncOzonClient=FakeClient
    builder.OzonConnector=FakeConnector
    class FakeAliConnector(FakeConnector):
        marketplace='aliexpress'
    builder.AsyncAliExpressClient=FakeClient
    builder.AliExpressConnector=FakeAliConnector
    class FakeWbConnector(FakeConnector):
        marketplace='wildberries'
    builder.AsyncWildberriesClient=FakeClient
    builder.WildberriesConnector=FakeWbConnector
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
startup_mode = os.environ.get('PRICE_SMOKE_STARTUP', '')
if startup_mode:
    env['PRICE_SMOKE_STARTUP_GATE'] = str(root/'startup-release')
    env['PRICE_SMOKE_STARTUP_FAIL'] = str(root/'startup-fail')
    if startup_mode == 'error': (root/'startup-fail').touch()
log = (root/'desktop.log').open('w')
launch_command = [str(repo/'frontend/src-tauri/target/release/price-watch')]
process = subprocess.Popen(launch_command + (['--background'] if startup_mode in ('background', 'queued') else []),
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


def native_keys(keysyms, target):
    # WebKit exposes focus but not EditableText. XTest targets only this
    # script's private Xvfb display; AT-SPI string synthesis is not available
    # in every installed registry build.
    x11=ctypes.CDLL('libX11.so.6')
    xtest=ctypes.CDLL('libXtst.so.6')
    x11.XOpenDisplay.argtypes=[ctypes.c_char_p]
    x11.XOpenDisplay.restype=ctypes.c_void_p
    x11.XKeysymToKeycode.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
    x11.XKeysymToKeycode.restype=ctypes.c_ubyte
    x11.XFlush.argtypes=[ctypes.c_void_p]
    x11.XCloseDisplay.argtypes=[ctypes.c_void_p]
    xtest.XTestFakeKeyEvent.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_int,ctypes.c_ulong]
    xtest.XTestFakeMotionEvent.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ulong]
    xtest.XTestFakeButtonEvent.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_int,ctypes.c_ulong]
    display=x11.XOpenDisplay(os.environ['DISPLAY'].encode())
    if not display: raise RuntimeError('Private Xvfb display unavailable')
    try:
        rect=target.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        xtest.XTestFakeMotionEvent(display,-1,rect.x+rect.width//2,rect.y+rect.height//2,0)
        xtest.XTestFakeButtonEvent(display,1,1,0)
        xtest.XTestFakeButtonEvent(display,1,0,0)
        for symbol in keysyms:
            key=x11.XKeysymToKeycode(display,symbol)
            if not key: raise RuntimeError('Native test key is absent from keymap')
            xtest.XTestFakeKeyEvent(display,key,1,0)
            xtest.XTestFakeKeyEvent(display,key,0,0)
        x11.XFlush(display)
    finally:
        x11.XCloseDisplay(display)


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
            if (os.environ.get('PRICE_SMOKE_ONLY_WB') or prices.get('ozon')=='100.10') and (not os.environ.get('PRICE_SMOKE_ALI') or prices.get('aliexpress')=='77648.00') and (not os.environ.get('PRICE_SMOKE_WB') or prices.get('wildberries')=='1024.00'): return
        except Exception: pass
        time.sleep(.2)
    raise RuntimeError('Private API price timeout')


report={'root':str(root),'pid':process.pid,'checks':{}}
try:
    if startup_mode:
        # xprop reports the mapped state through X11's ICCCM WM_STATE only with
        # a window manager. Query Xlib directly in this private, manager-free Xvfb.
        class WindowAttributes(ctypes.Structure):
            _fields_ = [(name, typ) for name, typ in [
                ('x',ctypes.c_int),('y',ctypes.c_int),('width',ctypes.c_int),('height',ctypes.c_int),
                ('border_width',ctypes.c_int),('depth',ctypes.c_int),('visual',ctypes.c_void_p),
                ('root',ctypes.c_ulong),('class_',ctypes.c_int),('bit_gravity',ctypes.c_int),
                ('win_gravity',ctypes.c_int),('backing_store',ctypes.c_int),('backing_planes',ctypes.c_ulong),
                ('backing_pixel',ctypes.c_ulong),('save_under',ctypes.c_int),('colormap',ctypes.c_ulong),
                ('map_installed',ctypes.c_int),('map_state',ctypes.c_int),('all_event_masks',ctypes.c_long),
                ('your_event_mask',ctypes.c_long),('do_not_propagate_mask',ctypes.c_long),
                ('override_redirect',ctypes.c_int),('screen',ctypes.c_void_p)]]
        x11=ctypes.CDLL('libX11.so.6')
        x11.XOpenDisplay.argtypes=[ctypes.c_char_p]; x11.XOpenDisplay.restype=ctypes.c_void_p
        display=x11.XOpenDisplay(os.environ['DISPLAY'].encode())
        x11.XDefaultRootWindow.argtypes=[ctypes.c_void_p]; x11.XDefaultRootWindow.restype=ctypes.c_ulong
        x11.XQueryTree.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),ctypes.POINTER(ctypes.c_uint)]
        x11.XFetchName.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_char_p)]
        x11.XGetWindowAttributes.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(WindowAttributes)]
        x11.XFree.argtypes=[ctypes.c_void_p]
        def visible_main():
            ancestor=ctypes.c_ulong(); parent=ctypes.c_ulong(); children=ctypes.POINTER(ctypes.c_ulong)(); count=ctypes.c_uint()
            x11.XQueryTree(display,x11.XDefaultRootWindow(display),ctypes.byref(ancestor),ctypes.byref(parent),ctypes.byref(children),ctypes.byref(count))
            found=False
            for index in range(count.value):
                name=ctypes.c_char_p(); attrs=WindowAttributes()
                x11.XFetchName(display,children[index],ctypes.byref(name))
                if name.value and name.value.decode()=='Price watch':
                    x11.XGetWindowAttributes(display,children[index],ctypes.byref(attrs))
                    found=children[index] if attrs.map_state==2 else found
                if name: x11.XFree(name)
            if children: x11.XFree(children)
            return found
        end=time.monotonic()+40
        while time.monotonic()<end and api_pid() is None: time.sleep(.1)
        if api_pid() is None: raise RuntimeError('API startup gate not reached')
        for _ in range(10):
            if visible_main(): raise RuntimeError('Main window appeared before services were ready')
            time.sleep(.1)
        if startup_mode=='queued':
            subprocess.run(launch_command,env=env,check=True,timeout=10)
            time.sleep(.3)
            if visible_main(): raise RuntimeError('Second instance revealed the startup window')
        (root/'startup-release').touch()
        if startup_mode=='error':
            retry=wait_for(lambda items:next((node for name,node in items if name=='Повторить'),None))
            if not visible_main(): raise RuntimeError('Startup error stayed hidden')
            (root/'startup-fail').unlink()
            if not retry.get_action_iface().do_action(0): raise RuntimeError('Startup retry failed')
        if startup_mode=='background':
            # Hidden WebKit does not expose its DOM through AT-SPI. Services
            # have started once the worker reaches its isolated fake connector.
            end=time.monotonic()+40
            while time.monotonic()<end and not (root/'failed-once').exists(): time.sleep(.1)
            if not (root/'failed-once').exists(): raise RuntimeError('Background services did not start')
            time.sleep(2)
            if visible_main(): raise RuntimeError('Background launch revealed main window')
            subprocess.run(launch_command,env=env,check=True,timeout=10)
        wait_for(lambda items:any(name=='Товары' for name,_ in items))
        end=time.monotonic()+5
        while time.monotonic()<end and not visible_main(): time.sleep(.1)
        if not visible_main(): raise RuntimeError('Ready main window did not open')
        class ClientMessage(ctypes.Structure):
            _fields_=[('type',ctypes.c_int),('serial',ctypes.c_ulong),('send_event',ctypes.c_int),
                ('display',ctypes.c_void_p),('window',ctypes.c_ulong),('message_type',ctypes.c_ulong),
                ('format',ctypes.c_int),('data',ctypes.c_long*5)]
        class XEvent(ctypes.Union):
            _fields_=[('message',ClientMessage),('padding',ctypes.c_long*24)]
        x11.XInternAtom.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_int]; x11.XInternAtom.restype=ctypes.c_ulong
        x11.XSendEvent.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_int,ctypes.c_long,ctypes.POINTER(XEvent)]
        x11.XFlush.argtypes=[ctypes.c_void_p]
        event=XEvent(); window=visible_main()
        event.message=ClientMessage(33,0,1,display,window,x11.XInternAtom(display,b'WM_PROTOCOLS',0),32,(ctypes.c_long*5)(x11.XInternAtom(display,b'WM_DELETE_WINDOW',0),0,0,0,0))
        x11.XSendEvent(display,window,0,0,ctypes.byref(event)); x11.XFlush(display)
        end=time.monotonic()+5
        while time.monotonic()<end and visible_main(): time.sleep(.1)
        if visible_main(): raise RuntimeError('Close did not hide the main window')
        old=api_pid()
        if old is None: raise RuntimeError('API missing before hidden recovery')
        os.kill(old,signal.SIGTERM)
        end=time.monotonic()+40
        while time.monotonic()<end and api_pid() in (None,old): time.sleep(.1)
        if api_pid() in (None,old): raise RuntimeError('Hidden API did not recover')
        time.sleep(2)
        if visible_main(): raise RuntimeError('Service recovery reopened a closed window')
        subprocess.run(launch_command,env=env,check=True,timeout=10)
        end=time.monotonic()+5
        while time.monotonic()<end and not visible_main(): time.sleep(.1)
        if not visible_main(): raise RuntimeError('Explicit reopen failed after recovery')
        report['checks']['closed_recovery_and_explicit_reopen']=True
        report['checks']['hidden_startup_'+startup_mode]=True
        print(json.dumps(report,ensure_ascii=False),flush=True)
    else:
        subprocess.run(['import','-window','root','/tmp/price-watch-rel-native-start.png'],check=True)
        button=wait_for(lambda items: next((node for name,node in items if name=='Повторить неудавшиеся и оставшиеся'),None))
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
        count=int(os.environ.get('PRICE_SMOKE_CATALOG_SIZE','0'))
        if count:
            initial=nodes()
            checkboxes=[name for name,_ in initial if name.startswith('Выбрать карточку ')]
            if not 1 < len(checkboxes) < 80: raise RuntimeError('Native catalog is not bounded: '+str(len(checkboxes)))
            search=next(node for name,node in initial if name=='Поиск по названию или артикулу')
            last=f'Нативный товар {count:05d}'
            query=f'{count:05d}'
            if not search.get_component_iface().grab_focus(): raise RuntimeError('Native search focus failed')
            native_keys(map(ord,query),search)
            wait_for(lambda items:any(name=='Выбрать карточку '+last for name,_ in items))
            grid=wait_for(lambda items:next((node for name,node in items if name=='Сетка'),None))
            if not grid.get_action_iface().do_action(0): raise RuntimeError('Native grid action failed')
            wait_for(lambda items:any(name=='Сетка' and node.get_state_set().contains(Atspi.StateType.CHECKED) for name,node in items))
            wait_for(lambda items:any(name==last for name,_ in items))
            search=wait_for(lambda items:next((node for name,node in items if name=='Поиск по названию или артикулу'),None))
            search.get_component_iface().grab_focus()
            native_keys([0xff08]*len(query),search)
            wait_for(lambda items:sum(name.startswith('Выбрать карточку ') for name,_ in items)>1)
            report['checks']['large_catalog_last_search_and_grid']=True
            report['catalog']={'syntheticCards':count,'initialAccessibleCardCheckboxes':len(checkboxes)}
        subprocess.run(['import','-window','root','/tmp/price-watch-rel-native-after.png'],check=True)
        report['names']=[name for name,_ in nodes()]
        files=list((root/'state').rglob('*.log'))
        report['logs']={str(path.relative_to(root/'state')):path.stat().st_size for path in files}
        if any(size>10*1024*1024 for size in report['logs'].values()): raise RuntimeError('Unbounded native process log')
        if any(path.name.endswith(('.log.1','.log.2','.log.old')) for path in (root/'state').rglob('*')):
            raise RuntimeError('Unexpected native log archive')
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
