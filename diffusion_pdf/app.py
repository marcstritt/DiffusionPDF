from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from .config import Config, ConfigError
from .shortcut import ensure_desktop_shortcut
from .ui.main_window import MainWindow
from .update.updater import cleanup_old_executable


def _icon_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "app.ico"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent / "packaging" / "assets" / "app.ico"


def main() -> int:
    cleanup_old_executable()
    ensure_desktop_shortcut()

    app = QApplication(sys.argv)
    app.setApplicationName("DiffusionPDF")
    app.setOrganizationName("Promed")
    app.setWindowIcon(QIcon(str(_icon_path())))

    try:
        config = Config.load_or_create()
    except ConfigError as exc:
        QMessageBox.information(None, "Configuration", str(exc))
        return 0

    window = MainWindow(config)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
