import sys
import os
import locale
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from ui.main_window import MainWindow
from ui.splash_screen import SplashScreen
from core.theme_manager import ThemeManager
from core.i18n import language_manager, tr


def main():
    app = QApplication(sys.argv)

    # mpv requires LC_NUMERIC="C" but QApplication changes it, so we revert it
    locale.setlocale(locale.LC_NUMERIC, 'C')

    # Set app icon
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Load QSS stylesheet via ThemeManager (replaces {{VARIABLES}} with actual colors)
    qss_path = os.path.join(os.path.dirname(__file__), "assets", "style.qss")
    theme_manager = ThemeManager()
    language_manager.configure(theme_manager)
    qss = theme_manager.get_qss(qss_path)
    app.setStyleSheet(qss)

    # Re-apply stylesheet whenever theme changes
    def _on_theme_changed():
        app.setStyleSheet(theme_manager.get_qss(qss_path))
    theme_manager.theme_changed.connect(_on_theme_changed)

    # Show animated splash screen on startup
    splash = SplashScreen(icon_path=icon_path, accent=theme_manager.current_theme['ACCENT_COLOR'])
    window = None

    def reveal_window():
        if window is not None:
            window.fade_in(320)

    def initialize_window():
        nonlocal window
        try:
            # Widgets must be built on the GUI thread, after the splash's first frames.
            window = MainWindow(theme_manager=theme_manager)
        except Exception:
            import traceback
            traceback.print_exc()
            splash.close()
            QMessageBox.critical(None, 'Music Crow', tr('Nie udało się uruchomić aplikacji. Szczegóły znajdziesz w terminalu.'))
            app.exit(1)
            return
        splash.mark_ready()

    splash.transition_started.connect(reveal_window)
    splash.show()
    splash.start_animation()
    QTimer.singleShot(300, initialize_window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
