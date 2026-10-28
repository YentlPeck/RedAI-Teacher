"""R17 (round b2): teacher fixes from the round b1 lessons, power-on to Brock only.

1. A route request gets the exact walk from the current tile in DO NOW (the text the player sees), never hidden
   behind "Train first" / "Heal first". Pewter gym door (16,17), approach (16,18) (PewterCity.asm); inside the gym
   every walk avoids the unbeaten trainer's sight row 6, x 3-8 (PewterGym.asm: trainer (3,6) facing RIGHT; the
   checked bypass of advise.brock_route). Same for the Viridian Forest gates.
2. No stale detours: heal only when HP is really low (or status / fainted / no attack PP); a "Train first" answer
   becomes the way to Brock once the Brock-only check passes (the optional gym trainer is not required).
3. Poison first: poisoned -> the first DO NOW line is the cure; in Viridian City before the forest leg with no
   Antidote -> the first line is buying one (Viridian Mart sells ANTIDOTE, data/items/marts.asm).
4. Heal on the earlier city visit: Viridian City before the forest leg (HP under 2/3), Pewter before the gym (under 3/4).
5. Menu-aware battle advice: the enemy by name, which menu shows, and a RUN sequence in wild fights when no
   experience is needed (Brock-only check passes).
6. a* (one press slot: A until the text ends or a choice shows) in text answers.
Old wording is kept where earlier tests and players rely on it; R17 adds or reorders, scoped to power-on..Brock.
"""
import json
import re

GYM_DOOR, GYM_MAT, GYM_ENTRY, BROCK_SPOT = (16, 17), (16, 18), (4, 13), (4, 2)
GYM_SIGHT = [(x, 6) for x in range(3, 9)]
GYM_TRAINER = "EVENT_BEAT_PEWTER_GYM_TRAINER_0"
VIRIDIAN_HEAL = 2 / 3          # long forest leg ahead, no Center until Pewter
GYM_HEAL = 3 / 4               # Brock: Geodude L12 + Onix L14 in a row
ROAD_HEAL = 1 / 2              # elsewhere: the old training rule (advise.training_needs_heal)
A_STAR = "a* (one press slot: A until the text ends or a choice shows)"

WAY_Q = re.compile(r"\b(where|way|walk|route|path|directions?|go|get to|reach|door|entrance|enter|exit|leave|gate|"
                   r"bypass|skip|coordinates?|warp|how (?:do i )?(?:get|reach)|what now|what next|next step|"
                   r"what should i do|challenge)\b", re.I)
GYM_Q = re.compile(r"\b(gym|brock)\b", re.I)
LEAVE_Q = re.compile(r"\b(leave|exit|get out|go out|out of (?:the )?gym)\b", re.I)
BYPASS_Q = re.compile(r"\b(bypass|skip|avoid|around|past|sneak)\b", re.I)
HEAL_Q = re.compile(r"\b(heal|healing|center|centre|nurse)\b", re.I)
FOREST_Q = re.compile(r"\bforest\b", re.I)
NORTH_Q = re.compile(r"\b(north|exit|out|leave|pewter|through)\b", re.I)
SOUTH_Q = re.compile(r"\b(south|back|viridian city|entrance)\b", re.I)
TRAIN_Q = re.compile(r"\b(train|training|grind|grinding|level up|exp)\b", re.I)
NO_TRAIN = re.compile(r"\b(?:do not|don'?t|dont|no|not|without|stop|skip)\b(?:\s+\w+){0,3}?\s+"
                      r"(?:train|training|grind|grinding|fight|fighting)\w*", re.I)
_CHECKS = {}


def result(do, why, details=()):
    return dict(do=do, why=why, details=list(details))


def pre_brock(s):
    return bool(s.get("team")) and (s["story"]["next"] or {}).get("id") == "badge1"


def early(A, s):
    """Power-on to Brock (round b2 scope); later parts keep the old answers."""
    return (s["story"]["next"] or {}).get("id") in A.PRE_BROCK


def free(s):
    return not s.get("battle") and not s.get("text_box") and not s.get("intro")


def here(s):
    p = s["place"]
    return p["map"], (p["x"], p["y"])


def defeated(s, event):
    return s.get("teacher_events", {}).get(event, False)


# ---------- facts: Brock-only check, real heal need ----------

def brock_check(A, s):
    """Brock alone (the left bypass skips the optional trainer), at full HP/PP (advise.gym1_check)."""
    key = json.dumps([[t["species"], t["level"], t["max_hp"], [m["move"] for m in t["moves"]], t.get("stats")]
                      for t in s["team"]] + [s.get("badges")], sort_keys=True, default=str)
    if key not in _CHECKS:
        _CHECKS[key] = A.gym1_check(s, keys=("Brock:1",))
    return _CHECKS[key]


def _unready(A, g):
    return A.gym1_text(g).split(". Train by")[0].replace("not ready yet: ", "", 1)


def brock_ready(A, s):
    return pre_brock(s) and brock_check(A, s)["ok"]


def _attacks(A, t):
    return [mv for mv in t["moves"] if (A.MOVES.get(mv["move"]) or {}).get("power") and (mv["pp"] is None or mv["pp"] > 0)]


def heal_need(A, s, share):
    """Why healing is needed now (a short reason), or None: lead HP under `share`, a fainted or sick member,
    or no attack PP. Full or nearly full HP never asks for a heal (B1: "Heal first" at 29/29 HP)."""
    team = s.get("team") or []
    alive = [t for t in team if t["hp"] > 0]
    if not alive:
        return "every Pokémon has fainted"
    out = [f"{t['species']} has fainted" for t in team if t["hp"] == 0]
    out += [f"{t['species']} is {t['status']}" for t in alive if t["status"] != "ok"]
    lead = alive[0]
    if lead["hp"] < lead["max_hp"] * share:
        out.append(f"{lead['species']} has only {lead['hp']}/{lead['max_hp']} HP")
    if not _attacks(A, lead):
        out.append(f"{lead['species']} has no attack PP left")
    elif share == GYM_HEAL and not out:
        short = pp_short(A, s)
        if short:
            out.append(short)
    return "; ".join(out) or None


def pp_short(A, s):
    """Fix round (Sol R17 final B2): the Brock fight with the CURRENT PP (full HP; a heal refills both). If the
    full-PP check wins but this one does not, a needed attack is low (Tackle PP must not hide an empty Bubble)."""
    if not pre_brock(s) or not brock_check(A, s)["ok"]:
        return None
    team = [A._party_mon(dict(t, hp=t["max_hp"]), s["badges"]) for t in s["team"]]
    win, left, _ = A.fight(team, A.TEAMS["Brock:1"]["party"])
    if win and left >= 0.25:              # same margin as advise.gym1_check
        return None
    low = [f"{mv['move']} {mv['pp']} PP" for t in s["team"] for mv in t["moves"]
           if (A.MOVES.get(mv["move"]) or {}).get("power") and mv["pp"] is not None
           and mv["pp"] < (A.MOVES.get(mv["move"]) or {}).get("pp", 0)]
    return "too little PP to beat Brock (" + (", ".join(low[:3]) or "PP low") + "); healing refills PP"


# ---------- inside Pewter Gym: never cross the trainer's sight row ----------

def gym_guard(s):
    """Every walk inside PEWTER_GYM avoids row 6 x 3-8 while the gym trainer is unbeaten (B1: Luna's heal walk
    'down 11' went straight through it). Standing in that row already: no block (the fight comes anyway)."""
    m, p = here(s)
    if m != "PEWTER_GYM" or defeated(s, GYM_TRAINER) or p in GYM_SIGHT:
        return s
    blocked = dict(s.get("teacher_blocked", {}))
    old = [tuple(t) for t in blocked.get("PEWTER_GYM", [])]
    blocked["PEWTER_GYM"] = old + [t for t in GYM_SIGHT if t not in old]
    return dict(s, teacher_blocked=blocked)


def _at(s, map_name, pos, last=None):
    place = dict(s["place"], map=map_name, x=pos[0], y=pos[1])
    if last:
        place["last_map"] = last
    return dict(s, place=place)


def _words(A, s, r):
    return ", ".join(A.walk_words(s, r))


def bypass_words(A, s):
    """The checked left bypass from the current gym tile to (4,2), below Brock; '' at (4,2); None if no walk."""
    r = A.brock_route(s)
    if r is None:
        return None
    return "" if r["cost"] == 0 else _words(A, s, r)


def brock_talk(A, s):
    walk = bypass_words(A, gym_guard(s))
    if walk is None:
        lead = ("You stand in the gym trainer's sight row: his fight comes first. After it, walk up to (4,2), "
                "below Brock.")
    elif walk == "":
        lead = "You stand below Brock at (4,2)."
    else:
        lead = f"Walk the checked left bypass to (4,2), below Brock: {walk}."
    return (f"{lead} Then, at (4,2), face up and press A: press up a a* (up only turns you to Brock at (4,1), "
            "A talks, a* reads his text until the battle menu shows).")


# ---------- route requests ----------

def route_request(A, s, question):
    """('brock',) / ('map', TARGET) when the question asks the way to a pre-Brock place; else None.
    Training questions keep the old training answer (its walk to the grass)."""
    if not question or not pre_brock(s) or not free(s):
        return None
    q = NO_TRAIN.sub(" ", question)
    m, _ = here(s)
    if not WAY_Q.search(q) or TRAIN_Q.search(q):
        return None
    if m == "PEWTER_GYM":
        if LEAVE_Q.search(q) and not HEAL_Q.search(q):
            return ("map", "PEWTER_CITY")
        if BYPASS_Q.search(q) or GYM_Q.search(q):
            return ("brock",)
        return None
    if GYM_Q.search(q):
        return ("map", "PEWTER_GYM")
    gate = re.search(r"\bgate\b", q, re.I)
    if m == "VIRIDIAN_FOREST" and (FOREST_Q.search(q) or gate or NORTH_Q.search(q) or SOUTH_Q.search(q)):
        # Fix round (Sol R17 final B1): an explicit south / back / Viridian City wins over generic exit words
        south = SOUTH_Q.search(q) and not re.search(r"\b(north|pewter)\b", q, re.I)
        return ("map", "VIRIDIAN_FOREST_SOUTH_GATE" if south else "VIRIDIAN_FOREST_NORTH_GATE")
    if FOREST_Q.search(q) and m not in ("VIRIDIAN_FOREST", "VIRIDIAN_FOREST_NORTH_GATE", "PEWTER_CITY"):
        return ("map", "VIRIDIAN_FOREST_SOUTH_GATE" if gate else "VIRIDIAN_FOREST")
    target = A.named_place(q, s)
    if target and not re.search(r"\bgrass\b", q, re.I) and not (HEAL_Q.search(q) and target.endswith("_POKECENTER")):
        return ("map", target)
    return None


def map_walk(A, s, target):
    """The way to `target` with the walk from the current tile in the same text; None if no checked walk."""
    s = gym_guard(s)
    r = A.walk_to(s, lambda mm, pp: mm == target)
    if not r:
        return None
    m, p = here(s)
    walk = f"The walk from ({p[0]},{p[1]}): {_words(A, s, r)}."
    more = " There, ask again for the next map." if len(r["maps"]) > 2 else ""
    if target == "PEWTER_GYM":
        door = ("Go to PEWTER_GYM: its door is at (16,17) in PEWTER_CITY; stand at (16,18) and walk up into it. "
                if m == "PEWTER_CITY" else
                "Go to PEWTER_GYM: its door is at (16,17) in PEWTER_CITY (walk up into it from (16,18)). ")
        text = door + walk
        if r["maps"][-1] == "PEWTER_GYM" and len(r["maps"]) == 2:
            b = bypass_words(A, gym_guard(_at(s, "PEWTER_GYM", GYM_ENTRY, last="PEWTER_CITY")))
            if b:
                text += (f" Inside, from (4,13), the checked left bypass to Brock: {b} (it avoids row 6, where the "
                         "optional trainer at (3,6) looks right). Then press: up a a*.")
        return text + more, []
    if target in ("VIRIDIAN_FOREST_NORTH_GATE", "VIRIDIAN_FOREST_SOUTH_GATE"):
        door = {"VIRIDIAN_FOREST_NORTH_GATE": "The forest's north exit is at (1,0)/(2,0) in VIRIDIAN_FOREST. ",
                "VIRIDIAN_FOREST_SOUTH_GATE": "The south gate of Viridian Forest is on ROUTE_2 at (3,43) (walk up "
                                              "into it from (3,44)). "}[target]
        if m == "VIRIDIAN_FOREST" and target.endswith("SOUTH_GATE"):
            door = "The forest's south exit is at (15-18,47) in VIRIDIAN_FOREST. "
        return door + walk + more, []
    old = A.place_advice(s, target)                    # keeps the old map-level words ("To get to X: walk off ...")
    lead = old["do"].replace(" There, ask again.", "") if old else f"To get to {target}:"
    return f"{lead} {walk}" + (more or (" There, ask again." if old else "")), (old or {}).get("details", [])


def route_answer(A, s, req, context):
    """The requested walk first; readiness and healing follow, never in its place."""
    m, p = here(s)
    details = []
    if req == ("brock",):
        do, target = brock_talk(A, s), "PEWTER_GYM"
    else:
        target = req[1]
        got = map_walk(A, s, target)
        if not got:
            return None
        do, details = got[0], list(got[1])
    if req == ("brock",) or target == "PEWTER_GYM" or (target == "PEWTER_CITY" and m == "PEWTER_GYM"):
        g = brock_check(A, s)
        need = heal_need(A, s, GYM_HEAL)
        if req == ("map", "PEWTER_CITY"):
            if need:
                details.append("Heal before Brock (" + need + "): " + A.heal_place(gym_guard(s)))
        elif not g["ok"]:
            do += (f" Not ready for Brock yet: {_unready(A, g)}. Train first for a safer fight (the way to the "
                   "training grass is below), or go in now and use Potions.")
            details += [d for d in A.training_advice(s, explicit=True)["details"]
                        if d.startswith(("The way to the training grass", "Training circuit"))]
        elif need:
            do = f"First heal ({need}): " + A.heal_place(gym_guard(s)) + " Then the gym: " + do
        else:
            details.append("Brock check: your team should beat Brock alone (estimate at full HP); skip the optional "
                           "trainer. Your HP is fine: no heal needed.")
        details += [l for l in g["lines"] if l.startswith("Against Brock")]
    if context is not None and target in ("PEWTER_GYM", "VIRIDIAN_FOREST_NORTH_GATE", "PEWTER_CITY"):
        context.pop("purpose", None)        # the player chose the way; no stale "Train first"
        context.pop("training_check", None)
    return dict(result(do, "You asked for this way; it is the checked walk from your tile.", details),
                related=[], kind="way")


# ---------- poison, antidote, earlier heal ----------

def cure_line(A, s):
    sick = [t for t in s["team"] if t["status"] == "poisoned" and t["hp"] > 0]
    if not sick or s.get("battle"):
        return None
    names = ", ".join(t["species"] for t in sick)
    bag = [b["item"] for b in s["bag"]]
    if "ANTIDOTE" in bag:
        return (f"FIRST cure the poison ({names} loses 1 HP every 4 steps): press start, move the arrow to ITEM, "
                f"press a; move to ANTIDOTE (item {bag.index('ANTIDOTE') + 1} in the bag list), press a, then a on "
                f"USE; pick {sick[0]['species']} and press a; then press b until the menu closes. Do this before "
                "walking on.")
    return (f"FIRST cure the poison ({names} loses 1 HP every 4 steps and can faint while walking): "
            + A.heal_place(gym_guard(s)) + " Walk straight there; do not train on the way.")


def antidote_line(A, s, walk=True):
    """Before the Viridian Forest leg (Weedle Poison Sting): buy Antidotes at the Viridian Mart.
    walk=False: an earlier FIRST line moves the player, so only the door is named."""
    m, p = here(s)
    if not pre_brock(s) or not free(s) or "pokedex" not in s["story"]["done"] or m not in ("VIRIDIAN_CITY", "VIRIDIAN_MART"):
        return None
    if A._bag(s).get("ANTIDOTE") or s.get("money", 0) < 100:
        return None
    if m == "VIRIDIAN_MART":
        return "Before the forest: buy 1-2 Antidotes (100 each). " + (A.shop_line(s) or "Talk to the clerk and pick BUY.")
    r = A.walk_to(s, lambda mm, pp: mm == "VIRIDIAN_MART") if walk else None
    way = (" The walk to its door (29,19): " + _words(A, s, r) + ".") if r else " Its door is at (29,19)."
    return ("Before the forest leg: buy 1-2 Antidotes (100 each) at the Viridian Mart (blue roof); Weedles in "
            "Viridian Forest poison, and poison drains HP while you walk." + way)


def city_heal_line(A, s):
    """Heal on this city visit, before the long leg (Viridian -> forest) or the gym (Pewter)."""
    m, p = here(s)
    if not pre_brock(s) or not free(s):
        return None
    if m == "VIRIDIAN_CITY" and "pokedex" in s["story"]["done"]:
        need = heal_need(A, s, VIRIDIAN_HEAL)
        if need:
            return f"FIRST heal here, before the long forest leg ({need}): " + A.heal_place(s)
    if m in ("PEWTER_CITY", "PEWTER_GYM") and brock_ready(A, s):
        need = heal_need(A, s, GYM_HEAL)
        if need:
            return f"FIRST heal here, before Brock ({need}): " + A.heal_place(gym_guard(s))
    return None


# ---------- battle ----------

def run_keys(ui):
    """Buttons from the visible cursor to RUN and select it; None when the cursor is not known."""
    if ui.get("phase") == "commands" and ui.get("cursor"):
        x, y = ui["cursor"]
        return " ".join((["right"] if x != 15 else []) + (["down"] if y != 16 else []) + ["a"])
    if ui.get("phase") == "moves":
        return "b right down a"      # B goes back to the menu with the arrow on FIGHT
    return None


def battle_fix(A, s, a):
    """Name the enemy and the menu on screen; wild fights when no experience is needed: RUN.
    Only with a live screen decoder (play.py's teacher_ui) or while the battle data is still loading."""
    b = s.get("battle") or {}
    if not b or b.get("kind") == "lost" or not early(A, s):
        return a
    foe, me = b.get("enemy"), b.get("yours")
    ui = s.get("teacher_ui") or {}
    phase = ui.get("phase", "unknown")
    who = (f"{'wild' if b.get('kind') == 'wild' else 'trainer'} {foe['species']} L{foe['level']}, "
           f"{foe['hp']}/{foe['max_hp']} HP") if foe else None
    menu = {"commands": "the FIGHT / PKMN / ITEM / RUN menu shows",
            "moves": "your move list shows (FIGHT is already open)",
            "party": "your party list shows", "items": "your bag list shows"}.get(phase)
    out = dict(a, details=list(a.get("details", [])))
    out["do"] = out["do"].replace("then press A through the text",
                                  "then press A through the text (a* does it in one press slot)")
    if not me or not foe:
        out["do"] += (f" Enemy: {who}." if who else "") + (f" Faster: press {A_STAR}; it stops when the FIGHT / "
                                                          "PKMN / ITEM / RUN menu shows.")
        return out
    wild_run = (b.get("kind") == "wild" and pre_brock(s) and foe["hp"] > 0 and me["hp"] > 0 and bool(ui)
                and brock_ready(A, s) and not a["do"].startswith(("Throw", "Use POTION", "Choose your next")))
    if wild_run:
        keys = run_keys(ui)
        how = (f"Press: {keys} (one command)" if keys else
               "When FIGHT / PKMN / ITEM / RUN shows, move the arrow to RUN (bottom-right) and press a")
        out["do"] = (f"Run from this {who}: you need no more experience for Brock. {how}; then a* through the "
                     "text. If it says you can't escape, choose RUN again.")
        out["why"] = ("Your team already passes the Brock-only check, so this wild fight gives nothing you need; "
                      "running costs fewer commands than fighting.")
        out["details"].insert(0, "Battle plan if you stay: " + a["do"])
        return out
    if menu:
        out["do"] = out["do"].rstrip() + f" (Enemy: {who}; {menu}.)"
    return out


# ---------- text: a* ----------

TEXT_A = re.compile(r"\b(press A to go on|press A once to read|press A to read on|press A to continue|"
                    r"press A through|press A once per page|read on with A)", re.I)


def text_fix(A, s, a):
    """Additive: the old wording stays; a* is offered when plain text (no choice, no menu) waits for A."""
    do = a.get("do", "")
    screen = s.get("teacher_screen") or {}
    if s.get("battle") or screen.get("cursor") or "a*" in do or not (s.get("intro") or early(A, s)):
        return a
    if "b*6" in do and "Professor Oak is talking" in do:
        return dict(a, do=do + f" Faster: press {A_STAR}; it stops at the NAME list.")
    if TEXT_A.search(do):
        return dict(a, do=do + f" Faster: press {A_STAR}; it never talks to the same person again.")
    return a


# ---------- the layer ----------

def before(A, s, question, context):
    """-> (state, question, plan): gym walks avoid the trainer's row; "do not train" words are not a training
    request; a route request is planned before the old intent can turn it into "Train first" / "heal"."""
    s = gym_guard(s)
    plan = route_request(A, s, question)
    if question and pre_brock(s):
        question = NO_TRAIN.sub(" ", question)
    return s, question, plan


def explicit_train(question):
    return bool(question and TRAIN_Q.search(NO_TRAIN.sub(" ", question)))


def bypass_known(A, s):
    """Brock-only verdicts need the bypass: always from outside the gym, inside only off the trainer's row."""
    return here(s)[0] != "PEWTER_GYM" or A.brock_route(gym_guard(s)) is not None


def ready_answer(A, s, context):
    m, _ = here(s)
    got = route_answer(A, s, ("brock",) if m == "PEWTER_GYM" else ("map", "PEWTER_GYM"), context)
    if got:
        got["do"] = "Your team is ready for Brock alone. Skip the optional trainer (checked left bypass). " + got["do"]
    return got


def after(A, s, question, context, plan, a):
    """Applied to the old answer (after r15, before r16's 6-press fitting)."""
    kind = a.get("kind")
    if s.get("battle"):
        return battle_fix(A, s, a)
    if s.get("text_box") or s.get("intro"):
        return text_fix(A, s, a)
    if not pre_brock(s):
        return a
    out = None
    ready = brock_ready(A, s) and bypass_known(A, s)
    if plan:
        out = route_answer(A, s, plan, context)
    elif ready and (kind == "ready" or "Train first" in a["do"] and not explicit_train(question)):
        out = ready_answer(A, s, context)        # B1 Luna n589/n594: no "Heal first" at full HP, no stale training
        if out and kind == "ready":
            out["details"] = list(out["details"]) + [d for d in a["details"] if d.startswith("Against the gym trainer")]
    elif kind == "ready" and not ready:
        g = brock_check(A, s)
        t = A.training_advice(s, explicit=True)
        a = dict(a, do="Not ready yet for Brock (Brock alone; the optional gym trainer is skipped): " + _unready(A, g)
                 + ". Train in the ROUTE_2 grass north of Viridian Forest (or fight the forest's bug catchers); heal "
                 "when HP is under half.",
                 details=list(a["details"]) + [d for d in t["details"] if d.startswith(
                     ("The way to the training grass", "Training circuit"))])
    elif a["do"].startswith("Ready for Brock after healing") and not heal_need(A, s, GYM_HEAL):
        back = next((d for d in a["details"] if d.startswith("The way back to Brock")), "")
        a = dict(a, do="Ready for Brock: your HP is fine, no heal needed. Return to PEWTER_GYM; skip the optional "
                       "trainer using the checked bypass. " + back,
                 details=[d for d in a["details"] if not d.startswith("Heal before the gym")])
    if any(str(d).startswith("Next boss: ") for d in a.get("details", [])):     # Brock alone, not the optional trainer
        g = brock_check(A, s)
        boss = "Next boss: " + ("your team should beat Brock alone (skip the optional gym trainer)." if g["ok"] else
                                "Brock alone: not ready yet: " + _unready(A, g) + ".")
        a = dict(a, details=[boss if str(d).startswith("Next boss: ") else d for d in a["details"]])
    if out:
        if context is not None:
            context.pop("purpose", None)
            context.pop("training_check", None)
        keep = [d for d in a.get("details", []) if d.startswith(("To buy", "Story check", "Before Viridian Forest"))
                or " poisoned: " in d]
        a = dict(a, do=out["do"], why=out["why"], details=out["details"] + keep, kind="way")
    # FIRST lines (B1 Luna: poison at n357, blackout n387): cure, then heal on this city visit, then the Antidote.
    # Only the first line that moves the player carries a walk from the current tile.
    has_antidote = bool(A._bag(s).get("ANTIDOTE"))
    done_heal = (kind in ("heal", "lesson") or a["do"].startswith(("To heal", "Pause training and heal"))
                 or "First heal (" in a["do"])
    cure = cure_line(A, s) if has_antidote or not done_heal else None
    heal = None if done_heal or (cure and not has_antidote) else city_heal_line(A, s)
    moved = bool(heal) or bool(cure and not has_antidote)
    anti = antidote_line(A, s, walk=not moved) if kind not in ("heal", "lesson") else None
    lines = [x for x in (cure, heal, anti) if x]
    if lines:
        details = list(a.get("details", []))
        if moved:
            details.insert(0, "The way after that (walk it from where you will stand): " + a["do"])
            a = dict(a, do=" Then: ".join(lines) + " After that, ask again or look for the next walk.", details=details)
        else:
            a = dict(a, do=" Then: ".join(lines + [a["do"]]), details=details)
    if kind in ("way", "train", "ready") and "Train first" not in a["do"]:
        a = dict(a, details=[d for d in a["details"] if not d.startswith("Heal first:") or heal_need(A, s, ROAD_HEAL)])
    return a
