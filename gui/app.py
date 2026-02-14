"""启动 GUI 应用。"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from .main_window import MainWindow


def run_app() -> None:
    Path(__file__).resolve().parent.parent
    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
