from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal


class QueueManager(QObject):
    """File des PDF de INPUT prêts à être affichés.

    Un fichier est "prêt" quand sa taille est restée identique entre deux
    scans successifs (évite d'ouvrir un PDF encore en cours d'écriture).
    """

    queue_changed = Signal()

    def __init__(self, input_dir: Path, poll_interval_ms: int = 500, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._input_dir = input_dir
        self._last_sizes: dict[str, int] = {}
        self._ready: dict[str, Path] = {}

        self._timer = QTimer(self)
        self._timer.setInterval(poll_interval_ms)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        self._poll()
        self._timer.start()

    def _poll(self) -> None:
        try:
            entries = sorted(
                p for p in self._input_dir.iterdir()
                if p.is_file() and p.suffix.lower() == ".pdf"
            )
        except OSError:
            return

        current_sizes: dict[str, int] = {}
        newly_ready = False
        for path in entries:
            name = path.name
            try:
                size = path.stat().st_size
            except OSError:
                continue
            current_sizes[name] = size
            if name not in self._ready and self._last_sizes.get(name) == size:
                self._ready[name] = path
                newly_ready = True
        self._last_sizes = current_sizes

        for name in list(self._ready):
            if name not in current_sizes:
                del self._ready[name]

        if newly_ready:
            self.queue_changed.emit()

    def next_candidate(self, exclude: set[Path]) -> Optional[Path]:
        for path in self._ready.values():
            if path not in exclude:
                return path
        return None

    def discard(self, path: Path) -> None:
        self._ready.pop(path.name, None)
        self._last_sizes.pop(path.name, None)
