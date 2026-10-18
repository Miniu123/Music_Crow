"""Download only the next audio track, with cancellation and a small disk cache."""
import hashlib
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from urllib.parse import urlparse

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from core.search_engine import run_extractor

log = logging.getLogger(__name__)
MAX_FILE_BYTES = 80 * 1024 * 1024
MAX_CACHE_BYTES = 200 * 1024 * 1024


def cache_key(url):
    return hashlib.sha256(url.encode('utf-8')).hexdigest()


class PrefetchWorker(QThread):
    ready = pyqtSignal(str, str)
    failed = pyqtSignal(str)

    def __init__(self, url, directory, parent=None):
        super().__init__(parent)
        self.url = url
        self.directory = Path(directory)

    def run(self):
        work = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            work = Path(tempfile.mkdtemp(prefix='.download-', dir=self.directory))
            proc = run_extractor(self, [
                sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-playlist',
                '--format', 'bestaudio/best', '--no-progress', '--no-warnings',
                '--socket-timeout', '15', '--retries', '1', '--fragment-retries', '1',
                '--max-filesize', '80M', '--no-simulate',
                '--match-filters', '!is_live & duration <= 1200',
                '--output', str(work / 'audio.%(ext)s'), '--print', 'after_move:filepath',
                '--', self.url,
            ], timeout=150)
            if self.isInterruptionRequested():
                return
            if proc.returncode:
                self.failed.emit(self.url)
                return
            paths = [Path(line.strip()).resolve() for line in proc.stdout.splitlines() if line.strip()]
            candidate = next((p for p in reversed(paths)
                              if p.is_file() and p.parent == work.resolve()
                              and 0 < p.stat().st_size <= MAX_FILE_BYTES), None)
            if candidate is None:
                self.failed.emit(self.url)
                return
            destination = self.directory / (cache_key(self.url) + candidate.suffix)
            os.replace(candidate, destination)
            self.ready.emit(self.url, str(destination))
        except InterruptedError:
            pass
        except Exception:
            log.exception('Audio prefetch failed')
            self.failed.emit(self.url)
        finally:
            if work:
                shutil.rmtree(work, ignore_errors=True)


class AudioPrefetcher(QObject):
    status_changed = pyqtSignal(str, str)  # URL, downloading/ready/unavailable/idle

    def __init__(self, parent=None, directory=None):
        super().__init__(parent)
        self.directory = Path(directory) if directory else Path.home() / '.cache/music-crow/audio'
        self._worker = None
        self._wanted = ''
        self._protected = set()
        self._failed_until = {}
        self._stopped = False
        self.state = 'idle'

    def cached_path(self, url):
        if not url or not self.directory.exists():
            return None
        for path in self.directory.glob(cache_key(url) + '.*'):
            try:
                if path.is_file() and 0 < path.stat().st_size <= MAX_FILE_BYTES:
                    return str(path)
            except OSError:
                continue
        return None

    def _status(self, url, state):
        self.state = state
        self.status_changed.emit(url, state)

    def request(self, url, protected_urls=()):
        if self._stopped:
            return
        self._protected = {cache_key(u) for u in protected_urls if u}
        self._wanted = url if urlparse(url).scheme in ('http', 'https') else ''
        if self._worker:
            if self._worker.url != self._wanted:
                self._worker._cancelled = True
                self._worker.requestInterruption()
            return
        self._start_wanted()

    def _start_wanted(self):
        if self._stopped:
            return
        url = self._wanted
        if not url:
            self._status('', 'idle')
            return
        if self.cached_path(url):
            self._status(url, 'ready')
            return
        if self._failed_until.get(url, 0) > time.monotonic():
            self._status(url, 'unavailable')
            return
        worker = PrefetchWorker(url, self.directory, self)
        self._worker = worker
        worker.ready.connect(self._ready)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._finished)
        self._status(url, 'downloading')
        worker.start()

    def _ready(self, url, path):
        if not self._stopped and url == self._wanted:
            self._status(url, 'ready')

    def _failed(self, url):
        self._failed_until[url] = time.monotonic() + 300
        if len(self._failed_until) > 100:
            self._failed_until.pop(next(iter(self._failed_until)))
        if not self._stopped and url == self._wanted:
            self._status(url, 'unavailable')

    def _finished(self):
        worker, self._worker = self._worker, None
        if worker:
            worker.deleteLater()
        self.prune()
        if not self._stopped and worker and (worker.url != self._wanted or getattr(worker, "_cancelled", False)):
            self._start_wanted()

    def prune(self):
        try:
            files = sorted((p for p in self.directory.glob('*') if p.is_file()),
                           key=lambda p: p.stat().st_mtime, reverse=True)
            size = 0
            for index, path in enumerate(files):
                size += path.stat().st_size
                if (index >= 3 or size > MAX_CACHE_BYTES) and path.stem not in self._protected:
                    path.unlink(missing_ok=True)
        except OSError:
            log.warning('Cannot prune audio cache')

    def shutdown(self):
        self._stopped = True
        if self._worker:
            self._worker.requestInterruption()
            self._worker.wait()
