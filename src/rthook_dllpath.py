"""Runtime hook: add _internal directory to DLL search path."""
import os
import sys

# In onedir mode, DLLs are in _internal/ next to the exe
if hasattr(sys, '_MEIPASS'):
    dll_dir = sys._MEIPASS
else:
    dll_dir = os.path.join(os.path.dirname(sys.executable), '_internal')
    if not os.path.isdir(dll_dir):
        dll_dir = os.path.dirname(sys.executable)

os.environ['PATH'] = dll_dir + os.pathsep + os.environ.get('PATH', '')
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(dll_dir)

# Also add the PIL subdirectory where _imaging.pyd lives
pil_dir = os.path.join(dll_dir, 'PIL')
if os.path.isdir(pil_dir):
    os.environ['PATH'] = pil_dir + os.pathsep + os.environ.get('PATH', '')
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(pil_dir)