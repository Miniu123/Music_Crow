from ui.artist_button import ArtistButton
from core.i18n import tr, text, set_text
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QSizePolicy, QPushButton, QInputDialog, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

from ui.icons import icon
from core.search_engine import PLATFORM_COLORS
from core.thumbnail_loader import ThumbnailManager, get_rounded_pixmap


class PlaylistTrackCard(QFrame):
    """A track card within a playlist view."""

    play_clicked = pyqtSignal(dict)
    artist_requested = pyqtSignal(dict)
    remove_clicked = pyqtSignal(int)  # index
    queue_clicked = pyqtSignal(dict)
    play_next_clicked = pyqtSignal(dict)

    def __init__(self, track: dict, index: int, parent=None):
        super().__init__(parent)
        self.track = track
        self.index = index
        self.setObjectName("PlaylistTrackCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(68)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        platform = track.get("platform", "")
        platform_color = PLATFORM_COLORS.get(platform, "#A1A9BE")

        self.setStyleSheet(f"""
            QFrame#PlaylistTrackCard {{
                background-color: rgba(255, 255, 255, 0.02);
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.03);
            }}
            QFrame#PlaylistTrackCard:hover {{
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid {platform_color};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 12, 6)
        layout.setSpacing(12)

        # Index number
        idx_label = QLabel(f"{index + 1}")
        idx_label.setFixedWidth(24)
        idx_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        idx_label.setStyleSheet("font-size: 12px; color: #969EB6; background: transparent; border: none;")
        layout.addWidget(idx_label)

        # Thumbnail
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(50, 50)
        self.thumbnail_label.setStyleSheet("background-color: rgba(255,255,255,0.06); border-radius: 6px;")
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setText("♪")
        layout.addWidget(self.thumbnail_label)

        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 2, 0, 2)

        title = QLabel(track.get("title", "Unknown"))
        title.setStyleSheet("font-weight: 600; font-size: 13px; color: #EAEAEA; background: transparent; border: none;")
        title.setWordWrap(False)

        info_row = QHBoxLayout()
        info_row.setSpacing(6)
        info_row.setContentsMargins(0, 0, 0, 0)

        artist = ArtistButton(track)
        artist.artist_requested.connect(self.artist_requested.emit)

        badge = QLabel(platform)
        badge.setStyleSheet(f"""
            font-size: 9px; color: {platform_color};
            background-color: rgba(255,255,255,0.04);
            border: 1px solid {platform_color};
            border-radius: 7px; padding: 1px 6px;
        """)
        badge.setFixedHeight(16)

        info_row.addWidget(artist)
        info_row.addWidget(badge)
        info_row.addStretch()

        text_layout.addWidget(title)
        text_layout.addLayout(info_row)
        layout.addLayout(text_layout, 1)

        # Duration
        dur = track.get("duration", 0) or 0
        if dur:
            m, s = divmod(int(dur), 60)
            dur_text = f"{m}:{s:02d}"
        else:
            dur_text = "—"
        dur_label = QLabel(dur_text)
        dur_label.setStyleSheet("font-size: 11px; color: #969EB6; background: transparent; border: none;")
        layout.addWidget(dur_label)

        # Remove button
        btn_remove = QPushButton("✕")
        btn_remove.setObjectName("IconButton")
        btn_remove.setFixedSize(26, 26)
        btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.04);
                color: #969EB6;
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 13px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(255,80,80,0.15);
                color: #FF5555;
                border: 1px solid rgba(255,80,80,0.3);
            }
        """)
        btn_remove.clicked.connect(lambda: self.remove_clicked.emit(self.index))
        layout.addWidget(btn_remove)

    def set_thumbnail(self, pixmap: QPixmap):
        rounded = get_rounded_pixmap(pixmap, 50, 50, radius=6)
        self.thumbnail_label.setPixmap(rounded)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.pos())
            # Avoid triggering play when clicking remove
            if not isinstance(child, QPushButton):
                self.play_clicked.emit(self.track)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1A1A24;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 8px 20px;
                color: #CCCCCC;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: rgba(139, 92, 246, 0.2);
                color: #FFFFFF;
            }
        """)
        action_play_next = menu.addAction(tr('▶️ Play Next'))
        action_play_next.triggered.connect(lambda: self.play_next_clicked.emit(self.track))
        action_queue = menu.addAction(tr('➕ Add to Queue'))
        action_queue.triggered.connect(lambda: self.queue_clicked.emit(self.track))
        menu.exec(event.globalPos())


class PlaylistPage(QWidget):
    """Page displaying the tracks of a single playlist."""

    play_requested = pyqtSignal(dict)
    artist_requested = pyqtSignal(dict)

    def __init__(self, player, playlist_manager, parent=None):
        super().__init__(parent)
        self.player = player
        self.playlist_manager = playlist_manager
        self.thumbnail_manager = ThumbnailManager()
        self._current_playlist = ""
        self._cards: list[PlaylistTrackCard] = []
        self.setObjectName("PlaylistPage")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 24, 30, 20)
        main_layout.setSpacing(16)

        # ═══════════════════════════════════════
        # Header: Cover image + Title + Actions
        # ═══════════════════════════════════════
        header_layout = QHBoxLayout()
        header_layout.setSpacing(20)

        # Cover image (clickable to change)
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(140, 140)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setCursor(Qt.CursorShape.PointingHandCursor)
        set_text(self.cover_label, 'Click to set cover image', 'toolTip')
        self.cover_label.setText("🎵")
        self.cover_label.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 0.04);
                border: 2px dashed rgba(255, 255, 255, 0.08);
                border-radius: 14px;
                font-size: 40px;
                color: #8993AE;
            }
            QLabel:hover {
                border: 2px dashed rgba(139, 92, 246, 0.3);
                background-color: rgba(139, 92, 246, 0.04);
            }
        """)
        self.cover_label.mousePressEvent = self._on_cover_click
        header_layout.addWidget(self.cover_label)

        # Title + info column
        title_col = QVBoxLayout()
        title_col.setSpacing(6)
        title_col.addStretch()

        # Playlist name row (with rename button)
        name_row = QHBoxLayout()
        name_row.setSpacing(10)

        self.playlist_title = QLabel("Playlist")
        self.playlist_title.setWordWrap(True)
        self.playlist_title.setStyleSheet(
            "font-size: 30px; font-weight: 700; color: #FFFFFF; background: transparent; border: none;"
        )
        name_row.addWidget(self.playlist_title)

        # Rename button
        self.btn_rename = QPushButton("")
        self.btn_rename.setIcon(icon("edit"))
        self.btn_rename.setObjectName("IconButton")
        self.btn_rename.setFixedSize(32, 32)
        self.btn_rename.setCursor(Qt.CursorShape.PointingHandCursor)
        set_text(self.btn_rename, 'Rename playlist', 'toolTip')
        self.btn_rename.setStyleSheet("")
        self.btn_rename.clicked.connect(self._on_rename)
        name_row.addWidget(self.btn_rename)
        name_row.addStretch()

        title_col.addLayout(name_row)

        self.track_count_label = QLabel("Utwory: 0")
        self.track_count_label.setStyleSheet(
            "font-size: 13px; color: #A1A9BE; background: transparent; border: none;"
        )
        title_col.addWidget(self.track_count_label)

        # Action buttons row
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)

        self.btn_play_all = text(QPushButton(""), 'Odtwórz wszystko')
        self.btn_play_all.setIcon(icon("play", "#FFFFFF"))
        self.btn_play_all.setObjectName("PrimaryButton")
        self.btn_play_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play_all.setFixedHeight(38)
        self.btn_play_all.setStyleSheet("")
        self.btn_play_all.clicked.connect(self._play_all)
        actions_row.addWidget(self.btn_play_all)

        self.btn_shuffle_play = text(QPushButton(""), 'Losowo')
        self.btn_shuffle_play.setIcon(icon("shuffle"))
        self.btn_shuffle_play.setObjectName("SecondaryButton")
        self.btn_shuffle_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_shuffle_play.setFixedHeight(38)
        self.btn_shuffle_play.setStyleSheet("")
        self.btn_shuffle_play.clicked.connect(self._shuffle_play)
        actions_row.addWidget(self.btn_shuffle_play)

        # Delete playlist button
        self.btn_delete = text(QPushButton(""), 'Usuń')
        self.btn_delete.setIcon(icon("trash"))
        self.btn_delete.setObjectName("DangerButton")
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.setFixedHeight(38)
        self.btn_delete.setStyleSheet("")
        self.btn_delete.clicked.connect(self._on_delete)
        actions_row.addWidget(self.btn_delete)

        actions_row.addStretch()
        title_col.addLayout(actions_row)
        title_col.addStretch()

        header_layout.addLayout(title_col, 1)
        main_layout.addLayout(header_layout)

        # Divider
        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: rgba(255,255,255,0.04);")
        main_layout.addWidget(divider)

        # Tracks scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("PlaylistScrollArea")

        self.tracks_widget = QWidget()
        self.tracks_widget.setObjectName("TracksSurface")
        self.tracks_layout = QVBoxLayout(self.tracks_widget)
        self.tracks_layout.setContentsMargins(0, 0, 6, 0)
        self.tracks_layout.setSpacing(3)
        self.tracks_layout.addStretch()

        self.scroll_area.setWidget(self.tracks_widget)
        main_layout.addWidget(self.scroll_area, 1)

        # React to playlist changes
        self.playlist_manager.playlist_updated.connect(self._on_playlist_updated)

    def load_playlist(self, name: str):
        self._current_playlist = name
        self.playlist_title.setText(name)
        self._load_cover()
        self._refresh()

    def _load_cover(self):
        """Load and display the playlist cover image."""
        cover_path = self.playlist_manager.get_cover_image(self._current_playlist)
        if cover_path and os.path.exists(cover_path):
            pixmap = QPixmap(cover_path)
            rounded = get_rounded_pixmap(pixmap, 140, 140, radius=14)
            self.cover_label.setPixmap(rounded)
            self.cover_label.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    border: none;
                    border-radius: 14px;
                }
                QLabel:hover {
                    border: 2px solid rgba(139, 92, 246, 0.4);
                }
            """)
        else:
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText("🎵")
            self.cover_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(255, 255, 255, 0.04);
                    border: 2px dashed rgba(255, 255, 255, 0.08);
                    border-radius: 14px;
                    font-size: 40px;
                    color: #8993AE;
                }
                QLabel:hover {
                    border: 2px dashed rgba(139, 92, 246, 0.3);
                    background-color: rgba(139, 92, 246, 0.04);
                }
            """)

    def _on_cover_click(self, event):
        """Open file dialog to select a cover image."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr('Select Cover Image'),
            "",
            tr('Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)'),
        )
        if file_path:
            self.playlist_manager.set_cover_image(self._current_playlist, file_path)
            self._load_cover()

    def _on_rename(self):
        """Open a dialog to rename the playlist."""
        old_name = self._current_playlist
        new_name, ok = QInputDialog.getText(
            self, tr('Rename Playlist'), tr('New name:'), text=old_name,
        )
        if ok and new_name.strip() and new_name.strip() != old_name:
            success = self.playlist_manager.rename_playlist(old_name, new_name.strip())
            if success:
                self._current_playlist = new_name.strip()
                self.playlist_title.setText(self._current_playlist)

    def _on_delete(self):
        """Delete the current playlist."""
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            tr('Delete Playlist'),
            tr('Czy usunąć playlistę „{name}”?\n\nTej operacji nie można cofnąć.').format(name=self._current_playlist),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.playlist_manager.delete_playlist(self._current_playlist)

    def _refresh(self):
        # Clear old cards
        for card in self._cards:
            self.tracks_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        tracks = self.playlist_manager.get_tracks(self._current_playlist)
        set_text(self.track_count_label, f"Utwory: {len(tracks)}")

        for i, track in enumerate(tracks):
            card = PlaylistTrackCard(track, i)
            card.play_clicked.connect(self._on_play)
            card.artist_requested.connect(self.artist_requested.emit)
            card.remove_clicked.connect(self._on_remove)
            card.play_next_clicked.connect(lambda t: self.player.add_to_queue(t, play_next=True))
            card.queue_clicked.connect(lambda t: self.player.add_to_queue(t, play_next=False))
            self._cards.append(card)
            self.tracks_layout.insertWidget(self.tracks_layout.count() - 1, card)

            thumb_url = track.get("thumbnail_url", "")
            
            def on_thumb_loaded(url, pixmap, c=card, tu=thumb_url):
                if url == tu:
                    try:
                        c.set_thumbnail(pixmap)
                    except RuntimeError:
                        pass

            if thumb_url:
                self.thumbnail_manager.load(thumb_url, on_thumb_loaded)

    def _on_play(self, track: dict):
        tracks = self.playlist_manager.get_tracks(self._current_playlist)
        try:
            index = next(i for i, t in enumerate(tracks) if t.get("url") == track.get("url"))
        except StopIteration:
            index = 0
            
        self.player.play_queue(tracks, index)
        self.play_requested.emit(track)

    def _on_remove(self, index: int):
        self.playlist_manager.remove_track(self._current_playlist, index)

    def _on_playlist_updated(self, name: str):
        if name == self._current_playlist:
            self._refresh()

    def _play_all(self):
        tracks = self.playlist_manager.get_tracks(self._current_playlist)
        if tracks:
            self.player.play_queue(tracks, 0)
            self.play_requested.emit(tracks[0])

    def _shuffle_play(self):
        tracks = self.playlist_manager.get_tracks(self._current_playlist)
        if tracks:
            import random
            start_idx = random.randint(0, len(tracks) - 1)
            
            if not self.player._shuffle:
                self.player.toggle_shuffle()
                
            self.player.play_queue(tracks, start_idx)
            self.play_requested.emit(tracks[start_idx])
