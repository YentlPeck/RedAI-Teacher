"""Non-emulator boundary, including the live Windows guard smoke test."""
import importlib.abc
import sys
import unittest
class NoEmulator(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0].lower() == 'pyboy':
            raise unittest.SkipTest('emulator disabled: non-emulator suite only')
sys.meta_path.insert(0, NoEmulator())
sys.dont_write_bytecode = True

# R15: inherited fixture cleanup must move files, never delete them.
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import r15_preserve
