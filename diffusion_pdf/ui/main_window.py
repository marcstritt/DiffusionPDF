from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QByteArray, QEvent, QSettings, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

from ..config import Config
from ..core.cache import Preloader
from ..core.distributor import move_to_bin
from ..core.queue_manager import QueueManager
from ..version import __version__
from .locations_dialog import LocationsDialog
from .pdf_view import PdfView


def _is_locked(path: Path) -> bool:
    """Le fichier est-il ouvert en exclusivité par un autre programme ?
    QPdfDocument ne distingue pas ce cas d'un fichier absent (FileNotFound),
    mais sous Windows une simple ouverture en lecture échoue alors avec
    PermissionError."""
    try:
        with path.open("rb") as fh:
            fh.read(1)
    except PermissionError:
        return True
    except OSError:
        return False
    return False


class MainWindow(QMainWindow):
    # Ratio largeur/hauteur d'une page A4 portrait (595 x 842 pt) : seul
    # format affiché par l'application, sert de taille de fenêtre au tout
    # premier lancement (ensuite la géométrie choisie par l'utilisateur est
    # reprise telle quelle).
    _A4_ASPECT_RATIO = 595 / 842

    # Documents chargés en arrière-plan en avance du document affiché : borné
    # volontairement (pas tout le dossier INPUT, qui peut contenir des
    # centaines de fichiers) pour limiter la mémoire consommée par les
    # QPdfDocument ouverts simultanément.
    _PRELOAD_AHEAD = 2

    # PDF verrouillé par un autre programme (en cours d'écriture, ouvert
    # ailleurs...) : nombre total de tentatives de lecture et délai entre
    # deux tentatives, avant abandon et passage au document suivant.
    _LOCKED_READ_ATTEMPTS = 3
    _LOCKED_READ_RETRY_MS = 10_000

    def __init__(self, config: Config) -> None:
        super().__init__()
        self._config = config
        self._current_path: Optional[Path] = None
        self._current_document: Optional[QPdfDocument] = None
        self._preload_paths: list[Path] = []

        self._load_attempts = 0
        self._load_retry_timer = QTimer(self)
        self._load_retry_timer.setSingleShot(True)
        self._load_retry_timer.timeout.connect(self._retry_load)

        # Bloque ←/→ pendant config.arrow_lock_seconds après l'affichage de
        # chaque document (Espace reste immédiat) : laisse le temps de voir
        # la page avant de pouvoir la trier par erreur.
        self._arrows_locked = False
        self._arrow_lock_timer = QTimer(self)
        self._arrow_lock_timer.setSingleShot(True)
        self._arrow_lock_timer.timeout.connect(self._unlock_arrows)

        self._set_title("Diffusion PDF")

        self._pdf_view = PdfView(self)
        self.setCentralWidget(self._pdf_view)
        self._pdf_view.left_pressed.connect(self._on_left)
        self._pdf_view.right_pressed.connect(self._on_right)
        self._pdf_view.space_pressed.connect(self._on_space)
        self._pdf_view.help_requested.connect(self._show_locations_dialog)

        self._queue = QueueManager(
            config.input_dir,
            poll_interval_ms=config.stable_file_check_ms,
            batch_size=config.batch_size,
            parent=self,
        )
        self._queue.queue_changed.connect(self._on_queue_changed)
        self._queue.queue_changed.connect(self._refresh_title)

        self._preloader = Preloader(self)

        self._init_geometry()

        # Fermeture automatique après inactivité de l'utilisateur.
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(QApplication.quit)
        # Même délai quand INPUT est vide : annulé dès qu'un document apparaît.
        self._empty_timer = QTimer(self)
        self._empty_timer.setSingleShot(True)
        self._empty_timer.timeout.connect(QApplication.quit)
        if config.idle_timeout_seconds > 0:
            QApplication.instance().installEventFilter(self)
            self._reset_idle_timer()

        self._queue.start()
        self._advance()

    # ---- popup d'emplacements (F1) ----
    def _show_locations_dialog(self) -> None:
        entries = [
            ("Configuration", Config.resolve_path() or Config.config_path()),
            ("INPUT", self._config.input_dir),
            ("OUTPUT_LEFT", self._config.output_left),
            ("OUTPUT_RIGHT", self._config.output_right),
            ("OUTPUT_SPACE", self._config.output_space),
        ]
        LocationsDialog(entries, self).exec()

    # ---- fenêtre ----
    _SETTINGS_GEOMETRY_KEY = "window/geometry"

    def _init_geometry(self) -> None:
        # Géométrie choisie par l'utilisateur lors de la session précédente
        # (QSettings = profil de l'utilisateur Windows) ; à défaut, au tout
        # premier lancement, pleine hauteur d'écran en format A4.
        saved = QSettings().value(self._SETTINGS_GEOMETRY_KEY)
        if isinstance(saved, QByteArray) and self.restoreGeometry(saved):
            return
        screen = QGuiApplication.primaryScreen().availableGeometry()
        width = round(screen.height() * self._A4_ASPECT_RATIO)
        self.setGeometry(screen.x(), screen.y(), width, screen.height())

    def closeEvent(self, event) -> None:
        QSettings().setValue(self._SETTINGS_GEOMETRY_KEY, self.saveGeometry())
        super().closeEvent(event)

    # ---- inactivité ----
    _ACTIVITY_EVENTS = {
        QEvent.Type.KeyPress,
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseMove,
        QEvent.Type.Wheel,
    }

    def eventFilter(self, watched, event) -> bool:
        if event.type() in self._ACTIVITY_EVENTS:
            self._reset_idle_timer()
        return False

    def _reset_idle_timer(self) -> None:
        self._idle_timer.start(round(self._config.idle_timeout_seconds * 1000))

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
        else:
            self._fill_preload_queue()

    def _exclude_set(self) -> set[Path]:
        exclude: set[Path] = set()
        if self._current_path is not None:
            exclude.add(self._current_path)
        exclude.update(self._preload_paths)
        return exclude

    def _fill_preload_queue(self) -> None:
        while len(self._preload_paths) < self._PRELOAD_AHEAD:
            candidate = self._queue.next_candidate(self._exclude_set())
            if candidate is None:
                return
            self._preload_paths.append(candidate)
            self._preloader.preload(candidate)

    def _advance(self) -> None:
        self._current_path = None
        self._load_retry_timer.stop()

        if self._preload_paths:
            path = self._preload_paths.pop(0)
            doc = self._preloader.take(path)
        else:
            path = self._queue.next_candidate(self._exclude_set())
            doc = None

        if path is None:
            # Lot précédent entièrement traité : on ne regarde les nouveaux
            # fichiers qu'à ce moment-là.
            self._queue.refill_batch()
            path = self._queue.next_candidate(self._exclude_set())

        if path is None:
            self._pdf_view.set_document(None)
            if self._queue.has_pending():
                self._set_title("Diffusion PDF — en attente de documents")
            else:
                # Plus aucun PDF dans INPUT : rien à trier, fermeture après le
                # même délai que l'inactivité (0 = jamais).
                self._set_title("Diffusion PDF — INPUT vide")
                if self._config.idle_timeout_seconds > 0 and not self._empty_timer.isActive():
                    self._empty_timer.start(round(self._config.idle_timeout_seconds * 1000))
            return

        self._empty_timer.stop()

        self._show(path, doc)

    def _show(self, path: Path, doc: Optional[QPdfDocument]) -> None:
        self._current_path = path
        self._load_attempts = 1
        self._set_title(path.name)
        self._lock_arrows()
        self._load_current(doc)
        self._fill_preload_queue()

    def _load_current(self, doc: Optional[QPdfDocument]) -> None:
        """Affiche le document courant (préchargé ou non), ou lance son chargement."""
        path = self._current_path
        doc = doc or QPdfDocument(self)
        self._current_document = doc
        status = doc.status()
        if status == QPdfDocument.Status.Ready:
            self._pdf_view.set_document(doc)
        elif status == QPdfDocument.Status.Error:
            # Document préchargé déjà en échec : aucun signal ne viendra plus.
            QTimer.singleShot(0, lambda d=doc, p=path: self._on_load_failed(p, d))
        else:
            doc.statusChanged.connect(
                lambda status, d=doc, p=path: self._on_document_status(p, d, status)
            )
            if status == QPdfDocument.Status.Null:
                doc.load(str(path))

    def _on_document_status(self, path: Path, doc: QPdfDocument, status) -> None:
        if path != self._current_path or doc is not self._current_document:
            return
        if status == QPdfDocument.Status.Ready:
            self._pdf_view.set_document(doc)
        elif status == QPdfDocument.Status.Error:
            # L'erreur peut être émise de façon synchrone, depuis doc.load() :
            # traitée une fois load() terminé, pour ne pas détruire le document
            # ni ouvrir une boîte de dialogue (boucle d'événements imbriquée)
            # pendant qu'il est encore en cours d'exécution.
            QTimer.singleShot(0, lambda: self._on_load_failed(path, doc))

    def _on_load_failed(self, path: Path, doc: QPdfDocument) -> None:
        if path != self._current_path or doc is not self._current_document:
            return
        self._current_document = None
        doc.close()
        doc.deleteLater()

        if not path.exists():
            # Retiré de INPUT entre-temps (par un autre poste ou programme).
            self._queue.discard(path)
            self._advance()
            return

        locked = _is_locked(path)
        if locked and self._load_attempts < self._LOCKED_READ_ATTEMPTS:
            delay_s = self._LOCKED_READ_RETRY_MS // 1000
            self._set_title(
                f"{path.name} — verrouillé par un autre programme, nouvelle tentative "
                f"({self._load_attempts + 1}/{self._LOCKED_READ_ATTEMPTS}) dans {delay_s} s"
            )
            self._load_retry_timer.start(self._LOCKED_READ_RETRY_MS)
            return

        self._queue.skip(path)
        if locked:
            title = "Document verrouillé"
            text = (
                f"{path.name} est verrouillé par un autre programme "
                f"({self._LOCKED_READ_ATTEMPTS} tentatives de lecture) : "
                "le fichier est ignoré et reste dans INPUT."
            )
        else:
            title = "Document illisible"
            text = f"Impossible d'ouvrir {path.name} : le fichier est ignoré et reste dans INPUT."
        QMessageBox.warning(self, title, text)
        self._advance()

    def _retry_load(self) -> None:
        if self._current_path is None:
            return
        self._load_attempts += 1
        self._set_title(self._current_path.name)
        self._load_current(None)

    def _release_current_document(self) -> None:
        """Ferme le document affiché pour libérer le verrou fichier Windows avant déplacement."""
        self._pdf_view.set_document(None)
        if self._current_document is not None:
            self._current_document.close()
            self._current_document.deleteLater()
            self._current_document = None

    # ---- verrou temporaire ←/→ ----
    def _lock_arrows(self) -> None:
        self._arrows_locked = True
        self._arrow_lock_timer.start(max(0, round(self._config.arrow_lock_seconds * 1000)))

    def _unlock_arrows(self) -> None:
        self._arrows_locked = False

    # ---- distribution ----
    def _on_left(self) -> None:
        if self._arrows_locked:
            return
        self._dispatch(self._config.output_left)

    def _on_right(self) -> None:
        if self._arrows_locked:
            return
        self._dispatch(self._config.output_right)

    def _on_space(self) -> None:
        self._dispatch(self._config.output_space)

    _MOVE_RETRY_MS = 100
    _MOVE_RETRY_MAX = 10

    def _dispatch(self, target_dir: Path) -> None:
        path = self._current_path
        if path is None or self._load_retry_timer.isActive():
            return  # rien d'affiché (ex. en attente d'un fichier verrouillé)
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
