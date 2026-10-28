"""Sol R9C's exact recorded WRAM inputs, scripted endings and failed exit repairs. Unit only."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import settings  # noqa: E402
import advise as A
import read_state as R


class SolR9C(unittest.TestCase):
    def recorded(self, name, **place):
        s = R.state_from_wram((settings.FixtureDir("record-1831000065-v2") / name).read_bytes())
        s.update(battle=None, text_box=False)
        s["place"].update(place)
        return s

    def test_fuji_talk_warp_keeps_the_recorded_face_up_a_on_repeated_asks(self):
        s = self.recorded("battle-042.wram", x=10, y=4)
        before = copy.deepcopy(s)
        self.assertEqual(s["place"]["map"], "POKEMON_TOWER_7F")
        self.assertEqual(A.match_record(s), (120, 2, 0))
        for _ in range(2):
            with patch.object(A, "_exit_walk", side_effect=AssertionError("Fuji is not an exit walk")):
                a = A.answer(s)
            route = next(t for t in a["details"] if t.startswith("Our route on this map"))
            self.assertIn("check it (face up, press A)", route)
            self.assertIn("his conversation takes you to MR_FUJIS_HOUSE", " ".join(a["details"]))
            self.assertNotIn("POKEMON_TOWER_6F", A.text(a))
            self.assertNotIn("stairs / door", A.text(a))
        self.assertEqual(s, before)

    def test_victory_road_keeps_the_recorded_down_step_onto_the_scripted_hole(self):
        s = self.recorded("split-17.wram", map="VICTORY_ROAD_3F", map_id=198, x=20, y=15)
        before = copy.deepcopy(s)
        self.assertEqual(A.match_record(s), (199, 38, 0))
        for _ in range(2):
            with patch.object(A, "_exit_walk", side_effect=AssertionError("the hole is not a replacement ladder")):
                a = A.answer(s)
            route = next(t for t in a["details"] if t.startswith("Our route on this map"))
            self.assertIn("up 1 to (20,14), right 3 to (23,14), down 1 to (23,15).", route)
            self.assertNotIn("(25,10)", route)
            self.assertNotIn("(27,15)", route)
            self.assertIn("scripted hole at (23,15)", " ".join(a["details"]))
        self.assertEqual(s, before)

    def test_replacement_suffix_cannot_relax_the_trapped_boulder(self):
        m = "VICTORY_ROAD_3F"
        exit_ = dict(tile=(27, 15), stand=(26, 15), step="right", target="VICTORY_ROAD_2F", side=None)
        self.assertIsNone(A.W.path(m, (23, 15), {exit_["stand"]}))
        presses = A.W.path(m, (23, 15), {exit_["stand"]}, people=False)
        self.assertIsNotNone(presses)
        g, pos, crossed = A.W.grid(m), (23, 15), []
        for d in presses:
            pos = dict(A.W.moves(g, pos, people=False))[d]
            crossed.append(pos)
        self.assertIn((24, 10, "SPRITE_BOULDER"), A._objects(m)[1])
        self.assertIn((24, 10), crossed)
        self.assertIn((25, 10), crossed)
        self.assertNotIn(g["tile"][(26, 10)], g["walk"])
        self.assertIsNone(A._exit_walk(m, (23, 15), exit_))
        # The final entry press must also respect boulders and observed blockers.
        one = dict(tile=(24, 10), stand=(23, 10), step="right", target="VICTORY_ROAD_2F", side=None)
        self.assertIsNone(A._exit_walk(m, (23, 10), one))

    def test_failed_replacement_keeps_story_actions_without_inventing_an_exit(self):
        s = self.recorded("battle-042.wram", map="PEWTER_MART", x=3, y=6)
        visit = dict(map="PEWTER_MART", points=[[2, 6, 0, 1], [3, 6, 0, 2]],
                     actions=[dict(frame=2, do="talk", x=3, y=6, dir="Up")])
        for no_exit in (False, True):
            with self.subTest(no_exit=no_exit), patch.object(A, "WALKS", [visit, dict(map="PEWTER_CITY")]), \
                    patch.object(A, "_travel_endings", return_value={}), \
                    patch.object(A, "match_record", return_value=(0, 1, 0)), \
                    patch.object(A, "_exit_walk", return_value=None) as suffix:
                if no_exit:
                    with patch.object(A, "_record_exit", return_value=None):
                        a = A.way_advice(s)
                    suffix.assert_not_called()
                else:
                    a = A.way_advice(s)
                    suffix.assert_called_once()
            route = next(t for t in a["details"] if t.startswith("Our route on this map"))
            self.assertIn("talk (face up, press A).", route)
            self.assertNotIn("right 1 to (4,6)", route)
            self.assertIn("No checked walk to PEWTER_CITY", " ".join(a["details"]))
            self.assertNotIn("stairs / door at (4,6)", A._record_exit_text("PEWTER_MART", "PEWTER_CITY", (3, 6), "right"))

    def test_real_inferred_warp_keeps_its_own_press_without_replacement(self):
        s = self.recorded("battle-042.wram", map="PEWTER_MART", x=3, y=6)
        visit = dict(map="PEWTER_MART", points=[[3, 5, 0, 1], [3, 6, 0, 2]], actions=[])
        with patch.object(A, "WALKS", [visit, dict(map="PEWTER_CITY")]), \
                patch.object(A, "_travel_endings", return_value={}), \
                patch.object(A, "match_record", return_value=(0, 1, 0)), \
                patch.object(A, "_exit_walk", side_effect=AssertionError("real warp needs no replacement")):
            a = A.way_advice(s)
        self.assertIn("down 1 to (3,7)", " ".join(a["details"]))

    def test_all_record_scripted_endings_and_nearby_non_transitions(self):
        # All 16 are among v4's 93 replaced exits: 1 talk, 2 holes, 6 Fly, 6 Dig, 1 Escape Rope.
        expected = {50, 79, 112, 120, 122, 146, 162, 163, 168, 174, 176, 179, 181, 187, 188, 199}
        kept = set()
        for i, w in enumerate(A.WALKS):
            nxt = next((q["map"] for q in A.WALKS[i + 1:] if q["map"] != w["map"]), None)
            text = A._scripted_ending(w["map"], nxt, w["points"][-1])
            if text:
                kept.add(i)
                self.assertFalse(A._real_inferred_exit(w["map"], nxt, w["points"][-1], A._last_step(w["points"])))
                self.assertEqual(A._exit_text(w["map"], nxt, w["points"][-1], A._last_step(w["points"])), text)
        self.assertEqual(kept, expected)
        for m, nxt, tile in [("POKEMON_TOWER_7F", "MR_FUJIS_HOUSE", (10, 5)),
                             ("POKEMON_TOWER_7F", "POKEMON_TOWER_6F", (10, 4)),
                             ("VICTORY_ROAD_3F", "VICTORY_ROAD_2F", (3, 5)),
                             ("VICTORY_ROAD_3F", "VICTORY_ROAD_2F", (27, 8)),
                             ("POKEMON_MANSION_3F", "POKEMON_MANSION_1F", (19, 14))]:
            with self.subTest(map=m, next_map=nxt, tile=tile):
                self.assertIsNone(A._scripted_ending(m, nxt, tile))


if __name__ == "__main__":
    unittest.main()
