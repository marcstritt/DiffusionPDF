from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from platformdirs import user_config_dir

APP_NAME = "DiffusionPDF"
APP_AUTHOR = "Promed"

DEFAULT_STABLE_CHECK_MS = 500

# Durée (en secondes) pendant laquelle ←/→ sont ignorées après l'affichage
# d'un nouveau document, pour éviter un tri accidentel avant d'avoir vu la
# page. Espace n'est jamais concerné : il reste immédiat.
DEFAULT_ARROW_LOCK_SECONDS = 2.0

# Nom du fichier "pointeur" écrit à l'emplacement standard quand l'utilisateur
# choisit d'enregistrer config.toml ailleurs (autre dossier, clé USB, partage
# réseau...) au premier lancement — contient simplement le chemin réel du
# config.toml à utiliser, pour que l'app le retrouve aux lancements suivants
# sans redemander où il se trouve.
_LOCATOR_FILENAME = "config_location.txt"


class ConfigError(RuntimeError):
    """Configuration absente, incomplète ou invalide."""


@dataclass
class Config:
    input_dir: Path
    output_left: Path
    output_right: Path
    output_space: Path
    stable_file_check_ms: int = DEFAULT_STABLE_CHECK_MS
    arrow_lock_seconds: float = DEFAULT_ARROW_LOCK_SECONDS

    @staticmethod
    def config_path() -> Path:
        """Emplacement standard (utilisé par défaut, et pour y chercher le
        fichier pointeur si config.toml a été enregistré ailleurs)."""
        return Path(user_config_dir(APP_NAME, APP_AUTHOR)) / "config.toml"

    @staticmethod
    def _locator_path() -> Path:
        return Path(user_config_dir(APP_NAME, APP_AUTHOR)) / _LOCATOR_FILENAME

    @classmethod
    def resolve_path(cls) -> Optional[Path]:
        """Emplacement réel de config.toml : à l'emplacement standard s'il y
        est, sinon via le fichier pointeur si l'utilisateur a choisi un autre
        dossier au premier lancement. None si aucune configuration n'existe
        encore."""
        standard = cls.config_path()
        if standard.exists():
            return standard
        locator = cls._locator_path()
        if locator.exists():
            pointed = Path(locator.read_text(encoding="utf-8").strip())
            if pointed.exists():
                return pointed
        return None

    @classmethod
    def exists(cls) -> bool:
        return cls.resolve_path() is not None

    @staticmethod
    def default_directories() -> dict[str, Path]:
        """Répertoires suggérés pour pré-remplir le dialogue de première ouverture."""
        base = Path.home() / "Documents" / "DiffusionPDF"
        return {
            "input": base / "INPUT",
            "output_left": base / "OUTPUT_LEFT",
            "output_right": base / "OUTPUT_RIGHT",
            "output_space": base / "OUTPUT_SPACE",
        }

    @classmethod
    def _write_locator_if_needed(cls, path: Path) -> None:
        """Enregistre le fichier pointeur si config.toml n'est pas à
        l'emplacement standard, pour que l'app le retrouve au prochain
        lancement sans redemander où il se trouve."""
        standard = cls.config_path()
        if path != standard:
            standard.parent.mkdir(parents=True, exist_ok=True)
            cls._locator_path().write_text(str(path), encoding="utf-8")

    @classmethod
    def create(
        cls,
        config_dir: Path,
        input_dir: Path,
        output_left: Path,
        output_right: Path,
        output_space: Path,
    ) -> "Config":
        """Écrit un nouveau fichier de configuration dans config_dir (choix
        fait via le dialogue de première ouverture) et renvoie la Config
        prête à l'emploi."""
        config_dir.mkdir(parents=True, exist_ok=True)
        path = config_dir / "config.toml"
        # Écrit en texte brut (pas via tomli_w) pour pouvoir inclure un
        # commentaire, et en slashes "/" pour éviter le piège de l'échappement
        # des antislashs Windows dans une chaîne TOML si l'utilisateur édite
        # ce fichier à la main par la suite.
        content = f'''# Fichier de configuration DiffusionPDF (par poste / utilisateur)
# Astuce : utilisez des slashes "/" dans les chemins, y compris sous
# Windows (ex. C:/Data/INPUT) — un antislash isolé n'est pas valide en TOML.

[paths]
input = "{input_dir.as_posix()}"
output_left = "{output_left.as_posix()}"
output_right = "{output_right.as_posix()}"
output_space = "{output_space.as_posix()}"

[behavior]
stable_file_check_ms = {DEFAULT_STABLE_CHECK_MS}
arrow_lock_seconds = {DEFAULT_ARROW_LOCK_SECONDS}
'''
        path.write_text(content, encoding="utf-8")
        cls._write_locator_if_needed(path)

        config = cls(
            input_dir=input_dir,
            output_left=output_left,
            output_right=output_right,
            output_space=output_space,
        )
        config._ensure_directories()
        return config

    @classmethod
    def adopt_existing(cls, path: Path) -> "Config":
        """Utilise un config.toml déjà présent ailleurs sur le disque, choisi
        via le dialogue de première ouverture : l'analyse pour valider son
        contenu, puis note son emplacement pour le retrouver ensuite."""
        config = cls._parse(path)
        cls._write_locator_if_needed(path)
        return config

    @classmethod
    def load(cls) -> "Config":
        path = cls.resolve_path()
        if path is None:
            raise ConfigError(f"Fichier de configuration introuvable :\n{cls.config_path()}")
        return cls._parse(path)

    @classmethod
    def _parse(cls, path: Path) -> "Config":
        with path.open("rb") as fh:
            try:
                data = tomllib.load(fh)
            except tomllib.TOMLDecodeError as exc:
                raise ConfigError(
                    f"Fichier de configuration invalide :\n{path}\n\n{exc}\n\n"
                    "Astuce : dans les chemins, utilisez des slashes \"/\" "
                    "(ex. C:/Data/INPUT) plutôt que des antislashs Windows, "
                    "qui doivent sinon être doublés pour être valides en TOML."
                ) from exc

        paths = data.get("paths", {})
        behavior = data.get("behavior", {})
        try:
            config = cls(
                input_dir=Path(paths["input"]),
                output_left=Path(paths["output_left"]),
                output_right=Path(paths["output_right"]),
                output_space=Path(paths["output_space"]),
                stable_file_check_ms=int(
                    behavior.get("stable_file_check_ms", DEFAULT_STABLE_CHECK_MS)
                ),
                arrow_lock_seconds=float(
                    behavior.get("arrow_lock_seconds", DEFAULT_ARROW_LOCK_SECONDS)
                ),
            )
        except KeyError as exc:
            raise ConfigError(f"Clé manquante dans {path} : {exc}") from exc

        config._ensure_directories()
        return config

    def _ensure_directories(self) -> None:
        for directory in (self.input_dir, self.output_left, self.output_right, self.output_space):
            directory.mkdir(parents=True, exist_ok=True)
