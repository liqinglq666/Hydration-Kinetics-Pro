from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from gui.main_window_safe import MainWindow
from utils.logger import logger


def get_asset_path(filename: str) -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS) / "assets"
    else:
        base_path = Path(__file__).resolve().parent / "assets"
    return str(base_path / filename)


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        app.setWindowIcon(QIcon(get_asset_path("lq.ico")))
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as exc:
        logger.critical("Application crashed: %s", exc, exc_info=True)
