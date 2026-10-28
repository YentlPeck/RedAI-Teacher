"""R17 lean player (arena/lean_player.py): fake model + fake play.py, no emulator, no model calls.

Checks: prompt history <= 8 commands, notes cap, JSON retry then look, one play.py call per turn (fresh turn key),
Done / budget / max-commands stops, price math, plain vs teacher rules, play.py --lean guard key.
Temporary folders are moved to REDAI_TRASH (default .trash/), never deleted.
"""
import json
import os
import re
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
OWN = HERE.parent
sys.path[:0] = [str(OWN / "tools"), str(OWN / "arena")]
import settings  # noqa: E402
PARK = settings.TRASH / "r17-test-fixtures"
import lean_player as L  # noqa: E402
import play as P  # noqa: E402
import guard as G  # noqa: E402

FAKE_PLAY = r'''
import json, os, sys
from pathlib import Path
cmd, run = sys.argv[1], sys.argv[2]
runs = Path(os.environ["FAKE_RUNS"]); d = runs / run
done_at = int(os.environ.get("FAKE_DONE_AT", "0"))
def count():
    return json.loads((d / "count.json").read_text())["n"]
if cmd == "start":
    d.mkdir(parents=True)
    budget = int(sys.argv[sys.argv.index("--budget") + 1])
    (d / "count.json").write_text(json.dumps({"n": 0, "budget": budget, "lean": "--lean" in sys.argv}))
    from PIL import Image
    Image.new("RGB", (160, 144), (200, 200, 200)).save(d / "screen.png")
    print("Place: no map yet (power-on).\nScreenshot: " + str(d / "screen.png") + f"\nCommands used: 0 of {budget}")
    sys.exit(0)
c = json.loads((d / "count.json").read_text())
sys.stderr.write("UserWarning: Using SDL2 binaries from pysdl2-dll 2.32.10\n")
if os.environ.get("FAKE_REFUSE"):
    with open(d / "calls.jsonl", "a") as f:
        f.write(json.dumps({"argv": sys.argv[1:], "turn": os.environ.get("LEAN_PLAYER_TURN"), "refused": True}) + "\n")
    print(f"Commands used: {c['n']} of {c['budget']}")
    sys.exit("NOT RUN (another command on this game is still running). This did not count as a command.")
with open(d / "calls.jsonl", "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "turn": os.environ.get("LEAN_PLAYER_TURN")}) + "\n")
if c["n"] >= c["budget"]:
    print(f"Your {c['budget']} commands are used up. Stop and write your report.\nCommands used: {c['n']} of {c['budget']}")
    sys.exit(1)
c["n"] += 1
(d / "count.json").write_text(json.dumps(c))
n = c["n"]
if cmd == "ask":
    print(f"DO NOW: walk north ({n})\nWHY: Oak waits.\nCommands used: {n} of {c['budget']}")
    sys.exit(0)
print(f"Place: PALLET_TOWN x={n} y=5 (x grows to the right, y grows down), facing up. Badges: 0. Money: 3000.\n"
      f"Team: none yet.\nBag: empty.\nScreen text: HELLO {n}\nScreenshot: {d / 'screen.png'}")
if n == done_at:
    print("\nDone: you have the Boulder Badge. The game is over: stop and write your report.")
print(f"Commands used: {n} of {c['budget']}")
'''


def park(path):
    path = Path(path)
    if path.exists():
        PARK.mkdir(parents=True, exist_ok=True)
        os.rename(path, PARK / f"{path.name}-{uuid.uuid4().hex}")


class FakeModel:
    """Replies from a list (cycled at the end) or from a function of the call index."""

    def __init__(self, replies):
        self.replies, self.calls = replies, []

    def __call__(self, system, user, image):
        i = len(self.calls)
        self.calls.append(dict(system=system, user=user, image=str(image)))
        text = self.replies(i) if callable(self.replies) else self.replies[min(i, len(self.replies) - 1)]
        return dict(text=text, tokens=dict(input=1000, cached=200, output=50), cli_cost_usd=None, tool_calls=0)


def press(buttons="up", notes="n"):
    return json.dumps({"command": "press", "buttons": buttons, "notes": notes})


class Loop(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="r17-lean-"))
        self.addCleanup(park, self.dir)
        self.runs = self.dir / "runs"
        self.runs.mkdir()
        self.play = self.dir / "fake_play.py"
        self.play.write_text(FAKE_PLAY, encoding="utf-8")
        env = patch.dict(os.environ, {"FAKE_RUNS": str(self.runs)})
        env.start()
        self.addCleanup(env.stop)
        cool = patch.object(L, "COOLDOWN", 0.0)
        cool.start()
        self.addCleanup(cool.stop)

    def go(self, model, group="plain", budget=1000, max_commands=None, name="g", done_at=None):
        with patch.dict(os.environ, {"FAKE_DONE_AT": str(done_at or 0)}):
            return L.play_game(name, "haiku", group, budget, max_commands, model_fn=model, py=sys.executable,
                               play=self.play, runs=self.runs, sleep=lambda s: None)

    def calls(self, name="g"):
        p = self.runs / name / "calls.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def rows(self, name="g"):
        return [json.loads(l) for l in (self.runs / name / "lean.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_prompt_shows_at_most_eight_recent_commands(self):
        m = FakeModel([press()])
        self.go(m, max_commands=12)
        last = m.calls[-1]["user"]                      # prompt for command 12: commands 1-11 happened
        recent = last.split("YOUR LAST COMMANDS (oldest first):\n")[1].split("\n\n")[0].splitlines()
        self.assertEqual(len(recent), 8)
        self.assertEqual([int(l.split(".")[0]) for l in recent], list(range(4, 12)))
        self.assertNotIn("\n3. press", last)
        self.assertIn("HELLO 11", last)                 # the newest view
        self.assertNotIn("HELLO 10", last.split("GAME VIEW NOW")[1])

    def test_notes_are_capped_and_replaced(self):
        m = FakeModel([press(notes="x" * 1000), press(notes="short plan"), press(notes="")])
        self.go(m, max_commands=4)
        notes = lambda u: u.split("truth):\n")[1].split("\n\nYOUR LAST")[0]
        self.assertEqual(notes(m.calls[0]["user"]), "(no notes yet)")
        self.assertEqual(notes(m.calls[1]["user"]), "x" * 600)
        self.assertEqual(notes(m.calls[2]["user"]), "short plan")
        self.assertEqual(notes(m.calls[3]["user"]), "short plan")    # empty notes keep the old ones

    def test_bad_json_is_retried_once_on_the_same_turn(self):
        m = FakeModel(["I think I will go up", press("up up")])
        tot = self.go(m, max_commands=1)
        self.assertEqual(len(m.calls), 2)
        self.assertEqual(m.calls[0]["user"], m.calls[1]["user"])     # same turn, same prompt
        self.assertEqual([c["argv"][0] for c in self.calls()], ["press"])
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertIn("not JSON", rows[0]["bad"])
        self.assertTrue(rows[1]["counted"])
        self.assertEqual(rows[0]["prompt_sha"], rows[1]["prompt_sha"])
        self.assertEqual((tot["model_calls"], tot["commands"], tot["fallback_looks"]), (2, 1, 0))

    def test_two_bad_replies_count_as_a_look(self):
        m = FakeModel(["nope", json.dumps({"command": "press", "buttons": "up*7"}), press()])
        tot = self.go(m, max_commands=2)
        self.assertEqual([c["argv"][0] for c in self.calls()], ["look", "press"])
        self.assertEqual(tot["fallback_looks"], 1)
        self.assertIn("counted as look", m.calls[2]["user"])

    def test_invalid_commands_are_bad_replies(self):
        for text, group in ((json.dumps({"command": "press", "buttons": "up*7"}), "plain"),
                            (json.dumps({"command": "press", "buttons": "jump"}), "plain"),
                            (json.dumps({"command": "press", "buttons": ""}), "plain"),
                            (json.dumps({"command": "ask", "question": "where?"}), "plain"),
                            (json.dumps({"command": "ask", "question": " "}), "teacher"),
                            (json.dumps({"command": "run"}), "teacher"),
                            ("[1, 2]", "plain")):
            with self.assertRaises(L.BadReply, msg=text):
                L.parse_reply(text, group)
        self.assertEqual(L.parse_reply('```json\n{"command": "press", "buttons": "up right*3 a, b"}\n```', "plain"),
                         (["press", "up", "right*3", "a", "b"], None))
        self.assertEqual(L.parse_reply('{"command": "ask", "question": "where  now?", "notes": "n"}', "teacher"),
                         (["ask", "where now?"], "n"))

    def test_one_play_call_per_turn_with_a_fresh_turn_key(self):
        m = FakeModel([press(), json.dumps({"command": "look"}), press("a a")])
        self.go(m, max_commands=6)
        calls = self.calls()
        self.assertEqual(len(calls), 6)
        self.assertEqual(len(m.calls), 6)
        self.assertEqual(len({c["turn"] for c in calls}), 6)
        self.assertTrue(all(re.fullmatch(r"g-[0-9a-f]{32}", c["turn"]) for c in calls))
        self.assertEqual([r["n"] for r in self.rows()], [1, 2, 3, 4, 5, 6])

    def test_ask_answer_comes_next_turn_and_view_stays(self):
        m = FakeModel([press(), json.dumps({"command": "ask", "question": "where?"}), press()])
        self.go(m, group="teacher", max_commands=3)
        third = m.calls[2]["user"]
        self.assertIn('TEACHER ANSWER (to your question "where?"):\nDO NOW: walk north (2)', third)
        self.assertIn("HELLO 1", third.split("GAME VIEW NOW")[1])
        self.assertNotIn("TEACHER ANSWER", m.calls[3 - 1 + 0]["user"].split("GAME VIEW NOW")[1])

    def test_stops_on_done(self):
        m = FakeModel([press()])
        tot = self.go(m, done_at=3)
        self.assertEqual((tot["stop"], tot["used"], len(self.calls())), ("done", 3, 3))

    def test_stops_when_the_budget_is_used(self):
        m = FakeModel([press()])
        tot = self.go(m, budget=4)
        self.assertEqual((tot["stop"], tot["used"], len(self.calls()), len(m.calls)), ("budget", 4, 4, 4))
        self.assertIn("used 3 of 4 commands", m.calls[-1]["user"])
        self.assertIn("4 commands in total", m.calls[0]["system"])

    def test_resume_keeps_notes_history_and_count(self):
        m = FakeModel([press(notes="plan A")])
        self.go(m, max_commands=2)
        m2 = FakeModel([press()])
        tot = self.go(m2, max_commands=1)
        self.assertIn("plan A", m2.calls[0]["user"])
        self.assertIn("2. press up", m2.calls[0]["user"])
        self.assertEqual(tot["used"], 3)

    def test_totals_and_log_fields(self):
        m = FakeModel([press()])
        tot = self.go(m, max_commands=3)
        row = self.rows()[0]
        for k in ("prompt_sha", "reply", "tokens", "price_usd", "image_sha", "play_out", "counted"):
            self.assertIn(k, row)
        self.assertEqual(tot["tokens"]["input"], 3000)
        self.assertAlmostEqual(tot["price_usd"], 3 * L.price("haiku", dict(input=1000, cached=200, output=50)))
        self.assertEqual(tot["per_command"]["input"], 1000.0)
        saved = json.loads((self.runs / "g" / "lean_totals.json").read_text())
        self.assertEqual(saved["commands"], 3)

    def test_library_warnings_stay_out_of_the_view(self):
        m = FakeModel([press()])
        self.go(m, max_commands=2)
        self.assertNotIn("Warning", m.calls[1]["user"])
        self.assertIn("SDL2", self.rows()[0]["play_err"])

    def test_refused_commands_show_the_reason_and_stop_after_three(self):
        m = FakeModel([press()])
        self.go(m, max_commands=1)
        with patch.dict(os.environ, {"FAKE_REFUSE": "1"}):
            tot = self.go(m, max_commands=5)
        self.assertEqual((tot["stop"], tot["used"]), ("play-errors", 1))
        self.assertEqual(sum(1 for c in self.calls() if c.get("refused")), 3)
        hist = json.loads((self.runs / "g" / "lean_state.json").read_text(encoding="utf-8"))["history"]
        self.assertTrue(hist[-1].startswith("2. press up -> NOT RUN: NOT RUN (another command"), hist[-1])
        self.assertNotIn("Warning", hist[-1])

    def test_prompt_has_no_coordinator_paths(self):
        m = FakeModel([press()])
        self.go(m, group="teacher", max_commands=2)
        for c in m.calls:
            text = c["system"] + c["user"]
            for bad in ("Screenshot:", "redai-runs", "Commands used:", "lean.jsonl", str(self.runs)):
                self.assertNotIn(bad, text)


class Rules(unittest.TestCase):
    def test_arms_differ_only_in_ask_parts(self):
        plain, teacher = L.rules("plain", 1000), L.rules("teacher", 1000)
        self.assertNotIn("ask", plain.replace("task", ""))
        self.assertIn("- ask: ask a Pokémon Red teacher", teacher)
        self.assertIn("(look, press, ask all count)", teacher)
        self.assertIn("At most 6 presses per command", plain)
        self.assertIn("1000 commands in total", plain)
        self.assertIn("pick NEW GAME once to begin", plain)
        self.assertIn("no tools", plain)
        stripped = (teacher.replace(L.ASK_LINE, "").replace(", ask", "").replace(' or "ask"', "")
                    .replace(' "question": "your question (ask only)",', ""))
        self.assertEqual(stripped, plain)
        self.assertNotIn("{", plain.split("Reply with")[0])


class Price(unittest.TestCase):
    def test_haiku_matches_the_cli_cost_of_the_probe(self):
        # 27 Oct probe: 2 input + 685 one-hour cache write + 71 output; claude CLI total_cost_usd 0.0001727
        tok = dict(input=687, cached=0, cache_write_5m=0, cache_write_1h=685, output=71)
        self.assertAlmostEqual(L.price("haiku", tok), 0.0001727, places=9)

    def test_rates(self):
        self.assertAlmostEqual(L.price("haiku", dict(input=1_000_000, output=0)), 0.10)
        self.assertAlmostEqual(L.price("haiku", dict(input=1_000_000, cached=1_000_000)), 0.01)
        self.assertAlmostEqual(L.price("haiku", dict(input=500_000, cache_write_5m=500_000)), 0.0625)
        self.assertAlmostEqual(L.price("haiku", dict(output=1_000_000)), 0.50)
        # Luna (round b1 result): the b1 game 95.79M input of which 95.26M cached, 85k output = ~$1.05
        self.assertAlmostEqual(L.price("luna", dict(input=95_790_000, cached=95_260_000, output=85_000)),
                               0.053 + 0.9526 + 0.0425, places=4)


class PlayLeanKey(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="r17-key-"))
        self.addCleanup(park, self.d)

    def meta(self, **extra):
        (self.d / "meta.json").write_text(json.dumps(dict(group="plain", budget=10, **extra)), encoding="utf-8")

    def test_normal_runs_keep_the_shell_key(self):
        self.meta()
        with patch.dict(os.environ, {P.LEAN_ENV: "abcdefgh123"}):
            self.assertIsNone(P.lean_key(self.d))

    def test_lean_runs_need_the_loop_key(self):
        self.meta(player="lean")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(P.LEAN_ENV, None)
            with self.assertRaises(SystemExit):
                P.lean_key(self.d)
        with patch.dict(os.environ, {P.LEAN_ENV: "bad key!"}):
            with self.assertRaises(SystemExit):
                P.lean_key(self.d)
        with patch.dict(os.environ, {P.LEAN_ENV: "g-0123456789abcdef"}):
            self.assertEqual(P.lean_key(self.d), "lean:g-0123456789abcdef")

    def test_guard_refuses_a_second_call_with_the_same_turn_key(self):
        self.meta(player="lean")
        G.check(self.d, now=100.0, key="lean:t1")
        G.release(self.d, key="lean:t1", now=100.0)
        with self.assertRaises(G.Blocked):
            G.check(self.d, now=200.0, key="lean:t1")          # same turn key: one command per turn
        G.check(self.d, now=300.0, key="lean:t2")              # next turn: allowed
        G.release(self.d, key="lean:t2", now=300.0)

    def test_play_refuses_a_turn_key_used_before_t1_t2_t1(self):
        """Fix round (Sol R17): guard only compares with the last key; play.py keeps every used key."""
        arena = Path(tempfile.mkdtemp(prefix="r17-keys-"))
        self.addCleanup(park, arena)
        d = arena / "g"
        d.mkdir()
        (d / "meta.json").write_text(json.dumps(dict(group="plain", model="m", budget=10, start="power-on",
                                                     start_sha256=None, player="lean")), encoding="utf-8")
        (d / "game.state").write_bytes(b"synthetic")
        (d / "log.jsonl").write_text(json.dumps({"n": 0, "cmd": "start"}) + "\n", encoding="utf-8")
        ran = []

        def run(token):
            with patch.dict(os.environ, {P.LEAN_ENV: token}), patch.object(P, "ARENA", arena), \
                    patch.object(P, "play", lambda a, dd: ran.append(token)), patch.object(G, "COOLDOWN", 0.0), \
                    patch.object(sys, "argv", ["play.py", "look", "g"]), patch.object(sys.stdout, "reconfigure",
                                                                                     lambda **k: None, create=True):
                P.main()

        run("g-turn-0001")
        run("g-turn-0002")
        with self.assertRaises(G.Blocked) as cm:
            run("g-turn-0001")
        self.assertIn("used before", str(cm.exception))
        self.assertEqual(ran, ["g-turn-0001", "g-turn-0002"])         # the reused key ran nothing
        self.assertEqual((d / "lean_keys.txt").read_text(encoding="utf-8").split(),
                         ["lean:g-turn-0001", "lean:g-turn-0002"])
        blocked = [json.loads(l) for l in (d / "blocked.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([b["why"] for b in blocked], ["this turn key was used before"])
        with self.assertRaises(G.Blocked):                             # still refused later
            run("g-turn-0002")
        run("g-turn-0003")
        self.assertEqual(ran[-1], "g-turn-0003")


def codex_events(*items, usage=True):
    out = [json.dumps({"type": "thread.started", "thread_id": "x"}), json.dumps({"type": "turn.started"})]
    for it in items:
        out.append(json.dumps({"type": "item.started", "item": it}))
        out.append(json.dumps({"type": "item.completed", "item": it}))
    if usage:
        out.append(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 0,
                                                                   "output_tokens": 10}}))
    return "\n".join(out) + "\n"


LOOK = {"id": "item_9", "type": "agent_message", "text": json.dumps({"command": "look", "notes": "n"})}


class LunaIsolation(unittest.TestCase):
    """Fix round (Sol R17 B1): any tool event or isolation warning stops the turn before play.py."""

    def setUp(self):
        self.run = Path(tempfile.mkdtemp(prefix="r17-iso-"))
        self.addCleanup(park, self.run)
        (self.run / "lean_codex_catalog.json").write_text("{}", encoding="utf-8")
        (self.run / "lean_screen.png").write_bytes(b"png")
        self.cmds = []

    def fake_run(self, stdout, stderr="Reading prompt from stdin...\n"):
        def run(cmd, **kw):
            self.cmds.append(cmd)
            return type("P", (), dict(returncode=0, stdout=stdout, stderr=stderr))()
        return run

    def call(self, stdout, stderr="Reading prompt from stdin...\n"):
        with patch.object(L.subprocess, "run", self.fake_run(stdout, stderr)), \
                patch.object(L, "codex_path", lambda: Path("codex.exe")):
            return L.call_luna("rules", "turn", self.run / "lean_screen.png")

    def test_clean_run_has_no_isolation_problem(self):
        res = self.call(codex_events(LOOK))
        self.assertEqual((res["isolation"], res["tool_calls"]), ([], 0))
        cmd = self.cmds[0]
        for flag in ("--ignore-user-config", "--ephemeral", "read-only", "agents.max_depth=0"):
            self.assertIn(flag, cmd)
        self.assertTrue(any(c.startswith("model_catalog_json=") for c in cmd))
        for f in ("shell_tool", "unified_exec", "multi_agent", "code_mode_host"):
            self.assertIn(f, cmd)

    def test_mocked_command_execution_event_is_an_isolation_failure(self):
        cmd_item = {"id": "item_1", "type": "command_execution", "command": "type C:\\secret.txt", "status": "done"}
        res = self.call(codex_events(cmd_item, LOOK))
        self.assertEqual(res["tool_calls"], 1)
        self.assertTrue(any("command_execution" in p for p in res["isolation"]))

    def test_warnings_and_stray_stderr_are_isolation_failures(self):
        warn = {"id": "item_0", "type": "error", "message": "Codex is ignoring 1 unrecognized configuration settings."}
        self.assertTrue(self.call(codex_events(warn, LOOK))["isolation"])
        self.assertTrue(self.call(codex_events(LOOK), stderr="Reading prompt from stdin...\nWARNING: x\n")["isolation"])

    def test_loop_retries_then_counts_a_look_and_never_runs_the_tool_turn(self):
        loop = Loop("test_prompt_shows_at_most_eight_recent_commands")
        loop.setUp()
        try:
            iso = ["item.completed command_execution: dir"]
            replies = iter([dict(text=press("up"), tokens=dict(input=1, output=1), isolation=iso),
                            dict(text=press("up"), tokens=dict(input=1, output=1), isolation=iso),
                            dict(text=press("down"), tokens=dict(input=1, output=1), isolation=[])])
            tot = loop.go(lambda s, u, i: next(replies), max_commands=2)
            self.assertEqual([c["argv"][:2] for c in loop.calls()], [["look", "g"], ["press", "g"]])
            self.assertEqual(loop.calls()[1]["argv"][2:], ["down"])
            rows = loop.rows()
            self.assertEqual([bool(r.get("isolation")) for r in rows], [True, True, False])
            self.assertNotIn("play_out", rows[0])                       # first isolation attempt ran nothing
            self.assertEqual(rows[1]["fallback"], "look")
            self.assertEqual((tot["isolation_failures"], tot["fallback_looks"], tot["commands"]), (2, 1, 2))
        finally:
            loop.doCleanups()

    def test_haiku_tool_use_is_an_isolation_failure(self):
        lines = [{"type": "system", "subtype": "init", "tools": ["Bash"]},
                 {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
                 {"type": "result", "result": press(), "usage": {"input_tokens": 5, "output_tokens": 5}}]
        out = "\n".join(json.dumps(x) for x in lines)
        fake = self.fake_run(out, "")
        with patch.object(L, "run_idle", lambda cmd, *a, **k: fake(cmd)):   # r23: call_haiku uses run_idle
            res = L.call_haiku("rules", "turn", self.run / "lean_screen.png")
        self.assertEqual(len(res["isolation"]), 2)

    def test_preflight_refuses_any_tool_but_request_user_input(self):
        models = json.dumps({"models": [{"slug": "gpt-6-luna", "tool_mode": "code_mode_only"}]})

        def prompt(tools):
            return json.dumps([{"type": "additional_tools", "tools": [{"type": "namespace", "name": "functions",
                                                                       "tools": [{"name": t} for t in tools]}]},
                               {"type": "message", "role": "developer"}])

        for tools, ok in ((["request_user_input"], True), ([], True), (["request_user_input", "exec"], False),
                          (["spawn_agent"], False)):
            outs = iter([models, prompt(tools)])

            def run(cmd, **kw):
                return type("P", (), dict(returncode=0, stdout=next(outs), stderr=""))()
            with patch.object(L.subprocess, "run", run), patch.object(L, "codex_path", lambda: Path("codex.exe")):
                if ok:
                    self.assertEqual(L.codex_preflight(self.run, "rules")["tools"], sorted(tools))
                else:
                    with self.assertRaises(SystemExit):
                        L.codex_preflight(self.run, "rules")
        cat = json.loads((self.run / "lean_codex_catalog.json").read_text(encoding="utf-8"))["models"][0]
        self.assertEqual((cat["tool_mode"], cat["multi_agent_version"], cat["apply_patch_tool_type"]),
                         ("direct", "v1", None))


if __name__ == "__main__":
    unittest.main()


class RunIdle(unittest.TestCase):
    """r23: a claude call that goes silent is cut after the idle limit; a normal call returns its output."""

    def test_silent_process_is_cut(self):
        code = "import sys, time; print('thinking', flush=True); time.sleep(30)"
        t = time.time()
        with self.assertRaises(L.subprocess.TimeoutExpired):
            L.run_idle([sys.executable, "-c", code], "", dict(os.environ), idle=2, total=60)
        self.assertLess(time.time() - t, 15)

    def test_normal_process_returns_output(self):
        code = "import sys; data = sys.stdin.read(); print('got', len(data)); print('err', file=sys.stderr)"
        p = L.run_idle([sys.executable, "-c", code], "hello\n", dict(os.environ), idle=10, total=60)
        self.assertEqual((p.returncode, p.stdout.strip(), p.stderr.strip()), (0, "got 6", "err"))
