from ui.artist_button import ArtistButton
from core.i18n import text, set_text, language_manager
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QMenu, QSlider
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QCursor

from core.thumbnail_loader import ThumbnailManager, get_rounded_pixmap
from ui.icons import icon
from ui.jump_slider import JumpSlider
from ui.animated_brand import SoundwaveVisualizer


class PlayerBar(QWidget):
    queue_view_requested = pyqtSignal()
    artist_requested = pyqtSignal(dict)

    def __init__(self, player, playlist_manager=None, parent=None):
        super().__init__(parent)
        self.player = player
        self.playlist_manager = playlist_manager
        self.setObjectName("PlayerBar")
        self.setFixedHeight(112)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._playing = False
        self.thumbnail_manager = ThumbnailManager()
        self._current_track_info = {}

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(20, 8, 20, 12)
        self.layout.setSpacing(0)

        # ═══════════════════════════════════════
        # Left: Track Info + Save button
        # ═══════════════════════════════════════
        self.track_info_layout = QHBoxLayout()
        self.track_info_layout.setSpacing(12)

        # Create a clickable widget for cover and text
        self.track_info_widget = QWidget()
        self.track_info_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        self.track_info_widget.mousePressEvent = lambda e: self.queue_view_requested.emit()
        self.track_info_widget.setObjectName("TrackInfoSurface")
        
        self.clickable_layout = QHBoxLayout(self.track_info_widget)
        self.clickable_layout.setContentsMargins(4, 4, 4, 4)
        self.clickable_layout.setSpacing(12)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(58, 58)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setText("♪")
        self.cover_label.setObjectName("CoverArt")

        self.track_text_layout = QVBoxLayout()
        self.track_text_layout.setSpacing(2)

        self.title_row = QHBoxLayout()
        self.title_row.setSpacing(6)
        self.title_row.setContentsMargins(0, 0, 0, 0)

        self.track_title = text(QLabel(""), 'Wybierz utwór')
        self.track_title.setObjectName("TrackTitle")
        self.track_title.setMaximumWidth(190)
        self.track_title.setStyleSheet("background: transparent;")

        self.visualizer = SoundwaveVisualizer(self)
        self.visualizer.hide()

        self.title_row.addWidget(self.track_title)
        self.title_row.addWidget(self.visualizer)
        self.title_row.addStretch()

        self.track_artist = ArtistButton({})
        self.track_artist.artist_requested.connect(self.artist_requested.emit)
        self.track_artist.setObjectName("TrackArtist")
        self.track_artist.setMaximumWidth(220)
        self.track_text_layout.addStretch()
        self.track_text_layout.addLayout(self.title_row)
        self.track_text_layout.addWidget(self.track_artist)
        self.track_text_layout.addStretch()

        self.clickable_layout.addWidget(self.cover_label)
        self.clickable_layout.addLayout(self.track_text_layout)

        # Save to playlist button (♡ heart)
        self.btn_save = QPushButton("♡")
        self.btn_save.setObjectName("SaveButton")
        self.btn_save.setFixedSize(36, 36)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        set_text(self.btn_save, 'Save to playlist', 'toolTip')
        self.btn_save.setStyleSheet("")
        self.btn_save.clicked.connect(self._on_save_to_playlist)

        self.track_info_layout.addWidget(self.track_info_widget)
        self.track_info_layout.addWidget(self.btn_save)
        self.track_info_layout.addStretch()

        # ═══════════════════════════════════════
        # Center: Controls + Progress
        # ═══════════════════════════════════════
        self.center_layout = QVBoxLayout()
        self.center_layout.setSpacing(6)

        self.controls_layout = QHBoxLayout()
        self.controls_layout.setSpacing(12)

        self.btn_shuffle = QPushButton("🔀")
        self.btn_shuffle.setObjectName("ControlButton")
        self.btn_shuffle.setFixedSize(36, 36)
        self.btn_shuffle.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_prev = QPushButton("⏮")
        self.btn_prev.setObjectName("ControlButton")
        self.btn_prev.setFixedSize(40, 40)
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_play = QPushButton("▶")
        self.btn_play.setObjectName("PlayPauseButton")
        self.btn_play.setFixedSize(46, 46)
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_next = QPushButton("⏭")
        self.btn_next.setObjectName("ControlButton")
        self.btn_next.setFixedSize(40, 40)
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_repeat = QPushButton("🔁")
        self.btn_repeat.setObjectName("ControlButton")
        self.btn_repeat.setFixedSize(36, 36)
        self.btn_repeat.setCursor(Qt.CursorShape.PointingHandCursor)

        self.controls_layout.addStretch()
        self.controls_layout.addWidget(self.btn_shuffle)
        self.controls_layout.addWidget(self.btn_prev)
        self.controls_layout.addWidget(self.btn_play)
        self.controls_layout.addWidget(self.btn_next)
        self.controls_layout.addWidget(self.btn_repeat)
        self.controls_layout.addStretch()

        self.progress_layout = QHBoxLayout()
        self.progress_layout.setSpacing(8)
        self.time_current = QLabel("0:00")
        self.time_current.setObjectName("TimeLabel")
        self.time_current.setFixedWidth(40)
        self.time_current.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.slider_progress = JumpSlider(Qt.Orientation.Horizontal)
        self.slider_progress.setObjectName("ProgressSlider")
        self.slider_progress.setRange(0, 100)
        self.time_total = QLabel("0:00")
        self.time_total.setObjectName("TimeLabel")
        self.time_total.setFixedWidth(40)

        self.progress_layout.addWidget(self.time_current)
        self.progress_layout.addWidget(self.slider_progress)
        self.progress_layout.addWidget(self.time_total)

        self.center_layout.addLayout(self.controls_layout)
        self.center_layout.addLayout(self.progress_layout)

        # ═══════════════════════════════════════
        # Right: Volume
        # ═══════════════════════════════════════
        self.right_layout = QHBoxLayout()
        self.right_layout.setSpacing(8)
        self.btn_volume = QPushButton("🔊")
        self.btn_volume.setObjectName("ControlButton")
        self.btn_volume.setFixedSize(36, 36)
        self.btn_volume.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider_volume = JumpSlider(Qt.Orientation.Horizontal)
        self.slider_volume.setObjectName("VolumeSlider")
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(80)
        self.slider_volume.setFixedWidth(110)
        self.right_layout.addStretch()
        self.right_layout.addWidget(self.btn_volume)
        self.right_layout.addWidget(self.slider_volume)

        self.btn_queue = QPushButton()
        self.btn_queue.setIcon(icon("queue"))
        self.btn_queue.setObjectName("ControlButton")
        self.btn_queue.setFixedSize(32, 32)
        set_text(self.btn_queue, 'Pokaż dwie kolejki', 'toolTip')
        self.btn_queue.clicked.connect(self.queue_view_requested.emit)
        self.right_layout.insertWidget(1, self.btn_queue)
        self.prefetch_label = QLabel("")
        self.prefetch_label.setObjectName("PrefetchStatus")
        self.prefetch_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.prefetch_label.setFixedHeight(14)
        self.center_layout.addWidget(self.prefetch_label)
        self.player.prefetch_changed.connect(lambda value: set_text(self.prefetch_label, value))
        for button, name, tooltip in (
            (self.btn_shuffle, "shuffle", "Odtwarzaj losowo"),
            (self.btn_prev, "previous", "Poprzedni utwór"),
            (self.btn_play, "play", "Odtwórz / pauza"),
            (self.btn_next, "next", "Następny utwór"),
            (self.btn_repeat, "repeat", "Powtarzanie"),
            (self.btn_volume, "volume", "Wycisz / przywróć głośność"),
            (self.btn_save, "heart", "Zapisz na playliście"),
        ):
            button.setText("")
            button.setIcon(icon(name, "#FFFFFF" if name == "play" else "#C7CADB"))
            button.setIconSize(QSize(19, 19))
            set_text(button, tooltip, "toolTip")
        self.btn_shuffle.setCheckable(True)
        self.btn_repeat.setCheckable(True)
        self.btn_volume.clicked.connect(self._toggle_mute)

        # Assemble
        self.layout.addLayout(self.track_info_layout, 1)
        self.layout.addLayout(self.center_layout, 2)
        self.layout.addLayout(self.right_layout, 1)

        # ═══════════════════════════════════════
        # Connections
        # ═══════════════════════════════════════
        self._is_slider_pressed = False
        self.btn_play.clicked.connect(self.player.toggle_pause)
        self.btn_next.clicked.connect(self.player.next_track)
        self.btn_prev.clicked.connect(self.player.prev_track)
        self.btn_shuffle.clicked.connect(self._toggle_shuffle)
        self.btn_repeat.clicked.connect(self._toggle_repeat)
        self.slider_volume.valueChanged.connect(self.player.set_volume)
        self.player.set_volume(self.slider_volume.value())

        self.slider_progress.sliderPressed.connect(self._on_slider_pressed)
        self.slider_progress.sliderReleased.connect(self._on_slider_released)

        self.player.time_pos_changed.connect(self._update_time)
        self.player.duration_changed.connect(self._update_duration)
        self.player.state_changed.connect(self._update_state)
        self.player.track_loaded.connect(self._update_track_info)
        self.player.shuffle_changed.connect(self._on_shuffle_changed)

    def _toggle_shuffle(self):
        self.player.toggle_shuffle()

    def _toggle_mute(self):
        if self.slider_volume.value():
            self._volume_before_mute = self.slider_volume.value()
            self.slider_volume.setValue(0)
            self.btn_volume.setIcon(icon("mute"))
        else:
            self.slider_volume.setValue(getattr(self, "_volume_before_mute", 80))
            self.btn_volume.setIcon(icon("volume"))

    def _on_shuffle_changed(self, is_shuffle):
        self.btn_shuffle.setChecked(is_shuffle)

    def _toggle_repeat(self):
        mode = self.player.toggle_repeat()
        self.btn_repeat.setChecked(mode != 0)
        self.btn_repeat.setText("1" if mode == 2 else "")
        set_text(self.btn_repeat, ("Powtarzanie wyłączone", "Powtarzaj playlistę", "Powtarzaj utwór")[mode], "toolTip")

    def _on_slider_pressed(self):
        self._is_slider_pressed = True

    def _on_slider_released(self):
        self._is_slider_pressed = False
        self.player.seek(self.slider_progress.value())

    def _update_time(self, time_pos):
        if not self._is_slider_pressed and self.player.mpv.duration:
            percentage = (time_pos / self.player.mpv.duration) * 100
            self.slider_progress.setValue(int(percentage))

        m, s = divmod(int(time_pos), 60)
        self.time_current.setText(f"{m}:{s:02d}")

    def _update_duration(self, duration):
        m, s = divmod(int(duration), 60)
        self.time_total.setText(f"{m}:{s:02d}")

    def _update_state(self, is_playing):
        self._playing = is_playing
        self.btn_play.setIcon(icon("pause" if is_playing else "play", "#FFFFFF"))
        self.visualizer.set_playing(is_playing)
        has_track = bool(self._current_track_info and self._current_track_info.get("title") and self.track_title.text() != "Wybierz utwór")
        if is_playing and has_track:
            self.visualizer.show()

    def _update_track_info(self, info: dict):
        """Update the track info section with title, artist, and thumbnail."""
        language_manager.unbind(self.track_title)
        self._current_track_info = info
        title = info.get("title", "Unknown")
        artist = info.get("artist", "")

        # Truncate with ellipsis
        metrics = self.track_title.fontMetrics()
        elided_title = metrics.elidedText(title, Qt.TextElideMode.ElideRight, 190)
        self.track_title.setText(elided_title)
        self.track_title.setToolTip(title)

        if title and title != "Wybierz utwór" and self._playing:
            self.visualizer.show()
            self.visualizer.set_playing(True)
        elif not title or title == "Wybierz utwór":
            self.visualizer.hide()
            self.visualizer.set_playing(False)

        pending = self.player._pending_metadata or {}
        self.track_artist.set_track(dict(pending, uploader=artist or pending.get('uploader', '')))
        if artist:
            elided_artist = metrics.elidedText(artist, Qt.TextElideMode.ElideRight, 220)
            self.track_artist.setText(elided_artist)
        else:
            self.track_artist.setText("")

        # Update save button to filled heart
        self.btn_save.setText("")
        self.btn_save.setIcon(icon("heart"))
        self.btn_save.setEnabled(True)

        self.thumbnail_manager.cancel_all()
        self.cover_label.setText("♪")
        # Load thumbnail
        thumb_url = info.get("thumbnail_url", "")
        if thumb_url:
            self.thumbnail_manager.load(thumb_url, self._set_cover)
        else:
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText("♪")

    def _set_cover(self, url: str, pixmap: QPixmap):
        rounded = get_rounded_pixmap(pixmap, 58, 58, radius=10)
        self.cover_label.setPixmap(rounded)

    def _on_save_to_playlist(self):
        """Show a context menu to save the currently playing track to a playlist."""
        if not self.playlist_manager or not self._current_track_info:
            return

        # Build the track dict from current info + pending metadata
        pending = self.player._pending_metadata or {}
        track = {
            **pending,
            "title": self._current_track_info.get("title", "Unknown"),
            "uploader": self._current_track_info.get("artist", pending.get("uploader", "")),
            "duration": pending.get("duration", 0),
            "thumbnail_url": self._current_track_info.get("thumbnail_url", ""),
            "url": pending.get("url", ""),
            "platform": self._current_track_info.get("platform", pending.get("platform", "")),
        }

        if not track.get("url"):
            return

        from ui.playlist_menu import show_playlist_menu
        show_playlist_menu(self, self.playlist_manager, track, self.player)

    def _save_track(self, playlist_name: str, track: dict):
        self.playlist_manager.add_track(playlist_name, track)
        # Visual feedback — filled heart
        self.btn_save.setText("")
        self.btn_save.setIcon(icon("heart", "#BEA8FF"))
        self.btn_save.setStyleSheet("")
