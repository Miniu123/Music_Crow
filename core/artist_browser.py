"""Bounded, cancellable browsing of a track's source channel."""
import json
import re
import subprocess
import sys
from urllib.parse import urlparse
from PyQt6.QtCore import QThread, pyqtSignal
from core.recommendations import artist_name, track_key
from core.search_engine import run_extractor, channel_metadata, SearchWorker

PAGE_SIZE = 30


def channel_url(track):
    for key in ('channel_url', 'uploader_url'):
        value = track.get(key) or ''
        parsed = urlparse(value)
        if parsed.scheme != 'https' or parsed.username or parsed.password:
            continue
        parts = parsed.path.strip('/').split('/')
        if parsed.hostname in ('www.youtube.com', 'youtube.com', 'music.youtube.com'):
            if ((len(parts) >= 2 and parts[0] in ('channel', 'c', 'user'))
                    or (parts and parts[0].startswith('@') and len(parts[0]) > 1)):
                base = '/'.join(parts[:1] if parts[0].startswith('@') else parts[:2])
                return f'https://www.youtube.com/{base}/videos'
        if parsed.hostname in ('soundcloud.com', 'www.soundcloud.com'):
            if parts and parts[0] and parts[0] not in ('discover', 'search', 'you', 'charts'):
                return f'https://soundcloud.com/{parts[0]}/tracks'
    identifier = track.get('channel_id') or ''
    if re.fullmatch(r'UC[\w-]{22}', identifier):
        return f'https://www.youtube.com/channel/{identifier}/videos'
    return ''


def supported_track_url(url):
    parsed = urlparse(url or '')
    return (parsed.scheme == 'https' and parsed.hostname in (
        'youtube.com', 'www.youtube.com', 'music.youtube.com', 'youtu.be',
        'soundcloud.com', 'www.soundcloud.com') and not parsed.username)


class ArtistWorker(QThread):
    results_ready = pyqtSignal(list)
    source_ready = pyqtSignal(dict)
    search_error = pyqtSignal(str)

    def __init__(self, track, offset=0, parent=None):
        super().__init__(parent)
        self.track = dict(track)
        self.offset = offset

    def _extract(self, target, *options):
        proc = run_extractor(self, [sys.executable, '-m', 'yt_dlp', '--ignore-config',
            '--dump-single-json', '--no-warnings', '--skip-download', '--socket-timeout', '15',
            *options, '--', target], timeout=45)
        if self.isInterruptionRequested():
            raise InterruptedError()
        if not proc.stdout.strip():
            raise ValueError('empty extractor response')
        data = json.loads(proc.stdout)
        if not isinstance(data, dict):
            raise ValueError('invalid extractor response')
        if proc.returncode and not data.get('entries'):
            raise ValueError('extractor failed')
        return data

    def run(self):
        try:
            track = dict(self.track)
            source = channel_url(track)
            # Old playlists did not retain channel identity. Resolve it from the song.
            if not source and not track.get('_artist_fallback') and supported_track_url(track.get('url')):
                try:
                    data = self._extract(track['url'], '--no-playlist')
                    track.update(channel_metadata(data))
                    if data.get('uploader') or data.get('channel'):
                        track['uploader'] = data.get('uploader') or data['channel']
                    source = channel_url(track)
                except (ValueError, subprocess.TimeoutExpired):
                    pass
            name = artist_name(track)
            if not source and not name:
                self.search_error.emit('Brak informacji o artyście lub kanale tego utworu.')
                return
            platform = 'SoundCloud' if (source.startswith('https://soundcloud.com/')
                        or (not source and track.get('platform') == 'SoundCloud')) else 'YouTube Music'
            fallback = not bool(source)
            track['_artist_fallback'] = fallback
            self.source_ready.emit({'track': track, 'fallback': fallback, 'url': source})
            if fallback:
                prefix = 'scsearch30:' if platform == 'SoundCloud' else 'ytsearch30:'
                target = prefix + name
                data = self._extract(target, '--flat-playlist', '--ignore-errors')
            else:
                data = self._extract(source, '--flat-playlist', '--ignore-errors',
                                     '--playlist-start', str(self.offset + 1),
                                     '--playlist-end', str(self.offset + PAGE_SIZE))
            entries = data.get('entries') or []
            if not isinstance(entries, list):
                raise ValueError('invalid channel entries')
            tracks, seen = [], set()
            for item in entries:
                if not isinstance(item, dict) or item.get('availability') in ('private', 'premium_only', 'subscriber_only'):
                    continue
                url = item.get('webpage_url') or item.get('url') or ''
                if not supported_track_url(url) or item.get('_type') in ('playlist', 'multi_video'):
                    continue
                result = {**(channel_metadata(track) if not fallback else {}), **channel_metadata(item),
                    'title': item.get('title') or 'Unknown Title',
                    'uploader': item.get('uploader') or item.get('channel') or (name if not fallback else ''),
                    'url': url, 'platform': platform, 'duration': item.get('duration') or 0,
                    'thumbnail_url': SearchWorker._best_thumbnail(item)}
                key = track_key(result)
                if key not in seen:
                    tracks.append(result)
                    seen.add(key)
            # Raw entries determine pagination even if some entries cannot be played.
            self.has_more = not fallback and len(entries) >= PAGE_SIZE
            self.results_ready.emit(tracks)
        except InterruptedError:
            return
        except (OSError, ValueError, subprocess.TimeoutExpired, TypeError):
            self.search_error.emit('Nie udało się wczytać kanału. Sprawdź połączenie i spróbuj ponownie.')
