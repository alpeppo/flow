"""PyInstaller-Hook fuer mlx_whisper.

Bundelt assets/mel_filters.npz und tiktoken-Vocab-Files, die als
Resource-Dateien in der Library liegen und ohne Hook nicht im Bundle landen.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("mlx_whisper", include_py_files=False)
hiddenimports = collect_submodules("mlx_whisper")
