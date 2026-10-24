"""Offline license information shipped alongside the application sources."""
from pathlib import Path

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTabWidget, QPlainTextEdit, QPushButton

from core.i18n import text, set_text, tr


class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('LicenseDialog')
        set_text(self, 'Licencje', 'windowTitle')
        self.resize(720, 560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        heading = text(QLabel(), 'Music Crow · © 2026 Miniu123')
        heading.setObjectName('SettingsRowTitle')
        layout.addWidget(heading)
        summary = text(QLabel(), 'Kod Music Crow: MIT. Biblioteki mają własne licencje, w tym GPLv3 dla PyQt6.')
        summary.setWordWrap(True)
        layout.addWidget(summary)
        tabs = QTabWidget()
        root = Path(__file__).resolve().parent.parent
        for filename, title in (('LICENSE', 'MIT'), ('THIRD_PARTY_NOTICES.md', 'Biblioteki i dystrybucja')):
            view = QPlainTextEdit()
            view.setReadOnly(True)
            try:
                view.setPlainText((root / filename).read_text(encoding='utf-8'))
            except OSError:
                view.setPlainText(tr('Brakuje pliku licencji. Pełne informacje: https://github.com/Miniu123/Music_Crow'))
            tabs.addTab(view, tr(title))
        layout.addWidget(tabs)
        close = text(QPushButton(), 'Gotowe')
        close.clicked.connect(self.accept)
        layout.addWidget(close)
