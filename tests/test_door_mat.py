"""Exit regressions from static WRAM and pokered maps; never start an emulator."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import settings  # noqa: E402
import advise as A
import read_state as R


class DoorMat(unittest.TestCase):
    def test_house_exit_from_all_three_reported_positions(self):
        for pos, door in [((7, 7), (3, 7)), ((0, 7), (2, 7)), ((2, 6), (2, 7))]:
            with self.subTest(pos=pos):
                s = R.state_from_wram((settings.fixture("start.wram")).read_bytes())
                s["place"].update(map="REDS_HOUSE_1F", x=pos[0], y=pos[1], last_map="PALLET_TOWN")
                a = A.answer(s, "How do I exit the house?")
                exit_text = next(t for t in a["details"] if t.startswith("The way to PALLET_TOWN"))
                self.assertIn(f"door at ({door[0]},7): stand at ({door[0]},6) above it and walk down onto it", exit_text)
                route = next(t for t in a["details"] if t.startswith("Our route on this map"))
                self.assertIn(f"down 1 to ({door[0]},7).", route)
                self.assertNotIn("left 5 to (2,6)", route)

    def test_every_record_exit_text_names_a_real_warp_or_connected_edge(self):
        checked = 0
        for i, w in enumerate(A.WALKS):  # already passed through skip_nidoran_detour
            m = w["map"]
            nxt = next((q["map"] for q in A.WALKS[i + 1:] if q["map"] != m), None)
            if not nxt:  # final Hall of Fame visit has no exit
                continue
            with self.subTest(visit=i, map=m, next_map=nxt):
                text = A._exit_text(m, nxt, w["points"][-1], A._last_step(w["points"]))
                coords = re.search(r"\((-?\d+),(-?\d+)\)", text)
                self.assertIsNotNone(coords, text)
                tile = tuple(map(int, coords.groups()))
                if A._scripted_ending(m, nxt, w["points"][-1]):
                    # Scripted travel is a real record ending, not a missing door press.
                    self.assertEqual(tile, tuple(w["points"][-1][:2]), text)
                    self.assertIsNone(A._record_exit(m, nxt, w["points"][-1], A._last_step(w["points"])))
                    self.assertNotIn("stairs / door", text)
                elif " edge at " in text:
                    side = re.search(r"\((north|south|west|east)\) edge", text)[1]
                    self.assertIn(side, A._conns(m), text)
                    width, height = (2 * n for n in A.W._tables()["dims"][m])
                    self.assertTrue(0 <= tile[0] < width and 0 <= tile[1] < height, text)
                    self.assertTrue({"north": tile[1] == 0, "south": tile[1] == height - 1,
                                     "west": tile[0] == 0, "east": tile[0] == width - 1}[side], text)
                else:
                    self.assertIn(tile, [(x, y) for x, y, _ in A._objects(m)[0]], text)
                checked += 1
        self.assertEqual(checked, len(A.WALKS) - 1)

    def test_other_indoor_false_exits_use_the_target_warp_and_real_press(self):
        for m, nxt, end, step, tile, into in [
            ("PEWTER_MART", "PEWTER_CITY", (3, 6), "right", (3, 7), "down"),
            ("VIRIDIAN_FOREST_NORTH_GATE", "ROUTE_2", (5, 1), "right", (5, 0), "up"),
            ("MT_MOON_B2F", "MT_MOON_B1F", (25, 8), "left", (25, 9), "down"),
            ("CELADON_MART_2F", "CELADON_MART_3F", (16, 2), "right", (16, 1), "up"),
            ("SILPH_CO_9F", "SILPH_CO_5F", (17, 14), "up", (17, 15), "down"),
            ("VIRIDIAN_GYM", "VIRIDIAN_CITY", (16, 16), "right", (16, 17), "down"),
        ]:
            with self.subTest(map=m):
                exit_ = A._record_exit(m, nxt, end, step)
                self.assertEqual(exit_["tile"], tile)
                self.assertEqual(exit_["target"], nxt)
                self.assertEqual(A._exit_walk(m, end, exit_), [f"{into} 1"])

    def test_skipped_maps_name_the_actual_first_map(self):
        text = A._exit_text("BILLS_HOUSE", "CERULEAN_CITY", (4, 5), "right")
        self.assertIn("first through ROUTE_25", text)
        self.assertIn("door at (3,7)", text)
        self.assertIn("walk down onto it (out the door)", text)

    def test_unknown_collision_grid_keeps_the_real_static_warp(self):
        text = A._exit_text("UNDERGROUND_PATH_NORTH_SOUTH", "UNDERGROUND_PATH_ROUTE_6", (2, 40), "down")
        self.assertIn("door at (2,41)", text)

    def test_exit_walk_respects_an_observed_blocker(self):
        exit_ = A._record_exit("REDS_HOUSE_1F", "PALLET_TOWN", (3, 6), "left", near=(2, 6))
        self.assertIsNone(A._exit_walk("REDS_HOUSE_1F", (3, 6), exit_, blocked={(2, 6)}))
        self.assertIsNone(A._exit_walk("REDS_HOUSE_1F", (3, 6), exit_, blocked={(2, 7)}))


if __name__ == "__main__":
    unittest.main()
