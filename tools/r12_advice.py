"""R12 advice layer, from the t15-4 / t15-7 game audits.

1. Readiness verdict for any "ready / can I win / should I fight / safe to go" question.
2. One concrete battle action with menu buttons (never a bare "look and ask again").
3. A warning before unbeaten trainers when HP or level is low, with a training spot and the way to heal.
4. A different, more concrete answer when the same answer would repeat a third time with no progress.
5. A blocked-tile check with a detour.  6. Nurse steps inside a Center.  7. Named places ("Route 4 Center").
All fights are estimates (average damage, strongest enemy attack, no critical hits); walks are map-checked only.
Runtime strings are player words: no meta words.
"""
import copy
import re

import r11_maps as M
import r11_advice as L

GRASS = 0x52
CENTER_NAME = {'PEWTER_POKECENTER': 'the Pewter Center', 'MT_MOON_POKECENTER': 'the Route 4 Center by Mt. Moon',
               'CERULEAN_POKECENTER': 'the Cerulean Center', 'VIRIDIAN_POKECENTER': 'the Viridian Center'}
READY_Q = re.compile(r"\b(ready|readiness|strong enough|tough enough|too weak|can i (?:win|beat|defeat|take|handle|pass|"
                     r"survive|fight|face)|should i (?:fight|battle|challenge|take on|face)|safe to|is it safe|"
                     r"without (?:losing|fainting|dying|a blackout)|will i (?:win|lose)|am i strong)\b")
LEADER_Q = re.compile(r"\b(misty|brock|gym|leader|super nerd|nerd|fossil|rockets?|rival)\b")
TRAINER_Q = re.compile(r"\b(trainers?|route|youngster|lass|bug catcher|hiker|forest|fight|battle)\b")
TRAIN_Q = re.compile(r"\b(train|training|grind|grinding|level up|gain levels|more levels|get stronger|exp|experience)\b")
BLOCK_Q = re.compile(r"\b(blocked|blocking|stuck|can ?not (?:move|pass|walk|go|get)|can'?t (?:move|pass|walk|go|get)|"
                     r"won'?t (?:move|let me)|not moving|does ?n[o']t move)\b")
SHOP_Q = re.compile(r"\b(buy|buying|purchase|shop|shopping|mart|stock|prices?)\b")
OPTIONAL_Q = re.compile(r"\b(oddish|nugget|bridge|route[ _]?2[45]|bill|mankey|moon stone|water gun|mega punch|rare candy|"
                        r"hp up|escape rope)\b")
WARN_MAPS = {'PEWTER_CITY', 'PEWTER_POKECENTER', 'PEWTER_MART', 'ROUTE_3', 'ROUTE_4', 'MT_MOON_POKECENTER'}
# Route 3 fights needed on the way east: each one alone blocks every sight-safe walk to Route 4 and to the grass
# (checked by tests/test_r12.py with the map data). The others can be walked around.
ROUTE_ORDER = {'ROUTE_3': ['EVENT_BEAT_ROUTE_3_TRAINER_0', 'EVENT_BEAT_ROUTE_3_TRAINER_1', 'EVENT_BEAT_ROUTE_3_TRAINER_6'],
               'MT_MOON_1F': []}   # 1F -> B1F has a sight-safe walk with no fight (tests/test_r12.py)
LEADS_TO = {'PEWTER_CITY': ('ROUTE_3', (0, 9)), 'PEWTER_POKECENTER': ('ROUTE_3', (0, 9)),
            'PEWTER_MART': ('ROUTE_3', (0, 9)), 'PEWTER_GYM': ('ROUTE_3', (0, 9)),
            'MT_MOON_POKECENTER': ('MT_MOON_1F', (14, 35)), 'ROUTE_4': ('MT_MOON_1F', (14, 35))}
# Grass where a hurt or weak team can train; nearest checked walk wins. Wild levels come from game_facts.json.
SPOTS = [('ROUTE_3', 'the Route 3 grass east of the first trainers', 'Route3'),
         ('ROUTE_2', 'the Route 2 grass just south of Pewter, by the Viridian Forest gate', 'Route2'),
         ('ROUTE_22', 'the Route 22 grass west of Viridian', 'Route22'),
         ('ROUTE_4', 'the Route 4 grass east of Mt. Moon', 'Route4'),
         ('ROUTE_24', 'the Route 24 grass north of Cerulean', 'Route24'),
         ('ROUTE_25', 'the Route 25 grass', 'Route25')]
ALIASES = [(r"route ?4 (?:pok[eé]mon )?(?:center|centre|pokecenter)|(?:mt\.?|mount) ?moon (?:pok[eé]mon )?"
            r"(?:center|centre|pokecenter)|moon (?:center|centre)", 'MT_MOON_POKECENTER'),
           (r"pewter (?:pok[eé]mon )?(?:center|centre|pokecenter)", 'PEWTER_POKECENTER'),
           (r"cerulean (?:pok[eé]mon )?(?:center|centre|pokecenter)", 'CERULEAN_POKECENTER'),
           (r"viridian (?:pok[eé]mon )?(?:center|centre|pokecenter)", 'VIRIDIAN_POKECENTER'),
           (r"cerulean (?:mart|shop)", 'CERULEAN_MART')]
INSIDE = ' Inside: walk up to the nurse counter, face up, press A, then A through the text.'
# Words that must never reach the player (R12 review B2); applied to every rendered answer and note.
SCRUB = [(r'normal-button game tests?', 'real play'), (r'\bgame tests?\b', 'real play'),
         (r'\buntested (guess|advice)\b', 'estimate'), (r'\(untested\)', '(estimate)'),
         (r'\buntested\b', 'not checked in play'), (r'\btested\b', 'checked'), (r'\btests\b', 'checks'),
         (r'\btest\b', 'check'), (r'\bround switch', 'floor switch'), (r'\brounds?\b', 'part'),
         (r'\bcoordinators?\b', 'helper'), (r'\bteacher group\b', 'player'), (r'\bplain group\b', 'player'),
         (r'\bplain\b', 'simple'), (r'\bexperiments?\b', 'trial')]


def scrub(text):
    if not isinstance(text, str):
        return text
    for pattern, word in SCRUB:
        text = re.sub(pattern, lambda m, w=word: w[0].upper() + w[1:] if m.group(0)[0].isupper() else w, text,
                      flags=re.I)
    return text


def scrub_answer(a):
    out = dict(a)
    for k, v in a.items():
        out[k] = [scrub(x) for x in v] if isinstance(v, list) else scrub(v)
    return out


MARGIN = 0.1    # lead HP share left that still counts as a likely win (expected values, no luck)
PAST = re.compile(r"\b(already|went|been|came|was|were|visited|left|not|dont|never|instead|from)\b")
MENU_SPOT = {'FIGHT': 'top-left', 'PKMN': 'top-right', 'ITEM': 'bottom-left', 'RUN': 'bottom-right'}
MENU_XY = {'FIGHT': (9, 14), 'PKMN': (15, 14), 'ITEM': (9, 16), 'RUN': (15, 16)}
DIRS = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}
LEG = re.compile(r"\b(up|down|left|right) (\d+) to \((-?\d+),(-?\d+)\)|jump (up|down|left|right)")


def result(do, why, details=(), **extra):
    return dict(do=do, why=why, details=list(details), **extra)


def here(s):
    return L.here(s)


def lead(s):
    return next((t for t in s['team'] if t['hp'] > 0), None)


def hurt(s):
    first = lead(s)
    return (not first or any(t['hp'] == 0 for t in s['team']) or any(t['status'] != 'ok' for t in s['team'])
            or first['hp'] * 2 < first['max_hp'])


def team_line(s):
    return ', '.join(f"{t['species']} L{t['level']} {t['hp']}/{t['max_hp']} HP"
                     + ('' if t['status'] == 'ok' else ' ' + t['status']) for t in s['team'])


def name(const):
    return CENTER_NAME.get(const, const.replace('_', ' ').title())


# ---------- trainers ahead and fight estimates ----------

def team_key(A, row):
    cls, idx = row['trainer'].split(':')
    return next((k for k in A.TEAMS if k.split(':')[1] == idx and
                 re.sub('[^a-z]', '', k.split(':')[0].lower()) == cls.replace('_', '').lower()), None)


def who(A, row):
    key = team_key(A, row)
    party = ', '.join(f"{p['species']} L{p['level']}" for p in A.TEAMS[key]['party']) if key else 'unknown team'
    return f"the {row['trainer'].split(':')[0].replace('_', ' ').title()} at ({row['x']},{row['y']}) ({party})"


def who_short(row):
    return f"the {row['trainer'].split(':')[0].replace('_', ' ').title()} at ({row['x']},{row['y']})"


def trainer_rows(A, s):
    """(map, unavoidable, avoidable): the next unbeaten trainers on the way. On maps in ROUTE_ORDER only the listed
    fights are unavoidable; elsewhere avoidability is not checked, so the nearest trainers count as the next fights."""
    m, pos = here(s)
    target, origin = m, pos
    if m in LEADS_TO and not (m == 'ROUTE_4' and pos[0] >= 22):
        target, origin = LEADS_TO[m]
    rows = [r for r in M.maps().get(target, {}).get('objects', [])
            if r.get('trainer') and r.get('event') and not M.defeated(s, r['event']) and team_key(A, r)]
    order = ROUTE_ORDER.get(target)
    if order is not None:
        must = [r for e in order for r in rows if r['event'] == e]
        rest = sorted((r for r in rows if r not in must and r['x'] >= origin[0] - 2), key=lambda r: r['x'])
        return target, must, rest
    rows.sort(key=lambda r: abs(r['x'] - origin[0]) + abs(r['y'] - origin[1]))
    return target, rows, []


def route3_clear(s):
    return all(M.defeated(s, e) for e in ROUTE_ORDER['ROUTE_3'])


def mons(A, s, healed=False):
    out = []
    for t in s['team']:
        p = A._party_mon(t, s['badges'])
        if healed:
            p = dict(p, hp=p['max_hp'], status='ok', moves=[dict(mv, pp=None) for mv in p['moves']])
        out.append(p)
    return out


def crit_factor(A, species):
    """Gen 1: a normal move is a critical hit with chance base Speed / 512 and does about double damage."""
    base = A.SPECIES.get(species, {}).get('base', {}).get('spd', 50)
    return 1 + base / 512


def hit(A, move, atk, dfn):
    """Expected damage of one use: average roll x accuracy x hits x critical chance. 0 for moves without damage."""
    m = A.MOVES.get(move)
    if not m or not m.get('power') or m.get('effect') == 'OHKO_EFFECT':
        return 0.0
    d = A.damage(move, atk['level'], atk['stats'], dfn['stats'], atk['types'], dfn['types'], dfn.get('hp'))
    if not d:
        return 0.0
    n = {3: 3, 2: 2}.get(A.hits(move), 1)
    return (d[0] + d[1]) / 2 * n * m['accuracy'] / 100 * crit_factor(A, atk['species'])


def foe_turn(A, foe, me):
    """(expected damage per turn, share of turns you are trapped). Gen 1 trainers on Route 3 (Bug Catcher, Lass:
    move choice 1; Youngster: none) pick each move with equal chance (core.asm SelectEnemyMove, trainer_ai.asm);
    choice 1 only avoids status moves when you already have a status. A Wrap that hits holds you about 2 more turns."""
    moves = [mv if isinstance(mv, str) else mv['move'] for mv in foe['moves']]
    n = max(1, len(moves))
    normal, wrap, extra = 0.0, 0.0, 0.0
    for mv in moves:
        e = hit(A, mv, foe, me)
        normal += e / n
        m = A.MOVES.get(mv, {})
        if m.get('effect') == 'TRAPPING_EFFECT':
            extra += 2 * m['accuracy'] / 100 / n
            wrap = e / (m['accuracy'] / 100)
    q = extra / (1 + extra)
    return (1 - q) * normal + q * wrap, q


def potion_now(hp, max_hp, have, foe_hurts, sure_ko_first):
    """The one Potion rule for forecasts and battle advice: heal when HP is below a third, you have a healing item, the
    foe can still hurt you, and your next hit does not surely knock it out first."""
    return bool(have) and hp * 3 < max_hp and foe_hurts and not sure_ko_first


def expected_fight(A, mine, party, pots=0):
    """One trainer fight with expected damage per turn: your team in party order, the best move with PP, HP and PP
    carried; a Potion (+20 HP, costs your turn) whenever HP is below a third. Returns (win, HP share left, Potions left,
    team). Not modelled: stat drops (String Shot, Leer, Tail Whip, Sand-Attack), poison after the fight."""
    team = copy.deepcopy(mine)
    for t in team:
        t['moves'] = [dict(mv, pp=mv['pp'] if mv.get('pp') is not None else A.MOVES.get(mv['move'], {}).get('pp', 10))
                      for mv in t['moves']]
    i = 0
    for e in party:
        foe = A._foe(e)
        fhp, turns = float(foe['hp']), 0
        while fhp > 0:
            turns += 1
            while i < len(team) and (team[i]['hp'] <= 0 or not any(
                    mv['pp'] > 0 and hit(A, mv['move'], team[i], foe) > 0 for mv in team[i]['moves'])):
                i += 1
            if i >= len(team) or turns > 300:
                return False, 0.0, pots, team
            me = team[i]
            dmg_in, q = foe_turn(A, dict(foe, hp=fhp), me)
            first = me['stats']['spd'] > foe['stats']['spd']
            sure = first and any(mv['pp'] > 0 and (A.move_option(mv['move'], mv['pp'], me, dict(foe, hp=fhp)) or {})
                                 .get('lo', 0) >= fhp for mv in me['moves'])
            if potion_now(me['hp'], me['max_hp'], pots, dmg_in > 0, sure):
                pots -= 1
                me['hp'] = min(me['max_hp'], me['hp'] + 20) - dmg_in
                if me['hp'] <= 0:
                    me['hp'] = 0
                continue
            mv = max((mv for mv in me['moves'] if mv['pp'] > 0),
                     key=lambda mv: hit(A, mv['move'], me, dict(foe, hp=fhp)))
            mv['pp'] -= 1
            out = hit(A, mv['move'], me, dict(foe, hp=fhp)) * (1 - q)
            if me['stats']['spd'] > foe['stats']['spd']:
                fhp -= out
                if fhp > 0:
                    me['hp'] -= dmg_in
            else:
                me['hp'] -= dmg_in
                if me['hp'] > 0:
                    fhp -= out
            if me['hp'] <= 0:
                me['hp'] = 0
    left = sum(max(0, t['hp']) for t in team) / max(1, sum(t['max_hp'] for t in mine))
    return True, left, pots, team


def outcome(A, mine, keys, pots=0):
    """(win, lead HP share left) over these fights in a row, HP, PP and Potions carried, no Center between.
    The lead is your first healthy Pokemon; a win where it faints and a weak backup finishes counts 0."""
    i = next((n for n, t in enumerate(mine) if t['hp'] > 0), 0)
    for key in keys:
        win, _, pots, mine = expected_fight(A, mine, A.TEAMS[key]['party'], pots)
        if not win:
            return False, 0.0
    return True, max(0.0, mine[i]['hp']) / mine[i]['max_hp']


def level_target(A, s, keys, pots=0):
    mine = mons(A, s, healed=True)
    i = next((n for n, t in enumerate(s['team']) if t['hp'] > 0), 0)
    base = mine[i]
    for lv in range(base['level'] + 1, base['level'] + 11):
        trial = mine[:i] + [A._scaled(base, lv)] + mine[i + 1:]
        ok, left = outcome(A, trial, keys, pots)
        if ok and left >= MARGIN:
            return lv
    return None


def potions(A, s):
    return sum(A._bag(s).get(k, 0) for k in A.HEAL)


# ---------- places: Center, grass, named places ----------

def nearest_center(A, s):
    m, _ = here(s)
    if m.endswith('_POKECENTER'):
        return m
    if m in ('ROUTE_3', 'ROUTE_4') and route3_clear(s) and A.walk_to(
            s, lambda mm, p: mm == 'MT_MOON_POKECENTER', max_maps=4, fallback=False):
        return 'MT_MOON_POKECENTER'          # no fight left on the way: heal forward, not back in Pewter
    r = A.walk_to(s, lambda mm, p: mm.endswith('_POKECENTER'), max_maps=6, fallback=False)
    if r:
        return r['target'][0]
    return 'PEWTER_POKECENTER' if m.startswith(('PEWTER', 'ROUTE_3')) else 'CERULEAN_POKECENTER' \
        if m.startswith(('CERULEAN', 'ROUTE_24', 'ROUTE_25')) else 'MT_MOON_POKECENTER'


def legs(text, n=3):
    """The first n walking legs of a walk answer."""
    words = re.findall(r"(?:up|down|left|right) \d+ to \(-?\d+,-?\d+\)(?: \([^)]*\))?|jump \w+ \(over the ledge\) "
                       r"to \(-?\d+,-?\d+\)|\(off the \w+ edge to \w+\)", text)
    return ', '.join(words[:n])


def center_walk(A, s, center=None):
    center = center or nearest_center(A, s)
    if here(s)[0] == center:
        return nurse(A, s)
    a = L.walk(A, s, lambda mm, p: mm == center, name(center))
    if not a['do'].startswith('Stop'):
        a['do'] += ' Inside: walk up to the nurse counter, face up, press A, then A through the text.'
    return a


def nurse(A, s):
    """Inside any Center: the stand-and-talk square below the nurse, with the walk from the current tile."""
    m, pos = here(s)
    nurse_at = next(((x, y) for x, y, sp in A._objects(m)[1] if sp == 'SPRITE_NURSE'), (3, 1))
    spot = (nurse_at[0], nurse_at[1] + 2)
    talk = 'face up, press A, then press A through the text (it heals your team for free).'
    who = f'talk to the nurse behind the counter at ({nurse_at[0]},{nurse_at[1]})'
    if pos == spot:
        return result(f'Heal now: {who}: {talk}', 'The nurse stands behind the counter right above you.',
                      ['Buttons: up a a a (one command), then look; press A until the text ends.'])
    r = A.walk_to(s, lambda mm, p: mm == m and p == spot, max_maps=1)
    walk = ', '.join(A.walk_words(s, r)) if r else f'walk to ({spot[0]},{spot[1]})'
    return result(f'Heal first: {who}. Walk up to the counter: {walk}. Then {talk}',
                  f'The nurse is behind the counter at ({nurse_at[0]},{nurse_at[1]}); you talk to her across it from '
                  f'({spot[0]},{spot[1]}).', ['Your team: ' + team_line(s) + '.'])


def grass_tiles(A, map_):
    if map_ == 'ROUTE_2':
        return A.training_tiles()
    g = A._grid(map_)
    return {p for p, t in g['tile'].items() if t == GRASS} if g else set()


def wild_levels(A, wild):
    mons_ = A.FACTS['wild'].get(wild, {}).get('grass', {}).get('mons', [])
    lv = [x for m in mons_ for x in m['levels']]
    return f'wild L{min(lv)}-{max(lv)}' if lv else 'wild Pokemon'


def training_spot(A, s):
    """(label, levels, route or None, tile): the nearest grass reachable without walking into an unbeaten trainer."""
    m, pos = here(s)
    best = None
    for map_, label, wild in SPOTS:
        tiles = grass_tiles(A, map_)
        if not tiles:
            continue
        if m == map_ and pos in tiles:
            return label, wild_levels(A, wild), None, pos
        r = A.walk_to(s, lambda mm, p, map_=map_, tiles=tiles: mm == map_ and p in tiles, max_maps=4, fallback=False)
        if r and (best is None or r['cost'] < best[2]['cost']):
            best = (label, wild_levels(A, wild), r, r['target'][1])
    return best


def circuit(A, map_, pos):
    tiles = grass_tiles(A, map_)
    g = A._grid(map_)
    pair = next(((d, q) for d, q in A.W.moves(g, pos) if q in tiles and pos in dict(A.W.moves(g, q)).values()), None)
    if not pair:
        return None
    d, q = pair
    back = next(d2 for d2, p2 in A.W.moves(g, q) if p2 == pos)
    return (f'In the grass at ({pos[0]},{pos[1]}): press {d}, then {back}, again and again until a wild Pokemon '
            f'appears. Fight it, check HP after each fight.')


def alias_target(q, s):
    for pattern, const in ALIASES:
        for hit in re.finditer(pattern, q):
            if not PAST.search(' '.join(q[:hit.start()].split()[-4:])) and const != here(s)[0]:
                return const
    return None


def place(A, s, target):
    if target.endswith('_POKECENTER'):
        a = center_walk(A, s, target)
    else:
        a = L.walk(A, s, lambda mm, p: mm == target, name(target))
    door = {'MT_MOON_POKECENTER': ' It is at the east end of Route 3, door at Route 4 (11,5), past the Route 3 trainers.',
            'PEWTER_POKECENTER': ' Its door is at Pewter (13,25).', 'CERULEAN_POKECENTER': ' Its door is at Cerulean (19,17).'}
    if a['do'].startswith('Stop'):
        a = after_way(A, s, None, a)
    a['why'] = f'You asked the way to {name(target)}.{door.get(target, "")} ' + a['why']
    return a


# ---------- 1 + 3: readiness verdict and the warning before trainers ----------

def mart_near(s):
    m = here(s)[0]
    if m.startswith('PEWTER') or m == 'ROUTE_3':
        return 'the Pewter Mart', 'Pewter Mart: city door (23,17); inside stand at (2,5), press left, A, BUY, POTION.'
    if m.startswith('CERULEAN') or m in ('ROUTE_24', 'ROUTE_25'):
        return 'the Cerulean Mart', 'Cerulean Mart: city door (25,25); talk to the clerk across the counter, BUY, POTION.'
    return None, None


def readiness(A, s, rows=None):
    """One verdict, in this order: "Ready: go" / "Not ready: heal at <Center> first" / "... buy N Potions, then
    fight" / "... train to about L<N>" (only when even healed with Potions is a likely loss)."""
    if not lead(s):
        return result('Not ready: your team has fainted. Press A through the text, then heal at the Center.',
                      'You black out to your last Center; heal and check again.', verdict='heal')
    if rows is None:
        target, rows, optional = trainer_rows(A, s)
        if not rows:
            return clear_way(A, s, target, optional)
    rows = rows[:2]
    keys = [team_key(A, r) for r in rows]
    if not rows or not keys[0]:
        return None
    first, k1 = rows[0], keys[0]
    have, money = potions(A, s), s.get('money', 0)
    mart, mart_line = mart_near(s)
    can_buy = max(0, min(4 - have, money // 300)) if mart else 0
    ok = lambda r: r[0] and r[1] >= MARGIN
    now = outcome(A, mons(A, s), [k1], have)
    healed = outcome(A, mons(A, s, True), [k1], have)
    need = next((k for k in range(0, can_buy + 1) if ok(outcome(A, mons(A, s, True), [k1], have + k))), None)
    center = nearest_center(A, s)
    is_hurt = hurt(s)
    fight = who_short(first)
    lines = []
    for r, k in zip(rows, keys):
        a, b = outcome(A, mons(A, s), [k], have), outcome(A, mons(A, s, True), [k], have)
        lines.append(f"{who(A, r)[0].upper()}{who(A, r)[1:]}: {'likely win' if ok(a) else 'likely loss'} now, "
                     f"{'likely win' if ok(b) else 'likely loss'} after healing"
                     + (f' (with your {have} Potions)' if have else '') + '.')
    details = []
    heal_go = center_walk(A, s, center)['do'] if is_hurt else ''
    pots_text = lambda n: (f'buy {n} Potions at {mart} (300 each; you have {money}), then fight and use a Potion when '
                           'HP falls below a third')
    if ok(now) and not is_hurt:
        verdict, do = 'ready', f'Ready: go. Next is {fight}: a likely win (estimate).'
        if have < 2 and can_buy >= 2 and now[1] < .4:
            details.append(f'Safer: {pots_text(min(3, can_buy))}.')
        way = L.answer(A, dict(s), None) if here(s)[0] in WARN_MAPS else None
        if way and not way['do'].startswith('Stop here'):
            details.append('Way on: ' + way['do'])
        elif way:
            details.append('Step into the trainer to start the fight; ask during the battle for each move.')
    elif ok(healed):
        verdict = 'heal'
        if have < 2 and can_buy >= 2 and healed[1] < .4:      # a close fight: Potions are cheap insurance
            do = (f'Not ready: heal at {name(center)} first, then buy {min(3, can_buy)} Potions at {mart} (300 each; '
                  f'you have {money}). Then {fight} is a likely win (estimate); use a Potion when HP falls below a third.')
        else:
            do = f'Not ready: heal at {name(center)} first. Then {fight} is a likely win (estimate).'
        go = center_walk(A, s, center)['do']
        do += (f' Walk: {legs(go)}.' if legs(go) else '') + INSIDE
        details.append('Way to heal (the nurse restores HP and PP): ' + go)
    elif need is not None:
        verdict = 'potions'
        n = min(can_buy, max(need, 3))
        do = 'Not ready: ' + (f'heal at {name(center)} first, then ' if is_hurt else '') + pots_text(n) + \
             f'. Then {fight} is a likely win (estimate).'
        if is_hurt:
            do += (f' Walk: {legs(heal_go)}.' if legs(heal_go) else '') + INSIDE
            details.append('Way to heal (the nurse restores HP and PP): ' + heal_go)
        elif mart == 'the Pewter Mart' and here(s)[0] != 'PEWTER_MART':
            shop = L.walk(A, s, lambda mm, p: mm == 'PEWTER_MART', 'the Pewter Mart')['do']
            do += f' Walk: {legs(shop)}.' if legs(shop) else ''
            details.append('Way to the Mart: ' + shop)
    else:
        verdict = 'train'
        all_pots = have + can_buy
        target = level_target(A, s, [k1], all_pots)
        spot = training_spot(A, s)
        train = (f'train to about L{target} (estimate)' if target else 'train several levels') + \
                (f' in {spot[0]} ({spot[1]})' if spot else ' in the nearest grass')
        do = 'Not ready: ' + (f'heal at {name(center)} first, then {train}' if is_hurt else train) + \
             (f', and {pots_text(can_buy)}.' if can_buy else '.')
        if is_hurt:
            details.append('Way to heal (the nurse restores HP and PP): ' + heal_go)
            do += (f' Walk: {legs(heal_go)}.' if legs(heal_go) else '') + INSIDE
        elif spot and spot[2]:
            do += f' Walk: {", ".join(A.walk_words(s, spot[2])[:3])}.'
        if spot:
            label, levels, route, tile = spot
            if route:
                details.append('Way to the grass: ' + ', '.join(A.walk_words(s, route)) + '. There, ask again.')
            loop = circuit(A, route['target'][0] if route else here(s)[0], tile)
            if loop:
                details.append(loop)
            details.append(f'Heal at {name(center)} when HP is under half. Ask "Am I ready?" again after each level.')
    if verdict in ('potions', 'train') and can_buy or 'Potions at' in do:
        details.append(mart_line)
    plan = fight_plan(A, s, k1)
    if plan:
        details.insert(0, plan)
    why = (f'Your team: {team_line(s)}. ' + ' '.join(lines) + ' Estimate: average damage, the trainer picks its moves '
           'at random like the game, normal accuracy; luck can still go either way.')
    return result(do, why, details, verdict=verdict)


def clear_way(A, s, target, optional):
    """No unavoidable fight left on the way: go on (heal forward if hurt); avoidable trainers are walked around."""
    if target not in ROUTE_ORDER:
        return None
    around = ('The walk goes around ' + ' and '.join(who_short(r) for r in optional[:2]) + '.') if optional else ''
    lines = [f"If you choose to fight {who(A, r)}: "
             f"{'likely win' if (lambda o: o[0] and o[1] >= MARGIN)(outcome(A, mons(A, s), [team_key(A, r)], potions(A, s))) else 'likely loss'}."
             for r in optional[:2]]
    if hurt(s):
        center = nearest_center(A, s)
        go = center_walk(A, s, center)['do']
        do = (f'No fight is needed on the way, but heal first at {name(center)}.' + (f' Walk: {legs(go)}.' if legs(go) else '')
              + INSIDE)
        return result(do, f'Your team: {team_line(s)}. ' + around, ['Way to heal (the nurse restores HP and PP): ' + go]
                      + lines, verdict='heal')
    way = L.answer(A, dict(s), None)
    details = ([f'Way on: {way["do"]}'] if way and not way['do'].startswith('Stop') else []) + lines
    return result('Ready: go. No trainer fight is needed on the way. ' + around, f'Your team: {team_line(s)}.', details,
                  verdict='ready')


def avoid_note(A, s):
    """For route answers: unbeaten trainers that the shown walk goes around."""
    _, must, optional = trainer_rows(A, s) if here(s)[0] in WARN_MAPS else (None, [], [])
    if not optional:
        return None
    return ('Avoidable: the walk shown goes around ' + ' and '.join(who_short(r) for r in optional[:2])
            + '; no fight needed.')


def fight_plan(A, s, key):
    """Which move your lead should use against the trainer's first Pokemon."""
    me = next((p for p in mons(A, s) if p['hp'] > 0), None)
    foe = A._foe(A.TEAMS[key]['party'][0])
    opts = [o for o in (A.move_option(mv['move'], mv['pp'] if mv['pp'] is not None else 10, me, foe)
                        for mv in me['moves']) if o and o['expect'] > 0] if me else []
    if not opts:
        return None
    o = max(opts, key=lambda o: o['expect'])
    return (f"Fight plan: lead {me['species']} with {o['move']} ({o['lo']}-{o['hi']} damage to {foe['species']}'s "
            f"{foe['hp']} HP); in battle, ask for each move.")


def wants_readiness(s, q):
    if not READY_Q.search(q) or LEADER_Q.search(q):
        return False
    if (s['story']['next'] or {}).get('id') == 'mt_moon':
        return True
    return bool(TRAINER_Q.search(q)) and 'Boulder' in s['badges'] or bool(re.search(r'\b(trainers?|route)\b', q))


def training(A, s):
    _, must, optional = trainer_rows(A, s)
    rows = must or optional
    key = team_key(A, rows[0]) if rows else None
    target = level_target(A, s, [key], potions(A, s)) if key else None
    spot = training_spot(A, s)
    if not spot:
        return None
    label, levels, route, tile = spot
    goal = f' until about L{target} (estimate)' if target else ''
    walk = ', '.join(A.walk_words(s, route)[:4]) if route else 'you are in the grass now'
    do = f'Train in {label} ({levels}){goal}: {walk}.'
    if hurt(s):
        do = f'Heal at {name(nearest_center(A, s))} first. Then train in {label} ({levels}){goal}.'
    verdict = readiness(A, s) if key else None
    if verdict and verdict['verdict'] != 'train':
        # Training costs many commands; the verdict says healing / Potions are enough for the next fight.
        first = verdict['do'].split(' Walk: ')[0].replace('Not ready: ', '').replace('Ready: go. ', '')
        do = (f'You do not need to train first: {first[0].lower()}{first[1:]} For extra levels anyway: {label} '
              f'({levels}){goal}.')
    details = []
    if hurt(s):
        details.append('Way to heal: ' + center_walk(A, s)['do'])
    if route and len(A.walk_words(s, route)) > 4:
        details.append('Whole way to the grass: ' + ', '.join(A.walk_words(s, route)) + '.')
    loop = circuit(A, route['target'][0] if route else here(s)[0], tile)
    if loop:
        details.append(loop)
    if rows and key:
        details.append(f'Then ask "Am I ready?" for {who(A, rows[0])}.')
    return result(do, 'This grass is the nearest one you can reach without walking into an unbeaten trainer. '
                      'Heal when HP is under half.', details)


# ---------- 5: blocked ----------

def blocked(A, s, q, context):
    m, pos = here(s)
    g = A._grid(m)
    for row in M.maps().get(m, {}).get('objects', []):
        if row.get('event') and not M.defeated(s, row['event']) and pos in M.sight(dict(s, teacher_events=dict(
                s.get('teacher_events', {}), **{r['event']: True for r in M.maps()[m]['objects']
                                                if r.get('event') and r is not row})), m):
            return result(f"A trainer has seen you: {who(A, row)}. The battle is starting: press A to read on; "
                          "you cannot walk away now.",
                          'Trainers stop you when you step into their line of sight. Ask during the battle for each move.',
                          [readiness(A, s, [row])['why']] if readiness(A, s, [row]) else [])
    word = re.search(r'\b(north|south|east|west|up|down|left|right)\b', q)
    direction = {'north': 'up', 'south': 'down', 'east': 'right', 'west': 'left'}.get(word[1], word[1]) if word else None
    base = None
    if not direction:
        base = A._answer_core(s, None, context=None)
        leg = LEG.search(base['do'])
        direction = (leg[1] or leg[5]) if leg else None
    if not direction:
        return result('Press A once (a text or battle may be starting), then look at your tile and ask the way again.',
                      'I could not tell which way you want to walk.', [])
    dx, dy = DIRS[direction]
    tile = (pos[0] + dx, pos[1] + dy)
    live = {(r['x'], r['y']) for r in s.get('teacher_objects', {}).get(m, []) if not r.get('hidden')}
    people = (set(g['people']) - set(g['balls'])) | live if g else live
    t = g['tile'].get(tile) if g else None
    ledge_dirs = {d for d, a, b in (g or {}).get('ledges', []) if t == b}
    confirmed = True
    if not g or tile not in g['tile']:
        why = f'({tile[0]},{tile[1]}) is past the map edge; there is no way {direction} here.'
    elif tile in people:
        why = f'A person stands on ({tile[0]},{tile[1]}). People do not step aside; walk around them.'
    elif ledge_dirs and direction not in ledge_dirs:
        why = (f'({tile[0]},{tile[1]}) is a ledge: you can only jump it going {"/".join(sorted(ledge_dirs))}, '
               f'never back {direction}.')
    elif t not in g['walk']:
        why = f'({tile[0]},{tile[1]}) is a wall, tree, sign or water tile: you cannot walk there.'
    else:
        confirmed = False
    if not confirmed:
        # Not confirmed by the map: keep the tile open. First one observed try; on a second report a short-lived
        # block (6 presses, the existing walk_occupancy timer), never a lasting ban. Doors are never blocked.
        key = [m, list(tile)]
        again = context is not None and context.get('r12_blocked') == key
        if context is not None:
            context['r12_blocked'] = key
        door = any(w[:2] == tile for w in A._warps(m))
        if not again or door:
            route = A._answer_core(s, None, context=None)
            what = f'the door at ({tile[0]},{tile[1]})' if door else f'({tile[0]},{tile[1]})'
            return result(f'You are at ({pos[0]},{pos[1]}). Nothing on the map blocks {what}. Try once: press A '
                          f'(a text may be open), then press {direction} once and look.',
                          'A walking person or an open text can stop you for a moment; the way stays the same.',
                          ['Way: ' + route['do']])
        if context is not None:
            context['walk_occupancy'] = (list(context.get('walk_occupancy', []))
                                         + [dict(map=m, tile=list(tile), ttl=6)])[-8:]
        why = (f'You still did not move: ({tile[0]},{tile[1]}) counts as blocked for your next few steps only '
               '(a walking person may stand there).')
    blocked_state = dict(s, teacher_blocked=dict(s.get('teacher_blocked', {})))
    blocked_state['teacher_blocked'][m] = list(blocked_state['teacher_blocked'].get(m, [])) + [tile]
    detour = A._answer_core(blocked_state, None, context=None)
    return result(f'You are at ({pos[0]},{pos[1]}); going {direction} is blocked. Detour: {detour["do"]}', why,
                  detour['details'][:2])


# ---------- 2: battle ----------

def battle_plan(A, s, advice):
    """The shared Potion rule (potion_now), then: wild battle, low HP, no Potion -> run (unless one sure hit wins)."""
    b = s['battle']
    me, foe = b.get('yours'), b.get('enemy')
    if not me or not foe or not me['hp'] or foe['hp'] == 0:
        return advice
    bag = A._bag(s)
    items = [i for i in sorted(A.HEAL, key=A.HEAL.get) if bag.get(i)]
    opts = [o for o in (A.move_option(mv['move'], mv['pp'], me, foe) for mv in me['moves'] if mv['pp'] > 0)
            if o and o['expect'] > 0]
    sure = me['stats']['spd'] > foe['stats']['spd'] and any(o['lo'] >= foe['hp'] for o in opts)
    hurts = 0 < A.best_threat(foe, me)[2] < A.LETHAL     # no Potion against a working one-hit KO move
    heal = re.match(r'Use (\w+) on (\w+)\.?$', advice['do'])
    wants = potion_now(me['hp'], me['max_hp'], len(items), hurts, sure)
    if heal and heal[1] in A.HEAL and heal[2] == me['species'] and not wants and opts:
        o = max(opts, key=lambda o: o['expect'])
        advice = dict(advice, do=f"Use {o['move']}{A._slot(me, o['move'])}.",
                      why=f"{me['species']} has {me['hp']}/{me['max_hp']} HP, above a third: attack and keep the Potion "
                          f"for later ({o['lo']}-{o['hi']} damage to {foe['species']}'s {foe['hp']} HP).")
    elif wants and advice['do'].startswith('Use ') and ' on ' not in advice['do'] and not advice['do'].startswith('Use ' + items[0]):
        advice = dict(advice, do=f"Use {items[0]} on {me['species']}.",
                      why=f"{me['species']} has {me['hp']}/{me['max_hp']} HP, below a third, and {foe['species']} can "
                          f"still hurt it: heal now (+{A.HEAL[items[0]]} HP).")
    if b.get('kind') != 'wild':
        return advice
    balls = any(A._bag(s).get(i) for i in ('POKE_BALL', 'GREAT_BALL', 'ULTRA_BALL'))
    if not advice['do'].startswith('Use ') or ' on ' in advice['do'] or balls and A.catch_reason(s, foe['species']):
        return advice
    if me['hp'] * 3 > me['max_hp'] or potions(A, s) or 'knocks out' in advice['why'] and 'for sure (' in advice['why']:
        return advice
    return dict(advice, do='Run (RUN is the bottom-right choice of the battle menu).',
                why=f"{me['species']} has only {me['hp']}/{me['max_hp']} HP and you have no Potion. Running keeps it "
                    'safe; if it fails, choose RUN again.')


def text_open(ui):
    rows = ui.get('rows') or []
    words = ' '.join(rows[12:]).upper()
    return (ui.get('phase') == 'unknown' and not ui.get('cursor_count') and not ui.get('submitted')
            and bool(re.search(r'[A-Z]{2}', words)) and not all(w in words for w in ('FIGHT', 'RUN')))


def menu_how(s, plan):
    """How to do the plan from the FIGHT / PKMN / ITEM / RUN menu, in words and buttons."""
    me = (s['battle'] or {}).get('yours') or {}
    names = [mv['move'] for mv in me.get('moves', [])]
    ui = s.get('teacher_ui') or {}
    use = re.match(r'Use (\w+)', plan)
    if use and use[1] in names and ' on ' not in plan:
        i = names.index(use[1])
        start = ui.get('move_index')
        pick = (f"the arrow starts on {names[start]}: press {'down' if i > start else 'up'} {abs(i - start)}, then A"
                if isinstance(start, int) and start < len(names) and start != i else
                'the arrow is already on it: press A' if start == i else
                f'move the arrow to {use[1]} (move {i + 1} of {len(names)}) with up/down, then press A')
        return 'FIGHT', f'FIGHT is top-left: press A on FIGHT, then {pick}', f'pick {use[1]}: {pick}'
    item = re.match(r'(?:Use (\w+) on (\w+)|Throw a (\w+))', plan)
    if item:
        what, target = item[1] or item[3], item[2]
        tail = f', then pick {target} and press A' if target else ''
        return ('ITEM', f'ITEM is bottom-left: press A on ITEM, pick {what} with up/down, press A{tail}',
                f'pick {what} with up/down, press A{tail}')
    sw = re.search(r'Switch to (\w+)|next Pok[eé]mon: (\w+)', plan)
    if sw:
        return ('PKMN', f'PKMN is top-right: press A on PKMN, pick {sw[1] or sw[2]} with up/down, press A, then SWITCH, A',
                f'pick {sw[1] or sw[2]} with up/down, press A, then SWITCH, A')
    if plan.startswith('Run'):
        return 'RUN', 'RUN is bottom-right: move the arrow there and press A', ''
    return None, None, None


def battle_buttons(s, plan, choice):
    """Exact buttons from a visible FIGHT / PKMN / ITEM / RUN cursor, when every cursor is known."""
    ui = s.get('teacher_ui') or {}
    if ui.get('phase') != 'commands' or choice not in ('FIGHT', 'RUN') or not ui.get('cursor'):
        return None
    (x, y), (tx, ty) = ui['cursor'], MENU_XY[choice]
    seq = (['right' if tx > x else 'left'] if x != tx else []) + (['down' if ty > y else 'up'] if y != ty else []) + ['a']
    if choice == 'FIGHT':
        names = [mv['move'] for mv in s['battle']['yours']['moves']]
        use = re.match(r'Use (\w+)', plan)
        start = ui.get('move_index')
        if not use or use[1] not in names or not isinstance(start, int) or start >= len(names):
            return None
        d = names.index(use[1]) - start
        seq += ['down' if d > 0 else 'up'] * abs(d) + ['a']
    return ' '.join(seq)


def battle_answer(A, s, advice, step):
    """Turn the menu step into one concrete action; never a bare "look and ask again"."""
    b = s['battle']
    me, foe = b.get('yours'), b.get('enemy')
    ui = s.get('teacher_ui') or {}
    plan = re.sub(r' \(FIGHT, then move \d+ of \d+ in the list\)', '', advice['do']).rstrip('.')
    choice, how, after = menu_how(s, advice['do'])
    then = f'{plan}: {how}.' if how else plan + '.'
    do = step['do']
    rows_text = ' '.join(r.strip() for r in (ui.get('rows') or [])[12:] if r.strip())
    keys = battle_buttons(s, advice['do'], choice) if me and foe else None
    skip_list = bool(me and foe) and (me.get('status') in ('asleep', 'frozen') or 'trapping' in foe.get('flags', []))
    pass_turn = bool(me and foe) and choice in (None, 'FIGHT') and (skip_list or re.match(
        r'(Pick any move|Pick your best move|Nothing saves|Look and ask with the current battle text)', advice['do']))
    if pass_turn:
        # core.asm MainInBattleLoop: asleep, frozen or wrapped -> FIGHT ends the turn, no move list opens.
        tail = ('press A on FIGHT to pass the turn (no move list opens while you are asleep, frozen or wrapped)'
                if skip_list else 'press A on FIGHT, then A on any move (attacks miss this turn)')
        lead_in = 'You cannot attack this turn' if skip_list else plan
        if ui.get('phase') == 'commands' and ui.get('cursor'):
            (x, y), (tx, ty) = ui['cursor'], MENU_XY['FIGHT']
            path = (['left'] if x != tx else []) + (['up'] if y != ty else [])
            press = (' then '.join(f'{d} once' for d in path) + ', then ') if path else ''
            buttons = ' '.join(path + ['a'] + ([] if skip_list else ['a']))
            do = (f'{lead_in}: FIGHT is top-left: {"press " + press if press else ""}{tail}. '
                  f'Press: {buttons} (one command), then press A through the text.')
        elif text_open(ui):
            do = f'Text is showing: press A to continue. Then {lead_in[0].lower()}{lead_in[1:]}: FIGHT is top-left: {tail}.'
        else:
            do = f'{lead_in}: on FIGHT / PKMN / ITEM / RUN, FIGHT is top-left: {tail}.'
    elif not me or not foe:
        do = ('The battle is starting: press A to read on. When FIGHT / PKMN / ITEM / RUN shows, FIGHT is top-left: '
              'press A on it and pick your strongest attack.')
    elif step['do'] == advice['do'] or not ui:
        do = advice['do']                       # no screen data (command line): the plan, with How below
    elif ui.get('phase') == 'commands' and choice:
        (x, y), (tx, ty) = ui['cursor'], MENU_XY[choice]
        moves_ = ' and '.join(f'{d} once' for d, n in ((('right' if tx > x else 'left'), x != tx),
                                                     (('down' if ty > y else 'up'), y != ty)) if n)
        verb = 'select' if choice == 'RUN' else 'open'
        do = (f'Press A once to {verb} {choice}' if not moves_ else f'Press {moves_} toward {choice}, then A to {verb} it')
        do += (f', then {after}.' if after else '.') + (f' Buttons: {keys} (one command), then press A through the text.'
                                                        if keys else '')
    elif 'ask again' in do and 'Look at the screen' not in do:
        if ui.get('phase') == 'moves' and choice == 'FIGHT' and 'toward' in do:
            names = [mv['move'] for mv in me['moves']]
            wanted = names.index(re.match(r'Use (\w+)', plan)[1])
            n, d = abs(wanted - ui['cursor']), 'down' if wanted > ui['cursor'] else 'up'
            do = f'Press: {" ".join([d] * n)} a (one command): that picks {names[wanted]}.'
        elif ui.get('phase') == 'moves':
            do = do.split(';')[0] + '.'
        elif 'advance the battle text' in do:
            do = f'Press A once to advance the battle text. Then: {then}'
        else:
            do = do.split(';')[0] + f'; then {then}'
    elif 'Look at the screen' in do:
        if text_open(ui):
            do = f'Text is showing: press A to continue. Then: {then}'
        elif ui.get('cursor_count') == 1 and re.search(r'\bNO\b', rows_text):   # the arrow may cover YES
            keep = f" and keep {me['species']} in" if re.search(r'change', rows_text, re.I) else ''
            do = f'A YES/NO choice is showing ("{rows_text[:60]}"). Press B to answer NO{keep}. Then: {then}'
        elif all(w in rows_text.upper() for w in ('FIGHT', 'RUN')):
            do = then                                     # the battle menu itself: B does nothing there
        else:
            do = (f'If a list or sub-menu is open, press B once to go back to FIGHT / PKMN / ITEM / RUN. Then: {then}')
    details = list(step['details'])
    if how and (step['do'] == advice['do'] or not ui):
        details.insert(0, 'How: ' + how + '.')
    if me and foe:
        now = (f"Now: {me['species']} {me['hp']}/{me['max_hp']} HP vs {foe['species']} L{foe['level']} "
               f"{foe['hp']}/{foe['max_hp']} HP.")
        details.insert(1 if details and details[0].startswith('Battle plan') else 0, now)
    return dict(step, do=do, details=details)


# ---------- 4: repeated answers ----------

def presses(do, limit=20):
    """The first walking legs of an answer as play.py buttons (max 20 presses)."""
    out, n = [], 0
    for leg in LEG.finditer(do):
        d, k = (leg[1], int(leg[2])) if leg[1] else (leg[5], 1)
        k = min(k, limit - n)
        if k <= 0:
            break
        out.append(d if k == 1 else f'{d}*{k}')
        n += k
    return ' '.join(out)


def signature(s):
    b = s.get('battle') or {}
    return [s['place']['map'], s['place']['x'], s['place']['y'], [t['hp'] for t in s['team']],
            sorted(s['story']['done']), bool(s.get('text_box')), ((b.get('enemy') or {}).get('hp'))]


def alternative(A, s, a):
    do = a['do']
    if s.get('battle'):
        return dict(a, do='Nothing changed since your last two asks. ' + do,
                    details=['Press the buttons in one command, then look at the result.'] + a['details'])
    step = re.match(r'Ready: step (up|down|left|right)', do)
    if step:
        return dict(a, do=f'Same answer three times without moving: press exactly {step[1]} in one command to start '
                          'the fight, then press A through the text and ask for each move.', details=[do] + a['details'])
    way = next((d for d in [do] + a['details'] if LEG.search(d) and 'Before:' not in d), None)
    if way and not s.get('text_box'):
        goal = re.match(r'(Way to [^:]+|Next toward [^:]+|To get to [^:]+)', way.split('Detour: ')[-1])
        return dict(a, do=f'Same answer three times without moving: press exactly {presses(way)} in one command, then '
                          'look.' + (f' ({goal[1]}.)' if goal else '') +
                          (' Inside: walk up to the nurse counter, face up, press A, then A through the text.'
                           if 'Inside:' in way else '') + ' If you still do not move, ask "I am blocked at x,y".',
                    details=[do] + a['details'])
    alt = center_walk(A, s) if hurt(s) else None
    ready = readiness(A, s) if not alt else None
    if ready and ready['verdict'] != 'ready':
        alt = ready
    if alt:
        b2 = presses(alt['do'])
        return dict(alt, do='Something else now: ' + alt['do'] + (f' Buttons: {b2}.' if b2 else ''),
                    details=['Before: ' + do] + alt['details'])
    if s.get('text_box'):
        return dict(a, do='Press A once now (one press), then look at the new text.', details=[do] + a['details'])
    return dict(a, do='Same answer three times: do it now, step by step: ' + do, details=a['details'])


def repeat_guard(A, s, question, context, a):
    if context is None or not question:
        return a
    sig = signature(s)
    hist = list(context.get('r12_repeat', []))
    same = len(hist) >= 2 and all(h['do'] == a['do'] and h['sig'] == sig for h in hist[-2:])
    context['r12_repeat'] = (hist + [dict(do=a['do'], sig=sig)])[-3:]
    return alternative(A, s, a) if same else a


# ---------- the hooks ----------

def answer(A, s, question, context):
    """Outside battle and text boxes: an R12 answer, or None (then the older rules answer)."""
    if s.get('battle') or not s['team']:
        return None
    q = (question or '').lower().replace('é', 'e')
    m, pos = here(s)
    post = 'Boulder' in s['badges']
    if q and BLOCK_Q.search(q) and (post or (A.story_step(s) or ('brock',))[0] == 'brock'):
        return blocked(A, s, q, context)
    if m.endswith('_POKECENTER') and (any(t['hp'] < t['max_hp'] or t['status'] != 'ok' for t in s['team'])
                                      and not SHOP_Q.search(q)):
        return nurse(A, s)
    target = alias_target(q, s) if q else None
    if target and not (SHOP_Q.search(q) and not target.endswith('MART')):
        return place(A, s, target)
    if q and wants_readiness(s, q) and m not in L.CAVE | L.TOWNS - {'ROUTE_24', 'ROUTE_25'}:
        r = readiness(A, s)
        if r:
            return r
    if q and post and TRAIN_Q.search(q) and not OPTIONAL_Q.search(q) and m not in L.TOWNS and not READY_Q.search(q):
        r = training(A, s)
        if r:
            return r
    if post and (s['story']['next'] or {}).get('id') == 'mt_moon' and m in WARN_MAPS and not SHOP_Q.search(q) \
            and not OPTIONAL_Q.search(q) and not LEADER_Q.search(q) and not (m == 'ROUTE_4' and pos[0] >= 22):
        r = readiness(A, s)
        if r and r['verdict'] != 'ready':
            way = L.answer(A, s, question)
            if way and not way['do'].startswith('Stop') and 'POKECENTER' not in way['do']:
                r['details'].append('If you go on anyway: ' + way['do'])
            return r
    return None


def after_way(A, s, question, a):
    """Older route answers: a verdict instead of a bare "Stop here", and nurse steps after a Center walk."""
    m, pos = here(s)
    if a['do'].startswith('Stop here'):
        side = re.match(r'Stop here: (\w+)', a['do'])[1]
        dx, dy = DIRS.get(side, (0, 0))
        tile = (pos[0] + dx, pos[1] + dy)
        rows = [r for r in M.maps().get(m, {}).get('objects', []) if r.get('event') and not M.defeated(s, r['event'])
                and tile in M.sight(dict(s, teacher_events=dict(s.get('teacher_events', {}), **{
                    o['event']: True for o in M.maps()[m]['objects'] if o.get('event') and o is not r})), m)]
        r = readiness(A, s, rows) if rows and team_key(A, rows[0]) else None
        if r:
            if r['verdict'] == 'ready':
                r['do'] = f'Ready: step {side} to start the fight with {who(A, rows[0])}; a likely win (estimate).'
            else:
                r['do'] = f'Do not step {side}: that starts the fight with {who(A, rows[0])}. ' + r['do']
            return r
    if a['do'].startswith('Next toward') and (note := avoid_note(A, s)):
        a = dict(a, details=list(a['details']) + [note])
    if re.search(r'\(into \w+_POKECENTER\)', a['do']) and 'nurse counter' not in a['do']:
        a = dict(a, do=a['do'] + ' Inside: walk up to the nurse counter, face up, press A, then A through the text.')
    return a


def text_extra(A, s, question, a):
    """A readiness question while a text box is open: read on first, then the verdict."""
    q = (question or '').lower()
    if not q or not (wants_readiness(s, q) or re.search(r'\bwithout losing\b', q)):
        return a
    m, pos = here(s)
    seen = [r for r in M.maps().get(m, {}).get('objects', []) if r.get('event') and not M.defeated(s, r['event'])
            and pos in M.sight(dict(s, teacher_events=dict(s.get('teacher_events', {}), **{
                o['event']: True for o in M.maps()[m]['objects'] if o.get('event') and o is not r})), m)]
    r = readiness(A, dict(s, text_box=False), seen or None)
    if not r:
        return a
    if seen:
        return dict(r, do=f'{who(A, seen[0])[0].upper()}{who(A, seen[0])[1:]} has seen you: the fight cannot be '
                          f'avoided now. Press A to read on. In the battle, ask for each move; '
                          + ('it is a likely win (estimate).' if r['verdict'] == 'ready' else
                             'it is a likely loss (estimate): use Potions if you have them.'))
    return dict(r, do='Press A to read on first. ' + r['do'])
