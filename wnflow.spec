# -*- mode: python ; coding: utf-8 -*-
# PyInstaller-Spec für worknetic-flow
#
# Build: pyinstaller wnflow.spec --noconfirm
#
# Erzeugt: dist/worknetic-flow.app (Menubar-Only, mit Squircle-Icon im Dock
# beim Start, dann LSUIElement=True → versteckt im Dock).
#
# Lessons (POCs 0-2):
# - multiprocessing.freeze_support() in __main__.py (sonst Fork-Loop)
# - mlx ist Namespace-Package (eigener Hook)
# - .metallib-Shader manuell rglob'en (sonst kein Metal-Backend)
# - NSWindow-Sub-Fenster: temporaer ActivationPolicy=Regular (in code)

import os

import tomllib
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

# SPEC is PyInstaller-injected: path to this .spec file
_pyproject = Path(SPEC).parent / "pyproject.toml"
WNFLOW_VERSION = tomllib.loads(_pyproject.read_text())["project"]["version"]

# Bundle the package's dist-info so importlib.metadata.version("worknetic-flow")
# works at runtime (otherwise __version__ falls back to "0.0.0+unknown").
_metadata = copy_metadata("worknetic-flow")

a = Analysis(
    ['src/wnflow/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        # Brand-Assets fürs Menubar-Icon und ggf. App-internes Logo
        ('brand/wnflow_icon_22.png', 'brand'),
        ('brand/wnflow_icon_16.png', 'brand'),
        ('brand/wnflow_icon_64.png', 'brand'),
        # Hauptfenster-HTML
        ('src/wnflow/web/index.html', 'wnflow/web'),
    ] + _metadata,
    hiddenimports=[
        # Sichergehen, dass alle wnflow-Submodule da sind
        'wnflow.app',
        'wnflow.audio_ducker',
        'wnflow.config',
        'wnflow.history_store',
        'wnflow.hotkey',
        'wnflow.fn_keymap',
        'wnflow.login_item',
        'wnflow.main_window',
        'wnflow.menubar',
        'wnflow.mic',
        'wnflow.notify',
        'wnflow.output',
        'wnflow.permissions',
        'wnflow.pill',
        'wnflow.pipeline',
        'wnflow.settings_data',
        'wnflow.state',
        'wnflow.threading_guard',
        'wnflow.stt',
        'wnflow.cleanup',
        # PyObjC-Frameworks
        'WebKit',
    ],
    hookspath=['dev/hooks'],
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
    [],
    exclude_binaries=True,
    name='Flow',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # upx kann mit .metallib/.dylib brechen
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',  # Apple Silicon only (mlx braucht Metal)
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Flow',
)

app = BUNDLE(
    coll,
    name='Flow.app',
    icon='brand/wnflow.icns',
    bundle_identifier='de.worknetic.flow',
    version=WNFLOW_VERSION,
    info_plist={
        'CFBundleName': 'Flow',
        'CFBundleDisplayName': 'Flow.',
        'CFBundleShortVersionString': WNFLOW_VERSION,
        'CFBundleVersion': WNFLOW_VERSION,
        'CFBundleIdentifier': 'de.worknetic.flow',
        'CFBundleExecutable': 'Flow',
        'CFBundleIconFile': 'wnflow.icns',
        'NSHighResolutionCapable': True,
        # Normale App: Dock-Icon + Menubar-Icon. Tim will sie wie eine
        # normale App im Programme-Ordner / Dock haben.
        # (LSUIElement=True wuerde sie zu Menubar-only machen — nicht gewollt.)
        'LSUIElement': False,
        'LSMinimumSystemVersion': '13.0',  # SMAppService braucht macOS 13+
        # Permissions: Mic + Accessibility + Apple Events (osascript-Notify)
        'NSMicrophoneUsageDescription':
            'worknetic-flow nutzt das Mikrofon für Push-to-Talk-Diktat.',
        'NSAppleEventsUsageDescription':
            'worknetic-flow zeigt System-Notifications über osascript.',
        # Keine Berechtigung im Plist, aber wichtig: Accessibility wird
        # via TCC-Prompt beim ersten Hotkey-Listener-Start angefragt.
    },
)
