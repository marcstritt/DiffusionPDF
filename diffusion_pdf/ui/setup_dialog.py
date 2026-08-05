from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class SetupDialog(QDialog):
    """Dialogue de première ouverture : soit créer une nouvelle configuration
    (dossiers INPUT/OUTPUT_* + emplacement où enregistrer config.toml), soit
    reprendre un config.toml déjà existant ailleurs sur le disque."""

    def __init__(self, defaults: dict[str, Path], default_config_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuration de DiffusionPDF")
        self.setMinimumWidth(560)

        self._mode_new = QRadioButton("Créer une nouvelle configuration")
        self._mode_existing = QRadioButton("Utiliser un fichier de configuration existant")
        self._mode_new.setChecked(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Premier lancement : indiquez où enregistrer (ou retrouver) la "
            "configuration de DiffusionPDF."
        ))

        mode_box = QGroupBox()
        mode_layout = QVBoxLayout(mode_box)
        mode_layout.addWidget(self._mode_new)
        mode_layout.addWidget(self._mode_existing)
        layout.addWidget(mode_box)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_new_page(defaults, default_config_dir))
        self._stack.addWidget(self._build_existing_page())
        layout.addWidget(self._stack)

        self._mode_new.toggled.connect(lambda checked: checked and self._stack.setCurrentIndex(0))
        self._mode_existing.toggled.connect(lambda checked: checked and self._stack.setCurrentIndex(1))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ---- page "nouvelle configuration" ----
    def _build_new_page(self, defaults: dict[str, Path], default_config_dir: Path) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)

        grid.addWidget(QLabel("Enregistrer la configuration dans :"), 0, 0)
        self._config_dir_field = QLineEdit(str(default_config_dir))
        grid.addWidget(self._config_dir_field, 0, 1)
        browse_config_dir = QPushButton("Parcourir…")
        browse_config_dir.clicked.connect(lambda: self._browse_dir(self._config_dir_field))
        grid.addWidget(browse_config_dir, 0, 2)

        rows = [
            ("input", "Dossier INPUT (fichiers à trier)"),
            ("output_left", "Dossier OUTPUT_LEFT (touche ←)"),
            ("output_right", "Dossier OUTPUT_RIGHT (touche →)"),
            ("output_space", "Dossier OUTPUT_SPACE (touche Espace)"),
        ]
        self._dir_fields: dict[str, QLineEdit] = {}
        for offset, (key, label) in enumerate(rows, start=1):
            grid.addWidget(QLabel(f"{label} :"), offset, 0)
            field = QLineEdit(str(defaults[key]))
            self._dir_fields[key] = field
            grid.addWidget(field, offset, 1)
            browse = QPushButton("Parcourir…")
            browse.clicked.connect(lambda _checked=False, f=field: self._browse_dir(f))
            grid.addWidget(browse, offset, 2)

        return page

    # ---- page "configuration existante" ----
    def _build_existing_page(self) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)
        grid.addWidget(QLabel("Fichier config.toml existant :"), 0, 0)
        self._existing_file_field = QLineEdit()
        grid.addWidget(self._existing_file_field, 0, 1)
        browse = QPushButton("Parcourir…")
        browse.clicked.connect(self._browse_existing_file)
        grid.addWidget(browse, 0, 2)
        return page

    def _browse_dir(self, field: QLineEdit) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choisir un dossier", field.text())
        if directory:
            field.setText(directory)

    def _browse_existing_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir un fichier de configuration", self._existing_file_field.text(),
            "Fichier de configuration (config.toml);;Tous les fichiers (*)",
        )
        if path:
            self._existing_file_field.setText(path)

    def _on_accept(self) -> None:
        if self._mode_new.isChecked():
            if not self._config_dir_field.text().strip() or any(
                not field.text().strip() for field in self._dir_fields.values()
            ):
                QMessageBox.warning(self, "Configuration", "Merci de renseigner tous les champs.")
                return
        else:
            if not self._existing_file_field.text().strip():
                QMessageBox.warning(self, "Configuration", "Merci de choisir un fichier de configuration.")
                return
            if not Path(self._existing_file_field.text()).is_file():
                QMessageBox.warning(self, "Configuration", "Le fichier choisi n'existe pas.")
                return
        self.accept()

    # ---- résultat ----
    def use_existing(self) -> bool:
        return self._mode_existing.isChecked()

    def config_directory(self) -> Path:
        return Path(self._config_dir_field.text())

    def directories(self) -> dict[str, Path]:
        return {key: Path(field.text()) for key, field in self._dir_fields.items()}

    def existing_config_path(self) -> Path:
        return Path(self._existing_file_field.text())
