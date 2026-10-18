from ui.artist_page import ArtistPage
from core.i18n import text, set_text
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QGridLayout,
    QHBoxLayout, QLineEdit, QStackedWidget, QDialog, QGraphicsOpacityEffect,
    QFrame, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap

from ui.search_page import SearchPage, SearchResultCard
from ui.playlist_page import PlaylistPage
from ui.queue_page import QueuePage
from ui.create_playlist_dialog import CreatePlaylistDialog
from core.thumbnail_loader import get_rounded_pixmap, ThumbnailManager
from core.recommendations import ListeningHistory, RecommendationManager, PlaybackRecommendationManager


class HomePage(QWidget):
    """The home/landing page content."""
    
    playlist_selected = pyqtSignal(str)
    search_requested = pyqtSignal(str)
    recommendation_add_requested = pyqtSignal(dict)
    artist_requested = pyqtSignal(dict)

    def __init__(self, player, playlist_manager=None, parent=None):
        super().__init__(parent)
        self.player = player
        self.playlist_manager = playlist_manager
        self.setObjectName("HomePage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        content_widget = QWidget()
        content_widget.setObjectName("HomeScrollContent")
        content_widget.setStyleSheet("#HomeScrollContent { background: transparent; }")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(30, 24, 30, 20)
        content_layout.setSpacing(20)

        # Header with greeting
        from datetime import datetime
        hour = datetime.now().hour
        if hour < 12:
            greeting = "Dzień dobry"
        elif hour < 18:
            greeting = "Miłego popołudnia"
        else:
            greeting = "Dobry wieczór"

        header_label = text(QLabel(), greeting)
        header_label.setStyleSheet(
            "font-size: 30px; font-weight: 700; color: #FFFFFF; background: transparent;"
        )
        content_layout.addWidget(header_label)

        subtitle = text(QLabel(""), 'Twoja muzyka. Twoje tempo. Włącz coś dla siebie.')
        subtitle.setObjectName("HomeSubtitle")
        content_layout.addWidget(subtitle)

        hero = QFrame()
        self.hero = hero
        hero.setObjectName("HomeHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 24, 28, 24)
        hero_layout.setSpacing(10)
        eyebrow = QLabel("MUSIC CROW  /  DISCOVER")
        eyebrow.setObjectName("HeroEyebrow")
        hero_layout.addWidget(eyebrow)
        hero_title = text(QLabel(""), 'Odkryj swoje\nnowe brzmienie.')
        hero_title.setObjectName("HeroTitle")
        hero_layout.addWidget(hero_title)
        hero_description = text(QLabel(""), 'YouTube Music i SoundCloud w jednym miejscu. Twoja biblioteka, Twój wybór.')
        hero_description.setWordWrap(True)
        hero_description.setObjectName("HeroDescription")
        hero_layout.addWidget(hero_description)
        explore = text(QPushButton(""), 'Odkrywaj muzykę →')
        explore.setObjectName("HeroButton")
        explore.setCursor(Qt.CursorShape.PointingHandCursor)
        explore.clicked.connect(lambda: self.search_input.setFocus())
        hero_layout.addWidget(explore, alignment=Qt.AlignmentFlag.AlignLeft)
        content_layout.addWidget(hero)

        # Quick play search bar
        self.search_input = QLineEdit()
        set_text(self.search_input, 'Szukaj utworów lub wykonawców…', 'placeholderText')
        self.search_input.setObjectName("HomeSearchInput")
        self.search_input.returnPressed.connect(self._on_search)
        content_layout.addWidget(self.search_input)

        library_header = QHBoxLayout()
        library_title = text(QLabel(""), 'Twoje playlisty')
        library_title.setObjectName("LibraryTitle")
        self.library_count = QLabel()
        self.library_count.setObjectName("HomeSubtitle")
        library_header.addWidget(library_title)
        library_header.addStretch()
        library_header.addWidget(self.library_count)
        content_layout.addLayout(library_header)
        self.empty_library = text(QLabel(""), 'Zbierz ulubione utwory w jednym miejscu. Utwórz pierwszą playlistę.')
        self.empty_library.setObjectName("HomeSubtitle")
        self.empty_library.setWordWrap(True)
        content_layout.addWidget(self.empty_library)

        # Playlists grid
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(12)
        self.grid_layout.setColumnStretch(0, 1)
        self.grid_layout.setColumnStretch(1, 1)
        content_layout.addLayout(self.grid_layout)

        recommendations_header = QHBoxLayout()
        recommendations_title = text(QLabel(""), 'Proponowane dla Ciebie')
        recommendations_title.setObjectName("LibraryTitle")
        recommendations_header.addWidget(recommendations_title)
        recommendations_header.addStretch()
        self.refresh_recommendations = text(QPushButton(""), 'Odśwież ↻')
        self.refresh_recommendations.setObjectName("RecommendationRefresh")
        self.refresh_recommendations.setCursor(Qt.CursorShape.PointingHandCursor)
        recommendations_header.addWidget(self.refresh_recommendations)
        content_layout.addLayout(recommendations_header)
        self.recommendation_status = text(QLabel(""), 'Przygotowuję propozycje…')
        self.recommendation_status.setObjectName("HomeSubtitle")
        self.recommendation_status.setWordWrap(True)
        content_layout.addWidget(self.recommendation_status)
        self.recommendations_layout = QVBoxLayout()
        self.recommendations_layout.setSpacing(8)
        content_layout.addLayout(self.recommendations_layout)
        self.recommendation_thumbnails = ThumbnailManager()
        self._recommendation_tracks = []
        self.history = ListeningHistory(player, self)
        self.recommendations = RecommendationManager(player, playlist_manager, self.history, self)
        self.recommendations.updated.connect(self._show_recommendations)
        self.recommendations.status_changed.connect(lambda value: set_text(self.recommendation_status, value))
        self.recommendations.busy_changed.connect(self.refresh_recommendations.setDisabled)
        self.refresh_recommendations.clicked.connect(lambda: self.recommendations.refresh(force=True))

        content_layout.addStretch()

        self.scroll_area.setWidget(content_widget)
        layout.addWidget(self.scroll_area)

        if self.playlist_manager:
            self.playlist_manager.playlist_created.connect(lambda _: self._refresh_playlists())
            self.playlist_manager.playlist_updated.connect(lambda _: self._refresh_playlists())
            self.playlist_manager.playlist_deleted.connect(lambda _: self._refresh_playlists())

        self._refresh_playlists()

    def _show_recommendations(self, tracks):
        self.hero.setVisible(not bool(tracks))
        self.recommendation_thumbnails.cancel_all()
        while self.recommendations_layout.count():
            item = self.recommendations_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._recommendation_tracks = tracks
        for track in tracks:
            reason = text(QLabel(), track.get("recommendation_reason", "Proponowane dla Ciebie"))
            reason.setObjectName("RecommendationReason")
            self.recommendations_layout.addWidget(reason)
            card = SearchResultCard(track)
            card.clicked.connect(self._play_recommendation)
            card.artist_requested.connect(self.artist_requested.emit)
            card.add_to_playlist.connect(self.recommendation_add_requested.emit)
            self.recommendations_layout.addWidget(card)
            self.recommendation_thumbnails.load(
                track.get("thumbnail_url", ""), lambda url, pixmap, c=card: c.set_thumbnail(pixmap)
            )

    def _play_recommendation(self, track):
        index = next((i for i, item in enumerate(self._recommendation_tracks)
                      if item.get("url") == track.get("url")), 0)
        self.player.play_queue(self._recommendation_tracks, index)

    def shutdown(self):
        self.recommendations.shutdown()
        self.recommendation_thumbnails.cancel_all()

    def _refresh_playlists(self):
        # Clear existing
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Utwórz playlistę Card
        create_card = QFrame()
        create_card.setObjectName("CreateLibraryCard")
        create_card.setStyleSheet("""
            QFrame#CreateLibraryCard {
                background-color: rgba(255, 255, 255, 0.03);
                border-radius: 8px;
                border: 1px dashed rgba(255,255,255,0.2);
            }
            QFrame#CreateLibraryCard:hover {
                background-color: rgba(255, 255, 255, 0.08);
            }
        """)
        create_card.setFixedHeight(76)
        create_card.setCursor(Qt.CursorShape.PointingHandCursor)
        
        c_layout = QHBoxLayout(create_card)
        c_layout.setContentsMargins(0, 0, 14, 0)
        
        c_img = QLabel("+")
        c_img.setFixedSize(76, 76)
        c_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_img.setStyleSheet("background-color: transparent; font-size: 24px; color: #A8B1C8;")
        
        c_title = text(QLabel(""), 'Utwórz playlistę')
        c_title.setStyleSheet("font-weight: 600; font-size: 13px; color: #EAEAEA; background: transparent; border: none;")
        
        c_layout.addWidget(c_img)
        c_layout.addWidget(c_title)
        
        create_card.mouseReleaseEvent = lambda e: self._show_create_dialog()
        self.grid_layout.addWidget(create_card, 0, 0)

        if not self.playlist_manager:
            return

        playlists = self.playlist_manager.list_playlists()
        set_text(self.library_count, f"Playlisty: {len(playlists)}")
        self.empty_library.setVisible(not playlists)
        colors = [
            "rgba(139, 92, 246, 0.15)",   # purple
            "rgba(236, 72, 153, 0.15)",    # pink
            "rgba(59, 130, 246, 0.15)",    # blue
            "rgba(16, 185, 129, 0.15)",    # green
            "rgba(245, 158, 11, 0.15)",    # amber
            "rgba(239, 68, 68, 0.15)",     # red
        ]

        for i, pl_name in enumerate(playlists):
            idx = i + 1
            card = QFrame()
            card.setObjectName("LibraryCard")
            color = colors[i % len(colors)]
            card.setStyleSheet(f"""
                QFrame#LibraryCard {{
                    background-color: {color};
                    border-radius: 8px;
                    border: 1px solid rgba(255,255,255,0.04);
                }}
                QFrame#LibraryCard:hover {{
                    border: 1px solid rgba(255,255,255,0.2);
                }}
            """)
            card.setFixedHeight(76)
            card.setCursor(Qt.CursorShape.PointingHandCursor)

            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 14, 0)

            img = QLabel()
            img.setFixedSize(76, 76)
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            cover_path = self.playlist_manager.get_cover_image(pl_name)
            if cover_path and os.path.exists(cover_path):
                pixmap = QPixmap(cover_path)
                rounded = get_rounded_pixmap(pixmap, 76, 76, radius=8)
                img.setPixmap(rounded)
                img.setStyleSheet("background-color: transparent;")
            else:
                img.setText("♪")
                img.setStyleSheet("background-color: rgba(255,255,255,0.08); border-radius: 8px; font-size: 24px; color: rgba(255,255,255,0.5);")

            title = QLabel(pl_name)
            title.setWordWrap(True)
            title.setToolTip(pl_name)
            title.setStyleSheet("font-weight: 600; font-size: 13px; color: #EAEAEA; background: transparent; border: none;")

            card_layout.addWidget(img)
            card_layout.addWidget(title)

            card.mouseReleaseEvent = lambda e, name=pl_name: self.playlist_selected.emit(name)
            self.grid_layout.addWidget(card, idx // 2, idx % 2)

    def _show_create_dialog(self):
        dialog = CreatePlaylistDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = dialog.name_input.text().strip()
            if name and self.playlist_manager:
                self.playlist_manager.create_playlist(name)
                if dialog.image_path:
                    self.playlist_manager.set_cover_image(name, dialog.image_path)

    def _on_search(self):
        query = self.search_input.text().strip()
        if query:
            self.search_requested.emit(query)
            self.search_input.clear()


class MainContent(QWidget):
    """Main content area with stacked pages for navigation."""

    def __init__(self, player, playlist_manager=None, parent=None):
        super().__init__(parent)
        self.player = player
        self.setObjectName("MainContent")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()

        self.home_page = HomePage(player, playlist_manager)
        self.home_page.playlist_selected.connect(self.show_playlist)
        self.home_page.search_requested.connect(self.show_search_with_query)
        self.search_page = SearchPage(player, playlist_manager)
        self.home_page.recommendation_add_requested.connect(self.search_page._on_add_to_playlist)
        self.playlist_page = PlaylistPage(player, playlist_manager)
        self.queue_page = QueuePage(player, playlist_manager=playlist_manager)
        self.playback_recommendations = PlaybackRecommendationManager(
            player, playlist_manager, self.home_page.history, self
        )
        self.playback_recommendations.status_changed.connect(self.queue_page.set_recommendation_status)

        self.stack.addWidget(self.home_page)      # index 0
        self.stack.addWidget(self.search_page)     # index 1
        self.stack.addWidget(self.playlist_page)   # index 2
        self.stack.addWidget(self.queue_page)      # index 3

        self.artist_page = ArtistPage(player, playlist_manager)
        self.stack.addWidget(self.artist_page)     # index 4
        self._artist_origin = 0
        for page in (self.home_page, self.search_page, self.playlist_page, self.queue_page, self.artist_page):
            page.artist_requested.connect(self.show_artist)
        self.artist_page.back_requested.connect(lambda: self._fade_to_page(self._artist_origin))
        layout.addWidget(self.stack)

    def _fade_to_page(self, index: int, on_switched=None):
        """Smoothly fades in the target page when switching tabs."""
        if hasattr(self, "_current_page_anim") and self._current_page_anim:
            self._current_page_anim.stop()
            self._current_page_anim = None

        if self.stack.currentIndex() == index:
            if on_switched:
                on_switched()
            return

        target_widget = self.stack.widget(index)
        self.stack.setCurrentIndex(index)
        if on_switched:
            on_switched()

        effect = QGraphicsOpacityEffect(target_widget)
        target_widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(180)
        anim.setStartValue(0.15)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)

        def _cleanup():
            if self.stack.currentIndex() == index:
                target_widget.setGraphicsEffect(None)

        anim.finished.connect(_cleanup)
        anim.start()
        self._current_page_anim = anim

    def show_home(self):
        self._fade_to_page(0)

    def show_search(self):
        self._fade_to_page(1, on_switched=lambda: self.search_page.search_input.setFocus())

    def show_search_with_query(self, query: str):
        self._fade_to_page(1, on_switched=lambda: self.search_page.perform_search(query))

    def show_playlist(self, name: str):
        self.playlist_page.load_playlist(name)
        self._fade_to_page(2)

    def show_queue(self):
        self.queue_page.refresh()
        self._fade_to_page(3)

    def show_artist(self, track):
        if self.stack.currentIndex() != 4:
            self._artist_origin = self.stack.currentIndex()
        self.artist_page.open_artist(track)
        self._fade_to_page(4)
