"""Measure bounded log draining on synthetic output; no services or user files."""
import sys,os,subprocess,tempfile,time,threading,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from marketplace_connector.browser.process_log import ProcessLog
rss=lambda:int(next(s.split()[1] for s in Path('/proc/self/status').read_text().splitlines() if s.startswith('VmRSS:')))
with tempfile.TemporaryDirectory() as d:
 path=Path(d)/'child.log';before={'rssKiB':rss(),'fds':len(list(Path('/proc/self/fd').iterdir())),'threads':threading.active_count()}
 log=ProcessLog(path);start=time.monotonic()
 child=subprocess.Popen(['python3','-c',"import os;chunk=b'x'*65536\nfor i in range(8192):os.write(1,chunk)\nos.write(2,b'END')"],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 log.start(child.stdout);peak=before['rssKiB']
 while child.poll() is None:
  peak=max(peak,rss());time.sleep(.002)
 log.close()
 after={'rssKiB':rss(),'fds':len(list(Path('/proc/self/fd').iterdir())),'threads':threading.active_count()}
 assert child.returncode==0 and path.stat().st_size<=10*1024*1024
 assert path.read_bytes().endswith(b'END') and len(list(Path(d).iterdir()))==1
 assert before['fds']==after['fds'] and before['threads']==after['threads']
 print(json.dumps({'outputBytes':8192*65536+3,'seconds':time.monotonic()-start,'before':before,'after':after,'peakRssKiB':peak,'logBytes':path.stat().st_size,'files':1}))
