from __future__ import annotations

import errno
import shutil
from pathlib import Path


def move_to_bin(src: Path, target_dir: Path) -> Path:
    """Déplace src dans target_dir en conservant son nom (suffixé si collision)."""
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / src.name
    if dest.exists():
        dest = _unique_path(dest)
    try:
        src.rename(dest)
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            # Verrou fichier (cas courant, cf. _move_with_retry côté appelant) ou
            # autre échec : rien n'a été déplacé, on laisse l'exception remonter
            # telle quelle pour un nouvel essai propre. Ne PAS utiliser
            # shutil.move ici : sur un échec de verrou, son repli copie+suppression
            # peut laisser une copie complète à dest avant que la suppression de
            # src n'échoue à son tour, dupliquant le fichier à chaque nouvelle
            # tentative (observé en production : fichiers "xxx.PDF" +
            # "xxx (1).PDF" identiques dans OUTPUT_LEFT/OUTPUT_RIGHT).
            raise
        # src et dest sur des volumes différents : rename() ne peut pas
        # fonctionner, repli sur copie+suppression (rare avec la config actuelle,
        # tout sous un même lecteur).
        shutil.move(str(src), str(dest))
    return dest


def _unique_path(dest: Path) -> Path:
    stem, suffix = dest.stem, dest.suffix
    counter = 1
    candidate = dest
    while candidate.exists():
        candidate = dest.with_name(f"{stem} ({counter}){suffix}")
        counter += 1
    return candidate
