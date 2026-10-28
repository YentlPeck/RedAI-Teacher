"""R19: stricter Brock readiness in the guide.

Non-emulator. Situations from round b3 (b3-1 Haiku lost its first Brock fight at L9 23/29 HP; b3-2 Luna won at
L9 28/28). Squirtle stats here are the game's formula with average DVs (8) unless a test says otherwise.
"""
import copy
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
OWN = HERE.parent
sys.path[:0] = [str(OWN / "tools"), str(OWN / "arena"), str(HERE)]
import advise as A  # noqa: E402
import r17_advice as X  # noqa: E402
import r18_guide as G  # noqa: E402
import r19_ready as Y  # noqa: E402
import lean_player as LP  # noqa: E402
import test_r18 as T  # noqa: E402

BASE = A.SPECIES["SQUIRTLE"]["base"]


def calc(b, level, dv, hp=False):
    return (b + dv) * 2 * level // 100 + (level + 10 if hp else 5)


def sq(level=9, hp=None, dv=8, bubble_pp=30, tackle_pp=35, spc_dv=None):
    mx = calc(BASE["hp"], level, dv, True)
    stats = {k: calc(BASE[k], level, dv) for k in ("atk", "def", "spd", "spc")}
    if spc_dv is not None:
        stats["spc"] = calc(BASE["spc"], level, spc_dv)
    return dict(species="SQUIRTLE", nickname="SQUIRTLE", level=level, hp=mx if hp is None else hp, max_hp=mx,
                status="ok", sleep_turns=0, stats=stats,
                moves=[dict(move="TACKLE", pp=tackle_pp), dict(move="TAIL_WHIP", pp=30), dict(move="BUBBLE", pp=bubble_pp)])


def at(map_name, x, y, mon, bag=None):
    return T.place(map_name, x, y, story=T.PRE, bag=bag or {"ANTIDOTE": 1}, team=[mon])


def brock_battle(mon, foe_index=0, foe_hp=None, phase="commands", cursor=(9, 14), move_index=0, bag=None):
    """Brock's fight at (4,2) in PEWTER_GYM: the record battle state with Brock's Pokémon and our Squirtle."""
    s, _ = T.battle(T.MENU)
    s = copy.deepcopy(s)
    e = A.TEAMS["Brock:1"]["party"][foe_index]
    foe = dict(A._foe(e), sleep_turns=0, flags=[], moves=[dict(move=m, pp=10) for m in e["moves"]])
    if foe_hp is not None:
        foe["hp"] = foe_hp
    me = dict(A._party_mon(mon), sleep_turns=0, flags=[])
    s["battle"] = dict(kind="trainer", enemy=foe, yours=me)
    s["team"] = [mon]
    s["bag"] = [dict(item=k, count=v) for k, v in (bag or {"ANTIDOTE": 1}).items()]
    s["place"] = dict(s["place"], map="PEWTER_GYM", x=4, y=2)
    s["badges"] = []
    s["story"] = dict(s["story"], done=list(T.PRE))
    s["teacher_ui"] = dict(s["teacher_ui"], phase=phase, cursor=cursor, move_index=move_index)
    return s


# ---------- 1. the real cause of b3-1 ----------

class Cause(unittest.TestCase):
    def test_b3_1_passed_the_old_three_quarter_line(self):
        """23/29 = 79% >= 75%: the R18 rule (r17 GYM_HEAL guess) saw no heal; the worst case says heal."""
        s = at("PEWTER_CITY", 16, 18, sq(9, hp=23))
        self.assertEqual(s["team"][0]["max_hp"], 28)          # DV 8; Haiku's mon had 29 (one DV point more)
        s29 = at("PEWTER_CITY", 16, 18, dict(sq(9, hp=23), max_hp=29))
        self.assertIsNone(X.heal_need(A, s29, X.GYM_HEAL))    # old line: no heal
        self.assertTrue(X.brock_ready(A, s29))                # old average check: ready
        self.assertIsNotNone(Y.heal_reason(A, s29))           # new line: heal
        self.assertEqual(G.guide(s29)["step"], "pewter_heal")

    def test_b3_1_brock_keys_from_the_guide_were_bubble_every_turn(self):
        """b3-1 n298-n303 (lean.jsonl): the guide's keys always reached BUBBLE; Haiku repeated 'a down down a a*'.
        The move list opens on the last move used and wraps (3 moves): replaying both key lists on that model gives
        the moves the logged PP drops show (n299 BUBBLE 20->19, n300 TAIL_WHIP 29->28, n301 TACKLE 34->33,
        n302 BUBBLE 19->18, n303 TAIL_WHIP 28->27, n304 TACKLE -> blackout)."""
        names = ["TACKLE", "TAIL_WHIP", "BUBBLE"]
        guide_keys = ["a down down a a*", "a a a*", "a down a a*", "a down down a a*", "a a a*", "a down a a*"]
        haiku_keys = ["a down down a a*"] * 6
        logged = ["BUBBLE", "TAIL_WHIP", "TACKLE", "BUBBLE", "TAIL_WHIP", "TACKLE"]

        def used(keys_list):
            cur, out = 0, []
            for i, keys in enumerate(keys_list):
                if keys_list is guide_keys:
                    cur = names.index(logged[i - 1]) if i else 0     # where Haiku's real presses left the arrow
                ks = keys.split()[1:]                               # after FIGHT
                for k in ks:
                    if k == "down":
                        cur = (cur + 1) % 3
                    elif k == "up":
                        cur = (cur - 1) % 3
                    elif k == "a":
                        out.append(names[cur])
                        break
            return out
        self.assertEqual(used(haiku_keys), logged)
        self.assertEqual(used(guide_keys), ["BUBBLE"] * 6)
        # and dev-r23 builds the same keys from each of those arrow positions
        for i, start in enumerate([0] + [names.index(m) for m in logged[:-1]]):
            s = brock_battle(sq(9, hp=23), move_index=start)
            ui = s["teacher_ui"]
            self.assertEqual(G.move_keys(ui, s["battle"]["yours"], "BUBBLE"), guide_keys[i])


# ---------- 2. readiness before Brock ----------

class Ready(unittest.TestCase):
    def test_safe_line_from_the_damage_model(self):
        w = Y.worst_case(A, at("PEWTER_CITY", 16, 18, sq(9)), full=True)
        # Geodude: 2 Bubbles (min roll 20 vs 33 HP), you are faster: 1 Tackle at max 8. Onix (faster): 2 turns,
        # Tackle max 7 each (Screech first gives 0 + 12). One critical hit: +5. 8 + 14 + 5 + 1 = 28.
        self.assertEqual(w["need"], 28)
        self.assertEqual(w["hits"], [("GEODUDE", 2, 1, 8), ("ONIX", 2, 2, 7)])

    def test_heal_below_the_line_never_at_full(self):
        for level, hp in ((9, 23), (10, 23), (9, 27), (11, 20)):
            s = at("PEWTER_CITY", 16, 18, sq(level, hp=hp))
            self.assertEqual(G.guide(s)["step"], "pewter_heal", (level, hp))
        for level in (9, 10, 11, 12):
            s = at("PEWTER_CITY", 16, 18, sq(level))
            self.assertIsNone(Y.heal_reason(A, s), level)
            self.assertEqual(G.guide(s)["step"], "gym_door", level)

    def test_heal_text_says_the_numbers(self):
        g = G.guide(at("PEWTER_CITY", 16, 18, dict(sq(9, hp=23), max_hp=29)))
        self.assertIn("HP 23/29; Brock's worst case needs 28", g["text"])
        self.assertLessEqual(len(g["text"]), G.MAX_CHARS)

    def test_heal_comes_before_the_gym_door_in_every_region(self):
        mon = sq(10, hp=23)
        for where in (("ROUTE_2", 3, 9), ("PEWTER_CITY", 18, 30), ("PEWTER_CITY", 16, 18), ("PEWTER_GYM", 4, 13),
                      ("PEWTER_GYM", 4, 2)):
            g = G.guide(at(*where, mon))
            self.assertEqual(g["step"], "pewter_heal", where)
            self.assertNotIn("Talk to Brock", g["text"].split("THEN:")[0], where)
        g = G.guide(at("PEWTER_GYM", 4, 13, mon))                  # inside: the walk out avoids row 6
        self.assertIn("GO:", g["text"])

    def test_low_bubble_pp_means_heal_first(self):
        s = at("PEWTER_CITY", 16, 18, sq(10, bubble_pp=2))
        self.assertIsNotNone(Y.heal_reason(A, s))
        self.assertEqual(G.guide(s)["step"], "pewter_heal")
        self.assertTrue(Y.ready(A, s))                             # a heal refills PP: no training needed

    def test_too_weak_trains_first(self):
        weak = sq(9, dv=8, spc_dv=4)            # Bubble min 17 vs Onix 36 HP: 3 hits, Bide can hit back
        s = at("ROUTE_2", 3, 9, weak)
        self.assertFalse(Y.ready(A, s))
        g = G.guide(s)
        self.assertEqual(g["step"], "train")
        self.assertIn("Brock's worst case needs", g["text"])
        self.assertTrue(Y.ready(A, at("ROUTE_2", 3, 9, sq(10, spc_dv=4))))

    def test_luna_b3_2_state_passes_without_a_detour(self):
        """b3-2: Luna healed in Pewter (9/28 -> 28/28, n241) and walked in at L9 28/28: no train, no second heal."""
        s = at("PEWTER_CITY", 16, 18, sq(9))
        self.assertEqual(s["team"][0]["max_hp"], 28)
        self.assertTrue(Y.ready(A, s))
        self.assertEqual(G.guide(s)["step"], "gym_door")
        self.assertEqual(G.guide(at("PEWTER_GYM", 4, 2, sq(9)))["step"], "brock")


# ---------- 3. the Brock battle ----------

class Battle(unittest.TestCase):
    def test_bubble_every_turn_with_the_arrow_in_words(self):
        s = brock_battle(sq(9, hp=23), move_index=2)
        g = G.guide(s, context={})
        self.assertIn("Use BUBBLE", g["text"])
        self.assertIn("PRESS: a a a*", g["text"])
        self.assertIn("opens on BUBBLE (your last move): no up/down needed", g["text"])
        self.assertIn("copy this line, not old notes", g["text"])
        s = brock_battle(sq(9, hp=23), move_index=1)
        g = G.guide(s, context={})
        self.assertIn("PRESS: a down a a*", g["text"])
        self.assertIn("opens on TAIL_WHIP (your last move), not on BUBBLE", g["text"])
        s = brock_battle(sq(9, hp=23), phase="moves", cursor=0)
        g = G.guide(s, context={})
        self.assertIn("PRESS: down down a a*", g["text"])
        self.assertIn("arrow is on TACKLE, not on BUBBLE", g["text"])
        for gg in (g,):
            self.assertLessEqual(len(gg["text"]), G.MAX_CHARS)

    def test_onix_too(self):
        g = G.guide(brock_battle(sq(10, hp=8), foe_index=1, move_index=2), context={})
        self.assertIn("Use BUBBLE", g["text"])

    def test_no_step_flip_mid_battle(self):
        ctx = {}
        full = brock_battle(sq(9), move_index=0)
        g1 = G.guide(full, context=ctx)
        self.assertEqual(g1["step"], "brock")
        self.assertIn("AFTER: Brock gives the Boulder Badge", g1["text"])
        hurt = brock_battle(sq(9, hp=5), foe_hp=9, move_index=2)    # b3-1 n301: 5/29 HP, Geodude 9/33
        g2 = G.guide(hurt, context=ctx)
        self.assertEqual(g2["step"], "brock")
        self.assertNotIn("Heal at the Pewter", g2["text"])
        self.assertEqual(G.guide(hurt)["step"], "pewter_heal")      # without the battle memory it would flip
        speech = dict(at("PEWTER_GYM", 4, 2, sq(9, hp=5)), text_box=True)   # the text right after the fight
        self.assertEqual(G.guide(speech, context=ctx)["step"], "brock")
        after = at("PEWTER_GYM", 4, 2, sq(9, hp=5))                 # battle over: checked again, lock cleared
        self.assertEqual(G.guide(after, context=ctx)["step"], "pewter_heal")
        self.assertNotIn("guide_battle", ctx)

    def test_potion_keys_when_hp_is_low(self):
        bag = {"POTION": 1, "ANTIDOTE": 1}
        s = brock_battle(sq(9, hp=4), foe_index=1, move_index=2, bag=bag)
        adv = A.battle_advice(s)
        self.assertTrue(adv["do"].startswith("Use POTION"), adv["do"])
        g = G.guide(s, context={})
        self.assertIn("use POTION", g["text"])
        self.assertIn("PRESS: down a", g["text"])                  # FIGHT -> ITEM, open the bag
        s2 = brock_battle(sq(9, hp=4), foe_index=1, bag=bag, phase="items", cursor=1)
        self.assertEqual(G.item_keys(s2["teacher_ui"], s2, s2["battle"]["yours"], "POTION"), "up a")
        s3 = brock_battle(sq(9, hp=4), foe_index=1, bag=bag, phase="item_target", cursor=0)
        s3["teacher_ui"]["item"] = "POTION"
        self.assertEqual(G.item_keys(s3["teacher_ui"], s3, s3["battle"]["yours"], "POTION"), "a a*")
        for keys in ("down a", "up a", "a a*"):
            LP.parse_buttons(keys)

    def test_sol_r19_potion_goes_to_the_advised_reserve(self):
        """Sol R19 B1: active L2 PIDGEY at 1 HP, reserve L10 SQUIRTLE at 4 HP, full Onix, one Potion."""
        pidgey = dict(species="PIDGEY", nickname="PIDGEY", level=2, hp=1, max_hp=13, status="ok", sleep_turns=0,
                      stats={"atk": 7, "def": 7, "spd": 8, "spc": 6}, moves=[dict(move="GUST", pp=35)])
        squirt = sq(10, hp=4)
        s = brock_battle(pidgey, foe_index=1, bag={"POTION": 1}, phase="item_target", cursor=0)
        s["team"] = [pidgey, squirt]
        s["teacher_ui"]["item"] = "POTION"
        adv = A.battle_advice(s)
        self.assertIn("Use POTION on SQUIRTLE", adv["do"])
        g = G.guide(s, context={})
        self.assertIn("then SQUIRTLE", g["text"])
        self.assertIn("PRESS: down a a*", g["text"])
        self.assertNotIn("then PIDGEY", g["text"])

    def test_sol_r19_wrong_item_target_backs_out(self):
        """Sol R19 B2: the Antidote's party list is open, the plan is a Potion: B, never a a*."""
        s = brock_battle(sq(9, hp=4), foe_index=1, bag={"ANTIDOTE": 1, "POTION": 1}, phase="item_target", cursor=0)
        s["teacher_ui"]["item"] = "ANTIDOTE"
        self.assertEqual(G.item_keys(s["teacher_ui"], s, s["battle"]["yours"], "POTION"), "b")
        g = G.guide(s, context={})
        self.assertIn("use POTION", g["text"])
        self.assertIn("PRESS: b", g["text"])
        self.assertNotIn("PRESS: a a*", g["text"])

    def test_no_potion_no_item_keys(self):
        s = brock_battle(sq(9, hp=4), foe_index=1, move_index=2)
        self.assertIsNone(G.item_keys(s["teacher_ui"], s, s["battle"]["yours"], "POTION"))


# ---------- 4. the player prompt ----------

class Prompt(unittest.TestCase):
    def test_copy_the_newest_guide_keys(self):
        self.assertIn("Copy the keys of the NEWEST GUIDE line, never keys from your notes", LP.ASK_LINE)
        self.assertTrue(re.search(r"battle keys change every turn", LP.ASK_LINE))


if __name__ == "__main__":
    unittest.main()
