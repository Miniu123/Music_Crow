from core.i18n import text, set_text
import os
import math
import random
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QLinearGradient, QPixmap, QPainterPath


class SoundwaveVisualizer(QWidget):
    """
    Mini equalizer soundwave animation (5 bouncy bars with spring physics & neon gradient).
    Automatically sleeps when paused to consume 0% CPU.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 20)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._is_playing = False
        self._num_bars = 5
        self._bars = [0.2] * self._num_bars
        self._velocities = [0.0] * self._num_bars
        self._targets = [0.2] * self._num_bars
        self._phase = 0.0

        # Animation timer (60 FPS for ultra-fluid movement)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)

    def set_playing(self, is_playing: bool):
        self._is_playing = is_playing
        if is_playing:
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._targets = [0.15] * self._num_bars

    def _on_tick(self):
        if self._is_playing:
            self._phase += 0.09
            # Dynamic frequency offsets
            self._targets[0] = 0.25 + 0.65 * abs(math.sin(self._phase * 1.4))
            self._targets[1] = 0.35 + 0.65 * abs(math.sin(self._phase * 1.9 + 0.4))
            self._targets[2] = 0.20 + 0.80 * abs(math.sin(self._phase * 1.2 + 1.1))
            self._targets[3] = 0.30 + 0.70 * abs(math.sin(self._phase * 2.3 + 0.7))
            self._targets[4] = 0.25 + 0.60 * abs(math.sin(self._phase * 1.7 + 1.8))

            # Spring physics update
            for i in range(self._num_bars):
                force = (self._targets[i] - self._bars[i]) * 0.32
                self._velocities[i] = (self._velocities[i] + force) * 0.72
                self._bars[i] += self._velocities[i]
                self._bars[i] = max(0.1, min(1.0, self._bars[i]))
            self.update()
        else:
            # Smoothly settle to resting state
            settled = True
            for i in range(self._num_bars):
                self._bars[i] += (0.15 - self._bars[i]) * 0.20
                if abs(self._bars[i] - 0.15) > 0.01:
                    settled = False
            self.update()
            if settled:
                self._timer.stop()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bar_width = 3.0
        gap = 2.5
        total_width = self._num_bars * bar_width + (self._num_bars - 1) * gap
        start_x = (self.width() - total_width) / 2.0
        max_h = self.height() - 4.0

        for i, val in enumerate(self._bars):
            h = max(2.5, val * max_h)
            x = start_x + i * (bar_width + gap)
            y = self.height() - 2.0 - h

            rect = QRectF(x, y, bar_width, h)

            if self._is_playing:
                # Vertical gradient: purple bottom -> cyan top
                grad = QLinearGradient(x, y + h, x, y)
                grad.setColorAt(0.0, QColor(139, 92, 246, 230))
                grad.setColorAt(1.0, QColor(6, 182, 212, 255))
                painter.setBrush(grad)
            else:
                painter.setBrush(QColor(120, 120, 140, 110))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 1.5, 1.5)


class AnimatedBrandWidget(QWidget):
    """
    Sidebar header widget featuring the Crow logo with interactive hover glow,
    spring-physics audio visualizer soundwave, and smooth navigation.
    """

    clicked = pyqtSignal()

    def __init__(self, player=None, parent=None):
        super().__init__(parent)
        self.player = player
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(64)
        self.setObjectName("AnimatedBrandWidget")

        self._is_hovered = False
        self._hover_factor = 0.0  # 0.0 -> 1.0 smooth interpolation
        self._is_playing = False
        self._glow_phase = 0.0

        # Load icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icon.png")
        self._pixmap = None
        if os.path.exists(icon_path):
            self._pixmap = QPixmap(icon_path)

        # Pulse & hover animation timer (60 FPS)
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._on_anim_tick)

        # Connect to player playback signals
        if self.player:
            self.player.state_changed.connect(self._on_playback_state_changed)

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        # Left: Logo container
        self.logo_container = QWidget(self)
        self.logo_container.setFixedSize(40, 40)
        self.logo_container.paintEvent = self._paint_logo

        # Center: Title + Subtitle
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 2, 0, 2)
        text_layout.setSpacing(1)

        self.title_label = QLabel("Music Crow", self)
        self.title_label.setStyleSheet("""
            font-size: 15px;
            font-weight: 700;
            color: #FFFFFF;
            background: transparent;
            letter-spacing: 0.5px;
        """)

        self.sub_label = text(QLabel("", self), 'Twoja muzyka')
        self.sub_label.setStyleSheet("""
            font-size: 10px;
            font-weight: 500;
            color: #666677;
            background: transparent;
        """)

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.sub_label)

        # Right: Mini Soundwave Visualizer
        self.visualizer = SoundwaveVisualizer(self)

        layout.addWidget(self.logo_container)
        layout.addLayout(text_layout, 1)
        layout.addWidget(self.visualizer)

    def paintEvent(self, event):
        """Draw interactive hover pill card."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._hover_factor > 0.01:
            pill_rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
            bg_col = QColor(255, 255, 255, int(15 * self._hover_factor))
            border_col = QColor(139, 92, 246, int(60 * self._hover_factor))
            painter.setBrush(bg_col)
            painter.setPen(border_col)
            painter.drawRoundedRect(pill_rect, 14, 14)

    def _paint_logo(self, event):
        painter = QPainter(self.logo_container)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w = self.logo_container.width()
        h = self.logo_container.height()
        cx = w / 2.0
        cy = h / 2.0

        # Draw glowing aura if playing or hovered
        effective_glow = max(self._hover_factor, 1.0 if self._is_playing else 0.0)
        if effective_glow > 0.01:
            pulse_extra = (3.0 * math.sin(self._glow_phase)) if self._is_playing else 0.0
            glow_radius = 17.0 + pulse_extra + 3.0 * self._hover_factor
            radial = QRadialGradient(cx, cy, glow_radius)
            alpha = int((140 if self._is_playing else 100) * effective_glow)
            radial.setColorAt(0.0, QColor(139, 92, 246, alpha))
            radial.setColorAt(0.65, QColor(99, 102, 241, int(alpha * 0.45)))
            radial.setColorAt(1.0, QColor(139, 92, 246, 0))
            painter.setBrush(radial)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(cx - glow_radius, cy - glow_radius, glow_radius * 2, glow_radius * 2))

        # Sub-pixel smooth scaling (28.0px -> 30.0px on hover)
        logo_size = 28.0 + 2.0 * self._hover_factor
        target_rect = QRectF(cx - logo_size / 2.0, cy - logo_size / 2.0, logo_size, logo_size)

        if self._pixmap and not self._pixmap.isNull():
            source_rect = QRectF(self._pixmap.rect())
            painter.drawPixmap(target_rect, self._pixmap, source_rect)
        else:
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(self.logo_container.rect(), Qt.AlignmentFlag.AlignCenter, "🎵")

    def _on_anim_tick(self):
        # Update hover factor smoothly
        target_hover = 1.0 if self._is_hovered else 0.0
        diff = target_hover - self._hover_factor
        if abs(diff) > 0.02:
            self._hover_factor += diff * 0.20
            self.update()
            self.logo_container.update()
        else:
            self._hover_factor = target_hover

        # Update glow pulse if playing
        if self._is_playing:
            self._glow_phase += 0.07
            if self._glow_phase > 2 * math.pi:
                self._glow_phase -= 2 * math.pi
            self.logo_container.update()

        # Stop timer if completely settled and not playing
        if not self._is_playing and abs(self._hover_factor - target_hover) < 0.01:
            self._anim_timer.stop()

    def _on_playback_state_changed(self, is_playing: bool):
        self._is_playing = is_playing
        self.visualizer.set_playing(is_playing)

        if is_playing:
            set_text(self.sub_label, 'Odtwarzanie 🎵', 'text')
            self.sub_label.setStyleSheet("font-size: 10px; font-weight: 600; color: #9672FF; background: transparent;")
            if not self._anim_timer.isActive():
                self._anim_timer.start()
        else:
            set_text(self.sub_label, 'Twoja muzyka', 'text')
            self.sub_label.setStyleSheet("font-size: 10px; font-weight: 500; color: #666677; background: transparent;")
            if not self._is_hovered:
                self._anim_timer.stop()
            self.logo_container.update()

    def enterEvent(self, event):
        self._is_hovered = True
        self.title_label.setStyleSheet("""
            font-size: 15px;
            font-weight: 700;
            color: #C4B5FD;
            background: transparent;
            letter-spacing: 0.5px;
        """)
        if not self._anim_timer.isActive():
            self._anim_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        self.title_label.setStyleSheet("""
            font-size: 15px;
            font-weight: 700;
            color: #FFFFFF;
            background: transparent;
            letter-spacing: 0.5px;
        """)
        if not self._anim_timer.isActive():
            self._anim_timer.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
