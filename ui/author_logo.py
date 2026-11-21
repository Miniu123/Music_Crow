"""The author's logo, shown in the About sections."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel

from core.i18n import set_text

LOGO = Path(__file__).resolve().parent.parent / 'assets' / 'author' / 'miniowski-wide.png'


def author_logo(width=260, parent=None):
    """A crisp, scaled copy of the wide "miniowski_" logo (empty if the file is missing)."""
    label = QLabel(parent)
    label.setObjectName('AuthorLogo')
    pixmap = QPixmap(str(LOGO))
    if not pixmap.isNull():
        ratio = label.devicePixelRatioF() or 1.0
        from core.thumbnail_loader import get_rounded_pixmap
        target_w = int(width * ratio)
        target_h = round(pixmap.height() * target_w / pixmap.width())
        scaled = get_rounded_pixmap(pixmap, target_w, target_h, radius=int(10 * ratio))
        scaled.setDevicePixelRatio(ratio)
        label.setPixmap(scaled)
        label.setFixedSize(width, int(scaled.height() / ratio))
    set_text(label, 'Autor: Miniowski_', 'toolTip')
    set_text(label, 'Logo autora: Miniowski_', 'accessibleName')
    return label
