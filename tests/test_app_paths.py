import unittest
from pathlib import Path
from unittest.mock import patch
from core.app_paths import config_dir, cache_dir


class AppPathTests(unittest.TestCase):
    def test_flatpak_xdg_directories_are_used(self):
        with patch.dict('os.environ', {'XDG_CONFIG_HOME': '/sandbox/config', 'XDG_CACHE_HOME': '/sandbox/cache'}):
            self.assertEqual(config_dir(), Path('/sandbox/config/music-crow'))
            self.assertEqual(cache_dir(), Path('/sandbox/cache/music-crow'))

    def test_missing_or_relative_xdg_paths_preserve_existing_locations(self):
        for value in ('', 'relative/path'):
            with patch.dict('os.environ', {'XDG_CONFIG_HOME': value, 'XDG_CACHE_HOME': value}):
                self.assertEqual(config_dir(), Path.home() / '.config/music-crow')
                self.assertEqual(cache_dir(), Path.home() / '.cache/music-crow')
