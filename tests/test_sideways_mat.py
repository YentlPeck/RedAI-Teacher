"""Sol R9D: sideways edge-mat entry needs an outward press; static data only."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import settings  # noqa: E402
import advise as A
import read_state as R


# Starts beside a bottom mat, not on its paired warp. Coordinates are test inputs only.
CASES = (
    ("REDS_HOUSE_1F", (4, 7), (3, 7), "left", "PALLET_TOWN"),
    ("OAKS_LAB", (6, 11), (5, 11), "left", "PALLET_TOWN"),
    ("VIRIDIAN_MART", (5, 7), (4, 7), "left", "VIRIDIAN_CITY"),
    ("VIRIDIAN_POKECENTER", (2, 7), (3, 7), "right", "VIRIDIAN_CITY"),
    ("VIRIDIAN_FOREST_NORTH_GATE", (3, 7), (4, 7), "right", "VIRIDIAN_FOREST"),
    ("VIRIDIAN_FOREST_SOUTH_GATE", (6, 7), (5, 7), "left", "ROUTE_2"),
    ("ROUTE_2_GATE", (3, 7), (4, 7), "right", "ROUTE_2"),
    ("PEWTER_GYM", (6, 13), (5, 13), "left", "PEWTER_CITY"),
)


class SidewaysMat(unittest.TestCase):
    def state(self, map_, pos, last):
        s = R.state_from_wram((settings.fixture("start.wram")).read_bytes())
        map_id = next(i for i, name in R.MAPS.items() if name == map_)
        s["place"].update(map=map_, map_id=map_id, x=pos[0], y=pos[1], last_map=last)
        s.update(battle=None, text_box=False)
        return s

    def route(self, s, target):
        r = A.walk_to(s, lambda m, p: m == target, max_maps=1, fallback=False)
        self.assertIsNotNone(r)
        return r

    def test_sols_exact_house_question_keeps_both_presses(self):
        s = self.state("REDS_HOUSE_1F", (4, 7), "PALLET_TOWN")
        self.assertEqual(s["place"]["map_id"], 37)
        expected = "left 1 to (3,7), down 1 (out the door to PALLET_TOWN)"
        for _ in range(2):
            self.assertIn(expected, A.text(A.answer(s, "Where is Pallet Town?")))

    def test_sideways_entry_stays_on_the_mat_until_outward_press(self):
        for map_, pos, mat, step, target in CASES:
            with self.subTest(map=map_):
                s = self.state(map_, pos, target)
                self.assertEqual(dict(A.W.moves(A._grid(map_), pos))[step], mat)
                r = self.route(s, target)
                self.assertEqual(r["cost"], 2)
                self.assertEqual(r["steps"][0], ((map_, pos), ("move", step)))
                self.assertEqual(r["steps"][1], ((map_, mat), ("warp", target, "down")))
                self.assertEqual(A.walk_words(s, r), [f"{step} 1 to ({mat[0]},{mat[1]})",
                                                     f"down 1 (out the door to {target})"])

    def test_outward_entry_is_still_one_press_on_each_bottom_mat(self):
        for map_, _, mat, _, target in CASES:
            with self.subTest(map=map_):
                s = self.state(map_, (mat[0], mat[1] - 1), target)
                r = self.route(s, target)
                self.assertEqual(r["cost"], 1)
                self.assertEqual(A.walk_words(s, r), [f"down 1 to ({mat[0]},{mat[1]}) (out the door to {target})"])

    def test_standing_on_each_mat_keeps_one_outward_press(self):
        for map_, _, mat, _, target in CASES:
            with self.subTest(map=map_):
                s = self.state(map_, mat, target)
                r = self.route(s, target)
                self.assertEqual(r["cost"], 1)
                self.assertEqual(A.walk_words(s, r), [f"down 1 (out the door to {target})"])

    def test_way_out_keeps_the_sideways_step_and_outward_press(self):
        for map_, pos, mat, step, target in CASES:
            with self.subTest(map=map_):
                s = self.state(map_, pos, target)
                self.assertEqual(A.way_out(s, [target])[3],
                                 [f"{step} 1 to ({mat[0]},{mat[1]})", "down 1 (out the door)"])

    def test_north_gate_finishes_with_upward_entry(self):
        s = self.state("VIRIDIAN_FOREST_NORTH_GATE", (4, 2), "ROUTE_2")
        r = self.route(s, "ROUTE_2")
        self.assertEqual(r["cost"], 3)
        self.assertEqual(r["steps"][-1], (("VIRIDIAN_FOREST_NORTH_GATE", (5, 1)),
                                           ("warp", "ROUTE_2", None, "up")))
        self.assertEqual(A.walk_words(s, r)[-1], "up 1 to (5,0) (out the door to ROUTE_2)")

    def test_stairs_warp_on_any_entry_direction(self):
        for pos, step in (((6, 1), "right"), ((7, 0), "down"), ((7, 2), "up")):
            with self.subTest(pos=pos):
                s = self.state("REDS_HOUSE_2F", pos, "PALLET_TOWN")
                r = self.route(s, "REDS_HOUSE_1F")
                self.assertEqual(r["cost"], 1)
                self.assertEqual(r["exit"], ("warp", "REDS_HOUSE_1F", None, step))

    def test_tile_lists_include_shared_labels_and_fallthrough(self):
        tiles = A.W._tables()["warps"]
        self.assertEqual(tiles["REDS_HOUSE_1"], {0x1A, 0x1C})
        self.assertEqual(tiles["REDS_HOUSE_2"], {0x1A, 0x1C})
        self.assertEqual(tiles["FOREST_GATE"], {0x3B, 0x1A, 0x1C})
        self.assertEqual(tiles["FACILITY"], {0x43, 0x58, 0x20, 0x1B, 0x13})
        self.assertEqual(tiles["CEMETERY"], {0x1B, 0x13})
        self.assertEqual(tiles["PLATEAU"], {0x1B, 0x3B})
        self.assertEqual(tiles["CLUB"], set())
        for map_, _, mat, _, _ in CASES:
            with self.subTest(map=map_):
                g = A._grid(map_)
                self.assertNotIn(g["tile"][mat], g["warp"])
        gate = A._grid("VIRIDIAN_FOREST_NORTH_GATE")
        self.assertIn(gate["tile"][(5, 0)], gate["warp"])


if __name__ == "__main__":
    unittest.main()
