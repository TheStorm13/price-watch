"""One bounded file for an owned child's output, without line-sized buffers."""
import logging
import os
from pathlib import Path
import select
import threading
import time

MAX_LOG_BYTES = 10 * 1024 * 1024


class ProcessLog:
    def __init__(self, path: Path, *, limit=MAX_LOG_BYTES):
        if limit <= 0:
            raise ValueError('Log limit must be positive')
        self.path, self.limit = Path(path), limit
        self._file = self.path.open('wb', buffering=0)
        self._stop = threading.Event()
        self._thread = None
        self._last_error = float('-inf')

    def start(self, stream):
        self._thread = threading.Thread(target=self._drain, args=(stream,), daemon=True, name='chrome-log')
        self._thread.start()

    def _write(self, data):
        try:
            if self._file is None:
                self._file = self.path.open('ab', buffering=0)
            while data:
                size = self._file.tell()
                if size >= self.limit:
                    self._file.seek(0)
                    self._file.truncate()
                    size = 0
                part = data[:self.limit-size]
                written = self._file.write(part)
                data = data[written:]
        except OSError as error:
            if self._file is not None:
                self._file.close()
                self._file = None
            if time.monotonic()-self._last_error >= 60:
                logging.getLogger(__name__).warning('Не удалось записать журнал Chrome: %s', error)
                self._last_error = time.monotonic()

    def _drain(self, stream):
        try:
            fd = stream.fileno()
            os.set_blocking(fd, False)
            while True:
                readable, _, _ = select.select([fd], [], [], 0.1)
                if not readable:
                    if self._stop.is_set():
                        break
                    continue
                try:
                    data = os.read(fd, 64*1024)
                except BlockingIOError:
                    continue
                if not data:
                    break
                self._write(data)
                if self._stop.is_set():
                    # Bound shutdown even if a descendant keeps the pipe open.
                    for _ in range(4):
                        try:
                            tail = os.read(fd, 64*1024)
                        except BlockingIOError:
                            break
                        if not tail:
                            break
                        self._write(tail)
                    break
        finally:
            stream.close()

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        if self._file is not None:
            self._file.close()
            self._file = None
