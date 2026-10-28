"""R18: the teacher as an always-on GUIDE.

Non-emulator: record WRAM fixtures moved to route places (as test_r17), screen rows patched for menus and battles,
fake games for play.py. Temporary folders are moved to REDAI_TRASH (default .trash/, never deleted).
"""
import io
import json
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
sys.path[:0] = [str(OWN / "tools"), str(OWN / "arena")]
import settings  # noqa: E402
REC = settings.FixtureDir("record-1831000065-v3")
PARK = settings.TRASH / "r18-test-fixtures"
import read_state as R  # noqa: E402
import advise as A  # noqa: E402
import walkable as W  # noqa: E402
import play as P  # noqa: E402
import r18_guide as G  # noqa: E402
import r18_replay as RP  # noqa: E402
import lean_player as LP  # noqa: E402


def park(path):
    path = Path(path)
    if path.exists():
        PARK.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(PARK / f"{path.name}-{uuid.uuid4().hex}"))


def tmpdir(case):
    d = Path(tempfile.mkdtemp(prefix="r18-"))
    case.addCleanup(park, d)
    return d


def tiles(rows):
    chars = {c: t for t, c in R.CHARS.items() if t >= 0x7F and len(c) == 1}
    out = {a: 0x7F for a in range(0xC3A0, 0xC3A0 + 360)}
    for r, text in rows:
        for c, ch in enumerate(text.ljust(20)[:20]):
            out[0xC3A0 + r * 20 + c] = 0xED if ch == ">" else chars.get(ch, 0x7F)
    return out


def screen(rows):
    """20x18 raw rows as r18_guide.raw_rows gives them."""
    out = [" " * 20 for _ in range(18)]
    for r, text in rows:
        out[r] = text.ljust(20)[:20]
    return out


def squirtle(level=11, hp=31, mx=31, status="ok", pp=30, bubble=True):
    moves = [dict(move="TACKLE", pp=pp), dict(move="TAIL_WHIP", pp=30)] + ([dict(move="BUBBLE", pp=pp)] if bubble else [])
    return [dict(species="SQUIRTLE", nickname="SQUIRTLE", level=level, hp=hp, max_hp=mx, status=status, sleep_turns=0,
                 moves=moves, stats={"atk": 4 + 2 * level, "def": 6 + 2 * level, "spd": 3 + 2 * level,
                                     "spc": 5 + 2 * level})]


def place(map_name, x, y, team=None, bag=None, money=3000, story=None, src="split-02", **extra):
    """A free-walking teacher state from a record split, moved to (map, x, y), with story/team/bag set."""
    data = bytearray((REC / f"{src}.wram").read_bytes())
    mid = next(i for i, n in R.MAPS.items() if n == map_name)
    for a, v in {R.A("wCurMap"): mid, R.A("wXCoord"): x, R.A("wYCoord"): y}.items():
        data[a - 0xC000] = v
    s = P.teacher_state(R.state_from_wram(bytes(data)), R.Wram(bytes(data)))
    s = dict(s, teacher_screen=dict(rows=[], cursor=False), text_box=False, money=money)
    s["team"] = squirtle() if team is None else team
    s["bag"] = [dict(item=k, count=v) for k, v in (bag or {}).items()]
    if story is not None:
        s["story"] = dict(s["story"], done=list(story))
    s["badges"] = []
    s.update(extra)
    return s


PRE = ["oak", "starter", "parcel", "pokedex"]
MENU = [(12, "+------------------+"), (14, "         >FIGHT PkMn"), (16, "          ITEM  RUN")]


def battle(rows, wild=True, team=None):
    """Record battle-002 (Viridian Forest, SQUIRTLE vs WEEDLE L9) with the screen patched."""
    data = bytearray((REC / "battle-002.wram").read_bytes())
    patch_ = dict(tiles(rows))
    if wild:
        patch_[R.A("wIsInBattle")] = 1
        patch_[R.A("wCurOpponent")] = data[R.A("wEnemyMonSpecies") - 0xC000]
        patch_[R.A("wCurEnemyLVL")] = data[R.A("wEnemyMonLevel") - 0xC000]
    for a, v in patch_.items():
        data[a - 0xC000] = v
    s = P.teacher_state(R.state_from_wram(bytes(data)), R.Wram(bytes(data)))
    if team is not None:
        s["team"] = team
    return s, G.raw_rows(R.Wram(bytes(data)))


def step(s, context=None, rows=None, bench=None, moving=False):
    return G.guide(s, context=context, rows=rows, bench=bench, moving=moving)


def go_keys(text):
    m = re.search(r"\b(?:GO|PRESS): ((?:(?:a\*|(?:up|down|left|right|a|b|start|select)(?:\*\d+)?) ?)+)", text)
    return m.group(1).split() if m else []


def walk_ok(s, keys):
    """Apply GO's first command on the map grid from the player's tile: every press must be a real move."""
    g = A._grid(s["place"]["map"])
    p = (s["place"]["x"], s["place"]["y"])
    for tok in keys:
        b, k = (tok.split("*")[0], int(tok.split("*")[1])) if "*" in tok and tok != "a*" else (tok, 1)
        if b not in W.STEP:
            return True
        for _ in range(k):
            q = dict(W.moves(g, p, people=False)).get(b)
            if q is None:
                edge = (p[1] == 0 and b == "up") or (p[0] == 0 and b == "left") or \
                       (p[1] == g["h"] - 1 and b == "down") or (p[0] == g["w"] - 1 and b == "right")
                if edge or any(w[:2] == (p[0] + W.STEP[b][0], p[1] + W.STEP[b][1]) for w in A._warps(s["place"]["map"])):
                    return True        # off the edge / into a door: the map changes here
                return False
            p = q
    return True


# ---------- 1. the route file ----------

class RouteFile(unittest.TestCase):
    def test_numbered_steps_power_on_to_brock(self):
        self.assertTrue(20 <= len(G.STEPS) <= 30, len(G.STEPS))
        self.assertEqual(len(set(G.IDS)), len(G.IDS))
        self.assertEqual(G.IDS[0], "new_game")
        self.assertEqual(G.IDS[-1], "brock")
        names = set(R.MAPS.values())
        for st in G.STEPS:
            self.assertIn(st["phase"], G.PHASES)
            self.assertLessEqual(len(st["objective"]), 130, st["id"])
            self.assertTrue(st["done"], st["id"])
            t = st.get("target", {})
            if "map" in t:
                self.assertIn(t["map"], names, st["id"])
        for _, maps in G.ROUTE["regions"]:
            for m in maps:
                self.assertIn(m.split("@")[0], names)

    def test_every_check_parses(self):
        s = place("VIRIDIAN_CITY", 23, 26, story=PRE)
        f = G.facts(s, [])
        for st in G.STEPS:
            G.check(st["done"], f, s, A)
            G.check(st.get("skip"), f, s, A)

    def test_phases_follow_the_story_flags(self):
        s = place("PALLET_TOWN", 10, 5, story=[])
        self.assertEqual(G.phase(G.facts(s)), "house")
        self.assertEqual(G.phase(G.facts(dict(s, story=dict(s["story"], done=["oak"]), team=[]))), "lab")
        s2 = place("ROUTE_1", 10, 10, story=["oak", "starter"], bag={"OAKS_PARCEL": 1})
        self.assertEqual(G.phase(G.facts(s2)), "deliver")
        self.assertEqual(G.phase(G.facts(place("ROUTE_1", 10, 10, story=PRE))), "brock")
        self.assertEqual(G.phase(G.facts(dict(place("PEWTER_CITY", 18, 30, story=PRE), badges=["Boulder"]))), "done")


# ---------- 2. done-checks and auto-advance along the route ----------

ROUTE_STATES = [
    # (map, x, y, story, bag, expected step)
    ("REDS_HOUSE_2F", 3, 6, [], {}, "room"),
    ("REDS_HOUSE_1F", 7, 1, [], {}, "house"),
    ("PALLET_TOWN", 5, 6, [], {}, "oak"),
    ("PALLET_TOWN", 10, 8, ["oak", "starter"], {}, "to_route1"),
    ("ROUTE_1", 10, 20, ["oak", "starter"], {}, "to_viridian"),
    ("VIRIDIAN_CITY", 23, 26, ["oak", "starter"], {}, "parcel"),
    ("VIRIDIAN_CITY", 29, 20, ["oak", "starter"], {"OAKS_PARCEL": 1}, "back_route1"),
    ("ROUTE_1", 10, 20, ["oak", "starter"], {"OAKS_PARCEL": 1}, "back_pallet"),
    ("PALLET_TOWN", 12, 13, ["oak", "starter"], {"OAKS_PARCEL": 1}, "lab_door"),
    ("OAKS_LAB", 5, 9, ["oak", "starter"], {"OAKS_PARCEL": 1}, "give_parcel"),
    ("OAKS_LAB", 5, 4, ["oak", "starter", "parcel"], {}, "pokedex"),
    ("PALLET_TOWN", 12, 13, PRE, {"ANTIDOTE": 1}, "north_route1"),
    ("ROUTE_1", 10, 20, PRE, {"ANTIDOTE": 1}, "north_viridian"),
    ("VIRIDIAN_CITY", 23, 26, PRE, {"ANTIDOTE": 1}, "to_route2"),
    ("ROUTE_2", 8, 60, PRE, {"ANTIDOTE": 1}, "forest_gate"),
    ("VIRIDIAN_FOREST_SOUTH_GATE", 4, 6, PRE, {"ANTIDOTE": 1}, "into_forest"),
    ("VIRIDIAN_FOREST", 17, 46, PRE, {"ANTIDOTE": 1}, "forest"),
    ("VIRIDIAN_FOREST_NORTH_GATE", 4, 6, PRE, {"ANTIDOTE": 1}, "north_gate"),
    ("ROUTE_2", 3, 9, PRE, {"ANTIDOTE": 1}, "to_pewter"),
    ("PEWTER_CITY", 18, 30, PRE, {"ANTIDOTE": 1}, "gym_door"),
    ("PEWTER_GYM", 4, 13, PRE, {"ANTIDOTE": 1}, "bypass"),
    ("PEWTER_GYM", 4, 2, PRE, {"ANTIDOTE": 1}, "brock"),
]


class DoneChecks(unittest.TestCase):
    def test_each_place_on_the_route_gets_its_step_and_steps_only_go_forward(self):
        last = 0
        for m, x, y, story, bag, want in ROUTE_STATES:
            s = place(m, x, y, story=story, bag=bag, team=squirtle() if story else [])
            g = step(s, context={})
            self.assertEqual(g["step"], want, (m, x, y, g["text"]))
            self.assertGreaterEqual(g["index"], last, (m, g["text"]))
            last = g["index"]
            self.assertTrue(g["text"].startswith(f"GUIDE STEP {g['index']}/{len(G.STEPS)}: "))
            self.assertLessEqual(len(g["text"]), G.MAX_CHARS)

    def test_intro_steps(self):
        s = place("PALLET_TOWN", 0, 0, story=[], team=[], intro=True, text_box=True)
        s["place"] = dict(s["place"], map_id=0)
        g = step(s, rows=screen([]))
        self.assertEqual(g["step"], "new_game")
        self.assertIn("PRESS: a a a a a a", g["text"])
        s["place"] = dict(s["place"], map_id=38)          # NEW GAME picked: Red's room is set before Oak talks
        g = step(s, rows=screen([]))
        self.assertEqual(g["step"], "names")
        self.assertIn("PRESS: a*", g["text"])               # never a row of A presses after NEW GAME
        names = screen([(1, "+----------+"), (2, ">NEW NAME"), (4, " RED"), (6, " ASH"), (8, " JACK"),
                        (12, "+------------------+"), (14, " Hmm.. what is your"), (16, " name?")])
        g = step(s, rows=names)
        self.assertIn("PRESS: down a", g["text"])           # one entry down = RED (rows 2 apart)
        self.assertIn("PRESS: a start", step(s, rows=screen([(3, "A B C D E F G H I")]))["text"])

    def test_auto_advance_when_the_done_check_passes(self):
        s = place("VIRIDIAN_CITY", 29, 20, story=["oak", "starter"])
        self.assertEqual(step(s)["step"], "parcel")
        s["bag"] = [dict(item="OAKS_PARCEL", count=1)]       # the Mart clerk gave it: next step at once
        self.assertEqual(step(s)["step"], "back_route1")
        self.assertEqual(step(s, bench=["got_parcel"])["step"], "back_route1")

    def test_conditional_steps(self):
        v = place("VIRIDIAN_CITY", 23, 26, story=PRE, bag={})
        self.assertEqual(step(v)["step"], "antidote")                 # no Antidote, money 3000
        self.assertEqual(step(dict(v, money=50))["step"], "to_route2")  # cannot pay: skipped
        hurt = place("VIRIDIAN_CITY", 23, 26, story=PRE, bag={"ANTIDOTE": 1}, team=squirtle(hp=15))
        self.assertEqual(step(hurt)["step"], "viridian_heal")
        # R19: the Pewter line is the worst-case Brock fight (tools/r19_ready.py): 20 HP for this L11 test mon
        p_hurt = place("PEWTER_CITY", 18, 30, story=PRE, bag={"ANTIDOTE": 1}, team=squirtle(hp=19))
        self.assertEqual(step(p_hurt)["step"], "pewter_heal")
        weak = place("PEWTER_CITY", 18, 30, story=PRE, bag={"ANTIDOTE": 1}, team=squirtle(level=6, hp=22, mx=22,
                                                                                         bubble=False))
        g = step(weak)
        self.assertEqual(g["step"], "train")
        self.assertIn("ROUTE_2 grass", g["text"])

    def test_training_in_the_grass_walks_a_circuit(self):
        weak = squirtle(level=6, hp=22, mx=22, bubble=False)
        tile = sorted(A.training_tiles())[0]
        s = place("ROUTE_2", tile[0], tile[1], story=PRE, bag={"ANTIDOTE": 1}, team=weak)
        g = step(s)
        self.assertEqual(g["step"], "train")
        keys = go_keys(g["text"])
        self.assertEqual(len(keys), 6)
        self.assertNotIn("look", g["text"])

    def test_starter_step(self):
        s = place("OAKS_LAB", 5, 6, story=["oak"], team=[])
        g = step(s)
        self.assertEqual(g["step"], "starter")
        self.assertIn("SQUIRTLE", g["text"])
        self.assertIn("(7,4)", g["text"])
        self.assertTrue(walk_ok(s, go_keys(g["text"])), g["text"])
        at = place("OAKS_LAB", 7, 4, story=["oak"], team=[])
        self.assertIn("PRESS: up a a*", step(at)["text"])
        near = place("OAKS_LAB", 7, 5, story=["oak"], team=[])
        self.assertIn("GO: up up a a*", step(near)["text"])            # walk + action in one command
        offer = dict(at, text_box=True)
        rows = screen([(12, "+------------------+"), (13, "So! You want the"), (14, "water POKéMON,"),
                       (15, "SQUIRTLE?"), (7, "+-----+"), (8, ">YES"), (10, " NO")])
        self.assertIn("PRESS: a a*", step(offer, rows=rows)["text"])
        rows_c = [r.replace("water POKéMON,", "fire POKéMON,").replace("SQUIRTLE?", "CHARMANDER?") for r in rows]
        self.assertIn("PRESS: b", step(offer, rows=rows_c)["text"])
        nick = screen([(13, "Do you want to give"), (14, "a NICKNAME to"), (8, ">YES"), (10, " NO")])
        self.assertIn("PRESS: b", step(dict(at, text_box=True, team=squirtle(5, 20, 20)), rows=nick)["text"])

    def test_smoke_n66_scrolled_starter_offer_gets_yes(self):
        at = place("OAKS_LAB", 7, 4, story=["oak"], team=[], text_box=True)
        rows = screen([(8, "               >YES"), (10, "                NO"), (14, " water POKéMON,"),
                       (16, " SQUIRTLE?")])                    # the real screen of smoke 1, n25-n90
        self.assertIn("PRESS: a a*", step(at, rows=rows)["text"])

    def test_scene_lets_time_pass(self):
        s = place("PALLET_TOWN", 10, 3, story=["oak"], team=[], teacher_scene=True)
        g = step(s)
        self.assertEqual(g["mode"], "text")
        self.assertIn("PRESS: b*6", g["text"])                 # smoke 2: a* moved Oak's escort one tile a command

    def test_rival_step_until_the_lab_flag(self):
        s = place("OAKS_LAB", 7, 4, story=["oak", "starter"], teacher_story=dict(rival_done=False, lab_script=None))
        g = step(s)
        self.assertEqual(g["step"], "rival")
        self.assertIn("row 6", g["text"])
        s["teacher_story"] = dict(rival_done=True, lab_script=None)
        self.assertEqual(step(s)["step"], "to_route1")


# ---------- 3. re-route and off-route recovery ----------

class Reroute(unittest.TestCase):
    def test_walking_back_moves_the_step_back_and_the_walk_starts_at_the_current_tile(self):
        ahead = place("ROUTE_2", 8, 60, story=PRE, bag={"ANTIDOTE": 1})
        back = place("VIRIDIAN_CITY", 20, 10, story=PRE, bag={"ANTIDOTE": 1})
        a, b = step(ahead), step(back)
        self.assertEqual(a["step"], "forest_gate")
        self.assertEqual(b["step"], "to_route2")
        for s, g in ((ahead, a), (back, b)):
            self.assertTrue(walk_ok(s, go_keys(g["text"])), g["text"])
        other = place("VIRIDIAN_CITY", 30, 26, story=PRE, bag={"ANTIDOTE": 1})
        self.assertNotEqual(go_keys(step(other)["text"]), go_keys(b["text"]))

    def test_full1_action_never_glued_to_a_walk_that_leaves_the_map(self):
        s = place("VIRIDIAN_MART", 3, 7, story=PRE, bag={"ANTIDOTE": 1}, team=squirtle(hp=15))
        g = step(s)
        self.assertEqual(g["step"], "viridian_heal")
        keys = go_keys(g["text"])
        self.assertEqual(keys, ["down"])                     # out the door only; no 'up' that walks back in
        self.assertIn("next map: VIRIDIAN_CITY", g["text"])
        city = place("VIRIDIAN_CITY", 23, 27, story=PRE, bag={"ANTIDOTE": 1}, team=squirtle(hp=15))
        self.assertNotIn("next map: VIRIDIAN_POKECENTER", step(city)["text"])   # the target itself is not repeated

    def test_off_route_map_gets_a_walk_back(self):
        s = place("ROUTE_22", 30, 8, story=PRE, bag={"ANTIDOTE": 1})
        g = step(s)
        self.assertEqual(g["step"], "to_route2")
        self.assertIn("GO: ", g["text"])
        self.assertTrue(walk_ok(s, go_keys(g["text"])))

    def test_no_progress_names_the_blocker_and_gives_a_new_walk(self):
        s = place("VIRIDIAN_CITY", 23, 26, story=PRE, bag={"ANTIDOTE": 1})
        ctx = {}
        first = step(s, context=ctx, moving=True)
        keys = go_keys(first["text"])
        d = keys[0].split("*")[0]
        tile = [23 + W.STEP[d][0], 26 + W.STEP[d][1]]
        texts = []
        for _ in range(G.STALL + 1):                 # pressing without getting closer
            ctx["walk_block"] = dict(map="VIRIDIAN_CITY", at=[23, 26], direction=d, tile=tile, count=1)
            texts.append(step(s, context=ctx, moving=True)["text"])
        hit = [t for t in texts if "NOT GETTING CLOSER" in t]
        self.assertTrue(hit, texts[-1])
        self.assertIn(str(tuple(tile)), hit[0])
        self.assertIn(["VIRIDIAN_CITY", tile], ctx["guide"]["avoid"])
        new = go_keys(hit[0])
        self.assertNotEqual(new[0].split("*")[0] if new else None, d)   # the fresh walk avoids that tile
        self.assertLessEqual(len(hit[0]), G.MAX_CHARS)

    def test_look_commands_do_not_count_as_stalling(self):
        s = place("VIRIDIAN_CITY", 23, 26, story=PRE, bag={"ANTIDOTE": 1})
        ctx = {}
        for _ in range(G.STALL + 3):
            g = step(s, context=ctx, moving=False)
        self.assertNotIn("NOT GETTING CLOSER", g["text"])

    def test_gym_walk_avoids_the_trainer_row(self):
        s = place("PEWTER_GYM", 5, 10, story=PRE, bag={"ANTIDOTE": 1})
        g = step(s)
        self.assertEqual(g["step"], "bypass")
        w = G.walk(G.STEPS[G.IDS.index("bypass")], s, A, None)
        x, y = 5, 10
        for d in w[0]:
            x, y = x + W.STEP[d][0], y + W.STEP[d][1]
            self.assertNotIn((x, y), [(c, 6) for c in range(3, 9)])
        self.assertEqual((x, y), (4, 2))
        row6 = place("PEWTER_GYM", 5, 6, story=PRE, bag={"ANTIDOTE": 1})
        self.assertIn("sight row", step(row6)["text"])


# ---------- 4. battle: the current menu and the right keys, never stale ----------

class Battle(unittest.TestCase):
    def test_menu_and_keys_follow_the_live_cursor(self):
        weak = squirtle(level=6, hp=22, mx=22, bubble=False)       # one Pokémon: no switch advice
        s, rows = battle(MENU, team=weak)
        g = step(s, rows=rows)
        self.assertEqual(g["mode"], "battle")
        self.assertIn("FIGHT/PKMN/ITEM/RUN menu shows", g["text"])
        self.assertIn("WEEDLE", g["text"])
        keys = go_keys(g["text"])
        self.assertEqual(keys[0], "a")                       # arrow already on FIGHT
        self.assertEqual(keys[-2:], ["a", "a*"])
        self.assertIn("Use TACKLE", g["text"])
        moved, rows2 = battle([(12, "+------------------+"), (14, "          FIGHT PkMn"),
                               (16, "          ITEM >RUN")], team=weak)
        k2 = go_keys(step(moved, rows=rows2)["text"])
        self.assertEqual(k2[:3], ["left", "up", "a"])        # same fight, arrow on RUN: back to FIGHT first

    def test_text_in_battle_is_a_star_never_wait(self):
        s, rows = battle([(12, "+------------------+"), (14, "Wild WEEDLE"), (16, "appeared!")])
        g = step(s, rows=rows)
        self.assertIn("PRESS: a*", g["text"])
        self.assertNotIn("Wait until", g["text"])

    def test_menu_text_is_never_the_stale_wait_line(self):
        s, rows = battle(MENU)
        self.assertNotIn("Wait", step(s, rows=rows)["text"])

    def test_ready_team_runs_from_wild_fights(self):
        s, rows = battle(MENU)
        with patch.object(G, "brock_ready", return_value=True):
            g = step(s, rows=rows)
        self.assertIn("RUN", g["text"])
        self.assertIn("PRESS: right down a a*", g["text"])

    def test_smoke3_menu_with_unknown_enemy_never_loops_on_a_star(self):
        weak = squirtle(level=6, hp=22, mx=22, bubble=False)
        s, rows = battle(MENU, team=weak)
        s = dict(s, battle=dict(s["battle"], enemy=None))
        g = step(s, rows=rows)
        self.assertNotIn("PRESS: a*", g["text"])
        self.assertEqual(go_keys(g["text"])[-2:], ["a", "a*"])     # FIGHT + an attack, then read on

    def test_smoke3_wild_enemy_read_when_the_menu_shows(self):
        data = bytearray((REC / "battle-002.wram").read_bytes())
        for a, v in tiles(MENU).items():
            data[a - 0xC000] = v
        data[R.A("wIsInBattle") - 0xC000] = 1
        data[R.A("wCurOpponent") - 0xC000] = 0                   # what the real game showed (smoke 3 n49)
        data[R.A("wCurEnemyLVL") - 0xC000] = data[R.A("wEnemyMonLevel") - 0xC000]
        m = R.Wram(bytes(data))
        s = P.teacher_state(R.state_from_wram(bytes(data)), m)
        self.assertIsNone(s["battle"]["enemy"])                  # read_state stays strict
        g = P.guide_block(s, m, {}, {"bench_milestones": []}, True)
        self.assertIn("WEEDLE", g["text"])
        self.assertNotIn("PRESS: a*", g["text"])

    def test_move_list_keys_from_its_arrow(self):
        me = None
        s, rows = battle([(12, "+------------------+")])
        me = s["battle"]["yours"]
        names = [m["move"] for m in me["moves"]]
        ui = dict(phase="moves", cursor=0)
        keys = G.move_keys(ui, me, names[-1])
        self.assertEqual(keys.split()[-2:], ["a", "a*"])
        self.assertEqual(keys.split().count("down"), len(names) - 1)
        ui2 = dict(phase="commands", cursor=(15, 16), move_index=len(names) - 1)
        k = G.move_keys(ui2, me, names[0]).split()
        self.assertEqual(k[:3], ["left", "up", "a"])
        self.assertEqual(k.count("up"), 1 + len(names) - 1)


# ---------- 5. text and menus, length cap ----------

class Screens(unittest.TestCase):
    def test_plain_text_gets_a_star(self):
        s = place("VIRIDIAN_CITY", 23, 26, story=PRE, bag={"ANTIDOTE": 1}, text_box=True)
        g = step(s, rows=screen([(12, "+------------------+"), (14, "I'm too sleepy")]))
        self.assertEqual(g["mode"], "text")
        self.assertIn("PRESS: a*", g["text"])

    def test_nurse_and_start_menu(self):
        s = place("PEWTER_POKECENTER", 3, 3, story=PRE, text_box=True)
        rows = screen([(6, ">HEAL"), (8, " CANCEL")])
        self.assertIn("PRESS: a a*", step(s, rows=rows)["text"])
        rows2 = screen([(6, " HEAL"), (8, ">CANCEL")])
        self.assertIn("PRESS: up a a*", step(s, rows=rows2)["text"])
        start = screen([(2, "         >POKéDEX"), (4, "          POKéMON"), (6, "          ITEM"),
                        (8, "          RED"), (10, "          SAVE"), (12, "          OPTION"), (14, "          EXIT")])
        self.assertIn("PRESS: b", step(s, rows=start)["text"])
        sick = place("VIRIDIAN_FOREST", 17, 30, story=PRE, bag={"ANTIDOTE": 1}, team=squirtle(status="poisoned"),
                     text_box=True)
        self.assertIn("PRESS: down*2 a", step(sick, rows=start)["text"])
        free_sick = dict(sick, text_box=False)
        g = step(free_sick)
        self.assertEqual(g["mode"], "cure")
        self.assertIn("PRESS: start", g["text"])

    def test_mart_buys_one_antidote(self):
        s = place("VIRIDIAN_MART", 2, 5, story=PRE, bag={}, text_box=True)
        self.assertEqual(step(s)["step"], "antidote")
        menu = screen([(0, ">BUY"), (2, " SELL"), (4, " QUIT")])
        self.assertIn("PRESS: a", step(s, rows=menu)["text"])
        lst = screen([(2, "+---------------+"), (3, " >POKé BALL"), (5, "  ANTIDOTE"), (7, "  PARLYZ HEAL")])
        self.assertIn("PRESS: down a", step(s, rows=lst)["text"])
        ok = screen([(1, " ▷BUY"), (4, "      POKé BALL"), (6, "     ▷ANTIDOTE"), (8, "      PARLYZ H >YES"),
                     (10, "      B ×01     NO"), (14, " That will be"), (16, " ¥100. OK?")])
        self.assertIn("PRESS: a", step(s, rows=ok)["text"])               # smoke 4: confirm, not "pick ANTIDOTE"
        wrong = [r.replace("     ▷ANTIDOTE", "      ANTIDOTE").replace("      PARLYZ H", "     ▷PARLYZ H") for r in ok]
        self.assertIn("PRESS: b", step(s, rows=wrong)["text"])            # the wrong item: NO
        done = dict(s, bag=[dict(item="ANTIDOTE", count=1)])
        self.assertIn("PRESS: down*2 a", step(done, rows=menu)["text"])     # bought: QUIT

    def test_length_cap(self):
        texts = [step(place(m, x, y, story=st, bag=b, team=squirtle() if st else []))["text"]
                 for m, x, y, st, b, _ in ROUTE_STATES]
        s, rows = battle(MENU)
        texts.append(step(s, rows=rows)["text"])
        for t in texts:
            self.assertLessEqual(len(t), G.MAX_CHARS, t)
        long = G._fit("GUIDE STEP 1/30: " + "x" * 300, " GO: up*6 | " + "left*6 | " * 20, " THEN: more")
        self.assertLessEqual(len(long), G.MAX_CHARS)
        self.assertTrue(long.endswith("..."))

    def test_runs_fit_six_presses(self):
        cmds = G.runs(["up"] * 14 + ["left"] * 2)
        self.assertEqual(cmds, ["up*6", "up*6", "up*2 left*2"])
        for c in cmds:
            self.assertLessEqual(G.slots(c), 6)


# ---------- 6. play.py and the lean loop ----------

def fake_game(s, src="split-02"):
    mem = R.Wram(bytes((REC / f"{src}.wram").read_bytes()))
    p = s["place"]
    return SimpleNamespace(m=mem, where=lambda: (p["map_id"], p["x"], p["y"]), press=lambda _: None,
                           close=lambda save=True: None, map_transitions=[], a_star=lambda: 0)


class Harness(unittest.TestCase):
    def run_press(self, meta, s):
        d = tmpdir(self)
        (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (d / "log.jsonl").write_text(json.dumps({"n": 0, "cmd": "start", "map": s["place"]["map"], "done": []}) + "\n",
                                     encoding="utf-8")
        out = io.StringIO()
        with patch.object(P, "Game", return_value=fake_game(s)), \
                patch.object(P, "view", return_value=(dict(s), "Place: VIEW")), redirect_stdout(out):
            P.play(SimpleNamespace(cmd="press", rest=["up"]), d)
        row = [json.loads(l) for l in (d / "log.jsonl").read_text(encoding="utf-8").splitlines()][-1]
        return out.getvalue(), row

    def test_guided_view_starts_with_the_guide_and_logs_the_step(self):
        s = place("VIRIDIAN_CITY", 23, 26, story=PRE, bag={"ANTIDOTE": 1})
        out, row = self.run_press(dict(group="teacher", budget=100, guide=True), s)
        self.assertTrue(out.startswith("GUIDE STEP "), out[:200])
        self.assertLess(out.index("GUIDE STEP"), out.index("Place: VIEW"))
        self.assertNotIn("TEACHER (", out)                    # old automatic notes are off in guided runs
        self.assertIn("guide", row)
        self.assertEqual(set(row["guide"]), {"step", "index", "mode"})
        self.assertTrue(row["guide_text"].startswith("GUIDE STEP"))
        self.assertIn("guide", row["teacher_context"])

    def test_unguided_runs_are_unchanged(self):
        s = place("VIRIDIAN_CITY", 23, 26, story=PRE, bag={"ANTIDOTE": 1})
        for meta in (dict(group="teacher", budget=100), dict(group="plain", budget=100)):
            out, row = self.run_press(meta, s)
            self.assertNotIn("GUIDE", out)
            self.assertNotIn("guide", row)

    def test_guide_needs_the_teacher_group(self):
        with patch.object(sys, "argv", ["play.py", "start", "r18-x-" + uuid.uuid4().hex[:6], "--group", "plain",
                                        "--guide"]), \
                patch.object(P, "ARENA", tmpdir(self)), self.assertRaises(SystemExit) as e:
            P.main()
        self.assertIn("--guide needs --group teacher", str(e.exception))

    def test_lean_start_asks_for_the_guide_only_in_the_teacher_arm(self):
        seen = []

        def fake_run(args, **kw):
            seen.append(args)
            return SimpleNamespace(returncode=0, stdout="Place: x\nCommands used: 0 of 10\n", stderr="")
        runs = tmpdir(self)
        for group in ("teacher", "plain"):
            (runs / f"g-{group}").mkdir()
            with patch.object(LP.subprocess, "run", side_effect=fake_run):
                LP.start_run(f"g-{group}", "haiku", group, 10, "py", "play", runs)
        self.assertIn("--guide", seen[0])
        self.assertNotIn("--guide", seen[1])

    def test_prompt_explains_the_guide_to_the_teacher_arm_only(self):
        teacher, plain = LP.rules("teacher", 1000), LP.rules("plain", 1000)
        self.assertIn("GUIDE", teacher)
        self.assertNotIn("GUIDE", plain)
        self.assertEqual(teacher.count("a*"), plain.count("a*"))


# ---------- 8. Sol R18 fix round ----------

def lean_ok(case, text):
    """The PRESS/GO keys of a guide text pass the real lean parser as one press command."""
    keys = go_keys(text)
    case.assertTrue(keys, text)
    args, _ = LP.parse_reply(json.dumps({"command": "press", "buttons": " ".join(keys), "notes": "n"}), "teacher")
    case.assertEqual(args[0], "press")
    return keys


class SolFix(unittest.TestCase):
    def test_b1_every_battle_cursor_and_move_index_fits_one_command(self):
        weak = squirtle(level=11, hp=31, mx=31)            # TACKLE / TAIL_WHIP / BUBBLE
        s, rows = battle(MENU, team=weak)
        me = s["battle"]["yours"]
        moves = [m["move"] for m in me["moves"]]
        seen = 0
        for cursor in [(9, 14), (15, 14), (9, 16), (15, 16)]:
            for idx in range(len(moves)):
                for target in moves:
                    ui = dict(phase="commands", cursor=cursor, move_index=idx)
                    keys = G.fit_keys(G.move_keys(ui, me, target))
                    LP.parse_buttons(keys)                   # raises BadReply above 6 presses
                    self.assertLessEqual(G.slots(keys), 6)
                    self.assertIn(keys.split()[-1], ("a", "a*"))  # a chunk ends on a selection
                    seen += 1
        for cur in range(len(moves)):
            for target in moves:
                LP.parse_buttons(G.fit_keys(G.move_keys(dict(phase="moves", cursor=cur), me, target)))
        self.assertGreater(seen, 0)

    def test_b1_sol_case_run_cursor_index_0_bubble(self):
        me = dict(moves=[dict(move="TACKLE", pp=35), dict(move="TAIL_WHIP", pp=30), dict(move="BUBBLE", pp=30)])
        raw = G.move_keys(dict(phase="commands", cursor=(15, 16), move_index=0), me, "BUBBLE")
        self.assertEqual(raw, "left up a down down a a*")             # 7 slots: Sol's reproduction
        self.assertEqual(G.fit_keys(raw), "left up a down down a")    # the valid chunk; a* comes next turn
        self.assertEqual(G.fit_keys("left up a up up up a a*"), "left up a")

    def test_b1_guide_texts_pass_the_lean_parser(self):
        weak = squirtle(level=11, hp=31, mx=31)
        for rows in (MENU, [(12, "+------------------+"), (14, "          FIGHT PkMn"), (16, "          ITEM >RUN")]):
            s, raw = battle(rows, team=weak)
            lean_ok(self, step(s, rows=raw)["text"])
        for m, x, y, st, b, _ in ROUTE_STATES:
            g = step(place(m, x, y, story=st, bag=b, team=squirtle() if st else []))
            if "GO:" in g["text"] or "PRESS:" in g["text"]:
                lean_ok(self, g["text"])

    def test_b2_injured_in_the_gym_heals_first_and_walks_out_safely(self):
        hurt = place("PEWTER_GYM", 4, 2, story=PRE, bag={"ANTIDOTE": 1}, team=squirtle(hp=1))
        g = step(hurt)
        self.assertEqual(g["step"], "pewter_heal")
        self.assertNotIn("PRESS: up a a*", g["text"])               # not "talk to Brock" at 1/31 HP
        w = G.walk(G.STEPS[G.IDS.index("pewter_heal")], hurt, A, None)
        x, y = 4, 2
        for d in w[0]:
            x, y = x + W.STEP[d][0], y + W.STEP[d][1]
            self.assertNotIn((x, y), [(c, 6) for c in range(3, 9)])     # never through the trainer's row
        full = place("PEWTER_GYM", 4, 2, story=PRE, bag={"ANTIDOTE": 1}, team=squirtle(hp=31))
        self.assertIn("PRESS: up a a*", step(full)["text"])

    def test_minor_unknown_enemy_bag_menu_gets_b(self):
        s, rows = battle([(4, "     >POTION"), (6, "      CANCEL")])
        ui = dict(s.get("teacher_ui") or {}, phase="items", cursor=0)
        s = dict(s, teacher_ui=ui, battle=dict(s["battle"], enemy=None))
        self.assertIn("PRESS: b", step(s, rows=rows)["text"])

    def test_minor_guided_ask_logs_the_guide(self):
        s = place("VIRIDIAN_CITY", 23, 26, story=PRE, bag={"ANTIDOTE": 1})
        d = tmpdir(self)
        (d / "meta.json").write_text(json.dumps(dict(group="teacher", budget=100, guide=True)), encoding="utf-8")
        (d / "log.jsonl").write_text(json.dumps({"n": 0, "cmd": "start", "map": "VIRIDIAN_CITY", "done": []}) + "\n",
                                     encoding="utf-8")
        mem = R.Wram(bytes((REC / "split-02.wram").read_bytes()))
        fake = SimpleNamespace(m=mem, gb=None, close=lambda save=True: None)
        out = io.StringIO()
        with patch.object(P, "Game", return_value=fake), patch.object(P.R, "state_from_pyboy", return_value=dict(s)), \
                redirect_stdout(out):
            P.play(SimpleNamespace(cmd="ask", rest=["where", "now?"]), d)
        row = [json.loads(l) for l in (d / "log.jsonl").read_text(encoding="utf-8").splitlines()][-1]
        self.assertEqual(row["cmd"], "ask")
        self.assertEqual(row["guide"]["step"], "to_route2")
        self.assertTrue(row["guide_text"].startswith("GUIDE STEP"))
        self.assertNotIn("GUIDE STEP", out.getvalue())        # the answer is printed as before


# ---------- 7. replay over logged rows (no emulator) ----------

class Replay(unittest.TestCase):
    def test_replay_on_a_synthetic_log(self):
        d = tmpdir(self)
        rows = [dict(n=0, cmd="start", map="PALLET_TOWN", map_id=0, done=[], intro=True, bench_milestones=[]),
                dict(n=1, cmd="press", map="REDS_HOUSE_2F", map_id=38, x=3, y=6, done=[], intro=False,
                     bench_milestones=[]),
                dict(n=2, cmd="press", map="PALLET_TOWN", map_id=0, x=5, y=6, done=[], intro=False,
                     bench_milestones=["left_house"]),
                dict(n=3, cmd="ask", map="PALLET_TOWN", done=[]),
                dict(n=4, cmd="press", map="OAKS_LAB", map_id=40, x=5, y=6, done=["oak", "starter"],
                     bench_milestones=["left_house", "got_starter"]),
                dict(n=5, cmd="press", map="ROUTE_1", map_id=12, x=10, y=30, done=["oak", "starter"],
                     bench_milestones=["left_house", "got_starter", "route_1"]),
                dict(n=6, cmd="press", map="REDS_HOUSE_1F", map_id=37, x=3, y=6, done=["oak", "starter"],
                     bench_milestones=["left_house", "got_starter", "route_1"])]
        (d / "log.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        out = RP.replay(d)
        self.assertEqual([r["step"] for r in out], ["new_game", "room", "oak", "rival", "to_viridian", "to_route1"])
        sm = RP.summary("synthetic", out)
        self.assertEqual(sm["back_steps"], 1)
        self.assertEqual(sm["walk_with_go"], sm["walk_rows"])


if __name__ == "__main__":
    unittest.main()
