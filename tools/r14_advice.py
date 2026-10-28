"""R14 advice layer: Mt. Moon floors, Route 4, Cerulean and Misty. Runs before the R13 layer.

1. Mt. Moon: the next ladder on THIS floor (1F (5,5), B1F (21,17), B2F the Rocket at (11,16) then the Super Nerd at
   (12,9)), the walk around the 1F Lass at (30,4), side ladders that only lead back, heal / lost questions answered with
   a verdict (no automatic Center trip at full HP), the fossil YES/NO box (A = YES), the way out after the fossil.
2. Route 4: the west part has no way east (Cerulean only through the cave); heal at the Route 4 Center before the cave
   (a blackout then brings you back to Route 4, not Pewter); the east ledges to Cerulean.
3. Cerulean: Center, Mart, rival and Misty readiness on ONE fight model (r13_advice.outcome / level_target), with a level
   target and a training place. Catch questions (Oddish, Pikachu, Paras) get "levels on your lead help more".
4. Battle: the move picked never differs from the best move when it is resisted; Misty foe lines.
Facts: reference/pokered (objects/MtMoon*.asm, scripts/MtMoonB2F.asm, engine/events/pokecenter.asm +
set_blackout_map.asm, data/maps/special_warps.asm, data/items/marts.asm + prices.asm, engine/battle/experience.asm,
base_stats/*.asm). Walks are map-checked with advise.walk_to; fights are estimates. Runtime strings: plain game words.
"""
import copy
import functools
import re
from pathlib import Path

import r11_maps as M
import r11_advice as L
import r13_advice as T

CAVE = L.CAVE
NERD = 'EVENT_BEAT_MT_MOON_EXIT_SUPER_NERD'
ROCKET = 'EVENT_BEAT_MT_MOON_3_TRAINER_0'      # B2F Rocket at (11,16): Rattata, Zubat L13 (MtMoonB2F.asm)
LASS = 'EVENT_BEAT_MT_MOON_1_TRAINER_2'        # 1F Lass at (30,4), facing down, sight 3
LASS_SIGHT = [(30, 5), (30, 6), (30, 7)]
ROCKET_SIGHT = [(11, 17), (11, 18), (11, 19), (11, 20)]
LADDER = {'MT_MOON_1F': (5, 5), 'MT_MOON_B1F': (21, 17)}
FLOOR_NAME = {'MT_MOON_1F': '1F', 'MT_MOON_B1F': 'B1F', 'MT_MOON_B2F': 'B2F'}
# Side ladders (map-checked, R14 build): each leads to a pocket that only comes back here.
SIDE = {('MT_MOON_1F', (17, 11)): 'a side room (TM Mega Punch) that only leads back here',
        ('MT_MOON_1F', (25, 15)): 'a side branch (the HP Up item) that only leads back here'}
WAY_DOWN = ('The Super Nerd and the fossils are on B2F, two floors down. Way: 1F ladder (5,5) -> B1F (5,5) -> walk to '
            'the B1F ladder (21,17) -> B2F (21,17).')
NEEDED = ('Needed fights before the fossil: only the Rocket at B2F (11,16) (Rattata, Zubat L13) and the Super Nerd at '
          'B2F (12,8) (Grimer, Voltorb, Koffing L12). 1F and B1F need no fight.')
NO_ROPE = 'Do not use an Escape Rope: it takes you back to the last Center you used, not to this exit.'
CENTER4 = 'the Route 4 Center (door (11,5))'
MART_LINE = ('Cerulean Mart (door (25,25)): Potion 300, Repel 350, Antidote 100, Poke Ball 200. No Super Potions here '
             '(the first ones are in Vermilion).')
HEAL_Q = re.compile(r"\b(heal|healing|hurt|cent(?:er|re)|pokecenter|am i (?:ok|okay|fine)|enough hp|low hp|"
                    r"hp (?:is )?(?:low|enough|ok))\b")
LOST_Q = re.compile(r"\b(lost|where am i|which way|where (?:is|are) the (?:ladder|stairs|exit|way)|next floor|"
                    r"next ladder|ladders?|stairs)\b")
ITEM_Q = re.compile(r"\b(moon stone|water gun|rare candy|mega punch|escape rope ball|hp up)\b")
EAST_Q = re.compile(r"\b(cerulean|east|blocked|ledge|wall|walled|other side|far side|way on|exit|cave exit|"
                    r"get past|go around)\b")
CATCH_Q = re.compile(r"\b(oddish|pikachu|paras|bellsprout)\b")
MISTY_READY_Q = re.compile(r"\b(misty|gym|cascade)\b")
TRAIN_Q = T.TRAIN_Q
WATER = ('WATER_GUN', 'BUBBLE', 'BUBBLEBEAM')


def result(do, why, details=(), **extra):
    return dict(do=do, why=why, details=list(details), **extra)


def here(s):
    return L.here(s)


def ok(r):
    return bool(r[0]) and r[1] >= T.MARGIN


def words(name):
    return name.replace('_', ' ')


def lead_index(s):
    return next((n for n, t in enumerate(s['team']) if t['hp'] > 0), 0)


def potion_gain(A, s):
    bag = A._bag(s)
    item = next((i for i in sorted(A.HEAL, key=A.HEAL.get) if bag.get(i)), 'POTION')
    return item, A.HEAL[item]


# ---------- one fight model: r13_advice.outcome ----------

def verdict(A, s, keys):
    """('win', 0) / ('potion', k) / ('heal', 0) / ('train', level or None) for these fights in a row."""
    have = T.potions(A, s)
    if ok(T.outcome(A, T.mons(A, s), keys, have)):
        return 'win', 0
    i = lead_index(s)
    first = s['team'][i]
    _, gain = potion_gain(A, s)
    for k in range(1, have + 1):
        trial = T.mons(A, s)
        trial[i]['hp'] = min(first['max_hp'], first['hp'] + gain * k)
        if ok(T.outcome(A, trial, keys, have - k)):
            return 'potion', k
    if ok(T.outcome(A, T.mons(A, s, True), keys, have)):
        return 'heal', 0
    return 'train', T.level_target(A, s, keys, have)


def fight_word(A, s, keys, healed=False):
    return 'likely win' if ok(T.outcome(A, T.mons(A, s, healed), keys, T.potions(A, s))) else 'likely loss'


def use_potions(A, s, k):
    item, gain = potion_gain(A, s)
    first = s['team'][lead_index(s)]
    name = words(item).title()
    return (f"Use {k} {name}{'s' if k != 1 else ''} now (+{gain} HP each): press START, pick ITEM, press A on "
            f"{item.replace('_', ' ')}, press A on USE, pick {first['species']}, press A" + T.potion_finish(name, k))


@functools.lru_cache(None)
def base_exp(species):
    f = Path(M.SRC) / 'data/pokemon/base_stats' / (species.lower().replace('_', '') + '.asm')
    m = re.search(r'db (\d+) ; base exp', f.read_text(encoding='utf-8')) if f.exists() else None
    return int(m[1]) if m else None


def trainer_exp(A, key):
    """EXP from one trainer for one Pokemon that fought alone: base exp x level / 7, x1.5 in trainer battles
    (engine/battle/experience.asm). None if a base exp is unknown."""
    total = 0
    for p in A.TEAMS[key]['party']:
        b = base_exp(p['species'])
        if b is None:
            return None
        e = b * p['level'] // 7
        total += e + e // 2
    return total


def best_move(A, me, foe, skip_resisted=True):
    """(move, option) with the highest expected damage among moves with PP; resisted moves only if nothing else hurts."""
    opts = []
    for mv in me['moves']:
        o = A.move_option(mv['move'], mv['pp'] if mv.get('pp') is not None else 10, me, foe)
        if o and o['expect'] > 0 and (mv.get('pp') is None or mv['pp'] > 0):
            res = A.type_mult(A.MOVES[mv['move']]['type'], foe['types']) < 1
            opts.append((res and skip_resisted, -o['expect'], mv['move'], o))
    if not opts:
        return None, None
    _, _, move, o = min(opts)
    return move, o


# ---------- Mt. Moon ----------

def all_beaten(s):
    return dict(s, teacher_events=dict(s.get('teacher_events', {}), **{e: True for e in M.events()
                                                                      if e.startswith('EVENT_BEAT_')}))


def floor_walk(A, s, tile, events=None):
    """A walk on this floor only to `tile` (None if there is none). events = extra beaten flags (map checks)."""
    m, pos = here(s)
    st = s if events is None else dict(s, teacher_events=dict(s.get('teacher_events', {}), **events))
    r = A.walk_to(st, lambda mm, p: mm == m and p == tile, max_maps=0, fallback=False)
    return (r, A.walk_words(st, r)) if r else (None, None)


def pocket(A, s):
    """The warps of this floor that can be reached from here (trainers ignored, people are walls)."""
    m, pos = here(s)
    st = all_beaten(s)
    out = []
    for w in A._warps(m):
        if w[:2] == pos or A.walk_to(st, lambda mm, p, t=w[:2]: mm == m and p == t, max_maps=0, fallback=False):
            out.append(w[:2])
    return out


def leg_text(ws, n=6):
    shown = ', '.join(ws[:n])
    rest = ', '.join(ws[n:])
    return shown, rest


def next_fight(s):
    if not M.defeated(s, ROCKET):
        return 'Rocket:1', 'the Rocket at B2F (11,16) (Rattata, Zubat L13)'
    if not M.defeated(s, NERD):
        return 'SuperNerd:2', 'the Super Nerd at B2F (12,8) (Grimer, Voltorb, Koffing L12)'
    return None, None


def center_legs(A, s):
    go = T.center_walk(A, s, 'MT_MOON_POKECENTER')['do']
    return T.legs(go, 4)


def heal_verdict(A, s, asked):
    """L9: a verdict with numbers, never an automatic Center walk. None = not a heal case (go on with the floor walk)."""
    i = lead_index(s)
    first = s['team'][i]
    half = first['hp'] * 2 >= first['max_hp']
    key, name = next_fight(s)
    have = T.potions(A, s)
    hp = f"{first['hp']}/{first['max_hp']} HP"
    if half and not asked:
        return None
    v = verdict(A, s, [key]) if key else ('win', 0)
    if half and v[0] == 'win':
        why = (f"By the fight model {name} is a likely win with {hp}" + (f" and your {have} Potion"
               f"{'s' if have != 1 else ''}" if have else '') + ' (estimate).') if key else 'No fight is needed on the way out.'
        return result(f"No need to heal: {first['species']} has {hp}, enough for " + (name if key else 'the way out') +
                      '.', why, [], verdict='go')
    k = 0
    if not half and have:
        _, gain = potion_gain(A, s)
        k = min(have, -(-(first['max_hp'] - 2 * first['hp']) // (2 * gain)))
    if v[0] == 'potion':
        k = max(k, v[1])
    if k:
        trial = copy.deepcopy(s)
        trial['team'][i]['hp'] = min(first['max_hp'], first['hp'] + potion_gain(A, s)[1] * k)
        trial['bag'] = [dict(b, count=b['count'] - k) if b['item'] == potion_gain(A, s)[0] else b for b in s['bag']]
        after = verdict(A, trial, [key])[0] if key else 'win'
        if after == 'win':
            return result(use_potions(A, s, k) + ' No Center trip is needed.',
                          f"{first['species']} has {hp}. A Potion is faster than walking back; then "
                          + (f"{name} is a likely win (estimate)." if key else 'the way out is safe.'), [], verdict='potion')
    legs = center_legs(A, s)
    why = (f"{first['species']} has {hp}" + (' and no Potion' if not have else '') + '; ' +
           (f"{name} is a likely loss now (estimate)." if key and v[0] != 'win' else 'that is below half for the cave.'))
    details = ['Inside: walk up to the nurse counter, face up, press A, then A through the text.']
    if v[0] == 'train':
        details.append(f"Even healed, {name} looks hard: train to about L{v[1]} (estimate)." if v[1] else
                       f"Even healed, {name} looks hard: train several levels.")
    rope = A._bag(s).get('ESCAPE_ROPE', 0)
    if rope and first['hp'] * 5 < first['max_hp'] and here(s)[0] != 'MT_MOON_1F':
        details.append('Nearly fainted and far from the Center: an Escape Rope (ITEM) takes you to the last Center you '
                       'used (' + str(s.get('last_heal_map') or 'not known') + '); your fossil and badges stay.')
    return result(f"Go back to {CENTER4} to heal" + (f": {legs}." if legs else '.'), why, details, verdict='heal')


def lass_line(A, s, q):
    if M.defeated(s, LASS) or not re.search(r'\b(fight|exp|experience|battle|lass|train|level)\b', q):
        return None
    me = T.mons(A, s)[lead_index(s)]
    foe = A._foe(A.TEAMS['Lass:5']['party'][0])
    move, _ = best_move(A, me, foe)
    water = [words(mv['move']) for mv in me['moves'] if mv['move'] in WATER]
    if fight_word(A, s, ['Lass:5']) != 'likely win' or not move:
        return 'The Lass is a likely loss right now (estimate): walk around her.'
    return (f"You may fight her for EXP (likely win, estimate) with {words(move)}." +
            (f" Never {' or '.join(water)}: her grass Pokemon resist water." if water else ''))


def cave_floor(A, s, q, pure):
    """L1-L6, L8: the walk to the next ladder or fight on this floor."""
    m, pos = here(s)
    fossil = L.has_fossil(A, s)
    nerd = M.defeated(s, NERD)
    reach = pocket(A, s)
    if fossil:
        if m == 'MT_MOON_B1F' and (27, 3) in reach:
            r, ws = floor_walk(A, s, (27, 3))
            if pos == (27, 3) or not ws:
                return None
            shown, rest = leg_text(ws)
            return result(f"To the exit: {shown} = the way out to Route 4 (24,5).", 'You have the fossil: the cave is done.',
                          ([f'Then: {rest}.'] if rest else []) + ([NO_ROPE] if not pure else []))
        if m == 'MT_MOON_B2F':
            a = L.walk(A, s, L.goal_at('ROUTE_4', (24, 5)), 'the Route 4 cave exit')
            a['details'].insert(0, 'Fossil taken: leave by B2F (5,7) -> B1F (23,3), then right 4 to B1F (27,3) -> '
                                   'Route 4 (24,5). Do not restart the cave.')
            if not pure:
                a['details'].append(NO_ROPE)
            return a
        return None
    if m == 'MT_MOON_1F':
        side = next((t for (mm, t) in SIDE if mm == m and abs(t[0] - pos[0]) + abs(t[1] - pos[1]) <= 2), None)
        r, ws = floor_walk(A, s, LADDER[m])
        if not ws:
            return None
        shown, rest = leg_text(ws)
        do = f"Next toward the ladder (5,5) in the north-west: {shown}." + ('' if rest else ' Step on it to go down to B1F.')
        if not M.defeated(s, LASS) and pos in ((30, 8), (30, 9), (30, 10)):
            do = (f"Do not walk up: the Lass at (30,4) sees (30,5)-(30,7). Go around: {shown}." +
                  (' Then on to the ladder at (5,5).' if rest else ''))
        if side:
            do = f"Not the ladder at ({side[0]},{side[1]}): it is {SIDE[(m, side)]}. Go to the ladder at (5,5): {shown}."
        details = [f'Then: {rest}, then step on the ladder to B1F.'] if rest else []
        if not pure:
            details += [NEEDED]
            line = lass_line(A, s, q)
            if line:
                details.append(line)
        return result(do if pure else WAY_DOWN + ' ' + do, 'The next ladder on this floor is the goal, not B2F.', details)
    if m == 'MT_MOON_B1F':
        if (21, 17) in reach:
            r, ws = floor_walk(A, s, (21, 17))
            if not ws:
                return None
            shown, rest = leg_text(ws)
            do = f"Next toward the B1F ladder (21,17): {shown}: ladder down to B2F (21,17)."
            return result(do if pure else 'The Super Nerd and the fossils are on B2F, one floor down. ' + do,
                          'B1F has no trainers; this ladder is the way to the fossils.',
                          ([f'Then: {rest}.'] if rest else []) + ([] if pure else [NEEDED]))
        back = next((w for w in reach if A._warp_dest(m, next(x for x in A._warps(m) if x[:2] == w), 'ROUTE_4')[0]
                     == 'MT_MOON_1F'), None)
        if back and not reach == [(23, 3), (27, 3)]:
            r, ws = floor_walk(A, s, back)
            shown = ', '.join(ws[:6]) if ws else 'you stand on it'
            return result(f"This part of B1F is a side branch that only leads back. Go up the ladder at ({back[0]},"
                          f"{back[1]}) ({shown}), then on 1F walk to the ladder at (5,5).",
                          'Only the 1F ladder at (5,5) leads to the B1F ladder (21,17) and the fossils.', [WAY_DOWN])
        return None
    # B2F, no fossil
    if (21, 17) not in reach:
        back = reach[0] if reach else None
        if not back:
            return None
        r, ws = floor_walk(A, s, back)
        return result(f"This part of B2F is a side room that only leads back. Go up the ladder at ({back[0]},{back[1]})"
                      + (f": {', '.join(ws[:6])}." if ws else '.'),
                      'The fossils are reached only from the ladder B1F (21,17) -> B2F (21,17).', [WAY_DOWN])
    if nerd:
        return None                                  # r11 pickup (with the fossil YES line added by the caller)
    key, name = next_fight(s)
    if pos == (12, 9):
        return nerd_ready(A, s, pure)
    r, ws = floor_walk(A, s, (12, 9))
    if ws:
        shown, rest = leg_text(ws)
        return result(f"Next toward the Super Nerd at (12,9): {shown}." + (' Then ask at (12,9).' if not rest else ''),
                      'He stands at (12,8) above the fossils; talk to him from (12,9).',
                      ([f'Then: {rest}.'] if rest else []) + ([] if pure else [nerd_line(A, s)]))
    if M.defeated(s, ROCKET):
        return None
    if pos == (11, 21):
        return rocket_ready(A, s, pure)
    r, ws = floor_walk(A, s, (11, 21))
    if not ws:
        return None
    shown, rest = leg_text(ws, 11)
    do = f"Next toward the needed Rocket fight, a long loop: {shown}."
    details = [f'Then: {rest}.'] if rest else []
    if not pure:
        do += (' The Rocket at (11,16) sees (11,17)-(11,20): this fight is needed (Rattata, Zubat L13). '
               f"With your team now he is a {fight_word(A, s, ['Rocket:1'])} (estimate).")
        details.append('After him: walk up to (12,9) below the Super Nerd. ' + nerd_line(A, s))
    return result(do, 'Only this fight blocks the way to the fossils on B2F; the other Rockets can be walked around.',
                  details)


def nerd_line(A, s):
    return (f"The Super Nerd (Grimer, Voltorb, Koffing L12) with your team now: {fight_word(A, s, ['SuperNerd:2'])} "
            '(estimate).')


def ready_text(A, s, key, name, go):
    v = verdict(A, s, [key])
    if v[0] == 'win':
        return f"Ready: {name} is a likely win (estimate). {go}", 'win'
    if v[0] == 'potion':
        return f"Almost ready: {use_potions(A, s, v[1])} Then {name} is a likely win (estimate). {go}", 'potion'
    legs = center_legs(A, s)
    if v[0] == 'heal':
        return (f"Not ready: heal first at {CENTER4}" + (f": {legs}." if legs else '.') +
                f" Healed, {name} is a likely win (estimate)."), 'heal'
    return (f"Not ready: even healed, {name} looks too strong. Train to about L{v[1]} (estimate) and heal at {CENTER4}."
            if v[1] else f"Not ready: train several levels first and heal at {CENTER4}."), 'train'


def rocket_ready(A, s, pure):
    do, v = ready_text(A, s, 'Rocket:1', 'the Rocket at (11,16) (Rattata, Zubat L13)',
                       'Step up 1 to (11,20): he sees you and the fight starts. In the battle, ask for each move.')
    return result(do if not pure else 'Step up 1 to (11,20).', 'This Rocket blocks the only way to the fossils.',
                  [] if pure else [nerd_line(A, s)], verdict=v)


def nerd_ready(A, s, pure):
    do, v = ready_text(A, s, 'SuperNerd:2', 'the Super Nerd (Grimer, Voltorb, Koffing L12)',
                       'Face up and press A to talk to him: the fight starts.')
    return result(do if not pure else 'Face up and press A.', 'He stands at (12,8) right above you; he guards the fossils.',
                  [] if pure else ['After the win: right 1 to (13,9), up 2 to (13,7), face up, press A on the fossil, '
                                   'and press A for YES.'], verdict=v)


def cave(A, s, q, context):
    m, pos = here(s)
    pure = bool(s.get('r13_pure'))
    live = [t for t in s['team'] if t['hp'] > 0]
    if not live or ITEM_Q.search(q) or 'Boulder' not in s['badges'] or 'Cascade' in s['badges']:
        return None
    if re.search(r'\b(escape|retreat|back out|poison|out of pp)\b', q):
        return None                                            # r11: Antidote / Escape Rope / poison checks
    if L.recovery_reason(A, s) and not L.recovery_reason(A, s).startswith('Heal first'):
        return None                                            # status, no PP: r11
    if T.BLOCK_Q.search(q) and not pure:
        return None                                            # r13 blocked check (sight lines, detours)
    if (re.search(r'\bready\b|\breadiness\b', q) and MISTY_READY_Q.search(q)
            or re.search(r'\bcan i (?:beat|defeat|fight|face|take on) (?:misty|(?:the )?gym)\b', q)):
        return None                                            # Misty readiness: r11 -> misty()
    if CATCH_Q.search(q) and not pure:
        return catch(A, s, q)
    nerd_fossil = M.defeated(s, NERD) and not L.has_fossil(A, s) and m == 'MT_MOON_B2F'
    if not pure and not nerd_fossil:
        h = heal_verdict(A, s, bool(HEAL_Q.search(q)))
        if h:
            if h['verdict'] == 'go':
                way = cave_floor(A, s, q, True)
                if way:
                    h['do'] += ' Go on: ' + way['do']
                    h['details'] += way['details']
            return h
    a = cave_floor(A, s, q, pure)
    if a is None and nerd_fossil and not pure:
        a = L.pickup(A, s, 'MT_MOON_B2F', (13, 6), 'HELIX_FOSSIL')
        a['details'].append('When it asks "You want the HELIX FOSSIL?", press A for YES. You need one fossil: the way '
                            'out opens only after you take it. The Super Nerd takes the other one.')
    return a


# ---------- fossil text box ----------

def fossil_box(s):
    rows = ' '.join(((s.get('teacher_screen') or {}).get('rows') or []))
    return re.search(r'\b(DOME|HELIX) FOSSIL\?', rows)


def text_extra(A, s, question, a, context=None):
    """L7: "You want the DOME/HELIX FOSSIL?" -> A for YES (overrides the general YES/NO = B rule)."""
    hit = fossil_box(s)
    if not hit or s.get('battle'):
        return a
    _, quote = T.screen_words(s)
    item = hit[1] + '_FOSSIL'
    after = dict(s, text_box=False, bag=list(s['bag']) + [dict(item=item, count=1)],
                 teacher_events=dict(s.get('teacher_events', {}), **{'EVENT_GOT_' + item: True}))
    r = A.walk_to(after, L.goal_at('ROUTE_4', (24, 5)), max_maps=4, fallback=False)
    walk = ', '.join(A.walk_words(after, r)[:6]) if r else ''
    do = (f'The text box says "{quote}". Press A for YES. You need one fossil: the way out opens only after you take '
          'it. Then press A through the text.' + (f' Then walk to the ladder: {walk}.' if walk else ''))
    return dict(a, do=do, why='Saying NO leaves both fossils there and the way to the exit ladder (5,7) stays closed.',
                details=['On B1F after the ladder: right 4 to (27,3) = the way out to Route 4 (24,5). ' + NO_ROPE])


def repeat_guard(A, s, question, context, a):
    out = T.repeat_guard(A, s, question, context, a)
    if out is not a and fossil_box(s) and s.get('text_box'):
        return dict(out, do='Same screen three times: press A once now (A says YES and you get the fossil). Do not '
                            'press B. Then press A through the text.', details=[a['do']])
    return out


# ---------- Route 4 ----------

def route4(A, s, q, context=None):
    m, pos = here(s)
    if 'Boulder' not in s['badges'] or L.has_fossil(A, s) or M.defeated(s, NERD):
        if m == 'ROUTE_4' and pos[0] >= 22:
            return route4_east(A, s, q)
        return None
    if m == 'ROUTE_4' and pos[0] >= 22:
        return route4_east(A, s, q)
    if T.SHOP_Q.search(q) or ITEM_Q.search(q) or (T.TRAIN_Q.search(q) and not EAST_Q.search(q)):
        return None
    if m == 'MT_MOON_POKECENTER' and (not EAST_Q.search(q) or T.hurt(s)):
        return None                                            # inside: r13 nurse steps
    if MISTY_READY_Q.search(q) and re.search(r'\b(ready|beat|win|strong)\b', q):
        return None                                            # Misty readiness: r11 -> misty()
    reason = L.recovery_reason(A, s)
    if reason and not reason.startswith('Heal first'):
        return None                                            # PP, status, fainted: r11 heal checks
    first = s['team'][lead_index(s)]
    hurt = first['hp'] < first['max_hp'] or first['status'] != 'ok'
    unset = s.get('last_heal_map') not in (None, 'ROUTE_4')
    heal_line = None
    if hurt or unset:
        go = T.center_walk(A, s, 'MT_MOON_POKECENTER')['do'] if m != 'MT_MOON_POKECENTER' else ''
        legs = T.legs(go, 4)
        heal_line = ('Heal at the Center first (door (11,5)' + (f": {legs}" if legs else '') + '; inside: walk up to the '
                     'nurse, face up, press A). Then a blackout in the cave brings you back here to Route 4, not to '
                     + ('Pewter' if s.get('last_heal_map') in (None, 'PEWTER_CITY') else words(s['last_heal_map']).title())
                     + '.')
    if EAST_Q.search(q):
        r = A.walk_to(s, L.goal_at('ROUTE_4', (18, 5)), max_maps=2, fallback=False)
        walk = ', '.join(A.walk_words(s, r)[:5]) if r else ''
        do = ('This part of Route 4 has no way east. The only way to Cerulean is through Mt. Moon: door at (18,5); you '
              'come out at Route 4 (24,5) on the far side.')
        details = ([f'Way to the cave door: {walk}.'] if walk else [])
        if heal_line:
            details.insert(0, heal_line)
        why = 'The ledges and rocks east of (20,6) cannot be crossed from this side (map check).'
        if T.BLOCK_Q.search(q) and m == 'ROUTE_4':
            b = T.blocked(A, s, q, context)                    # keep the R13 blocked check and its pure detour
            return result(b['do'] + ' ' + do, b['why'] + ' ' + why, details)
        return result(do, why, details)
    if heal_line and (not q or re.search(r'\b(next|where|what|how|go|way|cave|mt\.? ?moon|heal|should)\b', q)):
        return result(heal_line, f"Your team: {T.team_line(s)}. A blackout sends you to the last Center you used.",
                      ['The nurse restores HP and PP for free.', 'The cave door is at (18,5). Cerulean is only through Mt. Moon.'], verdict='heal')
    return None


def route4_east(A, s, q):
    if q and not (EAST_Q.search(q) or re.search(r'\b(next|where|what|how|way|go)\b', q)) or T.hurt(s):
        return None
    if T.SHOP_Q.search(q) or T.BLOCK_Q.search(q):
        return None
    r = A.walk_to(s, lambda mm, p: mm == 'CERULEAN_CITY', max_maps=2, fallback=False)
    if not r:
        return None
    ws = A.walk_words(s, r)
    return result('To Cerulean: ' + ', '.join(ws) + '. The ledges are one-way: you cannot walk back up them.',
                  'This is the east side of Route 4: Cerulean City is at the east end.',
                  ['In Cerulean: heal at the Center (door (19,17)), then ask if you are ready for Misty.'])


# ---------- Cerulean, rival, Misty ----------

MISTY_AT = (4, 2)                              # objects/CeruleanGym.asm; talk tile (4,3) below her


def by_misty(s):
    """Sol R14 B2: on the talk tile (4,3) or on another tile next to Misty the gym walk is done (the walker rejects a
    zero-step goal, so it must not decide here). No facing is read, so any tile next to her counts."""
    m, pos = here(s)
    return m == 'CERULEAN_GYM' and abs(pos[0] - MISTY_AT[0]) + abs(pos[1] - MISTY_AT[1]) == 1


def gym_keys(A, s):
    """The gym fights still ahead (same rule as r11 gym_plan, without its old fight model)."""
    if by_misty(s):
        # Only trainers still in the way: the Swimmer is behind; the Goldeen girl only if unbeaten and she sees this tile.
        m, pos = here(s)
        jr = 'EVENT_BEAT_CERULEAN_GYM_TRAINER_0'
        only_jr = dict(s, teacher_events=dict(s.get('teacher_events', {}), **{
            o['event']: True for o in M.maps()[m]['objects'] if o.get('event') and o['event'] != jr}))
        seen = not M.defeated(s, jr) and pos in M.sight(only_jr, m)
        return (['JrTrainerF:1'] if seen else []) + ['Misty:1'], 'here'
    flags = dict(s.get('teacher_events', {}), EVENT_BEAT_CERULEAN_GYM_TRAINER_0=True)
    bypass = A.walk_to(dict(s, teacher_events=flags), L.goal_at('CERULEAN_GYM', (4, 3)), max_maps=6, fallback=False)
    keys = []
    if not bypass and not M.defeated(s, 'EVENT_BEAT_CERULEAN_GYM_TRAINER_1'):
        keys.append('Swimmer:1')
    if not M.defeated(s, 'EVENT_BEAT_CERULEAN_GYM_TRAINER_0'):
        keys.append('JrTrainerF:1')
    return keys + ['Misty:1'], bypass


def rival_key(s):
    return {'SQUIRTLE': 'Rival1:7', 'BULBASAUR': 'Rival1:8', 'CHARMANDER': 'Rival1:9'}.get(s.get('rival_starter'))


def bridge_keys(A):
    rows = [r for r in M.maps()['ROUTE_24']['objects'] if r.get('event') and r['x'] in (10, 11)]
    return [T.team_key(A, r) for r in rows] + ['Rocket:6']


def train_place(A, s, pots):
    """Where to train before Misty, from the fight model: the rival + Nugget Bridge, else the Route 4 grass."""
    rk = rival_key(s)
    rival_open = rk and not M.defeated(s, 'EVENT_BEAT_CERULEAN_RIVAL')
    if rival_open and ok(T.outcome(A, T.mons(A, s, True), [rk], pots)):
        exp = [trainer_exp(A, k) for k in bridge_keys(A)]
        total = sum(exp) if None not in exp else None
        return (f"the rival north of the Center (walk up to (20,6): he comes to you), then the 5 Nugget Bridge trainers "
                f"and the Rocket at its end" + (f" (about {total:,} EXP)" if total else ''))
    grass = T.grass_tiles(A, 'ROUTE_4')
    r = A.walk_to(s, lambda mm, p: mm == 'ROUTE_4' and p in grass, max_maps=3, fallback=False) if grass else None
    target = T.level_target(A, s, [rk], pots) if rival_open else None
    place = 'the Route 4 grass just west of Cerulean'
    if r:
        place += f" (first grass at ({r['target'][1][0]},{r['target'][1][1]}), {T.wild_levels(A, 'Route4')})"
    return place + (f" until about L{target}; then the rival north of the Center" if target else '')


def lead_moves_line(A, s, me):
    foe = A._foe(A.TEAMS['Misty:1']['party'][-1])
    move, _ = best_move(A, me, foe)
    water = [words(mv['move']) for mv in me['moves'] if mv['move'] in WATER]
    if not move:
        return ''
    return (f"Use {words(move)}." + (f" Never {' or '.join(water)}: Staryu and Starmie resist water." if water else '') +
            ' Use a Potion when HP falls below a third.')


def misty(A, s):
    """L14: Misty readiness on the r13 fight model, with a level target and a training place. Keeps the r11 urgent first
    line and its fact lines (team moves, Speed 56, Bag)."""
    m, pos = here(s)
    keys, bypass = gym_keys(A, s)
    pots = T.potions(A, s)
    i = lead_index(s)
    first = s['team'][i]
    healed = T.outcome(A, T.mons(A, s, True), keys, pots)
    now = T.outcome(A, T.mons(A, s), keys, pots)
    healthy = all(t['hp'] == t['max_hp'] and t['status'] == 'ok' for t in s['team'])
    reason = L.recovery_reason(A, s)
    others = sorted({t['species'] for n, t in enumerate(s['team']) if n != i})
    keep_out = (f" Do not switch in {', '.join(others)}: EXP is shared by every Pokemon that fought." if others else '')
    target = None
    if not ok(healed):
        target = T.level_target(A, s, keys, pots)
        need = (f"you need about L{target} with {pots} Potion{'s' if pots != 1 else ''} (estimate)" if target else
                f"you need more than L{first['level'] + 10} with {pots} Potion{'s' if pots != 1 else ''} (estimate)")
        near = m in L.TOWNS or m == 'ROUTE_4' and pos[0] >= 22
        place = (train_place(A, s, pots) if near else
                 'the trainers and wild Pokemon on your way to Cerulean (heal at each Center); ask again in Cerulean '
                 'for the exact place')
        do = (f"Not ready for Misty: {first['species']} L{first['level']}; {need}. Train until L{target}: {place}."
              if target else f"Not ready for Misty: {first['species']} L{first['level']}; {need}. Train: {place}.")
        do += keep_out
        if 'Swimmer:1' not in keys and not M.defeated(s, 'EVENT_BEAT_CERULEAN_GYM_TRAINER_1') and \
                ok(T.outcome(A, T.mons(A, s, True), ['Swimmer:1'], pots)):
            exp = trainer_exp(A, 'Swimmer:1')
            do += f" You may also fight the Gym Swimmer (Horsea, Shellder L16{f', {exp} EXP' if exp else ''})."
    elif m == 'CERULEAN_GYM' and M.defeated(s, 'EVENT_BEAT_CERULEAN_GYM_TRAINER_0') and not healthy and not ok(now):
        do = ('Not ready for Misty yet: walk out and heal at the Center first (Gym door (4,13), city Center door (19,17)), '
              'then come back. Healed, Misty is a likely win (estimate).')
    elif reason or not healthy:
        do = 'Not ready for Misty yet: heal at the Center first (door (19,17)); healed, the gym fights are a likely win (estimate).'
    elif bypass == 'here' and keys == ['Misty:1']:
        me = T.mons(A, s)[i]
        face = {(4, 3): 'up', (3, 2): 'right', (5, 2): 'left', (4, 1): 'down'}[pos]
        do = (f'Ready (estimate): you stand next to Misty. Face {face} and press A to talk to her: the fight starts. ' +
              lead_moves_line(A, s, me))
    else:
        me = T.mons(A, s)[i]
        do = ('Ready (estimate): ' + ('heal at the Center (door (19,17)), then ' if m != 'CERULEAN_POKECENTER' else '') +
              'go to the Gym door (30,19). Inside: ' + ('keep left of the Swimmer, ' if bypass and 'Swimmer:1' not in keys
                                                         and not M.defeated(s, 'EVENT_BEAT_CERULEAN_GYM_TRAINER_1') else '') +
              ('fight the Goldeen girl, then ' if 'JrTrainerF:1' in keys else '') + 'talk to Misty at (4,2). ' +
              lead_moves_line(A, s, me))
    if not any(t['hp'] > 0 for t in s['team']):
        urgent = 'Your team has fainted. Let the blackout finish with A once, then look.'
    elif any(t['hp'] > 0 and t['status'] == 'poisoned' for t in s['team']):
        urgent = ('Use an Antidote now, then heal at a Center.' if A._bag(s).get('ANTIDOTE', 0)
                  else 'Cure poison and heal before walking; poison can cause a blackout.')
    elif any(t['hp'] == 0 for t in s['team']):
        urgent = 'A teammate has fainted; heal at a Center before another fight.'
    else:
        urgent = reason
    if urgent:
        do = urgent + '\n' + do
    names = {'Swimmer:1': 'gym Swimmer (Horsea, Shellder L16)', 'JrTrainerF:1': 'gym trainer (Goldeen L19)',
             'Misty:1': 'Misty'}
    lines, mine, left = [], T.mons(A, s, True), pots
    for key in keys:
        win, _, left, mine = T.expected_fight(A, mine, A.TEAMS[key]['party'], left)
        lines.append(names[key] + (': likely win' if win else ': likely loss'))
        if not win:
            break
    details = ['HP and PP carried between fights, healed first: ' + ', '.join(lines) + '.', L.starter_tip(A, s)]
    if s['team']:
        foe = A._foe(A.TEAMS['Misty:1']['party'][-1])
        move, o = best_move(A, T.mons(A, s)[i], foe)
        if move:
            details.append(f"Lead choice: {first['species']} with {words(move)}, if healthy.")
    weak = [t['species'] for t in s['team'] if A.type_mult('WATER', A._types_of(t['species'])) > 1]
    details.append('Staryu L18: Tackle, Water Gun. Starmie L21: Tackle, Water Gun, BubbleBeam; Speed 56. ' +
                   ('Water is super effective on ' + ', '.join(weak) + '. ' if weak else '') +
                   'BubbleBeam may lower Speed; critical hits or misses can overturn this estimate.')
    details.append(f'Bag: {pots} healing items; money {s.get("money", 0)}. ' + MART_LINE)
    if bypass == 'here':
        details.append('You stand next to Misty: the Swimmer is behind you and is not counted.' +
                       (' The Goldeen girl sees this tile: she fights first.' if 'JrTrainerF:1' in keys else ''))
    elif bypass:
        details.append('Swimmer bypass: left of row 7, across row 5. Goldeen L19 has Peck and Supersonic.')
    else:
        details.append('No Swimmer bypass checked from here; his Horsea L16 and Shellder L16 are counted too.')
    why = ('The current HP/PP forecast does not safely clear the gym fights. ' if not ok(healed) else '')
    return result(do, why + 'Bill is optional for the Cascade Badge. Estimate: your party order, average damage, no '
                            'critical hits or stat changes; one Potion when HP falls below a third.', details,
                  verdict='ready' if ok(healed) and healthy and not urgent else 'not ready', target=target)


def rival(A, s):
    """The Cerulean rival on the same fight model (the r11 version used the old one); keeps the r11 team lines."""
    key = rival_key(s)
    if not key or M.defeated(s, 'EVENT_BEAT_CERULEAN_RIVAL'):
        return L.rival(A, s)                       # unknown starter / already beaten: no fight estimate there
    sp = s.get('rival_starter')
    why = f'His starter is {sp} L17. His other Pokemon are Pidgeotto L18, Abra L15 and Rattata L15.'
    details = ['One full fight with your current HP/PP; estimate only. Pidgeotto and Rattata can use Quick Attack; '
               'Abra only has Teleport.']
    if L.recovery_reason(A, s):
        return result('Heal first; stay south of the bridge.', why, details)
    pots = T.potions(A, s)
    first = s['team'][lead_index(s)]
    if ok(T.outcome(A, T.mons(A, s), [key], pots)):
        do = ('Ready (estimate): the rival is a likely win. Heal first, then walk north to (20,6): he comes to you. In the '
              'battle, ask for each move.')
    else:
        t_ = T.level_target(A, s, [key], pots)
        do = (f"Not ready for the rival: likely loss now (estimate). Train {first['species']} to about L{t_} first; stay "
              'south of row 6.' if t_ else 'Not ready for the rival: likely loss now (estimate). Train first; stay south of row 6.')
    return result(do, why, details)


def catch(A, s, q):
    """L16: catching Oddish / Pikachu / Paras is not needed for Misty."""
    first = s['team'][lead_index(s)]
    sp = CATCH_Q.search(q)[1]
    reason = {'oddish': 'Oddish lives only in the Route 24/25 grass, past the rival and Nugget Bridge.',
              'bellsprout': 'Bellsprout is not in the wild in Red (Blue only).',
              'pikachu': 'Pikachu lives in Viridian Forest, far back south of Pewter.',
              'paras': 'Paras has no Grass attack yet (Scratch; Stun Spore at L13, Leech Life at L20).'}[sp]
    do = f"Not needed for Misty: levels on your {first['species']} help more (estimate). {reason}"
    if sp == 'oddish' and here(s)[0] in L.TOWNS:
        # r11 oddish() lines, without its old-model rival verdict (the rival line below uses the Misty fight model)
        owned = any(t['species'] in ('ODDISH', 'GLOOM', 'VILEPLUME') for t in s['team'])
        open_ = not M.defeated(s, 'EVENT_BEAT_CERULEAN_RIVAL')
        tip = L.starter_tip(A, s) + (' Heal and check the rival before going north; the catch is beyond his trigger.'
                                     if open_ else '')
        details = ['If you still want one: ' + ('train your Oddish and keep Absorb PP for Misty.' if owned else
                                                'Oddish is optional: catch one in Route 24/25 grass, L12-14, with Absorb.'),
                   tip, 'Butterfree: Confusion L12, Sleep Powder L17; Pidgey: Sand-Attack L5, Quick Attack L12. These are '
                        'support, not guaranteed Starmie answers.']
        if open_:
            details.append(rival(A, s)['do'])
        return result(do, 'Nugget Bridge and Bill are optional for Misty; use them for levels when your team needs them.',
                      details)
    return result(do, 'By the fight model a new Pokemon at its catch level does not win the gym fights; your lead with '
                      'more levels does.', [L.starter_tip(A, s)])


def cerulean(A, s, q):
    m, pos = here(s)
    if 'Cascade' in s['badges'] or 'Boulder' not in s['badges']:
        return None
    if T.BLOCK_Q.search(q):
        return None
    readiness = (re.search(r'\bready\b|\breadiness\b|strong enough', q) and re.search(r'\bmisty\b|\bgym\b', q)
                 or re.search(r'\bcan i (?:beat|defeat|fight|face|take on) (?:misty|(?:the )?gym)\b', q))
    if readiness:
        return misty(A, s)
    if CATCH_Q.search(q):
        return catch(A, s, q)
    if re.search(r'\brival\b', q):
        return rival(A, s)
    if TRAIN_Q.search(q) and re.search(r'\b(misty|gym|before|where|level)\b', q) and \
            not re.search(r'\b(nugget|bridge|bill|route[ _]?2[45])\b', q):
        return misty(A, s)
    if T.SHOP_Q.search(q) and m in ('CERULEAN_CITY', 'CERULEAN_MART'):
        if m == 'CERULEAN_MART':
            return result('Talk to the clerk across the counter; choose BUY.', MART_LINE,
                          [f"You have {s.get('money', 0)}."])
        a = L.walk(A, s, lambda mm, p: mm == 'CERULEAN_MART', 'Cerulean Mart, city door (25,25)')
        a['details'].append(MART_LINE + f" You have {s.get('money', 0)}.")
        return a
    if m == 'CERULEAN_CITY' and T.hurt(s) and (not q or re.search(r'\b(next|where|what|now|go|heal|cent(?:er|re))\b', q)):
        if any(t['status'] == 'poisoned' for t in s['team']) or not any(t['hp'] > 0 for t in s['team']):
            return None
        a = L.walk(A, s, lambda mm, p: mm == 'CERULEAN_POKECENTER', 'the Cerulean Center (door (19,17))')
        a['do'] = 'Heal at the Center (door (19,17)) first, then ask if you are ready for Misty. ' + a['do']
        a['details'].append(MART_LINE)
        return a
    generic = not q or re.fullmatch(r"\W*(what(?:'s| is)? (?:now|next)|where (?:now|next)|next( step)?|what should i do"
                                    r"(?: now| next)?)\W*", q)
    if generic and m in ('CERULEAN_CITY', 'CERULEAN_GYM') and not L.recovery_reason(A, s):
        a = misty(A, s)                  # R14: the Misty verdict decides, not the old r11 forecast
        if a['verdict'] == 'ready':
            walk = L.gym_walk(A, s)
            return dict(walk, details=list(walk['details']) + [a['do']])
        return a
    return None


# ---------- battle ----------

def battle_plan(A, s, advice):
    """G7: the move in DO never differs from the best move when the DO move is resisted."""
    b = s.get('battle') or {}
    me, foe = b.get('yours'), b.get('enemy')
    hit = re.match(r'Use (\w+)', advice.get('do', ''))
    if not me or not foe or not hit or hit[1] not in A.MOVES or ' on ' in advice['do']:
        return advice
    move = hit[1]
    if A.type_mult(A.MOVES[move]['type'], foe['types']) >= 1:
        return advice
    best, o = best_move(A, me, foe)
    if not best or best == move or A.type_mult(A.MOVES[best]['type'], foe['types']) < 1:
        return advice
    return dict(advice, do=f"Use {best}{A._slot(me, best)}.",
                why=f"{foe['species']} resists {move} (half damage); {best} does more: {o['lo']}-{o['hi']} damage to its "
                    f"{foe['hp']} HP.")


def battle_answer(A, s, a):
    """L15: in the Misty fight, say who is faster and what BubbleBeam does."""
    b = s.get('battle') or {}
    me, foe = b.get('yours'), b.get('enemy')
    if not me or not foe or here(s)[0] != 'CERULEAN_GYM' or foe['species'] not in ('STARYU', 'STARMIE'):
        return a
    fs, ms = foe['stats']['spd'], me['stats']['spd']
    line = (f"{foe['species']} is faster (Speed {fs} vs your {ms}): it attacks first each turn." if fs > ms else
            f"You are faster (Speed {ms} vs {fs}).")
    if foe['species'] == 'STARMIE':
        line += ' Its BubbleBeam may lower your Speed.'
    return dict(a, details=list(a['details']) + [line])


# ---------- the hook ----------

def answer(A, s, question, context):
    """Outside battle and text boxes: an R14 answer, or None (then the R13 and older rules answer)."""
    if s.get('battle') or not s['team'] or s.get('text_box'):
        return None
    q = (question or '').lower().replace('é', 'e')
    m, pos = here(s)
    if m in CAVE:
        return cave(A, s, q, context)
    if s.get('r13_pure'):
        return None
    if CATCH_Q.search(q) and 'Boulder' in s['badges'] and 'Cascade' not in s['badges'] and \
            m in {'ROUTE_4', 'MT_MOON_POKECENTER'} | L.TOWNS:
        return catch(A, s, q)
    if m in ('ROUTE_4', 'MT_MOON_POKECENTER'):
        return route4(A, s, q, context)
    if m in ('CERULEAN_CITY', 'CERULEAN_MART', 'CERULEAN_POKECENTER', 'CERULEAN_GYM'):
        if m == 'CERULEAN_POKECENTER' and T.hurt(s) and not T.SHOP_Q.search(q):
            return None
        return cerulean(A, s, q)
    return None
