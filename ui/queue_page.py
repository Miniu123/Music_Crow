from ui.artist_button import ArtistButton
from core.i18n import text, set_text
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame, QHBoxLayout, QPushButton, QSizePolicy, QApplication, QSplitter
)
import json

from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QTimer
from PyQt6.QtGui import QPixmap, QDrag

from ui.icons import icon
from ui.playlist_menu import show_playlist_menu
from core.search_engine import PLATFORM_COLORS
from core.recommendations import track_key

QUEUE_MIME = "application/x-music-crow-queue"
from core.thumbnail_loader import ThumbnailManager, get_rounded_pixmap

class QueueTrackCard(QFrame):
    """A track card within the queue view."""
    
    drag_state_changed = pyqtSignal(bool)
    play_clicked = pyqtSignal(dict)
    artist_requested = pyqtSignal(dict)
    play_next_clicked = pyqtSignal(int, str)
    save_to_playlist = pyqtSignal(dict)
    remove_clicked = pyqtSignal(int)  # index (only for priority queue)

    def __init__(self, track: dict, index: int, queue_type: str = "base", is_priority: bool = False, parent=None, compact=False):
        super().__init__(parent)
        self.track = track
        self.index = index
        self.queue_type = queue_type
        self.is_priority = is_priority
        self.drag_start_position = None
        self.setObjectName("QueueTrackCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(94 if queue_type == "recommended" else 68)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        platform = track.get("platform", "")
        platform_color = PLATFORM_COLORS.get(platform, "#A1A9BE")

        self.setStyleSheet(f"""
            QFrame#QueueTrackCard {{
                background-color: rgba(255, 255, 255, 0.02);
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.03);
            }}
            QFrame#QueueTrackCard:hover {{
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid {platform_color};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 12, 6)
        layout.setSpacing(8 if compact else 12)

        # Thumbnail
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(40 if compact else 50, 40 if compact else 50)
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
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setToolTip(track.get("title", ""))
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        info_row = QHBoxLayout()
        info_row.setSpacing(6)
        info_row.setContentsMargins(0, 0, 0, 0)

        artist = ArtistButton(track)
        artist.artist_requested.connect(self.artist_requested.emit)
        artist.setMaximumWidth(240)

        badge = QLabel(platform)
        badge.setStyleSheet(f"""
            font-size: 9px; color: {platform_color};
            background-color: rgba(255,255,255,0.04);
            border: 1px solid {platform_color};
            border-radius: 7px; padding: 1px 6px;
        """)
        badge.setFixedHeight(16)
        badge.setVisible(bool(platform) and not compact)

        if compact:
            artist.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        info_row.addWidget(artist, 1 if compact else 0)
        info_row.addWidget(badge)
        info_row.addStretch()

        text_layout.addWidget(title)
        text_layout.addLayout(info_row)
        if queue_type == "recommended":
            self.btn_play_next = text(QPushButton(""), 'Następny →')
            self.btn_play_next.setObjectName("QueuePlayNext")
            self.btn_play_next.setCursor(Qt.CursorShape.PointingHandCursor)
            set_text(self.btn_play_next, 'Przenieś do kolejki z playlisty i odtwórz po bieżącym utworze', 'toolTip')
            self.btn_play_next.clicked.connect(
                lambda: self.play_next_clicked.emit(self.index, track_key(self.track))
            )
            actions = QHBoxLayout()
            actions.setSpacing(6)
            actions.addWidget(self.btn_play_next)
            self.btn_save_playlist = QPushButton()
            self.btn_save_playlist.setObjectName("IconButton")
            self.btn_save_playlist.setIcon(icon("playlist", size=16))
            self.btn_save_playlist.setFixedSize(28, 28)
            self.btn_save_playlist.setCursor(Qt.CursorShape.PointingHandCursor)
            set_text(self.btn_save_playlist, "Dodaj do playlisty", "toolTip")
            self.btn_save_playlist.clicked.connect(lambda: self.save_to_playlist.emit(dict(self.track)))
            actions.addWidget(self.btn_save_playlist)
            actions.addStretch()
            text_layout.addLayout(actions)
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
        dur_label.setVisible(not compact)
        layout.addWidget(dur_label)

        # Remove button (only for priority queue)
        if is_priority:
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
        rounded = get_rounded_pixmap(pixmap, self.thumbnail_label.width(), self.thumbnail_label.height(), radius=6)
        self.thumbnail_label.setPixmap(rounded)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.pos()
            self._dragged = False
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.drag_start_position is not None and not getattr(self, "_dragged", False):
                self.play_clicked.emit(self.track)
            self.drag_start_position = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if (self.drag_start_position is None or self.queue_type == "now_playing"
                or getattr(self, "_dragged", False)
                or not event.buttons() & Qt.MouseButton.LeftButton):
            return
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return
        self._dragged = True
        drag = QDrag(self)
        mime_data = QMimeData()
        payload = {"queue": self.queue_type, "index": self.index, "key": track_key(self.track)}
        mime_data.setData(QUEUE_MIME, json.dumps(payload).encode("utf-8"))
        drag.setMimeData(mime_data)
        drag.setPixmap(self.grab())
        drag.setHotSpot(event.pos())
        self.drag_state_changed.emit(True)
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self.drag_start_position = None
            self.drag_state_changed.emit(False)


class DropContainer(QWidget):
    item_moved = pyqtSignal(int, int)
    recommendation_dropped = pyqtSignal(int, int, str)

    def __init__(self, queue_type: str, parent=None):
        super().__init__(parent)
        self.queue_type = queue_type
        self.setAcceptDrops(True)
        self.setObjectName("QueueDropTarget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(48)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(6)
        self.setProperty("dragOver", False)

    def _payload(self, event):
        source = event.source()
        if not isinstance(source, QueueTrackCard) or not event.mimeData().hasFormat(QUEUE_MIME):
            return None
        try:
            payload = json.loads(bytes(event.mimeData().data(QUEUE_MIME)))
            if (payload.get("queue") != source.queue_type or payload.get("index") != source.index
                    or payload.get("key") != track_key(source.track)):
                return None
            if payload["queue"] == self.queue_type and self.queue_type in ("priority", "base"):
                return payload
            if payload["queue"] == "recommended" and self.queue_type in ("priority", "base"):
                return payload
        except (ValueError, TypeError, AttributeError, KeyError):
            pass
        return None

    def _highlight(self, value):
        self.setProperty("dragOver", value)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def dragEnterEvent(self, event):
        if self._payload(event):
            self._highlight(True)
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if self._payload(event):
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._highlight(False)
        event.accept()

    def dropEvent(self, event):
        payload = self._payload(event)
        self._highlight(False)
        if not payload:
            event.ignore()
            return
        position = 0
        for i in range(self.layout.count()):
            widget = self.layout.itemAt(i).widget()
            if isinstance(widget, QueueTrackCard):
                if event.position().y() < widget.y() + widget.height() / 2:
                    break
                position += 1
        event.acceptProposedAction()
        if payload["queue"] == "recommended":
            self.recommendation_dropped.emit(payload["index"], position, payload["key"])
        else:
            if payload["index"] < position:
                position -= 1
            self.item_moved.emit(payload["index"], position)


class QueuePage(QWidget):
    """Two visible queues: the chosen playlist and its suggested continuation."""

    play_requested = pyqtSignal(dict)
    artist_requested = pyqtSignal(dict)

    def __init__(self, player, parent=None, playlist_manager=None):
        super().__init__(parent)
        self.player = player
        self.playlist_manager = playlist_manager
        self.thumbnail_manager = ThumbnailManager()
        self._cards = []
        self._drag_active = False
        self._refresh_pending = False
        self._pri_container = None
        self._base_container = None
        self._recommendation_status = "Wybierz utwór lub playlistę, aby otrzymać propozycje."
        self.setObjectName("QueuePage")
        main = QVBoxLayout(self)
        main.setContentsMargins(24, 20, 24, 20)
        main.setSpacing(12)
        header = QHBoxLayout()
        title = text(QLabel(""), 'Kolejki odtwarzania')
        title.setObjectName("QueuePageTitle")
        header.addWidget(title)
        header.addStretch()
        self.btn_shuffle_queue = text(QPushButton(""), 'Losuj playlistę')
        self.btn_shuffle_queue.setObjectName("RecommendationRefresh")
        self.btn_shuffle_queue.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_shuffle_queue.clicked.connect(self.player.shuffle_queue)
        header.addWidget(self.btn_shuffle_queue)
        main.addLayout(header)
        self.now_layout = QVBoxLayout()
        main.addLayout(self.now_layout)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.playlist_panel, self.playlist_layout, self.playlist_scroll, self.playlist_count = self._panel(
            "Z playlisty", "Twoja kolejność odtwarzania"
        )
        self.recommended_panel, self.recommended_layout, self.recommended_scroll, self.recommended_count = self._panel(
            "Proponowane", "Odtworzą się automatycznie po playliście"
        )
        self.splitter.addWidget(self.playlist_panel)
        self.splitter.addWidget(self.recommended_panel)
        self.splitter.setSizes([500, 500])
        main.addWidget(self.splitter, 1)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.refresh)
        self.player.queue_updated.connect(lambda: self._refresh_timer.start(0))

    def _panel(self, title, subtitle):
        panel = QFrame()
        panel.setObjectName("QueuePanel")
        panel.setMinimumWidth(260)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(10, 12, 10, 10)
        outer.setSpacing(8)
        heading = QHBoxLayout()
        label = text(QLabel(), title)
        label.setObjectName("QueuePanelTitle")
        count = QLabel("0")
        count.setObjectName("QueueHint")
        heading.addWidget(label)
        heading.addStretch()
        heading.addWidget(count)
        outer.addLayout(heading)
        description = text(QLabel(), subtitle)
        description.setWordWrap(True)
        description.setObjectName("QueuePanelSubtitle")
        outer.addWidget(description)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("QueueScrollArea")
        content = QWidget()
        content.setObjectName("QueueTracksContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 4, 0)
        content_layout.setSpacing(6)
        content_layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        return panel, content_layout, scroll, count

    def set_recommendation_status(self, text):
        self._recommendation_status = text
        if hasattr(self, "recommendation_status_label"):
            set_text(self.recommendation_status_label, text)

    def _on_drag_state_changed(self, active):
        self._drag_active = active
        if not active and self._refresh_pending:
            self._refresh_pending = False
            self._refresh_timer.start(0)

    @staticmethod
    def _clear(layout, stretch=True):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        if stretch:
            layout.addStretch()

    @staticmethod
    def _append(layout, widget):
        layout.insertWidget(layout.count() - 1, widget)

    def _card(self, track, index, queue_type):
        card = QueueTrackCard(track, index, queue_type=queue_type,
                              is_priority=queue_type in ("priority", "recommended"),
                              compact=queue_type != "now_playing")
        card.artist_requested.connect(self.artist_requested.emit)
        card.drag_state_changed.connect(self._on_drag_state_changed)
        if queue_type != "now_playing":
            card.play_clicked.connect(lambda _, kind=queue_type, i=index: self.player.play_queued_track(kind, i))
        if queue_type == "priority":
            card.remove_clicked.connect(self._on_remove_priority)
        elif queue_type == "recommended":
            card.remove_clicked.connect(self.player.remove_recommended)
            card.play_next_clicked.connect(self._play_next)
            card.btn_save_playlist.setEnabled(self.playlist_manager is not None)
            card.save_to_playlist.connect(self._save_proposal)
            set_text(card, 'Odtworzy się po playliście. Możesz przeciągnąć go do lewej kolejki lub wybrać Następny.', 'toolTip')
        self._cards.append(card)
        self._load_thumb(track, card)
        return card

    def refresh(self):
        if self._drag_active:
            self._refresh_pending = True
            return
        self.thumbnail_manager.cancel_all()
        self._cards.clear()
        self._clear(self.now_layout, stretch=False)
        self._clear(self.playlist_layout)
        self._clear(self.recommended_layout)
        if self.player._current_track:
            label = text(QLabel(""), 'Teraz odtwarzane')
            label.setObjectName("QueuePanelSubtitle")
            self.now_layout.addWidget(label)
            self.now_layout.addWidget(self._card(self.player._current_track, 0, "now_playing"))

        # Priority items form the beginning of the same visible playlist queue.
        self._pri_container = DropContainer("priority")
        self._pri_container.item_moved.connect(self.player.move_priority_track)
        self._pri_container.recommendation_dropped.connect(
            lambda index, position, key: self.player.promote_recommended(index, "priority", position, key)
        )
        self._append(self.playlist_layout, self._pri_container)
        if not self.player._priority_queue:
            hint = text(QLabel(""), 'Upuść propozycję tutaj, aby odtworzyć ją jako następną.')
            hint.setObjectName("QueueHint")
            hint.setWordWrap(True)
            hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self._pri_container.layout.addWidget(hint)
        for i, track in enumerate(self.player._priority_queue):
            self._pri_container.layout.addWidget(self._card(track, i, "priority"))

        if self.player._shuffle:
            upcoming = [self.player._base_queue[i] for i in self.player._shuffled_indices
                        if 0 <= i < len(self.player._base_queue)]
        else:
            upcoming = self.player._base_queue[self.player._current_base_index + 1:]
        self._base_container = DropContainer("base")
        self._base_container.item_moved.connect(self.player.move_upcoming_base_track)
        self._base_container.recommendation_dropped.connect(
            lambda index, position, key: self.player.promote_recommended(index, "base", position, key)
        )
        self._append(self.playlist_layout, self._base_container)
        for i, track in enumerate(upcoming[:101]):
            self._base_container.layout.addWidget(self._card(track, i, "base"))
        if not upcoming:
            empty = text(QLabel(""), 'Po tej kolejce odtworzą się proponowane utwory.')
            empty.setObjectName("QueueHint")
            empty.setWordWrap(True)
            self._base_container.layout.addWidget(empty)
        self.playlist_count.setText(str(len(self.player._priority_queue) + len(upcoming)))

        self.recommendation_status_label = text(QLabel(), self._recommendation_status)
        self.recommendation_status_label.setObjectName("QueueHint")
        self.recommendation_status_label.setWordWrap(True)
        self._append(self.recommended_layout, self.recommendation_status_label)
        for i, track in enumerate(self.player._recommended_queue):
            self._append(self.recommended_layout, self._card(track, i, "recommended"))
        self.recommended_count.setText(str(len(self.player._recommended_queue)))
        if not self.player._recommended_queue:
            empty = text(QLabel(""), 'Tutaj pojawią się propozycje do dalszego słuchania.')
            empty.setObjectName("QueueHint")
            empty.setWordWrap(True)
            self._append(self.recommended_layout, empty)

    def _save_proposal(self, track):
        show_playlist_menu(self, self.playlist_manager, track)

    def _play_next(self, index, key):
        self.player.promote_recommended(index, "priority", 0, key)

    def _load_thumb(self, track, card):
        def ready(url, pixmap):
            try:
                card.set_thumbnail(pixmap)
            except RuntimeError:
                pass
        self.thumbnail_manager.load(track.get("thumbnail_url", ""), ready)

    def _on_remove_priority(self, index):
        if 0 <= index < len(self.player._priority_queue):
            self.player._priority_queue.pop(index)
            self.player.queue_updated.emit()
