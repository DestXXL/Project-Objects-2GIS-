# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys


project_root = Path.cwd()
icon_path = project_root / "app" / "static" / "icons" / "app-icon.ico"
if not icon_path.exists():
    icon_path = None


a = Analysis(
    ["app/desktop.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "pandas",
        "openpyxl",
        "sqlalchemy",
        "alembic",
        "jinja2",
        "uvicorn",
        "fastapi",
        "starlette",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="WasteRegistryApp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path else None,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="WasteRegistryApp.app",
        icon=str(icon_path) if icon_path else None,
        bundle_identifier="ru.wasteregistry.desktop",
    )
else:
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="WasteRegistryApp",
    )
