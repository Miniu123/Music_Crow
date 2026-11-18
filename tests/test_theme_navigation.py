import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor

from core import player_state
from core import playlist_manager as playlists
from core.theme_manager import ThemeManager, derive_palette, parse_color

app = QApplication.instance() or QApplication([])
QSS_PATH = Path(__file__).resolve().parent.parent / 'assets' / 'style.qss'


def isolated_theme(directory):
    theme = ThemeManager()
    theme.config_dir = Path(directory)
    theme.config_path = Path(directory) / 'theme.json'
    return theme


class PaletteTests(unittest.TestCase):
    def test_parse_color_accepts_rgba_and_falls_back(self):
        color = parse_color('rgba(10, 16, 10, 0.97)')
        self.assertEqual((color.red(), color.green(), color.blue()), (10, 16, 10))
        self.assertAlmostEqual(color.alphaF(), 0.97, places=2)
        self.assertEqual(parse_color('not a colour', '#123456').name(), '#123456')

    def test_derived_tones_follow_the_accent_hue(self):
        for accent in ('#9672FF', '#10B981', '#3B82F6', '#EF4444'):
            palette = derive_palette(accent)
            hue = QColor(accent).hslHueF()
            for key in ('ACCENT_LIGHT', 'ACCENT_PALE', 'ACCENT_MUTED'):
                with self.subTest(accent=accent, key=key):
                    self.assertAlmostEqual(QColor(palette[key]).hslHueF(), hue, delta=0.02)
            self.assertGreater(QColor(palette['ACCENT_PALE']).lightnessF(), QColor(palette['ACCENT_LIGHT']).lightnessF())

    def test_stylesheet_has_no_unresolved_tokens_or_fixed_purple(self):
        with tempfile.TemporaryDirectory() as directory:
            theme = isolated_theme(directory)
            theme.current_theme['ACCENT_COLOR'] = '#10B981'
            qss = theme.get_qss(str(QSS_PATH))
        self.assertNotIn('{{', qss)
        for purple in ('#D5CAFF', '#C1AFFF', '#E1D8FF', '#A99BCF', '#9672FF', '139,92,246', '139, 92, 246'):
            self.assertNotIn(purple.lower(), qss.lower())
        self.assertIn(derive_palette('#10B981')['ACCENT_LIGHT'], qss)


class SettingsSignalTests(unittest.TestCase):
    def test_audio_setting_does_not_restyle_the_interface(self):
        with tempfile.TemporaryDirectory() as directory:
            theme = isolated_theme(directory)
            restyled, changed = [], []
            theme.theme_changed.connect(lambda: restyled.append(True))
            theme.settings_changed.connect(lambda: changed.append(True))
            theme.set_setting('BASS_GAIN', 4)
            theme.set_setting('BASS_GAIN', 4)  # unchanged values are not saved again
            self.assertEqual(changed, [True])
            self.assertEqual(restyled, [])
            self.assertEqual(theme.current_theme['BASS_GAIN'], 4)
            self.assertTrue(theme.config_path.exists())


class VolumeMemoryTests(unittest.TestCase):
    def test_volume_round_trip_and_invalid_values(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(player_state, 'config_dir', return_value=Path(directory)):
            self.assertEqual(player_state.load_volume(), player_state.DEFAULT_VOLUME)
            player_state.save_volume(37)
            self.assertEqual(player_state.load_volume(), 37)
            player_state.save_volume(140)
            self.assertEqual(player_state.load_volume(), 100)
            player_state.state_path().write_text('{"volume": "loud"}')
            self.assertEqual(player_state.load_volume(), player_state.DEFAULT_VOLUME)


class SidebarSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for field in ('PLAYLISTS_DIR', 'COVERS_DIR'):
            patcher = patch.object(playlists, field, str(Path(self.temp.name) / field))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.manager = playlists.PlaylistManager()
        self.manager.create_playlist('Chill')
        self.manager.create_playlist('Rock')
        from ui.sidebar import Sidebar
        self.sidebar = Sidebar(playlist_manager=self.manager, theme_manager=isolated_theme(self.temp.name))
        self.addCleanup(self.sidebar.deleteLater)

    def checked(self):
        state = {'home': self.sidebar.btn_home.isChecked(), 'search': self.sidebar.btn_search.isChecked()}
        for button in self.sidebar._playlist_buttons():
            state[button.property('playlistName')] = button.isChecked()
        return state

    def test_highlight_follows_the_page_shown(self):
        self.sidebar.set_active_page('search')
        self.assertEqual(self.checked(), {'home': False, 'search': True, 'Chill': False, 'Rock': False})
        self.sidebar.set_active_page('playlist', 'Rock')
        self.assertEqual(self.checked(), {'home': False, 'search': False, 'Chill': False, 'Rock': True})
        self.sidebar.set_active_page('queue')
        self.assertFalse(any(self.checked().values()))

    def test_selection_survives_playlist_list_rebuild(self):
        self.sidebar.set_active_page('playlist', 'Chill')
        self.manager.create_playlist('Jazz')
        self.assertTrue(self.checked()['Chill'])
        self.assertFalse(self.checked()['Jazz'])


if __name__ == '__main__':
    unittest.main()


class TileAndDiscoveryTests(unittest.TestCase):
    TRACKS = [{'title': f'Song {i}', 'artist': f'Artist {i % 3}', 'duration': 200 + i,
               'url': f'https://www.youtube.com/watch?v=video{i:06d}'} for i in range(7)]

    def test_grid_columns_and_height_follow_width(self):
        from ui.track_tile import TileGrid, TrackTile
        grid = TileGrid(min_tile_width=170, spacing=14)
        self.addCleanup(grid.deleteLater)
        grid.set_tiles([TrackTile(track, 'Z Twoich playlist') for track in self.TRACKS])
        grid.show()
        grid.resize(920, 10)
        app.processEvents()
        self.assertEqual(grid.columns(), 5)
        first, sixth = grid.tiles[0], grid.tiles[5]
        self.assertEqual(sixth.y(), first.height() + 14)  # wraps into a second row
        self.assertEqual(grid.minimumHeight(), 2 * first.height() + 14)
        self.assertEqual(first.cover.width(), first.cover.height())  # square artwork
        grid.resize(400, 10)
        app.processEvents()
        self.assertEqual(grid.columns(), 2)
        self.assertEqual(grid.tiles[2].y(), grid.tiles[0].height() + 14)

    def test_now_playing_matches_the_same_recording_only(self):
        from ui.track_tile import TrackTile, same_track
        current = dict(self.TRACKS[2], url='https://music.youtube.com/watch?v=video000002')
        self.assertTrue(same_track(self.TRACKS[2], current))
        self.assertFalse(same_track(self.TRACKS[3], current))
        self.assertFalse(same_track(self.TRACKS[2], None))
        tile = TrackTile(self.TRACKS[2])
        self.addCleanup(tile.deleteLater)
        tile.set_now_playing(True)
        self.assertTrue(tile.property('nowPlaying'))
        self.assertTrue(tile.cover.now_playing)

    def test_recent_searches_are_unique_newest_first_and_capped(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(player_state, 'config_dir', return_value=Path(directory)):
            for query in ('lofi', 'Jazz', 'rock', '  lofi  ', 'JAZZ'):
                player_state.remember_search(query)
            self.assertEqual(player_state.load_recent_searches(), ['JAZZ', 'lofi', 'rock'])
            for index in range(20):
                player_state.remember_search(f'q{index}')
            self.assertEqual(len(player_state.load_recent_searches()), player_state.MAX_RECENT_SEARCHES)

    def test_search_page_suggests_library_artists(self):
        from unittest.mock import MagicMock
        from ui.search_page import SearchPage
        manager = MagicMock()
        manager.list_playlists.return_value = ['A', 'B']
        manager.get_tracks.side_effect = lambda name: (
            [{'artist': 'Daft Punk'}, {'artist': 'Air'}] if name == 'A'
            else [{'uploader': 'daft punk'}, {'artist': 'Unknown Artist'}])
        with patch('ui.search_page.load_recent_searches', return_value=['lofi']):
            page = SearchPage(MagicMock(), manager)
        self.addCleanup(page.deleteLater)
        self.assertEqual(page.library_artists(), ['Daft Punk', 'Air'])
        self.assertEqual(page.recent_layout.count(), 1)
        self.assertEqual(page.artist_layout.count(), 2)


class ChromeTests(unittest.TestCase):
    def test_title_bar_names_the_page_and_keeps_playlist_names_untranslated(self):
        from PyQt6.QtWidgets import QWidget
        from core.i18n import language_manager
        from ui.custom_titlebar import CustomTitleBar
        window = QWidget()
        self.addCleanup(window.deleteLater)
        bar = CustomTitleBar(window)
        self.addCleanup(lambda: language_manager.set_language('pl', persist=False))
        bar.set_page('queue')
        self.assertEqual(bar.page_label.text(), 'Kolejka')
        bar.set_page('playlist', 'Moja lista')
        language_manager.set_language('en', persist=False)
        self.assertEqual(bar.page_label.text(), 'Moja lista')
        bar.set_page('search')
        self.assertEqual(bar.page_label.text(), 'Search')


class BundledFontTests(unittest.TestCase):
    def test_inter_weights_used_by_the_stylesheet_are_available(self):
        from PyQt6.QtGui import QFont, QFontInfo
        from ui.fonts import FONTS_DIR, load_bundled_fonts
        self.assertIn('Inter', load_bundled_fonts())
        self.assertTrue((FONTS_DIR / 'Inter-LICENSE.txt').exists())
        for weight, style in ((400, 'Regular'), (500, 'Medium'), (600, 'SemiBold'), (700, 'Bold')):
            font = QFont('Inter')
            font.setWeight(QFont.Weight(weight))
            info = QFontInfo(font)
            with self.subTest(weight=weight):
                self.assertEqual(info.family(), 'Inter')
                self.assertEqual(info.styleName(), style)
