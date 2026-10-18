import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import MagicMock, patch

from PyQt6 import sip
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QWidget

from ui.splash_screen import SplashScreen

app = QApplication.instance() or QApplication([])


class StartupAnimationTests(unittest.TestCase):
    def setUp(self):
        self.splash = SplashScreen()
        self.splash.show()
        self.splash.start_animation()
        self.splash._timer.stop()
        self.now = 0
        self.splash._clock = MagicMock()
        self.splash._clock.elapsed.side_effect = lambda: self.now
        self.splash._clock.isValid.return_value = True
        self.reveals = []
        self.finishes = []
        self.splash.transition_started.connect(lambda: self.reveals.append(self.now))
        self.splash.finished.connect(lambda: self.finishes.append(self.now))

    def tearDown(self):
        if not sip.isdeleted(self.splash):
            self.splash.close()
            self.splash.deleteLater()
        app.processEvents()

    def advance(self, milliseconds):
        self.now = milliseconds
        self.splash._tick()

    def test_slow_initialization_never_finishes_on_a_fake_deadline(self):
        self.advance(20000)
        self.assertEqual(self.reveals, [])
        self.assertTrue(self.splash.isVisible())
        self.splash.mark_ready()
        self.advance(20279)
        self.assertEqual(self.reveals, [])
        self.advance(20280)
        self.assertEqual(self.reveals, [20280])

    def test_early_click_waits_for_main_window_and_only_reveals_once(self):
        QTest.mouseClick(self.splash, Qt.MouseButton.LeftButton)
        self.advance(100)
        self.assertEqual(self.reveals, [])
        self.splash.mark_ready()
        self.splash.mark_ready()
        self.splash.finish_and_close()
        self.assertEqual(self.reveals, [100])
        self.advance(360)
        self.advance(1000)
        self.assertEqual(self.finishes, [360])
        self.assertFalse(self.splash._timer.isActive())
        self.assertFalse(self.splash.isVisible())

    def test_main_window_is_revealed_before_splash_disappears(self):
        window = QWidget()
        self.addCleanup(window.close)
        self.splash.transition_started.connect(window.show)
        self.advance(300)
        self.splash.mark_ready()
        self.advance(949)
        self.assertFalse(window.isVisible())
        self.advance(950)
        self.assertTrue(window.isVisible())
        self.assertTrue(self.splash.isVisible())
        self.advance(1210)
        self.assertFalse(self.splash.isVisible())
        self.assertTrue(window.isVisible())

    def test_hiding_stops_frame_timer(self):
        self.splash._timer.start()
        self.splash.hide()
        self.assertFalse(self.splash._timer.isActive())

    def test_main_window_fade_starts_transparent_before_show(self):
        from ui.main_window import MainWindow
        window = QWidget()
        window.central_widget = QWidget(window)
        observations = []
        with patch.object(window, 'show', side_effect=lambda: observations.append(window.central_widget.graphicsEffect().opacity())):
            MainWindow.fade_in(window, 30)
        self.assertEqual(observations, [0.0])
        QTest.qWait(80)
        self.assertIsNone(window.central_widget.graphicsEffect())
        window.close()
        window.deleteLater()


if __name__ == '__main__':
    unittest.main()
