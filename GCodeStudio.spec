# -*- mode: python ; coding: utf-8 -*-
"""
Конфигурация PyInstaller для сборки G-Code Studio в EXE.

Использование:
    pyinstaller GCodeStudio.spec

Результат:
    dist/GCodeStudio.exe
"""

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# ============================================================
# Сбор всех данных matplotlib (шрифты, бэкенды)
# ============================================================
matplotlib_datas, matplotlib_binaries, matplotlib_hiddenimports = collect_all('matplotlib')
numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all('numpy')

datas = matplotlib_datas + numpy_datas
binaries = matplotlib_binaries + numpy_binaries
hiddenimports = matplotlib_hiddenimports + numpy_hiddenimports

# ============================================================
# Добавление иконки
# ============================================================
icon_path = 'app_icon.ico'
if not os.path.exists(icon_path):
    icon_path = None

# ============================================================
# Добавление модулей проекта
# ============================================================
datas.append(('gcode_studio', 'gcode_studio'))

# Дополнительные скрытые импорты
hiddenimports += [
    'numpy',
    'matplotlib',
    'matplotlib.backends.backend_tkagg',
    'matplotlib.figure',
    'matplotlib.patches',
    'matplotlib.collections',
    'tkinter',
    'tkinter.ttk',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'tkinter.scrolledtext',
    'queue',
    'threading',
    'dataclasses',
    're',
    'datetime',
    'subprocess',
]

a = Analysis(
    ['gcode_studio\\main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'wx',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'scipy',
        'pandas',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GCodeStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                    # Без консольного окна (GUI)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
    version=None,
)