from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_config_dir

APP_NAME = "DiffusionPDF"
APP_AUTHOR = "Promed"

DEFAULT_SORT_DELAY_MS = 1000
DEFAULT_STABLE_CHECK_MS = 500


class ConfigError(RuntimeError):
    """Configuration absente, incomplète ou invalide."""


@dataclass
class Config:
    input_dir: Path
    output_left: Path
    output_right: Path
    output_space: Path
    sort_delay_after_last_page_ms: int = DEFAULT_SORT_DELAY_MS
    stable_file_check_ms: int = DEFAULT_STABLE_CHECK_MS

    @staticmethod
    def config_path() -> Path:
        return Path(user_config_dir(APP_NAME, APP_AUTHOR)) / "config.toml"

    @classmethod
    def load_or_create(cls) -> "Config":
        path = cls.config_path()
        if not path.exists():
            cls._write_default(path)
            raise ConfigError(
                f"Fichier de configuration créé :\n{path}\n\n"
                "Merci d'y renseigner les répertoires INPUT / OUTPUT_LEFT / "
                "OUTPUT_RIGHT / OUTPUT_SPACE puis de relancer l'application."
            )

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
                sort_delay_after_last_page_ms=int(
                    behavior.get("sort_delay_after_last_page_ms", DEFAULT_SORT_DELAY_MS)
                ),
                stable_file_check_ms=int(
                    behavior.get("stable_file_check_ms", DEFAULT_STABLE_CHECK_MS)
                ),
            )
        except KeyError as exc:
            raise ConfigError(f"Clé manquante dans {path} : {exc}") from exc

        config._ensure_directories()
        return config

    def _ensure_directories(self) -> None:
        for directory in (self.input_dir, self.output_left, self.output_right, self.output_space):
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _write_default(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        base = Path.home() / "Documents" / "DiffusionPDF"
        # Écrit en texte brut (pas via tomli_w) pour pouvoir inclure un
        # commentaire, et en slashes "/" pour éviter le piège de l'échappement
        # des antislashs Windows dans une chaîne TOML si l'utilisateur édite
        # ce fichier à la main.
        content = f'''# Fichier de configuration DiffusionPDF (par poste / utilisateur)
# Astuce : utilisez des slashes "/" dans les chemins, y compris sous
# Windows (ex. C:/Data/INPUT) — un antislash isolé n'est pas valide en TOML.

[paths]
input = "{(base / "INPUT").as_posix()}"
output_left = "{(base / "OUTPUT_LEFT").as_posix()}"
output_right = "{(base / "OUTPUT_RIGHT").as_posix()}"
output_space = "{(base / "OUTPUT_SPACE").as_posix()}"

[behavior]
sort_delay_after_last_page_ms = {DEFAULT_SORT_DELAY_MS}
stable_file_check_ms = {DEFAULT_STABLE_CHECK_MS}
'''
        path.write_text(content, encoding="utf-8")
