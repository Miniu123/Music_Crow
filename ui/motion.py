"""Short interaction animations; no idle timers or layout changes on hover."""
from PyQt6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QPushButton


class MotionButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hover = 0.0
        self._press = 0.0
        self._hover_anim = self._animation('_hover', 150)
        self._press_anim = self._animation('_press', 110)
        self.pressed.connect(lambda: self._animate(self._press_anim, self._press, 1.0))
        self.released.connect(lambda: self._animate(self._press_anim, self._press, 0.0))

    def _animation(self, attribute, duration):
        animation = QVariantAnimation(self)
        animation.setDuration(duration)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        def update(value):
            setattr(self, attribute, value)
            self.update()
        animation.valueChanged.connect(update)
        return animation

    @staticmethod
    def _animate(animation, start, end):
        animation.stop()
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.start()

    def enterEvent(self, event):
        self._animate(self._hover_anim, self._hover, 1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate(self._hover_anim, self._hover, 0.0)
        super().leaveEvent(event)

    def hideEvent(self, event):
        self._hover_anim.stop()
        self._press_anim.stop()
        self._hover = self._press = 0.0
        super().hideEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.isEnabled():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(185, 171, 255, int(18 * self._hover + 24 * self._press)))
        radius = self.height() / 2 if self.width() == self.height() else min(10, self.height() / 2)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(2, 2, -2, -2), radius, radius)


class TrashButton(MotionButton):
    """A vector bin whose lid lifts on hover and settles on release."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('QueueTrashButton')
        self.setFixedSize(32, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet('''
            QPushButton#QueueTrashButton { background: rgba(244,101,126,0.055);
                border: 1px solid rgba(244,101,126,0.12); border-radius: 9px; padding: 0; }
            QPushButton#QueueTrashButton:focus { border-color: #F18CA3; }
        ''')

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2 + self._press)
        painter.scale(0.78, 0.78)
        painter.translate(-12, -12)
        color = QColor('#F3A0B1') if self.isEnabled() else QColor('#777C91')
        painter.setPen(QPen(color, 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(6, 8, 7, 21)
        painter.drawLine(7, 21, 17, 21)
        painter.drawLine(17, 21, 18, 8)
        painter.drawLine(10, 11, 10, 17)
        painter.drawLine(14, 11, 14, 17)
        painter.translate(12, 6 - self._hover * 2)
        painter.rotate(-self._hover * 12)
        painter.drawLine(-9, 0, 9, 0)
        painter.drawLine(-3, 0, -3, -3)
        painter.drawLine(-3, -3, 3, -3)
        painter.drawLine(3, -3, 3, 0)
