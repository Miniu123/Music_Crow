"""Application data locations, including Flatpak's persistent XDG directories."""
import os
from pathlib import Path


def _xdg_directory(variable, fallback):
    value = os.environ.get(variable, '')
    return Path(value) if value and Path(value).is_absolute() else Path.home() / fallback


def config_dir():
    return _xdg_directory('XDG_CONFIG_HOME', '.config') / 'music-crow'


def cache_dir():
    return _xdg_directory('XDG_CACHE_HOME', '.cache') / 'music-crow'
