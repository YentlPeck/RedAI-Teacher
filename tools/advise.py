"""The teacher's answers (Phase 2, step 3): game state (+ an optional question) in, next step + why out.

No language model inside: every answer comes from the game's own rules (pokered), our knowledge base
(kb/kb.json) and our bot's route. The same state always gives the same answer, so tests can check it.

    import read_state, advise
    a = advise.answer(read_state.state_from_pyboy(pyboy), "which move should I use?")
    print(advise.text(a))

What it can do:
- battle:  which move (damage from the game's formula, with your stats now), heal / switch / run when in danger,
           catch a wild Pokémon your team needs (a flier, Cut, Surf, Strength)
- way:     the next story goal, which map comes next on our route, and the walk path on this map from where you are
- ready:   for the next boss: can your team win each fight, and if not, about which level is safe
- any question: the best matching lesson lines (with their tags) from the knowledge base

CLI: python tools/advise.py FILE ["question"] [--json]    (FILE = .wram, .sav or .state, like read_state.py)
"""
import functools
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import read_state as R  # noqa: E402
import walkable as W  # noqa: E402
import r11_maps as M

ROOT = R.ROOT
KB = json.loads((R.settings.KB / "kb.json").read_text(encoding="utf-8"))
FACTS = json.loads((R.settings.KB / "game_facts.json").read_text(encoding="utf-8"))
_W = json.loads((R.settings.KB / "walks.json").read_text(encoding="utf-8"))   # build_walks.py
WALKS, SIGS = _W["visits"], _W["sigs"]


def skip_nidoran_detour(walks):
    """Our record game walks from the Viridian Mart to Route 22 (luck-trick Nidoran) and back before Brock. A player who
    wants to beat the game does not need that (round 4: two Luna games lost many commands on Route 22). Drop the Route 22
    visits before the first Pewter Gym visit and join Viridian City's walk from the Mart (up to (15,18)) with its walk
    north (from (16,17)): one step right, one step up (walked in the game, 21 Oct)."""
    gym = next(i for i, w in enumerate(walks) if w["map"] == "PEWTER_GYM")
    trip = [i for i in range(gym) if walks[i]["map"] == "ROUTE_22"]
    if not trip:
        return walks, {}, None
    a, b = trip[0] - 1, trip[-1] + 1
    head, tail = walks[a], walks[b]
    assert head["map"] == tail["map"] == "VIRIDIAN_CITY", (head["map"], tail["map"])
    hx = [tuple(p[:2]) for p in head["points"]].index((15, 18))
    tx = [tuple(p[:2]) for p in tail["points"]].index((16, 17))
    last = head["points"][hx]
    joined = dict(head, points=head["points"][:hx + 1] + [[16, 18, last[2], last[3] + 1]] + tail["points"][tx:],
                  actions=head["actions"] + tail["actions"])
    return walks[:a] + [joined] + walks[b + 1:], {walks[i]["map"]: walks[i] for i in trip}, head["map"]


WALKS, DETOUR, DETOUR_BACK = skip_nidoran_detour(WALKS)
# Speedrun-only lines (step 5, 21 Oct): our bot catches a Nidoran on Route 22 with luck tricks. A player who wants to
# beat the game does not need that detour (round 4: two Luna games lost many commands on Route 22).
SPEEDRUN_ONLY = re.compile(r"nidoran.*route 22|route 22.*nidoran|catch a male nidoran|save-and-reset|luck trick|"
                           r"exact frames|nidoran and pidgey", re.I)
for _p in KB["parts"]:
    _p["lessons"] = {sec: [l for l in lines if not SPEEDRUN_ONLY.search(l)] for sec, lines in _p["lessons"].items()}
MOVES, SPECIES = KB["moves"], KB["species"]
TYPE_X = {(t["attacker"], t["defender"]): t["x"] for t in KB["types"]}
TEAMS = {f"{t['class']}:{t['index']}": t for t in FACTS["trainers"]}
R11_GUARDED = {"ROUTE_3", "ROUTE_4", "MT_MOON_1F", "MT_MOON_B1F", "MT_MOON_B2F", "CERULEAN_CITY", "CERULEAN_GYM", "ROUTE_24", "ROUTE_25"}
SPECIAL_TYPES = {"FIRE", "WATER", "GRASS", "ELECTRIC", "PSYCHIC", "ICE", "DRAGON"}   # Gen 1: the rest is physical
HEAL = {"POTION": 20, "SUPER_POTION": 50, "HYPER_POTION": 200, "MAX_POTION": 999, "FULL_RESTORE": 999}
CURE = {"poisoned": "ANTIDOTE", "paralyzed": "PARLYZ_HEAL", "asleep": "AWAKENING", "burned": "BURN_HEAL",
        "frozen": "ICE_HEAL"}
BADGE_BOOST = {"Boulder": "atk", "Thunder": "def", "Soul": "spd", "Volcano": "spc"}   # x 1.125 in battle
# Next boss per milestone (game_facts trainer keys)
MILESTONE_BOSS = {"badge1": ["Brock:1"], "badge2": ["Misty:1"], "badge3": ["LtSurge:1"], "badge4": ["Erika:1"],
                  "badge5": ["Koga:1"], "badge6": ["Sabrina:1"], "badge7": ["Blaine:1"], "badge8": ["Giovanni:3"],
                  "silph": ["Giovanni:2"], "rival22": ["Rival2:11"],
                  "lance": ["Lorelei:1", "Bruno:1", "Agatha:1", "Lance:1"], "champion": ["Rival3:2"]}
HM_NEEDED = ["CUT", "FLY", "SURF", "STRENGTH"]
ELITE_ROOMS = {"Lorelei": "LORELEIS_ROOM", "Bruno": "BRUNOS_ROOM", "Agatha": "AGATHAS_ROOM", "Lance": "LANCES_ROOM",
               "Rival3": "CHAMPIONS_ROOM"}


def goal_maps(milestone_id):
    """Maps where the next boss stands (from game_facts places, e.g. "Pewter Gym" -> PEWTER_GYM)."""
    out = set()
    for key in MILESTONE_BOSS.get(milestone_id, []):
        t = TEAMS[key]
        out.add(ELITE_ROOMS.get(t["class"]) or re.sub(r"[^A-Z0-9]+", "_", t["place"].upper()).strip("_"))
    return out & set(R.MAPS.values())
DIR_WORD = {"Up": "up", "Down": "down", "Left": "left", "Right": "right"}


# ---------- damage (pokered engine/battle/core.asm, CalculateDamage + AdjustDamageForMoveType + RandomizeDamage) ----

def type_mult(move_type, def_types):
    x = 1.0
    for t in set(def_types):
        x *= TYPE_X.get((move_type, t), 1.0)
    return x


FIXED = {"SEISMIC_TOSS": "level", "NIGHT_SHADE": "level", "SONICBOOM": 20, "DRAGON_RAGE": 40}
UNKNOWN = {"COUNTER", "BIDE"}   # damage depends on damage taken before: not estimated
LETHAL = 10 ** 6                 # a one-hit KO move that can work: lethal at any HP


def damage(move, level, atk_stats, def_stats, atk_types, def_types, def_hp=None, screens=()):
    """(min, max) damage of one hit, no critical hit. None for moves that do no direct damage.
    `screens`: the defender's "reflect" / "light_screen" flags (they double its defense)."""
    m = MOVES.get(move)
    if not m or move in UNKNOWN:
        return None
    if move in FIXED:   # the fixed-damage path skips the type chart in Gen 1 (core.asm)
        v = level if FIXED[move] == "level" else FIXED[move]
        return (v, v)
    if move == "PSYWAVE":
        return (1, max(1, level * 3 // 2 - 1))
    if m["effect"] == "SUPER_FANG_EFFECT":
        return (max(1, def_hp // 2), max(1, def_hp // 2)) if def_hp else None
    if not m["power"] or m["effect"] == "OHKO_EFFECT":
        return None
    if type_mult(m["type"], def_types) == 0:
        return (0, 0)
    special = m["type"] in SPECIAL_TYPES
    a = atk_stats["spc" if special else "atk"]
    d = def_stats["spc" if special else "def"]
    if ("light_screen" if special else "reflect") in screens:
        d *= 2
    if a > 255 or d > 255:
        a, d = (a >> 2) & 0xFF, (d >> 2) & 0xFF   # the game keeps only the low byte after dividing by 4
    if m["effect"] == "EXPLODE_EFFECT":
        d = max(1, d // 2)   # Selfdestruct / Explosion halve the target's defense (core.asm)
    base = (2 * level // 5 + 2) * m["power"] * a // max(d, 1) // 50
    base = min(base, 997) + 2
    if m["type"] in atk_types:
        base += base // 2
    for t in KB["types"]:   # in the game's table order: rounding makes the order matter
        if t["attacker"] == m["type"] and t["defender"] in def_types:
            base = base * int(t["x"] * 10) // 10
    return (max(1, base * 217 // 255), base) if base > 1 else (base, base)


def hits(move):
    eff = MOVES[move]["effect"]
    return 3 if eff == "TWO_TO_FIVE_ATTACKS_EFFECT" else 2 if eff in ("ATTACK_TWICE_EFFECT", "TWINEEDLE_EFFECT") else 1


def priority(move):
    """Gen 1 turn order: Quick Attack first, Counter last, otherwise speed (core.asm)."""
    return 1 if move == "QUICK_ATTACK" else -1 if move == "COUNTER" else 0


def move_option(move, pp, me, foe, me_first=None):
    """How good one of your moves is now: per-turn expected damage, notes."""
    m = MOVES.get(move)
    if not m:
        return None
    acc = m["accuracy"] / 100
    note = []
    if m["effect"] == "OHKO_EFFECT":
        if foe["stats"]["spd"] > me["stats"]["spd"] or type_mult(m["type"], foe["types"]) == 0:
            return dict(move=move, pp=pp, lo=0, hi=0, avg=0, acc=acc, expect=0, note=["fails: the enemy is faster"])
        return dict(move=move, pp=pp, lo=0, hi=foe["hp"], avg=foe["hp"], acc=acc, expect=foe["hp"] * acc,
                    note=[f"knocks out in one hit, but hits only {m['accuracy']}% of the time"])
    d = damage(move, me["level"], me["stats"], foe["stats"], me["types"], foe["types"], foe["hp"],
               foe.get("flags", ()))
    if d is None:
        return None
    n = hits(move)
    lo, hi = d[0] * (2 if n == 3 else n), d[1] * (5 if n == 3 else n)
    avg = (d[0] + d[1]) / 2 * n
    turns = 1
    if m["effect"] in ("CHARGE_EFFECT", "FLY_EFFECT"):
        turns = 2
        note.append("takes 2 turns")
    if m["effect"] == "HYPER_BEAM_EFFECT":
        note.append("you must rest a turn after it unless it knocks out")
    if m["effect"] == "DREAM_EATER_EFFECT" and foe["status"] != "asleep":
        return dict(move=move, pp=pp, lo=0, hi=0, avg=0, acc=acc, expect=0, note=["only works on a sleeping enemy"])
    if m["effect"] == "EXPLODE_EFFECT":
        note.append("your Pokémon faints")
        avg *= 0.3   # last resort only
    if m["effect"] == "THRASH_PETAL_DANCE_EFFECT":
        note.append("locks you in for 3-4 turns, then confuses you")
    if m["effect"] == "RECOIL_EFFECT":
        note.append("hurts you too (1/4 of the damage)")
    if m["effect"] == "JUMP_KICK_EFFECT":
        note.append("hurts you if it misses")
    x = type_mult(m["type"], foe["types"])
    if x > 1:
        note.append("super effective")
    elif 0 < x < 1:
        note.append("not very effective")
    elif x == 0:
        note.append("no effect")
    return dict(move=move, pp=pp, lo=lo, hi=hi, avg=avg, acc=acc, expect=avg * acc / turns, note=note,
                effect=m["effect"], prio=priority(move))


def best_threat(foe, me):
    """The enemy's most dangerous known move against you: (move, min, max). A one-hit KO move that can work counts as
    LETHAL (no amount of HP protects). Moves whose damage cannot be estimated (Counter, Bide) are returned separately by unknown_threats."""
    best = (None, 0, 0)
    for mv in foe.get("moves", []):
        name = mv["move"] if isinstance(mv, dict) else mv
        m = MOVES.get(name)
        if not m:
            continue
        if m["effect"] == "OHKO_EFFECT":
            if foe["stats"]["spd"] >= me["stats"]["spd"] and type_mult(m["type"], me["types"]) > 0:
                d = (LETHAL, LETHAL)
            else:
                continue
        else:
            d = damage(name, foe["level"], foe["stats"], me["stats"], foe["types"], me["types"], me["hp"],
                       me.get("flags", ()))
            if not d:
                continue
            d = (d[0] * min(hits(name), 2), d[1] * (5 if hits(name) == 3 else hits(name)))
        if d[1] > best[2]:
            best = (name, d[0], d[1])
    return best


def unknown_threats(foe):
    return [mv["move"] if isinstance(mv, dict) else mv for mv in foe.get("moves", [])
            if (mv["move"] if isinstance(mv, dict) else mv) in UNKNOWN]


def foe_moves_first(me, foe, my_move, threat):
    """Worst case: does the enemy act before your move this turn? (Quick Attack, then speed; a tie counts as yes.)"""
    pm, pf = priority(my_move), priority(threat) if threat else 0
    if pm != pf:
        return pf > pm
    return foe["stats"]["spd"] >= me["stats"]["spd"]


# ---------- battle advice ----------

def _types_of(species):
    return SPECIES.get(species, {}).get("types", [])


def _party_mon(t, badges=()):
    """A team member as it would be in battle: badge boosts, then burn (attack / 2) and paralysis (speed / 4)."""
    st = dict(t["stats"])
    for b in badges:
        if b in BADGE_BOOST:
            k = BADGE_BOOST[b]
            st[k] = min(999, st[k] + st[k] // 8)
    if t.get("status") == "burned":
        st["atk"] = max(1, st["atk"] // 2)
    if t.get("status") == "paralyzed":
        st["spd"] = max(1, st["spd"] // 4)
    return {"species": t["species"], "level": t["level"], "hp": t["hp"], "max_hp": t["max_hp"], "status": t["status"],
            "types": _types_of(t["species"]), "stats": st, "moves": t["moves"]}


def _bag(state):
    return {str(b["item"]): b["count"] for b in state["bag"]}


def catch_reason(state, species):
    team = state["team"]
    if len(team) >= 6:
        return None
    names = {t["species"] for t in team}
    can = SPECIES.get(species, {}).get("tm_hm", [])
    for hm in HM_NEEDED:
        if hm in can and not any(hm in SPECIES.get(n, {}).get("tm_hm", []) for n in names):
            return f"no one in your team can learn {hm}, and this Pokémon can (you need {hm} later)"
    return None


def _dmg_text(lo, hi, hp):
    return "knocks out in one hit" if lo >= hp else f"{lo}-{hi} damage"


def enemy_attacks(foe, me):
    """Every enemy move that can hurt you: (move, min, max) per turn (OHKO moves that can work: LETHAL)."""
    out = []
    for mv in foe.get("moves", []):
        name = mv["move"] if isinstance(mv, dict) else mv
        one = best_threat(dict(foe, moves=[name]), me)
        if one[0]:
            out.append(one)
    return out


def residual(mon):
    """HP lost at the end of each turn: poison / burn 1/16 (Toxic grows each turn: counted as 2/16), Leech Seed 1/16."""
    flags, r = mon.get("flags", []), 0
    if mon["status"] in ("poisoned", "burned"):
        r += max(1, mon["max_hp"] // 16) * (2 if "toxic" in flags else 1)
    if "seeded" in flags:
        r += max(1, mon["max_hp"] // 16)
    return r


def blockers(foe):
    """Things that make any "sure win" claim wrong, so the tool never makes one while they are there."""
    flags, moves = foe.get("flags", []), {mv["move"] if isinstance(mv, dict) else mv for mv in foe.get("moves", [])}
    out = []
    if "substitute" in flags:
        out.append(f"{foe['species']} has a Substitute: your hits break the Substitute first")
    if "trapping" in flags:
        out.append(f"{foe['species']} is wrapping you (Wrap / Bind / Fire Spin / Clamp): you cannot attack until it "
                   "stops (2-5 turns); you may still switch or use items")
    if "bide" in flags or "BIDE" in moves:
        out.append(f"{foe['species']} can use Bide: it returns double the damage it takes")
    return out


def safe_plan(me, foe, usable, hp_me, extra_enemy_turns=0):
    """Your move that knocks the enemy out before it can knock you out in the worst case: your lowest damage rolls,
    its strongest move every turn (any mix of its moves), on your last turn its strongest move that acts before yours
    (Quick Attack, then speed; ties count against you), plus poison / burn / Leech Seed at the end of each turn.
    None if there is no such move, or something blocks a sure claim (Substitute, wrapping, Bide)."""
    if blockers(foe):
        return None
    attacks = enemy_attacks(foe, me)
    res = residual(me)
    counter = any((mv["move"] if isinstance(mv, dict) else mv) == "COUNTER" for mv in foe.get("moves", []))
    best = None
    for o in usable:
        if o["lo"] <= 0 or o["acc"] < 0.95 or "takes 2 turns" in o["note"] or o["effect"] in (
                "EXPLODE_EFFECT", "RECOIL_EFFECT", "JUMP_KICK_EFFECT"):
            continue
        if counter and MOVES[o["move"]]["type"] in ("NORMAL", "FIGHTING"):
            continue   # Counter returns double the damage of Normal / Fighting moves
        n = math.ceil(foe["hp"] / o["lo"])
        if n > o["pp"] or (o["effect"] == "HYPER_BEAM_EFFECT" and n > 1):
            continue
        strongest = max((hi for _, _, hi in attacks), default=0)
        first = max((hi for mv, _, hi in attacks if foe_moves_first(me, foe, o["move"], mv)), default=0)
        taken = (n - 1 + extra_enemy_turns) * (strongest + res) + first
        if taken < hp_me and (best is None or (n, -o["acc"], len(o["note"])) < best[0]):
            best = ((n, -o["acc"], len(o["note"])), o, n)
    return (best[1], best[2]) if best else None


def can_act(t):
    return t["hp"] > 0 and t["status"] not in ("frozen", "asleep") and any(mv["pp"] > 0 for mv in t["moves"])


def battle_advice(state):
    """Safe play: attack when you surely win the race of hits, else heal, else switch, else run (wild).
    Critical hits and misses aside, "safe" means safe whatever damage rolls and enemy moves come."""
    b = state["battle"]
    if b["kind"] == "lost":
        return dict(do="You blacked out. You wake up in the last Pokémon Center you used, with half your money.",
                    why="All your Pokémon fainted.", details=[])
    me, foe = b.get("yours"), b.get("enemy")
    if not me or not foe:
        return dict(do="Wait until you see the FIGHT / PKMN / ITEM / RUN menu, then ask again.",
                    why="The battle is still starting: the game has not loaded both Pokémon yet.", details=[])
    if foe["hp"] == 0:
        return dict(do="Press A through the text. The trainer sends the next Pokémon; ask again then.",
                    why=f"{foe['species']} fainted.", details=[])
    if me["hp"] == 0:
        sw = switch_target(state, me, foe, entry_hit=False)
        return dict(do=f"Choose your next Pokémon{': ' + sw[0] if sw else ''}.", why=f"{me['species']} fainted."
                    + (" " + sw[1] if sw else ""), details=[])
    busy = [f for f in ("thrashing", "charging", "recharging", "bide") if f in me.get("flags", [])]
    if busy:
        return dict(do="Press A: you cannot choose a move this turn.",
                    why={"thrashing": "Thrash / Petal Dance keeps going for 3-4 turns.",
                         "charging": "Your two-turn move (Fly, Dig, Solar Beam ...) finishes this turn.",
                         "recharging": "After Hyper Beam your Pokémon must rest a turn.",
                         "bide": "Bide is storing energy."}[busy[0]], details=[])
    opts = [o for o in (move_option(mv["move"], mv["pp"], me, foe) for mv in me["moves"]) if o]
    usable = [o for o in opts if o["pp"] > 0 and o["expect"] > 0]
    threat, t_lo, t_hi = best_threat(foe, me)
    res = residual(me)
    me_first = me["stats"]["spd"] > foe["stats"]["spd"]
    tie = me["stats"]["spd"] == foe["stats"]["spd"]
    speed = (f"You move first (speed {me['stats']['spd']} vs {foe['stats']['spd']})." if me_first else
             f"Speed tie ({me['stats']['spd']}): who moves first is random." if tie else
             f"{foe['species']} moves first (speed {foe['stats']['spd']} vs your {me['stats']['spd']}).")
    details = [f"{o['move']}: {_dmg_text(o['lo'], o['hi'], foe['hp'])}, {foe['species']} has {foe['hp']} HP"
               + (f" ({', '.join(o['note'])})" if o["note"] else "") for o in sorted(opts, key=lambda o: -o["expect"])]
    if threat:
        acc = MOVES[threat]["accuracy"]
        details.append(f"{foe['species']}'s strongest move {threat} "
                       + ("can knock you out in one hit" if t_lo >= me["hp"] else f"does {t_lo}-{t_hi} to you")
                       + ("" if acc >= 100 else f" (hits {acc}% of the time)") + f"; you have {me['hp']} HP.")
    if res:
        details.append(f"You lose {res} HP at the end of every turn (poison / burn / Leech Seed).")
    if any((mv["move"] if isinstance(mv, dict) else mv) == "QUICK_ATTACK" for mv in foe.get("moves", [])):
        details.append(f"{foe['species']} knows Quick Attack: it always moves first with it.")
    for mv in unknown_threats(foe):
        details.append(f"{foe['species']} knows {mv}: its damage is not estimated (it returns damage it took).")
    for w in blockers(foe):
        details.insert(0, w + ".")
    details.append(speed)
    bag = _bag(state)
    danger = (t_hi if threat else 0) + res >= me["hp"]

    if "bide" in foe.get("flags", []):
        # Scout pass: do not turn a deliberate status stall into an automatic no-damage move choice.
        # Stored Bide damage / its release turn are not decoded, so never promise a safe attack here.
        item = next((i for i in sorted(HEAL, key=HEAL.get) if bag.get(i) and me["hp"] < me["max_hp"]), None)
        sw = switch_target(state, me, foe) if not item else None
        risk = ("Bide hits back with double the damage stored. Its stored damage and release turn are unknown; "
                "an item or switch does not guarantee survival.")
        if item or sw:
            return dict(do=f"Use {item} on {me['species']}." if item else f"Switch to {sw[0]}.",
                        why=risk + (" " + sw[1] if sw else ""), details=details)
        if usable and can_act(me):
            # Prefer a single-turn finishing hit; Bide may release first, so this is never a safety claim.
            hit = max(usable, key=lambda o: (o["lo"] >= foe["hp"] and "takes 2 turns" not in o["note"],
                                             o["expect"]))
            return dict(do=f"Use {hit['move']}{_slot(me, hit['move'])}. Risky: Bide may release first.",
                        why=f"Risky fallback while {foe['species']} is storing energy with Bide: "
                            f"{hit['move']} does {hit['lo']}-{hit['hi']} damage to its {foe['hp']} HP. "
                            "Bide may release before your attack; a miss or failure to finish can leave you exposed. "
                            + risk, details=details)

    def heal_plan(extra=1):
        """(item, HP after, sure): the smallest heal that makes the fight safe; else, when the next turn can knock you
        out, the smallest heal that gains more HP than the enemy takes per turn (better, but not sure). Never against
        a one-hit KO move that can work: no HP protects from it."""
        if t_hi >= LETHAL:
            return None
        items = [i for i in sorted(HEAL, key=HEAL.get) if bag.get(i)]
        for item in items:
            healed = min(me["max_hp"], me["hp"] + HEAL[item])
            if healed > me["hp"] and safe_plan(me, foe, usable, healed, extra):
                return item, healed, True
        per_turn = (t_lo + t_hi) / 2 + res
        if danger and per_turn:
            for item in items:
                healed = min(me["max_hp"], me["hp"] + HEAL[item])
                if healed - me["hp"] > per_turn and healed > t_hi + res:
                    return item, healed, False
        return None

    # A Pokémon that cannot act is never "safe": handle it first and always answer here.
    if me["status"] == "frozen":
        cure = next((i for i in ("ICE_HEAL", "FULL_HEAL", "FULL_RESTORE") if bag.get(i)), None)
        if cure:
            return dict(do=f"Use {cure} on {me['species']}.", why=f"{me['species']} is frozen: in Gen 1 it stays "
                        "frozen until cured (or hit by a Fire move).", details=details)
        sw = switch_target(state, me, foe)
        if sw:
            return dict(do=f"Switch to {sw[0]}.", why=f"{me['species']} is frozen and cannot attack. " + sw[1],
                        details=details)
        return dict(do="Nothing saves this Pokémon now: it cannot move while frozen. Pick any move and let the turn pass.",
                    why=f"{me['species']} is frozen, you have no Ice Heal / Full Heal, and no team member can come in "
                        "safely.", details=details)
    if me["status"] == "asleep":
        s = max(1, me.get("sleep_turns", 7))   # the turn it wakes up is lost too
        if safe_plan(me, foe, usable, me["hp"], extra_enemy_turns=s):
            return dict(do="Pick your best move and wait: it attacks once it wakes up.",
                        why=f"{me['species']} is asleep (up to {s} more turns), but even then it wins in time.",
                        details=details)
        cure = next((i for i in ("AWAKENING", "FULL_HEAL", "FULL_RESTORE") if bag.get(i)), None)
        if cure:
            return dict(do=f"Use {cure} on {me['species']}.", why=f"{me['species']} is asleep (up to {s} more turns) "
                        f"and {foe['species']} could knock it out before it wakes up.", details=details)
        sw = switch_target(state, me, foe)
        if sw:
            return dict(do=f"Switch to {sw[0]}.", why=f"{me['species']} is asleep. " + sw[1], details=details)
        return dict(do="Pick your best move and hope it wakes up soon.", why=f"{me['species']} is asleep (up to {s} more "
                    "turns); you have no Awakening and no safe switch.", details=details)
    if "trapping" in foe.get("flags", []):
        hp = heal_plan(extra=0) if danger else None
        sw = switch_target(state, me, foe) if danger and not hp else None
        return dict(do=f"Use {hp[0]} on {me['species']}." if hp else f"Switch to {sw[0]}." if sw else
                    "Pick any move and wait: the wrap ends after 2-5 turns.",
                    why=f"{foe['species']} is wrapping you: you cannot attack until it stops."
                        + (" Its hits could knock you out." if danger else ""), details=details)
    if "invulnerable" in foe.get("flags", []):
        hp = heal_plan(extra=0) if danger else None
        sw = switch_target(state, me, foe) if danger and not hp else None
        return dict(do=f"Use {hp[0]} on {me['species']}." if hp else f"Switch to {sw[0]}." if sw else
                    "Look and ask with the current battle text; no checked damaging move can hit this turn.",
                    why=f"{foe['species']} is in the air or underground this turn: attacks miss. It hits next turn.",
                    details=details)

    if b["kind"] == "wild":
        why_catch = catch_reason(state, foe["species"])
        balls = [i for i in ("ULTRA_BALL", "GREAT_BALL", "POKE_BALL") if bag.get(i)]
        if why_catch and balls and not danger:
            if foe["hp"] <= foe["max_hp"] // 2:
                return dict(do=f"Throw a {balls[0]} at {foe['species']}.",
                            why=f"Catch it: {why_catch}. It is weak, so the ball works more often.", details=details)
            soft = [o for o in usable if 0 < o["hi"] < foe["hp"] and o["effect"] not in (
                "OHKO_EFFECT", "RECOIL_EFFECT", "EXPLODE_EFFECT", "JUMP_KICK_EFFECT")]
            if soft:
                o = max(soft, key=lambda o: o["hi"])
                return dict(do=f"Use {o['move']} to weaken {foe['species']}, then throw a {balls[0]}.",
                            why=f"Catch it: {why_catch}. {o['move']} does at most {o['hi']}, so it cannot knock out "
                                f"{foe['species']} ({foe['hp']} HP), and its next hit cannot knock you out.",
                            details=details)
            return dict(do=f"Throw a {balls[0]} at {foe['species']} now.",
                        why=f"Catch it: {why_catch}. Every safe move could knock it out.", details=details)
    if not usable:
        sw = switch_target(state, me, foe)
        if sw:
            return dict(do=f"Switch to {sw[0]}.", why="No damaging attack with PP can hurt this enemy. " + sw[1],
                        details=details)
        return dict(do="No damaging attack with PP can hurt this enemy: switch, or restore PP if an item can do that.",
                    why="Exhausted moves cannot be used, and immune or status moves do no direct damage. "
                        "With no PP at all the game uses Struggle.", details=details)
    plan = safe_plan(me, foe, usable, me["hp"])
    if plan:
        o, n = plan
        why = (f"It knocks out {foe['species']} for sure ({o['lo']}-{o['hi']} damage, it has {foe['hp']} HP)"
               if n == 1 else f"It knocks out {foe['species']} in at most {n} hits ({o['lo']}-{o['hi']} each, it has "
                              f"{foe['hp']} HP)")
        why += " before it can knock you out." if threat else "."
        if o["note"]:
            why += f" Note: {', '.join(o['note'])}."
        return dict(do=f"Use {o['move']}{_slot(me, o['move'])}.", why=why, details=details)
    # Not safe: you could lose this Pokémon.
    if b["kind"] == "wild" and (me_first or tie) and not catch_reason(state, foe["species"]):
        return dict(do="Run (RUN is the bottom-right choice of the battle menu).", why=f"Winning this fight is not sure. You are at least as fast as {foe['species']}, so "
                    "running always works.", details=details)
    hp = heal_plan()
    if hp:
        return dict(do=f"Use {hp[0]} on {me['species']}.",
                    why=f"Now {foe['species']} could knock you out first ({threat} does up to {t_hi}, you have "
                        f"{me['hp']} HP). " + (f"With {hp[1]} HP you win the fight even if it hits hard." if hp[2] else
                                               f"With {hp[1]} HP you survive its next hit and gain more than it "
                                               f"takes away."), details=details)
    best = max(usable, key=lambda o: o["expect"])
    weak_now = best["avg"] * 3 < foe["hp"]
    if weak_now and danger:
        # This Pokémon cannot win and will faint: use its turn to heal the one that comes in next (Gen 1 allows items
        # on Pokémon in the back). It then comes in for free after this one faints.
        for t in state["team"]:
            if not can_act(t) or (t["species"] == me["species"] and t["level"] == me["level"]):
                continue
            now = duel(_party_mon(t, state["badges"]), foe)
            for item in sorted(HEAL, key=HEAL.get):
                healed = min(t["max_hp"], t["hp"] + HEAL[item])
                if not bag.get(item) or healed <= t["hp"] or now[0]:
                    continue
                after = duel(_party_mon(dict(t, hp=healed), state["badges"]), foe)
                if after[0] or (now[2] <= 1 < after[2]):
                    return dict(do=f"Use {item} on {t['species']} (in the back of your team).",
                                why=f"{me['species']} cannot win and will faint anyway. Use its turn to heal "
                                    f"{t['species']}: it then comes in for free after {me['species']} faints, and "
                                    + (f"should beat {foe['species']}." if after[0] else
                                       f"survives a hit from {foe['species']} instead of fainting at once."),
                                details=details)
    sw = switch_target(state, me, foe)
    if sw and (weak_now or danger):
        return dict(do=f"Switch to {sw[0]}.", why=sw[1], details=details)
    n = math.ceil(foe["hp"] / best["avg"]) if best["avg"] else 99
    why = f"It does the most damage: {best['lo']}-{best['hi']}, about {n} hit{'s' if n > 1 else ''} to knock out " \
          f"{foe['species']} ({foe['hp']} HP)."
    if danger:
        why += f" Risky: {foe['species']} can knock you out, and no item or switch fixes that."
    if best["note"]:
        why += f" Note: {', '.join(best['note'])}."
    return dict(do=f"Use {best['move']}{_slot(me, best['move'])}.", why=why, details=details)


def _slot(me, move):
    """Where the move is: FIGHT (top left of the battle menu), then the n-th move in the list."""
    names = [mv["move"] for mv in me["moves"]]
    return f" (FIGHT, then move {names.index(move) + 1} of {len(names)} in the list)" if move in names else ""


def battle_ui(m, state):
    """Teacher-only screen decoder. Match a filled cursor and visible menu text, never stale menu RAM alone.
    Layouts: pokered engine/battle/core.asm, home/pokemon.asm and home/list_menu.asm."""
    tiles = list(m[R.A("wTileMap"):R.A("wTileMap") + 360])
    rows = ["".join(R.CHARS.get(t, " ") if t >= 0x7f else " " for t in tiles[y * 20:(y + 1) * 20])
            for y in range(18)]
    cursors = [(i % 20, i // 20) for i, t in enumerate(tiles) if t == 0xed]
    ui = dict(phase="unknown", rows=rows, cursor_count=len(cursors), submitted=0xec in tiles)
    if "wPlayerMoveListIndex" in R.SYM:     # R12: the move list opens with the arrow on the last move used
        ui["move_index"] = m[R.A("wPlayerMoveListIndex")]
    if not cursors and not ui["submitted"]:
        # battle-043: the item list is visible between cursor draws. Matching several bag rows identifies
        # the menu, but not a selection: B is safe; never infer a highlighted item or press A here.
        start = m[R.A("wListScrollOffset")]
        labels = [b["item"] for b in state["bag"][start:start + 4]]
        if len(labels) >= 2 and all(re.sub(r"[^A-Z0-9]", "", rows[4 + 2 * i][6:].upper()).startswith(
                re.sub(r"[^A-Z0-9]", "", label)) for i, label in enumerate(labels)):
            ui.update(phase="items", cursor=None)
    if len(cursors) != 1:
        return ui
    x, y = cursors[0]
    all_text = " ".join(rows).upper()
    tail = " ".join(rows[12:]).upper()
    if x in (9, 15) and y in (14, 16) and all(w in tail for w in ("FIGHT", "ITEM", "RUN")):
        ui.update(phase="commands", cursor=(x, y))
    elif x == 5 and 13 <= y <= 16:
        mon = (state.get("battle") or {}).get("yours")
        moves = mon["moves"] if mon else []
        names = [mv["move"].replace("_", "") for mv in moves]
        visible = [re.sub(r"[^A-Z0-9]", "", row[6:]) for row in rows[13:13 + len(names)]]
        if names and names == visible and y - 13 < len(names):
            ui.update(phase="moves", cursor=y - 13)
    elif x == 12 and y in (12, 14, 16) and all(w in tail for w in ("SWITCH", "STATS", "CANCEL")):
        ui.update(phase="switch", cursor=(y - 12) // 2, selected=m[R.A("wWhichPokemon")])
    elif x == 0 and y % 2 == 1 and y < 12 and any(w in tail for w in ("CHOOSE A", "BRING OUT", "USE ITEM ON WHICH")):
        if y // 2 < len(state["team"]):
            ui.update(phase="item_target" if "USE ITEM ON WHICH" in tail else "party", cursor=y // 2,
                      forced="BRING OUT" in tail,
                      item=R.ITEMS.get(m[R.A("wCurItem" if "wCurItem" in R.SYM else "wcf91")]))
    elif x == 5 and y in (4, 6, 8):
        index = m[R.A("wListScrollOffset")] + (y - 4) // 2
        label = str(state["bag"][index]["item"]) if index < len(state["bag"]) else "CANCEL"
        visible = re.sub(r"[^A-Z0-9]", "", rows[y][6:].upper())
        if index <= len(state["bag"]) and visible.startswith(re.sub(r"[^A-Z0-9]", "", label)):
            ui.update(phase="items", cursor=index)
    return ui


def battle_step(state, advice):
    """One menu step from observed cursor to the tactical recommendation. No blind cursor resets."""
    ui = state.get("teacher_ui")
    if not ui or state["battle"]["kind"] == "lost":
        return advice
    phase, b = ui["phase"], state["battle"]
    me, foe = b.get("yours"), b.get("enemy")
    move = next((mv["move"] for mv in (me or {}).get("moves", [])
                 if mv["pp"] > 0 and foe and advice["do"].startswith("Use " + str(mv["move"]))
                 and (move_option(mv["move"], mv["pp"], me, foe) or {}).get("expect", 0) > 0), None)
    item_match = re.match(r"Use (\w+) on (\w+)", advice["do"])
    item = item_match[1] if item_match and item_match[1] in _bag(state) else None
    ball_match = re.match(r"Throw a (\w+)", advice["do"])
    if ball_match and ball_match[1] in _bag(state):
        item = ball_match[1]
    target = item_match[2] if item and item_match else next((t["species"] for t in state["team"]
             if f"Switch to {t['species']}" in advice["do"] or f": {t['species']}." in advice["do"]), None)
    forced = bool(me and not me["hp"]) or ui.get("forced", False)
    if forced and not target:
        target = next((t["species"] for t in state["team"] if can_act(t)), None)
    slot = next((i for i, t in enumerate(state["team"]) if t["species"] == target and (item or can_act(t))), None)
    action = None

    def select(current, wanted, label):
        return (f"Press {'down' if wanted > current else 'up'} once toward {label}; then look and ask again."
                if current != wanted else f"Press A once to select {label}; then look and ask again.")

    if phase == "commands" and me and foe and me["hp"] > 0:
        choice = "FIGHT" if move else "ITEM" if item or advice["do"].startswith("Throw a ") else \
                 "PKMN" if target else "RUN" if advice["do"].startswith("Run") else None
        if choice:
            tx, ty = {"FIGHT": (9, 14), "PKMN": (15, 14), "ITEM": (9, 16), "RUN": (15, 16)}[choice]
            x, y = ui["cursor"]
            action = (f"Press {'right' if tx > x else 'left'} once toward {choice}; then look and ask again." if x != tx
                      else f"Press {'down' if ty > y else 'up'} once toward {choice}; then look and ask again." if y != ty
                      else f"Press A once to {'select' if choice == 'RUN' else 'open'} {choice}; then look and ask again.")
    elif phase == "moves" and me and foe:
        if move:
            action = select(ui["cursor"], [mv["move"] for mv in me["moves"]].index(move), move)
        elif item or target or advice["do"].startswith("Run"):
            action = "Press B once to leave the move list for FIGHT / PKMN / ITEM / RUN; then look and ask again."
    elif phase == "party" and slot is not None and not item:
        action = select(ui["cursor"], slot, target + (" as the forced replacement" if forced else "; then choose SWITCH"))
    elif phase == "switch" and slot is not None and not item:
        action = (select(ui["cursor"], 0, "SWITCH") if ui.get("selected") == slot else
                  "Press B once to return to the party list; the selected Pokémon is not the recommended one.")
    elif phase == "items" and item and ui.get("cursor") is not None:
        action = select(ui["cursor"], [b["item"] for b in state["bag"]].index(item), item)
    elif phase == "item_target" and item and slot is not None and ui.get("item") == item:
        action = select(ui["cursor"], slot, target + " to receive " + item)
    if action is None and phase in ("party", "switch", "items", "item_target") and not (phase == "party" and forced):
        action = "Press B once to leave this menu; then look and ask again."
    if action is None:
        action = ("Look at the screen and ask again with the visible menu and highlighted choice. "
                  "The current screen/cursor or battle data is not clear enough for a button step.")
        if phase == "unknown" and ui.get("cursor_count") == 0 and not ui.get("submitted") and \
                re.search(r"\b(fainted|gained|used|effective)\b", " ".join(ui.get("rows", [])), re.I):
            action = "Press A once to advance the battle text, then look and ask again."
    return dict(do=action, why=advice["why"], details=["Battle plan: " + advice["do"]] + advice["details"])


def switch_target(state, me, foe, entry_hit=True):
    """The team member that does best against `foe`. It must be able to act (not frozen / asleep, PP left). With
    entry_hit it first takes the enemy's strongest hit (and its own poison / burn) while coming in; after a faint it
    comes in for free. "Beats" is only said when the same worst-case rules as for attacking (safe_plan) say so."""
    best = None
    for t in state["team"]:
        if not can_act(t) or (t["species"] == me["species"] and t["level"] == me["level"]):
            continue
        cand = _party_mon(t, state["badges"])
        cand["moves"] = [mv for mv in cand["moves"] if mv["pp"] > 0]
        if entry_hit:
            _, _, hit = best_threat(foe, cand)
            hit += residual(cand)
            if hit >= cand["hp"]:
                continue
            cand = dict(cand, hp=cand["hp"] - hit)
        usable = [o for o in (move_option(mv["move"], mv["pp"], cand, foe) for mv in cand["moves"]) if o
                  and o["expect"] > 0]
        plan = safe_plan(cand, foe, usable, cand["hp"])
        win, need, it_needs, mv = duel(cand, foe)
        if not mv or it_needs <= 1 and not plan:
            continue
        score = (plan is not None, it_needs - need)
        if best is None or score > best[0]:
            best = (score, t["species"], plan, mv, need, it_needs)
    if best:
        _, sp, plan, mv, need, it_needs = best
        coming = " even after taking a hit while switching in" if entry_hit else ""
        if plan:
            return sp, (f"{sp} beats {foe['species']} for sure{coming}: {plan[0]['move']} knocks it out in at most "
                        f"{plan[1]} hit{'s' if plan[1] > 1 else ''}.")
        return sp, (("Losing fallback, not a safe rescue: " if need >= it_needs else "Risky fallback: ")
                    + f"{sp} does best against {foe['species']}{coming} (not sure): with {mv} it needs about {need} "
                    f"hit{'s' if need > 1 else ''}, {foe['species']} needs about {it_needs}.")
    return None


# ---------- team check for the next boss ----------

def duel(me, foe):
    """Can `me` beat `foe` one on one? Returns (win, hits_you_need, hits_it_needs, your best move)."""
    opts = [o for o in (move_option(mv["move"], 99, me, foe, True) for mv in me["moves"]) if o and o["expect"] > 0]
    if not opts:
        return False, 99, 1, None
    o = max(opts, key=lambda o: o["expect"])
    need = math.ceil(foe["hp"] / max(o["expect"], 0.1))
    _, _, t_hi = best_threat(foe, me)
    t_avg = t_hi * 236 / 255
    it_needs = math.ceil(me["hp"] / t_avg) if t_avg else 99
    faster = me["stats"]["spd"] > foe["stats"]["spd"]
    return (need < it_needs or (need == it_needs and faster)), need, it_needs, o["move"]


def _calc(base, level, hp=False):
    return (base + 8) * 2 * level // 100 + (level + 10 if hp else 5)   # DV 8, no stat EXP: only used as a ratio


def _usefulness(move, types):
    m = MOVES.get(move, {})
    return (m.get("power") or 0) * (1.5 if m.get("type") in types else 1) * (m.get("accuracy") or 0) / 100


def _scaled(t, level):
    """Your Pokémon at a higher level, level by level: it learns its level-up moves, evolves at its evolution level and
    learns the new species' moves of that level too (keeps the 4 most useful). Stats grow like the game's formula; the ratio keeps
    your own DVs and stat EXP only roughly."""
    old = SPECIES.get(t["species"], {})
    sp, moves = t["species"], [m["move"] for m in t["moves"]]
    def learn(species, lv):
        for lm in SPECIES.get(species, {}).get("learnset", []):
            if lm["level"] == lv and lm["move"] not in moves:
                moves.append(lm["move"])
    for lv in range(t["level"] + 1, level + 1):
        learn(sp, lv)              # the game teaches level-up moves first (experience.asm) ...
        evo = [e for e in SPECIES.get(sp, {}).get("evolutions", []) if e.get("how") == "level" and e["level"] <= lv]
        if evo:
            sp = evo[0]["into"]
            learn(sp, lv)          # ... then evolves and checks the new species' moves at this level
    new = SPECIES.get(sp, old)
    types = new.get("types", t["types"])
    out = dict(t, species=sp, level=level, types=types)
    if old.get("base") and new.get("base"):
        out["stats"] = {k: max(1, round(v * _calc(new["base"][k], level) / _calc(old["base"][k], t["level"])))
                        for k, v in t["stats"].items()}
        out["hp"] = out["max_hp"] = round(t["max_hp"] * _calc(new["base"]["hp"], level, True)
                                          / _calc(old["base"]["hp"], t["level"], True))
    out["moves"] = [{"move": m, "pp": 99} for m in sorted(moves, key=lambda m: -_usefulness(m, types))[:4]]
    return out


def boss_keys(state, milestone_id):
    """Trainer keys of the next boss. Rival teams depend on the rival's starter (read from the game)."""
    keys = MILESTONE_BOSS.get(milestone_id, [])
    line = set()
    sp = state.get("rival_starter")
    while sp and sp not in line:
        line.add(sp)
        evo = SPECIES.get(sp, {}).get("evolutions", [])
        sp = evo[0]["into"] if evo else None
    out = []
    for key in keys:
        cls, idx = key.split(":")
        if cls.startswith("Rival") and line:
            first = (int(idx) - 1) // 3 * 3 + 1
            match = [f"{cls}:{i}" for i in range(first, first + 3)
                     if f"{cls}:{i}" in TEAMS and line & {e["species"] for e in TEAMS[f"{cls}:{i}"]["party"]}]
            key = match[0] if match else key
        out.append(key)
    return out


def team_check(state, keys):
    team = [_party_mon(dict(t, hp=t["max_hp"]), state["badges"]) for t in state["team"]]   # as if healed first
    lines, ok_all = [], True
    for key in keys:
        tr = TEAMS.get(key)
        if not tr:
            continue
        for e in tr["party"]:
            foe = {"species": e["species"], "level": e["level"], "hp": e["stats"]["hp"], "max_hp": e["stats"]["hp"],
                   "status": "ok", "types": e["types"], "stats": e["stats"], "moves": e["moves"]}
            res = [(duel(m, foe), m) for m in team]
            (win, need, it_needs, mv), m = max(res, key=lambda r: (r[0][0], r[0][2] - r[0][1]))
            ok_all &= win
            lines.append(f"{tr['class']}'s {e['species']} L{e['level']}: "
                         + (f"your {m['species']} wins with {mv} (you need ~{need} hits, it needs ~{it_needs})" if win
                            else f"hard: your best is {m['species']} with {mv}, you need ~{need} hits, it needs ~{it_needs}"))
    lead = max(team, key=lambda m: (m["level"], m["max_hp"])) if team else None
    target = None
    if not ok_all and lead:
        for lv in range(lead["level"] + 1, min(100, lead["level"] + 16)):
            big = _scaled(lead, lv)
            if all(duel(big, {"species": e["species"], "level": e["level"], "hp": e["stats"]["hp"], "status": "ok",
                              "max_hp": e["stats"]["hp"], "types": e["types"], "stats": e["stats"], "moves": e["moves"]})[0]
                   for key in keys if key in TEAMS for e in TEAMS[key]["party"]):
                target = lv
                break
    return ok_all, lines, (lead["species"], target) if target else None


# ---------- round 6: the Brock fight, turn by turn ----------

GYM1 = ["JrTrainerM:1", "Brock:1"]     # the Pewter Gym trainer, then Brock (game_facts trainers)
ON_THE_WAY = ["Route1", "Route2", "ViridianForest"]   # wild Pokémon a player meets before Brock (no Route 22 detour)


def _foe(e):
    return {"species": e["species"], "level": e["level"], "hp": e["stats"]["hp"], "max_hp": e["stats"]["hp"],
            "status": "ok", "types": e["types"], "stats": e["stats"], "moves": e["moves"]}


def _status_move(me):
    return next((mv["move"] for mv in me["moves"] if MOVES.get(mv["move"], {}).get("power", 0) == 0
                 and mv.get("pp", 1) > 0), None)


def fight(team, party, carry=False):
    """One trainer fight, turn by turn: your team in party order (the next one comes in when one faints), the enemy's
    Pokémon in order, HP carried over, PP counted. You use your best move with PP left (expected damage); the enemy
    always uses its strongest damaging move at average damage (careful: real trainers also use weaker status moves).
    Bide (Brock's Onix), modeled ONCE per Onix (it may use it again): it stores 3 turns (worst case); you use a move
    that does no damage for those turns (its PP is spent); turns without such a move you attack and get double the
    damage of those hits back. No critical hits, no stat changes. A move's PP of 0 stays 0 (None = full PP).
    Returns (win, HP left / max HP of your team, notes)."""
    mine = [dict(m, moves=[dict(mv, pp=mv["pp"] if mv.get("pp") is not None else MOVES.get(mv["move"], {}).get("pp", 10))
                           for mv in m["moves"]]) for m in team]
    notes, i = [], 0
    for e in party:
        foe = _foe(e)
        foe_hp = foe["hp"]
        bide = any((mv["move"] if isinstance(mv, dict) else mv) == "BIDE" for mv in foe["moves"])
        while foe_hp > 0:
            if i >= len(mine):
                return (False, 0.0, notes, mine) if carry else (False, 0.0, notes)
            me = mine[i]
            if me["hp"] <= 0:
                i += 1
                continue
            opts = [o for o in (move_option(mv["move"], mv["pp"], me, dict(foe, hp=foe_hp), True)
                                for mv in me["moves"] if mv["pp"] > 0) if o and o["expect"] > 0]
            if not opts:
                i += 1
                continue
            o = max(opts, key=lambda o: o["expect"])
            _, _, t_hi = best_threat(dict(foe, hp=foe_hp), me)
            hit_back = t_hi * 236 / 255
            if bide:                       # Onix stores up (modeled once per Onix, 3 turns)
                bide = False
                if math.ceil(foe_hp / max(o["expect"], 0.1)) > 2:
                    stored, waited, wait = 0.0, 0, _status_move(me)
                    for _ in range(3):           # Onix stores: it does not attack; each turn you wait or attack
                        st = next((mv for mv in me["moves"] if MOVES.get(mv["move"], {}).get("power", 0) == 0
                                   and mv["pp"] > 0), None)
                        if st:
                            st["pp"] -= 1
                            waited += 1
                            continue
                        hit = [h for h in (move_option(mv["move"], mv["pp"], me, dict(foe, hp=foe_hp), True)
                                           for mv in me["moves"] if mv["pp"] > 0) if h and h["expect"] > 0]
                        if not hit:
                            continue
                        h = max(hit, key=lambda h: h["expect"])
                        next(mv for mv in me["moves"] if mv["move"] == h["move"])["pp"] -= 1
                        foe_hp -= h["expect"]
                        stored += h["expect"]
                        if foe_hp <= 0:          # knocked out while storing: no Bide hit
                            break
                    if waited:
                        notes.append(f"Bide estimate: assumes {wait} stalls for {waited} harmless turns. "
                                     "Bide returns double the damage dealt while storing; this readiness model "
                                     "does not choose a live battle action.")
                    if foe_hp <= 0:
                        continue
                    me["hp"] -= 2 * stored       # Bide releases: double the damage it took while storing
                    if me["hp"] <= 0:
                        me["hp"] = 0
                        i += 1
                    continue                     # next turn: pick the move again (PP may have run out)
            me_first = me["stats"]["spd"] > foe["stats"]["spd"]
            next(mv for mv in me["moves"] if mv["move"] == o["move"])["pp"] -= 1
            if me_first:
                foe_hp -= o["expect"]
                if foe_hp > 0:
                    me["hp"] -= hit_back
            else:
                me["hp"] -= hit_back
                if me["hp"] > 0:
                    foe_hp -= o["expect"]
            if me["hp"] <= 0:
                me["hp"] = 0
                i += 1
    left = sum(max(0, m["hp"]) for m in mine) / max(1, sum(m["max_hp"] for m in team))
    return (True, left, notes, mine) if carry else (True, left, notes)


def _wild_mon(species, level):
    """A wild Pokémon at `level` (average DVs, no stat EXP): stats from the game's formula, its last 4 level-up moves."""
    sp = SPECIES[species]
    st = {k: _calc(sp["base"][k], level) for k in ("atk", "def", "spd", "spc")}
    hp = _calc(sp["base"]["hp"], level, True)
    moves = (sp.get("base_moves", []) + [lm["move"] for lm in sp.get("learnset", []) if lm["level"] <= level])[-4:]
    return {"species": species, "level": level, "hp": hp, "max_hp": hp, "status": "ok", "types": sp["types"],
            "stats": st, "moves": [{"move": m, "pp": MOVES.get(m, {}).get("pp", 10)} for m in moves]}


def gym1_check(state, margin=0.25, keys=None):
    """Round 6: can the team win the Pewter Gym trainer and then Brock (healed before each)? What level, or which catch
    on the way, makes it likely? Returns dict(ok, lines, level=(species, lv) or None, catch=(species, place, lv) or None)."""
    keys = tuple(keys or GYM1)
    # healed at a Pokémon Center before each fight: full HP and full PP (Sol R6C: 0 PP and 1 PP gave opposite verdicts)
    team = [_party_mon(dict(t, hp=t["max_hp"], moves=[dict(mv, pp=None) for mv in t["moves"]]), state["badges"])
            for t in state["team"]]
    if not team:
        return dict(ok=False, lines=[], level=None, catch=None)
    lines, ok = [], True
    for key in keys:
        win, left, notes = fight(team, TEAMS[key]["party"])
        who = "Brock" if key.startswith("Brock") else "the gym trainer"
        sure = win and left >= margin
        ok &= sure
        lines.append(f"Against {who} ({', '.join(e['species'] + ' L' + str(e['level']) for e in TEAMS[key]['party'])}): "
                     + (f"likely win, about {round(left * 100)}% of your HP left" if sure else
                        f"close: about {round(left * 100)}% of your HP left" if win else "likely loss") + ".")
        lines += notes
    lead = team[0]
    level = catch = None
    if not ok:
        for lv in range(lead["level"] + 1, lead["level"] + 16):
            big = [_scaled(lead, lv)] + team[1:]
            if all(fight(big, TEAMS[k]["party"])[0] and fight(big, TEAMS[k]["party"])[1] >= margin for k in keys):
                level = (lead["species"], lv, big[0]["species"])
                break
        if not level or level[1] - lead["level"] > 3:
            best = None
            for place in ON_THE_WAY:
                for w in FACTS["wild"].get(place, {}).get("grass", {}).get("mons", []):
                    base = _wild_mon(w["species"], min(w["levels"]))
                    for lv in range(base["level"], 16):
                        big = _scaled(base, lv) if lv > base["level"] else base
                        if all(fight(team + [big], TEAMS[k]["party"])[1] >= margin and fight([big], TEAMS[k]["party"])[0]
                               for k in keys):
                            if best is None or lv < best[2]:
                                best = (w["species"], place, lv, big["species"])
                            break
            catch = best
    return dict(ok=ok, lines=lines, level=level, catch=catch, keys=keys)


def _unready(g):
    """The training part of gym1_text, without "not ready yet: " and the where-to-train sentence."""
    return gym1_text(g).split(". Train by")[0].replace("not ready yet: ", "", 1)


def gym1_text(g):
    if g["ok"]:
        if g.get("keys") == ("Brock:1",):
            return "your team should win Brock alone after healing; the optional gym trainer is a separate fight."
        return "your team should win the gym trainer and Brock (heal before each fight)."
    out = "not ready yet"
    if g["level"]:
        sp, lv, into = g["level"]
        out += f": train {sp} to about level {lv}" + (f" (it becomes {into})" if into != sp else "")
    if g["catch"]:
        sp, place, lv, into = g["catch"]
        grown = f" (it becomes {into})" if into != sp else ""
        out += ("; or " if g["level"] else ": ") + f"catch a {sp} ({place}) and train it to about level {lv}{grown}"
    return out + (". Train by fighting wild Pokémon in the grass of Route 2 or Viridian Forest (close to the Pewter and "
                  "Viridian Pokémon Centers); heal when your HP is under half.")


# ---------- where to heal ----------

_OBJ = R.REF / "pokered" / "data" / "maps" / "objects"
_CONST = {n.replace("_", "").lower(): n for n in R.MAPS.values() if isinstance(n, str)}


@functools.lru_cache(None)
def _objects(const):
    """(warps, people) of a map from pokered: warps [(x, y, target)], people [(x, y, sprite)]."""
    f = next((f for f in _OBJ.glob("*.asm") if _CONST.get(f.stem.lower()) == const), None)
    t = f.read_text(encoding="utf-8") if f else ""
    return ([(int(x), int(y), w) for x, y, w in re.findall(r"warp_event\s+(\d+),\s*(\d+),\s*(\w+)", t)],
            [(int(x), int(y), s) for x, y, s in re.findall(r"object_event\s+(\d+),\s*(\d+),\s*(\w+)", t)])


def _healers():
    """Outdoor map -> where to heal there: the Pokémon Center door (Mom's house in Pallet Town) and the healer."""
    out = {}
    for const in [n for i, n in sorted(R.MAPS.items()) if i < len(TOWN_MAP)]:
        for x, y, target in _objects(const)[0]:
            if target.endswith("_POKECENTER") or target in ("INDIGO_PLATEAU_LOBBY", "REDS_HOUSE_1F"):
                who = next(((px, py) for px, py, s in _objects(target)[1] if s in ("SPRITE_NURSE", "SPRITE_MOM")), None)
                out[const] = dict(door=(x, y), inside=target, healer=who, mom=target == "REDS_HOUSE_1F")
                break
    return out


# the town map position of every outdoor map (pokered ExternalMapEntries; the table index is the map number)
TOWN_MAP = [(int(x), int(y)) for x, y in re.findall(
    r"outdoor_map\s+(\d+),\s*(\d+)", (R.REF / "pokered/data/maps/town_map_entries.asm").read_text(encoding="utf-8")
    .split("InternalMapEntries")[0])]
HEALERS = _healers()


def heal_place(state):
    """Plain-words line: where the nearest place to heal is, from the map the player is on."""
    here = state["place"]["map"]
    if here in [h["inside"] for h in HEALERS.values()]:
        h = next(h for h in HEALERS.values() if h["inside"] == here)
        who = "your Mom" if h["mom"] else "the nurse behind the counter"
        at = f" at ({h['healer'][0]},{h['healer'][1]})" if h["healer"] else ""
        return f"To heal: talk to {who}{at} (stand next to {'her' if h['mom'] else 'the counter'}, face her, " \
               f"press A, then pick YES if asked). It is free."
    ids = {n: i for i, n in R.MAPS.items()}
    outdoor = here if ids.get(here, 999) < len(TOWN_MAP) else state["place"].get("last_map")
    if ids.get(outdoor, 999) >= len(TOWN_MAP):
        return "To heal: go to the nearest Pokémon Center (a building with a red roof) and talk to the nurse."
    ox, oy = TOWN_MAP[ids[outdoor]]
    r = _heal_route(state)
    town = r["maps"][-1] if r else \
        min(HEALERS, key=lambda n: (abs(TOWN_MAP[ids[n]][0] - ox) + abs(TOWN_MAP[ids[n]][1] - oy), ids[n]))
    h = HEALERS[town]
    place = "your house (Mom heals you for free)" if h["mom"] else "the Pokémon Center (red roof, free healing)"
    leave = "" if here == outdoor or r else f"Go back out to {outdoor} first. "
    if town == outdoor:
        return f"{leave}To heal: {place} is here on {town}: its door is at ({h['door'][0]},{h['door'][1]}). " \
               f"Stand below the door and walk up into it, then talk to {'Mom' if h['mom'] else 'the nurse'} (press A)." \
               + _heal_walk(state, town, h)
    tx, ty = TOWN_MAP[ids[town]]
    side = " and ".join(w for w, d in (("north", oy - ty), ("south", ty - oy), ("west", ox - tx), ("east", tx - ox))
                        if d > 0)
    return f"{leave}To heal: the nearest is {place} in {town} ({side} of {outdoor}), door at " \
           f"({h['door'][0]},{h['door'][1]}) on that map." + _heal_walk(state, town, h)


def _heal_route(state):
    """Round 8 (Sol R8A): walk_to the nearest healer's door (Pokémon Center, or Mom in Pallet Town) by real presses."""
    pl = state["place"]
    key = (pl["map"], pl["x"], pl["y"], pl.get("last_map"),
           json.dumps([state.get(k, {}) for k in ("teacher_blocked", "teacher_events", "teacher_objects")], sort_keys=True))
    if key not in _HEAL_ROUTES:
        _HEAL_ROUTES[key] = walk_to(state, lambda m, p: m in HEALERS and p == HEALERS[m]["door"])
    return _HEAL_ROUTES[key]


_HEAL_ROUTES = {}


def _heal_walk(state, town, h):
    """Round 8 (t10-7: 25 commands to find the Viridian Center door): the real walk from where the player stands,
    to the healer's door on this map, or out of this map towards the healing town. "" if none."""
    r = _heal_route(state)
    if not r or r["maps"][-1] != town:
        return ""
    words = walk_words(state, r)
    if words and not r["exit"]:
        words[-1] += " (into the door)"
    return " The walk from where you stand: " + ", ".join(words) + "." if words else ""


def door_xy(here, target, near):
    """The door on this outdoor map into the next building (pokered warps), the one nearest `near`; None if none."""
    ids = {n: i for i, n in R.MAPS.items()}
    if not target or ids.get(here, 999) >= len(TOWN_MAP) or ids.get(target, 0) < len(TOWN_MAP):
        return None
    doors = [(x, y) for x, y, t in _objects(here)[0] if t == target]
    return min(doors, key=lambda d: abs(d[0] - near[0]) + abs(d[1] - near[1])) if doors else None


def door_step(door, near):
    """Direction from `near` into the door if `near` is the tile next to it (the record stood there), else None."""
    dx, dy = door[0] - near[0], door[1] - near[1]
    return {(0, -1): "up", (0, 1): "down", (-1, 0): "left", (1, 0): "right"}.get((dx, dy))


def door_text(here, target, near):
    """ Its door is at ...; how to step in only when the record stood right next to it (Sol S5B)."""
    d = door_xy(here, target, near)
    if not d:
        return ""
    step = door_step(d, near)
    return f" Its door is at ({d[0]},{d[1]})" + (f": stand at ({near[0]},{near[1]}) and walk {step} into it."
                                                if step else ".")


# ---------- round 7: the way out of a place our route does not use ----------

_PARENTS = {}


def _parents(const):
    """Maps with a door / stairs into `const` (where its LAST_MAP doors lead back to)."""
    if not _PARENTS:
        for m in {n for n in R.MAPS.values() if isinstance(n, str)}:
            for _, _, t in _objects(m)[0]:
                _PARENTS.setdefault(t, set()).add(m)
    return sorted(_PARENTS.get(const, ()))


def _exits(const, last=None):
    """Doors / stairs out of a map: [(x, y, target map)]; LAST_MAP is the map the player came from (or the map that
    leads in, if only one does)."""
    out, warps = [], _objects(const)[0]
    for x, y, t in warps:
        if t == "LAST_MAP":
            ps = [m for m in _parents(const) if m not in {w for _, _, w in warps}]   # not back up the stairs
            t = last if last in ps else (ps[0] if len(ps) == 1 else None)
        if t:
            out.append((x, y, t))
    return out


_EDGES = {}
EDGE_WORD = {"north": ("top", "up"), "south": ("bottom", "down"), "west": ("left", "left"), "east": ("right", "right")}


def _edges(const):
    """Outdoor neighbours across a map edge (pokered map headers): {target map: side}."""
    if not _EDGES:
        for f in (R.REF / "pokered" / "data" / "maps" / "headers").glob("*.asm"):
            t = f.read_text(encoding="utf-8")
            m = re.search(r"map_header\s+\w+,\s*(\w+)", t)
            if m:
                _EDGES[m.group(1)] = {c: side for side, c in re.findall(r"connection\s+(\w+),\s*\w+,\s*(\w+)", t)}
    return _EDGES.get(const, {})


def _legs(g, presses, start):
    """Presses -> ["down 3 to (x,y)", "jump down (over the ledge) to (x,y)", ...] with the real end squares (a ledge
    jump moves two; Sol R7B: W.legs counted one). A last press off the map edge moves one. Returns (words, end)."""
    out, p = [], start
    for d in presses:
        q = dict(W.moves(g, p, people=False)).get(d) or (p[0] + DELTA[d][0], p[1] + DELTA[d][1])
        if abs(q[0] - p[0]) + abs(q[1] - p[1]) > 1:
            out.append([f"jump {d} (over the ledge)", 0, q])
        elif out and out[-1][0] == d:
            out[-1][1:] = [out[-1][1] + 1, q]
        else:
            out.append([d, 1, q])
        p = q
    return [(w if not n else f"{w} {n}") + f" to ({q[0]},{q[1]})" for w, n, q in out], p


def way_out(state, route_maps):
    """Round 7: the player is on a map our record game never used at this point (home after a blackout, a Pokémon
    Center, a house; t9-7 spent 125 commands in its bedroom). The door / stairs to the nearest map of our route (fewest
    doors in between) and the real walk to it. Returns (target map, first map through the door, door, walk words) or
    None."""
    here = state["place"]["map"]
    goal = set(route_maps) - {here}
    seen, todo = {here: None}, [here]
    for m in todo:                                  # breadth first over doors
        if m in goal:
            break
        for t in [e[2] for e in _exits(m, state["place"].get("last_map") if m == here else None)] + list(_edges(m)):
            if t not in seen:
                seen[t] = m
                todo.append(t)
    target = next((m for m in todo if m in goal), None)
    if not target:
        return None
    first = target
    while seen[first] != here:
        first = seen[first]
    g = W.grid(here)
    pos = state["place"]["x"], state["place"]["y"]
    blocked = {tuple(p) for p in state.get("teacher_blocked", {}).get(here, [])}
    doors = {(x, y) for x, y, t in _exits(here, state["place"].get("last_map")) if t == first}
    if g and pos in doors and pos[1] not in (0, g["h"] - 1) and g["tile"][pos] in g["warp"]:
        # Already on stairs: preserve the checked step off and back on.
        for d, q in W.moves(g, pos, blocked=blocked):
            if q not in {(x, y) for x, y, _ in _objects(here)[0]} and \
                    dict(W.moves(g, q, blocked=blocked)).get(OPPOSITE[d]) == pos:
                return target, first, pos, [f"{d} 1 to ({q[0]},{q[1]})",
                                           f"{OPPOSITE[d]} 1 to ({pos[0]},{pos[1]}) (back onto the stairs)"]
    # Use the same collision, connection-offset and directional-mat rules as named
    # routes. A rim square alone does not prove there is walkable ground across it.
    route = walk_to(state, lambda m, p: m == first, max_maps=1)
    if not route or not route["exit"]:
        return None
    words = [w.replace(f" (out the door to {first})", " (out the door)") for w in walk_words(state, route)
             if not w.startswith("(off the ")]
    how = route["exit"]
    src = next(p for (m, p), step in route["steps"] if m == here and step[0] != "move")
    door = how[2] if how[0] == "edge" else \
        (src[0] + DELTA[how[3]][0], src[1] + DELTA[how[3]][1]) if len(how) == 4 else src
    if how[0] == "warp" and g["tile"][door] in g["warp"] and door[1] not in (0, g["h"] - 1):
        words = [w.replace(" (out the door)", "").replace(f" (into {first})", "") for w in words]
    return target, first, door, words


# ---------- round 8 (Sol R8A): the real walk across maps ----------

_GRIDS, _WARPS, _CONN = {}, {}, {}


def _grid(const):
    if const not in _GRIDS:
        _GRIDS[const] = W.grid(const)
    return _GRIDS[const]


def _warps(const):
    """[(x, y, target, n)]: n = the number (1-based) of the target's warp you arrive on (pokered warp_event)."""
    if const not in _WARPS:
        f = next((f for f in _OBJ.glob("*.asm") if _CONST.get(f.stem.lower()) == const), None)
        t = f.read_text(encoding="utf-8") if f else ""
        _WARPS[const] = [(int(x), int(y), w, int(n)) for x, y, w, n in
                         re.findall(r"warp_event\s+(\d+),\s*(\d+),\s*(\w+),\s*(\d+)", t)]
    return _WARPS[const]


def _conns(const):
    """{side: (target map, shift)}: across that edge you arrive on the target with the other coordinate + shift
    (pokered macros/scripts/maps.asm: _x / _y = offset * -2; Route 2 (8,0) north -> Pewter City (18,35))."""
    if not _CONN:
        for f in (R.REF / "pokered" / "data" / "maps" / "headers").glob("*.asm"):
            t = f.read_text(encoding="utf-8")
            m = re.search(r"map_header\s+\w+,\s*(\w+)", t)
            if m:
                _CONN[m.group(1)] = {s: (c, -2 * int(o)) for s, c, o in
                                     re.findall(r"connection\s+(\w+),\s*\w+,\s*(\w+),\s*(-?\d+)", t)}
    return _CONN.get(const, {})


def _warp_dest(const, w, last):
    """Where warp w = (x, y, target, n) of map const puts you: (map, (x, y)) or None."""
    t = w[2]
    if t == "LAST_MAP":
        ps = [m for m in _parents(const) if m not in {v[2] for v in _warps(const)}]
        t = last if last in ps else (ps[0] if len(ps) == 1 else None)
    tw = _warps(t) if t else []
    return (t, tw[w[3] - 1][:2]) if 0 < w[3] <= len(tw) else None


def _outward(g, p):
    """Directions facing off this map, as in pokered IsPlayerFacingEdgeOfMap."""
    return [d for d, (dx, dy) in DELTA.items() if (p[0] + dx, p[1] + dy) not in g["tile"]]


def _warp_on_entry(g, p, direction):
    """Only directional edge mats require outward facing; listed door/stair tiles do not."""
    outward = _outward(g, p)
    return g["tile"][p] in g["warp"] or not outward or direction in outward


def walk_to(state, goal, max_maps=6, limit=60000, fallback=True):
    """Prefer a walk around STAY objects. Relax static people only if there is no such walk.
    Explicitly reported blockers remain walls even on the fallback (sprites can hide or move)."""
    for people in ((True, False) if fallback else (True,)):
        route = _walk_to(state, goal, max_maps, limit, people)
        if route:
            route["people"] = people
            return route
    return None


def _walk_to(state, goal, max_maps, limit, people):
    """Fewest presses from where the player stands to a square where goal(map, (x, y)) is true, through doors,
    gates, map edges and ledges. Returns dict(cost, maps, presses, exit) or None:
    maps = the maps passed (first = here), presses = the presses on this map, exit = how this map is left
    ("warp", target, None, entry press) / ("warp", target, outward press from an edge mat) /
    ("edge", target, side) / None if the goal is on this map.
    Sol R8A: the forest north and south parts of Route 2 are not joined; straight-line distance chose wrong."""
    import heapq
    here, pos, last = state["place"]["map"], (state["place"]["x"], state["place"]["y"]), state["place"].get("last_map")
    ids = {n: i for i, n in R.MAPS.items()}
    near, todo = {here: 0}, [here]
    for m in todo:
        if near[m] < max_maps:
            for t in [e[2] for e in _exits(m, last if m == here else None)] + [c for c, _ in _conns(m).values()]:
                if t not in near:
                    near[t] = near[m] + 1
                    todo.append(t)
    start = (here, pos)
    dist, prev, heap, n = {start: 0}, {start: None}, [(0, 0, start)], 0
    while heap and n < limit:
        c, _, node = heapq.heappop(heap)
        if c > dist[node]:
            continue
        m, p = node
        if node != start and goal(m, p):
            steps, k = [], node
            while prev[k]:
                k, how = prev[k]
                steps.append((k, how))
            steps.reverse()
            maps = list(dict.fromkeys([here] + [s[0][0] for s in steps] + [m]))
            presses, out = [], None
            for (src, _), how in steps:
                if src != here:
                    break
                if how[0] == "move":
                    presses.append(how[1])
                else:
                    out = how
                    if how[0] == "edge":
                        presses.append(EDGE_WORD[how[2]][1])
                    break
            return dict(cost=c, maps=maps, presses=presses, exit=out, target=node, steps=steps)
        g = _grid(m)
        if m in R11_GUARDED and 'Boulder' in state['badges']:
            g = M.grid(state, m, g)
        if not g or p not in g["tile"]:
            continue
        blocked = {tuple(q) for q in state.get("teacher_blocked", {}).get(m, [])}
        if m in R11_GUARDED and 'Boulder' in state['badges']:
            blocked |= M.sight(state, m)
            blocked |= set(g["people"]) - set(g["balls"])
        outdoor = ids.get(m, 999) < len(TOWN_MAP)
        edge = {"up": p[1] == 0, "down": p[1] == g["h"] - 1, "left": p[0] == 0, "right": p[0] == g["w"] - 1}
        nexts = []
        for d, q in W.moves(g, p, people=people, blocked=blocked):
            if q in blocked:
                continue
            w = next((w for w in _warps(m) if w[:2] == q), None)
            # Listed doors/stairs warp on any entry. Edge mats need an outward-facing press.
            dest = (_warp_dest(m, w, last if m == here else None)
                    if w and not goal(m, q) and _warp_on_entry(g, q, d) else None)
            nexts.append((1, dest or (m, q), ("warp", dest[0], None, d) if dest else ("move", d)))
        w = next((w for w in _warps(m) if w[:2] == p), None)
        if w and not outdoor and (node == start or g["tile"][p] not in g["warp"]):
            # A sideways arrival stays on the mat, ready for its extra outward press.
            d = next((d for d, on in edge.items() if on), None)
            dest = _warp_dest(m, w, last if m == here else None) if d else None
            if dest:
                nexts.insert(0, (1, dest, ("warp", dest[0], d)))
        if outdoor:
            for side, (t, shift) in _conns(m).items():
                d = EDGE_WORD[side][1]
                tg = _grid(t) if t in near and edge[d] else None
                if tg:
                    q = {"north": (p[0] + shift, tg["h"] - 1), "south": (p[0] + shift, 0),
                         "west": (tg["w"] - 1, p[1] + shift), "east": (0, p[1] + shift)}[side]
                    if tg["tile"].get(q) in tg["walk"] and q not in {
                            tuple(b) for b in state.get("teacher_blocked", {}).get(t, [])}:
                        nexts.append((1, (t, q), ("edge", t, side)))
        for cost, node2, how in nexts:
            if node2[0] in R11_GUARDED and 'Boulder' in state['badges'] and node2[1] in M.sight(state, node2[0]):
                continue
            if node2[1] in {tuple(q) for q in state.get("teacher_blocked", {}).get(node2[0], [])}:
                continue
            if node2[0] in near and c + cost < dist.get(node2, 1e9):
                dist[node2], prev[node2] = c + cost, (node, how)
                n += 1
                heapq.heappush(heap, (c + cost, n, node2))
    return None


def walk_words(state, r):
    """The presses of walk_to's result on this map in words, with how the map is left."""
    here, pos = state["place"]["map"], (state["place"]["x"], state["place"]["y"])
    g = _grid(here)
    presses, out = list(r["presses"]), r["exit"]
    if out and out[0] == "warp" and len(out) == 4:      # stepped onto a door / stairs: that press is the last move
        presses.append(out[3])
    words, end = _legs(g, presses, pos) if g and presses else ([], pos)
    if out and out[0] == "edge":
        words.append(f"(off the {out[2]} edge to {out[1]})")
    elif out and out[0] == "warp":
        if len(out) == 3 and out[2]:
            words.append(f"{out[2]} 1 (out the door to {out[1]})")
        else:
            border = g and (end[0] in (0, g["w"] - 1) or end[1] in (0, g["h"] - 1))
            words[-1] += f" (out the door to {out[1]})" if border else f" (into {out[1]})"
    return words


def brock_route(state):
    """PewterGym.asm: trainer (3,6), facing RIGHT, sight 5. Require the left bypass.
    No relaxed-people fallback here: a route we cannot check is not a safe bypass."""
    blocked = dict(state.get("teacher_blocked", {}))
    blocked["PEWTER_GYM"] = list(blocked.get("PEWTER_GYM", [])) + [(x, 6) for x in range(3, 9)]
    if state["place"]["map"] == "PEWTER_GYM":
        p = (state["place"]["x"], state["place"]["y"])
        if p in blocked["PEWTER_GYM"]:
            return None
        if p == (4, 2):
            return dict(cost=0, maps=["PEWTER_GYM"], presses=[], exit=None, people=True,
                        target=("PEWTER_GYM", p), steps=[])
    return walk_to(dict(state, teacher_blocked=blocked), lambda m, p: m == "PEWTER_GYM" and p == (4, 2),
                   fallback=False)


def gym1_plan(state):
    """Separate fights, retaining the old conservative check when a bypass is not known."""
    route = brock_route(state)
    g = gym1_check(state, keys=("Brock:1",)) if route else gym1_check(state)
    if route:
        optional = gym1_check(state, keys=("JrTrainerM:1",))
        g["lines"] += optional["lines"]
    return g, route


def training_tiles():
    # tileset_headers.asm: Overworld grass = $52. North Route 2 is the Pewter-side patch.
    g = _grid("ROUTE_2")
    return {p for p, tile in g["tile"].items() if tile == 0x52 and p[1] < 16} if g else set()


def training_needs_heal(state):
    return any(t["hp"] * 2 <= t["max_hp"] or t["status"] != "ok" or
               not any(mv["pp"] is None or mv["pp"] > 0 for mv in t["moves"]) for t in state["team"])


def training_advice(state, explicit=False):
    """Route to actual grass, then a reversible two-tile circuit; healing and return use the same purpose."""
    g, bypass = gym1_plan(state)
    check = "Brock readiness: " + gym1_text(g)
    if training_needs_heal(state):
        return dict(do="Pause training and heal now: " + heal_place(state),
                    why="Heal at half HP or less, after a faint, with a status problem, or when PP runs out.",
                    details=[check, "Training purpose: after healing, resume the grass route until ready; then return to Brock."])
    if g["ok"] and not explicit:
        if bypass is not None and bypass["cost"] == 0:
            return way_advice(state)
        words = walk_words(state, bypass) if bypass else []
        return dict(do="Ready for Brock after healing. Return to PEWTER_GYM; "
                       + ("skip the optional trainer using the checked bypass." if bypass else
                          "no checked bypass is available from here, so prepare for the optional trainer too."),
                    why=check + " Estimates use full HP/PP, average damage, no critical hits or misses.",
                    details=["The way back to Brock: " + (", ".join(words) + ". There, ask again." if words else
                             "No checked bypass from here; ask for the gym route before walking past any trainer."),
                             "Heal before the gym: " + heal_place(state)])
    tiles = training_tiles()
    here = state["place"]
    pos = (here["x"], here["y"])
    r = None if here["map"] == "ROUTE_2" and pos in tiles else walk_to(
        state, lambda m, p: m == "ROUTE_2" and p in tiles)
    details = [check]
    if r:
        details.append("The way to the training grass (ROUTE_2), from where you stand: "
                       + ", ".join(walk_words(state, r)) + ". There, ask again for the next leg.")
        pos = r["target"][1]
    elif here["map"] != "ROUTE_2" or pos not in tiles:
        return dict(do="Train first, but no checked walk to the northern ROUTE_2 grass is available from here. Look and ask again.",
                    why=check, details=details)
    grid = _grid("ROUTE_2")
    pair = next(((d, q) for d, q in W.moves(grid, pos) if q in tiles and
                 pos in dict(W.moves(grid, q)).values()), None)
    if pair:
        d, q = pair
        back = next(d2 for d2, p2 in W.moves(grid, q) if p2 == pos)
        details.append(f"Training circuit: at ({pos[0]},{pos[1]}), {d} 1 to ({q[0]},{q[1]}), "
                       f"{back} 1 back; repeat these walkable grass steps, stop for battles, and check HP after each fight.")
    details.append("Training purpose: heal at half HP or less or with status/empty PP; return to Brock when the readiness check passes, after healing.")
    return dict(do="Train first in the northern ROUTE_2 grass near Viridian Forest; "
                   + ("follow the grass walk below." if r else "you are in the grass: use the circuit below."),
                why=check, details=details)


# ---------- the way ----------

ACTION_TEXT = {"talk": "talk (press A)", "dialogue": "talk (press A)", "interact": "check it (press A)",
               "take": "pick up the item (press A)", "push": "push the boulder", "bicycle": "get on the Bicycle",
               "squirtleIChooseYou": "take Squirtle's Poké Ball (press A)", "talkToBill": "talk to Bill",
               "procureBicycle": "get the Bicycle at the counter (needs the Bike Voucher)",
               "giveWater": "give the guard a drink", "playPokeFlute": "play the Poké Flute (wakes Snorlax)",
               "pokeDoll": "use the Poké Doll (the ghost battle ends)", "depositPokemon": "use the PC: deposit Pokémon",
               "shopTM07": "buy items here", "shopPokeDoll": "buy a Poké Doll", "refShopViridian": "buy items here",
               "refShopPewter": "buy items here", "refShopRepels": "buy Repels", "refShopBuffs": "buy items here",
               "refShopVermilionLate": "buy items here", "refMaybeHeal": "heal at the nurse if needed",
               "catchOddish": "catch an Oddish"}


def _action_text(a):
    d = DIR_WORD.get(a.get("dir") or "", "")
    do = a["do"]
    if do == "skill":
        return "use an HM here (Cut / Surf / Strength)"
    if do == "fly":
        return "fly"
    if do in ("teach", "refTeach", "teachThrash"):
        return "teach a move (TM / HM)"
    t = ACTION_TEXT.get(do)
    if not t:
        return None
    if d and do in ("talk", "dialogue", "interact", "take"):
        t = t.replace("(press A)", f"(face {d}, press A)")
    if d and do == "push":
        t += f" {d}"
    return t


def walk_from(seq, start):
    """Walk instructions from `start` (x, y) along seq (points (x, y) and action dicts, in time order)."""
    out, cur = [], None
    for p in seq:
        if isinstance(p, tuple):
            if cur is None:
                if p != tuple(start):
                    out.append(f"go to ({p[0]},{p[1]})")
                cur = p
                continue
            for n, word in ((p[0] - cur[0], "right" if p[0] > cur[0] else "left"),
                            (p[1] - cur[1], "down" if p[1] > cur[1] else "up")):
                if n:
                    last = out[-1].split() if out else []
                    if len(last) == 2 and last[0] == word and last[1].isdigit():
                        out[-1] = f"{word} {int(last[1]) + abs(n)}"
                    else:
                        out.append(f"{word} {abs(n)}")
            cur = p
        else:
            t = _action_text(p)
            if t and (not out or out[-1] != t):
                out.append(t)
    return out


ORDER = [mid for mid, *_ in R.MILESTONES]


OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}


def tidy(walk):
    """Merge steps along one axis: "up 4, down 1, up 1, down 1, up 5" (the bot's luck wiggles) -> "up 8"."""
    out = []
    for step in walk:
        parts = step.split()
        if len(parts) == 2 and parts[0] in OPPOSITE and parts[1].isdigit() and out:
            last = out[-1].split()
            if len(last) == 2 and last[0] in (parts[0], OPPOSITE[parts[0]]) and last[1].isdigit():
                net = int(last[1]) * (1 if last[0] == parts[0] else -1) + int(parts[1])
                out.pop()
                if net:
                    out.append(f"{parts[0] if net > 0 else OPPOSITE[parts[0]]} {abs(net)}")
                continue
        out.append(step)
    return out


DELTA_WORD = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def with_coords(walk, start):
    """Round 6: each move gets the tile it ends on, so a player can check where they are on a long walk (the forest):
    "up 32" -> "up 32 to (25,9)"."""
    out, (x, y) = [], start
    for step in walk:
        parts = step.split()
        done = re.search(r"\bto \((-?\d+),(-?\d+)\)", step)
        if done:    # R16 (Sol R16): already annotated: keep its end tile and move the cursor there, no second "to"
            x, y = int(done.group(1)), int(done.group(2))
        elif len(parts) == 2 and parts[0] in DELTA_WORD and parts[1].isdigit():
            dx, dy = DELTA_WORD[parts[0]]
            x, y = x + dx * int(parts[1]), y + dy * int(parts[1])
            step = f"{step} to ({x},{y})"
        elif len(parts) > 1 and parts[0] == "jump" and parts[1] in DELTA_WORD:   # a ledge: two squares
            dx, dy = DELTA_WORD[parts[1]]
            x, y = x + 2 * dx, y + 2 * dy
            step = f"{step} to ({x},{y})"
        else:
            m = re.match(r"go to \((\d+),(\d+)\)", step)
            if m:
                x, y = int(m.group(1)), int(m.group(2))
        out.append(step)
    return out


def rejoin(here, pos, pts, blocked=()):
    """Round 6: off our route, the real shortest way back onto it (walkable.py: trees, walls, ledges, people), to the
    tile that leaves the least walking in total. The forest walk (21 Oct) showed "go to (2,22)" runs into trees.
    Returns (walk words, k, tile): join the route at `tile` on the leg pts[k] -> pts[k+1]; None if no way is known."""
    g = W.grid(here)
    if not g or tuple(pos) not in g["tile"]:
        return None
    dist, todo = {tuple(pos): (0, None)}, [tuple(pos)]
    for p in todo:                                  # breadth first: list grows while we walk it
        for d, q in W.moves(g, p, blocked=blocked):
            if q not in dist:
                dist[q] = (dist[p][0] + 1, (d, p, abs(q[0] - p[0]) + abs(q[1] - p[1]) > 1))
                todo.append(q)
    best, rem = None, 0
    for k in range(len(pts) - 1, -1, -1):           # from the end back, so `rem` = route length left after a tile
        a, b = tuple(pts[k][:2]), tuple(pts[min(k + 1, len(pts) - 1)][:2])
        n = abs(b[0] - a[0]) + abs(b[1] - a[1])
        for i in range(n, -1, -1):
            t = (a[0] + (b[0] - a[0]) * i // max(n, 1), a[1] + (b[1] - a[1]) * i // max(n, 1))
            if t in dist and (best is None or dist[t][0] + rem + (n - i) < best[0]):
                best = (dist[t][0] + rem + (n - i), k, t)
        rem += n
    if best is None:
        return None
    _, k, t = best
    steps, p = [], t
    while dist[p][1]:
        d, p, jump = dist[p][1]
        steps.append(f"jump {d}" if jump else d)
    words = []
    for s in reversed(steps):
        if s.startswith("jump"):
            words.append(s + " (over the ledge)")
        elif words and words[-1].split()[0] == s:
            words[-1] = f"{s} {int(words[-1].split()[1]) + 1}"
        else:
            words.append(f"{s} 1")
    return words, k, t


def repair(here, pts, blocked=()):
    """Round 6: our record's logged points are turning points; a straight leg between two can run through a square
    the player cannot pass (forest walk 21 Oct: the Antidote ball at (25,11) on "up 32 to (25,9)"). Each leg is
    checked against walls, ledges, item balls and static people. Try a real detour first, relaxing static people
    only when necessary. Observed blockers are never relaxed. None means no checked detour is available."""
    g = W.grid(here)
    if not g or len(pts) < 2:
        return pts
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        (ax, ay), (bx, by) = tuple(a[:2]), tuple(b[:2])
        dirs = ["right" if bx > ax else "left"] * abs(bx - ax) + ["down" if by > ay else "up"] * abs(by - ay)
        p, i, ok = (ax, ay), 0, True
        while i < len(dirs):
            d = dirs[i]
            q = dict(W.moves(g, p, blocked=blocked)).get(d)
            one = (p[0] + DELTA_WORD[d][0], p[1] + DELTA_WORD[d][1])
            if q == one:
                p, i = q, i + 1
            elif q and i + 1 < len(dirs) and dirs[i + 1] == d:     # the record jumped a ledge here
                p, i = q, i + 2
            else:
                ok = False
                break
        if not ok:
            pr = W.path(here, (ax, ay), {(bx, by)}, blocked=blocked)
            people = True
            if pr is None:
                pr = W.path(here, (ax, ay), {(bx, by)}, people=False, blocked=blocked)
                people = False
            if pr is not None:
                p, turns = (ax, ay), []
                for n, d in enumerate(pr):
                    p = dict(W.moves(g, p, people=people, blocked=blocked))[d]
                    if n + 1 < len(pr) and pr[n + 1] != d:
                        turns.append(p)
                if p == (bx, by):
                    out += [[tx, ty, a[2], a[3] + (k + 1) / 1000] for k, (tx, ty) in enumerate(turns)]
            elif blocked:
                return None
        out.append(b)
    return out


def on_segment(a, b, p):
    """True if tile p lies on the straight line from a to b (same row or column, between them)."""
    return (a[0] == b[0] == p[0] and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])) or \
        (a[1] == b[1] == p[1] and min(a[0], b[0]) <= p[0] <= max(a[0], b[0]))


def _sig_dist(sig, prog):
    """10 per main milestone that differs (another story stage), 1 per optional milestone or key item. Only
    milestones up to the player's next goal count: a player who did something earlier than our record game (Misty
    before Bill) still matches the record moment before that next goal."""
    nxt = next((mid for mid in ORDER if mid not in prog["done"]), None)
    upto = set(ORDER[:ORDER.index(nxt) + 1]) if nxt else set(ORDER)
    diff = (set(sig["done"]) ^ set(prog["done"])) & upto
    return 10 * len(diff - R.OPTIONAL) + len(diff & R.OPTIONAL) + len(set(sig["keys"]) ^ set(prog["keys"]))


def _edge(map_name, p):
    """Say which side of an outdoor map an exit is on (houses and caves: the exit is a door / ladder tile)."""
    w = max((q[0] for v in WALKS if v["map"] == map_name for q in v["points"]), default=0)
    h = max((q[1] for v in WALKS if v["map"] == map_name for q in v["points"]), default=0)
    if p[1] == 0:
        return ": walk off the top (north) edge"
    if p[0] == 0:
        return ": walk off the left (west) edge"
    if p[1] >= h and h > 8:
        return ": walk off the bottom (south) edge"
    if p[0] >= w and w > 8:
        return ": walk off the right (east) edge"
    return ": a door or stairs there"


DELTA = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def _last_step(points):
    """Direction of the last move on a map visit (None if the visit has one point)."""
    xy = [tuple(p[:2]) for p in points]
    for a, b in zip(reversed(xy[:-1]), reversed(xy[1:])):
        if a != b:
            dx, dy = b[0] - a[0], b[1] - a[1]
            return ("right" if dx > 0 else "left") if abs(dx) >= abs(dy) else ("down" if dy > 0 else "up")
    return None


@functools.lru_cache(None)
def _exit_hop(here, target, last):
    """First real map transition when the record skips maps (Fly, Dig or missing logged positions)."""
    seen, todo = {here: None}, [here]
    for m in todo:
        if m == target:
            while seen[m] != here:
                m = seen[m]
            return m
        for t in [w[2] for w in _exits(m, last if m == here else None)] + list(_edges(m)):
            if t not in seen:
                seen[t] = m
                todo.append(t)
    return None


@functools.lru_cache(None)
def _exit_size(map_name):
    """Map dimensions still exist when the collision grid cannot be decoded."""
    dims = W._tables()["dims"].get(map_name)
    return (dims[0] * 2, dims[1] * 2) if dims else None


@functools.lru_cache(None)
def _elevator_targets(map_name):
    if not map_name.endswith("_ELEVATOR"):
        return set()
    f = next((f for f in (R.REF / "pokered/scripts").glob("*.asm")
              if _CONST.get(f.stem.lower()) == map_name), None)
    return set(re.findall(r"\bdb\s+\d+,\s*(\w+)", f.read_text(encoding="utf-8"))) if f else set()


@functools.lru_cache(None)
def _travel_endings():
    """Match recorded terminal actions to the route's explicit Fly, Dig and Escape Rope commands."""
    route = json.loads((R.settings.KB / "bot_route.json").read_text(encoding="utf-8"))
    commands = {}
    for section in route["sections"]:
        for visit in section["steps"]:
            for action in visit["path"]:
                if not isinstance(action, dict):
                    continue
                name = ("Fly" if action.get("do") == "fly" else
                        "Dig" if action.get("do") == "skill" and action.get("move") == "dig" else
                        "Escape Rope" if action.get("do") == "item" and action.get("item") == "escape_rope" else None)
                if name:
                    commands[section["split"], visit["map"], action["do"]] = name
    out = {}
    for i, visit in enumerate(WALKS):
        if not visit["actions"]:
            continue
        name = commands.get((visit["split"], visit["map"], visit["actions"][-1]["do"]))
        nxt = next((v["map"] for v in WALKS[i + 1:] if v["map"] != visit["map"]), None)
        if name and nxt:
            out[visit["map"], nxt, tuple(visit["points"][-1])] = name
    return out


def _scripted_ending(map_name, nxt_map, end):
    """These record endings trigger travel without an ordinary map warp / connected edge."""
    tile = tuple(end[:2])
    # scripts/PokemonTower7F.asm: MrFujiText -> WarpToMrFujiHouseScript;
    # objects/PokemonTower7F.asm: Fuji stands at (10,3).
    if (map_name, nxt_map, tile) == ("POKEMON_TOWER_7F", "MR_FUJIS_HOUSE", (10, 4)):
        return "At (10,4), face up and press A to talk to Mr. Fuji; his conversation takes you to MR_FUJIS_HOUSE."
    # scripts/VictoryRoad3F.asm .SwitchOrHoleCoords (the switch at (3,5) is NOT a warp),
    # scripts/PokemonMansion3F.asm .holeCoords (the third hole leads to 2F).
    holes = {("VICTORY_ROAD_3F", "VICTORY_ROAD_2F"): {(23, 15)},
             ("POKEMON_MANSION_3F", "POKEMON_MANSION_1F"): {(16, 14), (17, 14)},
             ("POKEMON_MANSION_3F", "POKEMON_MANSION_2F"): {(19, 14)}}
    if tile in holes.get((map_name, nxt_map), set()):
        return f"Walk onto the scripted hole at ({tile[0]},{tile[1]}); it takes you to {nxt_map}."
    # Field moves need the actual recorded point (including story/frame), not just a matching tile:
    # a caller asking for a walking exit from Bill's house may still need its real door.
    travel = _travel_endings().get((map_name, nxt_map, tuple(end)))
    if travel:
        return f"Keep the recorded ending at ({tile[0]},{tile[1]}): use {travel} to travel toward {nxt_map}."
    return None


def _real_inferred_exit(map_name, nxt_map, end, step):
    """Only replace a guess that is neither a warp tile nor a connected map edge."""
    x, y = (end[0] + DELTA[step][0], end[1] + DELTA[step][1]) if step else end[:2]
    if any((x, y) == (wx, wy) for wx, wy, _ in _objects(map_name)[0]):
        return True
    size, side = _exit_size(map_name), _edges(map_name).get(nxt_map)
    if not size or not side:
        return False
    width, height = size
    return {"north": y <= 0 and 0 <= x < width, "south": y >= height - 1 and 0 <= x < width,
            "west": x <= 0 and 0 <= y < height, "east": x >= width - 1 and 0 <= y < height}[side]


def _record_exit(map_name, nxt_map, end, step, near=None, last=None):
    """Check the inferred exit against pokered, then choose a real warp / connected edge.
    The last recorded direction need not be the warp press (house door: left, then unlogged down).
    `near` is the player's position, so paired door mats use the nearer real door."""
    if _scripted_ending(map_name, nxt_map, end):
        return None
    end, near = tuple(end[:2]), tuple(near[:2]) if near is not None else tuple(end[:2])
    g = W.grid(map_name)
    size = _exit_size(map_name)
    if not size or not nxt_map:
        return None
    exits = _exits(map_name, last or nxt_map)
    if nxt_map in _elevator_targets(map_name):
        # Elevator scripts replace the UNUSED_MAP placeholder with the selected floor.
        exits = [(x, y, nxt_map) for x, y, _ in _objects(map_name)[0]]
    target = nxt_map if any(t == nxt_map for _, _, t in exits) or nxt_map in _edges(map_name) else \
        _exit_hop(map_name, nxt_map, last)
    if not target:
        return None
    tiles = [(x, y) for x, y, t in exits if t == target]
    inferred = (end[0] + DELTA[step][0], end[1] + DELTA[step][1]) if step else end
    if tiles:
        # Some warp_event entries sit on an impassable tile (forest gates' left top
        # entry). Try the other real doors rather than falling back to end + step.
        for tile in sorted(tiles, key=lambda p: (p != inferred, abs(p[0] - near[0]) + abs(p[1] - near[1]))):
            recorded_entry = tile == inferred and door_step(tile, end)
            if g and g["tile"].get(tile) not in g["walk"] and not recorded_entry:
                continue
            if tile[1] == size[1] - 1:  # directional mats must be entered facing out
                neighbours = [((tile[0], tile[1] - 1), "down")]
            elif end == tile and step and not (0 <= inferred[0] < size[0] and 0 <= inferred[1] < size[1]):
                neighbours = [(end, step)]
            elif recorded_entry and (not g or g["tile"].get(tile) not in g["walk"]):
                # The record can enter a scripted door that opens after a boss;
                # unknown collision grids still retain their real static warp.
                neighbours = [(end, recorded_entry)]
            else:
                neighbours = [(p, d) for d, (dx, dy) in DELTA.items()
                              for p in [(tile[0] - dx, tile[1] - dy)]
                              if g and p in g["tile"] and _warp_on_entry(g, tile, d)]
                neighbours.sort(key=lambda v: abs(v[0][0] - end[0]) + abs(v[0][1] - end[1]))
            for stand, into in neighbours:
                if g and g["tile"].get(tile) in g["walk"] and stand != tile and \
                        dict(W.moves(g, stand, people=False)).get(into) != tile:
                    continue
                if g and W.path(map_name, near, {stand}, people=False) is None:
                    continue
                return dict(tile=tile, stand=stand, step=into, target=target, side=None)
        return None
    side = _edges(map_name).get(target)
    if not side or not g:
        return None
    tg, shift = W.grid(target), _conns(map_name)[side][1]
    rim = []
    for p in g["tile"]:
        if not {"north": p[1] == 0, "south": p[1] == g["h"] - 1,
                "west": p[0] == 0, "east": p[0] == g["w"] - 1}[side]:
            continue
        q = {"north": (p[0] + shift, tg["h"] - 1), "south": (p[0] + shift, 0),
             "west": (tg["w"] - 1, p[1] + shift), "east": (0, p[1] + shift)}[side] if tg else None
        if tg and q in tg["tile"] and (p == end or
                (g["tile"][p] in g["walk"] and tg["tile"][q] in tg["walk"])):
            rim.append(p)
    if not rim:
        return None
    tile = min(rim, key=lambda p: abs(p[0] - end[0]) + abs(p[1] - end[1]))
    return dict(tile=tile, stand=tile, step=EDGE_WORD[side][1], target=target, side=side)


def _exit_walk(map_name, start, exit_, blocked=()):
    """Checked final walk, without assuming that a static boulder can be pushed out of the way."""
    # The people=False fallback may relax NPCs, never boulders. Without a checked push plan,
    # keep the recorded ending rather than invent a Strength puzzle solution.
    blocked = set(blocked) | {(x, y) for x, y, sprite in _objects(map_name)[1] if sprite == "SPRITE_BOULDER"}
    if exit_["tile"] in blocked:
        return None
    g = W.grid(map_name)
    if not exit_["side"] and exit_["stand"] != exit_["tile"] and (not g or
            dict(W.moves(g, exit_["stand"], people=False, blocked=blocked)).get(exit_["step"]) != exit_["tile"]):
        return None
    for people in (True, False):
        presses = W.path(map_name, tuple(start[:2]), {exit_["stand"]}, people=people, blocked=blocked)
        if presses is not None:
            words = _legs(W.grid(map_name), presses, tuple(start[:2]))[0]
            return [re.sub(r" to \(-?\d+,-?\d+\)$", "", w) for w in words] + [f"{exit_['step']} 1"]
    return None


def _exit_text(map_name, nxt_map, end, step, near=None, last=None):
    scripted = _scripted_ending(map_name, nxt_map, end)
    if scripted:
        return scripted
    exit_ = _record_exit(map_name, nxt_map, end, step, near, last)
    if not exit_:
        return f"No checked door or map edge to {nxt_map} is available from this map."
    tile, stand, into = exit_["tile"], exit_["stand"], exit_["step"]
    via = f" (first through {exit_['target']})" if exit_["target"] != nxt_map else ""
    if exit_["side"]:
        side = exit_["side"]
        return (f"The way to {nxt_map}{via}: walk off the {EDGE_WORD[side][0]} ({side}) edge "
                f"at ({tile[0]},{tile[1]}).")
    mat = tile[1] == _exit_size(map_name)[1] - 1
    return (f"The way to {nxt_map}{via} is the stairs / door at ({tile[0]},{tile[1]}): "
            f"stand at ({stand[0]},{stand[1]})" + (" above it" if mat else "") +
            f" and walk {into} onto it" + (" (out the door)." if mat else "."))


def _record_exit_text(map_name, nxt_map, end, step):
    """Even a failed record suffix must never invent a door from the last direction."""
    return _exit_text(map_name, nxt_map, end, step)


def _record_walk_leaves(state, walk):
    """A recorded, action-free walk is usable only if its final press really exits.
    Do not cancel a step off stairs and back onto them, or a sideways mat arrival
    and its outward press. A connected rim must also have a walkable destination.
    """
    here = state["place"]["map"]
    g = W.grid(here)
    if not g:
        return False
    pos = state["place"]["x"], state["place"]["y"]
    blocked = {tuple(p) for p in state.get("teacher_blocked", {}).get(here, [])}
    blocked |= {(x, y) for x, y, sprite in _objects(here)[1] if sprite == "SPRITE_BOULDER"}
    warps = {(x, y) for x, y, _ in _exits(here, state["place"].get("last_map"))}
    presses = []
    for word in walk:
        move = re.fullmatch(r"(up|down|left|right) (\d+)", word)
        jump = re.fullmatch(r"jump (up|down|left|right)(?: \(over the ledge\))?", word)
        if not move and not jump:
            return False
        presses += [move[1]] * int(move[2]) if move else [jump[1]]
    for i, direction in enumerate(presses):
        q = dict(W.moves(g, pos, people=False, blocked=blocked)).get(direction)
        leaves = q in warps and _warp_on_entry(g, q, direction) if q is not None else False
        if q is None:
            dx, dy = DELTA[direction]
            if (pos[0] + dx, pos[1] + dy) in g["tile"]:
                return False
            leaves = pos in warps
            side = next((s for s, (_, d) in EDGE_WORD.items() if d == direction), None)
            conn = _conns(here).get(side)
            if not leaves and conn:
                target, shift = conn
                tg = W.grid(target)
                if tg:
                    dest = {"up": (pos[0] + shift, tg["h"] - 1), "down": (pos[0] + shift, 0),
                            "left": (tg["w"] - 1, pos[1] + shift), "right": (0, pos[1] + shift)}[direction]
                    leaves = tg["tile"].get(dest) in tg["walk"]
            if not leaves:
                return False
        if leaves:
            return i == len(presses) - 1
        pos = q
    return False


def match_record(state):
    """The moment of the record game that fits this player best: same story progress first, then the nearest tile on
    this map, then the earliest. Returns (visit index, point index, story distance) or None."""
    prog = R.progress(state)
    here, pos = state["place"]["map"], (state["place"]["x"], state["place"]["y"])
    best = None
    for vi, v in enumerate(WALKS):
        if v["map"] != here:
            continue
        for j, p in enumerate(v["points"]):
            key = (_sig_dist(SIGS[p[2]], prog), abs(p[0] - pos[0]) + abs(p[1] - pos[1]), vi, j)
            if best is None or key < best:
                best = key
    if not best:
        return None
    vi, j = handover(here, best[2], best[3], pos)
    return (vi, j, best[0])


MART_ITEMS = {"POKE_BALL", "ANTIDOTE", "PARLYZ_HEAL", "BURN_HEAL"}   # pokered data/items/marts.asm: Viridian


def skip_mart(state, vi, j):
    """Round 8: after the Pokédex our record game shops in the Viridian Mart, so the teacher sent every player there,
    also players who had shopped already (t10-7 n232 asked for Route 2 and got the Mart; 26-56 commands in the Mart
    per teacher game). With a Viridian Mart item in the bag (or under 100 money), go on to the walk out of town."""
    if state["place"]["map"] == "VIRIDIAN_CITY" and vi + 2 < len(WALKS) and WALKS[vi + 1]["map"] == "VIRIDIAN_MART" \
            and WALKS[vi + 2]["map"] == "VIRIDIAN_CITY" and (state["story"]["next"] or {}).get("id") == "badge1" \
            and (MART_ITEMS & set(_bag(state)) or state["money"] < 100):
        return vi + 2, 0
    return vi, j


def handover(here, vi, j, pos):
    """The Viridian Mart doorstep after the Pokédex: the player stands where the walk into the Mart ENDS and the later
    walk out of it starts (its first two points: the door, then the step off it; same story stage). Use the later walk:
    before, players who came out of the Mart were sent back in (4 times in rounds 1-4; step 5). Only there: elsewhere
    (Celadon Mart 5F -> roof drinks) the later walk can skip a needed visit (Sol S5B)."""
    if here == "VIRIDIAN_CITY" and vi + 1 < len(WALKS) and WALKS[vi + 1]["map"] == "VIRIDIAN_MART" \
            and j == len(WALKS[vi]["points"]) - 1 and tuple(WALKS[vi]["points"][j][:2]) == pos:
        later = next(((k, i) for k in range(vi + 1, len(WALKS)) if WALKS[k]["map"] == here
                      for i, q in enumerate(WALKS[k]["points"][:2])
                      if tuple(q[:2]) == pos and q[2] == WALKS[vi]["points"][j][2]), None)
        if later is not None:
            return later
    return vi, j


def off_route(state, nxt, why, maps, never, through):
    """Round 7: on a map our route does not use now, say the way out to the nearest route map first."""
    here = state["place"]["map"]
    out = way_out(state, maps)
    details = [through + " > ".join(maps[:12]) + "."]
    if not out:
        return dict(do=f"Next goal: {nxt['goal']}. {never}", why=why, details=details)
    target, first, door, words = out
    via = "" if first == target else f" (through {first})"
    if isinstance(door, str):                        # a map edge: door = north / south / west / east
        side, step = EDGE_WORD[door]
        do = (f"Next goal: {nxt['goal']}. {here} is not on our route now: walk off the {side} ({door}) edge of this "
              f"map to {first}" + (f", then on to {target}" if first != target else "")
              + "; from there ask again for the route.")
        if words:
            details.insert(0, "The way out, from where you stand: " + ", ".join(words) + ". (x grows to the right, "
                           "y grows down.)")
        return dict(do=do, why=why, details=details)
    do = (f"Next goal: {nxt['goal']}. {here} is not on our route now: leave by the door / stairs at "
          f"({door[0]},{door[1]}) and go to {target}{via}; from there ask again for the route.")
    if words:
        details.insert(0, "The way out, from where you stand: " + ", ".join(words) + ". (x grows to the right, "
                       "y grows down.)")
    return dict(do=do, why=why, details=details)


def way_advice(state):
    """Next goal, the next map and the walk on this map, from the record game's walk at the same story moment."""
    nxt = state["story"]["next"]
    if not nxt:
        return dict(do="You are the Champion. The game is beaten.", why="You entered the Hall of Fame.", details=[])
    here, pos = state["place"]["map"], (state["place"]["x"], state["place"]["y"])
    why = _reason_line(state, nxt)
    if here in DETOUR and nxt["id"] in PRE_BROCK:
        v = DETOUR[here]
        end, step = v["points"][-1], _last_step(v["points"])
        return dict(do=f"Next goal: {nxt['goal']}. {here} is a side trip you do not need now: go to {DETOUR_BACK}, "
                       f"then on to the next goal.", why=why,
                    details=[_exit_text(here, DETOUR_BACK, end, step),
                             f"From ({pos[0]},{pos[1]}) head east (right) to that edge; if something blocks you, step up "
                             "or down and try right again."])
    m = match_record(state)
    if not m:
        prog = R.progress(state)
        first = min(range(len(WALKS)), key=lambda i: (_sig_dist(SIGS[WALKS[i]["points"][0][2]], prog), i))
        maps = list(dict.fromkeys(w["map"] for w in WALKS[first:first + 40]))
        return off_route(state, nxt, why, maps, f"Our route never goes to {here} for this.",
                         "From this point of the story our route goes through: ")
    vi, j, dist = m
    if dist >= 10:   # our record game never stood on this map at this story stage: say where the step happens
        prog = R.progress(state)
        best = min(_sig_dist(SIGS[p[2]], prog) for w in WALKS for p in w["points"])
        maps = list(dict.fromkeys(w["map"] for w in WALKS if any(_sig_dist(SIGS[p[2]], prog) == best
                                                                 for p in w["points"])))
        return off_route(state, nxt, why, maps, f"Our record game was never on {here} at this point of the story.",
                         "At this point of the story our route goes through: ")
    vi, j = skip_mart(state, vi, j)
    v = WALKS[vi]
    t0 = v["points"][j][3]
    # walk only to where the story moves on (after that the game takes over, e.g. Oak walks you to his lab)
    stage = v["points"][j][2]
    cut = next((p[3] for p in v["points"][j:] if p[2] != stage), None)
    pts_now = [p for p in v["points"][j:] if cut is None or p[3] <= cut]
    P = v["points"]
    if j + 1 < len(P) and pts_now[1:] and on_segment(P[j], P[j + 1], pos):
        pts_now = [[pos[0], pos[1], P[j][2], P[j][3]]] + pts_now[1:]          # on the way to the next point
    elif j > 0 and on_segment(P[j - 1], P[j], pos) and tuple(P[j][:2]) != pos:
        pts_now = [[pos[0], pos[1], P[j][2], P[j][3] - 1]] + pts_now          # on the way to this point
    join = None
    if tuple(pts_now[0][:2]) != tuple(pos):     # round 6: off the route -> a real path back onto it
        acts = [a["frame"] for a in v["actions"] if a["frame"] >= t0 and (cut is None or a["frame"] <= cut)]
        upto = [p for p in pts_now if not acts or p[3] <= min(acts)] or pts_now[:1]   # never skip a story action
        join = rejoin(here, pos, upto, {tuple(p) for p in state.get("teacher_blocked", {}).get(here, [])})
        if join is None and W.grid(here):
            return dict(do="No checked rejoin around the observed blocker is available. Look and ask with the current obstacle.",
                        why="The recorded walk cannot be safely joined from this tile.", details=[])
        if join:
            k, t = join[1], join[2]
            pts_now = [[t[0], t[1], pts_now[k][2], pts_now[k][3]]] + pts_now[k + 1:]
            t0 = pts_now[0][3]
    pts_now = repair(here, pts_now, {tuple(p) for p in state.get("teacher_blocked", {}).get(here, [])})
    if pts_now is None:
        return dict(do="No checked walk around the observed blocker is available. Look and ask with the current obstacle.",
                    why="Repeating the blocked direction will not move you.", details=[])
    seq = sorted([(p[3], 0, tuple(p[:2])) for p in pts_now] +
                 [(a["frame"], 1, n) for n, a in enumerate(v["actions"]) if a["frame"] >= t0 and
                  (cut is None or a["frame"] <= cut)])
    seq = [x[2] if x[1] == 0 else v["actions"][x[2]] for x in seq]
    walk = join[0] + walk_from(seq, tuple(pts_now[0][:2])) if join else walk_from(seq, pos)
    nxt_map = next((w["map"] for w in WALKS[vi + 1:] if w["map"] != here), None)
    # The warp press is not logged; check it against pokered instead of repeating the last recorded direction.
    end, step = v["points"][-1], _last_step(v["points"])
    scripted = _scripted_ending(here, nxt_map, end)
    exit_text = None
    door = door_xy(here, nxt_map, end) if cut is None and not scripted else None
    into = door and door_step(door, end)  # the record ended right next to this door: step into it
    if into:   # step 5: Viridian Mart said "walk right onto (30,20)"; the door is (29,19), entered walking up
        walk.append(f"{into} 1")
    elif cut is None and nxt_map and not scripted:
        if _real_inferred_exit(here, nxt_map, end, step):
            if step:
                walk.append(f"{step} 1")
        else:
            exit_ = _record_exit(here, nxt_map, end, step, pos, state["place"].get("last_map"))
            tail = _exit_walk(here, end, exit_, {tuple(p) for p in state.get("teacher_blocked", {}).get(here, [])}) \
                if exit_ else None
            if tail is not None:
                walk += tail
            else:
                # A failed suffix must never erase recorded story actions or replace them with a bad route.
                exit_text = f"No checked walk to {nxt_map} is available after the recorded actions; look and ask again."
    walk = tidy(walk)
    if cut is None and nxt_map and not scripted and not any(isinstance(p, dict) for p in seq) \
            and not _record_walk_leaves(state, walk):
        # There are no remaining story actions to preserve. Build the whole exit
        # from the player's square, including standing on a mat/stairs and disconnected
        # outdoor regions; joining a record is not proof that its final press is legal.
        first = _record_exit(here, nxt_map, end, step, pos, state["place"].get("last_map"))
        blocked = dict(state.get("teacher_blocked", {}))
        blocked[here] = list(blocked.get(here, [])) + \
            [(x, y) for x, y, sprite in _objects(here)[1] if sprite == "SPRITE_BOULDER"]
        route = walk_to(dict(state, teacher_blocked=blocked), lambda m, p: m == first["target"], max_maps=1) if first else None
        if route and route["exit"]:
            walk = walk_words(state, route)
            how = route["exit"]
            src = next(p for (m, p), action in route["steps"] if m == here and action[0] != "move")
            press = EDGE_WORD[how[2]][1] if how[0] == "edge" else how[3] if len(how) == 4 else how[2]
            exit_text = _exit_text(here, nxt_map, src, press, src, state["place"].get("last_map"))
        else:
            walk = []
            exit_text = f"No checked walk to {nxt_map} is available from this square; look and ask again."
    if cut is not None:
        walk.append("here the story moves on (watch the text)")
    progress_here = any(p[2] != v["points"][j][2] for p in v["points"][j + 1:])   # the story moves on this map
    if here in goal_maps(nxt["id"]):
        do = f"Next goal: {nxt['goal']}. It is on this map ({here}): walk to the boss and talk to them."
        if nxt["id"] == "badge1" and state["team"]:   # round 7: t9-5 fought Brock 3 times and never asked if ready
            g, bypass = gym1_plan(state)
            if not g["ok"]:   # round 8: training first, before the gym trainer (t10-5b fought on: lead fainted)
                do = (f"Next goal: {nxt['goal']}. Not ready for Brock yet: {_unready(g)}. Train first: leave the gym "
                      f"and fight wild Pokémon in the grass of Route 2 north of Viridian Forest (closest to the Pewter "
                      f"Pokémon Center); the gym trainer fights you if you walk past him. Come back when ready.")
    elif nxt["id"] == "badge1" and nxt_map in goal_maps("badge1") and state["team"] \
            and not gym1_plan(state)[0]["ok"]:    # round 8: say it before the player walks in
        do = (f"Next goal: {nxt['goal']}. Not ready for Brock yet: {_unready(gym1_plan(state)[0])}. Train first in the "
              f"grass of Route 2 north of Viridian Forest (heal at the Pewter Pokémon Center), then go to {nxt_map}."
              + door_text(here, nxt_map, end))
    elif progress_here:
        do = f"Next goal: {nxt['goal']}. The next step happens here on {here}" + (f"; then go to {nxt_map}." if nxt_map
                                                                                   else ".")
    else:
        do = f"Next goal: {nxt['goal']}." + (f" From {here}, go to {nxt_map}." if nxt_map else "")
        do += door_text(here, nxt_map, end)
    details = []
    train = "Not ready for Brock yet" in do
    if train:   # Sol R8A: the walk must match the DO line: out to the training grass, not up to Brock
        walk = []
        details += training_advice(state, explicit=True)["details"]
    elif here == "PEWTER_GYM" and nxt["id"] == "badge1" and state["team"]:
        g, bypass = gym1_plan(state)
        if bypass:
            walk = []
            do = ("At Brock's talk tile (4,2), face up and press A to talk to Brock; heal first if needed."
                  if bypass["cost"] == 0 else
                  "Brock alone is viable after healing. Skip the optional gym trainer using the checked left-side bypass.")
            details.append("The checked bypass to Brock: " + (", ".join(walk_words(state, bypass)) + "; "
                           if bypass["cost"] else "already ") + "at (4,2), face up and press A.")
            details += g["lines"]
    elif nxt_map and not progress_here and here not in goal_maps(nxt["id"]) and not into:
        details.append(exit_text or _exit_text(here, nxt_map, end, step, pos, state["place"].get("last_map")))
    if walk:
        legs = with_coords(walk, pos)
        details.append("Our route on this map, from where you stand: " + ", ".join(legs)
                       + ". (x grows to the right, y grows down.)")
    if dist:
        details.append("(Your story progress differs a little from our record game here: check the goal.)")
    # round 6: walk into a gym with full HP (t7-2 lost twice to the Pewter Gym trainer)
    if nxt_map and nxt_map in goal_maps(nxt["id"]) and any(t["hp"] < t["max_hp"] for t in state["team"]):
        details.insert(0, "Heal before the gym: " + heal_place(state))
    # round 7: Weedle poison knocked out t9-6 and t9-7 in Viridian Forest; Viridian Mart sells Antidotes, no Potions
    if here == "VIRIDIAN_CITY" and nxt["id"] == "badge1" and "ANTIDOTE" not in _bag(state) and state["money"] >= 100:
        d = door_xy(here, "VIRIDIAN_MART", pos)
        details.append("Before Viridian Forest: buy 1-2 Antidotes (100 each) at the Viridian Mart (blue roof): Weedles "
                       "in the forest can poison you. This Mart sells no Potions." + (f" Its door is at ({d[0]},{d[1]})."
                                                                                      if d else ""))
    # round 6: Potions for Brock (Pewter Mart, plan item 2)
    if here == "PEWTER_CITY" and nxt["id"] == "badge1" and not any(k in HEAL for k in _bag(state)):
        d = door_xy(here, "PEWTER_MART", pos)
        details.append("No Potions in your bag: buy some at the Pewter Mart (blue roof)."
                       + door_text(here, "PEWTER_MART", (d[0], d[1] + 1)))
    return dict(do=do, why=why, details=details)


def _reason_line(state, nxt):
    part = KB["parts"][nxt["part"]]
    lines = part["lessons"].get("You need", []) + part["lessons"].get("Goal", [])
    words = _words(nxt["goal"])
    best = max(lines, key=lambda l: len(words & _words(l)), default=None)
    return _clean(best) if best else "This is the next step of the story; the game blocks the way until it is done."


# ---------- matching free questions to lesson lines ----------

STOP = set("a an the to of in on at for and or is are be it i my me you your do does how what where which who why when "
           "can should would will with from this that there have has get go use".split())


def _words(s):
    return {w.rstrip("s") for w in re.findall(r"[a-zé]+", s.lower()) if w not in STOP and len(w) > 2}


def _clean(line):
    return re.sub(r"\*\*", "", line)


SYNONYMS = {"choose": {"pick"}, "select": {"pick"}, "starter": {"squirtle", "bulbasaur", "charmander"},
            "heal": {"center", "potion"}, "gym": {"badge"}, "cave": {"moon", "tunnel"}}


def related_lines(state, question, n=3):
    q = _words(question)
    q |= {x for w in list(q) for x in SYNONYMS.get(w, ())}
    if not q:
        return []
    scored = []
    old = "parcel" in state["story"]["done"]      # round 8 (t10-5b n243): no parcel lesson after the parcel
    for p in KB["parts"]:
        for sec, lines in p["lessons"].items():
            for l in lines:
                if old and "parcel" in l.lower():
                    continue
                s = len(q & _words(l)) * (2 if p["id"] == state["part"] else 1)
                if s:
                    scored.append((s, p["id"], sec, l))
    scored.sort(key=lambda t: -t[0])
    return [f"(part {pid}, {sec}) {_clean(l)}" for _, pid, sec, l in scored[:n]]


def named_place(question, state):
    """Round 8 (t10-7 n232 "Route to Route 2 again?" got the Mart): the map a question asks the way TO ("to Route 2",
    "where is Pewter", "find the Pewter Gym"), or None. Only after to / reach / towards / is / find, so "I came from
    Route 1" names no goal. Towns also go by their first word (Pewter = PEWTER_CITY)."""
    q_raw = (question or "").lower().replace("é", "e").replace("'", "")
    names = {}
    for const in R.MAPS.values():
        if isinstance(const, str) and not const.startswith("UNUSED"):
            names[const.lower().replace("_", " ")] = const
            if const.endswith(("_CITY", "_TOWN")):
                names.setdefault(const.split("_")[0].lower(), const)
    no = re.compile(r"\b(already|went|been|came|was|were|visited|left|not|dont|never|longer|instead)\b")
    for c in re.split(r"[;,.?!]|\b(?:but|and then|then)\b", q_raw):
        c = " ".join(re.findall(r"[a-z0-9]+", c or ""))
        for name in sorted(names, key=len, reverse=True):
            for m in re.finditer(r"\b(to|reach|towards?|is|find)\s+(the\s+)?" + re.escape(name) + r"\b", c):
                # Sol R8A/B: skip a past or negated mention ("I already went to ...", "not want to go to ..."),
                # judged by the 4 words before it only ("how do I get to X from here" still asks for X)
                if not no.search(" ".join(c[:m.start()].split()[-4:])):
                    return names[name] if names[name] != state["place"]["map"] else None
    return None


def place_advice(state, target):
    """The way to a map the player asked for: how to leave this map and the real walk (walk_to); None if none."""
    if target == "OAKS_LAB" and (state["story"]["next"] or {}).get("id") == "oak":
        a = way_advice(state)
        a["why"] = "Oak must stop you in the grass north of Pallet before the lab visit can give you a starter."
        return a
    r = walk_to(state, lambda m, p: m == target)
    if not r or not r["exit"]:
        return None
    first, out = r["maps"][1], r["exit"]
    then = f", then on to {target}" if first != target else ""
    via = f" (through {', '.join(r['maps'][2:-1])})" if len(r["maps"]) > 3 else ""
    if out[0] == "edge":
        do = f"To get to {target}: walk off the {EDGE_WORD[out[2]][0]} ({out[2]}) edge of this map to {first}{then}{via}."
    else:
        do = f"To get to {target}: go through the door / stairs to {first}{then}{via}."
    details = ["The walk from where you stand: " + ", ".join(walk_words(state, r)) + ". (x grows to the right, "
               "y grows down.)"]
    nxt = state["story"]["next"]
    if nxt:
        details.append(f"Your next goal is: {nxt['goal']}. Ask without naming a place for our route to it.")
    if target == "PEWTER_GYM" and (nxt or {}).get("id") == "badge1" and state["team"]:
        g, bypass = gym1_plan(state)
        if not g["ok"]:
            requested = details[0].replace("The walk from where you stand:", "Requested gym walk (enter only after preparing):")
            details = training_advice(state, explicit=True)["details"] + [requested]
            do = "Not ready for Brock yet: " + _unready(g) + ". Train first."
        elif bypass:
            do = "Brock alone is viable after healing. " + do
            details += ["Optional trainer: skip it; its readiness is separate from Brock."] + g["lines"]
            details.append("The checked bypass: " + ", ".join(walk_words(state, bypass)) + ". On entering the gym, ask again for the left-side route.")
        else:
            details.append("Optional trainer: no checked bypass from here; do not assume you can avoid its fight.")
        if any(t["hp"] < t["max_hp"] or t["status"] != "ok" for t in state["team"]):
            details.insert(0, "Heal before the gym: " + heal_place(state))
    if state["place"]["map"] == "VIRIDIAN_CITY" and (nxt or {}).get("id") == "badge1" and \
            target in ("ROUTE_2", "VIRIDIAN_FOREST", "PEWTER_CITY") and "ANTIDOTE" not in _bag(state) and state["money"] >= 100:
        details.append("Before Viridian Forest: buy 1-2 Antidotes (100 each) at the Viridian Mart; this Mart sells no Potions.")
    return dict(do=do + " There, ask again.", why=f"You asked the way to {target}.", details=details)


PRE_BROCK = [i for i, *_ in R.MILESTONES[:[i for i, *_ in R.MILESTONES].index("badge1") + 1]]
STUCK = 8   # commands without moving before the teacher says "you are stuck"


def intent(question, state):
    q = (question or "").lower()
    way_words = re.search(r"\b(where|way|go|path|direction|exit|route|get to|find|door|enter|entrance|inside|"
                          r"stairs|building|tile)\b", q)
    ready_words = re.search(r"\b(ready|level|train|strong enough|team)\b", q)
    choose_words = re.search(r"\b(which|choose|pick|should i (take|buy|catch|teach|get))\b", q)
    if choose_words and not state["battle"] and not way_words and not ready_words \
            and related_lines(state, question, 1):
        return "lesson"
    if state["battle"] and not re.search(r"\b(where|ready|level|train|buy)\b", q):
        return "battle"
    if (state["story"]["next"] or {}).get("id") == "badge1" and (
            re.search(r"\b(train|training|grind)\b", q) and (way_words or not re.search(r"\b(level|ready|strong enough)\b", q)) or
            re.search(r"\bgrass\b", q) and re.search(r"\b(route[ _]?2|forest|train|training)\b", q)):
        return "train"
    if re.search(r"\b(heal|healing|center|centre|nurse|hurt|fainted)\b", q):
        return "heal"
    if re.search(r"\b(ready|level|train|strong enough|beat|team)\b", q):
        return "ready"
    return "way"


# ---------- the answer ----------

def poison_line(state):
    """Round 7 (t9-6, t9-7: Weedle poison in Viridian Forest): poisoned team members and how to cure them; None if none."""
    sick = [t for t in state["team"] if t["status"] == "poisoned" and t["hp"] > 0]
    if not sick:
        return None
    cure = "use an ANTIDOTE from your bag (START > ITEM)" if "ANTIDOTE" in _bag(state) else heal_place(state)
    return (f"{', '.join(t['species'] for t in sick)} poisoned: it loses 1 HP every 4 steps while you walk and can "
            f"faint. Cure it now: {cure}")


SHOP = {"VIRIDIAN_MART": "Antidotes (100 each; this Mart sells no Potions: a customer saying POTIONs are sold out "
                          "is only talk)",
        "PEWTER_MART": "Potions (300 each)"}


def shop_line(state):
    """Round 8 (t10-2, t10-5: players read a customer's "POTIONs are all sold out" as the shop's answer): inside a
    Mart before Brock, where to stand to talk to the clerk across the counter; None elsewhere."""
    here = state["place"]["map"]
    clerk = next(((x, y) for x, y, s in _objects(here)[1] if s == "SPRITE_CLERK"), None)
    if here not in SHOP or not clerk or not state["team"] or (state["story"]["next"] or {}).get("id") != "badge1":
        return None
    stand = (clerk[0] + 2, clerk[1])               # the clerk faces right, across the counter square next to him
    return (f"To buy {SHOP[here]}: stand at ({stand[0]},{stand[1]}), press left once to face the clerk behind the "
            f"counter, press A and pick BUY; pick the item, set the number with up/down, press A and YES; press B to "
            f"leave the menu. Only the clerk sells; the other people here just talk.")


MUST_SEE = ("The way out", "Before Viridian Forest", "Heal before the gym", "To buy",
            "The way to the training grass", "Training circuit", "Training purpose", "Brock readiness",
            "The way back to Brock", "Optional trainer", "The checked bypass", "Battle plan", "Story check",
            "After closing", "Observed blocker", "The way to the rival trigger")


# Script numbers come from the checked-in source, not a guessed ROM address or a remembered conversation.
LAB_SCRIPTS = re.findall(r"dw_const\s+\w+,\s*(SCRIPT_OAKSLAB_\w+)",
                        (R.REF / "pokered/scripts/OaksLab.asm").read_text(encoding="utf-8"))


def story_memory(m, state):
    """Extra facts for the teacher only; the common player view and milestone scoring do not change."""
    script = m[R.A("wOaksLabCurScript")]
    return dict(rival_done=R.event(m, "EVENT_BATTLED_RIVAL_IN_OAKS_LAB"),
                lab_script=LAB_SCRIPTS[script] if state["place"]["map"] == "OAKS_LAB" and script < len(LAB_SCRIPTS)
                else None)


def story_step(state):
    """Only the first unfinished early step, checked anew from decoded facts on every observation."""
    nxt = state["story"]["next"]
    if not nxt or nxt["id"] not in PRE_BROCK:
        return None
    facts = state.get("teacher_story", {})
    done = set(state["story"]["done"])
    if "oak" not in done:
        return ("oak", "trigger Oak north of Pallet", "Oak's event flag must be set")
    if "starter" not in done or not state["team"]:
        return ("starter", "take a starter in Oak's lab", "a Pokemon must actually be in your party")
    if facts.get("rival_done") is False and "parcel" not in done:
        return ("lab_rival", "finish the rival battle in Oak's lab", "the lab battle event must be set after battle")
    if facts.get("lab_script") in ("SCRIPT_OAKSLAB_RIVAL_STARTS_EXIT", "SCRIPT_OAKSLAB_PLAYER_WATCH_RIVAL_EXIT"):
        return ("rival_exit", "let the rival finish leaving the lab", "the lab script must release walking control")
    if "parcel" not in done:
        if _bag(state).get("OAKS_PARCEL", 0):
            return ("deliver_parcel", "bring the Parcel in your bag back to Oak", "Oak's handover event must be set")
        return ("get_parcel", "collect Oak's Parcel at Viridian Mart", "OAKS_PARCEL must actually appear in your bag")
    if "pokedex" not in done:
        return ("pokedex", "finish receiving the Pokedex from Oak", "the Pokedex event must be set")
    return ("brock", "prepare for Brock, then reach him", "only the Boulder Badge confirms the gym is done")


def lab_advice(state):
    """Do not route an exit request past an unfinished mandatory rival script (t11-2 n44/n53)."""
    step = story_step(state)
    if state["place"]["map"] != "OAKS_LAB" or not step or step[0] not in ("lab_rival", "rival_exit"):
        return None
    facts = state.get("teacher_story", {})
    details = []
    if step[0] == "lab_rival" and facts.get("lab_script") == "SCRIPT_OAKSLAB_RIVAL_CHALLENGES_PLAYER":
        if state["place"]["y"] == 6:
            action = "Press down once, then look: the rival challenge starts on row 6 before you can leave."
        else:
            route = walk_to(state, lambda m, p: m == "OAKS_LAB" and p[1] == 6)
            action = "Walk to row 6 to trigger the rival before leaving; then look."
            if route:
                details.append("The way to the rival trigger: " + ", ".join(walk_words(state, route)) + ".")
    else:
        action = "Let the rival's lab script finish; read waiting dialogue with A once, then look."
    return dict(do=action, why="The rival battle and his exit are mandatory. A starter alone does not confirm they happened.",
                details=details)


def text_advice(state, question, context):
    """Close only verified optional dialogue. Unknown menus/naming/quantity choices get no blind cancel."""
    screen = state.get("teacher_screen", {})
    words = " ".join(screen.get("rows", []))
    here = state["place"]["map"]
    done = set(state["story"]["done"])
    safe_oak = here == "OAKS_LAB" and {"parcel", "pokedex"} <= done and re.search(r"world wait for", words, re.I)
    safe_customer = here == "VIRIDIAN_MART" and re.search(r"POTIONs are.*all sold out", words, re.I)
    if (safe_oak or safe_customer) and not screen.get("cursor", True):
        after = []
        if safe_oak:
            route = place_advice(dict(state, text_box=False), "PALLET_TOWN")
            if route:
                after = ["After closing the text, stop pressing A. " + route["do"]] + route["details"]
        if shop_line(state):
            after.append(shop_line(state))
        return dict(do="Press B once to close this optional dialogue, then look before walking or talking again.",
                    why="Oak's handover is already complete." if safe_oak else
                        "The sold-out Potion line belongs to a customer; it is not the shop menu.", details=after)
    loop = (context or {}).get("text_loop", {})
    if loop.get("repeats", 0) >= 3:
        return dict(do="Stop repeating the same input. Look once and ask with the visible text and highlighted choice.",
                    why="The same text has appeared at least three times without a tile or story change. "
                        "This screen is not a checked optional dialogue, so its next button needs a visible choice.",
                    details=[shop_line(state)] if shop_line(state) else [])
    nxt = state["story"]["next"]
    step = story_step(state)
    after = (["After that, resume the training/healing trip; ask again for the next leg to the grass."]
             if context and context.get("purpose") == "train" else
             [f"After that, next step: {step[1]}; confirm from memory: {step[2]}."] if step and "teacher_story" in state else
             [f"After that, your next goal is: {nxt['goal']}."] if nxt else [])
    if shop_line(state):
        after.append(shop_line(state))
    if screen:
        choice = screen.get("cursor") or re.search(r"\b(NAME|NICKNAME|HOW MANY|QUANTITY|BUY|SELL|YES|NO)\b", words, re.I)
        return dict(do="Look once and ask with the visible choices before selecting or cancelling this menu." if choice else
                       "Press A once to read the waiting dialogue, then look before pressing again.",
                    why="Only the two checked optional conversations can be cancelled without examining a choice.",
                    details=after)
    if state.get('part') in (2, 3):
        return dict(do="Look once and ask with the visible text or choices before selecting or cancelling.",
                    why="A text box or menu is open; walking must wait.", details=[])
    return dict(do="Press A to read on (or B to close a menu): a text box or menu is open. Then ask again.",
                why="The game waits until the text is done; walking and the story only go on after it.", details=after)


def note(a):
    """Round 7 (Sol R7A): the automatic new-place note = DO plus the lines a player must not miss."""
    import r13_advice
    a = r13_advice.scrub_answer(a)
    return " ".join([a["do"]] + [d for d in a["details"] if d.startswith(MUST_SEE) or " poisoned: " in d])


def answer(state, question=None, stuck=0, context=None):
    """stuck = how many commands in a row the player pressed buttons without moving (outside battle).
    R12: the same answer a third time with no progress gets a different, more concrete answer."""
    import r13_advice
    import r16_advice
    import r17_advice
    # R17 (round b2): gym sight guard, stale train purpose, "do not train" words; route requests are planned here
    state, question, plan = r17_advice.before(sys.modules[__name__], state, question, context)
    early = r16_advice.early(sys.modules[__name__], state, question, context)   # R16: power-on intro, starter
    if early:
        early = r17_advice.after(sys.modules[__name__], state, question, context, None, early)
        return r13_advice.scrub_answer(r16_advice.finish(sys.modules[__name__], state, question, early))
    a = _answer_core(state, question, stuck, context)
    import r14_advice
    a = r14_advice.repeat_guard(sys.modules[__name__], state, question, context, a)   # R14: fossil box keeps A
    import r15_advice
    a = r15_advice.finish(sys.modules[__name__], state, question, a)
    a = r17_advice.after(sys.modules[__name__], state, question, context, plan, a)   # R17: B1_LESSONS fixes
    a = r16_advice.finish(sys.modules[__name__], state, question, a)    # R16: button lists fit 6-press commands
    return r13_advice.scrub_answer(a)      # R12 review B2: no meta words reach the player


def _answer_core(state, question=None, stuck=0, context=None):
    import r15_advice
    question = r15_advice.routing_question(state, question)
    if (state.get('battle') or {}).get('kind') == 'lost':
        a = dict(do='You blacked out. Press A once to finish the text, then look at your new town and tile.',
                 why='Your badges and fossil are kept; heal and recheck HP and PP before another fight.', details=[])
        return dict(a, related=[], kind='battle', state=R.summary(state))
    kind = intent(question, state)
    if state.get("battle"):          # R12: in battle every question gets one concrete battle action
        kind = "battle"
    target = named_place(question, state)
    if context is not None:
        M.refresh_context(state, context)
        if not target and not question and not state.get("text_box") and kind == "way":
            target = context.pop("deferred_target", None)
        elif target:
            context.pop("deferred_target", None)
            if state.get("text_box"):
                context["deferred_target"] = target
        blocked = dict(state.get("teacher_blocked", {}))
        bump = context.get("walk_block", {})
        if bump.get("map") == state["place"]["map"] and bump.get("count", 0) >= 2:
            blocked[bump["map"]] = list(blocked.get(bump["map"], [])) + [bump["tile"]]
        for seen in context.get('walk_occupancy', []):
            if seen.get('ttl', 0) > 0:
                blocked[seen['map']] = list(blocked.get(seen['map'], [])) + [seen['tile']]
        state = dict(state, teacher_blocked=blocked)
        if (state["story"]["next"] or {}).get("id") != "badge1":
            context.pop("purpose", None)
        if kind == "train":
            context["purpose"] = "train"
        elif target and target != "PEWTER_GYM" and kind != "heal":
            context.pop("purpose", None)
        if context.get("purpose") == "train" and kind == "way" and not target:
            p = state["place"]
            arrived = (not state["battle"] and not state.get("text_box") and p["map"] == "PEWTER_GYM"
                       and (p["x"], p["y"]) == (4, 2) and not training_needs_heal(state)
                       and gym1_plan(state)[0]["ok"])
            if arrived:
                context.pop("purpose", None)
            else:
                kind = "train"
        if context.get("purpose") != "train":
            context.pop("training_check", None)
    # A reported adjacent blocker remains a wall even if static people must be relaxed.
    block = re.search(r"(?:directly |immediately )?(north|south|east|west)\b", question or "", re.I)
    if block and re.search(r"\b(person|trainer|catcher|npc)\b", question or "", re.I) and \
            re.search(r"\b(blocks?|blocking|stands?)\b", question or "", re.I):
        side = {"north": "up", "south": "down", "east": "right", "west": "left"}[block[1].lower()]
        dx, dy = W.STEP[side]
        p = state["place"]
        blocked = dict(state.get("teacher_blocked", {}))
        blocked[p["map"]] = list(blocked.get(p["map"], [])) + [(p["x"] + dx, p["y"] + dy)]
        if context is not None:
            context["walk_block"] = dict(map=p["map"], at=[p["x"], p["y"]], direction=side,
                                         tile=[p["x"] + dx, p["y"] + dy], count=2, noted=False)
        state = dict(state, teacher_blocked=blocked)
    if state.get("text_box") and (kind != "lesson" or state.get("part") in (2,3)):
        import r13_advice
        a = r13_advice.text_extra(sys.modules[__name__], state, question, text_advice(state, question, context), context)
        import r14_advice
        a = r14_advice.text_extra(sys.modules[__name__], state, question, a, context)   # R14: fossil YES/NO = A
        return dict(a, related=[], kind="text", state=R.summary(state))
    if not state.get("battle"):
        import r14_advice
        early = r15_advice.answer(sys.modules[__name__], state, question, context)
        if early:
            return dict(early, related=[], kind="way", state=R.summary(state))
        early = r14_advice.answer(sys.modules[__name__], state, question, context)   # R14: Mt. Moon, Route 4, Cerulean
        if early:
            return dict(early, related=[], kind="way", state=R.summary(state))
        import r13_advice
        early = r13_advice.answer(sys.modules[__name__], state, question, context)
        if early:
            return dict(early, related=[], kind="way", state=R.summary(state))
        import r11_advice
        late = r11_advice.answer(sys.modules[__name__], state, question)
        if late:
            late = r13_advice.after_way(sys.modules[__name__], state, question, late)
            return dict(late, related=[], kind="way", state=R.summary(state))
    if kind == "lesson":
        lines = related_lines(state, question, 3)
        a = dict(do=lines[0].split(") ", 1)[1], why="From our lessons (the tag says how we know it).",
                 details=[l for l in lines[1:]])
    elif kind == "heal":
        hurt = [t for t in state["team"] if t["hp"] < t["max_hp"] or t["status"] != "ok"]
        a = dict(do=heal_place(state), why="Healing at a Pokémon Center (or your Mom) is free and fills HP and PP "
                 "and cures status." + ("" if hurt else " Your team is already at full health."), details=[])
    elif kind == "battle":
        import r13_advice
        import r14_advice
        plan = r13_advice.battle_plan(sys.modules[__name__], state, battle_advice(state))
        plan = r14_advice.battle_plan(sys.modules[__name__], state, plan)                 # R14: no resisted pick
        a = r13_advice.battle_answer(sys.modules[__name__], state, plan, battle_step(state, plan))
        a = r14_advice.battle_answer(sys.modules[__name__], state, a)                     # R14: Misty foe lines
    elif kind == "train":
        a = training_advice(state, explicit=intent(question, state) == "train")
    elif kind == "ready":
        a = ready_advice(state)
    elif kind == "way" and (lab := lab_advice(state)):
        a = lab
    elif kind == "way" and target and (place := place_advice(state, target)):
        a = place
    else:
        a = way_advice(state)
        boss = boss_keys(state, (state["story"]["next"] or {}).get("id"))
        if boss and state["team"] and (state["story"]["next"] or {}).get("id") == "badge1":
            a["details"].append("Next boss: " + gym1_text(gym1_plan(state)[0]))
        elif boss and state["team"]:
            ok, lines, target = team_check(state, boss)
            a["details"].append("Next boss: " + ("your team should win." if ok else
                                                 "not ready yet" + (f": train {target[0]} to about level {target[1]}"
                                                                    if target else "") + "."))
    if shop_line(state) and not state["battle"]:                          # round 8: who sells in a Mart
        a["details"].insert(0, shop_line(state))
    if poison_line(state) and not state["battle"] and kind != "heal":   # round 7: poison drains HP while walking
        a["details"].insert(0, poison_line(state))
    low = [t for t in state["team"] if t["hp"] * 3 < t["max_hp"]]
    if low and kind not in ("battle", "heal"):
        a["details"].insert(0, "Heal first: " + ", ".join(f"{t['species']} has {t['hp']}/{t['max_hp']} HP"
                                                          for t in low)
                            + ". " + heal_place(state))
    if stuck >= STUCK and not state["battle"]:
        a["details"].insert(0, f"You have not moved in your last {stuck} commands: pressing the same buttons again "
                               "will not help. Do the DO NOW step, one direction at a time, and look where you stand "
                               "after each command.")
    # Keep the fact check in automatic notes too, without adding a whole future checklist or changing scoring.
    step = story_step(state)
    if step and not state["battle"] and "teacher_story" in state:
        a["details"].append(f"Story check: next step is {step[1]}; confirm it from memory: {step[2]}. "
                            f"Current place {state['place']['map']} ({state['place']['x']},{state['place']['y']}) is read from memory.")
    part = KB["parts"][state["part"]]
    watch = part["lessons"].get("Watch out", [])
    here_words = _words(state["place"]["map"].replace("_", " "))
    fit = max(watch, key=lambda l: len(here_words & _words(l)), default=None)
    if fit and here_words & _words(fit):
        a["watch_out"] = _clean(fit)
    a["related"] = related_lines(state, question) if question and kind != "lesson" else []
    a["kind"] = kind
    a["state"] = R.summary(state)
    if context is not None and not state["battle"] and "Train first" in a["do"]:
        context["purpose"] = "train"
    return a


def ready_advice(state):
    nxt = state["story"]["next"]
    if (nxt or {}).get("id") == "badge2":
        import r11_advice
        return r11_advice.misty_advice(sys.modules[__name__], state)
    boss = boss_keys(state, (nxt or {}).get("id"))
    if not boss:
        return dict(do=f"No boss before your next goal ({nxt['goal'] if nxt else 'none'}).",
                    why="Fight the trainers on the way for EXP and keep Potions.", details=[])
    if (nxt or {}).get("id") == "badge1" and state["team"]:     # round 6: the gym trainer and Brock, turn by turn
        g, bypass = gym1_plan(state)
        do = ("Your team is ready. Heal first and bring Potions. " + heal_place(state)) if g["ok"] else \
            "Not ready yet: " + gym1_text(g)[len("not ready yet: "):]
        if bypass and g["ok"]:
            do += " Skip the optional trainer; ask for the checked left-side bypass in PEWTER_GYM."
        return dict(do=do, why="Turn by turn with the game's damage formula: your team in order, HP carried over, PP "
                               "counted; healed before each separate fight. A Brock-only verdict requires a checked trainer bypass.",
                    details=g["lines"] + ["Estimate: average damage, the enemy always attacks, no critical hits, "
                                          "no stat changes; Onix's Bide counted once (it may use it again). Train a "
                                          "bit above it to be safe."])
    ok, lines, target = team_check(state, boss)
    if ok:
        do, why = "Your team is ready. Heal first and bring Potions. " + heal_place(state), \
            "By the game's damage formula your best Pokémon wins each fight one on one."
    else:
        do = "Not ready yet: " + (f"train {target[0]} to about level {target[1]}" if target else "train more")
        do += ", or bring many Potions."
        why = "By the game's damage formula at least one enemy Pokémon beats your best answer to it."
    return dict(do=do, why=why, details=lines + ["Estimate: no critical hits, no stat changes, average damage."])


def text(a):
    import r13_advice
    a = r13_advice.scrub_answer(a)
    out = [f"DO NOW: {a['do']}", f"WHY: {a['why']}"]
    out += [f"- {d}" for d in a["details"]]
    if a.get("watch_out"):
        out.append(f"WATCH OUT: {a['watch_out']}")
    if a.get("related"):
        out.append("FROM THE LESSONS:")
        out += [f"- {r}" for r in a["related"]]
    return "\n".join(out)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("question", nargs="?")
    ap.add_argument("--rom", default=str(R.settings.ROM))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    f = Path(a.file)
    if f.suffix == ".sav":
        s = R.state_from_sav(f)
    elif f.suffix == ".state":
        import io
        from pyboy import PyBoy
        gb = PyBoy(a.rom, window="null", sound_emulated=False, ram_file=io.BytesIO(bytes(0x8000)))   # never write red.gb.ram
        try:
            with open(f, "rb") as fh:
                gb.load_state(fh)
            s = R.state_from_pyboy(gb)
        finally:
            gb.stop(save=False)
    else:
        s = R.state_from_wram(f.read_bytes())
    ans = answer(s, a.question)
    print(json.dumps(ans, indent=1, ensure_ascii=False) if a.json else ans["state"] + "\n\n" + text(ans))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
