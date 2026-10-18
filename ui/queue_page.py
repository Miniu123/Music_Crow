from ui.artist_button import ArtistButton
from core.i18n import text, set_text
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame, QHBoxLayout, QPushButton, QSizePolicy, QApplication, QSplitter, QLayout
)
import json

from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QTimer, QEvent
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
    drag_started = pyqtSignal(object)
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
        self._gesture_active = False
        self._native_drag_active = False
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
        if event.button() == Qt.MouseButton.LeftButton and not isinstance(self.childAt(event.pos()), QPushButton):
            self.drag_start_position = event.pos()
            self._dragged = False
            self._set_gesture_active(True)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._native_drag_active:
            # The platform may release the source's mouse grab when native DnD
            # takes over. Only QDrag.exec() finishing ends this drag gesture.
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if (self.drag_start_position is not None and not getattr(self, "_dragged", False)
                    and self.rect().contains(event.pos())):
                self.play_clicked.emit(self.track)
            self.drag_start_position = None
            self._set_gesture_active(False)
        super().mouseReleaseEvent(event)

    def _set_gesture_active(self, active):
        if self._gesture_active != active:
            self._gesture_active = active
            self.drag_state_changed.emit(active)

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
        self._set_gesture_active(True)
        self._native_drag_active = True
        try:
            self.drag_started.emit(self)
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self._native_drag_active = False
            self.drag_start_position = None
            self._set_gesture_active(False)


class DropContainer(QWidget):
    item_moved = pyqtSignal(int, int)
    recommendation_dropped = pyqtSignal(int, int, str)

    def __init__(self, queue_type: str, parent=None, can_drop=None, move_item=None):
        super().__init__(parent)
        self.queue_type = queue_type
        self._can_drop = can_drop
        self._move_item = move_item
        self._drop_position = None
        self.setAcceptDrops(True)
        self.setObjectName("QueueDropTarget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(48)
        self.layout = QVBoxLayout(self)
        self.layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.layout.setContentsMargins(4, 8, 4, 8)
        self.layout.setSpacing(8)
        self.setProperty("dragOver", False)
        # An overlay does not change card geometry as the insertion position moves.
        self.drop_indicator = QFrame(self)
        self.drop_indicator.setObjectName("QueueDropIndicator")
        self.drop_indicator.setStyleSheet('background: #B39AFF; border: none; border-radius: 2px;')
        self.drop_indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.drop_indicator.hide()

    def _payload(self, event):
        source = event.source()
        if not isinstance(source, QueueTrackCard) or not event.mimeData().hasFormat(QUEUE_MIME):
            return None
        if self._can_drop and not self._can_drop(source):
            return None
        try:
            payload = json.loads(bytes(event.mimeData().data(QUEUE_MIME)))
            if (payload.get("queue") != source.queue_type or payload.get("index") != source.index
                    or payload.get("key") != track_key(source.track)):
                return None
            if payload['queue'] in ('priority', 'base', 'recommended') and self.queue_type in ('priority', 'base'):
                return payload
        except (ValueError, TypeError, AttributeError, KeyError):
            pass
        return None

    def _cards(self):
        return [self.layout.itemAt(i).widget() for i in range(self.layout.count())
                if isinstance(self.layout.itemAt(i).widget(), QueueTrackCard)]

    def insertion_position(self, y):
        for index, card in enumerate(self._cards()):
            if y < card.y() + card.height() / 2:
                return index
        return len(self._cards())

    def _show_position(self, y):
        cards = self._cards()
        position = self.insertion_position(y)
        self._drop_position = position
        if not cards:
            line_y = self.height() // 2
        elif position == 0:
            line_y = cards[0].y() - 4
        elif position == len(cards):
            line_y = cards[-1].geometry().bottom() + 4
        else:
            line_y = (cards[position - 1].geometry().bottom() + cards[position].y()) // 2
        self.drop_indicator.setGeometry(8, max(2, min(line_y - 2, self.height() - 6)), max(1, self.width() - 16), 4)
        self.drop_indicator.raise_()
        self.drop_indicator.show()

    def _highlight(self, value):
        if self.property('dragOver') != value:
            self.setProperty('dragOver', value)
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()

    def clear_drag(self):
        self._drop_position = None
        self.drop_indicator.hide()
        self._highlight(False)

    def dragEnterEvent(self, event):
        self.dragMoveEvent(event)

    def dragMoveEvent(self, event):
        if self._payload(event):
            self._drag_source = event.source()
            self._highlight(True)
            self._show_position(event.position().y())
            event.acceptProposedAction()
        else:
            self.clear_drag()
            event.ignore()

    def dragLeaveEvent(self, event):
        self.clear_drag()
        event.accept()

    def dropEvent(self, event):
        payload = self._payload(event)
        position = self.insertion_position(event.position().y())
        self.clear_drag()
        if not payload:
            event.ignore()
            return
        if self._move_item:
            accepted = self._move_item(payload, self.queue_type, position)
            if accepted:
                event.acceptProposedAction()
            else:
                event.ignore()
        elif payload['queue'] == 'recommended':
            self.recommendation_dropped.emit(payload['index'], position, payload['key'])
            event.acceptProposedAction()
        elif payload['queue'] == self.queue_type:
            if payload['index'] < position:
                position -= 1
            self.item_moved.emit(payload['index'], position)
            event.acceptProposedAction()
        else:
            event.ignore()


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
        self._main_snapshot = None
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
        self.btn_shuffle_queue = text(QPushButton(""), 'Wymieszaj playlistę')
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
            "Kolejka", "Twoja kolejność odtwarzania"
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
        self._scroll_restore_timer = QTimer(self)
        self._scroll_restore_timer.setSingleShot(True)
        self._scroll_restore_timer.timeout.connect(self._restore_scroll)
        self._saved_scroll_positions = None
        self._scroll_source = None
        self._drag_position = None
        self._drag_scroll_timer = QTimer(self)
        self._drag_scroll_timer.setInterval(30)
        self._drag_scroll_timer.timeout.connect(self._scroll_during_drag)

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
        scroll.viewport().setAcceptDrops(True)
        scroll.setObjectName("QueueScrollArea")
        content = QWidget()
        content.setObjectName("QueueTracksContent")
        content_layout = QVBoxLayout(content)
        content_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
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
        if not active:
            QApplication.instance().removeEventFilter(self)
            self._drag_scroll_timer.stop()
            self._scroll_source = None
            self._drag_position = None
            for container in (self._pri_container, self._base_container):
                if container:
                    container.clear_drag()
        if not active and self._refresh_pending:
            self._refresh_pending = False
            self._refresh_timer.start(0)

    def _begin_drag_scroll(self, card):
        if self._card_is_current(card):
            self._scroll_source = card
            self._drag_position = None
            QApplication.instance().installEventFilter(self)
            self._drag_scroll_timer.start()

    def eventFilter(self, watched, event):
        if self._scroll_source is not None:
            kind = event.type()
            if kind in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
                self._drag_position = None
                if isinstance(watched, QWidget) and self._card_is_current(self._scroll_source):
                    try:
                        data = json.loads(bytes(event.mimeData().data(QUEUE_MIME)))
                        source = self._scroll_source
                        if (data.get('queue') == source.queue_type and data.get('index') == source.index
                                and data.get('key') == track_key(source.track)):
                            # Event coordinates remain reliable during native DnD,
                            # including Wayland where QCursor.pos() may be stale.
                            self._drag_position = watched.mapToGlobal(event.position().toPoint())
                            if watched in (self.playlist_scroll.viewport(), self.playlist_scroll.widget()):
                                # Keep receiving moves over margins and gaps too,
                                # not only while hovering a track's drop container.
                                event.acceptProposedAction()
                                return True
                    except (ValueError, TypeError, AttributeError):
                        pass
            elif kind == QEvent.Type.DragLeave:
                # A following dragEnter/dragMove supplies the new target position.
                self._drag_position = None
            elif kind == QEvent.Type.Drop:
                self._drag_position = None
                self._drag_scroll_timer.stop()
                if watched in (self.playlist_scroll.viewport(), self.playlist_scroll.widget()):
                    source = self._scroll_source
                    if self._card_is_current(source):
                        point = watched.mapToGlobal(event.position().toPoint())
                        base_point = self._base_container.mapFromGlobal(point)
                        target = self._pri_container if base_point.y() < 0 else self._base_container
                        position = target.insertion_position(target.mapFromGlobal(point).y())
                        if self.player.move_queue_item(source.queue_type, source.index, target.queue_type,
                                                       position, track_key(source.track), source.queue_snapshot):
                            event.acceptProposedAction()
                            return True
                    event.ignore()
                    return True
        return super().eventFilter(watched, event)

    def _scroll_during_drag(self):
        if not self.isVisible() or not self._card_is_current(self._scroll_source):
            self._drag_scroll_timer.stop()
            for container in (self._pri_container, self._base_container):
                if container:
                    container.clear_drag()
            return
        cursor = self._drag_position
        if cursor is None:
            return
        area = next((area for area in (self.playlist_scroll, self.recommended_scroll)
                     if area.viewport().rect().contains(area.viewport().mapFromGlobal(cursor))), None)
        if area is None:
            return
        viewport = area.viewport()
        point = viewport.mapFromGlobal(cursor)
        edge = min(72, max(24, viewport.height() // 3))
        if point.y() < edge:
            delta = -max(4, min(32, (edge - point.y()) // 2))
        elif point.y() > viewport.height() - edge:
            delta = max(4, min(32, (point.y() - viewport.height() + edge) // 2))
        else:
            return
        bar = area.verticalScrollBar()
        bar.setValue(bar.value() + delta)
        # Scrolling moves cards underneath a stationary cursor. Refresh the marker
        # for the container now underneath it, rather than keeping the old target.
        for container in (self._pri_container, self._base_container):
            local = container.mapFromGlobal(cursor)
            if area is self.playlist_scroll and viewport.rect().contains(point) and container.rect().contains(local):
                container._highlight(True)
                container._show_position(local.y())
            else:
                container.clear_drag()

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
        card.queue_snapshot = self._main_snapshot
        card.artist_requested.connect(self.artist_requested.emit)
        card.drag_state_changed.connect(self._on_drag_state_changed)
        card.drag_started.connect(self._begin_drag_scroll)
        if queue_type != "now_playing":
            card.play_clicked.connect(lambda _, c=card: self._play_card(c))
        if queue_type == "priority":
            card.remove_clicked.connect(lambda _, c=card: self._remove_card(c))
        elif queue_type == "recommended":
            card.remove_clicked.connect(lambda _, c=card: self._remove_card(c))
            card.play_next_clicked.connect(lambda _, key, c=card: self._play_next(c, key))
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
        self._refresh_timer.stop()
        if self._saved_scroll_positions is None:
            self._saved_scroll_positions = (self.playlist_scroll.verticalScrollBar().value(),
                                            self.recommended_scroll.verticalScrollBar().value())
        self._main_snapshot = self.player.queue_edit_snapshot()
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
        self._pri_container = self._drop_container('priority')
        self._append(self.playlist_layout, self._pri_container)
        if not self.player._priority_queue:
            hint = text(QLabel(""), 'Upuść utwór tutaj, aby odtworzyć go jako następny.')
            hint.setObjectName("QueueHint")
            hint.setWordWrap(True)
            hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self._pri_container.layout.addWidget(hint)
        for i, track in enumerate(self.player._priority_queue):
            self._pri_container.layout.addWidget(self._card(track, i, "priority"))

        upcoming = self.player.upcoming_base_tracks()
        self._base_container = self._drop_container('base')
        self._append(self.playlist_layout, self._base_container)
        for i, track in enumerate(upcoming):
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

        # Qt shows new children and recalculates scroll ranges on the next event-loop turn.
        self._scroll_restore_timer.start(0)

    def _restore_scroll(self):
        if self._saved_scroll_positions is None:
            return
        for area, position in zip((self.playlist_scroll, self.recommended_scroll), self._saved_scroll_positions):
            area.widget().layout().activate()
            area.verticalScrollBar().setValue(position)
        self._saved_scroll_positions = None

    def _card_is_current(self, card):
        return (isinstance(card, QueueTrackCard) and card in self._cards
                and card.queue_snapshot == self.player.queue_edit_snapshot())

    def _drop_container(self, queue_type):
        snapshot = self._main_snapshot
        return DropContainer(queue_type, can_drop=self._card_is_current,
            move_item=lambda payload, target, position: self.player.move_queue_item(
                payload['queue'], payload['index'], target, position, payload['key'], snapshot))

    def _play_card(self, card):
        if not self._card_is_current(card):
            return
        index = card.index
        if card.queue_type == 'recommended':
            index = next((i for i, track in enumerate(self.player._recommended_queue)
                          if track_key(track) == track_key(card.track)), -1)
        self.player.play_queued_track(card.queue_type, index)

    def _remove_card(self, card):
        if not self._card_is_current(card):
            return
        if card.queue_type == 'priority':
            self._on_remove_priority(card.index)
        else:
            index = next((i for i, track in enumerate(self.player._recommended_queue)
                          if track_key(track) == track_key(card.track)), -1)
            self.player.remove_recommended(index)

    def _save_proposal(self, track):
        show_playlist_menu(self, self.playlist_manager, track)

    def _play_next(self, card, key):
        if self._card_is_current(card):
            self.player.promote_recommended(card.index, "priority", 0, key)

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
