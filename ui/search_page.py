from ui.artist_button import ArtistButton
from core.i18n import text, set_text
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QScrollArea, QLabel, QSizePolicy, QFrame, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QCursor, QColor

from core.search_engine import SearchWorker, PLATFORM_COLORS
from core.thumbnail_loader import ThumbnailManager, get_rounded_pixmap


class PlatformFilterBar(QWidget):
    """Row of platform filter toggle buttons — all active by default, toggle to exclude."""

    filters_changed = pyqtSignal(list)

    PLATFORMS = [
        ("YouTube Music", "#FF0000"),
        ("SoundCloud", "#FF5500"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PlatformFilterBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        self.buttons: list[QPushButton] = []

        for name, color in self.PLATFORMS:
            btn = QPushButton(name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setFixedHeight(32)
            btn.clicked.connect(lambda checked, n=name: self._on_toggle(n))
            self.buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()
        self._apply_styles()

    def get_active_platforms(self) -> list[str]:
        return [btn.text() for btn in self.buttons if btn.isChecked()]

    def _on_toggle(self, platform_name: str):
        active = self.get_active_platforms()
        if len(active) == 0:
            for btn in self.buttons:
                if btn.text() == platform_name:
                    btn.setChecked(True)
                    break
        self._apply_styles()
        self.filters_changed.emit(self.get_active_platforms())

    def _apply_styles(self):
        for btn in self.buttons:
            name = btn.text()
            color = next(c for n, c in self.PLATFORMS if n == name)
            tint = QColor(color)
            soft = f"rgba({tint.red()}, {tint.green()}, {tint.blue()}, 0.12)"
            if btn.isChecked():
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {soft};
                        color: #FFFFFF;
                        border: 1px solid {color};
                        border-radius: 10px;
                        padding: 0px 20px;
                        font-weight: 600;
                        font-size: 12px;
                        min-height: 32px;
                        max-height: 32px;
                    }}
                    QPushButton:hover {{
                        background-color: {soft};
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: rgba(255, 255, 255, 0.04);
                        color: #9395AB;
                        border: 1px solid rgba(255, 255, 255, 0.08);
                        border-radius: 16px;
                        padding: 0px 20px;
                        font-weight: 500;
                        font-size: 12px;
                        min-height: 32px;
                        max-height: 32px;
                    }}
                    QPushButton:hover {{
                        background-color: rgba(255, 255, 255, 0.08);
                        color: #888888;
                        border: 1px solid {color};
                    }}
                """)


class SearchResultCard(QFrame):
    """A single search result card with thumbnail, title, artist, duration, and source badge."""

    clicked = pyqtSignal(dict)
    add_to_playlist = pyqtSignal(dict)
    artist_requested = pyqtSignal(dict)

    def __init__(self, result: dict, parent=None):
        super().__init__(parent)
        self.result = result
        self.setObjectName("SearchResultCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(76)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        platform = result.get("platform", "")
        platform_color = PLATFORM_COLORS.get(platform, "#A1A9BE")

        self.setStyleSheet(f"""
            QFrame#SearchResultCard {{
                background-color: rgba(255, 255, 255, 0.02);
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.03);
            }}
            QFrame#SearchResultCard:hover {{
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid {platform_color};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 12, 8)
        layout.setSpacing(14)

        # Thumbnail
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(58, 58)
        self.thumbnail_label.setStyleSheet(
            "background-color: rgba(255, 255, 255, 0.06); border-radius: 8px; border: none;"
        )
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setText("♪")
        self.thumbnail_label.setScaledContents(False)
        layout.addWidget(self.thumbnail_label)

        # Text info column
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 4, 0, 4)

        # Title
        self.title_label = QLabel()
        self.title_label.setStyleSheet(
            "font-weight: 600; font-size: 13px; color: #EAEAEA; background: transparent; border: none;"
        )
        self.title_label.setWordWrap(False)
        self.title_label.setMaximumWidth(420)
        metrics = self.title_label.fontMetrics()
        elided = metrics.elidedText(result.get("title", "Unknown"), Qt.TextElideMode.ElideRight, 420)
        self.title_label.setText(elided)
        self.title_label.setToolTip(result.get("title", ""))

        # Artist + platform badge row
        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        info_row.setContentsMargins(0, 0, 0, 0)

        self.artist_label = ArtistButton(result)
        self.artist_label.setMaximumWidth(300)
        self.artist_label.artist_requested.connect(self.artist_requested.emit)

        # Platform source badge
        self.platform_badge = QLabel(platform)
        self.platform_badge.setFixedHeight(18)
        self.platform_badge.setStyleSheet(f"""
            QLabel {{
                font-size: 10px;
                color: {platform_color};
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid {platform_color};
                border-radius: 9px;
                padding: 1px 8px;
            }}
        """)

        info_row.addWidget(self.artist_label)
        info_row.addWidget(self.platform_badge)
        info_row.addStretch()

        text_layout.addWidget(self.title_label)
        text_layout.addLayout(info_row)
        layout.addLayout(text_layout, 1)

        # Duration
        duration_secs = result.get("duration", 0) or 0
        if duration_secs:
            m, s = divmod(int(duration_secs), 60)
            dur_text = f"{m}:{s:02d}"
        else:
            dur_text = "—"
        self.duration_label = QLabel(dur_text)
        self.duration_label.setStyleSheet(
            "font-size: 11px; color: #9395AB; background: transparent; border: none;"
        )
        self.duration_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.duration_label)

        # Add to playlist button
        self.btn_add = QPushButton("+")
        set_text(self.btn_add, "Dodaj do playlisty", "toolTip")
        self.btn_add.setFixedSize(30, 30)
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.05);
                color: #888888;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 15px;
                font-size: 16px;
                font-weight: bold;
                padding: 0; min-height: 30px;
                max-height: 30px;
                min-width: 30px;
                max-width: 30px;
            }}
            QPushButton:hover {{
                background-color: rgba(139, 92, 246, 0.2);
                color: #8B5CF6;
                border: 1px solid rgba(139, 92, 246, 0.4);
            }}
        """)
        self.btn_add.clicked.connect(lambda: self.add_to_playlist.emit(self.result))
        layout.addWidget(self.btn_add)

    def set_thumbnail(self, pixmap: QPixmap):
        rounded = get_rounded_pixmap(pixmap, 58, 58, radius=8)
        self.thumbnail_label.setPixmap(rounded)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.pos())
            if not isinstance(child, QPushButton):
                self.clicked.emit(self.result)
        super().mousePressEvent(event)


class SearchPage(QWidget):
    """Full search page with multi-platform filters, source badges, and playlist integration."""

    play_requested = pyqtSignal(dict)
    artist_requested = pyqtSignal(dict)

    def __init__(self, player, playlist_manager=None, parent=None):
        super().__init__(parent)
        self.player = player
        self.playlist_manager = playlist_manager
        self.setObjectName("SearchPage")
        self.thumbnail_manager = ThumbnailManager()
        self._current_worker: SearchWorker | None = None
        self._result_cards: list[SearchResultCard] = []
        self._workers = set()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 24, 30, 20)
        main_layout.setSpacing(16)

        # Header
        header = text(QLabel(""), 'Odkrywaj muzykę')
        header.setStyleSheet(
            "font-size: 30px; font-weight: 700; color: #FFFFFF; background: transparent;"
        )
        main_layout.addWidget(header)

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchPageInput")
        set_text(self.search_input, 'Czego chcesz posłuchać?', 'placeholderText')
        self.search_input.setFixedHeight(46)
        self.search_input.returnPressed.connect(self._on_search)
        main_layout.addWidget(self.search_input)

        # Platform filters
        self.filter_bar = PlatformFilterBar()
        main_layout.addWidget(self.filter_bar)
        self.filter_bar.filters_changed.connect(lambda _: self._on_search())

        # Status label
        self.status_label = text(QLabel(""), 'Wpisz tytuł lub wykonawcę i odkryj kolejne utwory.')
        self.status_label.setStyleSheet("font-size: 12px; color: #9395AB; background: transparent;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

        # Results scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("SearchResultsScroll")

        self.results_widget = QWidget()
        self.results_widget.setObjectName("TracksSurface")
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setContentsMargins(0, 0, 6, 0)
        self.results_layout.setSpacing(4)
        self.results_layout.addStretch()

        self.scroll_area.setWidget(self.results_widget)
        main_layout.addWidget(self.scroll_area, 1)

    def perform_search(self, query: str):
        self.search_input.setText(query)
        self._on_search()

    def _on_search(self):
        query = self.search_input.text().strip()
        if not query:
            return

        self._clear_results()
        set_text(self.status_label, 'Szukam utworów…', 'text')
        self.status_label.setStyleSheet("font-size: 12px; color: #AAAAAA; background: transparent;")

        platforms = self.filter_bar.get_active_platforms()

        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.requestInterruption()

        self.thumbnail_manager.cancel_all()

        worker = SearchWorker(query, platforms)
        self._current_worker = worker
        self._workers.add(worker)
        worker.results_ready.connect(
            lambda results, w=worker: self._on_results(results) if w is self._current_worker else None
        )
        worker.search_error.connect(
            lambda error, w=worker: self._on_error(error) if w is self._current_worker else None
        )
        worker.finished.connect(lambda w=worker: self._finish_worker(w))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _finish_worker(self, worker):
        self._workers.discard(worker)
        if self._current_worker is worker:
            self._current_worker = None

    def shutdown(self):
        self._current_worker = None
        self.thumbnail_manager.cancel_all()
        for worker in list(self._workers):
            worker.requestInterruption()
            worker.wait()

    def _on_results(self, results: list):
        self.thumbnail_manager.cancel_all()
        self._clear_results()

        if not results:
            set_text(self.status_label, 'Brak wyników. Spróbuj innego tytułu lub wykonawcy.', 'text')
            self.status_label.setStyleSheet("font-size: 12px; color: #A1A9BE; background: transparent;")
            return

        set_text(self.status_label, f"Wyniki: {len(results)}")
        self.status_label.setStyleSheet("font-size: 12px; color: #9395AB; background: transparent;")

        for result in results:
            card = SearchResultCard(result)
            card.clicked.connect(self._on_result_clicked)
            card.artist_requested.connect(self.artist_requested.emit)
            card.add_to_playlist.connect(self._on_add_to_playlist)
            self._result_cards.append(card)

            self.results_layout.insertWidget(self.results_layout.count() - 1, card)

            thumb_url = result.get("thumbnail_url", "")
            if thumb_url:
                self.thumbnail_manager.load(
                    thumb_url,
                    lambda url, pixmap, c=card, tu=thumb_url: (
                        c.set_thumbnail(pixmap) if url == tu else None
                    ),
                )

    def _on_error(self, error_msg: str):
        set_text(self.status_label, f"Error: {error_msg}")
        self.status_label.setStyleSheet("font-size: 12px; color: #FF5555; background: transparent;")

    def _on_result_clicked(self, result: dict):
        url = result.get("url", "")
        if url:
            self.player.play_queue([result], 0)
            self.play_requested.emit(result)

    def _on_add_to_playlist(self, result: dict):
        from ui.playlist_menu import show_playlist_menu
        show_playlist_menu(self, self.playlist_manager, result, self.player)

    def _clear_results(self):
        for card in self._result_cards:
            self.results_layout.removeWidget(card)
            card.deleteLater()
        self._result_cards.clear()
