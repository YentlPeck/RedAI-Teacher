"""Checks for tools/advise.py on real moments of the bot's record game
(fixture record-1831000065-v2: game memory dumps, not in the repo; see README).

Run: python -m unittest discover -s tests -v
"""
import json
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import settings  # noqa: E402
import advise as A  # noqa: E402
import read_state as R  # noqa: E402

D = settings.FixtureDir("record-1831000065-v2")


def state(name):
    return R.state_from_wram((D / f"{name}.wram").read_bytes())


class Advise(unittest.TestCase):
    def test_every_moment_gets_an_answer(self):
        for f in sorted(D.glob("*.wram")):
            a = A.answer(R.state_from_wram(f.read_bytes()))
            self.assertTrue(a["do"] and a["why"], f.name)
            self.assertLess(len(A.text(a).splitlines()), 16, f.name)   # short enough to put in a prompt

    def test_heal_when_a_hit_can_knock_you_out(self):
        a = A.answer(state("battle-055"))   # Nidoking 15 HP vs Machoke (Karate Chop up to 17)
        self.assertEqual(a["do"], "Use POTION on NIDOKING.")

    def test_heal_the_next_pokemon_when_the_lead_is_lost(self):
        a = A.answer(state("battle-058"))   # Pidgey L5 vs Lorelei's Dewgong, Nidoking 25 HP in the back
        self.assertTrue(a["do"].startswith("Use FULL_RESTORE on NIDOKING"), a["do"])

    def test_wait_when_the_enemy_fainted(self):
        self.assertTrue(A.answer(state("battle-030"))["do"].startswith("Press A"))

    def test_sure_knock_out_prefers_the_accurate_move(self):
        s = state("battle-024")             # Pidgey 41 HP: Horn Attack (100%) is enough, Mega Punch is 85%
        s["battle"]["yours"]["flags"] = []  # (in the real moment Nidoking is already thrashing)
        self.assertTrue(A.answer(s)["do"].startswith("Use HORN_ATTACK (FIGHT, then move 1 of 4"))

    def test_no_choice_while_thrashing(self):
        self.assertTrue(A.answer(state("battle-024"))["do"].startswith("Press A"))

    def test_way_after_catching_nidoran(self):
        a = A.answer(state("split-02"))     # Route 22 before Brock (step 5: a side trip, go back to Viridian)
        self.assertIn("go to VIRIDIAN_CITY", a["do"])
        self.assertIn("SQUIRTLE to about level", " ".join(a["details"]))

    def test_way_in_the_luck_chain_part(self):
        a = A.answer(state("split-04"))     # Route 4 side of Pewter, before Mt. Moon
        self.assertIn("POKECENTER", a["do"])  # R11: hurt party heals before entering Moon.

    def test_champion(self):
        self.assertIn("Champion", A.answer(state("split-21"))["do"])

    def test_ready_question(self):
        a = A.answer(state("split-02"), "am I ready for Brock?")
        self.assertEqual(a["kind"], "ready")
        self.assertTrue(a["do"].startswith("Not ready yet"))
        self.assertTrue(any("ONIX" in d for d in a["details"]))

    def test_catch_what_the_team_needs(self):
        s = state("split-03")               # no one can learn Cut yet
        self.assertIn("CUT", A.catch_reason(s, "PARAS"))
        self.assertIsNone(A.catch_reason(s, "RATTATA"))

    def test_question_finds_lessons(self):
        a = A.answer(state("split-04"), "how do I get through Mt. Moon?")
        self.assertIn("POKECENTER", a["do"])
        self.assertIn("PP", " ".join(a["details"]))  # Recovery takes precedence over a future cave lesson.

    # ----- independent hand-computed damage cases (Sol AD1 #7, #8) -----
    S100 = {"atk": 100, "def": 100, "spd": 100, "spc": 100}

    def test_fixed_damage_ignores_types(self):
        self.assertEqual(A.damage("NIGHT_SHADE", 30, self.S100, self.S100, [], ["NORMAL"]), (30, 30))
        self.assertEqual(A.damage("SEISMIC_TOSS", 30, self.S100, self.S100, [], ["GHOST"]), (30, 30))
        self.assertEqual(A.damage("SONICBOOM", 30, self.S100, self.S100, [], ["GHOST"]), (20, 20))

    def test_type_order_is_the_game_table_order(self):
        # base 43; table: ICE->WATER x0.5 first (21), then ICE->FLYING x2 (42). The other order would give 43.
        for types in (["WATER", "FLYING"], ["FLYING", "WATER"]):
            self.assertEqual(A.damage("ICE_BEAM", 50, self.S100, self.S100, [], types), (35, 42))

    def test_explosion_and_reflect(self):
        self.assertEqual(A.damage("EXPLOSION", 50, self.S100, self.S100, [], ["FIRE"]), (128, 151))
        self.assertEqual(A.damage("TACKLE", 50, self.S100, self.S100, [], ["FIRE"]), (14, 17))
        self.assertEqual(A.damage("TACKLE", 50, self.S100, self.S100, [], ["FIRE"], screens=["reflect"]), (7, 9))

    # ----- unsafe advice found by Sol (AD1 #1-#6), on made-up battles -----
    def battle(self, me, foe, team=None, bag=(), kind="trainer"):
        s = state("split-02")
        s["battle"] = {"kind": kind, "yours": me, "enemy": foe, "trainer": "Lass:1"}
        s["team"] = team or [dict(me, stats=dict(me["stats"]))]
        s["bag"] = [{"item": i, "count": 1} for i in bag]
        return s

    def mon(self, species, level, hp, moves, spd=50, status="ok", flags=(), max_hp=None, stats=None):
        st = stats or {"atk": 60, "def": 50, "spd": spd, "spc": 50}
        return {"species": species, "level": level, "hp": hp, "max_hp": max_hp or hp, "status": status,
                "types": A.SPECIES[species]["types"], "stats": dict(st, spd=spd), "flags": list(flags),
                "moves": [{"move": m, "pp": 10} for m in moves]}

    def test_quick_attack_counts_in_the_race(self):
        me = self.mon("NIDOKING", 30, 5, ["HORN_ATTACK"], spd=80, max_hp=90)
        foe = self.mon("RATTATA", 30, 60, ["QUICK_ATTACK"], spd=40)
        a = A.answer(self.battle(me, foe, bag=["SUPER_POTION"]))
        self.assertNotIn("for sure", a["why"])
        self.assertEqual(a["do"], "Use SUPER_POTION on NIDOKING.")

    def test_frozen_without_cure_is_not_told_to_attack(self):
        me = self.mon("NIDOKING", 30, 80, ["HORN_ATTACK"], spd=80, status="frozen")
        foe = self.mon("RATTATA", 20, 40, ["TACKLE"], spd=40)
        other = self.mon("SQUIRTLE", 30, 80, ["WATER_GUN"])
        a = A.answer(self.battle(me, foe, team=[me, other]))
        self.assertFalse(a["do"].startswith("Use HORN_ATTACK"), a["do"])

    def test_enemy_horn_drill_is_a_threat(self):
        me = self.mon("NIDOKING", 30, 80, ["HORN_ATTACK"], spd=40)
        foe = self.mon("RHYHORN", 30, 300, ["HORN_DRILL"], spd=60)
        a = A.answer(self.battle(me, foe))
        self.assertTrue(any("HORN_DRILL can knock you out" in d for d in a["details"]), a["details"])
        self.assertNotIn("for sure", a["why"])

    def test_switch_counts_the_hit_on_entry(self):
        me = self.mon("PIDGEY", 5, 10, ["GUST"], spd=10)
        foe = self.mon("GEODUDE", 30, 80, ["ROCK_THROW"], spd=20)
        weak = self.mon("SQUIRTLE", 20, 3, ["WATER_GUN"], spd=30, max_hp=60)   # would faint while switching in
        self.assertIsNone(A.switch_target(self.battle(me, foe, team=[me, weak]), me, foe))

    def test_no_catch_advice_when_in_danger(self):
        me = self.mon("SQUIRTLE", 10, 3, ["TACKLE"], spd=10, max_hp=30)
        foe = self.mon("PARAS", 10, 30, ["SCRATCH"], spd=20)
        a = A.answer(self.battle(me, foe, bag=["POKE_BALL"], kind="wild"))
        self.assertNotIn("Catch", a["why"])

    def test_rival_team_follows_the_rival_starter(self):
        s = state("split-02")
        self.assertEqual(A.boss_keys(dict(s, rival_starter="BULBASAUR"), "rival22"), ["Rival2:11"])
        self.assertEqual(A.boss_keys(dict(s, rival_starter="CHARMANDER"), "rival22"), ["Rival2:12"])

    def test_growth_learns_moves_of_the_right_evolution(self):
        sq = dict(state("split-02")["team"][0], types=["WATER"])        # Squirtle L6
        moves = lambda lv: [m["move"] for m in A._scaled(sq, lv)["moves"]]
        self.assertEqual(A._scaled(sq, 23)["species"], "WARTORTLE")
        self.assertNotIn("BITE", moves(23))                              # Wartortle learns Bite at 24
        self.assertIn("BITE", moves(24))

    # ----- Sol AD2 round 2 -----
    def test_mixed_enemy_moves_count(self):
        # Horn Attack 19-23 needs 2 hits on 38 HP. Body Slam (up to 45) on turn 1, then Quick Attack (up to 22) before
        # your 2nd hit = 67. Each move alone (45, or 2 x 22 = 44) would look safe at 60 HP (AD2 #1).
        foe = self.mon("RATICATE", 30, 38, ["BODY_SLAM", "QUICK_ATTACK"], spd=40)
        for hp, safe in ((60, False), (70, True)):
            me = self.mon("NIDOKING", 30, hp, ["HORN_ATTACK"], spd=80, max_hp=90)
            plan = A.safe_plan(me, foe, [A.move_option("HORN_ATTACK", 10, me, foe)], hp)
            self.assertEqual(plan is not None, safe, hp)

    def test_frozen_always_answers(self):
        me = self.mon("NIDOKING", 30, 80, ["HORN_ATTACK"], spd=80, status="frozen")
        foe = self.mon("RATTATA", 20, 40, ["TACKLE"], spd=40)
        a = A.answer(self.battle(me, foe))          # no cure, no team: still not "Use HORN_ATTACK"
        self.assertIn("frozen", a["why"])
        self.assertFalse(a["do"].startswith("Use HORN_ATTACK"))

    def test_sleep_uses_awakening_when_it_would_faint_first(self):
        me = dict(self.mon("NIDOKING", 30, 40, ["HORN_ATTACK"], spd=80, status="asleep", max_hp=90), sleep_turns=5)
        foe = self.mon("RATICATE", 30, 80, ["HYPER_FANG"], spd=40)
        self.assertEqual(A.answer(self.battle(me, foe, bag=["AWAKENING"]))["do"], "Use AWAKENING on NIDOKING.")

    def test_substitute_wrap_and_counter_block_sure_wins(self):
        me = self.mon("NIDOKING", 50, 150, ["HORN_ATTACK", "THUNDERBOLT"], spd=80, stats={"atk": 150, "def": 100, "spd": 80, "spc": 100})
        for flags, moves in ((["substitute"], ["TACKLE"]), (["trapping"], ["WRAP"]), ([], ["COUNTER"])):
            foe = self.mon("RATTATA", 10, 20, moves, spd=20, flags=flags)
            a = A.answer(self.battle(me, foe))
            if flags:
                self.assertNotIn("for sure", a["why"], flags)
            else:                                  # Counter: a sure win only with a non-Normal / Fighting move
                self.assertNotIn("HORN_ATTACK", a["do"])

    def test_no_heal_against_a_working_horn_drill(self):
        me = self.mon("NIDOKING", 30, 5, ["HORN_ATTACK"], spd=40, max_hp=90)
        foe = self.mon("RHYHORN", 30, 300, ["HORN_DRILL"], spd=60)
        a = A.answer(self.battle(me, foe, bag=["SUPER_POTION", "HYPER_POTION"]))
        self.assertNotIn("POTION", a["do"])

    def test_switch_uses_the_same_safe_rules(self):
        me = self.mon("PIDGEY", 5, 10, ["GUST"], spd=10)
        foe = self.mon("RATTATA", 30, 60, ["QUICK_ATTACK"], spd=20)
        frozen = self.mon("SQUIRTLE", 30, 80, ["WATER_GUN"], spd=30, status="frozen")
        no_pp = dict(self.mon("NIDOKING", 30, 80, ["HORN_ATTACK"], spd=30), moves=[{"move": "HORN_ATTACK", "pp": 0}])
        self.assertIsNone(A.switch_target(self.battle(me, foe, team=[me, frozen, no_pp]), me, foe))

    def test_catch_never_uses_a_recoil_move(self):
        me = self.mon("RATTATA", 20, 1, ["DOUBLE_EDGE", "TAIL_WHIP"], spd=50, max_hp=50)
        foe = self.mon("PARAS", 10, 60, ["STUN_SPORE"], spd=10)   # no damaging move: not in danger
        a = A.answer(self.battle(me, foe, bag=["POKE_BALL"], kind="wild"))
        self.assertNotIn("DOUBLE_EDGE", a["do"])

    def test_poison_counts_in_the_race(self):
        me = self.mon("SQUIRTLE", 20, 6, ["TACKLE"], spd=50, status="poisoned", max_hp=96)
        foe = self.mon("RATTATA", 5, 50, ["TAIL_WHIP"], spd=10)    # harmless enemy, but poison takes 6 per turn
        self.assertNotIn("for sure", A.answer(self.battle(me, foe))["why"])

    def test_growth_learns_before_evolving(self):
        dn = {"species": "DRAGONAIR", "level": 54, "hp": 150, "max_hp": 150, "status": "ok", "types": ["DRAGON"],
              "stats": {"atk": 120, "def": 100, "spd": 100, "spc": 100}, "moves": [{"move": "SLAM", "pp": 20}]}
        self.assertIn("HYPER_BEAM", [m["move"] for m in A._scaled(dn, 55)["moves"]])   # Dragonair learns it at 55

    def test_screen_byte_overflow(self):
        # Defense 600 with Reflect = 1200; both stats / 4 keep only the low byte: 1200 / 4 = 300 -> 44, 100 / 4 = 25
        st = {"atk": 100, "def": 600, "spd": 100, "spc": 100}
        lo, hi = A.damage("TACKLE", 50, self.S100, st, [], ["FIRE"], screens=["reflect"])
        base = min(22 * 35 * 25 // 44 // 50, 997) + 2
        self.assertEqual((lo, hi), (base * 217 // 255, base))

    # ----- step 5: problems seen in the step 4 games -----
    def start_state(self, map_, x, y, team=False):
        s = R.state_from_wram(settings.fixture("start.wram").read_bytes())
        s["place"].update(map=map_, x=x, y=y)
        if team:
            s["team"] = state("split-02")["team"][:1]
        done = [i for i, g, f, p in R.MILESTONES if i == "starter" and team] + (["oak"] if team else [])
        s["story"]["done"] = done
        s["story"]["next"] = next({"id": i, "goal": g, "part": p} for i, g, f, p in R.MILESTONES if i not in done)
        return s

    def test_before_oak_the_lab_is_not_the_place(self):
        a = A.answer(self.start_state("OAKS_LAB", 5, 5))
        self.assertIn("tall grass", a["do"])
        self.assertIn("OAKS_LAB is not on our route now: leave by the door / stairs at (4,11) and go to PALLET_TOWN",
                      a["do"])   # round 7: the way out (was "never on OAKS_LAB at this point")

    def test_pallet_before_oak_leads_north(self):
        a = A.answer(self.start_state("PALLET_TOWN", 10, 6))
        self.assertIn("tall grass", a["do"])
        self.assertTrue(any("up" in d for d in a["details"]), a["details"])

    def test_starter_counts_as_soon_as_it_is_in_the_team(self):
        s = R.state_from_wram((D / "split-01.wram").read_bytes())
        self.assertIn("starter", s["story"]["done"])

    def test_which_starter_question_gets_a_lesson(self):
        a = A.answer(self.start_state("OAKS_LAB", 5, 3), "Which starter should I choose?")
        self.assertEqual(a["kind"], "lesson")
        self.assertIn("Squirtle", a["do"])

    def test_low_hp_warning_on_the_way(self):
        s = state("split-02")
        s["team"][0]["hp"] = 2
        self.assertTrue(A.answer(s)["details"][0].startswith("Heal first"))

    # ----- Sol S5 -----
    def test_other_story_order_still_gets_directions(self):
        # Misty beaten before Bill: the next goal is still Bill, and Route 25 is on the way to him
        s = state("split-07")                       # after Misty in the record game (Bill was earlier there)
        s["story"]["done"] = [d for d in s["story"]["done"] if d != "ss_ticket"]
        s["story"]["next"] = next({"id": i, "goal": g, "part": p} for i, g, f, p in R.MILESTONES if i == "ss_ticket")
        s["bag"] = [b for b in s["bag"] if b["item"] != "S_S_TICKET"]
        s["place"].update(map="ROUTE_25", x=20, y=6)
        a = A.answer(s)
        self.assertNotIn("never on ROUTE_25", a["do"])

    def test_which_way_is_a_direction_question(self):
        s = self.start_state("PALLET_TOWN", 10, 6)
        self.assertEqual(A.answer(s, "Which way should I go?")["kind"], "way")
        self.assertEqual(A.answer(state("split-02"), "Which level should I train to for Brock?")["kind"], "ready")

    def test_low_hp_warning_on_every_answer_outside_battle(self):
        s = self.start_state("OAKS_LAB", 5, 5, team=True)
        s["team"][0]["hp"] = 1
        for q in (None, "am I ready?", "Which starter should I choose?"):
            self.assertTrue(A.answer(s, q)["details"][0].startswith("Heal first"), q)

    # ----- round 3 fixes (rerun problems) -----
    def test_open_text_box_says_read_on(self):
        s = self.start_state("OAKS_LAB", 5, 3, team=True)
        s["text_box"] = True                      # e.g. Oak talking while the Parcel is handed over
        a = A.answer(s)
        self.assertTrue(a["do"].startswith("Press A to read on"))
        self.assertTrue(a["details"][0].startswith("After that, your next goal is"))

    def test_text_box_seen_in_a_real_moment(self):
        import io, sys
        sys.path.insert(0, str(ROOT / "arena"))
        self.assertFalse(R.state_from_wram(settings.fixture("start.wram").read_bytes())["text_box"])

    def test_exit_spot_is_named(self):
        a = A.answer(state("split-02"))           # Route 22 -> Viridian City is off the east edge
        self.assertIn("The way to VIRIDIAN_CITY: walk off the right (east) edge at (39,9).", a["details"])

    def test_stairs_exit_is_the_stairs_tile(self):
        a = A.answer(self.start_state("REDS_HOUSE_2F", 6, 1))   # round 3: a player stood here for 190 commands
        self.assertIn("stairs / door at (7,1): stand at (6,1) and walk right onto it", " ".join(a["details"]))
        self.assertIn("from where you stand: right 1 to (7,1).", " ".join(a["details"]))

    def test_heal_names_the_pokemon_center(self):
        s = self.start_state("ROUTE_2", 5, 50, team=True)           # round 3: "heal" without saying where
        s["team"][0]["hp"] = 1
        a = A.answer(s)
        self.assertIn("Pokémon Center (red roof, free healing) in VIRIDIAN_CITY (south of ROUTE_2), door at (23,25)",
                      a["details"][0])
        s["place"].update(map="VIRIDIAN_MART", last_map="VIRIDIAN_CITY")
        self.assertIn("Go back out to VIRIDIAN_CITY first", A.answer(s, "where can I heal?")["do"])
        s["place"].update(map="ROUTE_1")
        self.assertIn("your house (Mom heals you for free) in PALLET_TOWN", A.answer(s, "where can I heal?")["do"])
        s["place"].update(map="VIRIDIAN_POKECENTER")
        self.assertIn("talk to the nurse behind the counter at (3,1)", A.answer(s, "pokemon center?")["do"])

    def test_heal_names_the_nearest_town_on_a_route(self):        # round 8: t10-5 at the forest north gate
        s = self.start_state("ROUTE_2", 8, 5, team=True)
        self.assertIn("in PEWTER_CITY (north of ROUTE_2)", A.heal_place(s))
        s["place"].update(map="VIRIDIAN_FOREST_NORTH_GATE", last_map="ROUTE_2", x=4, y=2)
        self.assertIn("To heal: the nearest is the Pokémon Center (red roof, free healing) in PEWTER_CITY",
                      A.heal_place(s))
        s["place"].update(map="VIRIDIAN_FOREST_SOUTH_GATE")
        self.assertIn("in VIRIDIAN_CITY (south of ROUTE_2)", A.heal_place(s))
        s["place"].update(map="VIRIDIAN_FOREST", x=2, y=4)            # forest top: out by the north gate
        self.assertIn("in PEWTER_CITY", A.heal_place(s))
        s["place"].update(x=28, y=44)                                 # forest bottom: back to Viridian
        self.assertIn("in VIRIDIAN_CITY", A.heal_place(s))
        s["place"].update(x=17, y=45)                                 # Sol R8A: the south gate is 2 presses away
        self.assertIn("in VIRIDIAN_CITY", A.heal_place(s))
        self.assertIn("down 2 to (17,47) (out the door to VIRIDIAN_FOREST_SOUTH_GATE)", A.heal_place(s))
        s["place"].update(x=25, y=12)                                 # Sol R8A: 90 presses north vs 43 south
        self.assertIn("in VIRIDIAN_CITY", A.heal_place(s))
        s["place"].update(map="ROUTE_2", x=3, y=44)                   # south Route 2: the north edge is cut off
        self.assertIn("in VIRIDIAN_CITY", A.heal_place(s))
        s["place"].update(map="ROUTE_1", last_map="ROUTE_1", x=10, y=4)
        self.assertIn("in VIRIDIAN_CITY (north of ROUTE_1)", A.heal_place(s))
        s["place"].update(y=32)
        self.assertIn("your house (Mom heals you for free) in PALLET_TOWN", A.heal_place(s))

    def test_mart_says_who_sells(self):                           # round 8: "POTIONs are all sold out" is a customer
        s = state("split-03")                                     # Brock is next
        s["place"].update(map="VIRIDIAN_MART", x=3, y=6)
        a = A.answer(s)
        line = next(d for d in a["details"] if d.startswith("To buy"))
        self.assertIn("To buy Antidotes", line)
        self.assertIn("stand at (2,5), press left once to face the clerk", line)
        self.assertIn("To buy Antidotes", A.note(a))
        s["place"].update(map="PEWTER_MART")
        self.assertIn("To buy Potions (300 each): stand at (2,5)", A.text(A.answer(s)))
        s["place"].update(map="PEWTER_CITY", x=18, y=17)
        self.assertNotIn("To buy", A.text(A.answer(s)))
        s = self.start_state("VIRIDIAN_MART", 3, 6, team=True)   # before the parcel: no shop yet
        self.assertIsNone(A.shop_line(s))

    def test_heal_doors_come_from_the_game_maps(self):
        self.assertEqual(A.HEALERS["PEWTER_CITY"]["door"], (13, 25))
        self.assertEqual(A.HEALERS["ROUTE_4"]["inside"], "MT_MOON_POKECENTER")
        self.assertTrue(A.HEALERS["PALLET_TOWN"]["mom"])
        self.assertEqual(len(A.HEALERS), 13)

    def test_stuck_player_is_told(self):
        s = self.start_state("REDS_HOUSE_2F", 6, 1)
        self.assertNotIn("not moved", A.text(A.answer(s, stuck=3)))
        a = A.answer(s, stuck=8)
        self.assertIn("You have not moved in your last 8 commands", a["details"][0])
        self.assertIn("stairs / door at (7,1)", " ".join(a["details"]))

    # ---- step 5 (21 Oct): gym door, no speedrun Nidoran detour ----
    def test_gym_door_is_named_in_pewter(self):
        s = state("split-03")                                   # Brock is next
        s["place"].update(map="PEWTER_CITY", x=18, y=17)
        a = A.answer(s, "Which tile is the gym door and how do I step onto it?")   # round 4, t7-2's question
        self.assertEqual(a["kind"], "way")
        self.assertIn("PEWTER_GYM", a["do"])
        self.assertIn("door is at (16,17)", a["do"])
        self.assertIn("stand at (16,18) and walk up into it", a["do"])

    def test_door_step_is_up_into_the_door(self):
        s = state("split-02")
        s["place"].update(map="VIRIDIAN_CITY", x=20, y=35)      # from Route 1, Brock next: the route shops first
        s["bag"] = []                                           # round 8: only while nothing is bought yet
        a = A.answer(s)
        self.assertIn("door is at (29,19)", a["do"])
        self.assertNotIn("(30,20)", A.text(a))                  # before: "walk right onto (30,20)" (no door there)
        self.assertIn("right 10 to (29,20), up 1 to (29,19).", a["details"][0])

    def test_no_second_trip_into_the_viridian_mart(self):       # round 8: t10-7 n232 asked for Route 2, got the Mart
        s = state("split-02")
        s["place"].update(map="VIRIDIAN_CITY", x=23, y=28)
        s["bag"] = [{"item": "ANTIDOTE", "count": 2}]
        a = A.answer(s, "Where now?")
        self.assertIn("go to ROUTE_2", a["do"])
        self.assertIn("walk off the top (north) edge", A.text(a))
        s["bag"], s["money"] = [], 50                           # cannot buy anything: no Mart either
        self.assertIn("go to ROUTE_2", A.answer(s)["do"])

    def test_the_place_asked_for(self):                         # round 8: answer the place the player names
        s = state("split-02")
        s["place"].update(map="VIRIDIAN_CITY", x=23, y=28)
        self.assertEqual(A.named_place("Route to Route 2 again?", s), "ROUTE_2")
        self.assertEqual(A.named_place("where is Pewter?", s), "PEWTER_CITY")
        self.assertEqual(A.named_place("how do I find the Pewter Gym?", s), "PEWTER_GYM")
        self.assertIsNone(A.named_place("I came from Route 1, where now?", s))
        self.assertIsNone(A.named_place("how do I get to Viridian City?", s))      # already here
        a = A.answer(s, "where is Pewter?")
        self.assertIn("To get to PEWTER_CITY: walk off the top (north) edge of this map to ROUTE_2, then on to "
                      "PEWTER_CITY (through VIRIDIAN_FOREST_SOUTH_GATE, VIRIDIAN_FOREST, VIRIDIAN_FOREST_NORTH_GATE)",
                      a["do"])
        s["place"].update(x=29, y=20)                                       # Sol R8A: past / negated visits
        self.assertIsNone(A.named_place("I already went to Viridian Mart; where next?", s))
        self.assertEqual(A.named_place("I do not want to go to Route 1; how do I get to Route 2?", s), "ROUTE_2")
        self.assertEqual(A.named_place("How do I get to Route 2 from here?", s), "ROUTE_2")          # Sol R8B
        self.assertEqual(A.named_place("not sure how to get to Pewter", s), "PEWTER_CITY")
        self.assertIsNone(A.named_place("I came from Route 1 and went to the Viridian Mart", s))
        s["place"].update(x=23, y=28)
        self.assertIn("left 1 to (17,0), up 1 to (17,-1)", a["details"][0])   # lands on (7,71), as the record did
        s["place"].update(map="ROUTE_2", x=3, y=44)                       # Sol R8A: south Route 2 -> the forest
        self.assertIn("go through the door / stairs to VIRIDIAN_FOREST_SOUTH_GATE",
                      A.answer(s, "How do I get to Pewter?")["do"])
        s["place"].update(map="ROUTE_2", x=5, y=50)
        self.assertNotIn("parcel", A.text(A.answer(s, "Which tile on Route 2 is the way?")).lower())   # t10-5b n243

    def test_heal_gives_the_walk(self):                        # round 8: t10-7 took 25 commands to find the door
        s = state("split-02")
        s["place"].update(map="VIRIDIAN_CITY", x=23, y=28, last_map="VIRIDIAN_CITY")
        self.assertIn("The walk from where you stand: left 4 to (19,28), up 2 to (19,26), right 4 to (23,26), "
                      "up 1 to (23,25) (into the door).", A.heal_place(s))
        s["place"].update(map="ROUTE_2", x=5, y=50, last_map="ROUTE_2")
        self.assertIn("jump down (over the ledge) to (4,62)", A.heal_place(s))
        self.assertIn("(off the south edge to VIRIDIAN_CITY)", A.heal_place(s))
        s["place"].update(map="VIRIDIAN_FOREST_NORTH_GATE", x=4, y=2)
        self.assertIn("up 1 to (5,0) (out the door to ROUTE_2)", A.heal_place(s))

    def test_door_comes_from_the_game_maps_and_only_outdoors(self):
        self.assertEqual(A.door_text("VIRIDIAN_CITY", "VIRIDIAN_MART", (29, 20)),
                         " Its door is at (29,19): stand at (29,20) and walk up into it.")
        self.assertEqual(A.door_text("VIRIDIAN_CITY", "VIRIDIAN_MART", (20, 30)), " Its door is at (29,19).")
        # Sol S5B: not every door is entered walking up (Route 16 gate: left from (25,4))
        self.assertEqual(A.door_step((24, 4), (25, 4)), "left")
        self.assertEqual(A.door_text("VIRIDIAN_CITY", "ROUTE_2", (20, 30)), "")        # not a building
        self.assertEqual(A.door_text("VIRIDIAN_FOREST", "VIRIDIAN_FOREST_NORTH_GATE", (1, 1)), "")   # not outdoors

    def test_no_nidoran_detour_before_brock(self):
        s = state("split-02")                                   # after the Pokédex, Brock next
        s["team"] = [t for t in s["team"] if t["species"] != "NIDORAN_M"]
        for x, y in ((29, 20), (20, 30), (2, 16), (29, 19)):
            s["place"].update(map="VIRIDIAN_CITY", x=x, y=y)
            t = A.text(A.answer(s))
            self.assertNotIn("ROUTE_22", t)
            self.assertNotIn("Nidoran", t)
            if (x, y) != (20, 30):                               # from the south, the route shops at the Mart first
                self.assertIn("go to ROUTE_2", t)
        # out of the Mart: on to Route 2 by the walked join (15,18) -> (16,18) -> (16,17), not back into the Mart
        s["place"].update(map="VIRIDIAN_CITY", x=29, y=20)
        self.assertIn("left 14 to (15,20), up 2 to (15,18), right 1 to (16,18), up 2 to (16,16)", A.text(A.answer(s)))
        self.assertFalse(any(w["map"] == "ROUTE_22" for w in A.WALKS[:A.WALKS.index(next(
            w for w in A.WALKS if w["map"] == "PEWTER_GYM"))]))

    def test_route_22_before_brock_only_points_back_east(self):
        s = state("split-02")
        for x, y in ((39, 8), (29, 4), (33, 11)):                 # Sol S5B: arrival tile, rival tiles
            s["place"].update(map="ROUTE_22", x=x, y=y)
            a = A.answer(s)
            self.assertIn("side trip", a["do"])
            self.assertIn("go to VIRIDIAN_CITY", a["do"])
            self.assertIn("right (east) edge at (39,9)", " ".join(a["details"]))
            self.assertNotIn("Our route on this map", A.text(a))   # the record's walk there is the catch loop

    def test_handover_only_at_the_viridian_mart(self):
        # Sol S5B: a walk that ends where a later walk on the same map starts happens elsewhere too (Celadon Mart 5F,
        # before the roof drinks). Only the Viridian Mart doorstep may skip ahead.
        cases = []
        for vi, w in enumerate(A.WALKS):
            end = tuple(w["points"][-1][:2])
            for k in range(vi + 1, len(A.WALKS)):
                if A.WALKS[k]["map"] == w["map"] and any(tuple(q[:2]) == end and q[2] == w["points"][-1][2]
                                                         for q in A.WALKS[k]["points"][:2]):
                    cases.append((w["map"], vi, end))
                    break
        self.assertTrue(any(m == "CELADON_MART_5F" for m, _, _ in cases))
        for m, vi, end in cases:
            moved = A.handover(m, vi, len(A.WALKS[vi]["points"]) - 1, end)[0] != vi
            self.assertEqual(moved, m == "VIRIDIAN_CITY" and A.WALKS[vi + 1]["map"] == "VIRIDIAN_MART", (m, vi))

    def test_no_speedrun_lessons_or_nidoran_plan(self):
        self.assertIsNone(A.catch_reason(state("split-01"), "NIDORAN_M"))
        lines = [l for p in A.KB["parts"] for ls in p["lessons"].values() for l in ls]
        self.assertFalse([l for l in lines if A.SPEEDRUN_ONLY.search(l)])
        self.assertTrue(any("Nidoran learns Horn Attack" in l for l in lines))      # plain game facts stay
        for q in ("should I catch a Nidoran?", "where do I go now?"):
            self.assertNotIn("Route 22", A.text(A.answer(state("split-02"), q)))

    # ---- round 6 (dev copy): forest legs ----
    def test_forest_legs_have_checkpoints_and_start_on_the_path(self):
        s = state("split-02")
        s["place"].update(map="VIRIDIAN_FOREST", x=25, y=30)     # on the long way north (25,41) -> (25,9)
        d = A.answer(s)["details"][1]
        self.assertIn("from where you stand: up 18 to (25,12), right 1 to (26,12), up 3 to (26,9)", d)  # round the ball
        s["place"].update(map="VIRIDIAN_FOREST", x=5, y=21)
        self.assertIn("up 19 to (1,0)", A.answer(s)["details"][1])                  # the exit gate, top left

    def test_off_the_route_the_way_back_goes_around_the_trees(self):
        import walkable as W
        s = state("split-02")
        s["place"].update(map="VIRIDIAN_FOREST", x=1, y=31)       # t8-5 looped here; "go to (2,22)" hit trees
        d = A.answer(s)["details"][1]
        self.assertIn("from where you stand: right 5 to (6,31), down 9 to (6,40)", d)
        self.assertNotIn("go to", d)
        g = W.grid("VIRIDIAN_FOREST")
        self.assertNotIn("up", dict(W.moves(g, (2, 30))))          # the emulator walk was blocked there going up
        self.assertIn((16, 43), g["people"])                         # a trainer stands there
        self.assertEqual(W.path("VIRIDIAN_FOREST", (5, 21), {(1, 0)})[-1], "up")
        self.assertIsNone(W.path("VIRIDIAN_FOREST", (5, 21), {(0, 0)}))   # a tree: no way there

    def test_ledges_jump_only_downhill(self):
        import walkable as W
        g = W.grid("ROUTE_1")
        jumps = [(p, d, q) for p in g["tile"] for d, q in W.moves(g, p) if abs(q[0] - p[0]) + abs(q[1] - p[1]) == 2]
        self.assertTrue(jumps)
        self.assertTrue(all(d in ("down", "left", "right") for _, d, _ in jumps))
        self.assertEqual(A.with_coords(["jump down (over the ledge)", "up 1"], (5, 5)),
                         ["jump down (over the ledge) to (5,7)", "up 1 to (5,6)"])

    def test_every_square_players_stood_on_is_walkable(self):
        import glob
        import walkable as W
        bad, n = 0, 0
        if not glob.glob(str(settings.FIXTURES / "logs" / "t8-*" / "log.jsonl")):
            self.skipTest("needs round 4-5 game logs (not in the repo)")
        for f in glob.glob(str(settings.FIXTURES / "logs" / "t8-*" / "log.jsonl")):
            with open(f, encoding="utf-8") as fh:
                for r in map(json.loads, fh):
                    g = W.grid(r.get("map") or "")
                    if g and "x" in r:
                        n += 1
                        bad += g["tile"].get((r["x"], r["y"])) not in g["walk"]
        self.assertGreater(n, 1000)
        self.assertLess(bad / n, 0.002)       # 21 Oct: 5 of 8572 (ledge jumps / doors logged mid-move)

    def test_forest_walk_is_passable_from_every_square_players_stood_on(self):
        import glob
        import walkable as W
        g, s, sq = W.grid("VIRIDIAN_FOREST"), state("split-02"), set()
        if not glob.glob(str(settings.FIXTURES / "logs" / "t[78]-*" / "log.jsonl")):
            self.skipTest("needs round 4-5 game logs (not in the repo)")
        for f in glob.glob(str(settings.FIXTURES / "logs" / "t[78]-*" / "log.jsonl")):
            with open(f, encoding="utf-8") as fh:
                sq |= {(r["x"], r["y"]) for r in map(json.loads, fh) if r.get("map") == "VIRIDIAN_FOREST" and "x" in r}
        self.assertGreater(len(sq), 50)
        for x, y in sq:
            s["place"].update(map="VIRIDIAN_FOREST", x=x, y=y)
            d = next(t for t in A.answer(s)["details"] if "from where you stand:" in t)
            self.assertNotIn("go to", d)
            p = (x, y)
            for leg in d.split("from where you stand: ")[1].split(" (x grows")[0].rstrip(" .").split(", ")[:4]:
                word, n = leg.split()[:2]
                for _ in range(int(n)):
                    p = dict(W.moves(g, p, people=False)).get(word)
                    self.assertIsNotNone(p, (x, y, leg))

    # ---- round 7 (dev copy): the way out of places our route does not use ----
    def test_home_after_a_blackout_leads_out_of_the_house(self):
        s = state("split-02")                      # before Brock; t9-7 woke up at home and stayed in its bedroom
        s["place"].update(map="REDS_HOUSE_2F", x=0, y=2)
        a = A.answer(s)
        self.assertIn("leave by the door / stairs at (7,1) and go to PALLET_TOWN (through REDS_HOUSE_1F)", a["do"])
        self.assertIn("The way out, from where you stand: ", a["details"][0])
        self.assertTrue(a["details"][0].split(": ", 1)[1].split(". (x")[0].endswith("to (7,1)"))
        s["place"].update(map="REDS_HOUSE_1F", x=7, y=1)          # down the stairs: out of the front door
        a = A.answer(s)
        self.assertIn("go to PALLET_TOWN;", a["do"])
        self.assertIn("(out the door)", a["details"][0])

    def test_way_out_walks_only_on_walkable_squares(self):
        import walkable as W
        s = state("split-02")
        for m in ("REDS_HOUSE_2F", "REDS_HOUSE_1F", "VIRIDIAN_POKECENTER", "PEWTER_POKECENTER", "VIRIDIAN_SCHOOL_HOUSE",
                  "ROUTE_2_TRADE_HOUSE", "PEWTER_NIDORAN_HOUSE", "PEWTER_SPEECH_HOUSE", "VIRIDIAN_NICKNAME_HOUSE"):
            g = W.grid(m)
            for p in [q for q in g["tile"] if g["tile"][q] in g["walk"]][::3]:
                s["place"].update(map=m, x=p[0], y=p[1])
                a = A.answer(s)
                if "The way out" not in a["details"][0]:
                    continue
                legs = a["details"][0].split("from where you stand: ")[1].split(". (x grows")[0].split(", ")
                for leg in legs:
                    word, n = leg.split()[:2]
                    for _ in range(int(n)):
                        q = (p[0] + A.DELTA[word][0], p[1] + A.DELTA[word][1])
                        if q not in g["tile"] and "(out the door)" in leg:   # standing on the mat: step out
                            break
                        self.assertIn(q, g["tile"], (m, p, leg))
                        p = q
                self.assertIn(p, [(x, y) for x, y, _ in A._exits(m)], (m, legs))

    def test_just_inside_the_door_or_on_the_stairs(self):
        s = state("split-02")
        s["place"].update(map="VIRIDIAN_POKECENTER", x=3, y=7)
        self.assertIn("down 1 (out the door)", A.answer(s)["details"][0])
        s["place"].update(map="REDS_HOUSE_2F", x=7, y=1)                     # came up the stairs
        self.assertIn("(back onto the stairs)", A.answer(s)["details"][0])

    def test_outdoor_map_off_the_route_names_the_edge(self):
        s = state("split-02")                                                 # before Brock, on Route 3
        s["place"].update(map="ROUTE_3", x=10, y=6)
        a = A.answer(s)
        self.assertIn("walk off the left (west) edge of this map to PEWTER_CITY", a["do"])
        import walkable as W
        g = W.grid("ROUTE_3")
        for x, y in [(11, 5), (10, 6), (20, 10), (57, 0)]:   # Sol R7A: (11,5) hit a wall; R7B: (57,0) has a ledge
            if g["tile"].get((x, y)) not in g["walk"]:
                continue
            s["place"].update(map="ROUTE_3", x=x, y=y)
            d = A.answer(s)["details"][0]
            self.assertTrue(d.startswith("The way out"), d)
            p = (x, y)
            for leg in d.split("from where you stand: ")[1].split(". (x grows")[0].split(", "):
                word, n = leg.split()[:2]
                if word == "jump":
                    word, n = n, "1"
                for _ in range(int(n)):
                    q = dict(W.moves(g, p, people=False)).get(word)
                    if q is None and word == "left" and p[0] == 0:           # off the edge into Pewter City
                        q = (-1, p[1])
                    self.assertIsNotNone(q, (x, y, leg, p))
                    p = q
                self.assertTrue(leg.endswith(f"to ({p[0]},{p[1]})"), (x, y, leg, p))   # the stated end is real
            self.assertEqual(p[0], -1)

    def test_new_place_note_carries_the_must_see_lines(self):
        s = state("split-02")
        s["place"].update(map="VIRIDIAN_CITY", x=21, y=10)
        s["bag"] = [b for b in s["bag"] if b["item"] != "ANTIDOTE"]
        self.assertIn("buy 1-2 Antidotes", A.note(A.answer(s)))
        s["place"].update(map="REDS_HOUSE_2F", x=0, y=2)
        self.assertIn("The way out, from where you stand:", A.note(A.answer(s)))
        s["team"][0]["status"] = "poisoned"
        self.assertIn("poisoned: it loses 1 HP", A.note(A.answer(s)))
        self.assertIn("poisoned", A.poison_line(s))
        s["team"][0]["status"] = "ok"
        self.assertIsNone(A.poison_line(s))

    def test_pokemon_center_leads_back_to_the_town(self):
        s = state("split-02")
        s["place"].update(map="VIRIDIAN_POKECENTER", x=3, y=5)
        a = A.answer(s)
        self.assertIn("go to VIRIDIAN_CITY;", a["do"])
        self.assertIn("down 2 to (3,7) (out the door)", a["details"][0])

    def test_poisoned_outside_battle_is_told_to_cure(self):
        s = state("split-02")
        s["team"][0]["status"] = "poisoned"
        self.assertIn("poisoned: it loses 1 HP every 4 steps", A.text(A.answer(s, "where do I go?")))
        s["bag"] = [b for b in s["bag"] if b["item"] != "ANTIDOTE"] + [dict(item="ANTIDOTE", count=1)]
        self.assertIn("use an ANTIDOTE", A.text(A.answer(s, "where do I go?")))

    def test_antidotes_before_the_forest(self):
        s = state("split-02")
        s["place"].update(map="VIRIDIAN_CITY", x=21, y=10)
        s["bag"] = [b for b in s["bag"] if b["item"] != "ANTIDOTE"]
        self.assertIn("buy 1-2 Antidotes", A.text(A.answer(s)))
        s["bag"].append(dict(item="ANTIDOTE", count=1))
        self.assertNotIn("buy 1-2 Antidotes", A.text(A.answer(s)))

    def test_entering_the_gym_says_if_the_team_is_not_ready(self):
        s = state("split-02")
        s["place"].update(map="PEWTER_GYM", x=4, y=13)
        g = A.gym1_check(s)
        do = A.answer(s)["do"]
        self.assertFalse(g["ok"])
        self.assertIn("Not ready for Brock yet: train SQUIRTLE to about level 8", do)     # round 9: Brock alone + bypass
        self.assertIn("Train first: leave the gym", do)
        self.assertNotIn("walk to the boss", do)
        s["place"].update(x=4, y=6)                                                  # Sol R8A: no walk up to Brock
        a = A.answer(s, "Where now?")
        self.assertNotIn("talk (face up", A.text(a))
        self.assertIn("The way to the training grass (ROUTE_2), from where you stand: down 7 to (4,13) (out "
                      "the door to PEWTER_CITY)", A.text(a))
        s["place"].update(map="PEWTER_CITY", x=16, y=25)                             # before walking in
        self.assertIn("Not ready for Brock yet", A.answer(s)["do"])
        self.assertIn("then go to PEWTER_GYM. Its door is at (16,17)", A.answer(s)["do"])
        s = state("split-03")                                                          # a ready team: as before
        s["place"].update(map="PEWTER_CITY", x=16, y=25)
        self.assertIn("go to PEWTER_GYM", A.answer(s)["do"])
        self.assertNotIn("Not ready", A.answer(s)["do"])

    def test_with_coords(self):
        self.assertEqual(A.with_coords(["go to (3,4)", "up 2", "talk (press A)", "left 1"], (0, 0)),
                         ["go to (3,4)", "up 2 to (3,2)", "talk (press A)", "left 1 to (2,2)"])

    # ---- round 6 (dev copy): the Brock fight, turn by turn ----
    def brock_team(self, species, level):
        return dict(state("split-02"), team=[A._wild_mon(species, level)])

    def test_brock_levels_per_starter(self):
        for sp, lv in (("SQUIRTLE", 13), ("BULBASAUR", 13)):
            self.assertFalse(A.gym1_check(self.brock_team(sp, lv - 1))["ok"], sp)
            self.assertTrue(A.gym1_check(self.brock_team(sp, lv))["ok"], sp)
            self.assertEqual(A.gym1_check(self.brock_team(sp, 10))["level"][:2], (sp, lv))
        g = A.gym1_check(self.brock_team("CHARMANDER", 10))    # Ember is resisted: harder
        self.assertEqual(g["level"], ("CHARMANDER", 16, "CHARMELEON"))
        self.assertEqual(g["catch"][3], "BUTTERFREE")            # Confusion at 12 (pokered evos_moves.asm)
        self.assertIn("train CHARMANDER to about level 16 (it becomes CHARMELEON)", A.gym1_text(g))

    def test_brock_check_includes_the_gym_trainer_and_bide(self):
        g = A.gym1_check(self.brock_team("SQUIRTLE", 12))
        self.assertTrue(g["lines"][0].startswith("Against the gym trainer (DIGLETT L11, SANDSHREW L11)"))
        self.assertTrue(any(l.startswith("Against Brock (GEODUDE L12, ONIX L14)") for l in g["lines"]))
        # Bide only matters when Onix lasts more than 2 hits: then the advice says to use a move that does no damage
        self.assertFalse(any("Bide" in l for l in g["lines"]))                  # Bubble knocks Onix out fast
        notes = A.fight([A._wild_mon("CHARMANDER", 13)], A.TEAMS["Brock:1"]["party"][1:])[2]   # Onix alone
        self.assertTrue(any("Bide" in l and "GROWL" in l for l in notes))

    def test_heal_before_the_gym_and_where_to_train(self):
        s = self.brock_team("SQUIRTLE", 8)
        s["team"][0]["hp"] = s["team"][0]["max_hp"] - 3
        s["place"].update(map="PEWTER_CITY", x=18, y=30)
        a = A.answer(s)
        self.assertTrue(a["details"][0].startswith("Heal before the gym: "))
        self.assertIn("(13,25)", a["details"][0])                     # the Pewter Pokémon Center door
        self.assertIn("grass of Route 2 or Viridian Forest", A.text(a))
        s["team"][0]["hp"] = s["team"][0]["max_hp"]
        self.assertNotIn("Heal before the gym", A.text(A.answer(s)))
        s["bag"] = []
        self.assertIn("Pewter Mart (blue roof). Its door is at (23,17): stand at (23,18) and walk up into it.",
                      A.text(A.answer(s)))
        s["bag"] = [{"item": "POTION", "count": 2}]
        self.assertNotIn("Pewter Mart", A.text(A.answer(s)))

    def test_brock_check_assumes_full_pp_after_healing(self):          # Sol R6C point 1
        s = self.brock_team("SQUIRTLE", 13)
        verdicts = []
        for pp in (0, 1, None):
            s["team"][0]["moves"] = [dict(mv, pp=pp) for mv in s["team"][0]["moves"]]
            verdicts.append(A.gym1_check(s)["ok"])
        self.assertEqual(len(set(verdicts)), 1)
        win, _, _ = A.fight([dict(A._party_mon(s["team"][0]), moves=[dict(mv, pp=0) for mv in s["team"][0]["moves"]])],
                            A.TEAMS["Brock:1"]["party"])
        self.assertFalse(win)                                          # 0 PP really means no attacks

    def test_bide_attacks_spend_pp_and_hit_back(self):                 # Sol R6D
        mon = A._party_mon(self.brock_team("CHARMANDER", 16)["team"][0])
        low = dict(mon, moves=[dict(mv, pp=1) for mv in mon["moves"]])
        onix = [e for e in A.TEAMS["Brock:1"]["party"] if e["species"] == "ONIX"]
        win_low, left_low, _ = A.fight([low], onix)
        win_full, left_full, _ = A.fight([dict(mon, moves=[dict(mv, pp=None) for mv in mon["moves"]])], onix)
        self.assertLessEqual(left_low, left_full)
        self.assertFalse(win_low and left_low > 0.3)                   # R6D: 1 PP each "won" with 36% left

    def test_bide_without_rescue_labels_attack_risk(self):             # Sol R9A point 3
        s = self.brock_team("CHARMANDER", 13)
        me = A._party_mon(s["team"][0])
        foe = dict(A._foe(A.TEAMS["Brock:1"]["party"][1]), flags=["bide"])
        s["battle"] = {"kind": "trainer", "yours": dict(me, flags=[]), "enemy": foe, "trainer": "Brock:1"}
        a = A.battle_advice(s)
        self.assertTrue(a["do"].startswith("Use EMBER"))
        self.assertNotIn("GROWL", a["do"])
        self.assertIn("Risky fallback", a["why"])
        self.assertIn("storing energy with Bide", a["why"])
        self.assertIn("release turn are unknown", a["why"])

    def test_fight_carries_hp_over_and_counts_pp(self):
        me = A._wild_mon("SQUIRTLE", 13)
        one = A.fight([me], A.TEAMS["Brock:1"]["party"][:1])
        both = A.fight([me], A.TEAMS["Brock:1"]["party"])
        self.assertGreater(one[1], both[1])                      # HP carried over to Onix
        weak = dict(me, moves=[{"move": "BUBBLE", "pp": 1}])     # one Bubble, then nothing that hurts
        self.assertFalse(A.fight([weak], A.TEAMS["Brock:1"]["party"])[0])

    def test_ready_answer_for_brock(self):
        a = A.answer(self.brock_team("SQUIRTLE", 8), "is my team ready for Brock?")
        self.assertEqual(a["kind"], "ready")
        self.assertIn("train SQUIRTLE to about level 9", a["do"])  # round 9: Brock alone with a checked bypass
        self.assertEqual(A.gym1_check(self.brock_team("SQUIRTLE", 8))["level"][1], 13)  # both fights still need 13

    def test_luck_wiggles_are_merged(self):
        self.assertEqual(A.tidy(["up 4", "down 1", "up 1", "down 1", "up 5", "left 5"]), ["up 8", "left 5"])
        self.assertEqual(A.tidy(["up 2", "talk (press A)", "down 2"]), ["up 2", "talk (press A)", "down 2"])

    def test_damage_formula_matches_the_game(self):
        f = settings.fixture("damage_check.json")   # damage of every hit in the record game (not in the repo)
        counts = json.loads(f.read_text(encoding="utf-8"))["counts"]
        inside = sum(v for k, v in counts.items() if k.startswith("inside"))   # full values, knock-outs too
        self.assertGreater(inside, 200)
        self.assertGreater(counts.get("inside (knock-out, full value checked)", 0), 100)
        self.assertEqual(counts.get("OUTSIDE", 0), 0, counts)


class Round9(unittest.TestCase):
    brock_team = Advise.brock_team
    start_state = Advise.start_state

    def pewter(self, species="CHARMANDER", level=9, map_="PEWTER_CITY", x=16, y=18):
        s = self.brock_team(species, level)
        s["place"].update(map=map_, x=x, y=y, last_map="PEWTER_CITY")
        s["text_box"] = False
        return s

    def test_t11_2_n11_lab_and_grass_requires_oak_first(self):
        s = self.start_state("PALLET_TOWN", 10, 6)
        a = A.answer(s, "What is the walk to Oak's lab and to the tall grass north (Route 1)?")
        self.assertIn("tall grass", a["do"])
        self.assertIn("Oak must stop you", a["why"])
        self.assertNotIn("To get to OAKS_LAB", a["do"])
        self.assertTrue(any("up" in d for d in a["details"]))

    def test_lab_destination_after_oak_is_still_allowed(self):
        s = self.start_state("PALLET_TOWN", 10, 6, team=True)
        self.assertIn("OAKS_LAB", A.answer(s, "How do I get to Oak's lab?")["do"])

    def assert_walk(self, r, state_):
        self.assertIsNotNone(r)
        destinations = [step[0] for step in r["steps"][1:]] + [r["target"]]
        for ((m, p), how), dest in zip(r["steps"], destinations):
            if how[0] == "move":
                self.assertEqual(dest, (m, dict(A.W.moves(A._grid(m), p, people=r["people"]))[how[1]]))
            elif how[0] == "warp":
                q = dict(A.W.moves(A._grid(m), p, people=r["people"])).get(how[3]) if len(how) == 4 else p
                w = next(w for w in A._warps(m) if w[:2] == q)
                last = state_["place"].get("last_map") if m == state_["place"]["map"] else None
                self.assertEqual(dest, A._warp_dest(m, w, last))
            else:
                t, shift = A._conns(m)[how[2]]
                tg = A._grid(t)
                q = {"north": (p[0] + shift, tg["h"] - 1), "south": (p[0] + shift, 0),
                     "west": (tg["w"] - 1, p[1] + shift), "east": (0, p[1] + shift)}[how[2]]
                self.assertEqual(dest, (t, q))
                self.assertIn(tg["tile"][q], tg["walk"])

    def test_t11_2_n239_routes_around_defeated_bug_catcher(self):
        s = self.pewter(map_="VIRIDIAN_FOREST", x=2, y=19)
        s["place"]["last_map"] = "ROUTE_2"
        q = "A defeated bug catcher stands directly north and blocks the path. Which way leads to VIRIDIAN_FOREST_NORTH_GATE now?"
        a = A.answer(s, q)
        self.assertNotIn("up 17", A.text(a))
        r = A.walk_to(s, lambda m, p: m == "VIRIDIAN_FOREST_NORTH_GATE")
        self.assert_walk(r, s)
        self.assertTrue(r["people"])
        self.assertNotEqual(r["presses"][0], "up")
        self.assertNotIn(("VIRIDIAN_FOREST", (2, 18)), [step[0] for step in r["steps"]])

    def test_static_people_fallback_and_reported_blocker(self):
        g = dict(tile={(x, 0): 0 for x in range(3)}, walk={0}, w=3, h=1, pairs=set(), ledges=[],
                 people={(1, 0)}, balls=set())
        s = self.pewter(map_="TEST", x=0, y=0)
        with patch.object(A, "_grid", return_value=g), patch.object(A, "_exits", return_value=[]), \
                patch.object(A, "_conns", return_value={}), patch.object(A, "_warps", return_value=[]):
            goal = lambda m, p: p == (2, 0)
            self.assertFalse(A.walk_to(s, goal)["people"])
            self.assertIsNone(A.walk_to(s, goal, fallback=False))
            s["teacher_blocked"] = {"TEST": [(1, 0)]}
            self.assertIsNone(A.walk_to(s, goal))
            s.pop("teacher_blocked")
            g["people"] = set()  # a hidden/moved object must not be made a permanent wall
            self.assertTrue(A.walk_to(s, goal)["people"])

    def test_t11_2_n297_training_request_keeps_its_walk(self):
        s = self.pewter()
        q = "I want to train in the tall grass on ROUTE_2 near Viridian Forest, then return to Brock. What is the walk to that grass?"
        a = A.answer(s, q)
        self.assertEqual(a["kind"], "train")
        self.assertIn("The way to the training grass", A.note(a))
        self.assertIn("Training circuit", A.note(a))
        self.assertIn("Brock readiness", A.note(a))
        self.assertIn("half HP", A.text(a))
        self.assertEqual(A.intent("Which level should I train to for Brock?", s), "ready")

    def test_t10_4_n454_training_route_question(self):
        s = self.pewter()
        for q in ("How do I get to Route 2 grass from Pewter City?", "How do I get to Route 2 grass to train before Brock?",
                  "How do I train for Brock?", "I want to train before Brock"):
            a = A.answer(s, q)
            self.assertEqual(a["kind"], "train")
            self.assertIn("The way to the training grass", A.text(a))

    def test_each_training_leg_reaches_real_north_grass(self):
        for map_, x, y in (("PEWTER_GYM", 4, 12), ("PEWTER_CITY", 16, 18), ("ROUTE_2", 8, 1)):
            s = self.pewter(map_=map_, x=x, y=y)
            r = A.walk_to(s, lambda m, p: m == "ROUTE_2" and p in A.training_tiles())
            self.assert_walk(r, s)
            self.assertIn(r["target"][1], A.training_tiles())
            self.assertEqual(A._grid("ROUTE_2")["tile"][r["target"][1]], 0x52)
            if map_ == "PEWTER_GYM":
                self.assertEqual(r["maps"], ["PEWTER_GYM", "PEWTER_CITY", "ROUTE_2"])

    def test_training_grass_circuit_is_reversible_without_a_wall_bump(self):
        s = self.pewter(map_="ROUTE_2", x=7, y=7)
        a = A.training_advice(s, explicit=True)
        self.assertIn("you are in the grass", a["do"])
        line = next(d for d in a["details"] if d.startswith("Training circuit"))
        import re
        d, x, y, back = re.search(r", (\w+) 1 to \((\d+),(\d+)\), (\w+) 1 back", line).groups()
        g = A._grid("ROUTE_2")
        q = dict(A.W.moves(g, (7, 7)))[d]
        self.assertEqual(q, (int(x), int(y)))
        self.assertIn(q, A.training_tiles())
        self.assertEqual(dict(A.W.moves(g, q))[back], (7, 7))

    def test_training_purpose_survives_maps_healing_and_return(self):
        context = {}
        s = self.pewter(map_="PEWTER_GYM", x=4, y=12)
        A.answer(s, "How do I get to Route 2 grass to train?", context=context)
        self.assertEqual(context["purpose"], "train")
        for map_, x, y in (("PEWTER_CITY", 16, 18), ("ROUTE_2", 8, 1)):
            s["place"].update(map=map_, x=x, y=y)
            self.assertIn("The way to the training grass", A.note(A.answer(s, context=context)))
        s["place"].update(x=7, y=7)
        s["team"][0]["hp"] = 1
        a = A.answer(s, context=context)
        self.assertIn("Pause training and heal", a["do"])
        self.assertIn("PEWTER_CITY", a["do"])
        s["place"].update(map="PEWTER_POKECENTER", x=3, y=3)
        s["team"][0]["hp"] = s["team"][0]["max_hp"]
        self.assertIn("The way to the training grass", A.note(A.answer(s, context=context)))
        s["team"] = [A._wild_mon("SQUIRTLE", 11)]
        a = A.answer(s, context=context)
        self.assertIn("Ready for Brock", a["do"])
        self.assertIn("The way back to Brock", A.note(a))
        context["training_check"] = True
        s["story"]["next"] = {"id": "mt_moon", "goal": "Go to Mt Moon", "part": 2}
        A.answer(s, context=context)
        self.assertNotIn("purpose", context)
        self.assertNotIn("training_check", context)

    def test_t11_2_n277_named_gym_keeps_unready_warning(self):
        s = self.pewter()
        q = "How do I walk to the PEWTER_GYM door at (16,17), standing at (16,18)?"
        a = A.answer(s, q)
        self.assertIn("Not ready for Brock yet", a["do"])
        self.assertIn("Train first", a["do"])
        self.assertIn("The way to the training grass", A.note(a))
        self.assertIn("up 1", A.text(a))

    def test_named_forest_walk_retains_antidote_advice(self):
        s = self.pewter(map_="VIRIDIAN_CITY", x=23, y=28)
        s["bag"] = []
        s["money"] = 100
        a = A.answer(s, "How do I get to Route 2 from here?")
        self.assertIn("ROUTE_2", a["do"])
        self.assertIn("Before Viridian Forest", A.note(a))

    def test_t10_7_l11_brock_and_trainer_are_separate(self):
        s = self.pewter("SQUIRTLE", 11)
        self.assertTrue(A.gym1_check(s, keys=("Brock:1",))["ok"])
        self.assertFalse(A.gym1_check(s, keys=("JrTrainerM:1",))["ok"])
        a = A.answer(s, "Am I ready for Brock?")
        self.assertIn("ready", a["do"])
        self.assertNotIn("Not ready", a["do"])
        self.assertIn("Skip the optional trainer", a["do"])
        self.assertTrue(any("Against the gym trainer" in d for d in a["details"]))

    def test_brock_left_bypass_reaches_talk_tile_without_trainer_sight(self):
        s = self.pewter("SQUIRTLE", 11, "PEWTER_GYM", 4, 12)
        r = A.brock_route(s)
        self.assert_walk(r, s)
        self.assertEqual(r["target"], ("PEWTER_GYM", (4, 2)))
        self.assertTrue(r["people"])
        self.assertFalse(any(m == "PEWTER_GYM" and p[1] == 6 and p[0] >= 3 for (m, p), _ in r["steps"]))
        self.assertIn("at (4,2), face up and press A", A.text(A.answer(s)))

    def test_unavailable_bypass_does_not_claim_brock_only_readiness(self):
        s = self.pewter("SQUIRTLE", 11, "PEWTER_GYM", 4, 6)
        self.assertIsNone(A.brock_route(s))
        self.assertFalse(A.gym1_plan(s)[0]["ok"])
        self.assertIn("Train first", A.answer(s)["do"])
        s = self.pewter()
        self.assertFalse(A.gym1_check(s, keys=("Brock:1",))["ok"])

    def ui_memory(self, s, rows, cursor=None, **symbols):
        m = bytearray(65536)
        chars = {c: b for b, c in R.CHARS.items() if len(c) == 1}
        addr = R.A("wTileMap")
        m[addr:addr + 360] = bytes([0x7f]) * 360
        for y, text_ in rows.items():
            for x, c in enumerate(text_[:20]):
                m[addr + y * 20 + x] = chars.get(c, 0x7f)
        if cursor:
            m[addr + cursor[1] * 20 + cursor[0]] = 0xed
        for name, value in symbols.items():
            m[R.A(name)] = value
        return m

    def battle(self):
        s = self.pewter("SQUIRTLE", 13)
        foe = A._foe(A.TEAMS["Brock:1"]["party"][0])
        foe["moves"] = [{"move": mv, "pp": A.MOVES[mv]["pp"]} for mv in foe["moves"]]
        s["battle"] = dict(kind="trainer", yours=dict(A._party_mon(s["team"][0]), flags=[]),
                           enemy=dict(foe, flags=[]), trainer="Brock:1")
        return s

    def test_battle_command_cursor_moves_one_step_toward_fight(self):
        s = self.battle()
        m = self.ui_memory(s, {14: "          FIGHT PKMN", 16: "          ITEM  RUN"}, (15, 16))
        s["teacher_ui"] = A.battle_ui(m, s)
        self.assertEqual(s["teacher_ui"]["phase"], "commands")
        a = A.answer(s)
        self.assertTrue(a["do"].startswith("Press left once"))
        self.assertIn("Battle plan: Use BUBBLE", A.note(a))

    def test_move_cursor_uses_visible_remembered_row(self):
        s = self.battle()
        rows = {13 + i: "      " + mv["move"].replace("_", "") for i, mv in enumerate(s["battle"]["yours"]["moves"])}
        m = self.ui_memory(s, rows, (5, 13))
        s["teacher_ui"] = A.battle_ui(m, s)
        self.assertEqual(s["teacher_ui"]["phase"], "moves")
        self.assertTrue(A.answer(s)["do"].startswith("Press: down down a (one command): that picks BUBBLE"))  # R12 review S4
        s["teacher_ui"]["cursor"] = next(i for i, mv in enumerate(s["battle"]["yours"]["moves"]) if mv["move"] == "BUBBLE")
        self.assertTrue(A.answer(s)["do"].startswith("Press A once to select BUBBLE"))

    def test_t10_4_potion_advice_leaves_moves_then_selects_item_and_target(self):
        s = state("battle-055")
        s["teacher_ui"] = dict(phase="moves", cursor=2)
        self.assertTrue(A.answer(s)["do"].startswith("Press B once"))
        idx = [b["item"] for b in s["bag"]].index("POTION")
        s["teacher_ui"] = dict(phase="items", cursor=idx)
        self.assertTrue(A.answer(s)["do"].startswith("Press A once to select POTION"))
        target = next(i for i, t in enumerate(s["team"]) if t["species"] == "NIDOKING")
        s["teacher_ui"] = dict(phase="item_target", cursor=target, item="POTION")
        self.assertIn("NIDOKING to receive POTION", A.answer(s)["do"])

    def test_fainted_party_skips_fainted_members_without_opening_pkmn(self):
        s = self.battle()
        s["battle"]["yours"]["hp"] = 0
        s["team"][0]["hp"] = 0
        s["team"] += [dict(A._wild_mon("PIDGEY", 5), hp=0), A._wild_mon("SQUIRTLE", 14)]
        m = self.ui_memory(s, {14: "Bring out which", 16: "PKMN?"}, (0, 3))
        s["teacher_ui"] = A.battle_ui(m, s)
        self.assertEqual(s["teacher_ui"]["phase"], "party")
        self.assertIn("Press down once", A.answer(s)["do"])
        self.assertIn("forced replacement", A.answer(s)["do"])

    def test_switch_submenu_checks_selected_party_member(self):
        s = self.battle()
        s["battle"]["yours"].update(hp=0)
        s["team"][0]["hp"] = 0
        s["team"].append(A._wild_mon("BULBASAUR", 14))
        s["teacher_ui"] = dict(phase="switch", cursor=1, selected=0)
        self.assertTrue(A.answer(s)["do"].startswith("Press B once"))
        s["teacher_ui"]["selected"] = 1
        self.assertIn("Press up once toward SWITCH", A.answer(s)["do"])

    def test_unknown_battle_data_and_transient_cursors_request_observation(self):
        s = self.battle()
        s["teacher_ui"] = dict(phase="commands", cursor=(9, 14))
        s["battle"]["enemy"] = None
        self.assertTrue(A.answer(s)["do"].startswith("The battle is starting: press A"))  # R12: no bare "look and ask again"
        m = self.ui_memory(s, {14: "          FIGHT PKMN", 16: "          ITEM  RUN"})
        self.assertEqual(A.battle_ui(m, s)["phase"], "unknown")
        m[R.A("wTileMap") + 14 * 20 + 9] = 0xec  # unfilled arrow = selection already submitted
        self.assertEqual(A.battle_ui(m, s)["phase"], "unknown")

    def test_battle_notes_dedupe_cursor_changes_and_react_to_faint(self):
        sys.path.insert(0, str(ROOT / "arena"))
        import play
        s = self.battle()
        s["teacher_ui"] = dict(phase="commands", cursor=(15, 16))
        ctx = {}
        self.assertIsNotNone(play.battle_note(s, ctx))
        s["teacher_ui"]["cursor"] = (9, 14)
        self.assertIsNone(play.battle_note(s, ctx))
        s["battle"]["yours"]["hp"] = 4
        self.assertIsNotNone(play.battle_note(s, ctx))
        s["battle"]["yours"]["hp"] = 0
        s["teacher_ui"] = dict(phase="party", cursor=0, forced=True)
        self.assertIsNotNone(play.battle_note(s, ctx))
        self.assertIsNone(play.battle_note(s, ctx))
        s["battle"] = None
        self.assertIsNone(play.battle_note(s, ctx))
        self.assertNotIn("battle_seen", ctx)

    def test_teacher_context_comes_from_the_run_log(self):
        sys.path.insert(0, str(ROOT / "arena"))
        import play
        self.assertEqual(play.teacher_context([{"cmd": "start"}]), {})
        self.assertEqual(play.teacher_context([{"teacher_context": {"purpose": "train"}}, {"cmd": "look"}]),
                         {"purpose": "train"})

    def test_training_text_keeps_deferred_purpose(self):
        s = self.pewter(map_="PEWTER_POKECENTER", x=3, y=3)
        s["text_box"] = True
        a = A.answer(s, context={"purpose": "train"})
        self.assertIn("resume the training/healing trip", " ".join(a["details"]))

    def test_item_and_switch_screen_decoders_check_visible_choices(self):
        s = self.battle()
        s["bag"] = [dict(item="POTION", count=2)]
        m = self.ui_memory(s, {4: "      POTION x2", 6: "      CANCEL"}, (5, 4))
        self.assertEqual(A.battle_ui(m, s)["phase"], "items")
        m[R.A("wListScrollOffset")] = 1  # stale offset must not select an unseen item
        self.assertEqual(A.battle_ui(m, s)["phase"], "unknown")
        m = self.ui_memory(s, {14: "Use item on which", 16: "PKMN?"}, (0, 1),
                           wcf91=next(k for k, v in R.ITEMS.items() if v == "POTION"))
        ui = A.battle_ui(m, s)
        self.assertEqual((ui["phase"], ui["item"]), ("item_target", "POTION"))
        m = self.ui_memory(s, {12: "             SWITCH", 14: "             STATS", 16: "             CANCEL"},
                           (12, 14), wWhichPokemon=1)
        ui = A.battle_ui(m, s)
        self.assertEqual((ui["phase"], ui["cursor"], ui["selected"]), ("switch", 1, 1))

    def test_battle_text_is_one_step_and_unknown_choices_are_observed(self):
        s = self.battle()
        m = self.ui_memory(s, {14: "GEODUDE fainted!"})
        s["teacher_ui"] = A.battle_ui(m, s)
        self.assertTrue(A.answer(s)["do"].startswith("Press A once to advance"))
        m = self.ui_memory(s, {12: "GEODUDE fainted!", 14: "YES", 16: "NO"}, (0, 14))
        s["teacher_ui"] = A.battle_ui(m, s)
        self.assertTrue(A.answer(s)["do"].startswith("A YES/NO choice is showing"))  # R12: a concrete choice, not "look"

    def test_t10_4_n245_losing_weedle_switch_is_honest_and_executable(self):
        s = self.battle()
        lead = A._wild_mon("SQUIRTLE", 7)
        lead["hp"] = 1
        foe = A._wild_mon("WEEDLE", 9)
        s["team"] = [lead, A._wild_mon("WEEDLE", 4)]
        s["bag"] = []
        s["battle"].update(yours=dict(A._party_mon(lead), flags=[]), enemy=dict(foe, flags=[]))
        s["teacher_ui"] = dict(phase="moves", cursor=0)
        a = A.answer(s, "How can I survive the trainer Weedle?")
        self.assertIn("Losing fallback, not a safe rescue", a["why"])
        self.assertTrue(a["do"].startswith("Press B once"))
        self.assertIn("Switch to WEEDLE", a["details"][0])

    def test_new_place_context_is_saved_and_plain_view_stays_plain_without_emulator(self):
        import copy, io, tempfile
        from contextlib import redirect_stdout
        from types import SimpleNamespace
        sys.path.insert(0, str(ROOT / "arena"))
        import play
        ids = {v: k for k, v in R.MAPS.items()}
        s = self.pewter()
        s["place"]["map_id"] = ids["PEWTER_CITY"]
        fake = SimpleNamespace(m=bytearray(65536), where=lambda: (ids["ROUTE_2"], 8, 0), press=lambda _: None,
                               close=lambda: None, map_transitions=[])
        for group in ("teacher", "plain"):
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
                d = Path(tmp)
                (d / "meta.json").write_text(json.dumps(dict(group=group, budget=600)), encoding="utf-8")
                (d / "log.jsonl").write_text(json.dumps(dict(n=0, cmd="start", map="ROUTE_2")) + "\n", encoding="utf-8")
                out = io.StringIO()
                with patch.object(play, "Game", return_value=fake), patch.object(play, "view", return_value=(copy.deepcopy(s), "COMMON VIEW")), redirect_stdout(out):
                    play.play(SimpleNamespace(cmd="press", rest=["up"]), d)
                rows = [json.loads(line) for line in (d / "log.jsonl").read_text(encoding="utf-8").splitlines()]
                self.assertEqual(len(rows), 2)
                if group == "teacher":
                    self.assertEqual(rows[-1]["teacher_context"]["purpose"], "train")
                    self.assertIn("The way to the training grass", out.getvalue())
                    self.assertTrue((d / "auto.jsonl").exists())
                else:
                    self.assertNotIn("teacher_context", rows[-1])
                    self.assertEqual(out.getvalue(), "COMMON VIEW\nCommands used: 1 of 600\n")
                    self.assertFalse((d / "auto.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
