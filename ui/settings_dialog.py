from core.i18n import tr, text, set_text, language_manager
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QColorDialog,
    QFrame, QScrollArea, QWidget, QCheckBox, QGridLayout, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from ui.jump_slider import JumpSlider
from core.theme_manager import PRESETS

COLOR_OPTIONS = [
    ('accent', 'ACCENT_COLOR', 'Kolor akcentu', 'Przyciski, aktywne elementy i suwaki'),
    ('player', 'PLAYER_BAR_BG', 'Pasek odtwarzania', 'Tło dolnego panelu odtwarzacza'),
    ('window', 'MAIN_BG_COLOR', 'Tło okna', 'Podstawowy kolor aplikacji'),
    ('top', 'CENTRAL_BG_START', 'Gradient · góra', 'Górna część głównego panelu'),
    ('bottom', 'CENTRAL_BG_END', 'Gradient · dół', 'Dolna część głównego panelu'),
]


def text_column(layout, label, description):
    column = QVBoxLayout()
    column.setSpacing(4)
    title = text(QLabel(), label)
    title.setObjectName('SettingsRowTitle')
    detail = text(QLabel(), description)
    detail.setObjectName('SettingsRowDescription')
    detail.setWordWrap(True)
    column.addWidget(title)
    column.addWidget(detail)
    layout.addLayout(column, 1)


class ColorPickerRow(QWidget):
    def __init__(self, label, desc, theme_key, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_key, self.theme_manager = theme_key, theme_manager
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        text_column(layout, label, desc)
        self.swatch = QPushButton()
        self.swatch.setFixedSize(36, 36)
        set_text(self.swatch, 'Zmień kolor', 'toolTip')
        self.swatch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.swatch.clicked.connect(self._pick_color)
        layout.addWidget(self.swatch)
        theme_manager.theme_changed.connect(self._refresh)
        self._refresh()

    def _current_hex(self):
        value = str(self.theme_manager.current_theme.get(self.theme_key, '#10131F'))
        return '#10131F' if value.startswith('rgba') else value

    def _refresh(self):
        self.swatch.setStyleSheet(f'background: {self._current_hex()}; border: 2px solid #68728F; border-radius: 10px;')

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self._current_hex()), self, tr('Wybierz kolor'))
        if color.isValid():
            self.theme_manager.update_color(self.theme_key, color.name())


class SliderRow(QWidget):
    def __init__(self, label, desc, theme_key, min_val, max_val, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_key, self.theme_manager = theme_key, theme_manager
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        text_column(layout, label, desc)
        self.val_label = QLabel()
        self.val_label.setObjectName('SettingsValue')
        self.val_label.setFixedWidth(28)
        self.slider = JumpSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(min_val, max_val)
        self.slider.setFixedWidth(120)
        self.slider.setValue(int(theme_manager.current_theme.get(theme_key, 0)))
        self.val_label.setText(str(self.slider.value()))
        self.slider.valueChanged.connect(lambda value: self.val_label.setText(str(value)))
        self.slider.sliderReleased.connect(self._save)
        layout.addWidget(self.val_label)
        layout.addWidget(self.slider)
        theme_manager.theme_changed.connect(self._refresh)

    def _refresh(self):
        self.slider.setValue(int(self.theme_manager.current_theme.get(self.theme_key, 0)))

    def _save(self):
        self.theme_manager.current_theme[self.theme_key] = self.slider.value()
        self.theme_manager.save_theme()
        self.theme_manager.theme_changed.emit()


class ToggleRow(QWidget):
    def __init__(self, label, desc, theme_key, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_key, self.theme_manager = theme_key, theme_manager
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        text_column(layout, label, desc)
        self.checkbox = QCheckBox()
        set_text(self.checkbox, label, "accessibleName")
        self.checkbox.setChecked(bool(theme_manager.current_theme.get(theme_key, True)))
        self.checkbox.toggled.connect(self._save)
        layout.addWidget(self.checkbox)
        theme_manager.theme_changed.connect(self._refresh)

    def _refresh(self):
        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(bool(self.theme_manager.current_theme.get(self.theme_key, True)))
        self.checkbox.blockSignals(False)

    def _save(self, checked):
        self.theme_manager.current_theme[self.theme_key] = checked
        self.theme_manager.save_theme()
        self.theme_manager.theme_changed.emit()


class DraggableHeader(QWidget):
    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
        self._drag_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.dialog.windowHandle()
            if handle and handle.startSystemMove():
                return
            self._drag_pos = event.globalPosition().toPoint() - self.dialog.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.dialog.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


class SettingsDialog(QDialog):
    def __init__(self, theme_manager, parent=None, sync_manager=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        language_manager.configure(theme_manager)
        set_text(self, 'Ustawienia', 'windowTitle')
        self.setObjectName('SettingsDialog')
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(540, 540)
        self.resize(600, 680)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(16)
        header = DraggableHeader(self)
        head = QHBoxLayout(header)
        head.setContentsMargins(0, 0, 0, 0)
        title = text(QLabel(""), 'Ustawienia')
        title.setObjectName('DialogTitle')
        head.addWidget(title)
        head.addStretch()
        close = QPushButton('✕')
        close.setObjectName('DialogClose')
        close.setFixedSize(30, 30)
        close.clicked.connect(self.accept)
        head.addWidget(close)
        root.addWidget(header)
        subtitle = text(QLabel(""), 'Dopasuj wygląd i brzmienie do siebie.')
        subtitle.setObjectName('SettingsRowDescription')
        root.addWidget(subtitle)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName('TracksSurface')
        content = QVBoxLayout(body)
        content.setContentsMargins(2, 0, 12, 0)
        content.setSpacing(14)
        if sync_manager is not None:
            from ui.cloud_settings import CloudSettings
            cloud = self._section(content, 'DYSK GOOGLE')
            self.cloud_settings = CloudSettings(sync_manager, body)
            cloud.addWidget(self.cloud_settings)
        language_section = self._section(content, 'JĘZYK')
        row = QHBoxLayout()
        text_column(row, 'Język aplikacji', 'Zmiana języka działa od razu.')
        self.language_combo = QComboBox()
        self.language_combo.setObjectName('LanguageSelector')
        self.language_combo.addItem('Polski', 'pl')
        self.language_combo.addItem('English', 'en')
        self.language_combo.setCurrentIndex(self.language_combo.findData(language_manager.language))
        self.language_combo.currentIndexChanged.connect(
            lambda index: language_manager.set_language(self.language_combo.itemData(index))
        )
        language_manager.changed.connect(self._sync_language)
        row.addWidget(self.language_combo)
        language_section.addLayout(row)
        presets = self._section(content, 'MOTYW KOLORYSTYCZNY')
        grid = QGridLayout()
        for i, (name, preset) in enumerate(PRESETS.items()):
            button = QPushButton(name)
            button.setObjectName('PresetButton')
            accent = preset['ACCENT_COLOR']
            button.setStyleSheet(f'border-left: 4px solid {accent};')
            button.clicked.connect(lambda checked, n=name: theme_manager.apply_preset(n))
            grid.addWidget(button, i // 2, i % 2)
        presets.addLayout(grid)
        colors = self._section(content, 'KOLORY APLIKACJI')
        for _, key, label, description in COLOR_OPTIONS:
            colors.addWidget(ColorPickerRow(label, description, key, theme_manager, body))
        audio = self._section(content, 'ODTWARZANIE I BRZMIENIE')
        audio.addWidget(ToggleRow('Przygotuj następny utwór',
                                 'Pobieraj kolejny utwór w tle, aby skrócić przerwę w odtwarzaniu.',
                                 'PREFETCH_ENABLED', theme_manager, body))
        audio.addWidget(ToggleRow('Płynne przejścia', 'Mieszaj końcówkę utworu z początkiem następnego.',
                                 'CROSSFADE_ENABLED', theme_manager, body))
        audio.addWidget(SliderRow('Długość przejścia', 'Czas nakładania utworów w sekundach.',
                                 'CROSSFADE_DURATION', 1, 15, theme_manager, body))
        audio.addWidget(SliderRow('Niskie tony', 'Wzmocnienie basu w dB.', 'BASS_GAIN', -15, 15, theme_manager, body))
        audio.addWidget(SliderRow('Wysokie tony', 'Wzmocnienie wysokich częstotliwości w dB.', 'TREBLE_GAIN', -15, 15, theme_manager, body))
        about = self._section(content, 'O APLIKACJI I LICENCJE')
        text_column(about, 'Music Crow · © 2026 Miniu123',
                    'Kod Music Crow: MIT. Biblioteki mają własne licencje, w tym GPLv3 dla PyQt6.')
        licenses = text(QPushButton(), 'Przeczytaj licencje')
        licenses.setCursor(Qt.CursorShape.PointingHandCursor)
        licenses.clicked.connect(self._show_licenses)
        about.addWidget(licenses)
        content.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        done = text(QPushButton(""), 'Gotowe')
        done.setObjectName('PrimaryButton')
        done.setFixedHeight(38)
        done.clicked.connect(self.accept)
        root.addWidget(done, alignment=Qt.AlignmentFlag.AlignRight)

    def _show_licenses(self):
        from ui.license_dialog import LicenseDialog
        LicenseDialog(self).exec()

    def _sync_language(self, language):
        self.language_combo.blockSignals(True)
        self.language_combo.setCurrentIndex(self.language_combo.findData(language))
        self.language_combo.blockSignals(False)

    def _section(self, parent, title):
        frame = QFrame()
        frame.setObjectName('SettingsSection')
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        label = text(QLabel(), title)
        label.setObjectName('SectionTitle')
        layout.addWidget(label)
        parent.addWidget(frame)
        return layout
