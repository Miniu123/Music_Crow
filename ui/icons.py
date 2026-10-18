"""Small, consistent vector icons rendered at the display's pixel density."""
from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

PATHS = {
    'play': '<path d="m9 5 11 7-11 7Z" fill="currentColor" stroke="none"/>',
    'pause': '<path d="M8 5v14M16 5v14" stroke-width="4"/>',
    'next': '<path d="m5 5 10 7-10 7Z" fill="currentColor" stroke="none"/><path d="M19 5v14"/>',
    'previous': '<path d="m19 5-10 7 10 7Z" fill="currentColor" stroke="none"/><path d="M5 5v14"/>',
    'shuffle': '<path d="M3 6h3c5 0 7 12 12 12h3m-4-4 4 4-4 4M3 18h3c2 0 3-2 4-4m4-4c1-2 2-4 4-4h3m-4-4 4 4-4 4"/>',
    'repeat': '<path d="m17 2 4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4m14-1v2a3 3 0 0 1-3 3H3"/>',
    'volume': '<path d="M4 9h4l5-4v14l-5-4H4Zm12-1a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
    'mute': '<path d="M4 9h4l5-4v14l-5-4H4Zm13 0 5 6m0-6-5 6"/>',
    'home': '<path d="m3 10 9-7 9 7v11h-6v-7H9v7H3Z"/>',
    'search': '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/>',
    'settings': '<circle cx="12" cy="12" r="4"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2"/>',
    'queue': '<path d="M4 5h16M4 11h16M4 17h9m4-2 5 4-5 3Z"/>',
    'plus': '<path d="M12 4v16M4 12h16"/>',
    'download': '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
    'playlist': '<path d="M4 4h13M4 10h13M4 16h7m7-5v8"/><ellipse cx="15" cy="19" rx="3" ry="2"/>',
    'heart': '<path d="M12 21 3 12a6 6 0 0 1 9-8 6 6 0 0 1 9 8Z"/>',
    'edit': '<path d="m14 4 6 6M4 20l5-1L21 7l-4-4L5 15Z"/>',
    'trash': '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>',
}


def icon(name, color='#C7CADB', size=20):
    body = PATHS.get(name, PATHS['play']).replace('currentColor', color)
    data = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    renderer = QSvgRenderer(QByteArray(data.encode()))
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
