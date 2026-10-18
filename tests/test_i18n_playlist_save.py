import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QLabel, QDialog
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from core.i18n import language_manager, text, tr, set_text
from core.theme_manager import ThemeManager
from core import playlist_manager as playlists
from ui.settings_dialog import SettingsDialog
from ui.main_window import MainWindow
from ui.playlist_menu import build_playlist_menu

app = QApplication.instance() or QApplication([])


class LocalDataTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = ThemeManager()
        self.settings.current_theme['LANGUAGE'] = 'pl'
        self.settings.config_dir = Path(self.temp.name)
        self.settings.config_path = Path(self.temp.name) / 'theme.json'
        language_manager.configure(self.settings)
        self.addCleanup(lambda: language_manager.set_language('pl', persist=False))
        for field in ('PLAYLISTS_DIR', 'COVERS_DIR'):
            patcher = patch.object(playlists, field, str(Path(self.temp.name) / field))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.manager = playlists.PlaylistManager()


class LanguageTests(LocalDataTest):
    def test_switch_is_live_and_reversible(self):
        label = text(QLabel(), 'Proponowane dla Ciebie')
        language_manager.set_language('en')
        self.assertEqual(label.text(), 'Recommended for you')
        language_manager.set_language('pl')
        self.assertEqual(label.text(), 'Proponowane dla Ciebie')

    def test_setting_is_persisted_and_read_on_startup(self):
        language_manager.set_language('en')
        self.assertEqual(json.loads(self.settings.config_path.read_text())['LANGUAGE'], 'en')
        self.settings.current_theme = {'LANGUAGE': 'pl'}
        self.settings.load_theme()
        language_manager.configure(self.settings)
        self.assertEqual(language_manager.language, 'en')

    def test_settings_selector_updates_open_dialog(self):
        dialog = SettingsDialog(self.settings)
        dialog.language_combo.setCurrentIndex(dialog.language_combo.findData('en'))
        self.assertEqual(dialog.windowTitle(), 'Settings')
        self.assertTrue(any(label.text() == 'Application language' for label in dialog.findChildren(QLabel)))
        self.assertEqual(self.settings.current_theme['LANGUAGE'], 'en')
        dialog.close()

    def test_counts_reasons_status_and_tooltips_translate(self):
        count = text(QLabel(), 'Playlisty: 3')
        reason = text(QLabel(), 'Na podstawie: M83')
        status = text(QLabel(), 'Następny utwór gotowy')
        set_text(status, 'Dodaj do playlisty', 'toolTip')
        language_manager.set_language('en')
        self.assertEqual(count.text(), 'Playlists: 3')
        self.assertEqual(reason.text(), 'Based on: M83')
        self.assertEqual(status.text(), 'Next track ready')
        self.assertEqual(status.toolTip(), 'Add to playlist')

    def test_switch_does_not_change_playback_or_user_content(self):
        with patch('core.player.mpv.MPV', side_effect=[MagicMock(), MagicMock()]), patch('ui.main_window.MprisIntegration'):
            window = MainWindow(self.settings)
            self.addCleanup(window.close)
            window.main_content.home_page.recommendations.shutdown()
            window.main_content.playback_recommendations.shutdown()
            window.player.prefetcher.shutdown()
            # A title and playlist deliberately matching a translatable UI string.
            track = {'title': 'Ustawienia', 'uploader': 'Artysta', 'url': 'https://example.com/song'}
            window.playlist_manager.create_playlist('Ustawienia')
            window.playlist_manager.add_track('Ustawienia', track)
            window.player.play_queue([track])
            window.main_content.playlist_page.load_playlist('Ustawienia')
            before = [engine.play.call_count for engine in window.player.players]
            language_manager.set_language('en')
            self.assertEqual(window.sidebar.btn_search.text().strip(), 'Search')
            self.assertEqual(window.player_bar.track_title.text(), 'Ustawienia')
            self.assertEqual(window.main_content.playlist_page.playlist_title.text(), 'Ustawienia')
            self.assertEqual(window.player._current_track['url'], track['url'])
            self.assertEqual([engine.play.call_count for engine in window.player.players], before)
            self.assertEqual(window.player_bar.btn_queue.toolTip(), 'Show both queues')

    def test_theme_preset_preserves_language(self):
        language_manager.set_language('en')
        self.settings.apply_preset('Deep Purple')
        self.assertEqual(self.settings.current_theme['LANGUAGE'], 'en')

    def test_legacy_english_sources_show_polish(self):
        self.assertEqual(tr('Rename Playlist'), 'Zmień nazwę playlisty')
        self.assertEqual(tr('Importing... 2/5 tracks'), 'Importuję… 2/5 utworów')


class SaveProposalTests(LocalDataTest):
    def setUp(self):
        super().setUp()
        self.track = {'title': 'Suggested', 'url': 'https://example.com/song',
                      'uploader': 'Artist', 'recommendation_reason': 'Z Twojej historii'}

    def test_choose_existing_playlist_saves_without_playback_changes(self):
        self.manager.create_playlist('Favourites')
        parent = QLabel()
        menu = build_playlist_menu(parent, self.manager, self.track)
        action = next(action for action in menu.actions() if action.data() == 'Favourites')
        with patch('ui.playlist_menu.QToolTip.showText'):
            action.trigger()
        saved = self.manager.get_tracks('Favourites')
        self.assertEqual(saved[0]['url'], self.track['url'])
        self.assertNotIn('recommendation_reason', saved[0])
        menu.close()

    def test_already_saved_track_is_marked_and_cannot_duplicate(self):
        self.manager.create_playlist('Favourites')
        self.manager.add_track('Favourites', self.track)
        parent = QLabel()
        menu = build_playlist_menu(parent, self.manager, self.track)
        action = next(action for action in menu.actions() if action.data() == 'Favourites')
        self.assertTrue(action.isChecked())
        self.assertFalse(action.isEnabled())
        self.assertEqual(len(self.manager.get_tracks('Favourites')), 1)

    def test_empty_library_can_create_a_playlist_and_save(self):
        parent = QLabel()
        menu = build_playlist_menu(parent, self.manager, self.track)
        with patch('ui.playlist_menu.CreatePlaylistDialog') as dialog, patch('ui.playlist_menu.QToolTip.showText'):
            dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog.return_value.name_input.text.return_value = 'New collection'
            dialog.return_value.image_path = ''
            next(a for a in menu.actions() if a.data() == '__create__').trigger()
        self.assertEqual(self.manager.get_tracks('New collection')[0]['url'], self.track['url'])

    def test_cancel_new_playlist_does_not_save(self):
        parent = QLabel()
        menu = build_playlist_menu(parent, self.manager, self.track)
        with patch('ui.playlist_menu.CreatePlaylistDialog') as dialog:
            dialog.return_value.exec.return_value = QDialog.DialogCode.Rejected
            next(a for a in menu.actions() if a.data() == '__create__').trigger()
        self.assertFalse(self.manager.list_playlists())

    def test_queue_save_button_does_not_move_or_start_track(self):
        with patch('core.player.mpv.MPV', side_effect=[MagicMock(), MagicMock()]), patch('ui.main_window.MprisIntegration'):
            window = MainWindow(self.settings)
            self.addCleanup(window.close)
            window.main_content.home_page.recommendations.shutdown()
            window.main_content.playback_recommendations.shutdown()
            window.player.prefetcher.shutdown()
            window.player.play_queue([{'url': 'https://example.com/current', 'title': 'Current'}])
            window.player.set_recommended_queue([self.track])
            page = window.main_content.queue_page
            page.refresh()
            card = next(c for c in page._cards if c.queue_type == 'recommended')
            with patch('ui.queue_page.show_playlist_menu') as picker:
                QTest.mouseClick(card.btn_save_playlist, Qt.MouseButton.LeftButton)
                self.assertEqual(picker.call_args.args[2]['url'], self.track['url'])
            self.assertEqual(window.player._current_track['title'], 'Current')
            self.assertEqual(len(window.player._recommended_queue), 1)
            self.assertFalse(window.player._priority_queue)
