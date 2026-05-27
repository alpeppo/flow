"""PyInstaller-Hook fuer mlx (Metal-shaders).

mlx hat .metallib-Dateien die NICHT als Python-Imports erfasst werden.
collect_data_files reicht nicht — wir brauchen rglob fuer .metallib
plus collect_dynamic_libs fuer dylibs.
"""

import pathlib

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

# Standard-Approach
datas = collect_data_files("mlx", include_py_files=False)
binaries = collect_dynamic_libs("mlx")
# mlx ist ein Namespace-Package — Submodules wie mlx._reprlib_fix muessen
# explizit als hidden imports deklariert werden, sonst wirft mlx_whisper
# beim Bundle-Start ModuleNotFoundError.
hiddenimports = collect_submodules("mlx")

# Metal-shaders sind .metallib — finde alle und bundle sie
# mlx ist ein Namespace-Package: __file__ ist None, __path__ enthaelt die Pfade.
try:
    import mlx

    for mlx_path_str in list(mlx.__path__):
        mlx_dir = pathlib.Path(mlx_path_str)
        for metallib in mlx_dir.rglob("*.metallib"):
            rel_dir = str(metallib.relative_to(mlx_dir).parent)
            binaries.append(
                (str(metallib), f"mlx/{rel_dir}" if rel_dir != "." else "mlx")
            )
except ImportError:
    # mlx nicht installiert — kein Fehler in Hook
    pass
