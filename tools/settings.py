"""Where the teacher finds its files. Every path has a default and can be changed with an environment variable.

    REDAI_ROM          your own legal Pokémon Red ROM          (default: red.gb in the repo root, never committed)
    REDAI_REFERENCE    folder with pokered/ and pokered.sym    (default: reference/ in the repo root)
    REDAI_RUNS         one folder per game                     (default: ~/redai-runs)
    REDAI_PLAYER_CWD   empty folder the AI player CLI runs in  (default: ~/redai-player-cwd)
    REDAI_CLAUDE       path of the claude CLI                  (default: found on PATH)
    REDAI_CODEX        path of the codex CLI                   (default: found on PATH)
    REDAI_FIXTURES     test-only game memory dumps             (default: fixtures/ in the repo root, not shipped)
    REDAI_TRASH        tests move temporary folders here       (default: .trash/ in the repo root)
"""
import os
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _path(name, default):
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


ROM = _path("REDAI_ROM", REPO / "red.gb")
ROM_RAM = ROM.with_name(ROM.name + ".ram")          # a battery save PyBoy could write next to the ROM: refused
REFERENCE = _path("REDAI_REFERENCE", REPO / "reference")
POKERED = REFERENCE / "pokered"
KB = REPO / "kb"
RUNS = _path("REDAI_RUNS", Path.home() / "redai-runs")
PLAYER_CWD = _path("REDAI_PLAYER_CWD", Path.home() / "redai-player-cwd")
START_STATE = _path("REDAI_START_STATE", REPO / "states" / "start.state")   # only for --start-state tests
FIXTURES = _path("REDAI_FIXTURES", REPO / "fixtures")
TRASH = _path("REDAI_TRASH", REPO / ".trash")


def _cli(env, name):
    value = os.environ.get(env) or shutil.which(name)
    if not value:
        raise FileNotFoundError(f"{name} CLI not found: put it on PATH or set {env}")
    return Path(value)


def claude_cli():
    return _cli("REDAI_CLAUDE", "claude")


def codex_cli():
    return _cli("REDAI_CODEX", "codex")


def fixture(rel):
    """Tests only: a file in REDAI_FIXTURES. Skips the test when it is missing (game memory dumps are not shipped)."""
    path = FIXTURES / rel
    if not path.exists():
        import unittest
        raise unittest.SkipTest(f"needs test fixture {rel} (made from our own game runs, not in the repo; README, Tests)")
    return path


class FixtureDir:
    """Tests only: FixtureDir("bench") / "title.wram" is fixture("bench/title.wram")."""

    def __init__(self, rel):
        self.rel = rel

    def __truediv__(self, name):
        return fixture(f"{self.rel}/{name}")

    def glob(self, pattern):
        return fixture(self.rel).glob(pattern)


def need_reference():
    """A clear message when the pokered files are missing (the teacher reads them at import)."""
    if not (REFERENCE / "pokered.sym").is_file() or not POKERED.is_dir():
        raise FileNotFoundError(
            f"pokered reference not found in {REFERENCE}: see README (Setup), or set REDAI_REFERENCE")
