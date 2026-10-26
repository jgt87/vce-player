# PyInstaller desktop build. Research binaries and user exam files are excluded.
from pathlib import Path
root = Path(SPECPATH)
a = Analysis([str(root / 'player.py')], pathex=[str(root)], binaries=[],
             datas=[(str(root / 'examples' / 'network-basics.json'), 'examples')],
             hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['pytest', 'IPython', 'matplotlib', 'numpy', 'scipy'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='StudyPlayer',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
