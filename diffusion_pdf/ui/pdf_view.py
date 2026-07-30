from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPrintSupport import QPrintDialog, QPrinter


class PdfView(QPdfView):
    """QPdfView en mode lecture : ajustement automatique à la hauteur,
    zoom Ctrl +/-/0, impression Ctrl+P, et signaux bruts pour les touches
    de distribution (←/→/Espace) — la logique d'activation reste côté
    fenêtre principale."""

    left_pressed = Signal()
    right_pressed = Signal()
    space_pressed = Signal()

    _ZOOM_STEP = 1.15
    _ZOOM_MIN = 0.2
    _ZOOM_MAX = 8.0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setPageMode(QPdfView.PageMode.MultiPage)
        self.setZoomMode(QPdfView.ZoomMode.Custom)
        self._base_zoom = 1.0
        self._zoom_multiplier = 1.0

    def set_document(self, document: Optional[QPdfDocument]) -> None:
        self._zoom_multiplier = 1.0
        self.setDocument(document)
        self._update_fit_zoom()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_fit_zoom()

    def _update_fit_zoom(self) -> None:
        document = self.document()
        if document is None or document.status() != QPdfDocument.Status.Ready:
            return
        page_count = document.pageCount()
        if page_count == 0:
            return
        page = min(max(self.pageNavigator().currentPage(), 0), page_count - 1)
        page_size = document.pagePointSize(page)
        if page_size.height() <= 0:
            return

        available_height = max(self.viewport().height() - 2 * self.pageSpacing(), 1)
        self._base_zoom = available_height / page_size.height()
        self.setZoomFactor(self._base_zoom * self._zoom_multiplier)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)

        if ctrl:
            if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self._zoom_multiplier = min(self._zoom_multiplier * self._ZOOM_STEP, self._ZOOM_MAX)
                self.setZoomFactor(self._base_zoom * self._zoom_multiplier)
                return
            if key == Qt.Key.Key_Minus:
                self._zoom_multiplier = max(self._zoom_multiplier / self._ZOOM_STEP, self._ZOOM_MIN)
                self.setZoomFactor(self._base_zoom * self._zoom_multiplier)
                return
            if key == Qt.Key.Key_0:
                self._zoom_multiplier = 1.0
                self.setZoomFactor(self._base_zoom)
                return
            if key == Qt.Key.Key_P:
                self._print()
                return

        if mods == Qt.KeyboardModifier.NoModifier:
            if key == Qt.Key.Key_Left:
                self.left_pressed.emit()
                return
            if key == Qt.Key.Key_Right:
                self.right_pressed.emit()
                return
            if key == Qt.Key.Key_Space:
                self.space_pressed.emit()
                return

        super().keyPressEvent(event)

    def _print(self) -> None:
        document = self.document()
        if document is None or document.status() != QPdfDocument.Status.Ready:
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return

        painter = QPainter(printer)
        dpi = printer.resolution()
        for page in range(document.pageCount()):
            if page > 0:
                printer.newPage()
            page_size_pt = document.pagePointSize(page)
            image_size = QSize(
                max(int(page_size_pt.width() / 72 * dpi), 1),
                max(int(page_size_pt.height() / 72 * dpi), 1),
            )
            image = document.render(page, image_size)
            painter.drawImage(QRect(0, 0, image.width(), image.height()), image)
        painter.end()
