"""Run using the finished Flatpak Platform runtime, not the build SDK."""
import json
import locale
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import wave

# Test fixtures never use the user's real library or Google session.
root = Path(tempfile.mkdtemp(prefix='music-crow-smoke-'))
os.environ['XDG_CONFIG_HOME'] = str(root / 'config')
os.environ['XDG_CACHE_HOME'] = str(root / 'cache')
from PyQt6.QtWidgets import QApplication, QPlainTextEdit
from PyQt6.QtCore import QTimer, QTranslator, QLibraryInfo
from PyQt6.QtGui import QImage
from core.app_paths import config_dir, cache_dir
from core.google_oauth_config import bundled_client
from core.gdrive_sync import validate_client
from core.cloud_backup import collect_snapshot
from core.theme_manager import ThemeManager
from ui.main_window import MainWindow
from ui.license_dialog import LicenseDialog
import mpv
import dbus
from gi.repository import GLib
import google_auth_oauthlib
import yt_dlp

app = QApplication([])
translator = QTranslator()
assert translator.load('qtbase_pl', QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
locale.setlocale(locale.LC_NUMERIC, 'C')
assert config_dir().is_relative_to(root)
assert cache_dir().is_relative_to(root)
assert validate_client(bundled_client())
assert subprocess.run(['deno', '--version'], capture_output=True).returncode == 0
assert subprocess.run([sys.executable, '-m', 'yt_dlp', '--version'], capture_output=True).returncode == 0
source = root / 'silence.wav'
with wave.open(str(source), 'wb') as stream:
    stream.setnchannels(2)
    stream.setsampwidth(2)
    stream.setframerate(44100)
    stream.writeframes(b'\0' * 44100 * 4)
engine = mpv.MPV(video=False, ao='null', config=False, idle=True)
try:
    engine.play(str(source))
    deadline = time.monotonic() + 5
    while engine.time_pos is None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert engine.time_pos is not None, 'MPV did not start decoding test audio'
finally:
    engine.terminate()
theme = ThemeManager()
app.setStyleSheet(theme.get_qss('/app/share/music-crow/assets/style.qss'))
window = MainWindow(theme_manager=theme)
window.resize(1200, 800)
window.show()
errors = []
def verify():
    try:
        theme.save_theme()
        assert (config_dir() / 'theme.json').exists()
        snapshot = collect_snapshot(config_dir())
        assert snapshot['settings']
        assert window.sync_manager.has_client_configuration()
        licenses = LicenseDialog(window)
        license_texts = '\n'.join(view.toPlainText() for view in licenses.findChildren(QPlainTextEdit))
        assert 'MIT License' in license_texts
        assert 'Copyright (c) 2026 Miniu123' in license_texts
        assert 'GPL-3.0-only' in license_texts
        licenses.close()
        assert window.grab().save(sys.argv[1])
        print(json.dumps({'startup': 'ok', 'qt_window': 'ok', 'mpv_decode': 'ok',
                          'xdg_storage': 'ok', 'backup_preparation': 'ok',
                          'oauth_client': 'configured', 'deno': 'ok', 'yt_dlp': 'ok',
                          'mpris_modules': 'ok', 'offline_licenses': 'ok',
                          'qt_polish_translation': 'ok'}), flush=True)
    except Exception as error:
        errors.append(type(error).__name__ + ': ' + str(error))
    finally:
        window.close()
        app.quit()
QTimer.singleShot(1800, verify)
app.exec()
if errors:
    raise RuntimeError('; '.join(errors))
