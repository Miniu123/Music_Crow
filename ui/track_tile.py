"""Cover-art tiles in a responsive grid, plus the shared "now playing" marker."""
from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from core.i18n import set_text, tr
from core.recommendations import track_key
from core.theme_manager import active_accent, active_palette, with_alpha
from ui.artist_button import ArtistButton
from ui.motion import MotionButton


def same_track(track, current):
    """True when two track dicts point at the same recording."""
    if not isinstance(track, dict) or not isinstance(current, dict):
        return False
    if not track.get('url') or not current.get('url'):
        return False
    return track_key(track) == track_key(current)


def set_now_playing(widget, value):
    """Sets the `nowPlaying` style property and restyles only when it changes."""
    value = bool(value)
    if widget.property('nowPlaying') == value:
        return False
    widget.setProperty('nowPlaying', value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
    return True


def format_duration(seconds):
    if not seconds:
        return ''
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours}:{minutes:02d}:{seconds:02d}' if hours else f'{minutes}:{seconds:02d}'


class CoverView(QWidget):
    """Square artwork with a themed placeholder, duration pill and hover play button."""

    RADIUS = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._pixmap = None
        self._scaled = None
        self.hovered = False
        self.now_playing = False
        self.duration = ''

    def set_pixmap(self, pixmap):
        self._pixmap = pixmap if pixmap and not pixmap.isNull() else None
        self._scaled = None
        self.update()

    def _scaled_pixmap(self):
        size = self.size() * self.devicePixelRatioF()
        if self._pixmap is None:
            return None
        if self._scaled is None or self._scaled.size() != size:
            scaled = self._pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                         Qt.TransformationMode.SmoothTransformation)
            x = max(0, (scaled.width() - size.width()) // 2)
            y = max(0, (scaled.height() - size.height()) // 2)
            self._scaled = scaled.copy(x, y, size.width(), size.height())
            self._scaled.setDevicePixelRatio(self.devicePixelRatioF())
        return self._scaled

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, self.RADIUS, self.RADIUS)
        painter.setClipPath(path)
        accent = active_accent()
        pixmap = self._scaled_pixmap()
        if pixmap is not None:
            painter.drawPixmap(0, 0, pixmap)
        else:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0, with_alpha(accent, 90))
            gradient.setColorAt(1, QColor(20, 24, 38))
            painter.fillRect(rect, gradient)
            painter.setPen(QColor(active_palette()['ACCENT_LIGHT']))
            font = QFont(self.font())
            font.setPixelSize(max(18, int(rect.height() * 0.28)))
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, '♪')

        if self.hovered:
            painter.fillRect(rect, QColor(5, 8, 16, 95))
        if self.duration:
            self._pill(painter, self.duration, rect.left() + 8, rect.bottom() - 8, QColor(5, 8, 16, 185),
                       QColor('#E9ECF6'), anchor_bottom=True)
        if self.now_playing:
            self._pill(painter, tr('Teraz gra'), rect.left() + 8, rect.top() + 8, accent, QColor('#FFFFFF'))
        if self.hovered or self.now_playing:
            diameter = max(34.0, min(46.0, rect.width() * 0.24))
            circle = QRectF(rect.right() - diameter - 10, rect.bottom() - diameter - 10, diameter, diameter)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(accent)
            painter.drawEllipse(circle)
            painter.setBrush(QColor('#FFFFFF'))
            triangle = QPainterPath()
            cx, cy, size = circle.center().x() + diameter * 0.04, circle.center().y(), diameter * 0.2
            triangle.moveTo(cx - size * 0.8, cy - size)
            triangle.lineTo(cx + size, cy)
            triangle.lineTo(cx - size * 0.8, cy + size)
            triangle.closeSubpath()
            painter.drawPath(triangle)

    def _pill(self, painter, label, x, y, background, foreground, anchor_bottom=False):
        font = QFont(self.font())
        font.setPixelSize(10)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        width, height = metrics.horizontalAdvance(label) + 14, 18
        top = y - height if anchor_bottom else y
        pill = QRectF(x, top, width, height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(pill, 9, 9)
        painter.setPen(foreground)
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, label)


class TrackTile(QFrame):
    """A recommendation shown as artwork first, with title, artist and reason below."""

    clicked = pyqtSignal(dict)
    add_requested = pyqtSignal(dict)
    artist_requested = pyqtSignal(dict)

    TEXT_HEIGHT = 74

    def __init__(self, track, reason='', parent=None):
        super().__init__(parent)
        self.track = dict(track)
        self.setObjectName('TrackTile')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty('nowPlaying', False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)

        self.cover = CoverView(self)
        self.cover.duration = format_duration(track.get('duration'))
        layout.addWidget(self.cover)
        layout.addSpacing(6)

        self.add_button = MotionButton('+', self.cover)
        self.add_button.setObjectName('TileAddButton')
        self.add_button.setFixedSize(30, 30)
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        set_text(self.add_button, 'Dodaj do playlisty', 'toolTip')
        self.add_button.clicked.connect(lambda: self.add_requested.emit(dict(self.track)))

        self._full_title = track.get('title') or tr('Unknown')
        self.title = QLabel(self._full_title)
        self.title.setObjectName('TileTitle')
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setToolTip(self._full_title)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.title)

        self.artist = ArtistButton(track)
        self.artist.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.artist.artist_requested.connect(self.artist_requested.emit)
        layout.addWidget(self.artist)

        self.reason = QLabel()
        self.reason.setObjectName('TileReason')
        self.reason.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        if reason:
            set_text(self.reason, reason)
        self.reason.setVisible(bool(reason))
        layout.addWidget(self.reason)

    def tile_height(self, width):
        return width - 16 + 6 + self.TEXT_HEIGHT + 16

    def resizeEvent(self, event):
        side = max(1, self.width() - 16)
        self.cover.setFixedSize(side, side)
        self.add_button.move(side - self.add_button.width() - 8, 8)
        self.title.setText(self.title.fontMetrics().elidedText(
            self._full_title, Qt.TextElideMode.ElideRight, side))
        super().resizeEvent(event)

    def set_thumbnail(self, pixmap: QPixmap):
        self.cover.set_pixmap(pixmap)

    def set_now_playing(self, value):
        if set_now_playing(self, value):
            self.cover.now_playing = bool(value)
            self.cover.update()

    def enterEvent(self, event):
        self.cover.hovered = True
        self.cover.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.cover.hovered = False
        self.cover.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not isinstance(self.childAt(event.pos()), QPushButton):
            self.clicked.emit(dict(self.track))
        super().mousePressEvent(event)


class TileGrid(QWidget):
    """Lays tiles out in as many equal columns as the width allows."""

    def __init__(self, min_tile_width=172, spacing=14, parent=None):
        super().__init__(parent)
        self.min_tile_width = min_tile_width
        self.spacing = spacing
        self.tiles = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def set_tiles(self, tiles):
        for tile in self.tiles:
            tile.hide()
            tile.deleteLater()
        self.tiles = list(tiles)
        for tile in self.tiles:
            tile.setParent(self)
            tile.show()
        self._relayout()

    def columns(self, width=None):
        width = self.width() if width is None else width
        return max(2, (width + self.spacing) // (self.min_tile_width + self.spacing))

    def _relayout(self):
        if not self.tiles:
            self.setMinimumHeight(0)
            return
        width = max(self.width(), self.min_tile_width * 2)
        columns = self.columns(width)
        tile_width = (width - self.spacing * (columns - 1)) / columns
        tile_height = self.tiles[0].tile_height(int(tile_width))
        for index, tile in enumerate(self.tiles):
            row, column = divmod(index, columns)
            x = round(column * (tile_width + self.spacing))
            tile.setGeometry(x, row * (tile_height + self.spacing), int(tile_width), tile_height)
        rows = (len(self.tiles) + columns - 1) // columns
        self.setMinimumHeight(rows * tile_height + (rows - 1) * self.spacing)

    def resizeEvent(self, event):
        self._relayout()
        super().resizeEvent(event)
