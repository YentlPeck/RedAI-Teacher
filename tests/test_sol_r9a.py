"""Sol R9A's concrete WRAM/log regressions. No emulator or running game access."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import settings  # noqa: E402
import advise as A
import read_state as R
import test_advise as fixtures


class SolR9A(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.Round9()

    def recorded_menu(self, name):
        raw = (fixtures.D / (name + ".wram")).read_bytes()
        s = R.state_from_wram(raw)
        m = bytearray(65536)
        m[0xc000:0xe000] = raw
        s["teacher_ui"] = A.battle_ui(m, s)
        return s

    def test_recorded_item_menus_leave_for_thunderbolt_then_open_fight(self):
        for name in ("battle-041", "battle-043"):
            with self.subTest(name=name):
                s = self.recorded_menu(name)
                self.assertEqual(s["teacher_ui"]["phase"], "items")
                if name == "battle-041":
                    self.assertEqual(s["bag"][s["teacher_ui"]["cursor"]]["item"], "SUPER_REPEL")
                else:
                    self.assertIsNone(s["teacher_ui"]["cursor"])  # list visible between cursor draws
                for q in (None, "The item menu highlights SUPER_REPEL. What now?"):
                    a = A.answer(s, q)
                    self.assertTrue(a["do"].startswith("Press B once to leave this menu"), a["do"])
                    self.assertIn("then Use THUNDERBOLT: FIGHT is top-left", a["do"])  # R12: concrete, no "ask again"
                    self.assertIn("Battle plan: Use THUNDERBOLT", A.note(a))
                # Reobserve the command screen after B, with ITEM still highlighted.
                m = self.f.ui_memory(s, {14: "          FIGHT PKMN", 16: "          ITEM  RUN"}, (9, 16))
                s["teacher_ui"] = A.battle_ui(m, s)
                self.assertTrue(A.answer(s)["do"].startswith("Press up once toward FIGHT"))
                s["teacher_ui"]["cursor"] = (9, 14)
                self.assertTrue(A.answer(s)["do"].startswith("Press A once to open FIGHT"))

    def test_wrong_party_switch_and_item_target_menus_leave_for_attack(self):
        s = self.recorded_menu("battle-041")
        for ui in (dict(phase="party", cursor=0, forced=False),
                   dict(phase="switch", cursor=0, selected=0),
                   dict(phase="item_target", cursor=0, item="POTION")):
            with self.subTest(phase=ui["phase"]):
                s["teacher_ui"] = ui
                self.assertTrue(A.answer(s)["do"].startswith("Press B once to leave this menu"))

    def test_heal_plan_leaves_switch_menus_and_wrong_item_target(self):
        s = fixtures.state("battle-055")  # POTION on NIDOKING, rather than an attack.
        for ui in (dict(phase="party", cursor=0, forced=False),
                   dict(phase="switch", cursor=0, selected=0),
                   dict(phase="item_target", cursor=0, item="ANTIDOTE")):
            with self.subTest(phase=ui["phase"]):
                s["teacher_ui"] = ui
                a = A.answer(s)
                self.assertTrue(a["do"].startswith("Press B once to leave this menu"))
                self.assertIn("Battle plan: Use POTION on NIDOKING", A.note(a))

    def test_split03_training_arrives_and_hands_back_to_brock(self):
        original = fixtures.state("split-03")
        self.assertEqual((original["place"]["map"], original["place"]["x"], original["place"]["y"]),
                         ("PEWTER_GYM", 4, 2))
        for full in (False, True):
            with self.subTest(full_hp_pp=full):
                s = copy.deepcopy(original)
                if full:
                    for t in s["team"]:
                        t["hp"] = t["max_hp"]
                        for mv in t["moves"]:
                            mv["pp"] = A.MOVES[mv["move"]]["pp"]
                ctx = dict(purpose="train", training_check=True)
                route = A.brock_route(s)
                self.assertEqual((route["cost"], route["steps"]), (0, []))
                for _ in range(2):
                    a = A.answer(s, context=ctx)
                    self.assertEqual(a["kind"], "way")
                    self.assertIn("face up and press A", a["do"])
                    self.assertNotIn("Return to PEWTER_GYM", a["do"])
                    self.assertNotIn("No checked bypass", A.text(a))
                    self.assertNotIn("purpose", ctx)
                    self.assertNotIn("training_check", ctx)
                self.assertIn("face up and press A", A.training_advice(s)["do"])

    def test_arrival_does_not_end_unready_training_or_skip_urgent_healing(self):
        for s in (self.f.pewter("CHARMANDER", 5, "PEWTER_GYM", 4, 2), fixtures.state("split-03")):
            if s["team"][0]["species"] != "CHARMANDER":
                s["team"][0]["hp"] = 1
            ctx = dict(purpose="train")
            a = A.answer(s, context=ctx)
            self.assertEqual(ctx["purpose"], "train")
            self.assertNotIn("face up and press A", a["do"])

    def bide_log_state(self):
        # arena/clean/t11-5.jsonl:1457/1462 recorded HP, levels, moves, PP, bag and active Bide.
        # Logs omit own stats: legal DV-10, zero-stat-EXP stats, as in Sol's review reconstruction.
        s = fixtures.state("split-03")
        base = A.SPECIES["SQUIRTLE"]["base"]
        stats = {k: (base[k] + 10) * 2 * 13 // 100 + 5 for k in ("atk", "def", "spd", "spc")}
        me = dict(species="SQUIRTLE", level=13, hp=20, max_hp=37, status="ok", flags=[],
                  types=["WATER"], stats=stats,
                  moves=[dict(move=m, pp=p) for m, p in (("TACKLE", 34), ("TAIL_WHIP", 30), ("BUBBLE", 22))])
        foe = dict(A._foe(A.TEAMS["Brock:1"]["party"][1]), hp=4, flags=["bide"])
        self.assertEqual((foe["species"], foe["level"], foe["max_hp"]), ("ONIX", 14, 36))
        s.update(team=[copy.deepcopy(me)], bag=[dict(item="POKE_BALL", count=11), dict(item="ANTIDOTE", count=2)])
        s["battle"] = dict(kind="trainer", trainer="Brock:1", yours=me, enemy=foe)
        m = self.f.ui_memory(s, {14: "          FIGHT PKMN", 16: "          ITEM  RUN"}, (9, 14))
        s["teacher_ui"] = A.battle_ui(m, s)
        return s

    def test_t11_5_active_bide_gives_risky_bubble_and_executable_steps(self):
        s = self.bide_log_state()
        plan = A.battle_advice(s)
        self.assertTrue(plan["do"].startswith("Use BUBBLE"))
        self.assertIn("Risky fallback", plan["why"])
        self.assertIn("stored damage and release turn are unknown", plan["why"])
        self.assertNotIn("for sure", plan["why"])
        for q in (None, "FIGHT is selected; ONIX is storing Bide. What now?"):
            a = A.answer(s, q)
            self.assertTrue(a["do"].startswith("Press A once to open FIGHT"))
            self.assertIn("Battle plan: Use BUBBLE", A.note(a))
            self.assertIn("Risky: Bide may release first", A.note(a))
        rows = {13 + i: "      " + mv["move"].replace("_", "") for i, mv in enumerate(s["battle"]["yours"]["moves"])}
        s["teacher_ui"] = A.battle_ui(self.f.ui_memory(s, rows, (5, 15)), s)
        self.assertTrue(A.answer(s)["do"].startswith("Press A once to select BUBBLE"))

    def test_bide_fallback_never_selects_empty_pp_or_status_move(self):
        s = self.bide_log_state()
        s["battle"]["yours"]["moves"][2]["pp"] = 0
        a = A.answer(s)
        self.assertIn("Battle plan: Use TACKLE", A.note(a))
        self.assertIn("Risky fallback", a["why"])


if __name__ == "__main__":
    unittest.main()
