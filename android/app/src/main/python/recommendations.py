"""Pure ranking functions ported from core/recommendations.py (MIT)."""
import hashlib, math, re, time, unicodedata
from collections import Counter
from typing import NamedTuple
from urllib.parse import urlparse, parse_qs

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
    artist = str(track.get('artist') or '').strip()
    if not artist:
        # Search results often name a label or lyrics channel as the uploader.
        # Prefer a conventional explicit "Artist - Song" credit in that case.
        parts = re.split(r'\s+[-–—]\s+', str(track.get('title') or ''), maxsplit=1)
        credit = parts[0].strip() if len(parts) == 2 else ''
        if 2 <= len(credit) <= 80 and not re.match(r'(?:remaster(?:ed)?|live|acoustic|instrumental|official|remix|version|[0-9]{4})\b', parts[1], re.I) and not re.search(r'\b(official|lyrics?|mix|playlist|full album)\b', credit, re.I):
            artist = re.split(r'\s+(?:feat\.?|ft\.?|featuring)\s+', credit, maxsplit=1, flags=re.I)[0]
        else:
            artist = str(track.get('uploader') or '').strip()
    artist = re.sub(r'\s*-\s*Topic$', '', artist, flags=re.I).strip()
    return '' if artist.lower() in ('unknown artist', 'unknown', '') else artist

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


def is_remix(track):
    title = normalized(track.get('title'))
    return bool(re.search(r'\b(remix(?:es)?|remiks|bootleg|mashup|nightcore|slowed|sped ?up|speed ?up|bass boosted|club edit|dj edit)\b', title))


def credited_artists(track):
    """Match real credits, never an artist name appearing anywhere in a song title."""
    credits = {artist_key(artist_name(track))}
    featured = re.search(r'\b(?:feat\.?|ft\.?|featuring)\s+([^\]\)\(\[|]+)',
                         str(track.get('title') or ''), flags=re.I)
    if featured:
        names = re.split(r'\s[-–—]\s', featured[1], maxsplit=1)[0]
        credits.update(artist_key(name.strip(' .-')) for name in
                       re.split(r'\s*(?:,|&|\band\b)\s*', names, flags=re.I))
    return credits - {''}

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
    for track in list(known.values()) + context:
        source = artist_key(artist_name(track))
        if not source or (session and source not in session):
            continue
        credit = re.search(r'\b(?:feat\.?|ft\.?|featuring)\s+([^\]\)\(\[|]+)',
                           str(track.get('title') or ''), flags=re.I)
        if credit:
            credited = re.split(r'\s[-–—]\s', credit[1], maxsplit=1)[0]
            for name in re.split(r'\s*(?:,|&|\band\b)\s*', credited, flags=re.I)[:3]:
                name = name.strip(' .-')
                group = artist_key(name)
                if 2 <= len(group) <= 60 and group not in session and group not in related:
                    related[group] = (1.5, names[source])
                    names[group] = name
    # Context is also needed to exclude alternate uploads of the current recording,
    # even when this song has never been saved in the library.
    for track in context:
        key = track_key(track)
        if key and key not in known:
            known[key] = track
    return TasteProfile(known, weights, artists, names, recent, session, related, now)

def rank_tracks(candidates, profile, current_url='', discovery=False, limit=8,
                *, excluded=(), rotation=0, artist_limit=2, exposure=None, focused=False, mixed=False, allow_remixes=False):
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
        is_discovery = discovery or (mixed and key not in known)
        if is_discovery and (key in known or recording in known_recordings):
            continue
        duration = track.get('duration') or 0
        if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
            continue
        if (is_discovery or focused) and (track.get('is_live') or duration > 1200 or 0 < duration < 45
                          or re.search(r'\b(full album|compilation|greatest hits|1 hour|10 hours)\b', title)):
            continue
        if not allow_remixes and is_remix(track):
            continue
        artist = artist_key(artist_name(track))
        affinities = (set(profile.context) | set(profile.related)) if focused else (set(artists) | set(profile.context) | set(profile.related))
        matches = sorted(affinities & credited_artists(track))
        if (is_discovery or focused) and not matches:
            continue
        def affinity(a):
            taste = min(2, math.log1p(artists[a])) if focused else math.log1p(artists[a])
            return taste + profile.context[a] + profile.related.get(a, (0, ''))[0]
        matched = max(matches, key=lambda a: (affinity(a), a)) if matches else artist
        group = artist or matched or key
        familiarity = min(3, math.log1p(weights[key])) if focused else math.log1p(weights[key])
        score = 2 * familiarity + 2 * affinity(matched)
        reason = known.get(key, {}).get('recommendation_reason', 'Z Twojej biblioteki')
        if is_discovery:
            score += 3
            if matched in profile.context:
                reason = 'Pasuje do teraz: ' + names[matched]
            elif matched in profile.related:
                reason = 'Powiązane przez playlisty: ' + profile.related[matched][1]
            else:
                reason = 'Na podstawie: ' + names[matched]
        if focused and matched in profile.context:
            reason = 'Pasuje do teraz: ' + names[matched]
        elif focused and matched in profile.related:
            reason = 'Powiązane z: ' + profile.related[matched][1]
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
    scores = {} if profile.context else {a: math.log1p(score) for a, score in profile.artists.items()}
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


def recommend_tracks(groups, entries, *, context=(), discoveries=(), excluded=(), rotation=0):
    """Rank one combined pool with session relevance and a shared diversity cap."""
    context = [t for t in context if isinstance(t, dict) and track_key(t)]
    profile = build_profile([t for group in groups for t in group], entries,
                            context=context, playlist_groups=groups)
    blocked = {track_key(t) for t in list(excluded) + context if isinstance(t, dict)}
    # Include complete excluded metadata so alternate uploads cannot slip back in.
    for t in excluded:
        if isinstance(t, dict) and t.get('title'):
            profile.known.setdefault(track_key(t), t)
    candidates = list(discoveries) + list(profile.known.values())
    ranked = rank_tracks(candidates, profile, limit=20, excluded=blocked,
                         rotation=rotation, artist_limit=3, focused=bool(profile.context), mixed=True,
                         allow_remixes=bool(context and is_remix(context[-1])))
    return dict(tracks=ranked, seeds=discovery_seeds(profile, rotation),
                allow_remixes=bool(context and is_remix(context[-1])))
