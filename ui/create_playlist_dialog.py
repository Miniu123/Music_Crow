from core.i18n import tr, text, set_text
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal

class CreatePlaylistDialog(QDialog):
    INPUT_STYLE = """
        QLineEdit {
            background-color: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 12px;
            padding: 12px 16px;
            color: #FFFFFF;
            font-size: 13px;
        }
        QLineEdit:focus {
            border: 1px solid rgba(139,92,246,0.5);
            background-color: rgba(255,255,255,0.1);
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(500, 320)

        self.container = QWidget(self)
        self.container.setObjectName("DialogSurface")
        self.container.setGeometry(0, 0, 500, 320)
        self.container.setStyleSheet("")

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(28, 22, 28, 24)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        title = text(QLabel(""), 'Utwórz playlistę')
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #FFFFFF; background: transparent; border: none;")
        header_row.addWidget(title)
        header_row.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setObjectName("DialogClose")
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("")
        btn_close.clicked.connect(self.reject)
        header_row.addWidget(btn_close)
        layout.addLayout(header_row)

        subtitle = text(QLabel(""), 'Nadaj nazwę swojej kolekcji i wybierz okładkę.')
        subtitle.setStyleSheet("font-size: 11px; color: #A1A9BE; background: transparent; border: none;")
        layout.addWidget(subtitle)
        layout.addSpacing(4)

        self.name_input = QLineEdit()
        set_text(self.name_input, 'Nazwa playlisty…', 'placeholderText')
        self.name_input.setFixedHeight(44)
        self.name_input.setStyleSheet("")
        layout.addWidget(self.name_input)

        self.image_path = ""
        self.btn_select_image = text(QPushButton(""), 'Wybierz okładkę (opcjonalnie)')
        self.btn_select_image.setObjectName("SecondaryButton")
        self.btn_select_image.setFixedHeight(44)
        self.btn_select_image.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_select_image.setStyleSheet("")
        self.btn_select_image.clicked.connect(self._select_image)
        layout.addWidget(self.btn_select_image)

        layout.addStretch()

        self.btn_create = text(QPushButton(""), 'Utwórz playlistę')
        self.btn_create.setObjectName("PrimaryButton")
        self.btn_create.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_create.setFixedHeight(42)
        self.btn_create.setStyleSheet("")
        self.btn_create.clicked.connect(self.accept)
        layout.addWidget(self.btn_create)

        self._drag_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_active = True
            self._drag_pos = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if getattr(self, '_drag_active', False) and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_active = False
        event.accept()

    def _select_image(self):
        path, _ = QFileDialog.getOpenFileName(self, tr('Select Cover Image'), "", tr('Images (*.png *.jpg *.jpeg)'))
        if path:
            self.image_path = path
            set_text(self.btn_select_image, "Wybrano okładkę")

