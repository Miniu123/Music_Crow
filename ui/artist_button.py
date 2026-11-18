"""A keyboard-accessible artist link, shared by track cards and the player."""
from PyQt6.QtWidgets import QPushButton, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal
from core.i18n import set_text
from core.recommendations import artist_name
from core.artist_browser import channel_url, supported_track_url


class ArtistButton(QPushButton):
    artist_requested = pyqtSignal(dict)

    def __init__(self, track, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self.setMaximumWidth(300)
        self.setObjectName('ArtistLink')
        set_text(self, 'Przejdź do artysty / kanału', 'toolTip')
        set_text(self, 'Przejdź do artysty / kanału', 'accessibleName')
        self.clicked.connect(lambda: self.artist_requested.emit(dict(self.track)))
        self.set_track(track)

    def set_track(self, track):
        self.track = dict(track)
        self.setText(track.get('uploader') or track.get('artist') or '')
        self.setEnabled(bool(artist_name(track) or channel_url(track) or supported_track_url(track.get('url'))))

    def resizeEvent(self, event):
        name = self.track.get('uploader') or self.track.get('artist') or ''
        self.setText(self.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight, self.width()))
        super().resizeEvent(event)
