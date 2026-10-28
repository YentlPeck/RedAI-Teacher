"""Checks for tools/read_state.py on real game moments from the bot's record game replay
(fixture record-1831000065: game memory dumps, not in the repo; see README).

Run: python -m unittest discover -s tests -v
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import settings  # noqa: E402
import read_state as R  # noqa: E402

D = settings.FixtureDir("record-1831000065")


def wram(name):
    return R.state_from_wram((D / name).read_bytes())


class ReadState(unittest.TestCase):
    def test_misty_split(self):
        s = wram("split-07.wram")
        self.assertEqual(s["place"]["map"], "CERULEAN_GYM")
        self.assertEqual(s["badges"], ["Boulder"])
        lead = s["team"][0]
        self.assertEqual((lead["species"], lead["level"]), ("NIDOKING", 25))
        self.assertIn("THRASH", [m["move"] for m in lead["moves"]])
        self.assertEqual(s["story"]["next"]["id"], "badge2")
        self.assertEqual(s["part"], 3)

    def test_story_only_moves_forward(self):
        prev = set()
        for n in range(1, 21):
            done = set(wram(f"split-{n:02d}.wram")["story"]["done"])
            self.assertTrue(prev <= done, f"split {n} lost {prev - done}")
            prev = done
        self.assertIn("badge8", prev)

    def test_bag_and_hms(self):
        bag = [b["item"] for b in wram("split-09.wram")["bag"]]
        self.assertIn("BICYCLE", bag)
        self.assertIn("HM01 CUT", bag)

    def test_battles_match_game_teams(self):
        facts = json.loads((settings.KB / "game_facts.json").read_text(encoding="utf-8"))
        teams = {f"{t['class']}:{t['index']}": t for t in facts["trainers"]}
        files = sorted(D.glob("battle-*.wram"))
        self.assertGreater(len(files), 50)
        for f in files:
            b = R.state_from_wram(f.read_bytes())["battle"]
            self.assertIsNotNone(b, f.name)
            team = teams[b["trainer"]]["party"]
            self.assertIn((b["enemy"]["species"], b["enemy"]["level"]),
                          [(p["species"], p["level"]) for p in team], f.name)

    def test_champion_battle(self):
        b = wram("battle-062.wram")["battle"]
        self.assertEqual(b["trainer"], "Rival3:2")
        self.assertEqual((b["enemy"]["species"], b["enemy"]["max_hp"]), ("PIDGEOT", 182))

    def test_text_decoding(self):
        # English wins over Japanese on shared codes; multi-character entries decode (Sol RS1 #7)
        self.assertEqual("".join(R.CHARS[k] for k in (0x80, 0xBB, 0xE1, 0xE2, 0xF2)), "A'dPKMN.")

    def test_battle_start_is_unknown_not_stale(self):
        # A battle copy that does not match the party member it claims is reported unknown (Sol RS1 #5)
        raw = bytearray((D / "battle-001.wram").read_bytes())
        raw[R.A("wEnemyMonSpecies") - 0xC000] ^= 0xFF
        raw[R.A("wBattleMonLevel") - 0xC000] ^= 0x7F
        b = R.state_from_wram(bytes(raw))["battle"]
        self.assertIsNone(b["enemy"])
        self.assertIsNone(b["yours"])
        self.assertIn("not known yet", R.summary(R.state_from_wram(bytes(raw))))

    def test_final_split_saved(self):
        # The re-recording keeps the 21st (Hall of Fame) split (Sol RS1 #8)
        f = settings.fixture("record-1831000065-v2/split-21.wram")
        s = R.state_from_wram(f.read_bytes())
        self.assertIn("champion", s["story"]["done"])
        self.assertIsNone(s["story"]["next"])

    def test_save_file(self):
        s = R.state_from_sav(D / "last-save-at-split-08.sav")
        self.assertEqual(s["player"], "B")
        self.assertEqual(s["place"]["map"], "VERMILION_CITY")
        self.assertEqual(s["badges"], ["Boulder", "Cascade"])
        self.assertIsNone(s["battle"])


if __name__ == "__main__":
    unittest.main()
