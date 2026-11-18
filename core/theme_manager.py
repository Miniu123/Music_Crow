import json
import re
from pathlib import Path
from functools import lru_cache
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

SUCCESS_COLOR = "#4ADE80"
DANGER_COLOR = "#F4657E"
ACCENT_ALPHAS = (5, 10, 14, 15, 20, 25, 30, 35, 40)
_RGBA = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)")
_active_manager = None


def parse_color(value, fallback="#10131F") -> QColor:
    """Parses #hex and rgb()/rgba() strings, which QColor alone cannot read."""
    text = str(value or "").strip()
    match = _RGBA.fullmatch(text)
    if match:
        red, green, blue = (max(0, min(255, int(part))) for part in match.groups()[:3])
        alpha = float(match.group(4)) if match.group(4) is not None else 1.0
        color = QColor(red, green, blue)
        color.setAlphaF(max(0.0, min(1.0, alpha)))
        return color
    color = QColor(text)
    return color if color.isValid() else QColor(fallback)


def _tone(accent: QColor, lightness: float, saturation_scale: float = 1.0) -> str:
    hue, saturation, _, _ = accent.getHslF()
    hue = max(0.0, hue)  # achromatic colours report -1
    return QColor.fromHslF(hue, min(1.0, saturation * saturation_scale), lightness).name()


def derive_palette(accent_value) -> dict:
    """Every accent-dependent colour used by the stylesheet and custom painting."""
    return dict(_derive_palette(str(accent_value or "")))


@lru_cache(maxsize=16)
def _derive_palette(accent_value: str) -> dict:
    accent = parse_color(accent_value, DEFAULT_THEME["ACCENT_COLOR"])
    hue, saturation, lightness, _ = accent.getHslF()
    palette = {
        "ACCENT_COLOR": accent.name(),
        "ACCENT_HOVER": QColor.fromHslF(max(0.0, hue), saturation, max(0.0, lightness - 0.1)).name(),
        "ACCENT_LIGHT": _tone(accent, 0.82),
        "ACCENT_PALE": _tone(accent, 0.92),
        "ACCENT_MUTED": _tone(accent, 0.72, 0.3),
        "SUCCESS_COLOR": SUCCESS_COLOR,
        "DANGER_COLOR": DANGER_COLOR,
    }
    rgb = f"{accent.red()}, {accent.green()}, {accent.blue()}"
    for alpha in ACCENT_ALPHAS:
        palette[f"ACCENT_{alpha:02d}"] = f"rgba({rgb}, {alpha / 100:.2f})"
    return palette


def active_theme_manager():
    return _active_manager


def active_palette() -> dict:
    """The palette of the running app's theme, for widgets that paint themselves."""
    manager = _active_manager
    accent = manager.current_theme.get("ACCENT_COLOR") if manager else DEFAULT_THEME["ACCENT_COLOR"]
    return derive_palette(accent)


def active_accent() -> QColor:
    manager = _active_manager
    value = manager.current_theme.get("ACCENT_COLOR") if manager else DEFAULT_THEME["ACCENT_COLOR"]
    return parse_color(value, DEFAULT_THEME["ACCENT_COLOR"])


def with_alpha(color: QColor, alpha: int) -> QColor:
    result = QColor(color)
    result.setAlpha(max(0, min(255, int(alpha))))
    return result


def connect_theme_changed(slot):
    """Connects a widget refresh to theme changes when an app theme exists."""
    if _active_manager is not None:
        _active_manager.theme_changed.connect(slot)


class ThemeManager(QObject):
    theme_changed = pyqtSignal()      # Colours changed: restyle the interface
    settings_changed = pyqtSignal()   # Audio/playback preferences changed
    settings_saved = pyqtSignal()

    def __init__(self):
        global _active_manager
        super().__init__()
        self.config_dir = config_dir()
        self.config_path = self.config_dir / "theme.json"
        self.current_theme = dict(DEFAULT_THEME)
        self.load_theme()
        _active_manager = self

    def load_theme(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
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

    def set_setting(self, key: str, value):
        """Stores a non-visual preference without restyling the whole interface."""
        if self.current_theme.get(key) == value:
            return
        self.current_theme[key] = value
        self.save_theme()
        self.settings_changed.emit()

    def palette(self) -> dict:
        return derive_palette(self.current_theme.get("ACCENT_COLOR"))

    def get_qss(self, base_qss_path: str) -> str:
        """Loads QSS and replaces {{VARS}} with current theme colors + generated derivations."""
        try:
            with open(base_qss_path, "r", encoding="utf-8") as f:
                qss = f.read()
        except FileNotFoundError:
            return ""

        values = {key: value for key, value in self.current_theme.items() if isinstance(value, str)}
        values.update(self.palette())
        values["ASSET_DIR"] = str(Path(base_qss_path).resolve().parent).replace("\\", "/")
        return re.sub(r"\{\{([A-Z0-9_]+)\}\}", lambda match: str(values.get(match.group(1), match.group(0))), qss)
