from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal


def _creation_time(path: Path) -> float:
    """Date de création du fichier (st_ctime = création sous Windows ; sur les
    autres systèmes st_birthtime si disponible, sinon date de modification)."""
    st = path.stat()
    if sys.platform == "win32":
        return st.st_ctime
    return getattr(st, "st_birthtime", st.st_mtime)


class QueueManager(QObject):
    """Lot de PDF de INPUT à afficher, dans l'ordre chronologique de création.

    Un fichier est "prêt" quand sa taille est restée identique entre deux
    scans successifs (évite d'ouvrir un PDF encore en cours d'écriture).

    Les documents sont traités par lots : tant que le lot courant n'est pas
    entièrement traité, les nouveaux fichiers arrivés dans INPUT sont ignorés ;
    ils ne sont pris en compte que par le lot suivant (`refill_batch`).
    """

    queue_changed = Signal()

    def __init__(
        self,
        input_dir: Path,
        poll_interval_ms: int = 500,
        batch_size: int = 0,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._input_dir = input_dir
        self._batch_size = batch_size  # 0 = pas de limite
        self._last_sizes: dict[str, int] = {}
        self._ready: dict[str, tuple[float, Path]] = {}  # nom -> (date création, chemin)
        self._batch: list[Path] = []
        self._skipped: set[str] = set()

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
                if p.is_file() and p.suffix.lower() == ".pdf" and p.name not in self._skipped
            )
        except OSError:
            return

        current_sizes: dict[str, int] = {}
        newly_ready = False
        for path in entries:
            name = path.name
            try:
                size = path.stat().st_size
                created = _creation_time(path)
            except OSError:
                continue
            current_sizes[name] = size
            if name not in self._ready and self._last_sizes.get(name) == size:
                self._ready[name] = (created, path)
                newly_ready = True
        self._last_sizes = current_sizes

        for name in list(self._ready):
            if name not in current_sizes:
                del self._ready[name]

        if newly_ready:
            self.queue_changed.emit()

    def has_pending(self) -> bool:
        """Reste-t-il un PDF (non écarté) dans INPUT, prêt ou en cours d'écriture ?"""
        try:
            return any(
                p.is_file() and p.suffix.lower() == ".pdf" and p.name not in self._skipped
                for p in self._input_dir.iterdir()
            )
        except OSError:
            return True  # dossier momentanément illisible : ne pas conclure qu'il est vide

    def refill_batch(self) -> None:
        """Constitue le lot suivant (les plus anciens fichiers prêts) si le
        lot courant est entièrement traité. Sans effet sinon."""
        if self._batch:
            return
        ordered = sorted(self._ready.values(), key=lambda item: (item[0], item[1].name))
        paths = [path for _, path in ordered]
        self._batch = paths[: self._batch_size] if self._batch_size > 0 else paths

    def next_candidate(self, exclude: set[Path]) -> Optional[Path]:
        for path in self._batch:
            if path not in exclude:
                return path
        return None

    def discard(self, path: Path) -> None:
        """Retire un document traité (déplacé) du lot."""
        self._forget(path)

    def skip(self, path: Path) -> None:
        """Écarte définitivement un document illisible (reste dans INPUT)."""
        self._skipped.add(path.name)
        self._forget(path)

    def _forget(self, path: Path) -> None:
        self._ready.pop(path.name, None)
        self._last_sizes.pop(path.name, None)
        if path in self._batch:
            self._batch.remove(path)
