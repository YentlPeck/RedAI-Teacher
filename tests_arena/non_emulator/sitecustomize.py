"""No PyBoy imports; skip the live guard's unmarked emulator smoke before it starts.

Used through PYTHONPATH with the unchanged unittest discover command. This also
prevents that smoke from copying start.state to a temporary game directory.
"""
import importlib.abc
import sys
import unittest

class NoEmulator(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0].lower() == 'pyboy':
            raise RuntimeError('No emulators authorized: PyBoy import blocked')

sys.meta_path.insert(0, NoEmulator())
sys.dont_write_bytecode = True
original_load = unittest.TestLoader.loadTestsFromTestCase

def load_non_emulator(self, cls):
    if cls.__module__ == 'test_guard' and cls.__name__ == 'Guard':
        name = 'test_play_refuses_a_batch_before_it_changes_the_game'
        setattr(cls, name, unittest.skip('emulator smoke: no games authorized')(getattr(cls, name)))
    return original_load(self, cls)

unittest.TestLoader.loadTestsFromTestCase = load_non_emulator

# R15: inherited fixture cleanup must move files, never delete them.
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import r15_preserve
