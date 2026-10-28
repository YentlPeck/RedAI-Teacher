"""Warp entry is the last press on a map; unit checks against static pokered data."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import settings  # noqa: E402
import advise as A
import read_state as R


class EdgePress(unittest.TestCase):
    def state(self, map_, pos, last="PALLET_TOWN"):
        s = R.state_from_wram((settings.fixture("start.wram")).read_bytes())
        s["place"].update(map=map_, x=pos[0], y=pos[1], last_map=last)
        return s

    def route(self, s, target):
        r = A.walk_to(s, lambda m, p: m == target)
        self.assertIsNotNone(r)
        return r

    def test_house_stairs_warp_on_the_single_entry_step(self):
        s = self.state("REDS_HOUSE_2F", (6, 1))
        r = self.route(s, "REDS_HOUSE_1F")
        self.assertEqual(r["cost"], 1)
        self.assertEqual(len(r["steps"]), 1)
        self.assertEqual(r["target"], ("REDS_HOUSE_1F", (7, 1)))
        self.assertEqual(r["exit"], ("warp", "REDS_HOUSE_1F", None, "right"))
        self.assertTrue(A.walk_words(s, r)[0].startswith("right 1 to (7,1)"))
        self.assertEqual(len(A.walk_words(s, r)), 1)

    def test_north_gate_entry_press_leaves_the_map(self):
        s = self.state("VIRIDIAN_FOREST_NORTH_GATE", (4, 2), "ROUTE_2")
        r = self.route(s, "ROUTE_2")
        self.assertEqual(r["cost"], 3)
        self.assertEqual(r["exit"], ("warp", "ROUTE_2", None, "up"))
        self.assertEqual(A.walk_words(s, r)[-1], "up 1 to (5,0) (out the door to ROUTE_2)")
        self.assertNotIn(", up 1 (out the door", ", ".join(A.walk_words(s, r)))

    def test_both_house_mats_warp_on_the_single_entry_step(self):
        for x in (2, 3):
            with self.subTest(x=x):
                s = self.state("REDS_HOUSE_1F", (x, 6))
                r = self.route(s, "PALLET_TOWN")
                self.assertEqual(r["cost"], 1)
                self.assertEqual(A.walk_words(s, r), [f"down 1 to ({x},7) (out the door to PALLET_TOWN)"])

    def test_starting_on_the_house_mat_keeps_the_outward_press(self):
        s = self.state("REDS_HOUSE_1F", (3, 7))
        r = self.route(s, "PALLET_TOWN")
        self.assertEqual(r["cost"], 1)
        self.assertEqual(A.walk_words(s, r), ["down 1 (out the door to PALLET_TOWN)"])
        self.assertEqual(A.way_out(s, ["PALLET_TOWN"])[3], ["down 1 (out the door)"])

    def test_starting_on_the_gate_top_door_keeps_the_outward_press(self):
        s = self.state("VIRIDIAN_FOREST_NORTH_GATE", (5, 0), "ROUTE_2")
        r = self.route(s, "ROUTE_2")
        self.assertEqual(r["cost"], 1)
        self.assertEqual(A.walk_words(s, r), ["up 1 (out the door to ROUTE_2)"])
        self.assertEqual(A.way_out(s, ["ROUTE_2"])[3], ["up 1 (out the door)"])

    def test_arriving_on_stairs_does_not_add_an_outward_warp(self):
        s = self.state("REDS_HOUSE_2F", (6, 1))
        r = self.route(s, "PALLET_TOWN")
        self.assertEqual(r["steps"][0], (("REDS_HOUSE_2F", (6, 1)), ("warp", "REDS_HOUSE_1F", None, "right")))
        self.assertEqual(r["steps"][1][0], ("REDS_HOUSE_1F", (7, 1)))
        self.assertEqual(r["steps"][1][1][0], "move")
        self.assertTrue(all(len(how) == 4 for _, how in r["steps"] if how[0] == "warp"))

    def test_way_out_marks_the_single_gate_entry_step(self):
        s = self.state("VIRIDIAN_FOREST_NORTH_GATE", (4, 2), "ROUTE_2")
        words = A.way_out(s, ["ROUTE_2"])[3]
        self.assertTrue(words[-1].endswith("to (5,0) (out the door)"))
        self.assertNotIn(", up 1 (out the door)", ", ".join(words))


if __name__ == "__main__":
    unittest.main()
