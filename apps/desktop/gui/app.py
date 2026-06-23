from __future__ import annotations
import os
import sys
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
APP_DIR: str = os.path.dirname(os.path.abspath(sys.argv[0]))
_ICON_PATH: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'SWUIFT.icns')

def run() -> None:
    from .main_window import MainWindow
    app = QApplication(sys.argv)
    app.setApplicationName('SWUIFT')
    app.setOrganizationName('SWUIFT')
    app.setOrganizationDomain('swuift.app')
    if os.path.isfile(_ICON_PATH):
        app.setWindowIcon(QIcon(_ICON_PATH))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
