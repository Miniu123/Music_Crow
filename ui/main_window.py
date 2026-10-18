from core.i18n import language_manager, tr
import os
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QKeyEvent
from ui.custom_titlebar import CustomTitleBar
from ui.sidebar import Sidebar
from ui.player_bar import PlayerBar
from ui.main_content import MainContent
from core.gdrive_sync import GDriveSyncManager
from core.player import MusicPlayer
from core.playlist_manager import PlaylistManager
from core.mpris_integration import MprisIntegration


class MainWindow(QMainWindow):
    def __init__(self, theme_manager=None):
        super().__init__()
        self.theme_manager = theme_manager
        language_manager.configure(theme_manager)
        self.setWindowTitle("Music Crow")
        self.resize(1400, 900)
        self.setMinimumSize(1000, 700)

        # Set window icon (for taskbar / window manager)
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Frameless window for custom styling
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.central_widget = QWidget()
        self.central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Custom Title Bar
        self.title_bar = CustomTitleBar(self)
        self.main_layout.addWidget(self.title_bar)

        # Core services
        self.player = MusicPlayer(theme_manager=self.theme_manager)
        self.playlist_manager = PlaylistManager()
        self.sync_manager = GDriveSyncManager(self, root=self.theme_manager.config_dir if self.theme_manager else None)
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        self.sync_manager.open_browser.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        self.sync_manager.restore_ready.connect(self._confirm_restore)
        self.sync_manager.data_restored.connect(self._reload_cloud_data)
        for signal in (self.playlist_manager.playlist_created, self.playlist_manager.playlist_updated,
                       self.playlist_manager.playlist_deleted):
            signal.connect(self.sync_manager.schedule_sync)
        if self.theme_manager:
            self.theme_manager.settings_saved.connect(self.sync_manager.schedule_sync)
        self.mpris = MprisIntegration(self.player)

        # Middle Section (Sidebar + Content)
        self.middle_widget = QWidget()
        self.middle_widget.setObjectName("MiddleSection")
        self.middle_layout = QHBoxLayout(self.middle_widget)
        self.middle_layout.setContentsMargins(0, 0, 0, 0)
        self.middle_layout.setSpacing(0)

        self.sidebar = Sidebar(playlist_manager=self.playlist_manager, theme_manager=self.theme_manager, player=self.player, sync_manager=self.sync_manager)
        self.main_content = MainContent(self.player, playlist_manager=self.playlist_manager)

        self.main_content.home_page.history.changed.connect(self.sync_manager.schedule_sync)

        # Connect sidebar navigation
        self.sidebar.navigate.connect(self._on_navigate)
        self.sidebar.playlist_selected.connect(self._on_playlist_selected)

        self.middle_layout.addWidget(self.sidebar)
        self.middle_layout.addWidget(self.main_content)

        self.main_layout.addWidget(self.middle_widget, 1)

        # Bottom Player Bar — now receives playlist_manager for save-to-playlist
        self.player_bar = PlayerBar(self.player, playlist_manager=self.playlist_manager)
        self.player_bar.queue_view_requested.connect(self.main_content.show_queue)
        self.player_bar.artist_requested.connect(self.main_content.show_artist)
        self.main_layout.addWidget(self.player_bar)

        # Grab keyboard focus for multimedia keys
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _on_navigate(self, page: str):
        if page == "home":
            self.main_content.show_home()
        elif page == "search":
            self.main_content.show_search()

    def _on_playlist_selected(self, name: str):
        self.main_content.show_playlist(name)

    def keyPressEvent(self, event: QKeyEvent):
        """Handle multimedia keyboard keys for playback control."""
        key = event.key()

        if key == Qt.Key.Key_MediaPlay or key == Qt.Key.Key_MediaTogglePlayPause:
            self.player.toggle_pause()
        elif key == Qt.Key.Key_MediaPause:
            if not self.player.mpv.pause:
                self.player.toggle_pause()
        elif key == Qt.Key.Key_MediaStop:
            self.player.stop()
        elif key == Qt.Key.Key_MediaNext:
            self.player.next_track()
        elif key == Qt.Key.Key_MediaPrevious:
            self.player.prev_track()
        elif key == Qt.Key.Key_VolumeUp:
            new_vol = min(100, self.player._master_volume + 5)
            self.player.set_volume(new_vol)
            self.player_bar.slider_volume.setValue(new_vol)
        elif key == Qt.Key.Key_VolumeDown:
            new_vol = max(0, self.player._master_volume - 5)
            self.player.set_volume(new_vol)
            self.player_bar.slider_volume.setValue(new_vol)
        elif key == Qt.Key.Key_VolumeMute:
            if self.player._master_volume > 0:
                self._volume_before_mute = self.player._master_volume
                self.player.set_volume(0)
                self.player_bar.slider_volume.setValue(0)
            else:
                restore = getattr(self, '_volume_before_mute', 80)
                self.player.set_volume(restore)
                self.player_bar.slider_volume.setValue(restore)
        elif key == Qt.Key.Key_Space:
            # Space bar to toggle play/pause (only if search input isn't focused)
            focused = self.focusWidget()
            if focused is None or focused is self:
                self.player.toggle_pause()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def fade_in(self, duration=350):
        """Smoothly fades in the main window when transitioning from splash screen."""
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        effect = QGraphicsOpacityEffect(self.central_widget)
        effect.setOpacity(0.0)
        self.central_widget.setGraphicsEffect(effect)
        self._fade_anim = QPropertyAnimation(effect, b"opacity", self)
        self._fade_anim.setDuration(duration)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.finished.connect(lambda: self.central_widget.setGraphicsEffect(None))
        self.show()
        self._fade_anim.start()


    def _confirm_restore(self, snapshot):
        from PyQt6.QtWidgets import QMessageBox
        manager = self.sync_manager
        manager._auto.stop()
        manager._debounce.stop()
        manager._pending = False
        count = len(snapshot['playlists'])
        tracks = sum(len(item['tracks']) for item in snapshot['playlists'].values())
        summary = tr('Playlisty:') + f' {count}  ·  ' + tr('Utwory:') + f' {tracks}\n\n'
        message = tr('Przywrócić ustawienia i playlisty? Różne playlisty o tej samej nazwie zachowamy osobno. Obecne dane zapiszemy najpierw w lokalnej kopii.')
        answer = QMessageBox.question(self, tr('Przywróć kopię…'), summary + message,
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            manager.apply_restore(snapshot)
        if manager.connected:
            manager._auto.start()

    def _reload_cloud_data(self):
        import json
        from core.theme_manager import DEFAULT_THEME
        if self.theme_manager:
            self.theme_manager.current_theme = dict(DEFAULT_THEME)
            self.theme_manager.load_theme()
            language_manager.configure(self.theme_manager)
            self.theme_manager.theme_changed.emit()
        home = self.main_content.home_page
        history = home.history
        history.entries = json.loads(history.path.read_text()) if history.path.exists() else {}
        history.changed.emit()
        self.sidebar._refresh_playlists()
        home._refresh_playlists()
        page = self.main_content.playlist_page
        if page._current_playlist:
            page.load_playlist(page._current_playlist)

    def closeEvent(self, event):
        self.sync_manager.shutdown()
        self.main_content.playback_recommendations.shutdown()
        self.main_content.home_page.shutdown()
        self.main_content.search_page.shutdown()
        self.main_content.artist_page.shutdown()
        self.player_bar.thumbnail_manager.cancel_all()
        self.main_content.playlist_page.thumbnail_manager.cancel_all()
        self.main_content.queue_page.thumbnail_manager.cancel_all()
        self.player.shutdown()
        super().closeEvent(event)
