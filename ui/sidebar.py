from ui.motion import MotionButton
from core.i18n import tr, text, set_text
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QSpacerItem, QSizePolicy,
    QLabel, QInputDialog, QScrollArea, QHBoxLayout, QDialog,
    QLineEdit, QProgressBar, QMenu
)
from PyQt6.QtCore import pyqtSignal, Qt

from ui.icons import icon
from core.search_engine import PlaylistImportWorker
from ui.settings_dialog import SettingsDialog
from ui.animated_brand import AnimatedBrandWidget


class ImportPlaylistDialog(QDialog):
    """Dialog for importing a playlist from a URL."""

    import_finished = pyqtSignal(str, list)  # (playlist_name, tracks)

    INPUT_STYLE = """
        QLineEdit {
            background-color: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 12px;
            padding: 12px 16px;
            color: #FFFFFF;
            font-size: 13px;
        }
        QLineEdit:focus {
            border: 1px solid rgba(139,92,246,0.5);
            background-color: rgba(255,255,255,0.1);
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(500, 340)

        # Outer container with background
        self.container = QWidget(self)
        self.container.setObjectName("DialogSurface")
        self.container.setGeometry(0, 0, 500, 340)
        self.container.setStyleSheet("")

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(28, 22, 28, 24)
        layout.setSpacing(14)

        # Header with close button
        header_row = QHBoxLayout()
        title = text(QLabel(""), 'Importuj playlistę')
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #FFFFFF; background: transparent; border: none;")
        header_row.addWidget(title)
        header_row.addStretch()

        btn_close = MotionButton("✕")
        btn_close.setObjectName("DialogClose")
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("")
        btn_close.clicked.connect(self.reject)
        header_row.addWidget(btn_close)
        layout.addLayout(header_row)

        subtitle = text(QLabel(""), 'Wklej link do playlisty z YouTube lub SoundCloud.')
        subtitle.setStyleSheet("font-size: 11px; color: #A1A9BE; background: transparent; border: none;")
        layout.addWidget(subtitle)

        layout.addSpacing(4)

        # Name input
        self.name_input = QLineEdit()
        set_text(self.name_input, 'Nazwa playlisty…', 'placeholderText')
        self.name_input.setFixedHeight(44)
        self.name_input.setStyleSheet("")
        layout.addWidget(self.name_input)

        # URL input
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://music.youtube.com/playlist?list=...")
        self.url_input.setFixedHeight(44)
        self.url_input.setStyleSheet("")
        layout.addWidget(self.url_input)

        # Progress bar (hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("")
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 11px; color: #888888; background: transparent; border: none;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Import button
        self.btn_import = text(MotionButton(""), 'Importuj playlistę')
        self.btn_import.setObjectName("PrimaryButton")
        self.btn_import.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_import.setFixedHeight(42)
        self.btn_import.setStyleSheet("")
        self.btn_import.clicked.connect(self._start_import)
        layout.addWidget(self.btn_import, alignment=Qt.AlignmentFlag.AlignCenter)

        self._worker = None
        self._drag_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_active = True
            self._drag_pos = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if getattr(self, '_drag_active', False) and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_active = False
        event.accept()

    def _start_import(self):
        url = self.url_input.text().strip()
        name = self.name_input.text().strip()

        if not url:
            set_text(self.status_label, 'Please enter a playlist URL', 'text')
            self.status_label.setStyleSheet("font-size: 11px; color: #FF5555; background: transparent;")
            return

        if not name:
            name = "Imported Playlist"

        self.btn_import.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        set_text(self.status_label, '⏳ Importing...', 'text')
        self.status_label.setStyleSheet("font-size: 11px; color: #AAAAAA; background: transparent;")

        from PyQt6.QtWidgets import QApplication
        self._worker = PlaylistImportWorker(url, QApplication.instance())
        self._worker.progress.connect(self._on_progress)
        self._worker.import_finished.connect(lambda tracks: self._on_finished(name, tracks))
        self._worker.import_error.connect(self._on_error)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def reject(self):
        if self._worker is not None:
            try:
                if self._worker.isRunning():
                    self._worker.requestInterruption()
                    self._worker.wait()
            except RuntimeError:
                pass  # Qt may already have deleted the completed worker.
        super().reject()

    def _on_progress(self, current, total):
        if total > 0:
            self.progress_bar.setValue(int(current / total * 100))
            set_text(self.status_label, f"Importing... {current}/{total} tracks")

    def _on_finished(self, name, tracks):
        self.btn_import.setEnabled(True)
        if tracks:
            set_text(self.status_label, f"✅ Imported {len(tracks)} tracks!")
            self.status_label.setStyleSheet("font-size: 11px; color: #1DB954; background: transparent;")
            self.import_finished.emit(name, tracks)
            # Close after a moment
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(800, self.accept)
        else:
            set_text(self.status_label, 'No tracks found in this playlist.', 'text')
            self.status_label.setStyleSheet("font-size: 11px; color: #FF5555; background: transparent;")
            self.progress_bar.hide()

    def _on_error(self, error_msg):
        self.btn_import.setEnabled(True)
        self.progress_bar.hide()
        set_text(self.status_label, f"Error: {error_msg}")
        self.status_label.setStyleSheet("font-size: 11px; color: #FF5555; background: transparent;")


class Sidebar(QWidget):
    navigate = pyqtSignal(str)              # "home", "search"
    playlist_selected = pyqtSignal(str)     # playlist name

    def __init__(self, playlist_manager=None, theme_manager=None, player=None, parent=None, sync_manager=None):
        super().__init__(parent)
        self.playlist_manager = playlist_manager
        self.theme_manager = theme_manager
        self.sync_manager = sync_manager
        self.player = player
        self.setObjectName("Sidebar")
        self.setFixedWidth(240)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 14, 12, 16)
        self.main_layout.setSpacing(4)

        # Animated App logo / brand
        self.brand = AnimatedBrandWidget(player=self.player, parent=self)
        self.brand.clicked.connect(lambda: self._navigate("home"))
        self.main_layout.addWidget(self.brand)

        # Navigation section
        nav_label = text(QLabel(""), 'TWOJA MUZYKA')
        nav_label.setStyleSheet(
            "font-size: 10px; font-weight: 600; color: #929BB4; "
            "padding: 0 8px; letter-spacing: 1px; background: transparent;"
        )
        self.main_layout.addWidget(nav_label)
        self.main_layout.addSpacing(4)

        self.btn_home = text(MotionButton(""), '  Strona główna')
        self.btn_home.setIcon(icon("home"))
        self.btn_home.setObjectName("NavButton")
        self.btn_home.setCheckable(True)
        self.btn_home.setChecked(True)
        self.btn_home.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_home.clicked.connect(lambda: self._navigate("home"))

        self.btn_search = text(MotionButton(""), '  Szukaj')
        self.btn_search.setIcon(icon("search"))
        self.btn_search.setObjectName("NavButton")
        self.btn_search.setCheckable(True)
        self.btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_search.clicked.connect(lambda: self._navigate("search"))

        self._nav_buttons = [self.btn_home, self.btn_search]

        self.main_layout.addWidget(self.btn_home)
        self.main_layout.addWidget(self.btn_search)

        # Divider
        self.main_layout.addSpacing(12)
        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: rgba(255,255,255,0.05);")
        self.main_layout.addWidget(divider)
        self.main_layout.addSpacing(12)

        # Playlists section header
        pl_header_layout = QHBoxLayout()
        pl_header_layout.setContentsMargins(8, 0, 4, 0)
        pl_label = text(QLabel(""), 'BIBLIOTEKA')
        pl_label.setStyleSheet(
            "font-size: 10px; font-weight: 600; color: #929BB4; "
            "letter-spacing: 1px; background: transparent;"
        )
        pl_header_layout.addWidget(pl_label)
        pl_header_layout.addStretch()

        # Import playlist button
        self.btn_import_playlist = MotionButton("")
        self.btn_import_playlist.setObjectName("IconButton")
        self.btn_import_playlist.setIcon(icon("download", size=16))
        self.btn_import_playlist.setFixedSize(24, 24)
        self.btn_import_playlist.setCursor(Qt.CursorShape.PointingHandCursor)
        set_text(self.btn_import_playlist, 'Import playlist from URL', 'toolTip')
        self.btn_import_playlist.setStyleSheet("")
        self.btn_import_playlist.clicked.connect(self._import_playlist)
        pl_header_layout.addWidget(self.btn_import_playlist)

        # Create playlist button
        self.btn_create_playlist = MotionButton("")
        self.btn_create_playlist.setObjectName("IconButton")
        self.btn_create_playlist.setIcon(icon("plus", size=16))
        self.btn_create_playlist.setFixedSize(24, 24)
        self.btn_create_playlist.setCursor(Qt.CursorShape.PointingHandCursor)
        set_text(self.btn_create_playlist, 'New playlist', 'toolTip')
        self.btn_create_playlist.setStyleSheet("")
        self.btn_create_playlist.clicked.connect(self._create_playlist)
        pl_header_layout.addWidget(self.btn_create_playlist)
        self.main_layout.addLayout(pl_header_layout)
        self.main_layout.addSpacing(4)

        # Scrollable playlist list
        self.playlist_scroll = QScrollArea()
        self.playlist_scroll.setWidgetResizable(True)
        self.playlist_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 0px; }
        """)
        self.playlist_list_widget = QWidget()
        self.playlist_list_widget.setObjectName("TracksSurface")
        self.playlist_list_layout = QVBoxLayout(self.playlist_list_widget)
        self.playlist_list_layout.setContentsMargins(0, 0, 0, 0)
        self.playlist_list_layout.setSpacing(2)
        self.playlist_list_layout.addStretch()
        self.playlist_scroll.setWidget(self.playlist_list_widget)
        self.main_layout.addWidget(self.playlist_scroll, 1)

        # Bottom divider + settings
        self.main_layout.addSpacing(8)
        divider2 = QWidget()
        divider2.setFixedHeight(1)
        divider2.setStyleSheet("background-color: rgba(255,255,255,0.05);")
        self.main_layout.addWidget(divider2)
        self.main_layout.addSpacing(4)

        self.btn_settings = text(MotionButton(""), '  Ustawienia')
        self.btn_settings.setIcon(icon("settings"))
        self.btn_settings.setObjectName("NavButton")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.clicked.connect(self._show_settings)
        self.main_layout.addWidget(self.btn_settings)

        # Connect playlist manager signals
        if self.playlist_manager:
            self.playlist_manager.playlist_created.connect(lambda _: self._refresh_playlists())
            self.playlist_manager.playlist_deleted.connect(lambda _: self._refresh_playlists())
            self._refresh_playlists()

    def _navigate(self, page: str):
        for btn in self._nav_buttons:
            btn.setChecked(False)
        if page == "home":
            self.btn_home.setChecked(True)
        elif page == "search":
            self.btn_search.setChecked(True)
        self.navigate.emit(page)

    def _show_settings(self):
        if self.theme_manager:
            dialog = SettingsDialog(self.theme_manager, self, sync_manager=self.sync_manager)
            dialog.exec()
            dialog.deleteLater()

    def _create_playlist(self):
        name, ok = QInputDialog.getText(
            self, tr('New Playlist'), tr('Playlist name:'),
        )
        if ok and name.strip() and self.playlist_manager:
            self.playlist_manager.create_playlist(name.strip())

    def _import_playlist(self):
        """Open the import playlist dialog."""
        dialog = ImportPlaylistDialog(self)
        dialog.import_finished.connect(self._on_import_finished)
        dialog.exec()

    def _on_import_finished(self, name: str, tracks: list):
        """Handle imported playlist tracks."""
        if not self.playlist_manager:
            return

        # Create the playlist
        self.playlist_manager.create_playlist(name)

        # Add all tracks
        for track in tracks:
            self.playlist_manager.add_track(name, track)

    def _refresh_playlists(self):
        """Rebuild the playlist button list."""
        while self.playlist_list_layout.count() > 1:
            item = self.playlist_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.playlist_manager:
            return

        for pl_name in self.playlist_manager.list_playlists():
            btn = MotionButton(f"  {pl_name}")
            btn.setIcon(icon("playlist"))
            btn.setToolTip(pl_name)
            btn.setObjectName("PlaylistButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, n=pl_name: self._on_playlist_click(n))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, n=pl_name, b=btn: self._show_playlist_context_menu(pos, n, b)
            )
            self.playlist_list_layout.insertWidget(
                self.playlist_list_layout.count() - 1, btn
            )

    def _on_playlist_click(self, name: str):
        for btn in self._nav_buttons:
            btn.setChecked(False)
        self.playlist_selected.emit(name)

    def _show_playlist_context_menu(self, pos, name: str, button: QPushButton):
        """Right-click context menu for playlist items."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1A1A24;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 8px 20px;
                color: #CCCCCC;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: rgba(139,92,246,0.2);
                color: #FFFFFF;
            }
        """)

        rename_action = menu.addAction(tr('✏️  Rename'))
        delete_action = menu.addAction(tr('Usuń'))

        action = menu.exec(button.mapToGlobal(pos))
        if action == rename_action:
            self._rename_playlist(name)
        elif action == delete_action:
            self._delete_playlist(name)

    def _rename_playlist(self, old_name: str):
        new_name, ok = QInputDialog.getText(
            self, tr('Rename Playlist'), tr('New name:'), text=old_name,
        )
        if ok and new_name.strip() and new_name.strip() != old_name and self.playlist_manager:
            self.playlist_manager.rename_playlist(old_name, new_name.strip())

    def _delete_playlist(self, name: str):
        if self.playlist_manager:
            self.playlist_manager.delete_playlist(name)
