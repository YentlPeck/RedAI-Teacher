"""Pull hard game facts for the teacher out of the pokered disassembly (reference/pokered, see README).

Writes kb/game_facts.json: types, moves, species, every trainer team (levels, moves, stats)
and wild Pokémon per area (Red version). Nothing here is guessed: it is read from the game's source.

Run: python tools/extract_game_facts.py
"""
import json
import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import settings  # noqa: E402

SRC = settings.POKERED
OUT = settings.KB / "game_facts.json"

# Gen 1 trainer DVs are fixed: Atk 9, Def 8, Spd 8, Spc 8 -> HP DV 8. No stat experience.
TRAINER_DV = {"hp": 8, "atk": 9, "def": 8, "spd": 8, "spc": 8}
WILD_SLOT_PCT = [19.9, 19.9, 15.2, 9.8, 9.8, 9.8, 5.1, 5.1, 4.3, 1.2]  # data/wild/probabilities.asm
EFFECT = {"SUPER_EFFECTIVE": 2.0, "NOT_VERY_EFFECTIVE": 0.5, "NO_EFFECT": 0.0}
# data/trainers/special_moves.asm (LoneMoves): leader -> (party index, move); goes in move slot 3.
LONE_MOVES = {"Brock": (1, "BIDE"), "Misty": (1, "BUBBLEBEAM"), "LtSurge": (2, "THUNDERBOLT"),
              "Erika": (2, "MEGA_DRAIN"), "Koga": (3, "TOXIC"), "Sabrina": (3, "PSYWAVE"),
              "Blaine": (3, "FIRE_BLAST"), "Giovanni3": (4, "FISSURE")}
# TeamMoves: Elite Four member's 5th Pokémon gets this move in slot 3.
TEAM_MOVES = {"Lorelei": "BLIZZARD", "Bruno": "FISSURE", "Agatha": "TOXIC", "Lance": "BARRIER"}
BOSS_PLACE = {"Rival1": "Oak's Lab", "Brock": "Pewter Gym", "Misty": "Cerulean Gym", "LtSurge": "Vermilion Gym",
              "Erika": "Celadon Gym", "Koga": "Fuchsia Gym", "Sabrina": "Saffron Gym", "Blaine": "Cinnabar Gym",
              "Lorelei": "Indigo Plateau (Elite Four)", "Bruno": "Indigo Plateau (Elite Four)",
              "Agatha": "Indigo Plateau (Elite Four)", "Lance": "Indigo Plateau (Elite Four)",
              "Rival3": "Indigo Plateau (Champion)"}


def key(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def read(rel):
    return (SRC / rel).read_text(encoding="utf-8")


def pretty_type(t):
    return {"PSYCHIC_TYPE": "PSYCHIC"}.get(t, t)


def parse_types():
    chart = []
    for m in re.finditer(r"db\s+(\w+),\s+(\w+),\s+(\w+)", read("data/types/type_matchups.asm")):
        a, d, e = m.groups()
        if e in EFFECT:
            chart.append({"attacker": pretty_type(a), "defender": pretty_type(d), "x": EFFECT[e]})
    return chart


def parse_moves():
    moves = {}
    for m in re.finditer(r"^\s*move\s+(\w+),\s*(\w+),\s*(\d+),\s*(\w+),\s*(\d+),\s*(\d+)",
                         read("data/moves/moves.asm"), re.M):
        name, effect, power, typ, acc, pp = m.groups()
        moves[name] = {"type": pretty_type(typ), "power": int(power), "accuracy": int(acc),
                       "pp": int(pp), "effect": effect}
    return moves


def parse_learnsets():
    """label key -> {"evolutions": [...], "learnset": [(level, move)]}"""
    text = read("data/pokemon/evos_moves.asm")
    out = {}
    for block in re.split(r"\n(?=\w+EvosMoves:)", text):
        head = re.match(r"(\w+)EvosMoves:", block)
        if not head:
            continue
        evo_part, _, learn_part = block.partition("; Learnset")
        evos = []
        for line in re.findall(r"db\s+(EVOLVE_\w+),\s*([^\n;]+)", evo_part):
            kind, args = line[0], [a.strip() for a in line[1].split(",")]
            if kind == "EVOLVE_LEVEL":
                evos.append({"how": "level", "level": int(args[0]), "into": args[1]})
            elif kind == "EVOLVE_ITEM":
                evos.append({"how": "item", "item": args[0], "into": args[2]})
            else:
                evos.append({"how": "trade", "into": args[1]})
        learn = [(int(lv), mv) for lv, mv in re.findall(r"db\s+(\d+),\s*(\w+)", learn_part)]
        out[key(head.group(1))] = {"evolutions": evos, "learnset": learn}
    return out


def parse_species(learnsets):
    species = {}
    for f in sorted((SRC / "data/pokemon/base_stats").glob("*.asm")):
        t = f.read_text(encoding="utf-8")
        const = re.search(r"db DEX_(\w+)", t).group(1)
        hp, atk, df, spd, spc = map(int, re.search(
            r"db\s+(\d+),\s+(\d+),\s+(\d+),\s+(\d+),\s+(\d+)\s*\n\s*;\s*hp", t).groups())
        t1, t2 = re.search(r"db (\w+), (\w+) ; type", t).groups()
        catch = int(re.search(r"db (\d+) ; catch rate", t).group(1))
        base_moves = [m for m in re.search(r"db (\w+), (\w+), (\w+), (\w+) ; level 1 learnset", t).groups()
                      if m != "NO_MOVE"]
        tmhm = re.search(r"tmhm (.*?)\n\s*; end", t, re.S)
        tmhm = re.findall(r"\w+", tmhm.group(1)) if tmhm else []
        ls = learnsets.get(key(const), {"evolutions": [], "learnset": []})
        types = [pretty_type(t1)] + ([pretty_type(t2)] if t2 != t1 else [])
        species[const] = {"dex": None, "types": types,
                          "base": {"hp": hp, "atk": atk, "def": df, "spd": spd, "spc": spc},
                          "catch_rate": catch, "base_moves": base_moves,
                          "learnset": [{"level": lv, "move": mv} for lv, mv in ls["learnset"]],
                          "evolutions": ls["evolutions"], "tm_hm": tmhm}
    return species


def moves_at_level(sp, level):
    """Gen 1 default moves for an enemy: level-1 moves, then each learnset move up to `level`
    (oldest pushed out when there are already four)."""
    moves = list(sp["base_moves"])
    for entry in sp["learnset"]:
        if entry["level"] <= level and entry["move"] not in moves:
            if len(moves) == 4:
                moves.pop(0)
            moves.append(entry["move"])
    return moves


def stats_at_level(base, level, dv=TRAINER_DV):
    s = {k: (base[k] + dv[k]) * 2 * level // 100 + 5 for k in ("atk", "def", "spd", "spc")}
    s["hp"] = (base["hp"] + dv["hp"]) * 2 * level // 100 + level + 10
    return s


def parse_trainers(species):
    text = read("data/trainers/parties.asm")
    trainers = []
    for block in re.split(r"\n(?=\w+Data:)", text):
        head = re.match(r"(\w+)Data:", block)
        if not head or head.group(1) == "TrainerDataPointers":
            continue
        cls = head.group(1)
        place, index = None, 0
        for line in block.splitlines()[1:]:
            line = line.strip()
            if line.startswith(";"):
                place = line[1:].strip()
                continue
            m = re.match(r"db\s+(.*)", line)
            if not m:
                continue
            vals = [v.strip() for v in m.group(1).split(";")[0].split(",") if v.strip()]
            if vals[-1] == "0":
                vals = vals[:-1]
            index += 1
            if vals[0] == "$FF":
                pairs = [(int(vals[i]), vals[i + 1]) for i in range(1, len(vals), 2)]
            else:
                pairs = [(int(vals[0]), s) for s in vals[1:]]
            party = []
            for lv, sp in pairs:
                info = species[sp]
                party.append({"species": sp, "level": lv, "types": info["types"],
                              "moves": moves_at_level(info, lv), "stats": stats_at_level(info["base"], lv)})
            trainers.append({"class": cls, "index": index, "place": place, "party": party})
    # Teams listed without a place comment: fill in where they are fought.
    for t in trainers:
        if t["place"] is None:
            t["place"] = BOSS_PLACE.get(t["class"])
    # Special moves (the game adds them when the battle starts).
    giovanni = [t for t in trainers if t["class"] == "Giovanni"]
    for t in trainers:
        name = t["class"]
        if name == "Giovanni":
            name = f"Giovanni{giovanni.index(t) + 1}"
        if name in LONE_MOVES:
            i, mv = LONE_MOVES[name]
            t["party"][i]["moves"][2:3] = [mv]
            t["special_move"] = f"{t['party'][i]['species']} has {mv} (game script)"
        if name in TEAM_MOVES and len(t["party"]) >= 5:
            t["party"][4]["moves"][2:3] = [TEAM_MOVES[name]]
            t["special_move"] = f"{t['party'][4]['species']} has {TEAM_MOVES[name]} (game script)"
        if name == "Rival3":
            t["party"][0]["moves"][2:3] = ["SKY_ATTACK"]
            starter_move = {"BLASTOISE": "BLIZZARD", "VENUSAUR": "MEGA_DRAIN", "CHARIZARD": "FIRE_BLAST"}
            last = t["party"][-1]
            last["moves"][2:3] = [starter_move[last["species"]]]
            t["special_move"] = f"PIDGEOT has SKY_ATTACK, {last['species']} has {starter_move[last['species']]}"
    return trainers


def parse_wild():
    wild = {}
    for f in sorted((SRC / "data/wild/maps").glob("*.asm")):
        t = f.read_text(encoding="utf-8")
        # Red version only: drop IF DEF(_BLUE) ... ENDC blocks, keep IF DEF(_RED) content.
        t = re.sub(r"IF DEF\(_BLUE\).*?ENDC", "", t, flags=re.S)
        t = t.replace("IF DEF(_RED)", "").replace("ENDC", "")
        area = {}
        for kind in ("grass", "water"):
            m = re.search(rf"def_{kind}_wildmons (\d+).*?\n(.*?)end_{kind}_wildmons", t, re.S)
            if not m or int(m.group(1)) == 0:
                continue
            slots = re.findall(r"db\s+(\d+),\s*(\w+)", m.group(2))
            table = {}
            for (lv, sp), pct in zip(slots, WILD_SLOT_PCT):
                e = table.setdefault(sp, {"species": sp, "pct": 0.0, "levels": set()})
                e["pct"] = round(e["pct"] + pct, 1)
                e["levels"].add(int(lv))
            area[kind] = {"encounter_rate": int(m.group(1)),
                          "mons": sorted(({**e, "levels": sorted(e["levels"])} for e in table.values()),
                                         key=lambda e: -e["pct"])}
        if area:
            wild[f.stem] = area
    return wild


def main():
    learnsets = parse_learnsets()
    species = parse_species(learnsets)
    facts = {
        "source": "pokered disassembly (reference/pokered), Pokémon Red (English)",
        "notes": ["Trainer stats use Gen 1 trainer DVs (Atk 9, Def 8, Spd 8, Spc 8) and no stat experience.",
                  "Trainer moves = the game's default moves for that level, plus special moves set by game scripts.",
                  "Wild percentages are the chance per encounter in that area (Red version)."],
        "types": parse_types(),
        "moves": parse_moves(),
        "species": species,
        "trainers": parse_trainers(species),
        "wild": parse_wild(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(facts, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{OUT}: {len(facts['species'])} species, {len(facts['moves'])} moves, "
          f"{len(facts['trainers'])} trainer teams, {len(facts['wild'])} wild areas")


if __name__ == "__main__":
    main()
