"""R19 (28 Oct 2026): stricter Brock readiness from the damage model.

Round b3: Haiku walked into Brock at 23/29 HP (L9). The old Pewter heal line was a guess (HP under 3/4) and the
readiness check used AVERAGE damage. Here the line is the WORST CASE of the real fight, lead Pokemon alone
(the left bypass skips the gym trainer), turn by turn, with the game's damage formula (advise.damage):

- your hits: your best attack with PP left, at its LOWEST damage roll (217/255), one extra hit if it can miss;
- Brock's turns: one fewer than your hits if you are strictly faster, else as many;
- Brock's damage: its strongest attack at the HIGHEST roll; SCREECH (defense -2 stages) used first when that
  hurts more ((k - s) hits at the lowered defense after s Screeches); DEFENSE CURL raises its defense
  against your physical attacks;
- ONE critical hit (Gen 1: double level, stat changes ignored) on its strongest attack;
- BIDE (Onix): harmless if you need at most 2 hits after it starts (it stores 2-3 turns); with 3+ hits it can
  release double the damage it took: counted as that damage.
need = all of that + 1 HP. Heal when HP < need; ready for Brock when need <= max HP at full HP and PP.
"""
import math

STAGE = {0: 1.0, 1: 1.5, -2: 0.5, -4: 0.33, -6: 0.25}       # Gen 1 stat stage ratios (data/battle/stat_modifiers)
BRIEF = "Brock:1"


def _moves(me):
    return [dict(mv) for mv in me["moves"]]


def _hit(A, mv, me, foe, foe_def_up):
    """Lowest roll of one use of `mv` (0 if no direct damage)."""
    m = A.MOVES.get(mv)
    if not m or not m.get("power"):
        return 0
    fs = dict(foe["stats"])
    if foe_def_up and m["type"] not in A.SPECIAL_TYPES:
        fs["def"] = int(fs["def"] * STAGE[1])
    d = A.damage(mv, me["level"], me["stats"], fs, me["types"], foe["types"], foe["hp"])
    if not d:
        return 0
    return d[0] * (2 if A.hits(mv) == 2 else 1)


def _foe_max(A, foe, me, def_ratio=1.0, crit=False):
    """Brock's strongest attack at the highest roll vs your defense x def_ratio (crit: double level, no stages)."""
    best = 0
    st = dict(me["stats"])
    if not crit:
        st["def"] = max(1, int(st["def"] * def_ratio))
    for name in foe["moves"]:
        name = name["move"] if isinstance(name, dict) else name
        m = A.MOVES.get(name)
        if not m or not m.get("power"):
            continue
        d = A.damage(name, foe["level"] * (2 if crit else 1), foe["stats"], st, foe["types"], me["types"], me["hp"])
        if d:
            best = max(best, d[1])
    return best


def _effects(A, foe):
    return {A.MOVES.get(n["move"] if isinstance(n, dict) else n, {}).get("effect") for n in foe["moves"]}


def worst_case(A, s, full=False, key=BRIEF):
    """dict(need, ok, parts, lead, hits): the HP the lead needs to beat Brock in the worst case (see module doc).
    full=True: as after a heal (full HP and PP). None without a team."""
    team = [t for t in (s.get("team") or []) if t["hp"] > 0 or full]
    if not team:
        return None
    t = team[0]
    if full:
        t = dict(t, hp=t["max_hp"], status="ok", moves=[dict(mv, pp=A.MOVES.get(mv["move"], {}).get("pp", 10))
                                                         for mv in t["moves"]])
    me = A._party_mon(t, s.get("badges") or [])
    moves = {mv["move"]: (mv["pp"] if mv.get("pp") is not None else A.MOVES.get(mv["move"], {}).get("pp", 10))
             for mv in t["moves"]}
    total, crit_extra, parts, hits_all = 0, 0, [], []
    for e in A.TEAMS[key]["party"]:
        foe = A._foe(e)
        eff = _effects(A, foe)
        hp, n, used = foe["hp"], 0, []
        while hp > 0:
            opts = [(mv, _hit(A, mv, me, foe, "DEFENSE_UP1_EFFECT" in eff)) for mv, pp in moves.items() if pp > 0]
            opts = [o for o in opts if o[1] > 0]
            if not opts:
                return dict(need=10 ** 6, ok=False, parts=parts + [f"no attack PP left for {foe['species']}"],
                            lead=me, hits=hits_all)
            mv, lo = max(opts, key=lambda o: o[1])
            moves[mv] -= 1
            hp -= lo
            n += 1
            used.append(mv)
            if hp > 0 and n > 12:
                return dict(need=10 ** 6, ok=False, parts=parts + [f"cannot knock out {foe['species']}"], lead=me,
                            hits=hits_all)
        if any((A.MOVES.get(mv) or {}).get("accuracy", 100) < 100 for mv in used):
            n += 1                                   # one miss allowance
        faster = me["stats"]["spd"] > foe["stats"]["spd"]
        k = n - 1 if faster else n
        hit = _foe_max(A, foe, me)
        dmg = k * hit
        if "DEFENSE_DOWN2_EFFECT" in eff:            # Screech first, then hits at the lowered defense
            for sc in (1, 2, 3):
                if sc < k:
                    dmg = max(dmg, (k - sc) * _foe_max(A, foe, me, STAGE[-2 * sc]))
        if "BIDE_EFFECT" in eff and n >= 3:
            dmg = max(dmg, 2 * (foe["hp"] - 1))      # stored hits that did not knock it out, returned double
        if k > 0:
            crit_extra = max(crit_extra, _foe_max(A, foe, me, crit=True) - hit)
        total += dmg
        parts.append(f"{foe['species']} {dmg}")
        hits_all.append((foe["species"], n, k, hit))
    need = total + crit_extra + 1
    parts.append(f"one critical hit +{crit_extra}")
    return dict(need=need, ok=need <= me["hp"], parts=parts, lead=me, hits=hits_all)


def need_text(w):
    return f"{w['need']} HP (worst case: {', '.join(w['parts'])})"


def ready(A, s):
    """Ready for Brock = the old average check (r17_advice.brock_ready) AND the worst case at full HP/PP fits."""
    import r17_advice as X
    if not X.brock_ready(A, s):
        return False
    w = worst_case(A, s, full=True)
    return bool(w and w["ok"])


def heal_reason(A, s):
    """Why to heal before Brock now (str) or None. Fainted/sick lead -> heal; HP below the worst-case line -> heal
    (a heal also refills PP, so the line is computed with the PP you have now)."""
    import r17_advice as X
    base = X.heal_need(A, s, 0)                      # fainted / status / no attack PP (share 0: no HP line)
    if base:
        return base
    w = worst_case(A, s)
    if w and not w["ok"]:
        lead = w["lead"]
        return f"{lead['species']} has {lead['hp']}/{lead['max_hp']} HP; Brock needs {need_text(w)}"
    return None
