from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SHORTCUT_NAME = "DiffusionPDF.lnk"


def ensure_desktop_shortcut() -> None:
    """Crée un raccourci Bureau vers l'exécutable s'il n'existe pas encore.

    Tient lieu d'installation : l'application n'a pas d'installeur (exécutable
    unique, cf. README). N'est jamais bloquant ni fatal : simple confort,
    silencieux en cas d'échec (PowerShell absent, Bureau redirigé
    inaccessible, etc.), à l'image de la vérification de mise à jour.
    """
    if not getattr(sys, "frozen", False):
        return  # n'a de sens que pour l'exécutable compilé

    exe_path = str(Path(sys.executable)).replace("'", "''")
    exe_dir = str(Path(sys.executable).parent).replace("'", "''")
    script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop '{SHORTCUT_NAME}'
if (-not (Test-Path $shortcutPath)) {{
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = '{exe_path}'
    $shortcut.WorkingDirectory = '{exe_dir}'
    $shortcut.IconLocation = '{exe_path},0'
    $shortcut.Save()
}}
"""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    except OSError:
        pass
