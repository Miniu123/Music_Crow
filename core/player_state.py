"""Small, device-local playback preferences that are not part of cloud backups."""
import json

from core.app_paths import config_dir

DEFAULT_VOLUME = 80


def state_path():
    return config_dir() / 'player_state.json'


def load_state():
    try:
        data = json.loads(state_path().read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def load_volume():
    value = load_state().get('volume', DEFAULT_VOLUME)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return DEFAULT_VOLUME
    return max(0, min(100, int(value)))


def save_volume(volume):
    from core.cloud_backup import atomic_write, encode
    state = load_state()
    state['volume'] = max(0, min(100, int(volume)))
    try:
        atomic_write(state_path(), encode(state))
    except OSError as error:
        print(f'Error saving player state: {error}')


MAX_RECENT_SEARCHES = 8


def load_recent_searches():
    values = load_state().get('recent_searches', [])
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str) and value.strip()][:MAX_RECENT_SEARCHES]


def save_recent_searches(values):
    from core.cloud_backup import atomic_write, encode
    state = load_state()
    state['recent_searches'] = [str(value) for value in values][:MAX_RECENT_SEARCHES]
    try:
        atomic_write(state_path(), encode(state))
    except OSError as error:
        print(f'Error saving player state: {error}')


def remember_search(query):
    query = ' '.join(str(query).split())
    if not query:
        return load_recent_searches()
    values = [query] + [value for value in load_recent_searches() if value.casefold() != query.casefold()]
    save_recent_searches(values)
    return values[:MAX_RECENT_SEARCHES]
