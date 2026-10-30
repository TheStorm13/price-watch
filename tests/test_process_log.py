from pathlib import Path
import os
import subprocess
import tempfile
import time
import unittest
from marketplace_connector.browser.process_log import ProcessLog


class ProcessLogTests(unittest.TestCase):
    def test_continuous_stdout_stderr_and_new_session_have_one_bounded_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'chrome.log'
            log=ProcessLog(path,limit=1024)
            child=subprocess.Popen(['python3','-c',"import os;os.write(1,b'x'*300000);os.write(2,b'END')"],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            log.start(child.stdout)
            child.wait(timeout=5)
            log.close()
            self.assertLessEqual(path.stat().st_size,1024)
            self.assertTrue(path.read_bytes().endswith(b'END'))
            self.assertEqual(list(Path(directory).iterdir()),[path])
            ProcessLog(path,limit=1024).close()
            self.assertEqual(path.read_bytes(),b'')

    def test_stop_does_not_wait_for_pipe_eof(self):
        with tempfile.TemporaryDirectory() as directory:
            read,write=os.pipe()
            log=ProcessLog(Path(directory)/'chrome.log')
            log.start(os.fdopen(read,'rb',buffering=0))
            start=time.monotonic()
            log.close()
            os.close(write)
            self.assertLess(time.monotonic()-start,1)

    @unittest.skipUnless(Path('/dev/full').exists(), 'Linux /dev/full required')
    def test_disk_write_failure_still_drains_child_output(self):
        log=ProcessLog(Path('/dev/full'),limit=1024)
        child=subprocess.Popen(['python3','-c',"import os;os.write(1,b'x'*300000)"],stdout=subprocess.PIPE)
        stream=child.stdout
        log.start(stream)
        child.wait(timeout=5)
        log.close()
        self.assertEqual(child.returncode,0)
        self.assertTrue(stream.closed)
