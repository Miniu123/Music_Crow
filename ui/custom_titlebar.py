from core.i18n import text, set_text, language_manager
import os
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSpacerItem, QSizePolicy
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPixmap, QIcon
from core.thumbnail_loader import get_rounded_pixmap


class CustomTitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setObjectName("TitleBar")
        self.setFixedHeight(40)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 0, 5, 0)
        self._layout.setSpacing(8)

        # Breadcrumb: the sidebar already shows the app name, so name the page instead.
        app_label = QLabel("MUSIC CROW")
        app_label.setObjectName("TitleApp")
        self._separator = QLabel("/")
        self._separator.setObjectName("TitleSeparator")
        self.page_label = text(QLabel(""), 'Strona główna')
        self.page_label.setObjectName("TitlePage")
        self._layout.addWidget(app_label)
        self._layout.addWidget(self._separator)
        self._layout.addWidget(self.page_label)

        # Draggable space across the top bar
        self._layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        # Window control buttons
        self.min_btn = QPushButton("—")
        self.min_btn.setFixedSize(32, 32)
        self.min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.min_btn.clicked.connect(self.parent_window.showMinimized)

        self.max_btn = QPushButton("□")
        self.max_btn.setFixedSize(32, 32)
        self.max_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.max_btn.clicked.connect(self.toggle_max_restore)

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("CloseButton")
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.parent_window.close)

        self._layout.addWidget(self.min_btn)
        self._layout.addWidget(self.max_btn)
        self._layout.addWidget(self.close_btn)

    def toggle_max_restore(self):
        if self.parent_window.isMaximized():
            self.parent_window.showNormal()
            self.max_btn.setText("□")
        else:
            self.parent_window.showMaximized()
            self.max_btn.setText("❐")

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_max_restore()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # On Wayland, startSystemMove() is the ONLY way to move a window.
            # On X11, it also works and is the cleanest approach.
            window = self.window()
            if window:
                handle = window.windowHandle()
                if handle:
                    handle.startSystemMove()
            event.accept()

    def mouseMoveEvent(self, event):
        # Not needed — startSystemMove hands off to the compositor
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()


    PAGE_TITLES = {"home": "Strona główna", "search": "Wyszukiwanie", "playlist": "Playlista",
                   "queue": "Kolejka", "artist": "Wykonawca"}

    def set_page(self, page, playlist=""):
        if page == "playlist" and playlist:
            language_manager.unbind(self.page_label)  # user content is never translated
            self.page_label.setText(playlist)
        else:
            set_text(self.page_label, self.PAGE_TITLES.get(page, "Strona główna"))
