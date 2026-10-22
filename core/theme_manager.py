import json
import os
from pathlib import Path
from core.app_paths import config_dir
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor

DEFAULT_THEME = {
    "MAIN_BG_COLOR": "#10131F",
    "CENTRAL_BG_START": "#141827",
    "CENTRAL_BG_MID": "#101422",
    "CENTRAL_BG_END": "#0D111D",
    "PLAYER_BAR_BG": "#111624",
    "ACCENT_COLOR": "#9672FF",
    "LANGUAGE": "pl",
    "PREFETCH_ENABLED": True,
    "BASS_GAIN": 0,
    "TREBLE_GAIN": 0,
    "CROSSFADE_ENABLED": True,
    "CROSSFADE_DURATION": 5,
}

PRESETS = {
    "Deep Purple": DEFAULT_THEME,
    "Midnight Blue": {
        "MAIN_BG_COLOR": "#0A0C14",
        "CENTRAL_BG_START": "#0B101E",
        "CENTRAL_BG_MID": "#0E1424",
        "CENTRAL_BG_END": "#0A0C14",
        "PLAYER_BAR_BG": "rgba(10, 12, 20, 0.97)",
        "ACCENT_COLOR": "#3B82F6",
    },
    "Forest Green": {
        "MAIN_BG_COLOR": "#0A100A",
        "CENTRAL_BG_START": "#0C160C",
        "CENTRAL_BG_MID": "#0E1A0E",
        "CENTRAL_BG_END": "#0A100A",
        "PLAYER_BAR_BG": "rgba(10, 16, 10, 0.97)",
        "ACCENT_COLOR": "#10B981",
    },
    "Crimson Red": {
        "MAIN_BG_COLOR": "#140A0A",
        "CENTRAL_BG_START": "#1E0C0C",
        "CENTRAL_BG_MID": "#240E0E",
        "CENTRAL_BG_END": "#140A0A",
        "PLAYER_BAR_BG": "rgba(20, 10, 10, 0.97)",
        "ACCENT_COLOR": "#EF4444",
    }
}

class ThemeManager(QObject):
    theme_changed = pyqtSignal()
    settings_saved = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.config_dir = config_dir()
        self.config_path = self.config_dir / "theme.json"
        self.current_theme = dict(DEFAULT_THEME)
        self.load_theme()

    def load_theme(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                    self.current_theme.update(data)
            except Exception as e:
                print(f"Error loading theme: {e}")

    def save_theme(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        try:
            from core.cloud_backup import atomic_write, encode
            atomic_write(self.config_path, encode(self.current_theme))
            self.settings_saved.emit()
        except Exception as e:
            print(f"Error saving theme: {e}")

    def apply_preset(self, preset_name: str):
        if preset_name in PRESETS:
            self.current_theme.update({key: value for key, value in PRESETS[preset_name].items()
                                       if key.endswith("_COLOR") or key.startswith("CENTRAL_BG_") or key == "PLAYER_BAR_BG"})
            self.save_theme()
            self.theme_changed.emit()

    def update_color(self, key: str, hex_color: str):
        self.current_theme[key] = hex_color
        self.save_theme()
        self.theme_changed.emit()

    def get_qss(self, base_qss_path: str) -> str:
        """Loads QSS and replaces {{VARS}} with current theme colors + generated derivations."""
        try:
            with open(base_qss_path, "r", encoding="utf-8") as f:
                qss = f.read()
        except FileNotFoundError:
            return ""

        # Base replacements
        for key, value in self.current_theme.items():
            qss = qss.replace("{{" + key + "}}", str(value))

        # Derived accent colors
        accent = QColor(self.current_theme["ACCENT_COLOR"])
        
        # Hover (slightly darker, e.g. -10% lightness)
        h, s, l, a = accent.getHslF()
        hover_color = QColor.fromHslF(h, s, max(0, l - 0.1), a)
        qss = qss.replace("{{ACCENT_HOVER}}", hover_color.name())
        
        # Light / translucent variants
        qss = qss.replace("{{ACCENT_05}}", f"rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.05)")
        qss = qss.replace("{{ACCENT_14}}", f"rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.14)")
        qss = qss.replace("{{ACCENT_15}}", f"rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.15)")
        qss = qss.replace("{{ACCENT_20}}", f"rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.20)")
        qss = qss.replace("{{ACCENT_25}}", f"rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.25)")
        qss = qss.replace("{{ACCENT_30}}", f"rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.30)")
        qss = qss.replace("{{ACCENT_35}}", f"rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.35)")
        qss = qss.replace("{{ACCENT_40}}", f"rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.40)")
        qss = qss.replace("{{ACCENT_10}}", f"rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.10)")

        return qss
