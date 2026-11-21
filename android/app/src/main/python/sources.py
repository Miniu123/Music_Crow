"""Bounded yt-dlp searches and audio URL resolution, executed off the UI thread."""
import json
import re
import time
from urllib.parse import urlparse, parse_qs, urlencode
import yt_dlp

HOSTS = {'youtube.com', 'www.youtube.com', 'music.youtube.com', 'm.youtube.com', 'youtu.be', 'soundcloud.com', 'www.soundcloud.com', 'on.soundcloud.com'}

class QuietLog:
    def debug(self, message): pass
    def info(self, message): pass
    def warning(self, message): pass
    def error(self, message): pass


def supported(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.hostname in HOSTS and not parsed.username


def options(**extra):
    return dict(quiet=True, no_warnings=True, logger=QuietLog(), socket_timeout=15,
                retries=1, extractor_retries=1, cachedir=False, **extra)


def track(item, platform):
    if item.get('availability') == 'private' or item.get('title') in ('[Private video]', '[Deleted video]'):
        return None
    url = item.get('webpage_url') or item.get('url') or ''
    if not supported(url): return None
    images = item.get('thumbnails') or []
    thumb = item.get('thumbnail') or next((t['url'] for t in reversed(images) if t.get('url', '').startswith('https://')), '')
    result = dict(title=item.get('title') or 'Utwór', url=url, uploader=item.get('uploader') or item.get('channel') or '',
                  artist=item.get('artist') or '', duration=item.get('duration') or 0, thumbnail_url=thumb, platform=platform)
    result['is_live'] = bool(item.get('is_live'))
    for key in ('channel_url', 'channel_id', 'uploader_url', 'uploader_id'):
        result[key] = item.get(key) or ''
    return result


def extract_list(target, platform, offset=0, count=30):
    with yt_dlp.YoutubeDL(options(extract_flat='in_playlist', skip_download=True,
                                 ignoreerrors=True, playliststart=offset+1, playlistend=offset+count)) as dl:
        result = dl.extract_info(target, download=False)
    if not result: raise ValueError('Brak wyników. Sprawdź połączenie / No results. Check connection')
    entries = list(result['entries']) if result.get('entries') is not None else [result]
    tracks = [t for item in entries if item and (t := track(item, platform))]
    return dict(tracks=tracks, more=len(entries) >= count, title=result.get('title') or '',
                skipped=len(entries) - len(tracks))


def search(query, platform='YouTube Music'):
    query = query.strip()[:500]
    if not query: return json.dumps(dict(tracks=[], more=False))
    if query.startswith('https://'):
        if not supported(query): raise ValueError('Obsługiwane linki: YouTube i SoundCloud / Supported links: YouTube and SoundCloud')
        target = query
        platform = 'SoundCloud' if 'soundcloud.com' in urlparse(query).hostname else 'YouTube Music'
    else:
        target = ('scsearch20:' if platform == 'SoundCloud' else 'ytsearch20:') + query
    return json.dumps(extract_list(target, platform), ensure_ascii=False)


def discover(artist, platform='YouTube Music', allow_remixes=False):
    query = str(artist).strip()[:250]
    if platform != 'SoundCloud':
        query += ' official audio'
        if not allow_remixes:
            query += ' -remix -remiks -bootleg -mashup -nightcore -slowed -"sped up"'
    return search(query, platform)


def browse(raw, offset=0):
    item = json.loads(raw)
    source = channel_url(item)
    if not supported(source):
        if supported(item.get('url', '')):
            try:
                with yt_dlp.YoutubeDL(options(skip_download=True, noplaylist=True)) as dl:
                    data = dl.extract_info(item['url'], download=False)
                    source = channel_url(data or {})
            except yt_dlp.utils.DownloadError:
                source = ''
        if not supported(source):
            result = json.loads(search(item.get('artist') or item.get('uploader') or '', item.get('platform', 'YouTube Music')))
            result['fallback'] = True
            return json.dumps(result, ensure_ascii=False)
    platform = 'SoundCloud' if 'soundcloud.com' in urlparse(source).hostname else 'YouTube Music'
    source = source.rstrip('/')
    if platform == 'YouTube Music' and not source.endswith('/videos'): source += '/videos'
    if platform == 'SoundCloud' and not source.endswith('/tracks'): source += '/tracks'
    return json.dumps(extract_list(source, platform, int(offset)), ensure_ascii=False)


def resolve(url):
    if not supported(url): raise ValueError('Nieobsługiwane źródło / Unsupported source')
    with yt_dlp.YoutubeDL(options(format='bestaudio[protocol=https]/bestaudio[protocol=http]/best[protocol=https]', noplaylist=True, skip_download=True)) as dl:
        data = dl.extract_info(url, download=False)
    stream = data.get('url', '')
    if not stream.startswith('https://'): raise ValueError('Brak strumienia audio / Audio stream unavailable')
    return json.dumps(dict(url=stream, headers=data.get('http_headers') or {}, title=data.get('title') or '',
                           duration=data.get('duration') or 0, resolved_at=time.time()))


def page(url, offset=0):
    if not supported(url): raise ValueError('Nieobsługiwany link / Unsupported link')
    platform = 'SoundCloud' if 'soundcloud.com' in urlparse(url).hostname else 'YouTube Music'
    return json.dumps(extract_list(url, platform, int(offset)), ensure_ascii=False)


def playlist_url(raw):
    url = str(raw).strip()
    if not supported(url):
        raise ValueError('Wklej link HTTPS do playlisty YouTube Music, YouTube lub SoundCloud / Paste a playlist link')
    parsed = urlparse(url)
    if 'soundcloud.com' in parsed.hostname:
        return url
    identifier = parse_qs(parsed.query).get('list', [''])[0]
    if not re.fullmatch(r'[A-Za-z0-9_-]{2,200}', identifier):
        raise ValueError('Link nie zawiera playlisty. W YouTube Music wybierz Udostępnij na ekranie playlisty / Share the playlist, not a song')
    if identifier in ('WL', 'LL', 'LM') or identifier.startswith('RD'):
        raise ValueError('Zapisz utwory w zwykłej playliście i udostępnij jej link. Listy polubionych i radio wymagają konta / Share a saved playlist instead of likes or radio')
    # Ignore the selected video/index and sharing parameters: always fetch the complete list.
    return 'https://www.youtube.com/playlist?' + urlencode({'list': identifier})


def import_playlist(url):
    url = playlist_url(url)
    platform = 'SoundCloud' if 'soundcloud.com' in urlparse(url).hostname else 'YouTube Music'
    try:
        result = extract_list(url, platform, count=10001)
    except (ValueError, yt_dlp.utils.DownloadError) as error:
        raise ValueError('Nie udało się pobrać playlisty. Sprawdź połączenie i ustaw widoczność playlisty na publiczną lub niepubliczną / Check connection and use a public or unlisted playlist') from error
    if len(result['tracks']) > 10000 or result['more']:
        raise ValueError('Playlista przekracza limit 10000 utworów / Playlist exceeds 10000 tracks')
    if not result['tracks']:
        raise ValueError('Playlista jest pusta albo jej utwory są niedostępne / Playlist is empty or unavailable')
    return json.dumps(result, ensure_ascii=False)


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
