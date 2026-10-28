"""Checks for arena/guard.py: batched play.py calls are refused and do not count (round 5 on).

Run: python -m unittest discover -s tests -v
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "arena"))
import guard as G  # noqa: E402


class Guard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, key, start, end=None):
        G.check(self.run_dir, now=start, key=key)
        G.release(self.run_dir, key=key, now=start + 0.6 if end is None else end)

    def test_separate_commands_pass(self):
        self.call("shell-1", 100)
        self.call("shell-2", 103)
        self.call("shell-3", 106)
        self.assertFalse((self.run_dir / "blocked.jsonl").exists())

    def test_two_calls_in_one_shell_command_are_refused(self):
        self.call("shell-1", 100)
        with self.assertRaises(G.Blocked) as e:
            self.call("shell-1", 105)            # waiting between calls does not help
        self.assertIn("several play.py calls in one shell command", str(e.exception))
        self.assertIn("did not count", str(e.exception))
        self.assertTrue(G._take_lock(self.run_dir / "busy.lock"))           # the refused call left the lock free
        G._drop_lock(self.run_dir / "busy.lock")

    def test_fast_calls_are_refused(self):
        self.call("shell-1", 100, end=100.6)
        with self.assertRaises(G.Blocked) as e:
            self.call("shell-2", 101.0)          # 0.4 s after the previous one ended
        self.assertIn("less than 1 second", str(e.exception))
        with self.assertRaises(G.Blocked):
            self.call("shell-3", 101.7)          # 1.1 s after the last command, but 0.7 s after the refusal
        self.call("shell-4", 102.8)              # 1.1 s after the last refusal: fine

    def test_a_fast_loop_gets_nothing_through(self):
        self.call("shell-1", 100, end=100.6)
        for i in range(10):                     # new shell each time, 0.5 s apart: refusals restart the cooldown
            with self.assertRaises(G.Blocked):
                self.call(f"loop-{i}", 101.1 + 0.5 * i)
        self.call("shell-2", 101.1 + 0.5 * 9 + 1.1)

    def test_refusal_message_is_the_same_for_both_groups_and_neutral(self):
        self.call("shell-1", 100)
        with self.assertRaises(G.Blocked) as e:
            self.call("shell-1", 105)
        msg = str(e.exception).lower()
        for word in ("teacher", "ask", "pokémon", "route", "oak", "walk", "press"):
            self.assertNotIn(word, msg)

    def test_parallel_calls_are_refused(self):
        G.check(self.run_dir, now=100, key="shell-1")        # still running
        with self.assertRaises(G.Blocked) as e:
            G.check(self.run_dir, now=100.2, key="shell-2")
        self.assertIn("still running", str(e.exception))
        G.release(self.run_dir, key="shell-1", now=100.6)
        self.call("shell-3", 102)

    def holder(self, seconds):
        """A separate process that takes the game's lock (like a running command) and holds it."""
        code = ("import sys, time, pathlib; sys.path.insert(0, sys.argv[1]); import guard\n"
                "assert guard._take_lock(pathlib.Path(sys.argv[2]) / 'busy.lock'); print('held', flush=True)\n"
                "time.sleep(float(sys.argv[3]))")
        child = subprocess.Popen([sys.executable, "-c", code, str(ROOT / "arena"), str(self.run_dir),
                                  str(seconds)], stdout=subprocess.PIPE, text=True)
        self.assertEqual(child.stdout.readline().strip(), "held")
        return child

    def test_lock_held_by_another_process_refuses_and_is_freed_when_it_dies(self):
        child = self.holder(30)
        try:
            with self.assertRaises(G.Blocked) as e:
                G.check(self.run_dir, now=100, key="shell-1")
            self.assertIn("still running", str(e.exception))
            G.release(self.run_dir, key="shell-1", now=101)        # not the holder: writes nothing
            self.assertFalse((self.run_dir / "last_call.json").exists())
        finally:
            child.kill()                                           # a crashed command
            child.wait()
        self.call("shell-2", 102)                                  # the OS freed its lock: no stale lock

    def test_racing_callers_never_both_get_the_lock(self):
        """Sol GD2: two callers after a dead holder could both enter. Now the OS lock lets exactly one in."""
        dead = self.holder(0.1)
        dead.wait()
        code = ("import sys, time, pathlib; sys.path.insert(0, sys.argv[1]); import guard\n"
                "ok = guard._take_lock(pathlib.Path(sys.argv[2]) / 'busy.lock'); print(int(ok), flush=True)\n"
                "time.sleep(1.5)")
        for _ in range(3):
            kids = [subprocess.Popen([sys.executable, "-c", code, str(ROOT / "arena"), str(self.run_dir)],
                                     stdout=subprocess.PIPE, text=True) for _ in range(4)]
            got = [int(k.stdout.readline()) for k in kids]
            for k in kids:
                k.wait()
            self.assertEqual(sum(got), 1, got)

    def test_metadata_is_never_read_half_written(self):
        last = self.run_dir / "last_call.json"
        G._write(last, {"key": "k", "end": 1})
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import guard, pathlib; p = pathlib.Path(sys.argv[2])\n"
                "for i in range(300): guard._write(p, {'key': 'k' * (i % 50), 'end': i})")
        w = subprocess.Popen([sys.executable, "-c", code, str(ROOT / "arena"), str(last)])
        try:
            while w.poll() is None:
                self.assertIn("end", G._read(last))
        finally:
            w.wait()

    def test_refusals_are_logged_for_the_audit(self):
        self.call("shell-1", 100)
        for t in (105, 110):
            with self.assertRaises(G.Blocked):
                self.call("shell-1", t)
        self.assertEqual(len((self.run_dir / "blocked.jsonl").read_text(encoding="utf-8").splitlines()), 2)

    def test_outer_shell_walks_up_through_shells_only(self):
        procs = {1: (0, "t3 code.exe"), 2: (1, "codex.exe"),
                 10: (2, "powershell.exe"), 11: (10, "python.exe"), 12: (11, "python.exe"),     # command A
                 20: (2, "powershell.exe"), 21: (20, "python.exe"), 22: (21, "python.exe"),     # command B
                 30: (2, "bash.exe"), 31: (30, "bash.exe"), 32: (31, "python.exe"), 33: (31, "python.exe")}
        self.assertEqual(G.outer_shell(procs, 12), 10)
        self.assertEqual(G.outer_shell(procs, 22), 20)            # separate commands: different keys
        self.assertEqual(G.outer_shell(procs, 32), G.outer_shell(procs, 33))    # a loop in one bash: same key

    @unittest.skipUnless(os.name == "nt", "process tree check is Windows-only")
    @unittest.skipUnless(os.environ.get("ARENA_EMULATOR_TESTS") == "1", "emulator test: only between games")
    def test_play_refuses_a_batch_before_it_changes_the_game(self):
        import play as P
        old = P.ARENA
        P.ARENA = self.run_dir
        try:
            argv = sys.argv
            sys.argv = ["play.py", "start", "g", "--group", "plain", "--budget", "400"]
            P.main()
            sys.argv = ["play.py", "look", "g"]
            P.main()                                         # first call of this shell command: runs
            d = self.run_dir / "g"
            log, state = (d / "log.jsonl").read_bytes(), (d / "game.state").read_bytes()
            sys.argv = ["play.py", "press", "g", "up", "up"]
            with self.assertRaises(G.Blocked):
                P.main()                                     # same shell command (this test process): refused
            self.assertEqual((d / "log.jsonl").read_bytes(), log)        # not counted
            self.assertEqual((d / "game.state").read_bytes(), state)     # game unchanged
            self.assertTrue(G._take_lock(d / "busy.lock"))           # the refused call left the lock free
            G._drop_lock(d / "busy.lock")
        finally:
            sys.argv, P.ARENA = argv, old

    @unittest.skipUnless(os.name == "nt", "process tree check is Windows-only")
    def test_real_loop_in_one_shell_gets_one_key(self):
        code = "import sys; sys.path.insert(0, sys.argv[1]); import guard; print(guard.shell_key())"
        keys = {subprocess.run([sys.executable, "-c", code, str(ROOT / "arena")], capture_output=True,
                               text=True, check=True).stdout.strip() for _ in range(2)}
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys, {G.shell_key()})


if __name__ == "__main__":
    unittest.main()
