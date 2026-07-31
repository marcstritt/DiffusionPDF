from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QDialog, QGridLayout, QLabel, QPushButton, QWidget


class LocationsDialog(QDialog):
    """Popup (F1) listant le fichier de config et les répertoires INPUT/OUTPUT_*,
    chacun avec un bouton pour l'ouvrir dans l'explorateur de fichiers."""

    def __init__(self, entries: list[tuple[str, Path]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Emplacements")

        layout = QGridLayout(self)
        for row, (label, path) in enumerate(entries):
            layout.addWidget(QLabel(f"{label} :"), row, 0)
            layout.addWidget(QLabel(str(path)), row, 1)
            button = QPushButton("Ouvrir")
            button.clicked.connect(lambda _checked=False, p=path: self._open(p))
            layout.addWidget(button, row, 2)

    @staticmethod
    def _open(path: Path) -> None:
        directory = path.parent if path.is_file() else path
        QProcess.startDetached("explorer", [str(directory)])
