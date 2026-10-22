"""Local listening profile and bounded, asynchronous music discovery."""
import json
import hashlib
import unicodedata
from typing import NamedTuple
import logging
import math
import os
import re
import tempfile
import time
from collections import Counter
from pathlib import Path
from core.app_paths import config_dir
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
    artist = str(track.get('artist') or track.get('uploader') or '').strip()
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
        self.path = Path(path) if path else config_dir() / 'listening_history.json'
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


def normalized(value):
    return re.sub(r'[^\w]+', ' ', unicodedata.normalize('NFKC', str(value or '')).casefold()).strip()


def artist_key(value):
    value = re.sub(r'\s*(?:-\s*Topic|VEVO|\s+Official)$', '', str(value or ''), flags=re.I)
    return normalized(value)


def recording_key(track):
    """Collapse packaging labels, but retain live/remix/acoustic version names."""
    title = str(track.get('title') or '')
    title = re.sub(r'[\[(]([^\])]+)[\])]', lambda m: '' if re.fullmatch(
        r'(?:official|music|video|audio|lyrics?|visuali[sz]er|hd|hq|4k|1080p|\s)+',
        m[1].strip(), flags=re.I) else m[0], title)
    title = normalized(title)
    title = re.sub(r'\s+(?:official (?:music )?(?:video|audio)|lyrics? video)$', '', title)
    artist = artist_key(artist_name(track))
    if artist and title.startswith(artist + ' '):
        title = title[len(artist) + 1:]
    return (artist, title)


class TasteProfile(NamedTuple):
    known: dict
    weights: Counter
    artists: Counter
    names: dict
    recent: dict
    context: Counter
    related: dict
    now: float


def build_profile(playlist_tracks, entries, now=None, *, context=(), playlist_groups=()):
    now = time.time() if now is None else now
    known, names, recent = {}, {}, {}
    artists, weights, session = Counter(), Counter(), Counter()
    for track in playlist_tracks:
        if not isinstance(track, dict):
            continue
        key = track_key(track)
        if key and key not in known:
            known[key] = dict(track, recommendation_reason='Z Twoich playlist')
            weights[key] = 2
    for entry in entries.values():
        if not isinstance(entry, dict) or not isinstance(entry.get('track'), dict):
            continue
        plays, last = entry.get('plays'), entry.get('last_played')
        if not all(isinstance(v, (int, float)) and math.isfinite(v) and v >= 0 for v in (plays, last)):
            continue
        track = entry['track']
        key = track_key(track)
        if not key:
            continue
        known[key] = dict(track, recommendation_reason='Z Twojej historii')
        recent[key] = last
        age_days = max(0, (now - last) / 86400)
        weights[key] += (2 + math.log1p(min(plays, 10000))) * 0.5 ** (age_days / 30)
    for key, track in known.items():
        artist = artist_name(track)
        if artist:
            group = artist_key(artist)
            artists[group] += weights[key]
            names[group] = artist
    # Session influence is capped per artist: a huge playlist must not drown out
    # the song currently playing (the final item in context).
    context = list(context)
    for track in context:
        artist = artist_name(track)
        if artist:
            group = artist_key(artist)
            session[group] = 3
            names[group] = artist
    if context and artist_name(context[-1]):
        session[artist_key(artist_name(context[-1]))] = 8
    # Artists sharing a playlist are evidence of a connection, not proof of genre.
    related = {}
    for tracks in playlist_groups:
        groups = {artist_key(artist_name(t)): artist_name(t) for t in tracks if artist_name(t)}
        anchors = set(groups) & set(session)
        if not anchors or len(groups) > 40:
            continue
        strength = 1 / math.sqrt(max(1, len(groups) - 1))
        for group, name in groups.items():
            if group not in session:
                score = strength * max(session[a] for a in anchors)
                if score > related.get(group, (0, ''))[0]:
                    anchor = max(anchors, key=lambda a: (session[a], a))
                    related[group] = (score, names[anchor])
                    names[group] = name
    # Explicit featured-artist credits offer a narrow, explainable discovery path.
    for track in known.values():
        source = artist_key(artist_name(track))
        if not source:
            continue
        credit = re.search(r'\b(?:feat\.?|ft\.?|featuring)\s+([^\]\)\(\[|]+)',
                           str(track.get('title') or ''), flags=re.I)
        if credit:
            credited = re.split(r'\s[-–—]\s', credit[1], maxsplit=1)[0]
            for name in re.split(r'\s*(?:,|&|\band\b)\s*', credited, flags=re.I)[:3]:
                name = name.strip(' .-')
                group = artist_key(name)
                if 2 <= len(group) <= 60 and group not in artists and group not in related:
                    related[group] = (1.5, names[source])
                    names[group] = name
    return TasteProfile(known, weights, artists, names, recent, session, related, now)


def rank_tracks(candidates, profile, current_url='', discovery=False, limit=8,
                *, excluded=(), rotation=0, artist_limit=2, exposure=None):
    if limit <= 0:
        return []
    known, weights, artists, names = profile[:4]
    current = track_key({'url': current_url})
    excluded = set(excluded) | {current}
    known_recordings = {recording_key(t) for t in known.values()}
    blocked_recordings = {recording_key(known[k]) for k in excluded if k in known}
    ranked, seen = [], set()
    for track in candidates:
        if not isinstance(track, dict):
            continue
        key = track_key(track)
        title = normalized(track.get('title'))
        recording = recording_key(track)
        if not key or key in excluded or key in seen or not title or recording in blocked_recordings:
            continue
        if discovery and (key in known or recording in known_recordings):
            continue
        duration = track.get('duration') or 0
        if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
            continue
        if discovery and (track.get('is_live') or duration > 1200 or 0 < duration < 45
                          or re.search(r'\b(full album|compilation|greatest hits|1 hour|10 hours)\b', title)):
            continue
        artist = artist_key(artist_name(track))
        affinities = set(artists) | set(profile.context) | set(profile.related)
        # Token boundaries avoid matching e.g. "Air" to "Stairway".
        matches = [a for a in affinities if a and (a == artist or (' ' + a + ' ') in (' ' + title + ' '))]
        if discovery and not matches:
            continue
        def affinity(a):
            return math.log1p(artists[a]) + profile.context[a] + profile.related.get(a, (0, ''))[0]
        matched = max(matches, key=lambda a: (affinity(a), a)) if matches else artist
        group = artist or matched or key
        score = 2 * math.log1p(weights[key]) + 2 * affinity(matched)
        reason = known.get(key, {}).get('recommendation_reason', 'Z Twojej biblioteki')
        if discovery:
            score += 3
            if matched in profile.context:
                reason = 'Pasuje do teraz: ' + names[matched]
            elif matched in profile.related:
                reason = 'Powiązane przez playlisty: ' + profile.related[matched][1]
            else:
                reason = 'Na podstawie: ' + names[matched]
        last = profile.recent.get(key)
        if last is not None:
            hours = max(0, (profile.now - last) / 3600)
            score -= 12 * math.exp(-hours / 18)
            if hours >= 24 * 14:
                reason = 'Wróć do ulubionych'
        # Small stable tie variation; an explicit refresh explores other matches.
        jitter = int(hashlib.sha256(f'{rotation}:{key}'.encode()).hexdigest()[:8], 16) / 0xffffffff
        score += jitter * 1.5
        score -= min(4, (exposure or {}).get(key, 0)) * 1.8
        seen.add(key)
        ranked.append((score, key, recording, group, dict(track, recommendation_reason=reason,
                                                       recommendation_artist=group)))
    counts, recordings, result = Counter(), set(), []
    while ranked and len(result) < limit:
        # Greedy diversity: spread artists throughout the list, not just a final cap.
        best = max(range(len(ranked)), key=lambda i: (
            ranked[i][0] - counts[ranked[i][3]] * (2 + abs(ranked[i][0]) * 0.5), ranked[i][1]))
        _, _, recording, group, track = ranked.pop(best)
        if counts[group] >= artist_limit or recording in recordings:
            continue
        counts[group] += 1
        recordings.add(recording)
        result.append(track)
    return result


def discovery_seeds(profile, rotation=0, limit=4):
    scores = {a: math.log1p(score) + profile.context[a] for a, score in profile.artists.items()}
    for artist, score in profile.context.items():
        scores[artist] = scores.get(artist, 0) + score
    for artist, (score, _) in profile.related.items():
        scores[artist] = scores.get(artist, 0) + score
    ordered = sorted(scores, key=lambda a: (-scores[a], a))
    if not ordered:
        return []
    # Keep two strong anchors, rotate through the remaining taste profile.
    anchors, pool = ordered[:2], ordered[2:14]
    if pool:
        start = rotation % len(pool)
        pool = pool[start:] + pool[:start]
    selected = (anchors + pool)[:limit]
    newcomers = sorted(a for a in profile.related if a not in profile.artists)
    if newcomers and len(selected) >= limit:
        newcomer = newcomers[rotation % len(newcomers)]
        if newcomer not in selected:
            selected[-1] = newcomer
    return [profile.names[a] for a in dict.fromkeys(selected)]

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
        self._rotation = int(time.time() // 86400)
        self._exposure = Counter()
        self._last_displayed = []
        self._query_round = 0
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
        if force:
            self._rotation += 1
            self._exposure.update(self._last_displayed)
            self._exposure = Counter(dict(self._exposure.most_common(500)))
        self._profile = self._make_profile()
        self._publish()
        seeds = discovery_seeds(self._profile, self._rotation)
        if not seeds:
            self.status_changed.emit(self.EMPTY_STATUS)
            return
        fingerprint = tuple(seeds)
        cache_lifetime = 60 if self._had_error or self._needs_candidates() else 1800
        if not force and fingerprint == self._fingerprint and time.monotonic() - self._last_fetch < cache_lifetime:
            self.status_changed.emit('Nie udało się pobrać wszystkich nowości. Możesz spróbować ponownie.'
                                     if self._had_error else self.READY_STATUS)
            return
        self._fingerprint = fingerprint
        self._seeds = seeds
        self._candidates = []
        self._had_error = False
        self._query_round += 1
        self.busy_changed.emit(True)
        self.status_changed.emit('Szukam muzyki dopasowanej do Ciebie…')
        self._next_seed()

    def _make_profile(self):
        groups = self._library_groups(self.playlists)
        current = self.player._current_track
        return build_profile([t for group in groups for t in group], self.history.entries,
                             context=[current] if current else (), playlist_groups=groups)

    @staticmethod
    def _library_groups(library):
        groups = []
        if library:
            for name in library.list_playlists():
                try:
                    groups.append([t for t in library.get_tracks(name) if isinstance(t, dict)])
                except (OSError, ValueError, TypeError):
                    log.warning('Cannot read playlist %s for recommendations', name)
        return groups

    def _publish(self):
        queued = getattr(self.player, '_base_queue', []) + getattr(self.player, '_priority_queue', [])
        excluded = {track_key(t) for t in queued}
        local = rank_tracks(self._profile[0].values(), self._profile, self._current_url(), limit=8,
                            excluded=excluded, rotation=self._rotation, exposure=self._exposure)
        fresh = rank_tracks(self._cache, self._profile, self._current_url(), discovery=True, limit=6,
                            excluded=excluded, rotation=self._rotation, exposure=self._exposure)
        combined = []
        counts = Counter()
        recordings = set()
        for track in fresh + local:
            artist = track['recommendation_artist']
            recording = recording_key(track)
            if counts[artist] < 2 and recording not in recordings:
                combined.append(track)
                counts[artist] += 1
                recordings.add(recording)
            if len(combined) == 8:
                break
        self._last_displayed = [track_key(t) for t in combined]
        self.updated.emit(combined)

    def _needs_candidates(self):
        return not self._cache

    def _next_seed(self):
        if self._stopped:
            return
        if not self._seeds:
            self.busy_changed.emit(False)
            if self._candidates:
                # Retain a bounded candidate pool so refreshing can surface more
                # than the same first page without growing memory indefinitely.
                pool = {}
                for track in self._candidates + self._cache:
                    pool.setdefault(track_key(track), track)
                self._cache = list(pool.values())[:240]
            if self._request_is_current():
                self._profile = self._make_profile()
            self._last_fetch = time.monotonic()
            self._publish()
            self.status_changed.emit('Nie udało się pobrać wszystkich nowości. Możesz spróbować ponownie.'
                                     if self._had_error else self.READY_STATUS)
            return
        artist = self._seeds.pop(0)
        # At most four sequential searches; foreground search keeps its own limit.
        sources = Counter(t.get('platform') for t in [*self._profile[0].values(), self.player._current_track]
                          if artist_key(artist_name(t)) == artist_key(artist))
        platform = 'SoundCloud' if sources['SoundCloud'] > sources['YouTube Music'] else 'YouTube Music'
        suffix = ('music', 'songs', 'official audio')[(self._query_round - 1) % 3]
        worker = SearchWorker(artist + ' ' + suffix, [platform], self, result_limit=12)
        self._worker = worker
        worker.results_ready.connect(self._receive)
        worker.search_error.connect(self._error)
        worker.finished.connect(self._finished)
        worker.start()

    def _receive(self, tracks):
        if not self._stopped:
            self._candidates.extend(tracks)

    def _request_is_current(self):
        return True

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
        # History affects fatigue, but unrelated history artists must not hijack
        # the active playlist. Playlist co-occurrence supplies related artists.
        groups = self._library_groups(self.library)
        session_profile = build_profile(context, {}, context=context, playlist_groups=groups)
        allowed = set(session_profile.artists) | set(session_profile.related)
        history = {k: e for k, e in self.history.entries.items()
                   if isinstance(e, dict) and isinstance(e.get('track'), dict)
                   and artist_key(artist_name(e['track'])) in allowed}
        profile = build_profile(context, history, context=context, playlist_groups=groups)
        # Discovery excludes session tracks, not all familiar library songs.
        return profile._replace(known=session_profile.known)

    def _request_is_current(self):
        return self._request_session == self.player._queue_session

    def _needs_candidates(self):
        return len(self.player._recommended_queue) < 3

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
        queued_recordings = {recording_key(t) for t in self.player._base_queue + self.player._priority_queue}
        candidates = [t for t in candidates if track_key(t) not in excluded
                      and recording_key(t) not in queued_recordings]
        tracks = rank_tracks(candidates, self._profile, self._current_url(), discovery=True, limit=12,
                             rotation=self._rotation, artist_limit=3)
        self.updated.emit(tracks)
