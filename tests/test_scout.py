"""Scout pass: decoded memory, static maps and completed R7/R8 log excerpts. Never open an emulator.

scout_logs.json preserves the real inputs; screen tiles and team stats below are reconstructed test inputs,
not claimed to be RAM recorded at those turns. All temporary files stay in this test directory.
scout_logs.json is a test fixture (game log excerpts, not in the repo; see README).
"""
import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "arena")]
import settings  # noqa: E402
import advise as A
import play as P
import read_state as R
import test_advise as fixtures

LOGS = json.loads(settings.fixture("scout_logs.json").read_text(encoding="utf-8"))["runs"]
IDS = {v: k for k, v in R.MAPS.items()}


def row(run, n):
    return copy.deepcopy(next(r for r in LOGS[run] if r["n"] == n))


class Scout(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.Round9()

    def logged_state(self, run, n):
        r = row(run, n)
        s = self.f.pewter("CHARMANDER", 5, r["map"], r.get("x", 5), r.get("y", 6))
        s["place"]["map_id"] = IDS[r["map"]]
        s["story"]["done"] = r["done"]
        s["story"]["next"] = next(dict(id=i, goal=g, part=p, done=False) for i, g, _, p in R.MILESTONES
                                  if i not in r["done"])
        s["text_box"] = r.get("text", False)
        s["teacher_story"] = dict(rival_done="parcel" in r["done"], lab_script="SCRIPT_OAKSLAB_NOOP")
        return s

    def screen(self, s, rows, cursor=None):
        return P.teacher_state(s, self.f.ui_memory(s, rows, cursor))

    def test_pending_rival_precedes_t11_2_n53_exit_request(self):
        s = self.logged_state("t11-2-haiku-teacher", 51)
        s["teacher_story"].update(rival_done=False, lab_script="SCRIPT_OAKSLAB_RIVAL_CHALLENGES_PLAYER")
        a = A.answer(s, row("t11-2-haiku-teacher", 53)["q"])
        self.assertTrue(a["do"].startswith("Press down once"))
        self.assertIn("rival challenge", a["do"])
        self.assertNotIn("To get to PALLET_TOWN", a["do"])
        self.assertEqual(A.story_step(s)[0], "lab_rival")

    def test_rival_trigger_row_is_reachable_from_t11_2_n44_starter_tile(self):
        s = self.logged_state("t11-2-haiku-teacher", 45)
        s["text_box"] = False
        s["teacher_story"].update(rival_done=False, lab_script="SCRIPT_OAKSLAB_RIVAL_CHALLENGES_PLAYER")
        a = A.answer(s, row("t11-2-haiku-teacher", 44)["q"])
        self.assertIn("row 6", a["do"])
        r = A.walk_to(s, lambda m, p: m == "OAKS_LAB" and p[1] == 6)
        self.f.assert_walk(r, s)
        self.assertIn("The way to the rival trigger", A.note(a))

    def test_story_requires_observed_completion_not_repeated_advice_or_player_claims(self):
        s = self.logged_state("t11-2-haiku-teacher", 51)
        s["teacher_story"].update(rival_done=False, lab_script="SCRIPT_OAKSLAB_RIVAL_CHALLENGES_PLAYER")
        ctx = {}
        for _ in range(3):
            A.answer(s, "I finished the rival and got the Parcel. How do I leave?", context=ctx)
            self.assertEqual(A.story_step(s)[0], "lab_rival")
        s["teacher_story"].update(rival_done=True, lab_script="SCRIPT_OAKSLAB_PLAYER_WATCH_RIVAL_EXIT")
        self.assertEqual(A.story_step(s)[0], "rival_exit")
        self.assertIn("script finish", A.answer(s)["do"])
        s["teacher_story"]["lab_script"] = "SCRIPT_OAKSLAB_NOOP"
        self.assertEqual(A.story_step(s)[0], "get_parcel")
        self.assertIn("PALLET_TOWN", A.answer(s, "How do I leave for Pallet Town?")["do"])

    def test_story_parcel_bag_and_badge_are_separate_checks(self):
        s = self.logged_state("t11-2-haiku-teacher", 51)
        s["teacher_story"]["rival_done"] = True
        s["bag"] = []
        self.assertEqual(A.story_step(s)[0], "get_parcel")
        s["bag"] = [dict(item="OAKS_PARCEL", count=1)]
        self.assertEqual(A.story_step(s)[0], "deliver_parcel")
        s["story"]["done"].append("parcel")
        self.assertEqual(A.story_step(s)[0], "pokedex")
        s["story"]["done"].append("pokedex")
        self.assertEqual(A.story_step(s)[0], "brock")
        self.assertIn("Boulder Badge", A.story_step(s)[2])
        s["story"]["next"] = dict(id="mt_moon", goal="Continue", part=2)
        self.assertIsNone(A.story_step(s))

    def test_teacher_only_story_reads_real_event_bit_and_script_table(self):
        s = self.logged_state("t11-2-haiku-teacher", 51)
        s.pop("teacher_story")
        m = self.f.ui_memory(s, {})
        m[R.A("wOaksLabCurScript")] = A.LAB_SCRIPTS.index("SCRIPT_OAKSLAB_RIVAL_CHALLENGES_PLAYER")
        self.assertFalse(P.teacher_state(s, m)["teacher_story"]["rival_done"])
        bit = R.EVENTS["EVENT_BATTLED_RIVAL_IN_OAKS_LAB"]
        m[R.A("wEventFlags") + bit // 8] |= 1 << (bit % 8)
        private = P.teacher_state(s, m)
        self.assertTrue(private["teacher_story"]["rival_done"])
        self.assertEqual(private["teacher_story"]["lab_script"], "SCRIPT_OAKSLAB_RIVAL_CHALLENGES_PLAYER")
        self.assertNotIn("teacher_story", s)
        m[R.A("wOaksLabCurScript")] = 255
        self.assertIsNone(P.teacher_state(s, m)["teacher_story"]["lab_script"])

    def test_first_failed_direction_can_be_a_turn_second_confirms_block(self):
        pos = (IDS["VIRIDIAN_FOREST"], 2, 19)
        ctx = {}
        P.observe_walk(ctx, pos, pos, "up", True)
        self.assertEqual(ctx["walk_block"]["count"], 1)
        P.observe_walk(ctx, pos, pos, "up", True)
        self.assertEqual(ctx["walk_block"]["tile"], [2, 18])
        self.assertEqual(ctx["walk_block"]["count"], 2)
        P.observe_walk(ctx, pos, (pos[0], 1, 19), "left", True)
        self.assertNotIn("walk_block", ctx)

    def test_dialogue_battle_and_script_control_cannot_create_collision_walls(self):
        m = bytearray(65536)
        self.assertTrue(P.quiet_walk(m))
        for symbol, value in (("wIsInBattle", 1), ("wFontLoaded", 1), ("wJoyIgnore", 15), ("wd730", 1)):
            with self.subTest(symbol=symbol):
                m[R.A(symbol)] = value
                self.assertFalse(P.quiet_walk(m))
                ctx = {"walk_block": {"count": 2}}
                P.observe_walk(ctx, (1, 2, 3), (1, 2, 3), "up", P.quiet_walk(m))
                self.assertNotIn("walk_block", ctx)
                m[R.A(symbol)] = 0

    def test_real_t11_2_n238_block_replans_default_recorded_walk(self):
        s = self.logged_state("t11-2-haiku-teacher", 238)
        ctx = {}
        pos = (IDS["VIRIDIAN_FOREST"], 2, 19)
        with patch.object(P, "MAX_PRESSES", 20):     # R16: this real t11 row was played under the old 20-press rule
            keys = P.parse_buttons(row("t11-2-haiku-teacher", 238)["keys"])
        for bt in keys:
            P.observe_walk(ctx, pos, pos, bt, True)
        a = A.answer(s, context=ctx)
        self.assertNotIn("up 17", A.text(a))
        self.assertIn("left", A.text(a))
        r = A.walk_to(dict(s, teacher_blocked={"VIRIDIAN_FOREST": [(2, 18)]}),
                      lambda m, p: m == "VIRIDIAN_FOREST_NORTH_GATE")
        self.f.assert_walk(r, s)
        self.assertNotIn(("VIRIDIAN_FOREST", (2, 18)), [step[0] for step in r["steps"]])

    def test_reported_blocker_is_retained_for_followup_ask(self):
        s = self.logged_state("t11-2-haiku-teacher", 238)
        ctx = {}
        A.answer(s, row("t11-2-haiku-teacher", 239)["q"], context=ctx)
        self.assertEqual(ctx["walk_block"]["tile"], [2, 18])
        self.assertNotIn("up 17", A.text(A.answer(s, "Where now?", context=ctx)))

    def test_repair_and_rejoin_keep_observed_blocker_on_relaxed_pass(self):
        blocked = {(2, 18)}
        pts = [[2, 19, 0, 0], [2, 16, 0, 10]]
        fixed = A.repair("VIRIDIAN_FOREST", pts, blocked)
        self.assertTrue(any(p[0] != 2 for p in fixed))
        join = A.rejoin("VIRIDIAN_FOREST", (2, 19), pts, blocked)
        self.assertIsNotNone(join)
        self.assertNotIn(join[2], blocked)
        grid = dict(tile={(x, 0): 0 for x in range(3)}, walk={0}, w=3, h=1,
                    pairs=set(), ledges=[], people={(1, 0)}, balls=set())
        with patch.object(A.W, "grid", return_value=grid):
            self.assertIsNone(A.repair("TEST", [[0, 0, 0, 0], [2, 0, 0, 1]], {(1, 0)}))

    def test_ledge_jump_cannot_land_on_or_jump_through_observed_person(self):
        g = dict(tile={(0, 0): 1, (0, 1): 2, (0, 2): 1}, walk={1}, w=1, h=3,
                 pairs=set(), ledges=[("down", 1, 2)], people=set(), balls=set())
        self.assertIn(("down", (0, 2)), list(A.W.moves(g, (0, 0))))
        for blocked in ({(0, 1)}, {(0, 2)}):
            self.assertEqual(list(A.W.moves(g, (0, 0), people=False, blocked=blocked)), [])

    def test_three_repeated_texts_count_reopened_dialogue_and_emit_once(self):
        s = self.logged_state("t10-2b-haiku-teacher", 155)
        s["teacher_screen"] = dict(rows=["PKMN around the", "world wait for", "you, RED!"], cursor=False)
        ctx = {}
        self.assertFalse(P.observe_text(ctx, s))
        s["text_box"] = False
        self.assertFalse(P.observe_text(ctx, s))
        s["text_box"] = True
        self.assertFalse(P.observe_text(ctx, s))
        self.assertTrue(P.observe_text(ctx, s))
        self.assertFalse(P.observe_text(ctx, s))
        for _ in range(20):
            P.observe_text(ctx, s)
        self.assertEqual(len(ctx["text_loop"]["recent"]), 6)

    def test_changing_dialogue_story_tile_or_battle_resets_repeat_recovery(self):
        s = self.logged_state("t10-2b-haiku-teacher", 155)
        s["teacher_screen"] = dict(rows=["a different page"], cursor=False)
        ctx = {}
        for i in range(6):
            s["teacher_screen"]["rows"] = [f"Page {i}"]
            self.assertFalse(P.observe_text(ctx, s))
        s["place"]["x"] += 1
        self.assertFalse(P.observe_text(ctx, s))
        self.assertEqual(ctx["text_loop"]["repeats"], 1)
        s["story"]["done"] = s["story"]["done"] + ["badge1"]
        self.assertFalse(P.observe_text(ctx, s))
        self.assertEqual(ctx["text_loop"]["repeats"], 1)
        s["battle"] = dict(kind="wild")
        self.assertFalse(P.observe_text(ctx, s))
        self.assertNotIn("text_loop", ctx)

    def test_t10_2b_n159_oak_dialogue_closes_once_and_supplies_exit(self):
        s = self.logged_state("t10-2b-haiku-teacher", 158)
        s = self.screen(s, {12: "PKMN around the", 14: "world wait for", 16: "you, RED!"})
        a = A.answer(s, row("t10-2b-haiku-teacher", 159)["q"])
        self.assertTrue(a["do"].startswith("Press B once"))
        self.assertIn("PALLET_TOWN", A.note(a))
        self.assertIn("stop pressing A", A.note(a))

    def test_t10_5b_n205_customer_dialogue_retains_actual_shop_answer(self):
        s = self.logged_state("t10-5b-haiku-teacher", 204)
        s = self.screen(s, {14: "No! POTIONs are", 16: "all sold out."})
        a = A.answer(s, row("t10-5b-haiku-teacher", 205)["q"])
        self.assertTrue(a["do"].startswith("Press B once"))
        self.assertIn("customer", a["why"])
        self.assertIn("stand at (2,5)", A.note(a))
        self.assertIn("pick BUY", A.note(a))

    def test_optional_oak_close_requires_both_handover_facts_and_no_choice_cursor(self):
        s = self.logged_state("t10-2b-haiku-teacher", 158)
        s = self.screen(s, {12: "world wait for", 14: "YES", 16: "NO"}, (0, 14))
        self.assertNotIn("Press B", A.answer(s)["do"])
        s["teacher_screen"]["cursor"] = False
        s["story"]["done"].remove("pokedex")
        self.assertNotIn("Press B", A.answer(s)["do"])

    def test_repeated_naming_quantity_and_mandatory_choices_never_guess_a_button(self):
        s = self.logged_state("t10-5b-haiku-teacher", 204)
        for rows in (["Your NAME?", "A B C D E"], ["HOW MANY?", "x02"], ["YES", "NO"]):
            with self.subTest(rows=rows):
                s["teacher_screen"] = dict(rows=rows, cursor=True)
                ctx = {}
                for _ in range(3):
                    P.observe_text(ctx, s)
                a = A.answer(s, context=ctx)
                # R13 (on purpose): a repeated screen gets an exact press, never only "stop repeating" / "look".
                self.assertNotIn("Stop repeating", a["do"])
                self.assertIn("The text box says", a["do"])
                self.assertRegex(a["do"], r"press START|up or down|Press B to say NO")

    def test_text_question_keeps_destination_until_the_text_closes(self):
        s = self.logged_state("t10-2b-haiku-teacher", 158)
        s = self.screen(s, {14: "world wait for"})
        ctx = {}
        A.answer(s, "How do I get to Viridian City?", context=ctx)
        self.assertEqual(ctx["deferred_target"], "VIRIDIAN_CITY")
        s["text_box"] = False
        a = A.answer(s, context=ctx)
        self.assertIn("To get to VIRIDIAN_CITY", a["do"])
        self.assertNotIn("deferred_target", ctx)

    def test_zero_pp_move_is_never_the_selected_attack(self):
        s = self.f.battle()
        for mon in (s["team"][0], s["battle"]["yours"]):
            for mv in mon["moves"]:
                if mv["move"] == "BUBBLE":
                    mv["pp"] = 0
        a = A.battle_advice(s)
        self.assertNotIn("Use BUBBLE", a["do"])
        s["teacher_ui"] = dict(phase="moves", cursor=0)
        rejected = A.battle_step(s, dict(do="Use BUBBLE.", why="stale choice", details=[]))
        self.assertNotIn("select BUBBLE", rejected["do"])

    def test_no_damage_or_no_pp_switches_to_named_usable_party_member(self):
        for move, pp in (("TACKLE", 0), ("GROWL", 40), ("TACKLE", 35)):
            with self.subTest(move=move, pp=pp):
                s = self.f.battle()
                lead = dict(A._wild_mon("PIDGEY", 10), moves=[dict(move=move, pp=pp)])
                foe = A._wild_mon("GASTLY", 5)
                s["team"] = [lead, A._wild_mon("CHARMANDER", 16)]
                s["battle"].update(yours=A._party_mon(lead), enemy=foe)
                s["teacher_ui"] = dict(phase="commands", cursor=(9, 14))
                a = A.answer(s)
                self.assertIn("Switch to CHARMANDER", A.note(a))
                self.assertTrue(a["do"].startswith("Press right once toward PKMN"))

    def test_battle_step_cannot_execute_an_immune_or_status_move(self):
        s = self.f.battle()
        s["battle"]["yours"] = A._party_mon(dict(A._wild_mon("PIDGEY", 10),
                                  moves=[dict(move="TACKLE", pp=35), dict(move="GROWL", pp=40)]))
        s["battle"]["enemy"] = A._wild_mon("GASTLY", 5)
        s["teacher_ui"] = dict(phase="moves", cursor=0)
        for mv in ("TACKLE", "GROWL"):
            a = A.battle_step(s, dict(do="Use " + mv + ".", why="stale plan", details=[]))
            self.assertNotIn("to select", a["do"])

    def test_active_bide_uses_item_instead_of_no_damage_move_or_blind_attack(self):
        s = self.f.battle()
        s["battle"]["enemy"]["flags"] = ["bide"]
        s["battle"]["yours"]["hp"] = 1
        s["bag"] = [dict(item="POTION", count=1)]
        a = A.battle_advice(s)
        self.assertEqual(a["do"], "Use POTION on SQUIRTLE.")
        self.assertIn("does not guarantee survival", a["why"])
        self.assertNotIn("GROWL", a["do"])

    def test_training_stop_and_heal_rules_are_checked_from_current_team(self):
        for change in ("half_hp", "poison", "empty_pp", "fainted"):
            with self.subTest(change=change):
                s = self.f.pewter("CHARMANDER", 9, "ROUTE_2", 7, 7)
                mon = s["team"][0]
                if change in ("half_hp", "fainted"):
                    mon["hp"] = mon["max_hp"] // 2 if change == "half_hp" else 0
                elif change == "poison":
                    mon["status"] = "poisoned"
                else:
                    for move in mon["moves"]:
                        move["pp"] = 0
                self.assertTrue(A.answer(s, context={"purpose": "train"})["do"].startswith("Pause training and heal"))
        s = self.f.pewter("SQUIRTLE", 11, "ROUTE_2", 7, 7)
        self.assertTrue(A.answer(s, context={"purpose": "train"})["do"].startswith("Ready for Brock"))

    def run_mocked_press(self, s, memory, history, keys, group="teacher"):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            d = Path(tmp)
            (d / "meta.json").write_text(json.dumps(dict(group=group, budget=600)), encoding="utf-8")
            (d / "log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in history), encoding="utf-8")
            p = s["place"]
            fake = SimpleNamespace(m=memory, where=lambda: (p["map_id"], p["x"], p["y"]),
                                   press=lambda _: None, close=lambda: None, map_transitions=[])
            out = io.StringIO()
            with patch.object(P, "Game", return_value=fake), patch.object(P, "view", return_value=(copy.deepcopy(s), "COMMON VIEW")), redirect_stdout(out):
                P.play(SimpleNamespace(cmd="press", rest=keys), d)
            logs = [json.loads(l) for l in (d / "log.jsonl").read_text(encoding="utf-8").splitlines()]
            notes = [json.loads(l) for l in (d / "auto.jsonl").read_text(encoding="utf-8").splitlines()] if (d / "auto.jsonl").exists() else []
            return out.getvalue(), logs, notes

    def test_auto_text_recovery_is_logged_once_without_adding_a_command(self):
        s = self.logged_state("t10-2b-haiku-teacher", 158)
        m = self.f.ui_memory(s, {12: "PKMN around the", 14: "world wait for", 16: "you, RED!"})
        m[R.A("wFontLoaded")] = 1
        ctx = {}
        private = P.teacher_state(s, m)
        for _ in range(2):
            P.observe_text(ctx, private)
        history = [dict(n=0, cmd="start", map="OAKS_LAB", teacher_context=ctx)]
        out, logs, notes = self.run_mocked_press(s, m, history, ["a"])
        self.assertIn("TEACHER (repeated text)", out)
        self.assertEqual(len(logs), 2)
        self.assertEqual([n["kind"] for n in notes], ["repeated text"])
        out, logs, notes = self.run_mocked_press(s, m, logs, ["a"])
        self.assertNotIn("TEACHER (repeated text)", out)
        self.assertEqual(notes, [])

    def test_auto_block_recovery_includes_a_different_checked_walk(self):
        s = self.logged_state("t11-2-haiku-teacher", 238)
        m = bytearray(65536)
        out, logs, notes = self.run_mocked_press(s, m, [dict(n=0, cmd="start", map="VIRIDIAN_FOREST")], ["up*6"])   # R16: max 6 (was up*17)
        self.assertIn("TEACHER (blocked walk)", out)
        self.assertIn("left", out)
        self.assertNotIn("up 17", out)
        self.assertEqual(len(logs), 2)
        self.assertEqual(notes[0]["kind"], "blocked walk")

    def test_plain_group_has_no_teacher_loop_memory_or_extra_notes(self):
        s = self.logged_state("t11-2-haiku-teacher", 238)
        out, logs, notes = self.run_mocked_press(s, bytearray(65536), [dict(n=0, cmd="start", map="VIRIDIAN_FOREST")],
                                                ["up*6"], group="plain")   # R16: max 6 (was up*17)
        self.assertEqual(out, "COMMON VIEW\nCommands used: 1 of 600\n")
        self.assertNotIn("teacher_context", logs[-1])
        self.assertEqual(notes, [])

    def test_training_check_waits_for_battle_text_then_stops_training_when_ready(self):
        s = self.f.pewter("SQUIRTLE", 11, "ROUTE_2", 7, 7)
        s["place"]["map_id"] = IDS["ROUTE_2"]
        s["text_box"] = True
        m = self.f.ui_memory(s, {14: "Gained EXP!"})
        m[R.A("wFontLoaded")] = 1
        history = [dict(n=0, cmd="start", map="ROUTE_2", battle=True, teacher_context=dict(purpose="train"))]
        _, logs, notes = self.run_mocked_press(s, m, history, ["a"])
        self.assertTrue(logs[-1]["teacher_context"]["training_check"])
        self.assertFalse(any(n["kind"] == "training check" for n in notes))
        s["text_box"] = False
        out, logs, notes = self.run_mocked_press(s, bytearray(65536), logs, ["a"])
        self.assertIn("Ready for Brock", out)
        self.assertEqual([n["kind"] for n in notes], ["training check"])
        self.assertNotIn("training_check", logs[-1]["teacher_context"])

    def test_confirmed_story_step_is_announced_after_text_without_changing_map(self):
        s = self.logged_state("t11-2-haiku-teacher", 238)
        s["text_box"] = True
        m = self.f.ui_memory(s, {14: "Take these with you!"})
        m[R.A("wFontLoaded")] = 1
        history = [dict(n=0, cmd="start", map=s["place"]["map"], teacher_context=dict(story_step="pokedex"))]
        _, logs, notes = self.run_mocked_press(s, m, history, ["a"])
        self.assertFalse(any(n["kind"] == "story step" for n in notes))
        s["text_box"] = False
        out, logs, notes = self.run_mocked_press(s, bytearray(65536), logs, ["a"])
        self.assertEqual([n["kind"] for n in notes], ["story step"])
        self.assertIn("Boulder Badge", out)
        self.assertEqual(logs[-1]["teacher_context"]["story_step"], "brock")

    def test_battle_note_history_is_bounded_and_clears_after_battle(self):
        s = self.f.battle()
        s["teacher_ui"] = dict(phase="commands", cursor=(9, 14))
        ctx = dict(battle_seen=[str(i) for i in range(24)])
        self.assertIsNotNone(P.battle_note(s, ctx))
        self.assertEqual(len(ctx["battle_seen"]), 24)
        s["battle"] = None
        P.battle_note(s, ctx)
        self.assertNotIn("battle_seen", ctx)


if __name__ == "__main__":
    unittest.main()
