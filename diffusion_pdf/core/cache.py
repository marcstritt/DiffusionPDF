from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject
from PySide6.QtPdf import QPdfDocument


class Preloader(QObject):
    """Charge en arrière-plan le document PDF suivant pour un affichage instantané."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._pending: dict[Path, QPdfDocument] = {}

    def preload(self, path: Path) -> None:
        if path in self._pending:
            return
        document = QPdfDocument(self)
        self._pending[path] = document
        document.load(str(path))

    def take(self, path: Path) -> Optional[QPdfDocument]:
        return self._pending.pop(path, None)

    def discard(self, path: Path) -> None:
        document = self._pending.pop(path, None)
        if document is not None:
            document.deleteLater()
