# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Electron backend sidecar."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT_DIR = Path.cwd().resolve()


_tiktoken_data = collect_data_files("tiktoken")


def tree_datas(root: Path, dest: str, exclude_parts=(), exclude_names=(), exclude_suffixes=()):
    root_path = Path(root)
    rows = []
    if not root_path.exists():
        return rows
    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root_path)
        parts = set(rel.parts)
        if (
            path.name == ".DS_Store"
            or path.name in exclude_names
            or any(path.name.endswith(suffix) for suffix in exclude_suffixes)
            or any(part in parts for part in exclude_parts)
        ):
            continue
        rows.append((str(path), str(Path(dest) / rel.parent)))
    return rows


hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("fastapi")
    + collect_submodules("anyio")
    + collect_submodules("starlette")
    + [
        "ming_sim",
        "agno.agent",
        "agno.db.sqlite",
        "agno.models.openai",
        "agno.skills",
        "agno.skills.loaders.local",
        "openai",
        "tiktoken",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
    ]
)

datas = (
    _tiktoken_data
    + tree_datas(
        ROOT_DIR / "web" / "dist",
        "web/dist",
        exclude_parts={"_backup_rgb", "_original_before_cutout", "steam-stock"},
        exclude_names={
            "hud-preview.html",
            "ming-ui-editor.html",
            "ming-ui-mockup.html",
            "ming-ui-preview.html",
            "ui-reference-11236.jpg",
            "最新ui.jpg",
        },
        exclude_suffixes=(".original.png", ".wm.png"),
    )
    + [
        (str(ROOT_DIR / "content"), "content"),
    ]
    + tree_datas(ROOT_DIR / ".agno_skills", ".agno_skills")
)

binaries = []

block_cipher = None

a = Analysis(
    ["server_backend.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "matplotlib",
        "pandas",
        "numpy.tests",
        "webview",
        "tkinter",
        "playwright",
        "sounddevice",
        "openpyxl",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MingSalvageBackend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MingSalvageBackend",
)
