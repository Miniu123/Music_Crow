from PyQt6.QtCore import Qt, QObject, QUrl
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPainterPath
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply


def get_rounded_pixmap(pixmap: QPixmap, width: int, height: int, radius: int = 8) -> QPixmap:
    """Scales, crops and smoothly rounds a pixmap to the given dimensions and radius with antialiasing."""
    if not pixmap or pixmap.isNull():
        return pixmap
    scaled = pixmap.scaled(
        width, height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation
    )
    x = max(0, (scaled.width() - width) // 2)
    y = max(0, (scaled.height() - height) // 2)
    cropped = scaled.copy(x, y, width, height)

    rounded = QPixmap(width, height)
    rounded.fill(Qt.GlobalColor.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(0, 0, width, height, radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, cropped)
    painter.end()
    return rounded


class ThumbnailManager(QObject):
    """Asynchronous downloads on the GUI event loop with bounded caching."""

    def __init__(self):
        super().__init__()
        self._network = QNetworkAccessManager(self)
        self._cache = {}
        self._pending = {}

    def load(self, url: str, callback):
        if not url or QUrl(url).scheme() not in ("http", "https"):
            return
        if url in self._cache:
            callback(url, self._cache[url])
            return
        if url in self._pending:
            self._pending[url][1].append(callback)
            return
        request = QNetworkRequest(QUrl(url))
        request.setTransferTimeout(10000)
        reply = self._network.get(request)
        self._pending[url] = (reply, [callback])
        reply.finished.connect(lambda: self._finished(url, reply))

    def _finished(self, url, reply):
        pending = self._pending.get(url)
        if pending is None or pending[0] is not reply:
            reply.deleteLater()
            return
        _, callbacks = self._pending.pop(url)
        if reply.error() == QNetworkReply.NetworkError.NoError:
            pixmap = QPixmap()
            if pixmap.loadFromData(bytes(reply.readAll())):
                if len(self._cache) >= 128:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[url] = pixmap
                for callback in callbacks:
                    callback(url, pixmap)
        reply.deleteLater()

    def clear_cache(self):
        self._cache.clear()

    def cancel_all(self):
        pending, self._pending = self._pending, {}
        for reply, _ in pending.values():
            reply.abort()
