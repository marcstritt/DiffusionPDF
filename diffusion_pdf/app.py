from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from .config import Config, ConfigError
from .ui.main_window import MainWindow
from .update.updater import cleanup_old_executable


def main() -> int:
    cleanup_old_executable()

    app = QApplication(sys.argv)
    app.setApplicationName("DiffusionPDF")
    app.setOrganizationName("Promed")

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
