"""R17 (round b2): the six teacher fixes from the round b1 lessons.

Non-emulator by default: record WRAM fixtures moved to the b1 situations (Squirtle-only team as in b1), fake games
for a*. The emulator checks (saved record states, one emulator at a time, ram_file = empty 32 KB buffer) run only
with ARENA_EMULATOR_TESTS=1. Temporary folders are moved to REDAI_TRASH (default .trash/).
"""
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
OWN = HERE.parent
ROOT = OWN
sys.path[:0] = [str(OWN / "tools"), str(OWN / "arena")]
import settings  # noqa: E402
REC = settings.FixtureDir("record-1831000065-v3")
PARK = settings.TRASH / "r17-test-fixtures"
import read_state as R  # noqa: E402
import advise as A  # noqa: E402
import play as P  # noqa: E402
import r17_advice as X  # noqa: E402
import lean_player as LP  # noqa: E402

EMULATOR = os.environ.get("ARENA_EMULATOR_TESTS") == "1"


def park(path):
    path = Path(path)
    if path.exists():
        PARK.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(PARK / f"{path.name}-{uuid.uuid4().hex}"))


def tmpdir(case):
    d = Path(tempfile.mkdtemp(prefix="r17-"))
    case.addCleanup(park, d)
    return d


# ---------- fixtures: record WRAM moved to the b1 places ----------

def at(map_name, x, y):
    mid = next(i for i, n in R.MAPS.items() if n == map_name)
    return {R.A("wCurMap"): mid, R.A("wXCoord"): x, R.A("wYCoord"): y}


def tiles(rows):
    chars = {c: t for t, c in R.CHARS.items() if t >= 0x7F and len(c) == 1}
    out = {a: 0x7F for a in range(0xC3A0, 0xC3A0 + 360)}
    for r, text in rows:
        for c, ch in enumerate(text.ljust(20)[:20]):
            out[0xC3A0 + r * 20 + c] = 0xED if ch == ">" else chars.get(ch, 0x7F)
    return out


def squirtle(level=9, hp=29, mx=29, status="ok", pp=30):
    return [dict(species="SQUIRTLE", nickname="A", level=level, hp=hp, max_hp=mx, status=status, sleep_turns=0,
                 moves=[dict(move="TACKLE", pp=pp), dict(move="TAIL_WHIP", pp=30), dict(move="BUBBLE", pp=pp)],
                 stats={"atk": 4 + level, "def": 6 + level, "spd": 3 + level, "spc": 5 + level})]


def place(src, map_name, x, y, team=None, bag=None, money=None):
    """A free-walking teacher state (no text box) from a record split, moved to (map, x, y)."""
    data = bytearray((REC / f"{src}.wram").read_bytes())
    for a, v in at(map_name, x, y).items():
        data[a - 0xC000] = v
    s = P.teacher_state(R.state_from_wram(bytes(data)), R.Wram(bytes(data)))
    s = dict(s, teacher_screen=dict(rows=[], cursor=False), text_box=False)
    if team is not None:
        s["team"] = team
    if bag is not None:
        s["bag"] = [dict(item=k, count=v) for k, v in bag.items()]
    if money is not None:
        s["money"] = money
    return s


MENU = [(14, "         >FIGHT PkMn"), (16, "          ITEM  RUN")]


def battle(rows=None, wild=True, team=None, src="battle-002"):
    """Record battle-002 (Viridian Forest, SQUIRTLE vs WEEDLE L9) with the screen and battle kind patched."""
    data = bytearray((REC / f"{src}.wram").read_bytes())
    patch_ = dict(tiles(rows or []))
    if wild:
        patch_[R.A("wIsInBattle")] = 1
        patch_[R.A("wCurOpponent")] = data[R.A("wEnemyMonSpecies") - 0xC000]
        patch_[R.A("wCurEnemyLVL")] = data[R.A("wEnemyMonLevel") - 0xC000]
    for a, v in patch_.items():
        data[a - 0xC000] = v
    s = P.teacher_state(R.state_from_wram(bytes(data)), R.Wram(bytes(data)))
    if team is not None:
        s["team"] = team
    return s


LEG = re.compile(r"\b(up|down|left|right) (\d+) to \((-?\d+),(-?\d+)\)")
STEP = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def tiles_walked(text, start):
    """Every tile a 'down 1 to (4,4), left 3 to (1,4)' walk passes, checked against its own end points."""
    x, y = start
    out = []
    for d, n, ex, ey in LEG.findall(text):
        dx, dy = STEP[d]
        for _ in range(int(n)):
            x, y = x + dx, y + dy
            out.append((x, y))
        assert (x, y) == (int(ex), int(ey)), (text, (x, y), (ex, ey))
    return out


def ask(s, q=None, context=None):
    a = A.answer(s, q, context={} if context is None else context)
    return a, A.text(a)


def do_line(text):
    return text.splitlines()[0]


# ---------- 1. named routes in the text the player sees ----------

class Routes(unittest.TestCase):
    def test_b1_haiku_n558_gym_walk_next_to_the_center_is_not_a_heal(self):
        s = place("split-03", "PEWTER_CITY", 13, 26, squirtle())
        q = ("I'm at PEWTER_CITY (13,26) with Squirtle L9 at full HP, next to the Pokemon Center. I've decided to "
             "challenge Brock now. Give the exact walk to the PEWTER_GYM door by map coordinates.")
        a, text = ask(s, q, {"purpose": "train"})
        line = do_line(text)
        self.assertTrue(line.startswith("DO NOW: Go to PEWTER_GYM: its door is at (16,17)"), line)
        self.assertIn("stand at (16,18)", line)
        self.assertIn("The walk from (13,26):", line)
        self.assertIn("up 1 to (16,17) (into PEWTER_GYM)", line)
        self.assertIn("Inside, from (4,13), the checked left bypass to Brock", line)
        self.assertNotIn("To heal", line)
        self.assertEqual(tiles_walked(line.split("The walk from (13,26):")[1].split("Inside")[0], (13, 26))[-1], (16, 17))

    def test_b1_haiku_n591_n651_no_train_words_still_get_the_door(self):
        s = place("split-03", "PEWTER_CITY", 4, 9, squirtle())
        for q in ("I am in PEWTER_CITY at (4,9). Where is the PEWTER_GYM building door (Brock's gym) on the "
                  "PEWTER_CITY map? Give its coordinates and the walk from (4,9). Do not tell me to train.",
                  "Give the walk to the gym door. No training advice."):
            with self.subTest(q=q):
                a, text = ask(s, q, {"purpose": "train"})
                self.assertFalse(a["do"].startswith("Train first"), a["do"])
                self.assertIn("(16,17)", a["do"])
                self.assertIn("The walk from (4,9): down 9 to (4,18), right 12 to (16,18), up 1 to (16,17)", a["do"])

    def test_unready_gym_request_gives_the_walk_first_then_the_warning(self):
        s = place("split-03", "PEWTER_CITY", 4, 9, squirtle())          # L9: Brock check says L10
        a, _ = ask(s, "Where is the gym door?")
        self.assertTrue(a["do"].startswith("Go to PEWTER_GYM"))
        self.assertLess(a["do"].index("(16,17)"), a["do"].index("Not ready for Brock yet"))
        self.assertTrue(any(d.startswith("The way to the training grass") for d in a["details"]))

    def test_b1_luna_n594_leave_the_gym_never_crosses_the_trainer_row(self):
        for x, y in ((4, 3), (4, 2), (6, 4), (2, 5)):
            with self.subTest(at=(x, y)):
                s = place("split-03", "PEWTER_GYM", x, y, squirtle(10, 30, 30))
                a, text = ask(s, "How skip trainer and leave gym?", {"purpose": "train"})
                line = do_line(text)
                self.assertIn("(out the door to PEWTER_CITY)", line)
                walked = tiles_walked(line, (x, y))
                self.assertFalse(set(walked) & set(X.GYM_SIGHT), walked)
                self.assertEqual(walked[-1][1], 13)

    def test_heal_walk_inside_the_gym_avoids_the_trainer_row(self):
        s = place("split-03", "PEWTER_GYM", 4, 2, squirtle(10, 9, 30))
        a, _ = ask(s, "Where do I heal?")
        self.assertIn("(out the door to PEWTER_CITY)", a["do"])
        self.assertFalse(set(tiles_walked(a["do"], (4, 2))) & set(X.GYM_SIGHT))
        s["teacher_events"] = dict(s.get("teacher_events", {}), **{X.GYM_TRAINER: True})   # beaten: straight down is fine
        self.assertIs(X.gym_guard(s), s)

    def test_bypass_to_brock_from_the_entrance_and_the_talk_keys(self):
        s = place("split-03", "PEWTER_GYM", 4, 13, squirtle(11, 31, 31))
        a, text = ask(s, "How do I get past the trainer to Brock?")
        line = do_line(text)
        self.assertIn("checked left bypass to (4,2)", line)
        self.assertFalse(set(tiles_walked(line, (4, 13))) & set(X.GYM_SIGHT))
        self.assertIn("press up a a*", line)

    def test_forest_gates_get_their_walks(self):
        s = place("split-02", "ROUTE_2", 7, 70, squirtle(8, 16, 27))
        q = ("I'm on ROUTE_2 at (7,70) with Squirtle at 16/27 HP. Give the exact walk to the Viridian Forest south "
             "gate at (3,44), by map coordinates, through the tall grass without fighting if possible.")
        a, text = ask(s, q, {"purpose": "train"})
        self.assertIn("(3,43)", a["do"])
        self.assertIn("(into VIRIDIAN_FOREST_SOUTH_GATE)", do_line(text))
        self.assertNotIn("Train first", a["do"])
        s = place("split-02", "VIRIDIAN_FOREST", 16, 40, squirtle(8, 20, 27))
        a, text = ask(s, "Route to north gate?")
        self.assertIn("(out the door to VIRIDIAN_FOREST_NORTH_GATE)", do_line(text))
        self.assertEqual(tiles_walked(do_line(text), (16, 40))[-1], (1, 0))

    def test_fix_b1_explicit_south_exit_wins_over_exit_words(self):
        s = place("split-02", "VIRIDIAN_FOREST", 16, 40, squirtle(8, 20, 27))
        for q in ("Where is the south exit of Viridian Forest?",
                  "How do I leave the forest through the south gate back to Viridian City?"):
            with self.subTest(q=q):
                self.assertEqual(X.route_request(A, s, q), ("map", "VIRIDIAN_FOREST_SOUTH_GATE"))
                a, text = ask(s, q)
                self.assertIn("south exit is at (15-18,47)", a["do"])
                self.assertNotIn("(1,0)", do_line(text))
                walked = tiles_walked(do_line(text), (16, 40))
                self.assertEqual(walked[-1][1], 47)
                self.assertLess(len(walked), 15)
        self.assertEqual(X.route_request(A, s, "Where is the north exit to Pewter?"), ("map", "VIRIDIAN_FOREST_NORTH_GATE"))

    def test_training_questions_keep_the_training_answer(self):
        s = place("split-03", "PEWTER_CITY", 16, 18, squirtle())
        a, _ = ask(s, "How do I get to Route 2 grass to train before Brock?")
        self.assertEqual(a["kind"], "train")
        self.assertIsNone(X.route_request(A, s, "Where can I train before Brock?"))
        self.assertEqual(X.route_request(A, s, "Walk to the gym, do not tell me to train"), ("map", "PEWTER_GYM"))


# ---------- 2. no stale detours ----------

class Stale(unittest.TestCase):
    def test_b1_luna_n589_ready_at_full_hp_has_no_heal_first(self):
        s = place("split-03", "PEWTER_GYM", 4, 2, squirtle(10, 30, 30))
        a, text = ask(s, "Ready for Brock; what now?", {"purpose": "train"})
        self.assertNotIn("Heal first", do_line(text))
        self.assertNotIn("To heal", do_line(text))
        self.assertIn("face up and press A", a["do"])
        s["team"][0]["hp"] = 12                                            # really low: heal, then Brock
        a, _ = ask(s, "Ready for Brock; what now?")
        self.assertIn("heal", a["do"].lower())
        self.assertIn("12/30", a["do"])

    def test_ready_after_healing_needs_no_heal_at_full_hp(self):
        s = place("split-03", "VIRIDIAN_FOREST", 16, 40, squirtle(11, 31, 31))
        old = A._answer_core(s, None, 0, {"purpose": "train"})
        self.assertTrue(old["do"].startswith("Ready for Brock after healing"))
        a = A.answer(s, None, 0, {"purpose": "train"})
        self.assertIn("no heal needed", a["do"])
        self.assertFalse(any(d.startswith("Heal before the gym") for d in a["details"]))

    def test_heal_need_is_real_hp_status_pp(self):
        s = place("split-03", "PEWTER_CITY", 18, 30, squirtle(11, 31, 31))
        self.assertIsNone(X.heal_need(A, s, X.GYM_HEAL))
        s["team"][0]["hp"] = 24                                            # 77%: fine before Brock
        self.assertIsNone(X.heal_need(A, s, X.GYM_HEAL))
        s["team"][0]["hp"] = 22                                            # 71%: heal before Brock
        self.assertIn("22/31", X.heal_need(A, s, X.GYM_HEAL))
        s["team"][0].update(hp=31, status="poisoned")
        self.assertIn("poisoned", X.heal_need(A, s, X.GYM_HEAL))
        s["team"][0].update(status="ok", moves=[dict(m, pp=0) if m["move"] != "TAIL_WHIP" else m
                                                 for m in s["team"][0]["moves"]])
        self.assertIn("no attack PP", X.heal_need(A, s, X.GYM_HEAL))

    def test_fix_b2_empty_bubble_with_tackle_pp_is_not_ready_without_a_heal(self):
        s = place("split-03", "PEWTER_CITY", 16, 18, squirtle(11, 31, 31))
        s["team"][0]["moves"] = [dict(move="TACKLE", pp=35), dict(move="TAIL_WHIP", pp=30), dict(move="BUBBLE", pp=0)]
        self.assertTrue(X.brock_check(A, s)["ok"])                          # full-PP estimate: ready
        need = X.heal_need(A, s, X.GYM_HEAL)
        self.assertIn("BUBBLE 0 PP", need)
        a, text = ask(s, "Am I ready for Brock?")
        self.assertTrue(a["do"].split("Skip the optional trainer (checked left bypass). ")[-1].startswith("First heal ("),
                        a["do"])
        self.assertIn("BUBBLE 0 PP", do_line(text))
        s["team"][0]["moves"][2]["pp"] = 30                                  # refilled: no heal
        self.assertIsNone(X.heal_need(A, s, X.GYM_HEAL))
        self.assertNotIn("First heal", ask(s, "Am I ready for Brock?")[0]["do"])

    def test_readiness_is_brock_only(self):
        s = place("split-03", "ROUTE_2", 7, 40, squirtle(8, 25, 27))
        a, _ = ask(s, "Is my team ready for Brock?")
        self.assertTrue(a["do"].startswith("Not ready yet"))
        self.assertIn("Brock alone", a["do"])
        self.assertIn("about level 10", a["do"])                            # Brock only (not 13 for the gym trainer)
        s = place("split-03", "ROUTE_2", 7, 40, squirtle(11, 31, 31))
        self.assertTrue(X.brock_ready(A, s))
        self.assertFalse(A.gym1_check(s, keys=("JrTrainerM:1",))["ok"])    # optional trainer not required

    def test_explicit_route_drops_the_train_purpose(self):
        ctx = {"purpose": "train"}
        ask(place("split-03", "PEWTER_CITY", 4, 9, squirtle()), "Where is the gym door?", ctx)
        self.assertNotIn("purpose", ctx)


# ---------- 3. poison first, 4. heal on the earlier city visit ----------

class PoisonAndHeal(unittest.TestCase):
    def test_poisoned_with_antidote_cure_steps_come_first(self):
        s = place("split-02", "VIRIDIAN_FOREST", 16, 40, squirtle(8, 12, 27, "poisoned"),
                  bag={"POTION": 1, "ANTIDOTE": 1})
        a, text = ask(s, "Route to north gate?")
        self.assertTrue(a["do"].startswith("FIRST cure the poison"), a["do"])
        for w in ("start", "ITEM", "ANTIDOTE (item 2", "USE", "SQUIRTLE"):
            self.assertIn(w, a["do"])
        self.assertLess(a["do"].index("ANTIDOTE"), a["do"].index("(1,0)"))   # then the requested walk

    def test_poisoned_without_antidote_goes_to_the_center_first(self):
        s = place("split-02", "VIRIDIAN_FOREST", 16, 40, squirtle(8, 12, 27, "poisoned"), bag={"POTION": 1})
        a, _ = ask(s, "Route to north gate?")
        self.assertTrue(a["do"].startswith("FIRST cure the poison"))
        self.assertIn("Pokémon Center", a["do"])
        self.assertTrue(any("north exit" in d for d in a["details"]))       # the requested walk is kept, after

    def test_no_cure_line_in_battle(self):
        s = battle(MENU, team=squirtle(8, 12, 27, "poisoned"))
        self.assertIsNone(X.cure_line(A, s))

    def test_antidote_before_the_forest_leg(self):
        s = place("split-02", "VIRIDIAN_CITY", 20, 20, squirtle(8, 27, 27), bag={"POKE_BALL": 2}, money=500)
        a, text = ask(s)
        self.assertTrue(a["do"].startswith("Before the forest leg: buy 1-2 Antidotes"), a["do"])
        self.assertIn("(into VIRIDIAN_MART)", do_line(text))
        self.assertIn("Then: ", a["do"])
        s = place("split-02", "VIRIDIAN_CITY", 20, 20, squirtle(8, 27, 27), bag={"ANTIDOTE": 1}, money=500)
        self.assertNotIn("Antidotes", ask(s)[0]["do"])
        s = place("split-02", "VIRIDIAN_CITY", 20, 20, squirtle(8, 27, 27), bag={}, money=50)
        self.assertNotIn("Antidotes", ask(s)[0]["do"])                          # cannot pay
        s = place("split-01", "VIRIDIAN_CITY", 20, 20, squirtle(6, 22, 22), bag={}, money=500)
        self.assertIsNone(X.antidote_line(A, s))                                 # parcel trip: not yet

    def test_viridian_heals_before_the_forest_when_hp_is_low(self):
        s = place("split-02", "VIRIDIAN_CITY", 20, 20, squirtle(8, 9, 27), bag={"ANTIDOTE": 1})
        a, text = ask(s)
        self.assertTrue(a["do"].startswith("FIRST heal here, before the long forest leg"), a["do"])
        self.assertIn("9/27", a["do"])
        self.assertIn("(into the door)", do_line(text))
        s["team"][0]["hp"] = 19                                                 # 70%: no detour
        self.assertNotIn("FIRST heal", ask(s)[0]["do"])

    def test_pewter_heals_before_the_gym_when_hp_is_low(self):
        s = place("split-03", "PEWTER_CITY", 18, 30, squirtle(11, 15, 31))
        a, _ = ask(s, "what now?")
        self.assertTrue(a["do"].startswith("FIRST heal here, before Brock (SQUIRTLE has only 15/31 HP)"), a["do"])
        self.assertIn("(into the door)", a["do"])
        self.assertTrue(any(d.startswith("The way after that") for d in a["details"]))
        a, _ = ask(s, "Where is the gym door?")                               # asked for the gym: heal, then gym
        self.assertTrue(a["do"].startswith("First heal (SQUIRTLE has only 15/31 HP)"), a["do"])
        self.assertLess(a["do"].index("heal"), a["do"].index("Then the gym"))
        s["team"][0]["hp"] = 31
        a, text = ask(s, "what now?")
        self.assertNotIn("heal", do_line(text).lower().replace("no heal needed", ""))


# ---------- 5. menu-aware battle advice ----------

class Battle(unittest.TestCase):
    def test_wild_fight_when_brock_ready_gives_the_run_keys(self):
        a, _ = ask(battle(MENU, team=squirtle(12, 33, 33)))
        self.assertTrue(a["do"].startswith("Run from this wild WEEDLE L9"), a["do"])
        self.assertIn("Press: right down a (one command)", a["do"])
        self.assertTrue(a["details"][0].startswith("Battle plan if you stay"))
        moves = [(13, "     >TACKLE"), (14, "      TAIL WHIP"), (15, "      BUBBLE")]
        s = battle(moves, team=squirtle(12, 33, 33))
        if s["teacher_ui"]["phase"] == "moves":
            self.assertIn("b right down a", ask(s)[0]["do"])
        self.assertEqual(X.run_keys(dict(phase="commands", cursor=(15, 16))), "a")
        self.assertEqual(X.run_keys(dict(phase="commands", cursor=(9, 16))), "right a")

    def test_wild_fight_needing_experience_names_enemy_and_menu(self):
        a, _ = ask(battle(MENU), "what move?")
        self.assertNotIn("Run from", a["do"])
        self.assertIn("(Enemy: wild WEEDLE L9, 27/27 HP; the FIGHT / PKMN / ITEM / RUN menu shows.)", a["do"])
        self.assertIn("a* does it in one press slot", a["do"])

    def test_trainer_fight_never_runs(self):
        a, _ = ask(battle(MENU, wild=False, team=squirtle(12, 33, 33)))
        self.assertNotIn("Run from", a["do"])
        self.assertIn("Enemy: trainer WEEDLE", a["do"])

    def test_battle_start_names_the_enemy_and_offers_a_star(self):
        s = battle(MENU)
        s["battle"] = dict(s["battle"], yours=None)
        a, _ = ask(s)
        self.assertIn("Enemy: wild WEEDLE L9", a["do"])
        self.assertIn("a*", a["do"])

    def test_later_parts_keep_the_old_battle_answer(self):
        s = battle(MENU)
        s["story"] = dict(s["story"], next={"id": "mt_moon", "goal": "x", "part": 2})
        self.assertIs(X.battle_fix(A, s, dict(do="Use TACKLE.", why="", details=[])).get("do"), "Use TACKLE.")


# ---------- 6. a*: harness, lean loop, prompt, teacher text ----------

class FakeMem:
    def __init__(self):
        self.b = bytearray(0x10000)

    def __getitem__(self, k):
        if isinstance(k, slice):
            return list(self.b[k])
        return self.b[k]


class FakeGB:
    """Text pages: each A press (new press edge) shows the next page after `delay` frames of printing; after the
    last page the box closes. A filled cursor can appear after a page (a choice)."""

    def __init__(self, mem, pages, delay=20, choice_after=None, endless=False):
        self.m, self.pages, self.delay, self.choice_after, self.endless = mem, pages, delay, choice_after, endless
        self.page, self.frames_since, self.held, self.presses, self.unstable_presses = 0, 999, False, 0, 0
        self.show()

    def show(self):
        for i in range(0xC3A0, 0xC3A0 + 360):
            self.m.b[i] = 0x7F
        if self.page < len(self.pages) or self.endless:
            self.m.b[R.A("wFontLoaded")] |= 1
            full = self.pages[self.page % len(self.pages)]
            text = full[:self.frames_since * len(full) // self.delay]      # letters print one by one
            for t, line in tiles([(14, text)]).items():
                self.m.b[t] = line
            if self.choice_after is not None and self.page == self.choice_after and self.frames_since >= self.delay:
                self.m.b[0xC3A0 + 16 * 20 + 1] = 0xED
        elif getattr(self, "stale", False):
            self.m.b[R.A("wFontLoaded")] |= 1               # flag left set over a plain map
        else:
            self.m.b[R.A("wFontLoaded")] &= ~1

    def button_press(self, b):
        if b == "a" and not self.held:
            self.presses += 1
            if self.frames_since < self.delay:
                self.unstable_presses += 1
            self.page += 1
            self.frames_since = 0
        self.held = True

    def button_release(self, b):
        self.held = False

    def tick(self, n=1, render=True):
        self.frames_since += 1
        self.show()


def fake_game(pages, **kw):
    g = P.Game.__new__(P.Game)
    g.m = FakeMem()
    g.m.b[R.A("wCurMapWidth")] = 20                 # a map is loaded: not the intro
    g.gb = FakeGB(g.m, pages, **kw)
    g.map_transitions, g.transition_cause, g.run = [], None, None
    return g


class AStar(unittest.TestCase):
    def test_parse_counts_a_star_as_one_press(self):
        self.assertEqual(P.parse_buttons(["up", "a", "a*"]), ["up", "a", "a*"])
        self.assertEqual(P.parse_buttons(["A*", "b*5"]), ["a*"] + ["b"] * 5)
        with self.assertRaises(SystemExit):
            P.parse_buttons(["a*", "b*6"])
        with self.assertRaises(SystemExit):
            P.parse_buttons(["b*"])
        self.assertEqual(LP.parse_buttons("up a A*"), ["up", "a", "a*"])
        with self.assertRaises(LP.BadReply):
            LP.parse_buttons("a* a*3 a*3")

    def test_presses_through_pages_until_the_box_closes(self):
        g = fake_game(["PAGE ONE", "PAGE TWO", "PAGE THREE"])
        self.assertEqual(g.a_star(), 3)
        self.assertFalse(g.text_waits())
        self.assertEqual(g.gb.unstable_presses, 0)          # every A waited for stable text
        self.assertEqual(g.a_star(), 0)                     # closed: never talks to the same person again
        self.assertEqual(g.gb.presses, 3)

    def test_stops_at_a_choice_without_pressing_it(self):
        g = fake_game(["HEAL YOUR POKEMON", "YES NO", "AFTER"], choice_after=1)
        self.assertEqual(g.a_star(), 1)
        self.assertIn(0xED, g.m[0xC3A0:0xC3A0 + 360])
        self.assertEqual(g.gb.page, 1)

    def test_font_flag_without_words_never_presses(self):
        g = fake_game(["ONLY PAGE"])
        g.gb.page, g.gb.stale = 1, True
        g.gb.show()
        self.assertTrue(g.m[R.A("wFontLoaded")] & 1)         # stale flag, plain map on screen
        self.assertEqual(g.a_star(), 0)
        self.assertEqual(g.gb.presses, 0)

    def test_fix_b3_no_a_when_the_screen_never_settles(self):
        g = fake_game(["ONE PAGE"])
        frame = [0]
        real_tick = g.gb.tick

        def flicker(n=1, render=True):                       # the words change every frame: never stable
            real_tick(n, render)
            frame[0] += 1
            for t, v in tiles([(14, f"PAGE {frame[0]:06d}")]).items():
                g.m.b[t] = v
        g.gb.tick = flicker
        self.assertEqual(g.a_star(), 0)
        self.assertEqual(g.gb.presses, 0)

    def test_fix_b3_late_choice_after_a_slow_page_is_not_pressed(self):
        g = fake_game(["HEAL YOUR POKEMON YES NO"], choice_after=0)
        frame = [0]
        real_tick = g.gb.tick

        def slow(n=1, render=True):                          # busy screen past SETTLE_MAX, then the choice shows
            real_tick(n, render)
            frame[0] += 1
            if frame[0] < P.SETTLE_MAX + 60:
                g.m.b[0xC3A0 + 16 * 20 + 1] = 0x7F
                for t, v in tiles([(14, f"BUSY {frame[0]:06d}")]).items():
                    g.m.b[t] = v
        g.gb.tick = slow
        self.assertEqual(g.a_star(), 0)                      # settle timed out: stop, no A
        for _ in range(80):
            g.gb.tick()
        self.assertIn(0xED, g.m[0xC3A0:0xC3A0 + 360])        # the late choice is still unanswered
        self.assertEqual(g.gb.presses, 0)
        self.assertEqual(g.a_star(), 0)                      # and a second a* stops at it

    def test_hard_cap(self):
        g = fake_game(["AGAIN AND AGAIN"], endless=True)
        self.assertEqual(g.a_star(), P.A_STAR_CAP)

    def test_play_logs_the_a_star_count_and_teacher_still_runs(self):
        s = place("split-03", "PEWTER_CITY", 18, 30, squirtle(11, 31, 31))
        d = tmpdir(self)
        (d / "meta.json").write_text(json.dumps(dict(group="teacher", budget=100)), encoding="utf-8")
        (d / "log.jsonl").write_text(json.dumps({"n": 0, "cmd": "start", "map": "PEWTER_CITY", "done": []}) + "\n",
                                     encoding="utf-8")
        mem = R.Wram(bytes((REC / "split-03.wram").read_bytes()))
        p = s["place"]
        fake = SimpleNamespace(m=mem, where=lambda: (p["map_id"], p["x"], p["y"]), press=lambda _: None,
                               close=lambda save=True: None, map_transitions=[], a_star=lambda: 4)
        out = io.StringIO()
        with patch.object(P, "Game", return_value=fake), patch.object(P, "view", return_value=(dict(s), "VIEW")), \
                redirect_stdout(out):
            P.play(SimpleNamespace(cmd="press", rest=["a*", "up"]), d)
        row = [json.loads(l) for l in (d / "log.jsonl").read_text(encoding="utf-8").splitlines()][-1]
        self.assertEqual(row["a_star"], [4])
        self.assertEqual(row["keys"], ["a*", "up"])

    def test_prompt_explains_a_star_for_both_arms(self):
        for group in ("plain", "teacher"):
            text = LP.rules(group, 1000)
            self.assertIn("`a*` counts as one press", text)
        self.assertEqual(LP.rules("plain", 1000).count("a*"), LP.rules("teacher", 1000).count("a*"))

    def test_teacher_text_offers_a_star_only_for_plain_text(self):
        s = place("split-02", "VIRIDIAN_CITY", 20, 20, squirtle(8, 27, 27), bag={"ANTIDOTE": 1})
        s = dict(s, text_box=True, teacher_screen=dict(rows=["Hello there"], cursor=False))
        self.assertIn("a* (one press slot", ask(s)[0]["do"])
        s = dict(s, teacher_screen=dict(rows=["HEAL", "YES", "NO"], cursor=True))
        self.assertNotIn("a*", ask(s)[0]["do"])


# ---------- emulator checks (saved record states, one emulator at a time) ----------

@unittest.skipUnless(EMULATOR, "set ARENA_EMULATOR_TESTS=1 (one emulator)")
class Emulator(unittest.TestCase):
    def game_from(self, name):
        self.assertFalse(settings.ROM_RAM.exists())
        d = tmpdir(self)
        shutil.copyfile(REC / f"{name}.state", d / "game.state")
        return P.Game(d)

    def test_a_star_stops_at_the_battle_menu_without_choosing(self):
        g = self.game_from("battle-002")                    # Viridian Forest, WEEDLE's turn text on screen
        try:
            g.tick(120)
            n = g.a_star()
            rows = " ".join(P.screen_text(g.m))
            self.assertEqual(g.m[R.A("wIsInBattle")], 2)
            self.assertIn("FIGHT", rows)
            self.assertIn(0xED, g.m[0xC3A0:0xC3A0 + 360])
            self.assertTrue(0 < n < P.A_STAR_CAP, n)
            self.assertEqual(g.a_star(), 0)                 # a decision shows: nothing is pressed
            self.assertIn("FIGHT", " ".join(P.screen_text(g.m)))
            print(f"\n[emulator] battle text: a* pressed A {n} times, stopped at: {rows[:60]}")
        finally:
            g.close(save=False)
        self.assertFalse(settings.ROM_RAM.exists())

    def test_a_star_reads_brocks_long_talk_until_closed_and_never_talks_again(self):
        g = self.game_from("split-03")                      # PEWTER_GYM (4,2), Brock's after-battle talk
        try:
            g.tick(120)
            self.assertTrue(g.text_waits())
            n = g.a_star()
            self.assertFalse(g.text_waits())
            self.assertFalse(g.m[R.A("wFontLoaded")] & 1)
            self.assertTrue(0 < n < P.A_STAR_CAP, n)
            self.assertEqual(g.a_star(), 0)                 # closed box: A would talk to Brock again
            print(f"\n[emulator] Brock talk: a* pressed A {n} times, then 0 (closed box, no new talk)")
        finally:
            g.close(save=False)
        self.assertFalse(settings.ROM_RAM.exists())


if __name__ == "__main__":
    unittest.main()
