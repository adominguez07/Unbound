import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    # When running as a PyInstaller-frozen .exe, bundled assets live under sys._MEIPASS.
    # In dev, resolve relative to the project root (one level above this file).
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).resolve().parent.parent / relative
