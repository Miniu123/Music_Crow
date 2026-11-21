"""Resolve track pages to direct audio streams, ahead of playback when possible.

Why playback used to take ~8.5 s: YouTube's default (TV) client hands out
stream URLs that only start working ~6 s after they are issued, and mpv's own
yt-dlp hook waits for that. Two clients avoid the wait:

* the embedded-player client returns audio-only streams (best quality) that
  work at once, but only for videos that allow embedding;
* the Android client works at once for the rest (many label-owned music videos
  block embedding) and returns a small muxed stream, used to start playing.

A click therefore gets its own lookup that asks both clients concurrently and
plays in ~1-2 s, never queued behind background work. Upcoming, visible and
hovered tracks are resolved in the background for best quality; their streams
are kept with the time they become usable, so a later click plays in ~0.1 s.
"""
import collections
import json
import logging
import sys
import threading
import time
from urllib.parse import parse_qs, urlparse

from PyQt6.QtCore import QObject, pyqtSignal

log = logging.getLogger(__name__)

SUPPORTED_HOSTS = {
    'youtube.com', 'www.youtube.com', 'music.youtube.com', 'm.youtube.com', 'youtu.be',
    'soundcloud.com', 'www.soundcloud.com', 'm.soundcloud.com',
}
EXPIRY_MARGIN = 10 * 60        # never hand mpv a URL that expires mid-track
DEFAULT_TTL = 30 * 60          # for streams without an expiry parameter
FAILURE_BACKOFF = 2 * 60
MAX_PREFETCH_QUEUE = 8
MAX_CACHED_STREAMS = 200
YDL_OPTIONS = {
    'quiet': True, 'no_warnings': True, 'noprogress': True,
    # Audio only when offered; otherwise a small muxed stream, never 1080p video.
    'format': 'bestaudio/best[height<=480]/best',
    'noplaylist': True, 'skip_download': True,
    'socket_timeout': 15, 'retries': 1, 'extractor_retries': 1,
}
PROFILES = {
    'embedded': dict(YDL_OPTIONS, extractor_args={'youtube': {'player_client': ['web_embedded']}}),
}
# Other clients run in a separate yt-dlp process: once another YouTube client had
# been used in-process, the embedded client started returning HLS video manifests
# instead of audio-only streams for the rest of the session.
ISOLATED_CLIENTS = {'android': ['--extractor-args', 'youtube:player_client=android'], 'default': []}

_active_resolver = None


def is_resolvable(url):
    try:
        parsed = urlparse(str(url or ''))
    except ValueError:
        return False
    return parsed.scheme in ('http', 'https') and (parsed.hostname or '').lower() in SUPPORTED_HOSTS


def stream_key(url):
    from core.recommendations import track_key
    return track_key({'url': url})


def stream_expiry(stream_url, now=None):
    """Unix time at which a stream URL stops working (from its `expire` parameter)."""
    now = time.time() if now is None else now
    try:
        query = parse_qs(urlparse(stream_url).query)
        for name in ('expire', 'Expires', 'expires'):
            if query.get(name):
                return float(query[name][0])
    except (ValueError, TypeError):
        pass
    return now + DEFAULT_TTL


def wait_time(info):
    """Seconds until a resolved stream starts answering (0 when usable now)."""
    return max(0.0, float((info or {}).get('available_at') or 0) - time.time())


_instances = {}
_instance_locks = {name: threading.Lock() for name in PROFILES}
_creation_lock = threading.Lock()


def _youtube_dl(profile):
    """One shared yt-dlp instance per client profile.

    Instances are created one at a time: building two concurrently left the
    embedded-client instance misconfigured (it then returned muxed video
    formats). Each instance is used by one thread at a time (see _lookup).
    """
    with _creation_lock:
        if profile not in _instances:
            import yt_dlp
            _instances[profile] = yt_dlp.YoutubeDL(dict(PROFILES[profile]))
        return _instances[profile]


def _audio_stream(info):
    if not info or info.get('is_live') or info.get('_type') in ('playlist', 'multi_video'):
        return None  # live streams and playlists stay with mpv's own handling
    stream = info.get('url')
    headers = info.get('http_headers') or {}
    if not stream:
        audio = [f for f in info.get('requested_formats') or [] if f.get('vcodec') in (None, 'none')]
        if not audio:
            return None
        stream, headers = audio[0].get('url'), audio[0].get('http_headers') or headers
    if not stream:
        return None
    return {'url': stream, 'headers': {str(k): str(v) for k, v in headers.items()},
            'expires': stream_expiry(stream), 'protocol': info.get('protocol', ''),
            'available_at': float(info.get('available_at') or 0),
            'audio_only': info.get('vcodec') in (None, 'none')}


class _NeverInterrupted:
    @staticmethod
    def isInterruptionRequested():
        return False


def _lookup_isolated(client, url, timeout=30):
    """A one-off yt-dlp process (yt-dlp.exe in the Windows build), sharing no state."""
    from core.search_engine import run_extractor
    command = [sys.executable, '-m', 'yt_dlp', '--ignore-config', '--quiet', '--no-warnings',
               '--no-playlist', '--dump-single-json', '--format', YDL_OPTIONS['format'],
               '--socket-timeout', '15', *ISOLATED_CLIENTS[client], '--', url]
    try:
        process = run_extractor(_NeverInterrupted(), command, timeout)
        if process.returncode:
            log.info('%s lookup failed for %s: %s', client, url, (process.stderr or '').strip()[-300:])
            return None
        return _audio_stream(json.loads(process.stdout))
    except Exception as error:
        log.info('%s lookup failed for %s: %s', client, url, error)
        return None


def _lookup(profile, url):
    if profile in ISOLATED_CLIENTS:
        return _lookup_isolated(profile, url)
    try:
        ydl = _youtube_dl(profile)
        with _instance_locks[profile]:  # YoutubeDL is not safe for concurrent use
            return _audio_stream(ydl.extract_info(url, download=False))
    except Exception as error:  # yt-dlp raises DownloadError when a client is refused
        log.info('%s lookup failed for %s: %s', profile, url, error)
        return None


def extract_stream(url, fast=False):
    """Blocking yt-dlp lookup; `fast` favours starting now over best quality."""
    if 'youtu' not in (urlparse(url).hostname or ''):
        return _lookup('default', url)
    if not fast:
        return _lookup('embedded', url) or _lookup('default', url)
    # Ask the Android client at the same time: its stream works at once even
    # when the video blocks embedding, so a click never waits for YouTube.
    backup = {}
    helper = threading.Thread(target=lambda: backup.update(stream=_lookup('android', url)), daemon=True)
    helper.start()
    primary = _lookup('embedded', url)
    if primary and wait_time(primary) == 0:
        return primary
    helper.join(timeout=20)
    if backup.get('stream') and wait_time(backup['stream']) == 0:
        return backup['stream']
    return primary or backup.get('stream') or _lookup('default', url)


def active_resolver():
    return _active_resolver


def prefetch_tracks(tracks, limit=3):
    """Resolves the first few tracks a user is likely to play next."""
    resolver = _active_resolver
    if resolver is not None:
        resolver.prefetch([track.get('url', '') for track in tracks if isinstance(track, dict)][:limit])


class StreamResolver(QObject):
    # page URL, stream dict or None, True for a lookup started by a click
    resolved = pyqtSignal(str, object, bool)

    def __init__(self, parent=None, extractor=extract_stream, workers=2):
        global _active_resolver
        super().__init__(parent)
        self._extract = extractor
        self._workers = workers
        self._cond = threading.Condition()
        self._prefetch_queue = collections.OrderedDict()  # key -> url, newest last
        self._prefetching = set()
        self._playing = set()
        self._cache = {}
        self._failed_until = {}
        self._threads = []
        self._stopped = False
        _active_resolver = self

    # --- cache -----------------------------------------------------------
    def cached(self, url):
        """A resolved, unexpired stream (it may still have a short `wait_time`)."""
        if not is_resolvable(url):
            return None
        key = stream_key(url)
        with self._cond:
            info = self._cache.get(key)
            if info is None:
                return None
            if info['expires'] - EXPIRY_MARGIN <= time.time():
                del self._cache[key]
                return None
            return info

    def usable(self, url):
        """A cached stream that can be played this instant."""
        info = self.cached(url)
        return info if info and wait_time(info) == 0 else None

    # --- playback: never queued behind background work --------------------
    def play_now(self, url):
        """Starts a lookup for a click; True means `resolved` will follow for it."""
        if self._stopped or not is_resolvable(url) or self.usable(url):
            return False
        key = stream_key(url)
        with self._cond:
            if key in self._playing:
                return True
            if self._failed_until.get(key, 0) > time.monotonic():
                return False
            self._playing.add(key)
        threading.Thread(target=self._resolve, args=(key, url, True), name='stream-play', daemon=True).start()
        return True

    # --- background ------------------------------------------------------
    def prefetch(self, urls):
        if self._stopped:
            return
        with self._cond:
            for url in urls:
                if not url or not is_resolvable(url):
                    continue
                key = stream_key(url)
                info = self._cache.get(key)
                if (key in self._prefetching or key in self._playing
                        or (info and info['expires'] - EXPIRY_MARGIN > time.time())
                        or self._failed_until.get(key, 0) > time.monotonic()):
                    continue
                self._prefetch_queue.pop(key, None)
                self._prefetch_queue[key] = url
            while len(self._prefetch_queue) > MAX_PREFETCH_QUEUE:
                self._prefetch_queue.popitem(last=False)  # the oldest intent is dropped
            if self._prefetch_queue:
                self._ensure_workers()
                self._cond.notify_all()

    def warm_up(self):
        """Imports yt-dlp in the background so the first click does not pay for it."""
        if self._extract is extract_stream:
            threading.Thread(target=self._import_ytdlp, name='stream-warmup', daemon=True).start()

    @staticmethod
    def _import_ytdlp():
        try:
            _youtube_dl('embedded')
        except ImportError:
            log.warning('yt-dlp is not installed; streams will open through mpv')

    def _ensure_workers(self):
        self._threads = [thread for thread in self._threads if thread.is_alive()]
        while len(self._threads) < self._workers and not self._stopped:
            thread = threading.Thread(target=self._work, name='stream-prefetch', daemon=True)
            self._threads.append(thread)
            thread.start()

    def _work(self):
        while True:
            with self._cond:
                while not self._stopped and not self._prefetch_queue:
                    self._cond.wait()
                if self._stopped:
                    return
                key, url = self._prefetch_queue.popitem(last=True)  # newest intent first
                self._prefetching.add(key)
            self._resolve(key, url, False)

    def _resolve(self, key, url, for_playback):
        started = time.monotonic()
        try:
            info = self._extract(url, fast=for_playback)
        except Exception as error:
            log.info('Stream lookup failed for %s: %s', url, error)
            info = None
        with self._cond:
            (self._playing if for_playback else self._prefetching).discard(key)
            if info:
                current = self._cache.get(key)
                # Keep a stream that works now over one that is still waiting.
                if not (current and wait_time(current) == 0 < wait_time(info)):
                    self._cache[key] = info
                while len(self._cache) > MAX_CACHED_STREAMS:
                    self._cache.pop(next(iter(self._cache)))
            elif for_playback:
                self._failed_until[key] = time.monotonic() + FAILURE_BACKOFF
        log.debug('Resolved %s in %.2fs', url, time.monotonic() - started)
        if not self._stopped:
            self.resolved.emit(url, info, for_playback)

    def shutdown(self):
        global _active_resolver
        with self._cond:
            self._stopped = True
            self._prefetch_queue.clear()
            self._cond.notify_all()
        if _active_resolver is self:
            _active_resolver = None
