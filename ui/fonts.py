"""Registers the bundled Inter typeface so the UI looks the same on every system."""
from pathlib import Path

from PyQt6.QtGui import QFontDatabase

FONTS_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'fonts'


def load_bundled_fonts(directory=FONTS_DIR):
    """Adds every bundled .ttf to the application; returns the family names registered."""
    families = set()
    for path in sorted(Path(directory).glob('*.ttf')):
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            print(f'Could not load font: {path.name}')
            continue
        families.update(QFontDatabase.applicationFontFamilies(font_id))
    return families
