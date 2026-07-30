# -*- mode: python ; coding: utf-8 -*-
# Build : pyinstaller packaging/diffusion_pdf.spec --noconfirm
# (fonctionne quel que soit le répertoire courant : les chemins sont
# résolus depuis SPECPATH, injecté par PyInstaller = dossier packaging/)

import os

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    [os.path.join(SPECPATH, "entrypoint.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DiffusionPDF-win64',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    # icon='assets/app.ico',
)
