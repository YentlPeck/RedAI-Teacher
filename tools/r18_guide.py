"""R18 (28 Oct 2026): the teacher as an always-on GUIDE, power-on to Brock (RestedXP-style route guide).

Every turn of a guided run (play.py `start --guide`, teacher arm only) the player's game view starts with one GUIDE
block, built fresh from the RAM state of that moment:

    GUIDE STEP 9/30: Walk north up Route 1 to Viridian City. GO: up*6 | up*6 | left*2 up*3 (21 presses to
    VIRIDIAN_CITY). THEN: Enter the Viridian Mart ...

- The step list is kb/guide_route.json (objective, waypoint, done-check from RAM). The current step = the first step
  of the current story phase that is not done and not skipped, so it auto-advances and goes back by itself when the
  player walks back (re-route from the current tile every turn).
- GO = advise.walk_to from the current tile (doors, edges, ledges, people, observed blockers), as button commands of
  at most 6 presses. At the waypoint: PRESS = the step's action (e.g. "up a a*").
- Battle: the enemy, the menu that shows now (play.py's live screen decoder) and the exact keys from the cursor
  (fight with the planned move, or RUN from wild fights once the team passes the Brock-only check). Text: a*.
  Choice screens (names, starter, nickname, nurse, Mart, start menu) get keys from the visible cursor.
- Off-route recovery: walking but not getting closer for STALL commands -> what blocks (wall, person, ledge,
  trainer) and a fresh walk with that tile blocked.
No language model; same state + context -> same text. The guide text is the same for every model.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROUTE = json.loads((HERE.parent / "kb" / "guide_route.json").read_text(encoding="utf-8"))
STEPS = ROUTE["steps"]
IDS = [s["id"] for s in STEPS]
REGIONS = [name for name, _ in ROUTE["regions"]]
SPLIT_Y = ROUTE["route2_split_y"]
MAX_CHARS = 400
MAX_PRESSES = 6
STALL = 4                 # walk commands without getting closer before the guide explains the blocker
PHASES = ("intro", "house", "lab", "parcel", "deliver", "pokedex", "brock", "done")
VIRIDIAN_HEAL, GYM_HEAL, ROAD_HEAL = 2 / 3, 3 / 4, 1 / 2      # same lines as r17_advice
MENU_POS = {"FIGHT": (9, 14), "PKMN": (15, 14), "ITEM": (9, 16), "RUN": (15, 16)}
MART_STOCK = {"VIRIDIAN_MART": ["POKE_BALL", "ANTIDOTE", "PARLYZ_HEAL", "BURN_HEAL"]}   # data/items/marts.asm


def _A():
    import advise
    return advise


# ---------------------------------------------------------------- facts from RAM (or from a logged row)

def region(map_name, y=None):
    """Index of the route region (kb regions), None off the route. ROUTE_2 is two parts (forest in between)."""
    if map_name == "ROUTE_2":
        key = "ROUTE_2@south" if (y or 0) >= SPLIT_Y else "ROUTE_2@north"
    else:
        key = map_name
    return next((i for i, (_, maps) in enumerate(ROUTE["regions"]) if key in maps), None)


def facts(s, bench=None):
    """Plain facts the checks read. Unknown facts are None (a logged row has no bag or team details)."""
    p = s["place"]
    team = s.get("team")
    bag = s.get("bag")
    return dict(
        intro=bool(s.get("intro")),
        started=bool(s.get("intro")) and p.get("map_id", 0) != 0,     # NEW GAME sets Red's room (r16_advice)
        map=p["map"], x=p["x"], y=p["y"], region=region(p["map"], p["y"]),
        story=set(s["story"]["done"]),
        team=None if team is None else bool(team),
        bag=None if bag is None else {str(b["item"]): b["count"] for b in bag},
        bench=None if bench is None else set(bench),
        badge="Boulder" in (s.get("badges") or []),
        rival_done=(s.get("teacher_story") or {}).get("rival_done"),
        money=s.get("money"),
    )


def phase(f):
    """The story part, from RAM flags (sticky): walking back never changes it."""
    if f["intro"]:
        return "intro"
    if f["badge"]:
        return "done"
    st = f["story"]
    if "pokedex" in st:
        return "brock"
    if "parcel" in st:
        return "pokedex"
    if "oak" not in st:
        return "house"
    if not (f["team"] or "starter" in st):
        return "lab"
    if has_parcel(f):
        return "deliver"
    if f["map"] == "OAKS_LAB" and f["rival_done"] is not True:
        return "lab"          # the rival fight comes before leaving (unknown in battle and in logged rows)
    return "parcel"


def has_parcel(f):
    if f["bag"] is not None and f["bag"].get("OAKS_PARCEL"):
        return True
    return bool(f["bench"] and "got_parcel" in f["bench"])


# ---------------------------------------------------------------- checks

def _atom(a, f, s, A):
    neg = a.startswith("!")
    a = a.lstrip("!")
    v = _value(a, f, s, A)
    return v if v is None or not neg else not v


def _value(a, f, s, A):
    if a in ("intro", "started", "team", "badge", "rival_done"):
        return f[a]
    if a == "parcel":
        return "parcel" in f["story"] or has_parcel(f)
    kind, _, arg = a.partition(":")
    if kind == "story":
        return arg in f["story"]
    if kind == "has":
        return None if f["bag"] is None else bool(f["bag"].get(arg))
    if kind == "bench":
        return None if f["bench"] is None else arg in f["bench"]
    if kind == "map":
        return f["map"] == arg
    if kind == "at":
        m, xy = arg.split(":")
        x, y = map(int, xy.split(","))
        return f["map"] == m and (f["x"], f["y"]) == (x, y)
    if a.startswith("region>=") or a.startswith("region<="):
        r = REGIONS.index(a[8:])
        if f["region"] is None:
            return False
        return f["region"] >= r if a[6] == ">" else f["region"] <= r
    if a.startswith("money<"):
        return None if f["money"] is None else f["money"] < int(a[6:])
    if kind == "heal_ok":
        if not s.get("team") or A is None:
            return None
        import r17_advice as X
        if arg == "pewter" and brock_ready(s, A):
            return pewter_reason(s, A) is None       # R19: the worst-case Brock line, not "under 3/4"
        share = VIRIDIAN_HEAL if arg == "viridian" else ROAD_HEAL
        return X.heal_need(A, s, share) is None
    if a == "brock_ready":
        return brock_ready(s, A) if s.get("team") and A is not None else None
    raise ValueError(f"unknown guide check {a!r}")


def check(expr_list, f, s, A):
    """All of the list; 'a|b' = any. Three-valued: None when a needed fact is unknown."""
    out = True
    for expr in expr_list or []:
        vals = [_atom(a, f, s, A) for a in expr.split("|")]
        v = True if True in vals else (None if None in vals else False)
        if v is False:
            return False
        if v is None:
            out = None
    return out


def brock_ready(s, A):
    """R19: the old average check AND the worst case at full HP/PP (tools/r19_ready.py)."""
    import r19_ready as Y
    return Y.ready(A, s)


def pewter_reason(s, A):
    """R19: why the Pewter heal is due before Brock (None = no heal needed)."""
    import r19_ready as Y
    return Y.heal_reason(A, s)


def step_note(st, s, A):
    """R19: one short reason on the heal and train steps (the numbers behind the detour)."""
    if not s.get("team") or A is None or st["id"] not in ("pewter_heal", "train"):
        return ""
    import r19_ready as Y
    w = Y.worst_case(A, s, full=st["id"] == "train")
    if not w or w["need"] >= 10 ** 6:
        return ""
    lead = w["lead"]
    if st["id"] == "train":
        return f" (max HP {lead['max_hp']}; Brock's worst case needs {w['need']})"
    why = pewter_reason(s, A)
    if why and "Brock needs" not in why:
        return f" ({why})"
    return f" (HP {lead['hp']}/{lead['max_hp']}; Brock's worst case needs {w['need']})"


def applicable(step, f, s, A):
    """Not done and not skipped. An unknown skip fact counts as skip (a logged row cannot say if a heal is due)."""
    if check(step["done"], f, s, A):
        return False
    if "skip" in step and check(step["skip"], f, s, A) is not False:
        return False
    return True


def current(f, s, A):
    """(index, step) of the current step, or (None, None) when the game is done."""
    ph = phase(f)
    if ph == "done":
        return None, None
    idx = [i for i, st in enumerate(STEPS) if st["phase"] == ph]
    for i in idx:
        if applicable(STEPS[i], f, s, A):
            return i, STEPS[i]
    return idx[-1], STEPS[idx[-1]]


def following(i, f, s, A):
    """The next step after i that will apply (later phases: their first step)."""
    for st in STEPS[i + 1:]:
        if st["phase"] == STEPS[i]["phase"]:
            if applicable(st, f, s, A):
                return st
        elif "skip" not in st:
            return st
    return None


# ---------------------------------------------------------------- buttons

def runs(presses):
    """['up','up','left'] -> ['up*2', 'left'] chunks of <= 6 presses, one string per command."""
    cmds, cur, n = [], [], 0
    for b in presses:
        if n == MAX_PRESSES:
            cmds.append(cur)
            cur, n = [], 0
        if cur and cur[-1][0] == b:
            cur[-1][1] += 1
        else:
            cur.append([b, 1])
        n += 1
    if cur:
        cmds.append(cur)
    return [" ".join(b if k == 1 else f"{b}*{k}" for b, k in c) for c in cmds]


def slots(keys):
    return sum(int(t.split("*")[1]) if "*" in t and t != "a*" else 1 for t in keys.split())


def route_presses(r):
    """walk_to result -> the presses on this map, with the press that leaves it (door / mat / edge)."""
    presses, out = list(r["presses"]), r["exit"]
    if out and out[0] == "warp":
        if len(out) == 4:
            presses.append(out[3])
        elif len(out) == 3 and out[2]:
            presses.append(out[2])
    return presses


def goal_of(target):
    m = target.get("map")
    if "xy" in target:
        xy = tuple(target["xy"])
        return lambda mm, pp: mm == m and pp == xy
    if "row" in target:
        row = target["row"]
        return lambda mm, pp: mm == m and pp[1] == row
    return lambda mm, pp: mm == m


def at_target(target, f):
    if target.get("special"):
        return False
    if f["map"] != target.get("map"):
        return False
    if "xy" in target:
        return (f["x"], f["y"]) == tuple(target["xy"])
    if "row" in target:
        return f["y"] == target["row"]
    return True


def blocked_state(s, context):
    """Observed blockers from the run context (advise._answer_core does the same) and the gym sight row."""
    import r17_advice as X
    blocked = {k: list(v) for k, v in (s.get("teacher_blocked") or {}).items()}
    ctx = context or {}
    bump = ctx.get("walk_block", {})
    if bump.get("map") == s["place"]["map"] and bump.get("count", 0) >= 2:
        blocked.setdefault(bump["map"], []).append(tuple(bump["tile"]))
    for seen in ctx.get("walk_occupancy", []):
        if seen.get("ttl", 0) > 0:
            blocked.setdefault(seen["map"], []).append(tuple(seen["tile"]))
    for extra in (ctx.get("guide") or {}).get("avoid", []):
        if extra[0] == s["place"]["map"]:
            blocked.setdefault(extra[0], []).append(tuple(extra[1]))
    return X.gym_guard(dict(s, teacher_blocked=blocked))


def grass_circuit(s, A):
    """At a training grass tile: 'd back d back d back' between two grass tiles (wild fights come on their own)."""
    import walkable as W
    p = s["place"]
    pos, tiles = (p["x"], p["y"]), A.training_tiles()
    if p["map"] != "ROUTE_2" or pos not in tiles:
        return None
    g = A._grid("ROUTE_2")
    for d, q in W.moves(g, pos):
        if q in tiles:
            back = next((d2 for d2, p2 in W.moves(g, q) if p2 == pos), None)
            if back:
                return " ".join([d, back] * 3)
    return None


def walk(step, s, A, context):
    """-> (presses, cost, where, leaves this map) for the step's waypoint from the current tile, or None (no checked walk)."""
    t = step.get("target") or {}
    s2 = blocked_state(s, context)
    if t.get("special") == "brock":
        r = A.brock_route(s2)
        where = "(4,2) below Brock"
    elif t.get("special") == "train":
        tiles = A.training_tiles()
        p = s["place"]
        if p["map"] == "ROUTE_2" and (p["x"], p["y"]) in tiles:
            return [], 0, "the grass", False
        r = A.walk_to(s2, lambda m, q: m == "ROUTE_2" and q in tiles)
        where = "the ROUTE_2 grass"
    else:
        if at_target(t, facts(s)):
            return [], 0, t.get("map"), False
        r = A.walk_to(s2, goal_of(t))
        where = (f"({t['xy'][0]},{t['xy'][1]}) in {t['map']}" if "xy" in t else
                 f"row {t['row']} of {t['map']}" if "row" in t else t["map"])
    if r is None:
        return None
    leaves = bool(r["exit"])
    if leaves and r["maps"][1] != r["maps"][-1]:
        where += f" (next map: {r['maps'][1]})"
    return route_presses(r), r["cost"], where, leaves


# ---------------------------------------------------------------- screens (text and menus)

def raw_rows(m):
    """The 20x18 tile map as text with '>' for the filled cursor (0xED); map graphics are spaces."""
    import read_state as R
    tiles = list(m[0xC3A0:0xC3A0 + 360])
    return ["".join(">" if t == 0xED else (R.CHARS.get(t, " ") if t >= 0x7F else " ") for t in tiles[y * 20:(y + 1) * 20])
            for y in range(18)]


def _norm(t):
    return re.sub(r"[^A-Z0-9]", "", t.upper().replace("É", "E"))


def cursor_at(rows):
    found = [(x, y) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch == ">"]
    return found[0] if len(found) == 1 else None


def menu_entries(rows, x, y):
    """Rows of the menu the cursor is in: entries start one column right of the cursor, one or two rows apart,
    without crossing a box border (so the text box below a menu is not counted)."""
    def entry(r):
        return 0 <= r < len(rows) and len(rows[r]) > x + 1 and bool(_norm(rows[r][x + 1]))

    def blank(r):
        return 0 <= r < len(rows) and (len(rows[r]) <= x + 1 or rows[r][x + 1] == " ")
    out = [y]
    for step in (1, -1):
        r = y
        while True:
            if entry(r + step):
                r += step
            elif blank(r + step) and entry(r + 2 * step):
                r += 2 * step
            else:
                break
            out.append(r)
    return sorted(out)


def cursor_keys(rows, word):
    """Keys from the visible cursor to the menu line that starts with `word`, then 'a'. Menus list one entry per
    line in the cursor's column (often every second row): one up/down press per entry, not per row.
    None when the cursor or the word is not on the screen."""
    cur = cursor_at(rows)
    if not cur:
        return None
    x, y = cur
    w = _norm(word)
    entries = menu_entries(rows, x, y)
    for ty in entries:
        if _norm(rows[ty][x + 1:]).startswith(w):
            d = entries.index(ty) - entries.index(y)
            moves = ["down"] * d if d > 0 else ["up"] * (-d)
            return " ".join(runs(moves) + ["a"]) if moves else "a"
    return None


def menu_screen(s, f, rows, step, A):
    """(why, keys) for a choice or menu screen; None if no cursor is visible."""
    cur = cursor_at(rows)
    if not cur:
        return None
    text = " ".join(rows).upper()
    flat = _norm(text)
    if "NICKNAME" in text:
        return "nickname question", "b"
    if f["map"] == "OAKS_LAB" and not s.get("team") and "YES" in flat:
        # the offer scrolls ("So! You want the" / "water POKéMON," / "SQUIRTLE?"): the name decides (smoke n66)
        if "SQUIRTLE" in flat:
            return "SQUIRTLE offered: YES", "a a*"
        if "CHARMANDER" in flat or "BULBASAUR" in flat:
            return "not SQUIRTLE: answer NO, then take the middle ball", "b"
    if "HEAL" in flat and "CANCEL" in flat:
        k = cursor_keys(rows, "HEAL")
        return "the nurse heals for free", (k + " a*") if k else "a a*"
    if "BUY" in flat and "SELL" in flat and "QUIT" in flat:
        want = step and step["id"] == "antidote"
        k = cursor_keys(rows, "BUY" if want else "QUIT")
        return ("buy 1 Antidote" if want else "nothing to buy here"), k or ("a" if want else "b")
    if f["map"].endswith("_MART") and "OK" in flat and "YES" in flat:
        # the price question shows over the list; the unfilled arrow (▷) marks the item being bought (smoke 4)
        picked = next((r for r in rows if "▷" in r and "ANTIDOTE" in _norm(r.split("▷", 1)[1])), None)
        if step and step["id"] == "antidote" and picked:
            return "confirm 1 Antidote", cursor_keys(rows, "YES") or "a"
        return "not the Antidote: answer NO", "b"
    stock = MART_STOCK.get(f["map"])
    if stock and "ANTIDOTE" in flat and "POKEBALL" in flat:
        if step and step["id"] == "antidote":
            return "pick ANTIDOTE", cursor_keys(rows, "ANTIDOTE") or "down a"
        return "close the shop list", "b"
    if "EXIT" in flat and "ITEM" in flat and ("POKEMON" in flat or "POKEDEX" in flat):
        if cure_needed(s, f):
            return "cure the poison: open ITEM", cursor_keys(rows, "ITEM") or "a"
        return "the start menu is open; close it", "b"
    if cure_needed(s, f) and "ANTIDOTE" in flat:
        return "pick ANTIDOTE", cursor_keys(rows, "ANTIDOTE") or "a"
    if cure_needed(s, f) and "USE" in flat and "TOSS" in flat:
        return "USE it", cursor_keys(rows, "USE") or "a"
    if cure_needed(s, f) and "USEITEMONWHICH" in flat:
        sick = next((t for t in s["team"] if t["status"] == "poisoned"), None)
        return "give it to the poisoned Pokemon", (cursor_keys(rows, sick["nickname"] or sick["species"]) if sick else None) or "a"
    if "YES" in flat and "NO" in flat:
        return "a YES/NO question: read it", None
    return "a menu is open; B closes it", "b"


def intro_screen(rows, started=False):
    """(why, keys) before the first map loads (r16_advice.intro's facts). After NEW GAME (started) blank pages
    between Oak's lines get a*, never a row of A presses (an A on the name list opens the letter screen)."""
    text = " ".join(rows).upper()
    words = text.split()
    if "A B C D E F G H I" in text:
        return "the letter screen: one letter, then START", "a start"
    if "NEW NAME" in text and any(n in words for n in ("RED", "ASH", "JACK", "BLUE", "GARY", "JOHN")):
        name = "BLUE" if any(n in words for n in ("BLUE", "GARY", "JOHN")) else "RED"
        return f"pick the ready-made name {name}", cursor_keys(rows, name) or "down a"
    if "NEW GAME" in text:
        return "pick NEW GAME", cursor_keys(rows, "NEW GAME") or "a"
    if re.search(r"TEXT SPEED|BATTLE ANIMATION|BATTLE STYLE", text):
        return "leave OPTION", "b"
    if not any(r.strip() for r in rows) and not started:
        return "logo and title: A goes on", "a a a a a a"
    return "Oak is talking: a* reads on until the name list", "a*"


def cure_needed(s, f):
    team = s.get("team") or []
    return any(t["status"] == "poisoned" and t["hp"] > 0 for t in team) and bool((f["bag"] or {}).get("ANTIDOTE"))


# ---------------------------------------------------------------- battle

def fit_keys(keys):
    """Sol R18 B1: every PRESS fits one command (max 6 presses; a* = 1). A longer plan is cut after its last 'a'
    inside the first 6 presses (e.g. FIGHT + move chosen); the next turn rebuilds the rest from the new screen."""
    if not keys or slots(keys) <= MAX_PRESSES:
        return keys
    out, n = [], 0
    for tok in keys.split():
        k = slots(tok)
        if n + k > MAX_PRESSES:
            break
        out.append(tok)
        n += k
    cut = max((i for i, tok in enumerate(out) if tok == "a"), default=None)
    return " ".join(out[:cut + 1] if cut is not None else out)


def cursor_note(ui, me, move):
    """R19 (b3-1 n299-n304): Haiku copied the first turn's 'a down down a a*' every turn, but the move arrow opens
    on the LAST move used, so the same keys picked TAIL_WHIP and TACKLE. Say where the arrow is."""
    names = [mv["move"] for mv in me["moves"]]
    if ui.get("phase") == "commands":
        i = ui.get("move_index", 0) or 0
        where = names[i] if 0 <= i < len(names) else names[0]
        lead = f"The move list opens on {where} (your last move)"
    elif ui.get("phase") == "moves":
        i = ui.get("cursor", 0) or 0
        where = names[i] if 0 <= i < len(names) else names[0]
        lead = f"The arrow is on {where}"
    else:
        return ""
    if where == move:
        return f" {lead}: no up/down needed. New keys every turn: copy this line, not old notes."
    return f" {lead}, not on {move}. New keys every turn: copy this line, not old notes."


def item_keys(ui, s, me, item, target=None):
    """R19: keys to use a healing item on `target` (species advised by battle_advice; default the fighting
    Pokémon): ITEM (commands), the item (bag list, cursor), the Pokémon (party list). One menu per command; the next
    turn continues from the new screen. Sol R19: the party list must be for THIS item (ui item), else B."""
    bag = [str(b["item"]) for b in s.get("bag") or []]
    if item not in bag:
        return None
    ph = ui.get("phase")
    if ph == "commands" and ui.get("cursor"):
        x, y = ui["cursor"]
        return " ".join((["left"] if x != 9 else []) + (["down"] if y != 16 else []) + ["a"])
    if ph == "items" and ui.get("cursor") is not None:
        d = bag.index(item) - ui["cursor"]
        return " ".join(runs(["down"] * d if d > 0 else ["up"] * (-d)) + ["a"])
    if ph == "item_target" and ui.get("cursor") is not None:
        if ui.get("item") != item:
            return "b"                       # another item's target list is open: back out (battle_step does too)
        team = s.get("team") or []
        want = target or me["species"]
        same = [i for i, t in enumerate(team) if t["species"] == want]
        if not same:
            return None
        slot = next((i for i in same if want == me["species"] and team[i]["level"] == me["level"]
                     and team[i]["hp"] == me["hp"]), same[0])
        d = slot - ui["cursor"]
        return " ".join(runs(["down"] * d if d > 0 else ["up"] * (-d)) + ["a", "a*"])
    return None


def move_keys(ui, me, move):
    """FIGHT from the cursor, then the move from the move list's arrow, A, a*; None if not computable."""
    names = [mv["move"] for mv in me["moves"]]
    if move not in names:
        return None
    j = names.index(move)
    if ui.get("phase") == "commands" and ui.get("cursor"):
        x, y = ui["cursor"]
        keys = (["left"] if x != 9 else []) + (["up"] if y != 14 else []) + ["a"]
        i = ui.get("move_index", 0) or 0
        i = i if 0 <= i < len(names) else 0
    elif ui.get("phase") == "moves":
        keys, i = [], ui.get("cursor", 0)
    else:
        return None
    keys += (["down"] * (j - i) if j > i else ["up"] * (i - j)) + ["a", "a*"]
    return " ".join(keys)


def battle_line(s, f, A):
    """(text, keys) for the battle now. Never older than this command: built from the live screen decoder."""
    import r17_advice as X
    b = s.get("battle") or {}
    if b.get("kind") == "lost":
        return "You blacked out: you wake up in the last Pokemon Center.", "a*"
    foe, me = b.get("enemy"), b.get("yours")
    ui = s.get("teacher_ui") or {}
    phase_ = ui.get("phase", "unknown")
    who = (f"{b.get('kind', 'wild')} {foe['species']} L{foe['level']} {foe['hp']}/{foe['max_hp']} HP" if foe
           else f"{b.get('kind', 'wild')} enemy")
    menu = {"commands": "FIGHT/PKMN/ITEM/RUN menu", "moves": "move list", "party": "party list",
            "items": "bag list", "switch": "switch menu", "item_target": "party list (item)"}.get(phase_)
    head = f"BATTLE vs {who}" + (f"; {menu} shows" if menu else "; battle text shows")
    if phase_ == "unknown":
        return head + ". a* reads on until the menu shows.", "a*"
    if (not foe or not me) and phase_ in ("party", "switch", "items", "item_target"):
        # Sol R18 minor: no PRESS here before. B goes back where cancelling is allowed; a forced switch picks a
        # Pokémon that can fight (advise.battle_step).
        if ui.get("forced") or (me and not me.get("hp")):
            step = A.battle_step(s, dict(do="", why="", details=[]))["do"]
            k = re.search(r"Press (down|up|left|right|A|B) once", step)
            return head + ". Choose a Pokémon that can fight.", (k.group(1).lower() if k else None)
        return head + ". B goes back to the battle menu.", "b"
    if not foe or not me:
        # a menu shows but the battle data is not checked: never "wait for the menu" (b2 stale note, smoke 3);
        # fight with the strongest attack that has PP
        if me and phase_ in ("commands", "moves"):
            usable = [mv for mv in me["moves"] if (A.MOVES.get(mv["move"]) or {}).get("power") and mv["pp"]]
            if usable:
                best = max(usable, key=lambda mv: A.MOVES[mv["move"]]["power"])["move"]
                keys = move_keys(ui, me, best)
                if keys:
                    return head + f". Use {best}.", keys
        return head + ". Read the menu; FIGHT is top left, RUN bottom right.", None
    ready = b.get("kind") == "wild" and X.pre_brock(s) and foe["hp"] > 0 and me["hp"] > 0 and brock_ready(s, A)
    if ready and phase_ in ("commands", "moves"):
        keys = X.run_keys(ui)
        if keys:
            return head + ". RUN: you need no more experience for Brock.", keys + " a*"
    adv = A.battle_advice(s)
    mv = re.match(r"Use (\w+)", adv["do"])
    if mv and phase_ in ("commands", "moves") and mv.group(1) in [m["move"] for m in me["moves"]]:
        keys = move_keys(ui, me, mv.group(1))
        if keys:
            return head + f". Use {mv.group(1)}." + cursor_note(ui, me, mv.group(1)), keys
    it = re.match(r"Use (\w+) on (\w+)", adv["do"])
    if it and it.group(1) in A.HEAL:
        keys = item_keys(ui, s, me, it.group(1), it.group(2))
        if keys:
            return head + f". HP is low: use {it.group(1)} (ITEM, {it.group(1)}, then {it.group(2)}).", keys
    if adv["do"].startswith("Run") and phase_ in ("commands", "moves"):
        keys = X.run_keys(ui)
        if keys:
            return head + ". RUN (this fight is not safe).", keys + " a*"
    step = A.battle_step(s, adv)["do"]
    k = re.search(r"Press (down|up|left|right|A|B) once", step)
    keys = k.group(1).lower() if k else None
    return head + ". " + adv["do"].split(".")[0] + ".", keys


# ---------------------------------------------------------------- the guide

def stall(context, step_id, cost, moving_cmd):
    """Track progress toward the waypoint across commands (context['guide']); -> commands without getting closer."""
    if context is None:
        return 0
    g = dict(context.get("guide") or {})
    if g.get("step") != step_id:
        g = dict(step=step_id, best=cost, flat=0, avoid=[])
    elif moving_cmd and cost is not None:
        if g.get("best") is None or cost < g["best"]:
            g["best"], g["flat"] = cost, 0
        else:
            g["flat"] = g.get("flat", 0) + 1
    context["guide"] = g
    return g["flat"]


def blocker(s, context, A):
    """What stops the walk: the tile the player bumped into last (context walk_block), in words."""
    ctx = context or {}
    bump = ctx.get("walk_block") or {}
    m = s["place"]["map"]
    if bump.get("map") != m:
        return None, None
    tile = tuple(bump["tile"])
    g = A._grid(m)
    people = {(x, y) for x, y, *_ in A._objects(m)[1]} if A._objects(m) else set()
    if tile in people or (g and tile in set(g.get("people", []))):
        why = f"a person at {tile} blocks you"
    elif g and g["tile"].get(tile) in {lt for _, _, lt in g.get("ledges", [])}:
        why = f"a ledge at {tile}: you can only jump down it"
    elif g and g["tile"].get(tile) in g["walk"]:
        why = f"something moving stands at {tile}"
    else:
        why = f"{tile} is a wall, tree or counter"
    return why, [m, list(tile)]


def guide(s, context=None, bench=None, rows=None, A=None, moving=False):
    """-> dict(text, step, index, mode). s = play.py's teacher state; bench = PokéBench milestones so far;
    rows = raw_rows(m) of this screen (None from a logged row); moving = this command pressed buttons."""
    A = A or _A()
    f = facts(s, bench)
    i, st = current(f, s, A)
    if context is not None:
        # R19 (b3-1 n299): the step flipped from "brock" to "pewter_heal" in the middle of Brock's fight. A battle
        # keeps the step it started in; the step is checked again once the battle is over.
        lock = context.get("guide_battle")
        if s.get("battle") and st is not None:
            if lock in IDS and STEPS[IDS.index(lock)]["phase"] == st["phase"]:
                i, st = IDS.index(lock), STEPS[IDS.index(lock)]
            else:
                context["guide_battle"] = st["id"]
        elif lock in IDS and s.get("text_box") and STEPS[IDS.index(lock)]["phase"] == (st or {}).get("phase"):
            i, st = IDS.index(lock), STEPS[IDS.index(lock)]      # the text right after it (b3-2 n262: Brock's
        elif not s.get("battle"):                                # speech before the badge) keeps it too
            context.pop("guide_battle", None)
    total = len(STEPS)
    if st is None:
        return dict(text="GUIDE: Boulder Badge won. The game is done.", step="done", index=total, mode="done")
    head = f"GUIDE STEP {i + 1}/{total}: {st['objective']}" + (step_note(st, s, A) if not s.get("battle") else "")
    nxt = following(i, f, s, A)
    then = f" THEN: {nxt['objective']}" if nxt else ""
    mode, body = "walk", ""
    if s.get("battle"):
        mode = "battle"
        line, keys = battle_line(s, f, A)
        keys = fit_keys(keys)
        body = f" {line}" + (f" PRESS: {keys}" if keys else " Read the screen; ask if unsure.")
        then = (" AFTER: Brock gives the Boulder Badge (a* reads on)." if st["id"] == "brock"
                else f" AFTER: {st['objective']}")
        head = f"GUIDE STEP {i + 1}/{total} (battle):"
    elif s.get("intro"):
        mode = "text"
        why, keys = intro_screen(rows or [], f["started"])
        keys = fit_keys(keys)
        body = f" Now: {why}. PRESS: {keys}"
    elif s.get("teacher_scene"):
        mode = "text"
        # smoke 2: a* waited only ~10 frames here (no text on screen): Oak's escort took one command per tile.
        # Six B presses let ~300 frames pass; B reads text on like A and does nothing on the map.
        body = " A scene plays; you cannot walk now. PRESS: b*6 (lets the scene run; B also reads text on)."
    elif s.get("text_box"):
        mode = "text"
        got = menu_screen(s, f, rows, st, A) if rows else None
        if got:
            why, keys = got
            keys = fit_keys(keys)
            body = f" Now: {why}." + (f" PRESS: {keys}" if keys else " Read it; ask if unsure.")
        else:
            body = " Text shows. PRESS: a* (reads to the end; stops at a choice)."
    else:
        body, cost = walk_body(st, s, f, A, context, moving)
        if cure_needed(s, f):
            mode = "cure"
            body = " FIRST cure the poison (ANTIDOTE). PRESS: start" + body.replace(" GO:", " Then GO:", 1)
    text = _fit(head, body, then)
    return dict(text=text, step=st["id"], index=i + 1, mode=mode)


def walk_body(st, s, f, A, context, moving):
    w = walk(st, s, A, context)
    if w is None:
        stall(context, st["id"], None, moving)
        if f["map"] == "PEWTER_GYM" and (f["x"], f["y"]) in [(x, 6) for x in range(3, 9)]:
            return (" You stand in the gym trainer's sight row (row 6): his fight comes first. After it, walk up to "
                    "(4,2), below Brock."), None
        return (f" No checked walk from ({f['x']},{f['y']}) yet: walk toward {st.get('target', {}).get('map', 'it')} "
                "and look again."), None
    presses, cost, where, leaves = w
    flat = stall(context, st["id"], cost, moving)
    extra = ""
    if flat >= STALL:
        why, avoid = blocker(s, context, A)
        if avoid and context is not None:
            g = context["guide"]
            if avoid not in g.setdefault("avoid", []):
                g["avoid"] = (g["avoid"] + [avoid])[-4:]
                g["best"], g["flat"] = None, 0
            w2 = walk(st, s, A, context)
            if w2:
                presses, cost, where, leaves = w2
        extra = (f" NOT GETTING CLOSER for {flat} commands: {why or 'the last walk did not move you'}. New walk:")
    action = st.get("action")
    if (st.get("target") or {}).get("special") == "train":
        action = grass_circuit(s, A)
    if not presses:
        return extra + f" You are at {where}. PRESS: {action or 'look'}", 0
    cmds = runs(presses)
    if action and len(presses) + slots(action) <= MAX_PRESSES and not leaves:
        return extra + f" GO: {cmds[0]} {action} (walk to {where}, then {action})", cost
    shown = " | ".join(cmds[:3]) + (" | ..." if len(cmds) > 3 else "")
    return extra + f" GO: {shown} ({len(presses)} press{'es' if len(presses) > 1 else ''} to {where})", cost


def _fit(head, body, then):
    text = head + body + then
    if len(text) <= MAX_CHARS:
        return text
    text = head + body
    if len(text) <= MAX_CHARS:
        room = MAX_CHARS - len(text)
        return text + (then[:room - 3] + "..." if room > 12 else "")
    return text[:MAX_CHARS - 3] + "..."


# ---------------------------------------------------------------- replay over logged rows (no emulator)

def state_from_row(row, last_map=None):
    """A minimal teacher state from a play.py log row: place, story, money, flags. No team or bag details."""
    return dict(place=dict(map=row["map"], map_id=row.get("map_id", 0), x=row.get("x", 0), y=row.get("y", 0),
                           last_map=last_map),
                story=dict(done=row.get("done", [])), team=None, bag=None,
                badges=["Boulder"] if (row.get("badges_byte") or 0) & 1 else [], money=row.get("money"),
                battle={"kind": "logged"} if row.get("battle") else None, text_box=bool(row.get("text")),
                intro=bool(row.get("intro")))
