from core.i18n import text, set_text
import os
import math
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QLinearGradient, QPixmap, QFont, QPainterPath


class AnimatedLogo(QWidget):
    """
    High-fidelity animated Crow logo widget with sub-pixel scaling,
    radial neon breathing glow, and expanding energy ripple effect.
    """

    def __init__(self, icon_path, parent=None):
        super().__init__(parent)
        self.setFixedSize(160, 160)
        self.icon_path = icon_path
        self._pixmap = None
        if os.path.exists(icon_path):
            self._pixmap = QPixmap(icon_path)

        self._phase = 0.0
        self._ripple_radius = 45.0
        self._ripple_opacity = 0.0

        # Animation timer (60 FPS for ultra-smooth fluid motion)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    def _on_tick(self):
        self._phase += 0.04
        if self._phase > 2 * math.pi:
            self._phase -= 2 * math.pi

        # Expanding ripple wave
        self._ripple_radius += 0.6
        if self._ripple_radius > 75.0:
            self._ripple_radius = 42.0

        # Ripple opacity fades out as it expands
        norm = (self._ripple_radius - 42.0) / 33.0  # 0.0 -> 1.0
        self._ripple_opacity = max(0.0, min(1.0, math.sin(norm * math.pi)))

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        cx = self.width() / 2.0
        cy = self.height() / 2.0

        # Gentle floating offset
        float_y = 2.0 * math.sin(self._phase)
        center_y = cy + float_y

        # Scale breathing (1.0 -> 1.045)
        scale = 1.0 + 0.04 * math.sin(self._phase)
        glow_intensity = 0.55 + 0.35 * (0.5 + 0.5 * math.sin(self._phase))

        # 1. Outer ambient radial purple glow
        glow_r = 72.0 * scale
        radial = QRadialGradient(cx, center_y, glow_r)
        c_core = QColor(139, 92, 246, int(140 * glow_intensity))
        c_mid = QColor(99, 102, 241, int(60 * glow_intensity))
        c_edge = QColor(139, 92, 246, 0)
        radial.setColorAt(0.0, c_core)
        radial.setColorAt(0.5, c_mid)
        radial.setColorAt(1.0, c_edge)

        painter.setBrush(radial)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx - glow_r, center_y - glow_r, glow_r * 2, glow_r * 2))

        # 2. Expanding energy ripple ring
        if self._ripple_opacity > 0.01:
            ring_pen = QColor(167, 139, 250, int(90 * self._ripple_opacity))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(ring_pen)
            r_rad = self._ripple_radius
            painter.drawEllipse(QRectF(cx - r_rad, center_y - r_rad, r_rad * 2, r_rad * 2))

        # 3. Draw high-resolution anti-aliased logo
        if self._pixmap and not self._pixmap.isNull():
            base_size = 80.0 * scale
            draw_x = cx - base_size / 2.0
            draw_y = center_y - base_size / 2.0
            target_rect = QRectF(draw_x, draw_y, base_size, base_size)
            source_rect = QRectF(self._pixmap.rect())
            painter.drawPixmap(target_rect, self._pixmap, source_rect)
        else:
            font = QFont("Segoe UI Emoji", int(40 * scale))
            painter.setFont(font)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "🎵")


class SplashScreen(QWidget):
    """
    Ultra-sleek dark glassmorphism splash screen with soft drop shadow,
    pulsing neon logo, fluid interpolated progress bar, and buttery transitions.
    """

    finished = pyqtSignal()

    def __init__(self, icon_path=None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.SplashScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(520, 380)

        # Robust multi-monitor centering
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2
            )

        if not icon_path:
            icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icon.png")

        # Opacity effect for smooth window fade-in / fade-out
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        # Layout inside the glass card (20px padding accounts for drop shadow)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 40, 50, 42)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Animated Logo
        self.logo_widget = AnimatedLogo(icon_path, self)
        layout.addWidget(self.logo_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # Title
        self.title_label = QLabel("Music Crow", self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("""
            font-size: 29px;
            font-weight: 800;
            color: #FFFFFF;
            letter-spacing: 1.5px;
            background: transparent;
        """)
        layout.addWidget(self.title_label)

        # Tagline
        self.tagline_label = text(QLabel("", self), 'TWÓJ MUZYCZNY ŚWIAT')
        self.tagline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tagline_label.setStyleSheet("""
            font-size: 10px;
            font-weight: 700;
            color: #9672FF;
            letter-spacing: 3.5px;
            background: transparent;
            margin-bottom: 6px;
        """)
        layout.addWidget(self.tagline_label)

        layout.addSpacing(6)

        # Sleek Neon Progress Bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #9672FF,
                    stop:0.6 #6366F1,
                    stop:1 #06B6D4
                );
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Status text
        self.status_label = text(QLabel("", self), 'Uruchamianie odtwarzacza...')
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            font-size: 11px;
            font-weight: 500;
            color: #7E7E94;
            background: transparent;
        """)
        layout.addWidget(self.status_label)

        # Smooth simulation stages
        self._steps = [
            (25, "Inicjalizacja silnika MPV i kodeków..."),
            (50, "Wczytywanie playlist i biblioteki utworów..."),
            (75, "Ładowanie motywów i korektora graficznego..."),
            (92, "Przygotowywanie interfejsu użytkownika..."),
            (100, "Wszystko gotowe! Uruchamianie...")
        ]
        self._current_step_idx = 0
        self._target_progress = 0.0
        self._current_progress = 0.0
        self._is_finishing = False

        # Fluid progress interpolation timer (60 FPS)
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(16)
        self._progress_timer.timeout.connect(self._on_progress_tick)

        # Step advancement timer
        self._step_timer = QTimer(self)
        self._step_timer.setInterval(300)
        self._step_timer.timeout.connect(self._advance_step)

    def paintEvent(self, event):
        """Draw sleek rounded glass card with ambient dark shadow and glowing border."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Card rect (leaving 16px around for shadow effect)
        margin = 16.0
        card_rect = QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin)

        # 1. Ambient soft drop shadow behind the card
        for i in range(1, 5):
            shadow_rect = card_rect.adjusted(-i * 2.5, -i * 2.5, i * 2.5, i * 2.5)
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(shadow_rect, 22 + i, 22 + i)
            shadow_col = QColor(0, 0, 0, int(35 / i))
            painter.fillPath(shadow_path, shadow_col)

        # 2. Main Glass Card Background
        card_path = QPainterPath()
        card_path.addRoundedRect(card_rect, 22, 22)

        bg_gradient = QLinearGradient(0, card_rect.top(), 0, card_rect.bottom())
        bg_gradient.setColorAt(0.0, QColor(22, 20, 34, 248))
        bg_gradient.setColorAt(0.5, QColor(16, 14, 24, 252))
        bg_gradient.setColorAt(1.0, QColor(10, 10, 16, 255))
        painter.fillPath(card_path, bg_gradient)

        # 3. Glowing neon border
        border_pen = QColor(139, 92, 246, 60)
        painter.setPen(border_pen)
        painter.drawPath(card_path)

    def start_animation(self):
        """Fade in and start loading."""
        self._anim_fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim_fade_in.setDuration(400)
        self._anim_fade_in.setStartValue(0.0)
        self._anim_fade_in.setEndValue(1.0)
        self._anim_fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim_fade_in.start()

        self._progress_timer.start()
        self._step_timer.start()

    def _advance_step(self):
        if self._current_step_idx < len(self._steps):
            pct, msg = self._steps[self._current_step_idx]
            self._target_progress = float(pct)
            set_text(self.status_label, msg)
            self._current_step_idx += 1
        else:
            self._step_timer.stop()

    def _on_progress_tick(self):
        # Smooth asymptotic interpolation towards target
        diff = self._target_progress - self._current_progress
        if diff > 0.1:
            self._current_progress += diff * 0.12
            self.progress_bar.setValue(int(self._current_progress))
        elif self._current_step_idx >= len(self._steps) and self._current_progress >= 99.0:
            self.progress_bar.setValue(100)
            self._progress_timer.stop()
            QTimer.singleShot(220, self.finish_and_close)

    def mousePressEvent(self, event):
        """Allows instant skip if the user clicks on the splash screen."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._step_timer.stop()
            self._progress_timer.stop()
            self.progress_bar.setValue(100)
            set_text(self.status_label, 'Uruchamianie...', 'text')
            self.finish_and_close()
        super().mousePressEvent(event)

    def finish_and_close(self):
        """Smoothly fades out the splash screen and signals finished."""
        if self._is_finishing:
            return
        self._is_finishing = True

        self._anim_fade_out = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim_fade_out.setDuration(320)
        self._anim_fade_out.setStartValue(self._opacity_effect.opacity())
        self._anim_fade_out.setEndValue(0.0)
        self._anim_fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim_fade_out.finished.connect(self._on_fade_out_finished)
        self._anim_fade_out.start()

    def _on_fade_out_finished(self):
        self.hide()
        self.finished.emit()
        self.deleteLater()
