import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import sys
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from core import playlist_manager as playlists
from core.player import MusicPlayer
from core.search_engine import SearchWorker, run_extractor
from ui.search_page import SearchPage, SearchResultCard, PlatformFilterBar

app = QApplication.instance() or QApplication([])


class PlaylistTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for name in ('PLAYLISTS_DIR', 'COVERS_DIR'):
            path = str(Path(self.temp.name) / name)
            patcher = patch.object(playlists, name, path)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.manager = playlists.PlaylistManager()

    def test_create_add_rename_persist(self):
        self.assertTrue(self.manager.create_playlist('Muzyka'))
        self.assertFalse(self.manager.create_playlist('Muzyka'))
        track = {'title': 'Test', 'url': 'https://example.com/song'}
        self.manager.add_track('Muzyka', track)
        self.manager.add_track('Muzyka', track)
        self.assertTrue(self.manager.rename_playlist('Muzyka', 'Nowa'))
        self.assertEqual(self.manager.get_tracks('Nowa'), [track])
        self.assertEqual(self.manager.list_playlists(), ['Nowa'])
        self.assertFalse(list(Path(playlists.PLAYLISTS_DIR).glob('*.tmp')))

    def test_empty_name_rejected(self):
        self.assertFalse(self.manager.create_playlist('  '))

    def test_failed_write_preserves_original(self):
        self.manager.create_playlist('Safe')
        original = Path(self.manager._path('Safe')).read_bytes()
        with patch.object(playlists.os, 'replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                self.manager.add_track('Safe', {'url': 'new'})
        self.assertEqual(Path(self.manager._path('Safe')).read_bytes(), original)
        self.assertFalse(list(Path(playlists.PLAYLISTS_DIR).glob('*.tmp')))


class PlayerTests(unittest.TestCase):
    def setUp(self):
        patcher = patch('core.player.mpv.MPV')
        factory = patcher.start()
        self.addCleanup(patcher.stop)
        factory.side_effect = [MagicMock(), MagicMock()]
        self.player = MusicPlayer()
        self.addCleanup(self.player.shutdown)

    def test_queue_does_not_mutate_playlist(self):
        tracks = [{'url': 'a'}, {'url': 'b'}]
        self.player.play_queue(tracks)
        self.player.next_track()
        self.assertNotIn('_source', tracks[0])
        self.assertIsNot(self.player._base_queue, tracks)

    def test_stop_stops_both_engines(self):
        self.player._is_crossfading = True
        self.player.stop()
        self.assertFalse(self.player._is_crossfading)
        for engine in self.player.players:
            engine.command.assert_called_with('stop')

    def test_invalid_start_index_is_clamped(self):
        self.player.play_queue([{'url': 'a'}], 99)
        self.assertEqual(self.player._current_track['url'], 'a')


class SearchTests(unittest.TestCase):
    def test_default_sources_are_real_sources(self):
        self.assertEqual(SearchWorker('music').platforms, ['YouTube Music', 'SoundCloud'])
        self.assertEqual(len(PlatformFilterBar().buttons), 2)

    def test_finished_search_can_be_repeated(self):
        page = SearchPage(MagicMock())
        with patch('core.search_engine.run_extractor', return_value=subprocess.CompletedProcess([], 0, '', '')):
            for _ in range(2):
                page.perform_search('music')
                page._current_worker.wait()
                app.processEvents()
                self.assertIsNone(page._current_worker)
                self.assertFalse(page._workers)
        page.shutdown()

    def test_subprocess_timeout(self):
        with self.assertRaises(Exception) as error:
            run_extractor(SearchWorker(''), [sys.executable, '-c', 'import time; time.sleep(2)'], 0.1)
        self.assertEqual(type(error.exception).__name__, 'TimeoutExpired')

    def test_thumbnail_is_not_cleared(self):
        card = SearchResultCard({'title': 'Test'})
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.GlobalColor.red)
        card.set_thumbnail(pixmap)
        self.assertFalse(card.thumbnail_label.pixmap().isNull())


if __name__ == '__main__':
    unittest.main()
