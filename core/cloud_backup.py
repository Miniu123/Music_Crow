"""Portable, validated Music Crow backups. OAuth files and audio are never included."""
import base64
import copy
import json
import math
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from PyQt6.QtGui import QColor, QImage
from core.theme_manager import DEFAULT_THEME

MAX_BACKUP_BYTES = 40 * 1024 * 1024
MAX_COVER_BYTES = 5 * 1024 * 1024
TRACK_FIELDS = ('title', 'uploader', 'artist', 'url', 'thumbnail_url', 'platform',
                'channel_url', 'channel_id', 'uploader_url', 'uploader_id')


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def encode(data):
    result = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(result) > MAX_BACKUP_BYTES:
        raise ValueError('Kopia przekracza limit 40 MB.')
    return result


def safe_name(name):
    if (not isinstance(name, str) or not name.strip() or len(name) > 180
            or name in ('.', '..') or any(c in name for c in '/\\\x00')
            or any(ord(c) < 32 for c in name)):
        raise ValueError('Nieprawidłowa kopia danych.')
    return name


def clean_track(track):
    if not isinstance(track, dict):
        raise ValueError('Nieprawidłowa kopia danych.')
    result = {}
    for field in TRACK_FIELDS:
        value = track.get(field, '')
        if not isinstance(value, str) or len(value) > 20000:
            raise ValueError('Nieprawidłowa kopia danych.')
        result[field] = value
    duration = track.get('duration') or 0
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
        raise ValueError('Nieprawidłowa kopia danych.')
    result['duration'] = duration
    return result


def clean_theme(theme):
    if not isinstance(theme, dict):
        raise ValueError('Nieprawidłowa kopia danych.')
    result = {}
    for key, value in theme.items():
        if key not in DEFAULT_THEME:
            continue
        valid = False
        if key == 'LANGUAGE':
            valid = value in ('pl', 'en')
        elif key.endswith('_ENABLED'):
            valid = isinstance(value, bool)
        elif key in ('BASS_GAIN', 'TREBLE_GAIN', 'CROSSFADE_DURATION'):
            low, high = (1, 15) if key == 'CROSSFADE_DURATION' else (-15, 15)
            valid = type(value) is int and low <= value <= high
        elif isinstance(value, str):
            valid = QColor(value).isValid() or bool(re.fullmatch(
                r'rgba\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*(?:0(?:\.\d+)?|1(?:\.0+)?)\s*\)', value))
        if not valid:
            raise ValueError('Nieprawidłowa kopia danych.')
        result[key] = value
    return result


def validate_snapshot(data):
    if not isinstance(data, dict) or data.get('format') != 'music-crow-backup' or data.get('version') != 1:
        raise ValueError('Nieprawidłowa kopia danych.')
    result = {'format': 'music-crow-backup', 'version': 1,
              'created_at': str(data.get('created_at', ''))[:80],
              'settings': clean_theme(data.get('settings', {})), 'playlists': {}, 'history': {}}
    playlists = data.get('playlists')
    if not isinstance(playlists, dict) or len(playlists) > 1000:
        raise ValueError('Nieprawidłowa kopia danych.')
    for name, playlist in playlists.items():
        safe_name(name)
        if not isinstance(playlist, dict) or not isinstance(playlist.get('tracks'), list) or len(playlist['tracks']) > 10000:
            raise ValueError('Nieprawidłowa kopia danych.')
        item = {'tracks': [clean_track(t) for t in playlist['tracks']], 'cover': ''}
        cover = playlist.get('cover', '')
        if cover:
            if not isinstance(cover, str) or len(cover) > MAX_COVER_BYTES * 1.4:
                raise ValueError('Nieprawidłowa okładka w kopii.')
            raw = base64.b64decode(cover, validate=True)
            if len(raw) > MAX_COVER_BYTES or QImage.fromData(raw).isNull():
                raise ValueError('Nieprawidłowa okładka w kopii.')
            item['cover'] = cover
        result['playlists'][name] = item
    history = data.get('history', {})
    if not isinstance(history, dict) or len(history) > 500:
        raise ValueError('Nieprawidłowa kopia danych.')
    for key, entry in history.items():
        if not isinstance(entry, dict):
            raise ValueError('Nieprawidłowa kopia danych.')
        plays, last = entry.get('plays'), entry.get('last_played')
        if (not isinstance(plays, (int, float)) or not math.isfinite(plays) or plays < 0
                or not isinstance(last, (int, float)) or not math.isfinite(last) or last < 0):
            raise ValueError('Nieprawidłowa kopia danych.')
        result['history'][key] = {'track': clean_track(entry.get('track')), 'plays': plays, 'last_played': last}
    return result


def collect_snapshot(root, include_history=True):
    root = Path(root)
    snapshot = {'format': 'music-crow-backup', 'version': 1,
                'created_at': datetime.now(timezone.utc).isoformat(), 'settings': {}, 'playlists': {}, 'history': {}}
    if (root / 'theme.json').exists():
        snapshot['settings'] = json.loads((root / 'theme.json').read_text())
    for path in sorted((root / 'playlists').glob('*.json')):
        if path.is_symlink():
            continue
        item = json.loads(path.read_text())
        cover = root / 'covers' / (path.stem + '.png')
        raw = b''
        if cover.is_file() and not cover.is_symlink():
            if cover.stat().st_size > MAX_COVER_BYTES:
                raise ValueError('Okładka przekracza limit 5 MB.')
            raw = cover.read_bytes()
        snapshot['playlists'][path.stem] = {'tracks': item.get('tracks', []), 'cover': base64.b64encode(raw).decode()}
    if include_history and (root / 'listening_history.json').exists():
        snapshot['history'] = json.loads((root / 'listening_history.json').read_text())
    snapshot = validate_snapshot(snapshot)
    encode(snapshot)
    return snapshot


def restore_snapshot(root, snapshot):
    """Merge playlists without losing collisions; keep a recovery copy and roll back failed writes."""
    root = Path(root)
    snapshot = validate_snapshot(snapshot)
    current = collect_snapshot(root)
    recovery = root / 'recovery' / (datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
    atomic_write(recovery, encode(current))
    writes = {}
    occupied = set(current['playlists'])
    for name, item in snapshot['playlists'].items():
        target = name
        if target in occupied:
            if current['playlists'].get(target) == item:
                continue
            stem = name[:140]
            target = stem + ' (Google Drive)'
            number = 2
            while target in occupied:
                if current['playlists'].get(target) == item:
                    target = None
                    break
                target = f'{stem} (Google Drive {number})'
                number += 1
            if target is None:
                continue
        occupied.add(target)
        cover_path = root / 'covers' / (target + '.png')
        playlist = {'name': target, 'tracks': item['tracks'], 'created_at': snapshot['created_at'],
                    'cover_image': str(cover_path) if item['cover'] else ''}
        writes[root / 'playlists' / (target + '.json')] = encode(playlist)
        if item['cover']:
            writes[cover_path] = base64.b64decode(item['cover'])
    writes[root / 'theme.json'] = encode({**DEFAULT_THEME, **snapshot['settings']})
    history = copy.deepcopy(current['history'])
    for key, entry in snapshot['history'].items():
        local = history.get(key)
        if local:
            newer = entry if entry['last_played'] > local['last_played'] else local
            history[key] = dict(newer, plays=max(local['plays'], entry['plays']))
        else:
            history[key] = entry
    history = dict(sorted(history.items(), key=lambda pair: pair[1]['last_played'], reverse=True)[:500])
    writes[root / 'listening_history.json'] = encode(history)
    previous = {path: path.read_bytes() if path.exists() else None for path in writes}
    changed = []
    try:
        for path, payload in writes.items():
            # Refuse symbolic links inside the application data directory.
            if path.is_symlink() or path.parent.is_symlink():
                raise ValueError('Nieprawidłowa ścieżka danych.')
            atomic_write(path, payload)
            changed.append(path)
    except Exception:
        for path in reversed(changed):
            if previous[path] is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, previous[path])
        raise
    return recovery
