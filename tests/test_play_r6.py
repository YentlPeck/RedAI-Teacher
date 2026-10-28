"""Round 6 (dev copy): the teacher's new-place note in play.py. Runs the emulator: only between arena games.

Run: ARENA_EMULATOR_TESTS=1 python -m unittest discover -s tests -p test_play_r6.py
"""
import io
import os
import json
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "arena"), str(ROOT / "tools")]
import guard  # noqa: E402
import play  # noqa: E402


@unittest.skipUnless(os.environ.get("ARENA_EMULATOR_TESTS") == "1", "emulator test: only between games")
class NewPlaceNote(unittest.TestCase):
    def run_game(self, group, presses):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        old_arena, old_key, old_argv = play.ARENA, guard.shell_key, sys.argv
        play.ARENA = Path(tmp.name)
        outs = []
        try:
            for i, argv in enumerate([["start", "g", "--group", group, "--budget", "600",
                                       "--start-state", str(play.START)]] +   # R16: power-on is the new default
                                     [["press", "g"] + p.split() for p in presses]):
                guard.shell_key = lambda i=i: f"test-{i}"          # each call = its own shell command
                if i:
                    time.sleep(1.1)
                sys.argv = ["play.py"] + argv
                buf = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")   # play.main() calls stdout.reconfigure
                with redirect_stdout(buf):
                    play.main()
                buf.flush()
                outs.append(buf.buffer.getvalue().decode("utf-8"))
        finally:
            play.ARENA, guard.shell_key, sys.argv = old_arena, old_key, old_argv
        d = Path(tmp.name) / "g"
        log = [json.loads(l) for l in open(d / "log.jsonl", encoding="utf-8")]
        notes = [json.loads(l) for l in open(d / "auto.jsonl", encoding="utf-8")] if (d / "auto.jsonl").exists() else []
        return outs, log, notes

    def test_teacher_speaks_on_a_new_map_and_logs_it(self):
        outs, log, notes = self.run_game("teacher", ["right right", "up up up up up", "right right"])
        self.assertEqual(log[-1]["map"], "REDS_HOUSE_1F")
        self.assertIn("TEACHER (new place, REDS_HOUSE_1F):", outs[-1])
        self.assertEqual([(x["n"], x["kind"]) for x in notes], [(3, "new place")])
        self.assertEqual(len(log), 4)                               # the note costs no command

    def test_plain_group_gets_no_note(self):
        outs, log, notes = self.run_game("plain", ["right right", "up up up up up", "right right"])
        self.assertEqual(log[-1]["map"], "REDS_HOUSE_1F")
        self.assertNotIn("TEACHER", "".join(outs))
        self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
