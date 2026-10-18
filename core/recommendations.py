"""Local listening profile and bounded, asynchronous music discovery."""
import json
import logging
import math
import os
import re
import tempfile
import time
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from core.search_engine import SearchWorker

log = logging.getLogger(__name__)


def track_key(track):
    url = str(track.get('url') or '')
    parsed = urlparse(url)
    if parsed.hostname in ('youtube.com', 'www.youtube.com', 'music.youtube.com', 'm.youtube.com'):
        video = parse_qs(parsed.query).get('v', [''])[0]
        if video:
            return 'youtube:' + video
    if parsed.hostname == 'youtu.be':
        return 'youtube:' + parsed.path.strip('/')
    return url.split('?')[0].rstrip('/')


def artist_name(track):
    artist = str(track.get('uploader') or track.get('artist') or '').strip()
    artist = re.sub(r'\s*-\s*Topic$', '', artist, flags=re.I).strip()
    return '' if artist.lower() in ('unknown artist', 'unknown', '') else artist


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class ListeningHistory(QObject):
    changed = pyqtSignal()

    def __init__(self, player, parent=None, path=None, clock=time.monotonic):
        super().__init__(parent)
        self.player = player
        self.path = Path(path) if path else Path.home() / '.config/music-crow/listening_history.json'
        self.clock = clock
        self.entries = {}
        self._track = None
        self._seconds = 0
        self._recorded = False
        self._last_tick = clock()
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                self.entries = {key: entry for key, entry in data.items()
                                if isinstance(entry, dict) and isinstance(entry.get('track'), dict)
                                and isinstance(entry.get('plays'), (int, float))
                                and isinstance(entry.get('last_played'), (int, float))}
        except (OSError, ValueError):
            pass
        player.track_started.connect(self._start)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _start(self, track):
        self._track = dict(track)
        self._seconds = 0
        self._recorded = False
        self._last_tick = self.clock()

    def _tick(self):
        now = self.clock()
        elapsed = max(0, min(2, now - self._last_tick))
        self._last_tick = now
        if not self._track or self._recorded:
            return
        try:
            engine = self.player.mpv
            if engine.pause or engine.idle_active or engine.time_pos is None:
                return
            duration = engine.duration or 0
        except Exception:
            return
        self._seconds += elapsed
        # Real listening time, so seeking does not count as listening.
        threshold = min(30, max(5, duration / 2)) if duration else 30
        if self._seconds >= threshold:
            self._recorded = True
            self.record(self._track)

    def record(self, track):
        key = track_key(track)
        if not key:
            return
        previous = self.entries.get(key, {})
        self.entries[key] = {'track': dict(track), 'plays': previous.get('plays', 0) + 1,
                             'last_played': time.time()}
        self.entries = dict(sorted(self.entries.items(),
                                   key=lambda item: item[1]['last_played'], reverse=True)[:500])
        try:
            save_json(self.path, self.entries)
        except OSError:
            log.exception('Cannot save listening history')
        self.changed.emit()


def build_profile(playlist_tracks, entries, now=None):
    now = time.time() if now is None else now
    known = {}
    artists = Counter()
    names = {}
    weights = Counter()
    for track in playlist_tracks:
        key = track_key(track)
        if key and key not in known:
            known[key] = dict(track, recommendation_reason='Z Twoich playlist')
            weights[key] += 2
    for key, entry in entries.items():
        track = entry['track']
        known[key] = dict(track, recommendation_reason='Z Twojej historii')
        age_days = max(0, (now - entry['last_played']) / 86400)
        weights[key] += (2 + math.log1p(max(0, entry['plays']))) * 0.5 ** (age_days / 30)
    for key, track in known.items():
        artist = artist_name(track)
        if artist:
            normalized = artist.casefold()
            artists[normalized] += weights[key]
            names[normalized] = artist
    return known, weights, artists, names


def rank_tracks(candidates, profile, current_url='', discovery=False, limit=8):
    known, weights, artists, names = profile
    current = track_key({'url': current_url})
    ranked = []
    seen = set()
    titles = set()
    for track in candidates:
        key = track_key(track)
        title = re.sub(r'\W+', ' ', str(track.get('title') or '').casefold()).strip()
        if not key or key == current or key in seen or not title:
            continue
        if discovery and key in known:
            continue
        artist = artist_name(track)
        score = weights[key] + artists[artist.casefold()] * 0.4
        if discovery:
            # Keep only candidates linked to an artist in the user's profile.
            matching = [a for a in artists if a == artist.casefold() or a in title]
            if not matching:
                continue
            matched = max(matching, key=lambda a: artists[a])
            score += artists[matched]
            reason = 'Na podstawie: ' + names[matched]
            group = matched
        else:
            reason = known.get(key, {}).get('recommendation_reason', 'Z Twojej biblioteki')
            group = artist.casefold() or key
        seen.add(key)
        ranked.append((score, key, title, group, dict(track, recommendation_reason=reason, recommendation_artist=group)))
    counts = Counter()
    result = []
    for _, key, title, group, track in sorted(ranked, key=lambda item: (-item[0], item[1])):
        if counts[group] >= 2 or title in titles:
            continue
        counts[group] += 1
        titles.add(title)
        result.append(track)
        if len(result) >= limit:
            break
    return result


class RecommendationManager(QObject):
    READY_STATUS = 'Dopasowane do Twojej historii i playlist.'
    EMPTY_STATUS = 'Posłuchaj muzyki lub dodaj utwory do playlist, aby otrzymać propozycje.'
    updated = pyqtSignal(list)
    status_changed = pyqtSignal(str)
    busy_changed = pyqtSignal(bool)

    def __init__(self, player, playlists, history, parent=None):
        super().__init__(parent)
        self.player, self.playlists, self.history = player, playlists, history
        self._worker = None
        self._stopped = False
        self._seeds = []
        self._candidates = []
        self._cache = []
        self._last_fetch = 0
        self._fingerprint = None
        self._profile = build_profile([], {})
        self._had_error = False
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(1200)
        self.debounce.timeout.connect(self.refresh)
        history.changed.connect(self.schedule)
        player.track_started.connect(self.schedule)
        if playlists:
            for signal in (playlists.playlist_created, playlists.playlist_updated, playlists.playlist_deleted):
                signal.connect(self.schedule)
        QTimer.singleShot(0, self.refresh)

    def schedule(self, *_):
        if not self._stopped:
            self.debounce.start()

    def _current_url(self):
        return self.player._current_track.get('url', '')

    def refresh(self, force=False):
        if self._stopped:
            return
        if self._worker is not None:
            self.schedule()
            return
        self._profile = self._make_profile()
        self._publish()
        artists = self._profile[2]
        seeds = [self._profile[3][a] for a, _ in artists.most_common(3)]
        if not seeds:
            self.status_changed.emit(self.EMPTY_STATUS)
            return
        fingerprint = tuple(seeds)
        if not force and fingerprint == self._fingerprint and time.monotonic() - self._last_fetch < 1800:
            self.status_changed.emit(self.READY_STATUS)
            return
        self._fingerprint = fingerprint
        self._seeds = seeds
        self._candidates = []
        self._had_error = False
        self.busy_changed.emit(True)
        self.status_changed.emit('Szukam muzyki dopasowanej do Ciebie…')
        self._next_seed()

    def _make_profile(self):
        tracks = []
        if self.playlists:
            for name in self.playlists.list_playlists():
                try:
                    tracks.extend(t for t in self.playlists.get_tracks(name) if isinstance(t, dict))
                except (OSError, ValueError, TypeError):
                    log.warning('Cannot read playlist %s for recommendations', name)
        return build_profile(tracks, self.history.entries)

    def _publish(self):
        local = rank_tracks(self._profile[0].values(), self._profile, self._current_url(), limit=4)
        fresh = rank_tracks(self._cache, self._profile, self._current_url(), discovery=True, limit=6)
        combined = []
        counts = Counter()
        for track in fresh + local:
            artist = track['recommendation_artist']
            if counts[artist] < 2:
                combined.append(track)
                counts[artist] += 1
            if len(combined) == 8:
                break
        self.updated.emit(combined)

    def _next_seed(self):
        if self._stopped:
            return
        if not self._seeds:
            self.busy_changed.emit(False)
            if self._candidates:
                self._cache = self._candidates
            self._last_fetch = time.monotonic()
            self._publish()
            self.status_changed.emit('Nie udało się pobrać wszystkich nowości. Możesz spróbować ponownie.'
                                     if self._had_error else self.READY_STATUS)
            return
        artist = self._seeds.pop(0)
        # One source per seed keeps background traffic bounded to three searches.
        sources = Counter(t.get('platform') for t in self._profile[0].values()
                          if artist_name(t).casefold() == artist.casefold())
        platform = 'SoundCloud' if sources['SoundCloud'] > sources['YouTube Music'] else 'YouTube Music'
        worker = SearchWorker(artist + ' music', [platform], self)
        self._worker = worker
        worker.results_ready.connect(self._receive)
        worker.search_error.connect(self._error)
        worker.finished.connect(self._finished)
        worker.start()

    def _receive(self, tracks):
        if not self._stopped:
            self._candidates.extend(tracks)

    def _error(self, _):
        self._had_error = True

    def _finished(self):
        worker, self._worker = self._worker, None
        if worker:
            worker.deleteLater()
        self._next_seed()

    def shutdown(self):
        self._stopped = True
        self.debounce.stop()
        self.history.timer.stop()
        if self._worker is not None:
            self._worker.requestInterruption()
            self._worker.wait()


class PlaybackRecommendationManager(RecommendationManager):
    """Continuation based on the active session, separate from home suggestions."""

    READY_STATUS = 'Dopasowane do odtwarzania. Wybierz Następny lub zostaw do odtworzenia po playliście.'
    EMPTY_STATUS = 'Wybierz utwór lub playlistę, aby otrzymać propozycje do dalszego słuchania.'

    def __init__(self, player, playlists, history, parent=None):
        self.library = playlists
        self._request_session = player._queue_session
        super().__init__(player, None, history, parent)
        player.queue_started.connect(self._new_session)
        self.updated.connect(player.set_recommended_queue)

    def _new_session(self):
        self._fingerprint = None
        self._last_fetch = 0
        self._cache = []
        self._candidates = []
        self._seeds = []
        if self._worker is not None:
            self._worker.requestInterruption()
        self.schedule()

    def _make_profile(self):
        self._request_session = self.player._queue_session
        context = list(self.player._recommendation_context)
        if self.player._current_track:
            context.append(self.player._current_track)
        return build_profile(context, {})

    def _receive(self, tracks):
        if self._request_session == self.player._queue_session:
            super()._receive(tracks)

    def _publish(self):
        if self._request_session != self.player._queue_session:
            return
        # Familiar songs by the same artists remain available while offline.
        candidates = list(self._cache)
        candidates.extend(entry['track'] for entry in self.history.entries.values())
        if self.library:
            for name in self.library.list_playlists():
                try:
                    candidates.extend(t for t in self.library.get_tracks(name) if isinstance(t, dict))
                except (OSError, ValueError, TypeError):
                    pass
        excluded = {track_key(t) for t in self.player._base_queue + self.player._priority_queue}
        excluded.update(self.player._recommendation_seen)
        candidates = [t for t in candidates if track_key(t) not in excluded]
        tracks = rank_tracks(candidates, self._profile, self._current_url(), discovery=True, limit=12)
        self.updated.emit(tracks)
