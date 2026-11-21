"""Portable Android library and desktop-compatible backups. No OAuth tokens here."""
import base64
import copy
import json
import math
import os
import re
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from recommendations import recommend_tracks, track_key

MAX_BYTES = 40 * 1024 * 1024
MAX_COVER = 5 * 1024 * 1024
FIELDS = ('title', 'uploader', 'artist', 'url', 'thumbnail_url', 'platform',
          'channel_url', 'channel_id', 'uploader_url', 'uploader_id')
DEFAULTS = dict(MAIN_BG_COLOR='#10131F', ACCENT_COLOR='#9672FF', LANGUAGE='pl',
                PREFETCH_ENABLED=True, BASS_GAIN=0, TREBLE_GAIN=0,
                CROSSFADE_ENABLED=False, CROSSFADE_DURATION=5)
_lock = threading.RLock()
_root = None
_data = None


def encode(data):
    raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(raw) > MAX_BYTES:
        raise ValueError('Kopia przekracza 40 MB / Backup exceeds 40 MB')
    return raw


def atomic(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def safe_name(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > 180
            or value in ('.', '..') or any(c in '/\\' or ord(c) < 32 for c in value)):
        raise ValueError('Nieprawidłowa nazwa playlisty / Invalid playlist name')
    return value


def clean_track(track):
    if not isinstance(track, dict):
        raise ValueError('Nieprawidłowy utwór / Invalid track')
    result = {}
    for key in FIELDS:
        value = track.get(key, '')
        if value is None: value = ''
        if not isinstance(value, str) or len(value) > 20000:
            raise ValueError('Nieprawidłowe metadane / Invalid metadata')
        result[key] = value
    value = track.get('duration') or 0
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Nieprawidłowy czas / Invalid duration')
    result['duration'] = value
    return result


def validate(data):
    if not isinstance(data, dict) or data.get('format') != 'music-crow-backup' or data.get('version') != 1:
        raise ValueError('To nie jest kopia Music Crow / Not a Music Crow backup')
    result = dict(format='music-crow-backup', version=1, created_at=str(data.get('created_at', ''))[:80],
                  settings={}, playlists={}, history={})
    settings = data.get('settings', {})
    if not isinstance(settings, dict):
        raise ValueError('Nieprawidłowe ustawienia / Invalid settings')
    colors = {'MAIN_BG_COLOR', 'CENTRAL_BG_START', 'CENTRAL_BG_MID', 'CENTRAL_BG_END', 'PLAYER_BAR_BG', 'ACCENT_COLOR'}
    for key, value in settings.items():
        if key in colors:
            if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{3,8}|[a-zA-Z]{1,24}|rgba\([\d.,\s]+\)', value):
                raise ValueError('Nieprawidłowy kolor / Invalid color')
        elif key == 'LANGUAGE':
            if value not in ('pl', 'en'): raise ValueError('Invalid language')
        elif key in ('BASS_GAIN', 'TREBLE_GAIN', 'CROSSFADE_DURATION'):
            lo, hi = (1, 15) if key == 'CROSSFADE_DURATION' else (-15, 15)
            if type(value) is not int or not lo <= value <= hi: raise ValueError('Invalid sound setting')
        elif key in ('PREFETCH_ENABLED', 'CROSSFADE_ENABLED'):
            if type(value) is not bool: raise ValueError('Invalid setting')
        else:
            continue
        result['settings'][key] = value
    playlists = data.get('playlists')
    if not isinstance(playlists, dict) or len(playlists) > 1000:
        raise ValueError('Nieprawidłowe playlisty / Invalid playlists')
    for name, playlist in playlists.items():
        safe_name(name)
        if not isinstance(playlist, dict) or not isinstance(playlist.get('tracks'), list) or len(playlist['tracks']) > 10000:
            raise ValueError('Nieprawidłowa playlista / Invalid playlist')
        cover = playlist.get('cover', '')
        if not isinstance(cover, str) or len(cover) > MAX_COVER * 1.4: raise ValueError('Invalid cover')
        if cover:
            raw = base64.b64decode(cover, validate=True)
            if len(raw) > MAX_COVER or not (raw.startswith(b'\x89PNG\r\n\x1a\n') or raw.startswith(b'\xff\xd8') or raw[:4] == b'RIFF'):
                raise ValueError('Nieprawidłowa okładka / Invalid cover')
        result['playlists'][name] = dict(tracks=[clean_track(t) for t in playlist['tracks']], cover=cover)
    history = data.get('history', {})
    if not isinstance(history, dict) or len(history) > 500: raise ValueError('Invalid history')
    for key, entry in history.items():
        if not isinstance(entry, dict): raise ValueError('Invalid history')
        for field in ('plays', 'last_played'):
            value = entry.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError('Invalid history')
        result['history'][key] = dict(track=clean_track(entry.get('track')), plays=entry['plays'], last_played=entry['last_played'])
    encode(result)
    return result


def initial():
    return dict(format='music-crow-backup', version=1, created_at='', settings=dict(DEFAULTS), playlists={}, history={})


def initialize(root):
    global _root, _data
    with _lock:
        _root = Path(root)
        _data = None
        path = _root / 'music-crow-android.json'
        if path.exists():
            if path.stat().st_size > MAX_BYTES: raise ValueError('Library too large')
            _data = validate(json.loads(path.read_bytes()))
        else:
            _data = initial()
            old = _root / 'library.json'
            if old.exists():
                _data['playlists']['Z telefonu'] = dict(tracks=[clean_track(t) for t in json.loads(old.read_bytes())], cover='')
            atomic(path, encode(_data))
    return True


def merge(current, incoming):
    result = copy.deepcopy(current)
    for name, playlist in incoming['playlists'].items():
        target, index = name, 1
        while target in result['playlists']:
            if result['playlists'][target] == playlist:
                target = None
                break
            target = name[:140] + (' (Google Drive)' if index == 1 else f' (Google Drive {index})')
            index += 1
        if target: result['playlists'][target] = copy.deepcopy(playlist)
    result['settings'] = {**DEFAULTS, **incoming['settings']}
    for key, entry in incoming['history'].items():
        previous = result['history'].get(key)
        if previous:
            newer = entry if entry['last_played'] > previous['last_played'] else previous
            result['history'][key] = dict(newer, plays=max(entry['plays'], previous['plays']))
        else:
            result['history'][key] = copy.deepcopy(entry)
    result['history'] = dict(sorted(result['history'].items(), key=lambda pair: pair[1]['last_played'], reverse=True)[:500])
    return result


def dispatch(action, arguments='{}'):
    global _data
    args = json.loads(arguments)
    with _lock:
        if _data is None: raise ValueError('Biblioteka nie została otwarta / Library not ready')
        if action == 'state': return json.dumps(_data, ensure_ascii=False)
        if action == 'backup':
            result = copy.deepcopy(_data)
            result['created_at'] = result['created_at'] or datetime.now(timezone.utc).isoformat()
            if not args.get('history', False): result['history'] = {}
            return encode(result).decode()
        if action == 'preview':
            incoming = validate(args['snapshot'])
            return json.dumps(dict(playlists=len(incoming['playlists']), tracks=sum(len(p['tracks']) for p in incoming['playlists'].values())))
        if action == 'recommend':
            groups = [p['tracks'] for p in _data['playlists'].values()]
            result = recommend_tracks(groups, _data['history'], context=args.get('context', []),
                                      discoveries=args.get('discoveries', []), excluded=args.get('excluded', []),
                                      rotation=args.get('rotation', 0))
            return json.dumps(result, ensure_ascii=False)
        updated = copy.deepcopy(_data)
        playlists = updated['playlists']
        if action == 'create':
            name = safe_name(args['name'].strip())
            if name in playlists: raise ValueError('Playlista już istnieje / Playlist already exists')
            playlists[name] = dict(tracks=[], cover='')
        elif action == 'rename':
            name = safe_name(args['new'].strip())
            if name in playlists: raise ValueError('Playlista już istnieje / Playlist already exists')
            playlists[name] = playlists.pop(args['name'])
        elif action == 'delete': del playlists[args['name']]
        elif action == 'add':
            name = safe_name(args['name'])
            if args.get('new_only') and name in playlists:
                raise ValueError('Playlista już istnieje. Wybierz inną nazwę / Playlist already exists. Choose another name')
            playlist = playlists.setdefault(name, dict(tracks=[], cover=''))
            keys = {track_key(t) for t in playlist['tracks']}
            for track in args['tracks']:
                track = clean_track(track)
                key = track_key(track)
                if key and key not in keys:
                    playlist['tracks'].append(track)
                    keys.add(key)
        elif action == 'remove': playlists[args['name']]['tracks'].pop(args['index'])
        elif action == 'move':
            tracks = playlists[args['name']]['tracks']
            source, dest = args['from'], args['to']
            if not 0 <= source < len(tracks) or not 0 <= dest < len(tracks): raise ValueError('Invalid position')
            tracks.insert(dest, tracks.pop(source))
        elif action == 'cover': playlists[args['name']]['cover'] = args['cover']
        elif action == 'settings': updated['settings'].update(args)
        elif action == 'restore':
            incoming = validate(args['snapshot'])
            atomic(_root / 'recovery' / f'{time.time_ns()}.json', encode(_data))
            updated = merge(updated, incoming)
        elif action == 'record':
            track = clean_track(args['track']); key = track_key(track)
            previous = updated['history'].get(key, {})
            updated['history'][key] = dict(track=track, plays=previous.get('plays', 0) + 1, last_played=time.time())
            updated['history'] = dict(sorted(updated['history'].items(), key=lambda pair: pair[1]['last_played'], reverse=True)[:500])
        else: raise ValueError('Unknown action')
        updated['created_at'] = datetime.now(timezone.utc).isoformat()
        updated = validate(updated)
        atomic(_root / 'music-crow-android.json', encode(updated))
        _data = updated
        return json.dumps(updated, ensure_ascii=False)
