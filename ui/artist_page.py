from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QHBoxLayout
from core.artist_browser import ArtistWorker, PAGE_SIZE
from core.recommendations import artist_name, track_key
from core.i18n import text, set_text
from ui.search_page import SearchPage


class ArtistPage(SearchPage):
    """Channel catalogue with independent navigation, playback and pagination."""
    back_requested = pyqtSignal()

    def __init__(self, player, playlist_manager=None, parent=None):
        super().__init__(player, playlist_manager, parent)
        self._artist_track = {}
        self._tracks = []
        self._offset = 0
        self._fallback = False
        self.search_input.hide()
        self.filter_bar.hide()
        self.layout().itemAt(0).widget().hide()
        self.back_button = text(QPushButton(), '← Wróć')
        self.back_button.clicked.connect(self.back_requested.emit)
        self.layout().insertWidget(0, self.back_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.artist_title = QLabel()
        self.artist_title.setStyleSheet('font-size: 30px; font-weight: 700; color: white;')
        self.artist_title.setWordWrap(True)
        self.layout().insertWidget(1, self.artist_title)
        self.source_label = QLabel()
        self.source_label.setWordWrap(True)
        self.source_label.setObjectName('HomeSubtitle')
        self.layout().insertWidget(2, self.source_label)
        actions = QHBoxLayout()
        self.play_all = text(QPushButton(), 'Odtwórz wszystko')
        self.play_all.clicked.connect(lambda: self.player.play_queue(self._tracks, 0) if self._tracks else None)
        self.retry = text(QPushButton(), 'Spróbuj ponownie')
        self.retry.clicked.connect(self._load)
        self.more = text(QPushButton(), 'Pokaż więcej')
        self.more.clicked.connect(self._load)
        actions.addWidget(self.play_all)
        actions.addStretch()
        actions.addWidget(self.retry)
        actions.addWidget(self.more)
        self.layout().addLayout(actions)

    def open_artist(self, track):
        if self._current_worker:
            self._current_worker.requestInterruption()
        self._current_worker = None
        self.thumbnail_manager.cancel_all()
        self._clear_results()
        self._artist_track = dict(track)
        self._tracks = []
        self._offset = 0
        self._fallback = False
        self.artist_title.setText(artist_name(track) or track.get('uploader') or '♪')
        set_text(self.source_label, 'Utwory z kanału wykonawcy')
        self.play_all.setEnabled(False)
        self.scroll_area.verticalScrollBar().setValue(0)
        self._load()

    def _load(self):
        if self._current_worker and self._current_worker.isRunning():
            return
        self.retry.hide()
        self.more.hide()
        set_text(self.status_label, 'Wczytuję utwory artysty…')
        worker = ArtistWorker(self._artist_track, self._offset, self)
        self._current_worker = worker
        self._workers.add(worker)
        worker.source_ready.connect(lambda source, w=worker: self._source(source) if self._current_worker is w else None)
        worker.results_ready.connect(lambda tracks, w=worker: self._loaded(tracks, w) if self._current_worker is w else None)
        worker.search_error.connect(lambda error, w=worker: self._failed(error) if self._current_worker is w else None)
        worker.finished.connect(lambda w=worker: self._finish_worker(w))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _source(self, source):
        self._artist_track = source['track']
        self._fallback = source['fallback']
        self.artist_title.setText(artist_name(self._artist_track) or self.artist_title.text())
        set_text(self.source_label, 'Nie znaleziono adresu kanału. Wyniki wyszukiwania nazwy artysty.'
                 if self._fallback else 'Utwory z kanału wykonawcy')

    def _loaded(self, tracks, worker):
        known = {track_key(track) for track in self._tracks}
        self._tracks.extend(track for track in tracks if track_key(track) not in known)
        scroll = self.scroll_area.verticalScrollBar().value()
        super()._on_results(self._tracks)
        self.scroll_area.verticalScrollBar().setValue(scroll)
        self.play_all.setEnabled(bool(self._tracks))
        self._offset = worker.offset + PAGE_SIZE
        self.more.setVisible(worker.has_more)
        if not self._tracks:
            set_text(self.status_label, 'Brak dostępnych utworów na tym kanale.')
        self.retry.hide()

    def _failed(self, error):
        set_text(self.status_label, error)
        self.retry.show()
        self.more.hide()

    def _on_result_clicked(self, result):
        index = next((i for i, track in enumerate(self._tracks) if track_key(track) == track_key(result)), 0)
        if self._tracks:
            self.player.play_queue(self._tracks, index)
            self.play_requested.emit(result)
