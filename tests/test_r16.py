"""R16 (PokéBench rules): 6-press limit, power-on start, milestones, score_bench, teacher fixes, one emulator smoke.

Non-emulator by default (WRAM fixtures and fake games). R16_TEST_DEV=<dev folder> runs only the Teacher class
against another dev folder (the unchanged dev-r15 baseline: those tests must fail there).
The emulator smoke runs only with ARENA_EMULATOR_TESTS=1 (one emulator, ram_file = empty 32 KB buffer).
Temporary folders are moved to REDAI_TRASH (default .trash/), never deleted.
"""
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import types
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
OWN = HERE.parent
DEV = Path(os.environ.get("R16_TEST_DEV", OWN)).resolve()
BASELINE = DEV != OWN
ROOT = OWN
TEACHER = OWN.parent
sys.path[:0] = [str(DEV / "tools"), str(DEV / "arena")]
import settings  # noqa: E402
FIX = settings.FixtureDir("bench")                       # game memory at boot screens (not in the repo)
REC = settings.FixtureDir("record-1831000065-v3")
PARK = settings.TRASH / "r16-test-fixtures"
import read_state as R  # noqa: E402
import advise as A  # noqa: E402
import play as P  # noqa: E402

if not BASELINE:
    import bench as B  # noqa: E402
    sys.path.insert(0, str(OWN / "arena"))
    SB = importlib.util.spec_from_file_location("r16_score_bench", OWN / "arena" / "score_bench.py")
    S = importlib.util.module_from_spec(SB)
    SB.loader.exec_module(S)
    MP = importlib.util.spec_from_file_location("r16_make_prompt", OWN / "arena" / "make_prompt.py")
    M = importlib.util.module_from_spec(MP)
    MP.loader.exec_module(M)


def park(path):
    """Move a test folder out of the way (never delete)."""
    path = Path(path)
    if path.exists():
        PARK.mkdir(parents=True, exist_ok=True)
        os.rename(path, PARK / f"{path.name}-{uuid.uuid4().hex}")


def tmpdir(case):
    d = Path(tempfile.mkdtemp(prefix="r16-"))
    case.addCleanup(park, d)
    return d


# ---------- WRAM fixtures (boot probe + record game) ----------

def wram(path, patch_=None):
    data = bytearray(Path(path).read_bytes())
    for addr, val in (patch_ or {}).items():
        data[addr - 0xC000] = val
    return bytes(data)


def ev(data_path, *names):
    data = Path(data_path).read_bytes()
    out = {}
    for n in names:
        bit = R.EVENTS[n]
        a = R.A("wEventFlags") + bit // 8
        out[a] = out.get(a, data[a - 0xC000]) | (1 << (bit % 8))
    return out


def at(map_name, x, y):
    mid = next(i for i, n in R.MAPS.items() if n == map_name)
    return {R.A("wCurMap"): mid, R.A("wXCoord"): x, R.A("wYCoord"): y}


def bag(*items):
    ids = {n: i for i, n in R.ITEMS.items()}
    out = {R.A("wNumBagItems"): len(items)}
    for i, (name, n) in enumerate(items):
        out[R.A("wBagItems") + 2 * i], out[R.A("wBagItems") + 2 * i + 1] = ids[name], n
    out[R.A("wBagItems") + 2 * len(items)] = 0xFF
    return out


def tiles(rows):
    chars = {c: t for t, c in R.CHARS.items() if t >= 0x7F and len(c) == 1}
    out = {a: 0x7F for a in range(0xC3A0, 0xC3A0 + 360)}
    for r, text in rows:
        for c, ch in enumerate(text.ljust(20)[:20]):
            out[0xC3A0 + r * 20 + c] = 0xED if ch == ">" else chars.get(ch, 0x7F)
    return out


def teacher_view(data):
    """The teacher's private state as play.py builds it (intro = no map header, wCurMapWidth 0)."""
    m = R.Wram(data)
    s = R.state_from_wram(data)
    if m[R.A("wCurMapWidth")] == 0:
        s = dict(s, intro=True, text_box=True)
    return P.teacher_state(s, m)


def ask(data, q=None):
    a = A.answer(teacher_view(data), q, context={})
    return a, A.text(a)


def merged(*patches):
    out = {}
    for p in patches:
        out.update(p)
    return out


BUTTON_RUN = re.compile(r"(?<![\w*])(?:up|down|left|right|a|b|start|select)(?:\*\d+)?"
                        r"(?: (?:up|down|left|right|a|b|start|select)(?:\*\d+)?)*(?![\w*])")


def longest_run(text):
    return max((sum(int(t.split("*")[1]) if "*" in t else 1 for t in r.split()) for r in BUTTON_RUN.findall(text)),
               default=0)


# ---------- 1. harness: 6 presses, power-on start, done after the badge ----------

class Output(io.StringIO):
    def reconfigure(self, **kwargs):
        pass


@unittest.skipIf(BASELINE, "harness tests are for dev-r23 only")
class Harness(unittest.TestCase):
    def setUp(self):
        self.arena = tmpdir(self)

    def main(self, args):
        out = Output()
        with patch.object(P, "ARENA", self.arena), patch.object(sys, "argv", ["play.py"] + args), redirect_stdout(out):
            P.main()
        return out.getvalue()

    def game(self, rows, budget=1000, group="plain"):
        d = self.arena / "g"
        d.mkdir()
        (d / "meta.json").write_text(json.dumps(dict(group=group, model="m", budget=budget, start="power-on",
                                                     start_sha256=None)), encoding="utf-8")
        (d / "game.state").write_bytes(b"synthetic")
        (d / "log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        return d

    def test_six_presses_pass_seven_are_refused(self):
        self.assertEqual(P.MAX_PRESSES, 6)
        self.assertEqual(P.parse_buttons(["a*3", "up", "b", "start"]), ["a"] * 3 + ["up", "b", "start"])
        for keys in (["a*7"], ["a*3", "b*4"], ["up"] * 7, ["right*3", "a", "b", "down", "left"]):
            with self.subTest(keys=keys), self.assertRaisesRegex(SystemExit, "^at most 6 presses per command$"):
                P.parse_buttons(keys)

    def blocked(self, d):
        f = d / "blocked.jsonl"
        return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []

    def refused(self, d, cmd, pattern):
        """Run a refused command on a fake game: nothing opens, log/state/count unchanged, one audit row."""
        before = {n: (d / n).read_bytes() for n in ("log.jsonl", "game.state")}
        used = P.commands_used(P.history_rows(d))
        rows = len(self.blocked(d))
        with patch.object(P, "Game") as game, patch.object(P.guard, "check"), patch.object(P.guard, "release"):
            with self.assertRaisesRegex(SystemExit, pattern):
                self.main(cmd)
        game.assert_not_called()
        self.assertEqual({n: (d / n).read_bytes() for n in before}, before)
        self.assertEqual(P.commands_used(P.history_rows(d)), used)
        new = self.blocked(d)[rows:]
        self.assertEqual(len(new), 1)
        self.assertEqual((new[0]["cmd"], new[0]["keys"]), (cmd[0], cmd[2:]))
        return new[0]

    def test_seven_presses_run_nothing_and_cost_nothing(self):
        d = self.game([dict(n=0, cmd="start", map="PALLET_TOWN", done=[], bench_started=False, bench_milestones=[])])
        row = self.refused(d, ["press", "g", "a*3", "b*4"], "^at most 6 presses per command$")
        self.assertEqual((row["why"], row["message"]), ("too many presses", "at most 6 presses per command"))
        self.assertEqual(self.refused(d, ["press", "g", "jump"], "unknown button")["why"], "unknown button")

    def test_budget_and_no_teacher_refusals_are_logged(self):
        rows = [dict(n=0, cmd="start", map="PALLET_TOWN", done=[], bench_started=False, bench_milestones=[])]
        rows += [dict(n=i, cmd="press", map="PALLET_TOWN", done=[]) for i in (1, 2)]
        d = self.game(rows, budget=2)
        row = self.refused(d, ["look", "g"], "commands are used up")
        self.assertEqual(row["why"], "budget used")
        park(d)
        d = self.game(rows[:1])
        self.assertEqual(self.refused(d, ["ask", "g", "help"], "no teacher")["why"], "no teacher")

    def test_start_without_state_is_power_on_with_default_budget(self):
        s = dict(place=dict(map="PALLET_TOWN", map_id=0), story=dict(done=[]), intro=True)
        mem = bytearray(0x10000)
        with patch.object(P, "Game") as game, patch.object(P, "view", return_value=(s, "BOOT VIEW")), \
                patch.object(Path, "read_bytes", side_effect=AssertionError("no state or save file may be read")):
            game.return_value.m = mem
            out = self.main(["start", "g", "--group", "teacher"])
        game.assert_called_once()
        self.assertEqual(game.call_args.kwargs, dict(fresh=True))
        game.return_value.tick.assert_called_once_with(P.BOOT_FRAMES)
        d = self.arena / "g"
        meta = json.loads((d / "meta.json").read_text())
        row = P.history_rows(d)[0]
        self.assertEqual((meta["budget"], meta["start"], meta["start_sha256"]), (1000, "power-on", None))
        self.assertEqual((row["budget"], row["start"], row["intro"]), (1000, "power-on", True))
        self.assertEqual((row["bench_started"], row["bench_milestones"]), (False, []))
        self.assertFalse((d / "game.state").exists())          # Game.close() writes it after the boot
        self.assertEqual(out, "BOOT VIEW\nCommands used: 0 of 1000\n")

    def test_fresh_game_never_loads_a_state_and_uses_an_empty_save_buffer(self):
        made = {}

        class FakePyBoy:
            def __init__(self, rom, **kw):
                made.update(rom=rom, **kw)
                self.memory = bytearray(0x10000)

            def set_emulation_speed(self, n):
                pass

            def load_state(self, fh):
                raise AssertionError("fresh boot must not load a state")

        fake = types.ModuleType("pyboy")
        fake.PyBoy = FakePyBoy
        d = self.arena / "fresh"
        d.mkdir()
        with patch.dict(sys.modules, {"pyboy": fake}):
            P.Game(d, fresh=True)
        ram = made["ram_file"]
        self.assertIsInstance(ram, io.BytesIO)
        self.assertEqual(ram.getvalue(), bytes(0x8000))
        self.assertEqual(Path(made["rom"]), settings.ROM)
        self.assertEqual(list(d.iterdir()), [])

    def test_done_after_boulder_badge_refuses_every_command_for_free(self):
        rows = [dict(n=0, cmd="start", map="PALLET_TOWN", done=[], bench_started=False, bench_milestones=[]),
                dict(n=1, cmd="press", map="PEWTER_GYM", done=["badge1"], bench_started=True,
                     bench_milestones=list(B.KEYS))]
        d = self.game(rows, group="teacher")
        before = (d / "log.jsonl").read_bytes()
        for cmd in (["look", "g"], ["press", "g", "a"], ["ask", "g", "what now?"]):
            with self.subTest(cmd=cmd):
                row = self.refused(d, cmd, "^Done: you have the Boulder Badge")
                self.assertEqual((row["why"], row["message"]), ("game done", B.DONE_MESSAGE))
        self.assertEqual(len(self.blocked(d)), 3)
        self.assertEqual((d / "log.jsonl").read_bytes(), before)
        with self.assertRaisesRegex(SystemExit, "game is done"):
            P.resume(d, "player", "stop")

    def test_the_command_that_wins_the_badge_prints_done(self):
        rows = [dict(n=0, cmd="start", map="PEWTER_GYM", done=[], bench_started=True,
                     bench_milestones=list(B.KEYS[:-1]))]
        d = self.game(rows)
        mem = bytearray(0x10000)
        mem[R.A("wCurMap")] = B.MAP_OF["pewter_gym"]
        mem[R.A("wObtainedBadges")] = 1
        s = dict(place=dict(map="PEWTER_GYM", map_id=54, x=4, y=2), story=dict(done=["badge1"]), team=[],
                 battle=None, money=0, text_box=True)
        with patch.object(P, "Game") as game, patch.object(P, "view", return_value=(s, "VIEW")), \
                patch.object(P.guard, "check"), patch.object(P.guard, "release"):
            game.return_value.m = mem
            game.return_value.where.return_value = (54, 4, 2)
            game.return_value.map_transitions = []
            out = self.main(["press", "g", "a"])
        self.assertIn(B.DONE_MESSAGE, out)
        last = P.history_rows(d)[-1]
        self.assertEqual(last["bench_milestones"], list(B.KEYS))

    def test_intro_view_hides_the_boot_place_and_logo_letters(self):
        data = wram(FIX / "title.wram")
        g = types.SimpleNamespace(m=R.Wram(data), gb=None)
        with patch.object(P.R, "state_from_pyboy", return_value=R.state_from_wram(data)):
            s, text = P.view(g, self.arena)
        self.assertTrue(s["intro"] and s["text_box"])
        self.assertIn("Place: no map yet (power-on", text)
        self.assertNotIn("PALLET_TOWN", text)
        self.assertNotIn("Screen text", text)            # the logo tiles decode as the alphabet: filtered
        self.assertEqual(P.screen_text(R.Wram(wram(FIX / "naming_screen.wram")))[:2], ["YOUR NAME?", "A B C D E F G H I"])
        room = R.Wram(wram(FIX / "room_after_a.wram"))
        self.assertFalse(P.in_intro(room))


# ---------- 2. milestones ----------

def pokered_map_ids():
    text = (settings.REFERENCE / "pokered/constants/map_constants.asm").read_text(encoding="utf-8")
    return {n: int(h, 16) for n, h in re.findall(r"map_const (\w+),[^;]*;\s*\$([0-9A-Fa-f]+)", text)}


@unittest.skipIf(BASELINE, "milestones are dev-r23 only")
class Milestones(unittest.TestCase):
    def test_ram_facts_match_pokered(self):
        ids = pokered_map_ids()
        self.assertEqual(B.HOUSE, {ids["REDS_HOUSE_1F"], ids["REDS_HOUSE_2F"]})
        self.assertEqual(B.HOUSE, {0x25, 0x26})
        self.assertEqual(B.MAP_OF, dict(route_1=0x0C, viridian_city=0x01, viridian_forest=0x33, pewter_city=0x02,
                                        pewter_gym=0x36))
        self.assertEqual({k: ids[n] for k, n in (("route_1", "ROUTE_1"), ("viridian_city", "VIRIDIAN_CITY"),
                                                 ("viridian_forest", "VIRIDIAN_FOREST"), ("pewter_city", "PEWTER_CITY"),
                                                 ("pewter_gym", "PEWTER_GYM"))}, B.MAP_OF)
        items = (settings.REFERENCE / "pokered/constants/item_constants.asm").read_text(encoding="utf-8")
        self.assertEqual(B.PARCEL, int(re.search(r"const OAKS_PARCEL\s*;\s*\$([0-9A-F]+)", items)[1], 16))
        sym = (settings.REFERENCE / "pokered.sym").read_text(encoding="utf-8")
        for name, addr in (("wCurMap", 0xD35E), ("wPartyCount", 0xD163), ("wObtainedBadges", 0xD356),
                           ("wNumBagItems", 0xD31D), ("wEventFlags", 0xD747), ("wCurMapWidth", 0xD369)):
            self.assertIn(f"00:{addr:04x} {name}", sym)
        mart = (settings.REFERENCE / "pokered/scripts/ViridianMart.asm").read_text(encoding="utf-8")
        self.assertRegex(mart, r"lb bc, OAKS_PARCEL, 1\s+call GiveItem\s+SetEvent EVENT_GOT_OAKS_PARCEL")
        lab = (settings.REFERENCE / "pokered/scripts/OaksLab.asm").read_text(encoding="utf-8")
        self.assertIn("SetEvent EVENT_GOT_POKEDEX", lab)
        badges = (settings.REFERENCE / "pokered/constants/ram_constants.asm").read_text(encoding="utf-8")
        self.assertRegex(badges, r"const_def\s+(?:;.*\s+)?const BIT_BOULDERBADGE")

    def test_same_ladder_as_pokebench(self):
        src = settings.FIXTURES / "pokebench" / "milestones.py"
        if not src.exists():
            self.skipTest("PokéBench copy not present")
        theirs = re.findall(r'\("(\w+)",\s+"([^"]+)"', src.read_text(encoding="utf-8"))
        self.assertEqual([k for k, _ in theirs], list(B.KEYS))

    def test_boot_title_and_menu_never_count_as_leaving_the_house(self):
        prev = {}
        for name in ("title", "menu"):
            prev = B.fields(R.Wram(wram(FIX / f"{name}.wram")), prev)
            self.assertEqual(prev, dict(bench_started=False, bench_milestones=[]))
        self.assertIn("left_house", B.checks(R.Wram(wram(FIX / "title.wram"))))   # map 0 reads as Pallet Town
        prev = B.fields(R.Wram(wram(FIX / "oak_speech.wram")), prev)       # NEW GAME sets Red's room
        self.assertEqual(prev, dict(bench_started=True, bench_milestones=[]))
        prev = B.fields(R.Wram(wram(FIX / "room_after_a.wram")), prev)
        self.assertEqual(prev["bench_milestones"], [])

    def test_record_states_reach_each_milestone(self):
        cases = [
            (REC / "split-01.wram", None, {"left_house", "got_starter"}),
            (REC / "split-01.wram", at("ROUTE_1", 10, 20), {"left_house", "got_starter", "route_1"}),
            (REC / "split-01.wram", at("VIRIDIAN_CITY", 21, 26), {"left_house", "got_starter", "viridian_city"}),
            (REC / "split-01.wram", merged(at("VIRIDIAN_MART", 3, 5), bag(("OAKS_PARCEL", 1))),
             {"left_house", "got_starter", "got_parcel"}),
            (REC / "split-02.wram", None, {"left_house", "got_starter", "got_parcel", "got_pokedex"}),
            (REC / "battle-002.wram", None, {"left_house", "got_starter", "got_parcel", "got_pokedex", "viridian_forest"}),
            (REC / "split-02.wram", at("PEWTER_CITY", 18, 30),
             {"left_house", "got_starter", "got_parcel", "got_pokedex", "pewter_city"}),
            (REC / "split-03.wram", None, {"left_house", "got_starter", "got_parcel", "got_pokedex", "pewter_gym"}),
            (REC / "split-04.wram", None, {"left_house", "got_starter", "got_parcel", "got_pokedex", "beat_brock"}),
            (FIX / "lab_arrival.wram", None, {"left_house"}),
        ]
        for path, p, want in cases:
            with self.subTest(path=path.name, patch=p and sorted(p)[:1]):
                self.assertEqual(B.checks(R.Wram(wram(path, p))), want)

    def test_milestones_are_kept_and_ordered(self):
        prev = dict(bench_started=True, bench_milestones=["left_house"])
        room = R.Wram(wram(FIX / "room_after_a.wram"))                  # back home later: still counted
        self.assertEqual(B.fields(room, prev)["bench_milestones"], ["left_house"])
        badge = R.Wram(wram(REC / "split-04.wram"))
        self.assertEqual(B.fields(badge, prev)["bench_milestones"],
                         ["left_house", "got_starter", "got_parcel", "got_pokedex", "beat_brock"])
        rows = [dict(n=0, cmd="start"), dict(n=1, cmd="press", **B.fields(badge, prev))]
        self.assertTrue(B.finished(rows))


# ---------- 3. score_bench ----------

def run_rows(hits, n=1000, resume_at=None):
    """A log with `hits` = {command: [new keys]}; bench fields carried forward like play.py."""
    rows, got = [dict(n=0, cmd="start", bench_started=False, bench_milestones=[])], []
    for i in range(1, n + 1):
        got = got + [k for k in hits.get(i, []) if k not in got]
        rows.append(dict(n=i, cmd="ask" if i % 7 == 0 else "press", bench_started=True,
                         bench_milestones=[k for k in B.KEYS if k in got]))
        if resume_at == i:
            rows.append(dict(n=i, cmd="resume", bench_milestones=rows[-1]["bench_milestones"]))
    return rows


@unittest.skipIf(BASELINE, "score_bench is dev-r23 only")
class ScoreBench(unittest.TestCase):
    def test_first_command_of_each_milestone(self):
        r = S.summarize(run_rows({3: ["left_house"], 40: ["got_starter"], 41: ["route_1"], 300: ["viridian_city"]},
                                 resume_at=100))
        self.assertEqual(r["first_command"], dict(left_house=3, got_starter=40, route_1=41, viridian_city=300))
        self.assertEqual((r["furthest_index"], r["furthest_key"], r["furthest_command"]), (4, "viridian_city", 300))
        self.assertEqual(r["commands_used"], 1000)

    def test_budget_cuts_late_milestones_and_badge_stops(self):
        late = S.summarize(run_rows({5: ["left_house"], 1000: ["got_starter"], 1001: ["route_1"]}, n=1001), 1000)
        self.assertEqual(late["furthest_key"], "got_starter")
        won = S.summarize(run_rows({k + 1: [key] for k, key in enumerate(B.KEYS)}, n=20))
        self.assertTrue(won["beat_brock"])
        self.assertEqual((won["furthest_index"], won["furthest_command"], won["commands_used"]), (10, 10, 10))

    def test_rank_furthest_then_fewer_commands(self):
        a = dict(run="a", **S.summarize(run_rows({1: ["left_house"], 9: ["got_starter"], 500: ["pewter_city"]})))
        b = dict(run="b", **S.summarize(run_rows({1: ["left_house"], 9: ["got_starter"], 450: ["pewter_city"]})))
        c = dict(run="c", **S.summarize(run_rows({1: ["left_house"], 9: ["got_starter"], 900: ["pewter_gym"]})))
        none = dict(run="n", **S.summarize(run_rows({})))
        self.assertEqual([r["run"] for r in S.ranking([a, none, b, c])], ["c", "b", "a", "n"])
        self.assertEqual(none["furthest_index"], 0)

    def test_unknown_key_is_an_error_and_cli_reads_games(self):
        with self.assertRaises(ValueError):
            S.summarize([dict(n=1, cmd="press", bench_milestones=["moon"])])
        arena = tmpdir(self)
        for name, hits in (("g1", {2: ["left_house"]}), ("g2", {2: ["left_house"], 3: ["got_starter"]})):
            d = arena / name
            d.mkdir()
            (d / "meta.json").write_text(json.dumps(dict(group="teacher", model="haiku", budget=1000, start="power-on")))
            (d / "log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in run_rows(hits, n=5)))
        out = Output()
        with patch.object(S, "ARENA", arena), redirect_stdout(out):
            S.main(["g1", "g2", "--json"])
        res = json.loads(out.getvalue())
        self.assertEqual([r["run"] for r in res], ["g2", "g1"])
        self.assertTrue(all(r["rules_ok"] for r in res))


# ---------- 4. player prompt ----------

@unittest.skipIf(BASELINE, "prompt is dev-r23 only")
class Prompt(unittest.TestCase):
    def test_power_on_prompt_numbers_and_equal_arms(self):
        arena = tmpdir(self)
        out = {}
        for group in ("plain", "teacher"):
            d = arena / ("runp" if group == "plain" else "runt")
            d.mkdir()
            (d / "meta.json").write_text(json.dumps(dict(group=group, model="", budget=1000, start="power-on",
                                                         start_sha256=None)))
            with patch.object(M, "ARENA", arena):
                out[group] = M.prompt(d.name)
        for text in out.values():
            self.assertIn("The game starts from power-on (the Game Freak logo): pick NEW GAME once to begin", text)
            self.assertIn("Do not restart the game: never pick NEW GAME a second time and never reset.", text)
            self.assertIn("Keep playing until the tool says the game\n  is done or all of them are used", text)
            self.assertIn("Stop only when the tool says the game is done or all 1000 commands are used.", text)
            self.assertNotIn("ONLY reason", text)
            self.assertNotIn("start a new game yourself", text)
            self.assertNotIn("Do not start a new game", text)
            self.assertIn("At most 6 presses per\ncommand.", text)
            self.assertIn("You have 1000 commands in total", text)
            self.assertNotIn("20 presses", text)
            self.assertNotIn("bedroom", text)
        normalized = "\n".join(l for l in out["teacher"].split("\n") if "arena/play.py ask " not in l)
        self.assertEqual(out["plain"], normalized.replace(", ask", "").replace("runt", "runp"))
        if not (TEACHER / "dev-r15").is_dir():
            self.skipTest("needs the round 15 prompt (project history, not in the repo)")
        old = (TEACHER / "dev-r15" / "arena" / "PLAYER_PROMPT.md").read_text(encoding="utf-8").replace("dev-r15", "dev-r23")
        new = (OWN / "arena" / "PLAYER_PROMPT.md").read_text(encoding="utf-8")
        changed = [l for l in new.splitlines() if l not in old.splitlines()]
        self.assertEqual(len(changed), 5, changed)        # 6 presses, Done-or-budget (2 lines), no restart, stop line
        self.assertTrue(all(re.search(r"6 presses|done|restart|says the game", l) for l in changed), changed)


# ---------- 5. teacher fixes (each fails on the unchanged dev-r15) ----------

class Teacher(unittest.TestCase):
    def test_logo_and_title_say_press_a_not_walking(self):
        for data in (wram(FIX / "title.wram"), wram(FIX / "title.wram", tiles([]))):
            a, text = ask(data, "What should I do?")
            self.assertIn("a a a a a a", a["do"])
            self.assertNotIn("rejoin", text)
            self.assertNotIn("Oak's event flag", text)

    def test_main_menu_picks_new_game(self):
        a, text = ask(wram(FIX / "menu.wram"))
        self.assertTrue(a["do"].startswith("Press A: the arrow is on NEW GAME"))
        self.assertNotIn("sign or person", text)

    def test_oak_talk_uses_b_so_the_name_list_is_safe(self):
        for name in ("oak_speech", "legend_text"):
            a, text = ask(wram(FIX / f"{name}.wram"), "What should I do?")
            self.assertIn("b*6", a["do"])
            self.assertNotIn("REDS_HOUSE_1F", text)

    def test_name_lists_pick_a_ready_made_name(self):
        a, _ = ask(wram(FIX / "name_menu.wram"), "What name should I pick?")
        self.assertIn("Press: down a", a["do"])
        self.assertIn("RED", a["do"])
        b, _ = ask(wram(FIX / "rival_menu.wram"))
        self.assertIn("Press: down a", b["do"])
        self.assertIn("BLUE", b["do"])
        self.assertNotIn("START", a["do"] + b["do"])

    def test_letter_screen_one_letter_then_start(self):
        for rows in (None, tiles([(1, " RIVAL's NAME?"), (5, " A B C D E F G H I")])):
            a, _ = ask(wram(FIX / "naming_screen.wram", rows), "how do I finish?")
            self.assertIn("Press: a start", a["do"])
            self.assertNotIn("jump to the END", a["do"])

    def test_pallet_town_walks_to_the_top_row(self):
        data = wram(FIX / "room_after_a.wram", at("PALLET_TOWN", 5, 6))
        a, _ = ask(data, "Where do I go?")
        self.assertIn("(10,1)", a["do"])
        self.assertRegex(a["do"], r"up \d+ to \(1[01],1\)")
        top, _ = ask(wram(FIX / "room_after_a.wram", at("PALLET_TOWN", 10, 2)))
        self.assertIn("up 1 to (10,1)", top["do"])

    def test_lab_starter_how_and_why(self):
        data = wram(FIX / "lab_arrival.wram", at("OAKS_LAB", 5, 3))
        for q in ("Which starter should I pick?", "Should I take Charmander?", None):
            with self.subTest(q=q):
                a, text = ask(data, q)
                self.assertIn("SQUIRTLE", a["do"])
                self.assertIn("(7,4)", a["do"])
                self.assertIn("half damage", a["why"])
                self.assertIn("nickname", text)
                self.assertNotIn("Mt. Moon", text)
                self.assertNotIn("Go downstairs", text)

    def test_nickname_question_and_screen(self):
        q = wram(REC / "split-01.wram", merged(tiles([(12, " Do you want to"), (14, " give a nickname"),
                                                       (16, " to SQUIRTLE?"), (8, "              YES")]),
                                                {R.A("wFontLoaded"): 1}))
        a, _ = ask(q)
        self.assertTrue(a["do"].startswith("Press B for NO"))
        screen = wram(REC / "split-01.wram", merged(tiles([(1, " SQUIRTLE"), (3, " NICKNAME?"),
                                                            (5, " A B C D E F G H I")]), {R.A("wFontLoaded"): 1}))
        b, _ = ask(screen)
        self.assertTrue(b["do"].startswith("Press START"))

    def test_parcel_goes_to_oak_from_below(self):
        data = wram(REC / "split-01.wram", merged(at("OAKS_LAB", 5, 6), bag(("OAKS_PARCEL", 1)),
                                                  ev(REC / "split-01.wram", "EVENT_BATTLED_RIVAL_IN_OAKS_LAB",
                                                     "EVENT_GOT_OAKS_PARCEL")))
        a, _ = ask(data, "What do I do here?")
        self.assertIn("(5,3)", a["do"])
        self.assertIn("up a", a["do"])
        self.assertNotIn("(5,1)", a["do"])

    def test_old_man_needs_the_pokedex(self):
        data = wram(REC / "split-01.wram", merged(at("VIRIDIAN_CITY", 19, 10), bag(("OAKS_PARCEL", 1)),
                                                  ev(REC / "split-01.wram", "EVENT_BATTLED_RIVAL_IN_OAKS_LAB",
                                                     "EVENT_GOT_OAKS_PARCEL")))
        a, _ = ask(data, "An old man blocks the road north. How do I pass?")
        self.assertIn("Pokédex", a["do"])
        self.assertIn("Parcel", a["do"])

    def test_no_answer_asks_for_more_than_six_presses(self):
        states = [wram(FIX / f.name) for f in sorted(FIX.glob("*.wram"))]
        states += [wram(REC / f"{n}.wram") for n in ("split-01", "battle-001", "battle-002", "split-02", "split-03")]
        for i, data in enumerate(states):
            for q in (None, "What should I do?", "Which move?"):
                a, text = ask(data, q)
                self.assertLessEqual(longest_run(text), 6, (i, q, text))
        # R13's repeated-screen answer (test_r13 t16-4 case): keys plus the first walk in ONE command.
        sys.path.insert(0, str(DEV / "tests"))
        import test_r12 as H
        s = H.state("PEWTER_POKECENTER", (3, 3), hp=31, text_box=True,
                    teacher_screen=dict(rows=["Thank you!", "Your POKéMO"], cursor=False))
        ctx = {}
        for _ in range(4):
            out = A.answer(s, "What is happening?", context=ctx)
        self.assertIn("press these in ONE command: b*3", out["do"])
        self.assertLessEqual(longest_run(A.text(out)), 6, out["do"])

    def test_long_walking_legs_name_their_commands(self):
        cases = [wram(REC / "split-02.wram", at("VIRIDIAN_FOREST", 16, 40)),
                 wram(REC / "split-02.wram", at("ROUTE_2", 8, 60))]
        seen = 0
        for data in cases:
            for q in (None, "How do I get through the forest?", "Where is Viridian Forest?"):
                a, _ = ask(data, q)
                notes = [d for d in a["details"] if d.startswith("Long walks as commands (at most 6 presses each): ")]
                walk = " ".join([a["do"]] + [d for d in a["details"] if d not in notes])
                legs = [m for m in re.finditer(r"\b(up|down|left|right) (\d+) to \((-?\d+),(-?\d+)\)", walk)
                        if int(m.group(2)) > 6]
                self.assertEqual(len(notes), 1 if legs else 0, a["details"])
                for m in legs:
                    seen += 1
                    d, n = m.group(1), int(m.group(2))
                    got = re.search(rf"{d} {n} toward \({m.group(3)},{m.group(4)}\): ([^;.]*)", notes[0])
                    self.assertTrue(got, (m.group(0), notes[0]))
                    parts = got.group(1).split(" | ")
                    self.assertEqual(sum(int(x.split("*")[1]) if "*" in x else 1 for x in parts), n)
                    self.assertTrue(all(x.split("*")[0] == d and longest_run(x) <= 6 for x in parts), parts)
        self.assertGreater(seen, 0)

    def test_annotated_legs_keep_one_end_tile(self):
        data = wram(REC / "split-01.wram", merged(at("VIRIDIAN_CITY", 29, 20), bag(("OAKS_PARCEL", 1)),
                                                  ev(REC / "split-01.wram", "EVENT_BATTLED_RIVAL_IN_OAKS_LAB",
                                                     "EVENT_GOT_OAKS_PARCEL")))
        _, text = ask(data, "Where now?")
        self.assertNotRegex(text, r"to \(-?\d+,-?\d+\) to \(")
        self.assertEqual(A.with_coords(["down 6 to (29,26)", "jump down (over the ledge) to (29,28)", "down 2"], (29, 20)),
                         ["down 6 to (29,26)", "jump down (over the ledge) to (29,28)", "down 2 to (29,30)"])

    def test_long_button_lists_are_split(self):
        if BASELINE:
            import r13_advice as T
            self.assertEqual(T.presses("up 12 to (5,1)"), "up*6")
            return
        import r16_advice as X
        import r13_advice as T
        self.assertEqual(T.presses("up 12 to (5,1), right 3 to (8,1)"), "up*6")
        self.assertEqual(X.chunks("a right a down down down a"), ["a right a down down down", "a"])
        self.assertEqual(X.fit_text("Buttons: a right a down down down a (one command), then press A."),
                         "Buttons: a right a down down down (one command), then a (one command each), then press A.")
        self.assertEqual(X.fit_text("press a b up"), "press a b up")


# ---------- 6. one emulator smoke ----------

@unittest.skipUnless(os.environ.get("ARENA_EMULATOR_TESTS") == "1" and not BASELINE, "emulator smoke: one emulator only")
class Smoke(unittest.TestCase):
    def test_fresh_boot_and_a_few_presses_reach_the_title_menu(self):
        ram = settings.ROM_RAM
        self.assertFalse(ram.exists())
        rom_files = sorted(p.name for p in settings.ROM.parent.iterdir() if p.name.startswith(settings.ROM.stem + "."))
        rom_sha = hashlib.sha256(settings.ROM.read_bytes()).hexdigest()
        run = tmpdir(self)
        g = P.Game(run, fresh=True)
        try:
            g.tick(P.BOOT_FRAMES)
            self.assertTrue(P.in_intro(g.m))
            seen = []
            for _ in range(12):
                g.press("a")
                rows = P.screen_text(g.m)
                seen.append(rows)
                if "NEW GAME" in rows:
                    break
            self.assertIn("NEW GAME", seen[-1], seen)
            self.assertTrue(P.in_intro(g.m))
            self.assertEqual(B.fields(g.m), dict(bench_started=False, bench_milestones=[]))
        finally:
            g.close()
        self.assertTrue((run / "game.state").exists())
        self.assertFalse(ram.exists())
        self.assertEqual(sorted(p.name for p in settings.ROM.parent.iterdir() if p.name.startswith(settings.ROM.stem + ".")), rom_files)
        self.assertEqual(hashlib.sha256(settings.ROM.read_bytes()).hexdigest(), rom_sha)


if __name__ == "__main__":
    unittest.main()
