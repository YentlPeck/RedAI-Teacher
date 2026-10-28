"""Read where a player is in Pokémon Red (English) from game memory, for the teacher.

Works with three sources:
- a running PyBoy emulator           state_from_pyboy(pyboy)
- a work RAM dump (0xC000-0xDFFF)    state_from_wram(bytes)
- a battery save file (.sav, 32 KB)  state_from_sav(path)     (no battle data: saves are made outside battle)

Returns a plain dict: place (map, x, y, which lesson part), team, bag, badges, money, battle, story progress
(milestones done and the next one) and the lesson part to read. All addresses and names come from the pokered
disassembly (reference/pokered.sym and constants), nothing is hard-coded from memory.

CLI: python tools/read_state.py FILE (.wram, .sav or .state with --rom)  [--json]
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import settings  # noqa: E402

settings.need_reference()
ROOT = settings.REPO
REF = settings.REFERENCE
KB = settings.KB / "kb.json"


# ---------- names and addresses from pokered ----------

def _consts_hex(path, pattern):
    text = (REF / "pokered" / path).read_text(encoding="utf-8")
    return {int(h, 16): n for n, h in re.findall(pattern, text)}


SYM = {}
for _line in (REF / "pokered.sym").read_text(encoding="utf-8").splitlines():
    _m = re.match(r"([0-9a-f]{2}):([0-9a-f]{4}) (\w+)", _line)
    if _m and _m.group(3) not in SYM:
        SYM[_m.group(3)] = (int(_m.group(1), 16), int(_m.group(2), 16))


def A(name):
    """Address of a WRAM symbol."""
    return SYM[name][1]


SPECIES = _consts_hex("constants/pokemon_constants.asm", r"const (\w+)\s*;\s*\$([0-9A-Fa-f]+)")
MAPS = _consts_hex("constants/map_constants.asm", r"map_const (\w+),[^;]*;\s*\$([0-9A-Fa-f]+)")
ITEMS = _consts_hex("constants/item_constants.asm", r"const (\w+)\s*;\s*\$([0-9A-Fa-f]+)")
for _n, _h in re.findall(r"add_(?:hm|tm) (\w+)\s*;\s*\$([0-9A-Fa-f]+)",
                         (REF / "pokered/constants/item_constants.asm").read_text(encoding="utf-8")):
    _id = int(_h, 16)
    ITEMS[_id] = (f"HM{_id - 0xC3:02d}" if _id < 0xC9 else f"TM{_id - 0xC8:02d}") + f" {_n}"
MOVES = {}
_i = 0
for _line in (REF / "pokered/constants/move_constants.asm").read_text(encoding="utf-8").splitlines():
    _m = re.match(r"\s*const (\w+)", _line)
    if _m:
        MOVES[_i] = _m.group(1)
        _i += 1
CHARS = {}
_KANA = re.compile(r"[぀-ヿ「-』]")   # hiragana, katakana, Japanese quotes
# Tokens that stand for printed text (other <...> tokens are control codes and never appear in names)
_TOKENS = {"<PK>": "PK", "<MN>": "MN", "<PKMN>": "PKMN", "<DOT>": ".", "<PC>": "PC", "<TM>": "TM",
           "<TRAINER>": "TRAINER", "<ROCKET>": "ROCKET", "<LV>": "Lv", "<ID>": "ID", "<to>": "to", "<……>": "……",
           "<COLON>": ":", "<ED>": "ED", "<BOLD_V>": "V", "<BOLD_S>": "S", "<BOLD_P>": "P"}
for _c, _h in re.findall(r'charmap "([^"]+)",\s*\$([0-9a-f]{2})', (REF / "pokered/constants/charmap.asm").read_text(encoding="utf-8")):
    _k = int(_h, 16)   # charmap.asm also lists Japanese characters on the same codes: an English one always wins
    if _k not in CHARS or (_KANA.search(CHARS[_k]) and not _KANA.search(_c)):
        CHARS[_k] = _TOKENS.get(_c, _c)
TYPES = {k: v.replace("_TYPE", "") for k, v in
         _consts_hex("constants/type_constants.asm", r"const (\w+)\s*;\s*\$([0-9A-Fa-f]+)").items()}
TRAINER_CLASSES = re.findall(r"dw (\w+)Data", (REF / "pokered/data/trainers/parties.asm").read_text(encoding="utf-8"))
KEY_ITEMS = {ITEMS[i + 1] for i, flag in enumerate(re.findall(r"dbit (TRUE|FALSE)", (REF / "pokered/data/items/key_items.asm")
             .read_text(encoding="utf-8"))) if flag == "TRUE" and i + 1 in ITEMS}
BADGES = ["Boulder", "Cascade", "Thunder", "Rainbow", "Soul", "Marsh", "Volcano", "Earth"]
LEADERS = ["Brock", "Misty", "Lt. Surge", "Erika", "Koga", "Sabrina", "Blaine", "Giovanni"]


def _event_bits():
    """EVENT_* name -> bit index in wEventFlags (const_def / const / const_skip / const_next)."""
    value, out = 0, {}
    for line in (REF / "pokered/constants/event_constants.asm").read_text(encoding="utf-8").splitlines():
        s = line.split(";")[0].strip()
        if s.startswith("const_def"):
            value = 0
        elif s.startswith("const_skip"):
            arg = s[len("const_skip"):].strip()
            value += int(arg) if arg else 1
        elif s.startswith("const_next"):
            arg = re.sub(r"\$([0-9A-Fa-f]+)", r"0x\1", s[len("const_next"):].strip())   # e.g. "$F0 - 2"
            assert re.fullmatch(r"[0-9a-fA-Fx +\-*()]+", arg), arg
            value = eval(arg)
        elif s.startswith("const "):
            out[s.split()[1]] = value
            value += 1
    return out


EVENTS = _event_bits()


# ---------- memory sources ----------

class Wram:
    """WRAM bytes for 0xC000-0xDFFF."""
    def __init__(self, data, base=0xC000):
        self.data, self.base = bytes(data), base

    def __getitem__(self, addr):
        if isinstance(addr, slice):
            return self.data[addr.start - self.base:addr.stop - self.base]
        return self.data[addr - self.base]


class PyBoyMem:
    def __init__(self, pyboy):
        self.m = pyboy.memory

    def __getitem__(self, addr):
        if isinstance(addr, slice):
            return bytes(self.m[addr.start:addr.stop])
        return self.m[addr]


class Sav:
    """A .sav file: bank 1 of cartridge RAM holds copies of the party data and the main data block."""
    def __init__(self, raw):
        self.raw = bytes(raw)
        self.ranges = []
        for ws, we, sname in ((A("wPlayerName"), A("wPlayerName") + 11, "sPlayerName"),
                              (A("wPartyDataStart"), A("wPartyDataEnd"), "sPartyData"),
                              (A("wMainDataStart"), A("wMainDataEnd"), "sMainData")):
            bank, saddr = SYM[sname]
            self.ranges.append((ws, we, bank * 0x2000 + saddr - 0xA000))

    def _off(self, addr):
        for ws, we, off in self.ranges:
            if ws <= addr < we:
                return off + addr - ws
        return None

    def __getitem__(self, addr):
        if isinstance(addr, slice):
            return bytes(self[a] for a in range(addr.start, addr.stop))
        off = self._off(addr)
        return self.raw[off] if off is not None else 0


# ---------- reading ----------

def text(m, addr, n):
    out = ""
    for b in m[addr:addr + n]:
        if b == 0x50:
            break
        out += CHARS.get(b, "?")
    return out


def word(m, addr):
    return m[addr] * 256 + m[addr + 1]


def status_text(b):
    if b & 7:
        return "asleep"
    return next((s for bit, s in ((3, "poisoned"), (4, "burned"), (5, "frozen"), (6, "paralyzed")) if b & (1 << bit)),
                "ok")


def event(m, name):
    bit = EVENTS[name]
    return bool(m[A("wEventFlags") + bit // 8] >> (bit % 8) & 1)


def read_party(m):
    team = []
    count = min(m[A("wPartyCount")], 6)
    for i in range(count):
        p = A("wPartyMons") + 44 * i
        moves = [MOVES.get(x, x) for x in m[p + 8:p + 12]]
        pps = [x & 63 for x in m[p + 29:p + 33]]
        team.append({
            "species": SPECIES.get(m[p], m[p]), "nickname": text(m, A("wPartyMonNicks") + 11 * i, 11),
            "level": m[p + 33], "hp": word(m, p + 1), "max_hp": word(m, p + 34), "status": status_text(m[p + 4]),
            "sleep_turns": m[p + 4] & 7,
            "moves": [{"move": mv, "pp": pp} for mv, pp in zip(moves, pps) if mv != "NO_MOVE"],
            "stats": {k: word(m, p + 36 + 2 * j) for j, k in enumerate(("atk", "def", "spd", "spc"))},
        })
    return team


def read_bag(m):
    n = min(m[A("wNumBagItems")], 20)
    return [{"item": ITEMS.get(m[A("wBagItems") + 2 * i], m[A("wBagItems") + 2 * i]),
             "count": m[A("wBagItems") + 2 * i + 1]} for i in range(n)]


def _mon(m, prefix):
    """One battle Pokémon. Stats are the ones in use now (stat changes, paralysis, burn and badge boosts included)."""
    pp = [x & 63 for x in m[A(prefix + "PP"):A(prefix + "PP") + 4]]
    return {"species": SPECIES.get(m[A(prefix + "Species")], m[A(prefix + "Species")]),
            "level": m[A(prefix + "Level")], "hp": word(m, A(prefix + "HP")),
            "max_hp": word(m, A(prefix + "MaxHP")), "status": status_text(m[A(prefix + "Status")]),
            "sleep_turns": m[A(prefix + "Status")] & 7,   # turns of sleep left
            "types": sorted({TYPES.get(m[A(prefix + "Type1")]), TYPES.get(m[A(prefix + "Type2")])} - {None}),
            "stats": {k: word(m, A(prefix + n)) for k, n in (("atk", "Attack"), ("def", "Defense"),
                                                             ("spd", "Speed"), ("spc", "Special"))},
            "moves": [{"move": MOVES.get(x, x), "pp": q} for x, q in zip(m[A(prefix + "Moves"):A(prefix + "Moves") + 4], pp)
                      if x]}


FLAGS = {"BattleStatus1": {0: "bide", 1: "thrashing", 4: "charging", 5: "trapping", 6: "invulnerable", 7: "confused"},
         "BattleStatus2": {0: "x_accuracy", 4: "substitute", 5: "recharging", 7: "seeded"},
         "BattleStatus3": {0: "toxic", 1: "light_screen", 2: "reflect"}}


def _flags(m, side):
    return [name for reg, bits in FLAGS.items() for bit, name in bits.items() if m[A(f"w{side}{reg}")] >> bit & 1]


def read_battle(m):
    """Battle info. While a battle starts (or a Pokémon is switched) the battle copies can still hold the previous
    Pokémon: then "enemy" / "yours" is None (unknown) instead of wrong."""
    kind = m[A("wIsInBattle")]
    if kind == 0:
        return None
    if kind == 0xFF:   # lost the battle (or an overworld poison blackout): the battle data is not valid
        return {"kind": "lost"}
    enemy, yours = _mon(m, "wEnemyMon"), _mon(m, "wBattleMon")
    if kind == 2:      # trainer: the enemy must be the party member it says it is
        pos = m[A("wEnemyMonPartyPos")]
        ok = pos < min(m[A("wEnemyPartyCount")], 6) and m[A("wEnemyPartyCount") + 1 + pos] == m[A("wEnemyMonSpecies")]             and m[A("wEnemyMons") + 44 * pos + 33] == enemy["level"]
    else:              # wild: wCurOpponent / wCurEnemyLVL hold the encounter
        ok = m[A("wCurOpponent")] == m[A("wEnemyMonSpecies")] and m[A("wCurEnemyLVL")] == enemy["level"]
    num = m[A("wPlayerMonNumber")]
    mine = num < min(m[A("wPartyCount")], 6) and m[A("wPartySpecies") + num] == m[A("wBattleMonSpecies")]         and m[A("wPartyMons") + 44 * num + 33] == yours["level"]
    enemy["flags"], yours["flags"] = _flags(m, "Enemy"), _flags(m, "Player")
    b = {"kind": {1: "wild", 2: "trainer"}.get(kind, str(kind)), "enemy": enemy if ok else None,
         "yours": yours if mine else None}
    if kind == 2:
        cls = m[A("wCurOpponent")] - 200          # OPP_ID_OFFSET
        if 0 < cls <= len(TRAINER_CLASSES):
            b["trainer"] = f"{TRAINER_CLASSES[cls - 1]}:{m[A('wTrainerNo')]}"   # same key as game_facts.json
    return b


# Story milestones in our route's order: (id, text, done-check, lesson part). The first one not done is "next".
def _has(state, item):
    return any(str(b["item"]).startswith(item) for b in state["bag"])


MILESTONES = [
    # Oak only appears when you walk north out of Pallet Town into the grass (step 4 test: AI players went to the lab)
    ("oak", "Walk north out of Pallet Town into the tall grass (Route 1): Professor Oak stops you and takes you to his "
     "lab", lambda m, s: event(m, "EVENT_OAK_APPEARED_IN_PALLET") or event(m, "EVENT_FOLLOWED_OAK_INTO_LAB")
     or bool(s["team"]), 1),
    # the game sets EVENT_GOT_STARTER only after the rival picks too: a Pokémon in the team counts at once
    ("starter", "Get your first Pokémon from Oak (pick a Poké Ball on his table)",
     lambda m, s: event(m, "EVENT_GOT_STARTER") or bool(s["team"]), 1),
    ("parcel", "Bring Oak's Parcel from the Viridian Mart to Oak", lambda m, s: event(m, "EVENT_OAK_GOT_PARCEL"), 1),
    ("pokedex", "Get the Pokédex from Oak", lambda m, s: event(m, "EVENT_GOT_POKEDEX"), 1),
    ("badge1", "Beat Brock (Boulder Badge)", lambda m, s: "Boulder" in s["badges"], 1),
    ("mt_moon", "Beat the Super Nerd at the Mt. Moon exit (then take a fossil and go on to Cerulean)",
     lambda m, s: event(m, "EVENT_BEAT_MT_MOON_EXIT_SUPER_NERD") or "Cascade" in s["badges"], 2),
    ("badge2", "Beat Misty (Cascade Badge)", lambda m, s: "Cascade" in s["badges"], 3),
    ("ss_ticket", "Help Bill on Route 25 (S.S. Ticket)", lambda m, s: event(m, "EVENT_GOT_SS_TICKET"), 3),
    ("cut", "Get HM01 Cut from the S.S. Anne captain", lambda m, s: event(m, "EVENT_GOT_HM01"), 4),
    ("badge3", "Beat Lt. Surge (Thunder Badge)", lambda m, s: "Thunder" in s["badges"], 4),
    ("bicycle", "Get the Bicycle (voucher from the Vermilion Fan Club)",
     lambda m, s: event(m, "EVENT_GOT_BIKE_VOUCHER") or _has(s, "BICYCLE"), 5),
    ("fly", "Get HM02 Fly (Route 16 house)", lambda m, s: event(m, "EVENT_GOT_HM02"), 5),
    ("flute", "Rescue Mr. Fuji in Pokémon Tower (Poké Flute)", lambda m, s: event(m, "EVENT_GOT_POKE_FLUTE"), 5),
    ("silph", "Beat Giovanni in Silph Co.", lambda m, s: event(m, "EVENT_BEAT_SILPH_CO_GIOVANNI"), 6),
    ("surf", "Get HM03 Surf in the Safari Zone", lambda m, s: event(m, "EVENT_GOT_HM03"), 6),
    ("badge5", "Beat Koga (Soul Badge)", lambda m, s: "Soul" in s["badges"], 6),
    ("strength", "Give the Gold Teeth to the Warden (HM04 Strength)", lambda m, s: event(m, "EVENT_GOT_HM04"), 7),
    ("secret_key", "Get the Secret Key in the Pokémon Mansion", lambda m, s: _has(s, "SECRET_KEY")
     or "Volcano" in s["badges"], 7),
    ("badge4", "Beat Erika (Rainbow Badge)", lambda m, s: "Rainbow" in s["badges"], 7),
    ("badge7", "Beat Blaine (Volcano Badge)", lambda m, s: "Volcano" in s["badges"], 7),
    ("badge6", "Beat Sabrina (Marsh Badge)", lambda m, s: "Marsh" in s["badges"], 7),
    ("badge8", "Beat Giovanni (Earth Badge)", lambda m, s: "Earth" in s["badges"], 7),
    ("rival22", "Beat the rival on Route 22", lambda m, s: event(m, "EVENT_BEAT_ROUTE22_RIVAL_2ND_BATTLE"), 8),
    # The Hall of Fame clears the Lance/Champion flags before saving: wNumHoFTeams > 0 is the lasting proof.
    ("lance", "Beat the Elite Four (Lorelei, Bruno, Agatha, Lance)",
     lambda m, s: event(m, "EVENT_BEAT_LANCE") or m[A("wNumHoFTeams")] > 0, 8),
    ("champion", "Beat the Champion",
     lambda m, s: event(m, "EVENT_BEAT_CHAMPION_RIVAL") or m[A("wNumHoFTeams")] > 0, 8),
]
OPTIONAL = {"bicycle", "fly"}   # a player can finish without them: never the "next" goal once a later milestone is done


def read(m, with_battle=True):
    badges_byte = m[A("wObtainedBadges")]
    s = {
        "player": text(m, A("wPlayerName"), 11),
        "place": {"map": MAPS.get(m[A("wCurMap")], m[A("wCurMap")]), "map_id": m[A("wCurMap")],
                  "x": m[A("wXCoord")], "y": m[A("wYCoord")],
                  # the outdoor map you came from (inside a house, cave or Pokémon Center)
                  "last_map": MAPS.get(m[A("wLastMap")], m[A("wLastMap")])},
        "team": read_party(m),
        "bag": read_bag(m),
        "badges": [b for i, b in enumerate(BADGES) if badges_byte >> i & 1],
        "money": int("".join(f"{b:02x}" for b in m[A("wPlayerMoney"):A("wPlayerMoney") + 3]) or 0),
        "battle": read_battle(m) if with_battle else None,
        "rival_starter": SPECIES.get(m[A("wRivalStarter")]),
        "last_heal_map": MAPS.get(m[A("wLastBlackoutMap")]),
        # a text box or menu is open outside battle (the game loads its font for it): the player must read on first
        "text_box": with_battle and not m[A("wIsInBattle")] and bool(m[A("wFontLoaded")] & 1),
    }
    done = [{"id": i, "goal": g, "done": bool(f(m, s)), "part": p} for i, g, f, p in MILESTONES]
    last_done = max((i for i, d in enumerate(done) if d["done"]), default=-1)
    nxt = next((d for i, d in enumerate(done) if not d["done"] and not (d["id"] in OPTIONAL and i < last_done)), None)
    s["story"] = {"done": [d["id"] for d in done if d["done"]], "next": nxt}
    import r11_maps
    s.update(r11_maps.memory(m, sys.modules[__name__], s))
    s["part"] = lesson_part(s)
    return s


_KB_CACHE = {}


def _map_to_part():
    if "m" not in _KB_CACHE:
        try:
            _KB_CACHE["m"] = json.loads(KB.read_text(encoding="utf-8"))["map_to_part"]
        except OSError:
            _KB_CACHE["m"] = {}
    return _KB_CACHE["m"]


def progress(s):
    """Where in the story: milestones done + key items in the bag (e.g. Oak's Parcel). Used to match a player to the
    same moment of the record game."""
    return {"done": sorted(s["story"]["done"]), "keys": sorted(str(b["item"]) for b in s["bag"]
                                                               if b["item"] in KEY_ITEMS or str(b["item"]).startswith("HM"))}


def lesson_part(s):
    """Which lesson part fits: the part of the next milestone, unless the map belongs only to other parts."""
    nxt = s["story"]["next"]
    part = nxt["part"] if nxt else 8
    parts = _map_to_part().get(s["place"]["map"])
    if parts and part not in parts and len(parts) == 1:
        return parts[0]
    return part


def state_from_pyboy(pyboy):
    return read(PyBoyMem(pyboy))


def state_from_wram(data):
    return read(Wram(data))


def state_from_sav(path):
    return read(Sav(Path(path).read_bytes()), with_battle=False)


def summary(s):
    """A short text a player (or an AI agent) can read."""
    p = s["place"]
    lines = [f"Place: {p['map']} ({p['x']},{p['y']}). Badges: {len(s['badges'])} ({', '.join(s['badges']) or 'none'}). "
             f"Money: {s['money']}."]
    for t in s["team"]:
        moves = ", ".join(f"{mv['move']} {mv['pp']}" for mv in t["moves"])
        lines.append(f"- {t['species']} L{t['level']} {t['hp']}/{t['max_hp']} HP, {t['status']}: {moves}")
    b = s["battle"]
    if b and b["kind"] == "lost":
        lines.append("You just lost (blacked out): you go back to the last Pokémon Center.")
    elif b:
        e = b.get("enemy")
        foe = f"{e['species']} L{e['level']} {e['hp']}/{e['max_hp']} HP" if e else "enemy not known yet (battle starting)"
        lines.append(f"In a {b['kind']} battle{' vs ' + b['trainer'] if 'trainer' in b else ''}: {foe}.")
    nxt = s["story"]["next"]
    lines.append(f"Next goal: {nxt['goal'] if nxt else 'done: you are the Champion'} (lesson part {s['part']}).")
    return "\n".join(lines)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--rom", default=str(settings.ROM), help="for .state files")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    f = Path(a.file)
    if f.suffix == ".sav":
        s = state_from_sav(f)
    elif f.suffix == ".state":
        import io
        from pyboy import PyBoy
        # ram_file: never let PyBoy write red.gb.ram next to the ROM (fresh boots would load it)
        gb = PyBoy(a.rom, window="null", sound_emulated=False, ram_file=io.BytesIO(bytes(0x8000)))
        try:
            with open(f, "rb") as fh:
                gb.load_state(fh)
            s = state_from_pyboy(gb)
        finally:
            gb.stop(save=False)
    else:
        s = state_from_wram(f.read_bytes())
    print(json.dumps(s, indent=1, ensure_ascii=False) if a.json else summary(s))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
