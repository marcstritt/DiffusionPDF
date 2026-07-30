from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import requests
from packaging.version import InvalidVersion, Version
from PySide6.QtCore import QThread, Signal

from ..version import __version__

GITHUB_REPO = "marcstritt/DiffusionPDF"
ASSET_NAME = "DiffusionPDF-win64.exe"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
REQUEST_TIMEOUT = 10


class UpdateInfo:
    def __init__(self, version: str, download_url: str, checksum_url: Optional[str]) -> None:
        self.version = version
        self.download_url = download_url
        self.checksum_url = checksum_url


def check_for_update() -> Optional[UpdateInfo]:
    try:
        response = requests.get(API_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    remote_tag = data.get("tag_name", "")
    try:
        remote_version = Version(remote_tag.lstrip("v"))
        local_version = Version(__version__)
    except InvalidVersion:
        return None
    if remote_version <= local_version:
        return None

    assets = {asset["name"]: asset["browser_download_url"] for asset in data.get("assets", [])}
    download_url = assets.get(ASSET_NAME)
    if not download_url:
        return None
    checksum_url = assets.get(f"{ASSET_NAME}.sha256")
    return UpdateInfo(version=remote_tag, download_url=download_url, checksum_url=checksum_url)


def apply_update(info: UpdateInfo) -> bool:
    if not getattr(sys, "frozen", False):
        return False  # ne s'auto-remplace qu'une fois compilé (PyInstaller)

    current_exe = Path(sys.executable)
    tmp_dir = Path(tempfile.mkdtemp(prefix="diffusion_pdf_update_"))
    new_exe = tmp_dir / ASSET_NAME

    if not _download(info.download_url, new_exe):
        return False
    if info.checksum_url and not _verify_checksum(new_exe, info.checksum_url):
        return False

    old_exe = current_exe.with_suffix(current_exe.suffix + ".old")
    try:
        if old_exe.exists():
            old_exe.unlink()
        os.replace(current_exe, old_exe)
        shutil.move(str(new_exe), str(current_exe))
    except OSError:
        return False

    subprocess.Popen([str(current_exe)], close_fds=True)
    return True


def cleanup_old_executable() -> None:
    """À appeler au tout début de l'appli pour purger le .old laissé par une mise à jour précédente."""
    if not getattr(sys, "frozen", False):
        return
    old_exe = Path(sys.executable).with_suffix(Path(sys.executable).suffix + ".old")
    if old_exe.exists():
        try:
            old_exe.unlink()
        except OSError:
            pass


def _download(url: str, dest: Path) -> bool:
    try:
        with requests.get(url, stream=True, timeout=REQUEST_TIMEOUT) as response:
            response.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1 << 16):
                    fh.write(chunk)
        return True
    except (requests.RequestException, OSError):
        return False


def _verify_checksum(path: Path, checksum_url: str) -> bool:
    try:
        response = requests.get(checksum_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        expected = response.text.strip().split()[0].lower()
    except (requests.RequestException, IndexError):
        return False

    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest().lower() == expected


class UpdateWorker(QThread):
    """Vérifie et applique une mise à jour en arrière-plan, sans bloquer l'UI.

    En cas de succès, le nouveau process est déjà relancé : la fenêtre principale
    n'a plus qu'à se fermer (aucun fichier n'a été déplacé entre-temps, la session
    de tri reprendra simplement là où elle en était)."""

    update_applied = Signal()

    def run(self) -> None:
        info = check_for_update()
        if info is None:
            return
        if apply_update(info):
            self.update_applied.emit()
