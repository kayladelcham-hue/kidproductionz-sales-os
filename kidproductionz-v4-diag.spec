from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


PROJECT_ROOT = Path(SPECPATH).resolve()
FRONTEND_DIST = PROJECT_ROOT / "app" / "frontend" / "dist"
ASSETS = PROJECT_ROOT / "assets"

# Keep the browser application and runtime modules inside the unpacked bundle.
datas = [
    (str(FRONTEND_DIST), "app/frontend/dist"),
    (str(ASSETS), "assets"),
]

hiddenimports = []
for package in ("app.api", "src"):
    try:
        hiddenimports.extend(collect_submodules(package))
    except Exception:
        # The explicit API entry point remains discoverable even when an
        # optional V5 module is not importable in a packaging environment.
        pass

hiddenimports.extend([
    "app.api.main",
    "app.api.database",
    "app.api.google_service",
    "app.api.hubspot_client",
    "app.api.hubspot_service",
    "app.api.hubspot_sync_service",
])


a = Analysis(
    [str(PROJECT_ROOT / "desktop_launcher.py")],
    pathex=[str(PROJECT_ROOT), str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=sorted(set(hiddenimports)),
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
    exclude_binaries=True,
    name="KidProductionz Sales OS V4 Diagnostic",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="KidProductionz Sales OS V4 Diagnostic",
)

