"""Painted startup animation, driven by elapsed time and real UI readiness."""
import math
import os

from PyQt6.QtCore import QElapsedTimer, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap, QRadialGradient
from PyQt6.QtWidgets import QWidget

from core.i18n import tr


def _ease(value):
    value = max(0.0, min(1.0, value))
    return 1.0 - (1.0 - value) ** 3


class SplashScreen(QWidget):
    transition_started = pyqtSignal()
    finished = pyqtSignal()
    MIN_VISIBLE_MS = 950
    EXIT_MS = 260

    def __init__(self, icon_path=None, parent=None, accent="#9672FF"):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.SplashScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(520, 392)
        self.setAccessibleName("Music Crow")
        self.setAccessibleDescription(tr('Uruchamianie odtwarzacza...'))
        screen = self.screen()
        if screen:
            self.move(screen.availableGeometry().center() - self.rect().center())
        icon_path = icon_path or os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icon.png")
        self._pixmap = QPixmap(icon_path)
        self._accent = QColor(accent)
        if not self._accent.isValid():
            self._accent = QColor("#9672FF")
        self._clock = QElapsedTimer()
        self._elapsed = 0
        self._ready_at = None
        self._exit_at = None
        self._skip_requested = False
        self._completed = False
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def start_animation(self):
        if self._clock.isValid() or self._completed:
            return
        self._clock.start()
        self._timer.start()
        self.update()

    def mark_ready(self):
        """Only the creator of the main window can complete loading."""
        if self._ready_at is None and not self._completed:
            self._ready_at = self._clock.elapsed() if self._clock.isValid() else 0
            self.setAccessibleDescription(tr('Wszystko gotowe! Uruchamianie...'))
            self._tick()

    def finish_and_close(self):
        """Skip the minimum display time, but never skip initialization."""
        self._skip_requested = True
        self._tick()

    def _tick(self):
        if not self._clock.isValid() or self._completed:
            return
        self._elapsed = self._clock.elapsed()
        if self._ready_at is not None and self._exit_at is None:
            deadline = max(self.MIN_VISIBLE_MS, self._ready_at + 280)
            if self._skip_requested or self._elapsed >= deadline:
                self._exit_at = self._elapsed
                # Reveal the main window behind this card before removing it.
                self.transition_started.emit()
                self.raise_()
        if self._exit_at is not None and self._elapsed - self._exit_at >= self.EXIT_MS:
            self._completed = True
            self._timer.stop()
            self.finished.emit()
            self.hide()
            self.deleteLater()
            return
        self.update()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.finish_and_close()
            event.accept()
            return
        super().mousePressEvent(event)

    def _color(self, alpha):
        color = QColor(self._accent)
        color.setAlpha(max(0, min(255, int(alpha))))
        return color

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        elapsed = self._elapsed
        opacity = _ease(elapsed / 300)
        if self._exit_at is not None:
            opacity *= 1.0 - _ease((elapsed - self._exit_at) / self.EXIT_MS)
        painter.setOpacity(opacity)
        card = QRectF(16, 16, 488, 360)
        for spread in range(12, 0, -2):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 9))
            painter.drawRoundedRect(card.adjusted(-spread, -spread / 2, spread, spread), 26, 26)
        path = QPainterPath()
        path.addRoundedRect(card, 24, 24)
        background = QLinearGradient(card.topLeft(), card.bottomRight())
        background.setColorAt(0, QColor("#1B2033"))
        background.setColorAt(1, QColor("#0D111D"))
        painter.fillPath(path, background)
        painter.save()
        painter.setClipPath(path)
        ambient = QRadialGradient(260, 70, 245)
        ambient.setColorAt(0, self._color(36))
        ambient.setColorAt(1, self._color(0))
        painter.fillRect(card, ambient)
        painter.restore()
        painter.setPen(self._color(65))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # Logo arrives once, then gently breathes without bouncing or ripples.
        reveal = _ease(elapsed / 520)
        pulse = math.sin(elapsed / 850)
        center_y = 116 + 12 * (1 - reveal)
        painter.save()
        painter.setOpacity(opacity * reveal)
        halo = QRadialGradient(260, center_y, 86)
        halo.setColorAt(0, self._color(70 + pulse * 12))
        halo.setColorAt(1, self._color(0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(QRectF(174, center_y - 86, 172, 172))
        size = 96 * (0.88 + 0.12 * reveal)
        if not self._pixmap.isNull():
            painter.drawPixmap(QRectF(260 - size / 2, center_y - size / 2, size, size), self._pixmap, QRectF(self._pixmap.rect()))
        else:
            painter.setPen(QColor("#F4F3FF"))
            painter.setFont(QFont("sans-serif", 38))
            painter.drawText(QRectF(210, 66, 100, 100), Qt.AlignmentFlag.AlignCenter, "♫")
        painter.restore()

        self._draw_text(painter, "Music Crow", 184, 42, 30, QColor("#F5F5FC"), opacity * _ease((elapsed - 90) / 400), bold=True)
        self._draw_text(painter, tr('TWÓJ MUZYCZNY ŚWIAT'), 230, 24, 10, self._color(225), opacity * _ease((elapsed - 180) / 400), tracking=2.2)

        # Small sound bars provide motion while waiting; no invented percentages.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color(225))
        painter.setOpacity(opacity * _ease((elapsed - 240) / 350))
        for index in range(7):
            height = 5 + 12 * (0.5 + 0.5 * math.sin(elapsed / 230 + index * 0.8))
            painter.drawRoundedRect(QRectF(233 + index * 8, 284 - height / 2, 5, height), 2.5, 2.5)
        status = 'Wszystko gotowe! Uruchamianie...' if self._ready_at is not None else 'Uruchamianie odtwarzacza...'
        self._draw_text(painter, tr(status), 305, 22, 11, QColor("#A5ADC2"), opacity * _ease((elapsed - 200) / 400))

        painter.setOpacity(opacity)
        rail = QRectF(92, 343, 336, 3)
        painter.setBrush(QColor("#292F43"))
        painter.drawRoundedRect(rail, 1.5, 1.5)
        offset = (0.5 - 0.5 * math.cos(elapsed / 480)) * 0.76
        width = 0.24
        if self._ready_at is not None:
            completion = _ease((elapsed - self._ready_at) / 280)
            offset = (0.5 - 0.5 * math.cos(self._ready_at / 480)) * 0.76 * (1 - completion)
            width += 0.76 * completion
        gradient = QLinearGradient(rail.topLeft(), rail.topRight())
        gradient.setColorAt(0, self._accent)
        gradient.setColorAt(1, QColor("#66D4DF"))
        painter.setBrush(gradient)
        painter.drawRoundedRect(QRectF(rail.x() + rail.width() * offset, rail.y(), rail.width() * width, rail.height()), 1.5, 1.5)

    def _draw_text(self, painter, value, top, height, size, color, opacity, bold=False, tracking=0):
        painter.save()
        painter.setOpacity(opacity)
        font = QFont(self.font())
        font.setPixelSize(size)
        font.setWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, tracking)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(QRectF(40, top, 440, height), Qt.AlignmentFlag.AlignCenter, value)
        painter.restore()
