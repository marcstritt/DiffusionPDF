from __future__ import annotations

import shutil
from pathlib import Path


def move_to_bin(src: Path, target_dir: Path) -> Path:
    """Déplace src dans target_dir en conservant son nom (suffixé si collision)."""
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / src.name
    if dest.exists():
        dest = _unique_path(dest)
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
