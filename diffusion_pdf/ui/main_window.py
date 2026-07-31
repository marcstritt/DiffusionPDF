from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

from ..config import Config
from ..core.cache import Preloader
from ..core.distributor import move_to_bin
from ..core.queue_manager import QueueManager
from ..update.updater import UpdateWorker
from ..version import __version__
from .locations_dialog import LocationsDialog
from .pdf_view import PdfView


class MainWindow(QMainWindow):
    # Ratio largeur/hauteur d'une page A4 portrait (595 x 842 pt) : seul
    # format affiché par l'application, sert de largeur de fenêtre initiale
    # avant le chargement du premier document.
    _A4_ASPECT_RATIO = 595 / 842

    def __init__(self, config: Config) -> None:
        super().__init__()
        self._config = config
        self._current_path: Optional[Path] = None
        self._current_document: Optional[QPdfDocument] = None
        self._next_path: Optional[Path] = None
        self._broken_paths: set[Path] = set()

        self._set_title("Diffusion PDF")

        self._pdf_view = PdfView(self)
        self.setCentralWidget(self._pdf_view)
        self._pdf_view.left_pressed.connect(self._on_left)
        self._pdf_view.right_pressed.connect(self._on_right)
        self._pdf_view.space_pressed.connect(self._on_space)
        self._pdf_view.help_requested.connect(self._show_locations_dialog)

        self._queue = QueueManager(config.input_dir, poll_interval_ms=config.stable_file_check_ms, parent=self)
        self._queue.queue_changed.connect(self._on_queue_changed)
        self._queue.queue_changed.connect(self._refresh_title)

        self._preloader = Preloader(self)

        self._init_geometry()

        self._update_worker = UpdateWorker(self)
        self._update_worker.update_applied.connect(QApplication.quit)
        self._update_worker.start()

        self._queue.start()
        self._advance()

    # ---- popup d'emplacements (F1) ----
    def _show_locations_dialog(self) -> None:
        entries = [
            ("Configuration", Config.config_path()),
            ("INPUT", self._config.input_dir),
            ("OUTPUT_LEFT", self._config.output_left),
            ("OUTPUT_RIGHT", self._config.output_right),
            ("OUTPUT_SPACE", self._config.output_space),
        ]
        LocationsDialog(entries, self).exec()

    # ---- fenêtre ----
    def _init_geometry(self) -> None:
        # Toujours pleine hauteur d'écran : seul format affiché (A4) sert de
        # largeur de départ, affinée par document via _fit_window_to_page.
        screen = QGuiApplication.primaryScreen().availableGeometry()
        width = round(screen.height() * self._A4_ASPECT_RATIO)
        self.setGeometry(screen.x(), screen.y(), width, screen.height())

    def _set_title(self, text: str) -> None:
        self._title_text = text
        self._refresh_title()

    def _refresh_title(self) -> None:
        self.setWindowTitle(f"v{__version__} [{self._pending_count()}] {self._title_text}")

    def _pending_count(self) -> int:
        try:
            return sum(
                1 for p in self._config.input_dir.iterdir()
                if p.is_file() and p.suffix.lower() == ".pdf"
            )
        except OSError:
            return 0

    # ---- file d'attente ----
    def _on_queue_changed(self) -> None:
        if self._current_path is None:
            self._advance()
        elif self._next_path is None:
            self._preload_next()

    def _exclude_set(self) -> set[Path]:
        exclude = set(self._broken_paths)
        if self._current_path is not None:
            exclude.add(self._current_path)
        if self._next_path is not None:
            exclude.add(self._next_path)
        return exclude

    def _preload_next(self) -> None:
        candidate = self._queue.next_candidate(self._exclude_set())
        if candidate is not None:
            self._next_path = candidate
            self._preloader.preload(candidate)

    def _advance(self) -> None:
        self._current_path = None

        if self._next_path is not None:
            path = self._next_path
            doc = self._preloader.take(self._next_path)
            self._next_path = None
        else:
            path = self._queue.next_candidate(self._exclude_set())
            doc = None

        if path is None:
            self._pdf_view.set_document(None)
            self._set_title("Diffusion PDF — en attente de documents")
            return

        self._show(path, doc)

    def _show(self, path: Path, doc: Optional[QPdfDocument]) -> None:
        self._current_path = path
        self._current_document = doc
        self._set_title(path.name)

        if doc is not None and doc.status() == QPdfDocument.Status.Ready:
            self._pdf_view.set_document(doc)
            self._on_document_ready()
        else:
            doc = doc or QPdfDocument(self)
            self._current_document = doc
            doc.statusChanged.connect(
                lambda status, d=doc, p=path: self._on_document_status(p, d, status)
            )
            if doc.status() == QPdfDocument.Status.Null:
                doc.load(str(path))

        self._preload_next()

    def _on_document_status(self, path: Path, doc: QPdfDocument, status) -> None:
        if path != self._current_path or doc is not self._current_document:
            return
        if status == QPdfDocument.Status.Ready:
            self._pdf_view.set_document(doc)
            self._on_document_ready()
        elif status == QPdfDocument.Status.Error:
            self._broken_paths.add(path)
            self._current_document = None
            doc.deleteLater()
            QMessageBox.warning(
                self,
                "Document illisible",
                f"Impossible d'ouvrir {path.name} : le fichier est ignoré et reste dans INPUT.",
            )
            self._advance()

    def _release_current_document(self) -> None:
        """Ferme le document affiché pour libérer le verrou fichier Windows avant déplacement."""
        self._pdf_view.set_document(None)
        if self._current_document is not None:
            self._current_document.close()
            self._current_document.deleteLater()
            self._current_document = None

    def _on_document_ready(self) -> None:
        self._fit_window_to_page()

    # ---- largeur de fenêtre adaptée à la page (hauteur toujours pleine) ----
    def _fit_window_to_page(self) -> None:
        ideal_width = self._pdf_view.ideal_content_width()
        if ideal_width is None:
            return
        chrome = self.width() - self._pdf_view.viewport().width()
        target_width = ideal_width + chrome
        screen = QGuiApplication.primaryScreen().availableGeometry()
        target_width = max(1, min(target_width, screen.width()))
        self.resize(target_width, self.height())

    # ---- distribution ----
    def _on_left(self) -> None:
        self._dispatch(self._config.output_left)

    def _on_right(self) -> None:
        self._dispatch(self._config.output_right)

    def _on_space(self) -> None:
        self._dispatch(self._config.output_space)

    _MOVE_RETRY_MS = 100
    _MOVE_RETRY_MAX = 10

    def _dispatch(self, target_dir: Path) -> None:
        path = self._current_path
        if path is None:
            return
        self._queue.discard(path)
        self._release_current_document()
        self._move_with_retry(path, target_dir, attempt=0)

    def _move_with_retry(self, path: Path, target_dir: Path, attempt: int) -> None:
        try:
            move_to_bin(path, target_dir)
        except OSError:
            # Sur Windows, la fermeture du QPdfDocument peut libérer le verrou du
            # fichier avec un léger retard (état intermédiaire "Unloading").
            if attempt < self._MOVE_RETRY_MAX:
                QTimer.singleShot(
                    self._MOVE_RETRY_MS,
                    lambda: self._move_with_retry(path, target_dir, attempt + 1),
                )
                return
            QMessageBox.warning(
                self, "Erreur de déplacement",
                f"{path.name} : fichier verrouillé, déplacement impossible."
            )
            return
        self._advance()
