"""R15 replay repairs. Offline rules; the R14 fight model and map walker stay unchanged."""
import re

import r11_advice as L
import r11_maps as M
import r13_advice as T
import r14_advice as X

MARTS = {'PEWTER_MART', 'CERULEAN_MART'}
# reference/pokered/data/items/marts.asm, in list order.
STOCK = {m: ['POKE BALL', 'POTION', third, 'ANTIDOTE', 'BURN HEAL', 'AWAKENING', 'PARLYZ HEAL']
         for m, third in [('PEWTER_MART', 'ESCAPE ROPE'), ('CERULEAN_MART', 'REPEL')]}
ITEMS = set().union(*map(set, STOCK.values()))
HEAL = re.compile(r'\b(heal|healing|hurt|low hp|enough hp|am i ok|am i okay)\b', re.I)
CENTER = r'(?:pokemon\s+)?(?:pokecenter|center|centre)'


def result(do, why, details=(), **extra):
    return dict(do=do, why=why, details=list(details), **extra)


def routing_question(s, question):
    """A previous Center visit is context, not a destination. Keep explicit directions to a Center."""
    if not question or s.get('battle') or s.get('text_box'):
        return question
    q = question
    # A movement request at the end wins over a place named in the history before it.
    requests = list(re.finditer(r'(?i)\b(?:where (?:is|are)|how do i (?:get|reach)|give me (?:the )?'
                                r'(?:route|way)|(?:route|way|directions) to)\b', q))
    if requests and re.search(r'(?i)\b(healthy|healed|visited|standing|inside|healing done)\b', q[:requests[-1].start()]):
        q = q[requests[-1].start():]
    # Whole words: healthy/healed never match the old unbounded "heal" rule.
    q = re.sub(r'(?i)\b(?:healthy|healed)\b|\bhealing done\b', 'at full HP', q)
    return q


def buy_count(A, s):
    return min(max(0, 3 - A._bag(s).get('POTION', 0)), max(0, s.get('money', 0)) // 300)


def buy_plan(A, s):
    n = buy_count(A, s)
    if not n:
        return ('You already have at least 3 Potions; press B to leave the shop menu.'
                if A._bag(s).get('POTION', 0) >= 3 else
                'You cannot afford a Potion (300); press B to leave the menu and use the Center for free healing.')
    return f'Buy {n} Potion{"s" if n != 1 else ""} ({n * 300}) to carry 3 if you can afford them.'


def select(rows, item, q=''):
    """Known cursor: count item rows. The harness strips arrows: give a safe named anchor then exact presses."""
    names = ['POKE BALL', 'POTION', 'ESCAPE ROPE', 'REPEL', 'ANTIDOTE', 'BURN HEAL', 'AWAKENING', 'PARLYZ HEAL', 'CANCEL']
    entries = [(row, next((n for n in names if n in row.upper().replace('É', 'E')), None)) for row in rows]
    entries = [(row, n) for row, n in entries if n]
    cursor = next((i for i, (row, _) in enumerate(entries) if re.search(r'[▶►▷>]', row)), None)
    if cursor is None:
        cursor = next((i for i, (_, n) in enumerate(entries)
                       if re.search(r'(?:arrow|cursor) (?:is )?on (?:the )?' + re.escape(n), q, re.I)), None)
    target = next((i for i, (_, n) in enumerate(entries) if n == item), None)
    if cursor is not None and target is not None:
        delta = target - cursor
        return (f'Press {"down" if delta > 0 else "up"} {abs(delta)} to {item}, then press A' if delta else
                f'The arrow is on {item}: press A')
    if item == 'POTION':
        return ('Move the arrow to POTION before A: from POKE BALL press down 1; from ESCAPE ROPE or REPEL press up 1; '
                'from any other row move to POKE BALL at the top, then down 1. Press A on POTION')
    return f'Move the arrow to {item}, then press A on {item}'


def quantity(n, current=1):
    delta = n - current
    return f'press {"up" if delta > 0 else "down"} {abs(delta)} to set {n}' if delta else f'keep quantity {n}'


def reanchor(intro, item, n, selling=False):
    """B from quantity/confirmation returns to the list; B from the list returns to the main menu.

    Stop on the visible main menu, since another B there would close the shop.
    Pokemart's main loop resets the scroll offset; up to the top is also a safe named anchor.
    """
    choice = 'SELL' if selling else 'BUY'
    selection = (f'Select {item} by its bag name; scroll up or down until it is highlighted' if selling else
                 'Scroll up to POKE BALL at the top, then press down 1 to POTION')
    return ('Press B once to back out; if BUY/SELL/QUIT is not visible yet, press B once more. '
            'Stop as soon as BUY/SELL/QUIT appears. ' + intro + f' Target: {item}.' +
            f' Move the arrow to {choice}, then press A. ' + selection +
            f', press A, {quantity(n)}, press A, check the item and total, choose YES, press A.')


def shop(A, s, question):
    if T.here(s)[0] not in MARTS:
        return None
    q = question or ''
    rows, _ = T.screen_words(s)
    words = ' '.join(rows).upper().replace('É', 'E')
    main = all(re.search(r'\b' + choice + r'\b', words) for choice in ('BUY', 'SELL', 'QUIT'))
    explicit_buy = bool(re.search(r'\bbuy(?:ing)?\b', q, re.I))
    selling = bool(re.search(r'\bsell(?:ing)?\b', q, re.I) or
                   not main and not explicit_buy and re.search(r'like to sell|I can pay you', words, re.I))
    # A visible background Rope is not a request to sell it instead of the named Potions.
    requested = next((n for n in ('POTION', 'ESCAPE ROPE') if re.search(n.replace(' ', '[ _]'), q, re.I)), None)
    item = requested if selling and requested else ('ESCAPE ROPE' if selling and 'ESCAPE ROPE' in words else 'POTION')
    plan = buy_plan(A, s)
    if not s.get('text_box'):
        if T.SHOP_Q.search(q) or not q:
            if T.here(s)[0] == 'PEWTER_MART':
                a = L.pewter_shop(A, s)
                return dict(a, do=a['do'] + ' ' + plan + ' Select POTION (down 1 from POKE BALL), A, '
                            f'{quantity(buy_count(A, s))}, A, then YES.' if buy_count(A, s) else a['do'] + ' ' + plan,
                            details=a['details'] + ([A.shop_line(s)] if A.shop_line(s) else []))
            return result('Talk to the clerk across the counter; choose BUY. ' + plan +
                          ' Select POTION (down 1 from POKE BALL), A, set the quantity, A, then YES.', X.MART_LINE,
                          [A.shop_line(s)] if A.shop_line(s) else [])
        return None
    # The live decoder strips the quantity marker and numeric-only row. Stock rows alone
    # cannot distinguish a list from its overlaid quantity box.
    number = bool(re.search(r'HOW MANY|QUANTITY|[x×]\s*\d+', words, re.I))
    confirm = bool(re.search(r'\bYES\b|\bOK\?|I CAN PAY YOU', words))
    is_list = not number and not confirm and any(n in words for n in ITEMS | {'CANCEL'})
    # The question mark belongs to the item-price dialogue, never to a stock row.
    # After cont scrolls twice even this item row is gone: stock adjacency proves nothing.
    foreground = re.search(r'\b(' + '|'.join(sorted(ITEMS)) + r')\?\s+THAT WILL BE\b', words)
    total = re.search(r'THAT WILL BE\s+(\d[\d,]*)\s*\.\s*OK\?', words)
    if not selling and (number or confirm):
        selected = foreground[1] if foreground else None
        if not confirm:
            names = [n for n in ITEMS if n in words]
            selected = names[0] if len(names) == 1 else None
        if (confirm and selected is not None and selected != 'POTION') or (number and selected != 'POTION'):
            return result(f'Press B once to cancel {selected or "this unverified item"}; read the visible choices before buying. '
                          + plan + ' Then ask again before selecting POTION.',
                          'Check the item and total before spending money.')
    # Even an unidentified shop list must not fall through to generic A / walking advice.
    if not (is_list or number or confirm or main or T.SHOP_Q.search(q) or
            (s.get('teacher_screen') or {}).get('cursor') or
            re.search(r'MONEY|TAKE YOUR TIME|LIKE TO SELL', words)):
        return None
    n = A._bag(s).get(item.replace(' ', '_'), 0) if selling else buy_count(A, s)
    inferred = False
    if selling and not n and item in words:
        count = re.search(r'\b(\d+|three)\s+escape[ _]ropes?\b', q, re.I)
        if count:
            n = 3 if count[1].lower() == 'three' else int(count[1])
            inferred = True
    if not n:
        return result('Press B to cancel: you have no ' + item + ' to sell.' if selling else plan,
                      'Keep the money and needed healing items.')
    price = n * (275 if item == 'ESCAPE ROPE' else 150) if selling else n * 300
    intro = f'Sell {n} {item} for {price} (half price).' if selling else plan
    if inferred:
        intro = f'Check you have {n}: the bag count was not recorded. ' + intro
    current = re.search(r'[x×]\s*(\d+)', words, re.I)
    # Screen rows often omit the digits. Do not guess a quantity after the box is already open.
    if number and not current:
        return result(reanchor(intro, item, n, selling),
                      'A new number box starts at 1; its current number was not recorded.')
    if confirm:
        # Selling text has no foreground item name: safely reselect rather than guess from stock.
        if selling:
            return result(reanchor(intro, item, n, selling), 'Reselect the named bag item before selling.')
        if total and int(total[1].replace(',', '')) != price:
            return result('Press B once to cancel this unverified total. ' + intro,
                          'Only confirm the named item, quantity and price you intend.')
        if not total:
            return result(intro + f' Read the visible choices. Check the price on screen is exactly {price} for {n} '
                          f'Potion{"s" if n != 1 else ""} at 300 each. '
                          'Only if it matches: Choose YES (up once if NO is selected), then press A. '
                          'If the total differs or you cannot read it, press B to cancel and ask again.',
                          'The item may have scrolled away and the price row was not recorded; '
                          'check the visible total, never background money or stock.')
        do = intro + ' Choose YES (up once if NO is selected), then press A.'
    elif number:
        do = intro + f' {quantity(n, int(current[1]))}, press A, choose YES (up once if NO is selected), press A.'
    elif is_list:
        if any(re.search(r'[▶►▷>]', row) for row in rows) and not selling:
            do = intro + ' ' + select(rows, item, q) + f', then {quantity(n)}, press A, choose YES (up once if NO is selected), press A.'
        else:
            do = reanchor(intro, item, n, selling)
    elif main:
        choice = 'SELL' if selling else 'BUY'
        do = (f'Move the arrow to {choice}, press A. ' + intro + ' ' +
              (f'Select {item}' if selling else 'Press down 1 from POKE BALL to POTION') +
              f', press A, {quantity(n)}, press A, choose YES, press A.')
    else:
        do = reanchor(intro, item, n, selling)
    return result(do, 'Read the item and total before confirming. Potion 300; Escape Rope 550, sells for 275.')


def grass_walk(A, s, q):
    """A requested training destination needs directions even when training is optional."""
    q = q.lower()
    if not re.search(r'\bgrass\b', q) or not re.search(r'\b(where|how|give|coordinates|reach|route|go|get)\b', q):
        return None
    m, pos = T.here(s)
    tile = re.search(r'\bgrass at\s*\(?(\d+),\s*(\d+)\)?', q)
    if tile:
        dest = (int(tile[1]), int(tile[2]))
        if dest in T.grass_tiles(A, m):
            return L.walk(A, s, L.goal_at(m, dest), f'the grass at ({dest[0]},{dest[1]})', max_maps=0)
    spot = T.training_spot(A, s)
    if not spot:
        return result('Stop and look; I have no checked safe walk to grass from here.',
                      'An unbeaten trainer or a blocked tile may be in the way.')
    label, levels, route, dest = spot
    walk = ', '.join(A.walk_words(s, route)[:5]) if route else 'you are in the grass now'
    return result(f'To {label} ({levels}): {walk}.',
                  'This walk avoids unbeaten trainers. Training is optional if the next fight is already a likely win.',
                  [d for d in [T.circuit(A, route['target'][0] if route else m, dest),
                              'Check HP after each fight and ask if you are ready after each level.'] if d])


def moon_routes(A, s, q, context):
    m, pos = T.here(s)
    leave = bool(not L.has_fossil(A, s) and re.search(
        r'\b(?:leave (?:mt\.?\s*moon|mount moon|the cave)|'
        r'how (?:do|can) i (?:leave|get out|exit)|way back out)\b', q))
    if context is not None:
        arrived = m == 'ROUTE_4' and pos[0] < 22
        target = A.named_place(q, s) or T.alias_target(q, s)
        floors = {'MT_MOON_1F': 0, 'MT_MOON_B1F': 1, 'MT_MOON_B2F': 2}
        floor_goal = re.search(r'\b(?:to|reach|find|towards?|is)\s+(?:the\s+)?(b1f|b2f|1f)\b', q)
        if floor_goal:
            target = 'MT_MOON_' + floor_goal[1].upper()
        # A floor on the way back is still the retreat. Only an explicit inward
        # destination or another place changes it; "next ladder" and "from B1F" do not.
        new_goal = (floors[target] > floors.get(m, 2) if target in floors else
                    bool(target and target not in {'ROUTE_4', 'MT_MOON_POKECENTER'}))
        new_goal = new_goal or re.search(
            r'\b(?:where (?:is|are)|reach|find|route to|way to|go to|head to|continue to)\b.*'
            r'\b(?:fossil|cerulean|pewter|grass|rocket|nerd|route 4 east)\b', q)
        if arrived or new_goal and not leave:
            context.pop('r15_retreat', None)
        elif leave and m in X.CAVE:
            context['r15_retreat'] = 'ROUTE_4_WEST'
    retreat = leave or (context or {}).get('r15_retreat') == 'ROUTE_4_WEST'
    if m not in X.CAVE or 'Cascade' in s['badges']:
        return None
    if pos in M.sight(s, m):
        a = T.blocked(A, s, q, context)
        return dict(a, do=a['do'].replace('press A to read on', 'press A once to read on'))
    reason = L.recovery_reason(A, s)
    if reason and not reason.startswith('Heal first'):
        return None
    if retreat:
        a = L.walk(A, s, lambda mm, p: mm == 'ROUTE_4' and p[0] < 22,
                   'Route 4 west through the cave entrance')
        return dict(a, why='Before taking a fossil, this retreat returns to the entrance and the Route 4 Center. '
                    'To reach Cerulean instead, continue via 1F (5,5) and B1F (21,17).')
    if T.BLOCK_Q.search(q):
        direction = T.blocked_direction(q)
        if direction:
            dx, dy = A.W.STEP[direction]
            if (pos[0] + dx, pos[1] + dy) in M.sight(s, m):
                a = X.cave(A, s, '', context)
                if a:
                    return a
    return None


def bypass(A, s, q):
    """A request to avoid a needed Route 3 fight must explain the limit, not trigger it."""
    if not re.search(r'\b(avoid\w*|bypass|without (?:a |the )?(?:trainer|fight|battle))\b', q):
        return None
    # Check from THIS tile; a trainer behind the player need not be fought again.
    if A.walk_to(s, lambda m, p: m == 'ROUTE_4', max_maps=2, fallback=False):
        return L.walk(A, s, lambda m, p: m == 'ROUTE_4', 'Route 4', max_maps=2)
    _, needed, _ = T.trainer_rows(A, s)
    if not needed:
        return None
    if T.here(s)[1] in M.sight(s, 'ROUTE_3'):
        return T.blocked(A, s, q, None)
    row = needed[0]
    a = T.readiness(A, s, [row])
    if not a:
        return None
    way = grass_walk(A, s, 'Where is the nearest grass for training?')
    return dict(a, do=f'You cannot bypass {T.who_short(row)} on the checked way east. ' + a['do'] +
                (' If you want to train first: ' + way['do'] if way else ''),
                details=list(a['details']) + ['You can use Potions in trainer battles: ITEM, POTION, then your Pokemon.'])


def answer(A, s, question, context):
    if s.get('battle') or s.get('text_box') or not s.get('team') or s.get('r13_pure'):
        return None
    q = (question or '').lower()
    m, pos = T.here(s)
    # Also clear the retained goal on the first observation at Route 4 west.
    a = moon_routes(A, s, q, context)
    if m in MARTS:
        return shop(A, s, question)
    if 'Boulder' not in s['badges']:
        return None
    if a:
        return a
    if m in {'ROUTE_3', 'ROUTE_4'} | X.CAVE and not L.recovery_reason(A, s):
        a = grass_walk(A, s, q)
        if a:
            return a
    if m == 'ROUTE_3':
        a = bypass(A, s, q)
        if a:
            return a
    first = T.lead(s)
    if m == 'MT_MOON_B2F' and not M.defeated(s, X.ROCKET) and first and first['status'] == 'ok' \
            and first['hp'] * 3 >= first['max_hp'] and first['hp'] * 2 < first['max_hp'] \
            and L.recovery_reason(A, s) in (None, 'Heal first; your team is hurt.') and not T.potions(A, s) and not re.search(
                r'\b(center|centre|escape|retreat|back|return)\b', q) and X.verdict(A, s, ['Rocket:1'])[0] == 'win':
        walk = X.cave_floor(A, s, '', False)
        if walk:
            return dict(walk, do='You can try the needed Rocket first: a likely win with current HP and PP (estimate). '
                        + walk['do'], details=walk['details'] +
                        ['Wild encounters are not included in this estimate. Recheck HP after each fight; heal if it falls.'])
    # Explicit Center directions still go through the old checked named-place walker.
    center_directions = re.search(r'(?:where is|how (?:do|can) i (?:get|reach)|(?:route|way|directions) to|'
                                  r'(?:go|take)(?: me)?(?: back)? to)\s+(?:(?:to|the|nearest|pokemon|pewter|route 4|'
                                  r'mt\.? moon)\s+)*' + CENTER, q)
    if m == 'ROUTE_3' and HEAL.search(q) and not center_directions:
        a = T.potion_first(A, s) or T.readiness(A, s)
        if a and a.get('verdict') in ('potion', 'ready') and re.search(r'\b(route|way|where|moves|reach)\b', q):
            walk = L.walk(A, s, L.goal_at('ROUTE_4', (18, 5)), 'Mt. Moon entrance at Route 4 (18,5)')
            return dict(a, do=a['do'] + ' For the Mt. Moon entrance, after any healing and closing the menus: ' + walk['do'],
                        details=list(a['details']) + walk['details'])
        return a
    if m == 'ROUTE_3' and pos == (11, 6) and not M.defeated(s, 'EVENT_BEAT_ROUTE_3_TRAINER_0') and not re.search(
            r'\b(center|centre|retreat|escape|buy|train|catch|heal|potion)\b', q):
        row = next(r for r in M.maps()[m]['objects'] if r.get('event') == 'EVENT_BEAT_ROUTE_3_TRAINER_0')
        a = T.readiness(A, s, [row])
        if a and a.get('verdict') == 'ready':
            return dict(a, do='Ready: face left once toward the Bug Catcher at (10,6), then press A once to start the battle. '
                        'Ask for a move when the battle menu opens.')
        return a
    if re.search(r'\bready\b|strong enough', q) and re.search(r'mt\.?\s*moon|mount moon', q) and 'mt_moon' not in s['story']['done']:
        key, name = X.next_fight(s)
        v, n = X.verdict(A, s, [key]) if key else ('win', 0)
        if v == 'win':
            do = f'Ready for {name}: a likely win at your current HP and PP (estimate).'
        elif v == 'potion':
            do = X.use_potions(A, s, n) + f' Then {name} is a likely win (estimate).'
        elif v == 'train':
            do = f'Train to about L{n} (estimate), then heal and ask again about {name}.' if n else f'Train and ask again about {name}: likely loss (estimate).'
        else:
            do = f'Heal at a Center before {name}; likely loss now, likely win healed (estimate).'
        return result(do, 'This checks the next needed cave fight, not only the story goal.',
                      ['Wild encounters and later fights can still cost HP and PP. Recheck at each floor.'])
    if m in {'CERULEAN_CITY', 'ROUTE_24', 'ROUTE_25'} and re.search(r'\bbridge\b|\bnugget\b', q) and not re.search(r'\b(catch|oddish|back|return)\b', q):
        a = T.readiness(A, s) if m in ('ROUTE_24', 'ROUTE_25') else X.rival(A, s)
        exp = sum(X.trainer_exp(A, k) or 0 for k in X.bridge_keys(A))
        return result('Nugget Bridge is useful training before Misty: 5 trainers, then the Rocket. '
                      + (a['do'] if a else 'Check readiness before the next unbeaten trainer.'),
                      f'The whole unbeaten bridge gives about {exp:,} EXP to one Pokemon fighting alone; beaten trainers cannot be fought again.',
                      [X.misty(A, s)['do'], 'Recheck HP and PP after each fight; use the Center when needed.'])
    return None


def finish(A, s, question, a):
    """Final wording guards also apply after old repeat handling."""
    if s.get('battle'):
        return a
    rows, quote = T.screen_words(s)
    words = ' '.join(rows)
    if s.get('text_box'):
        if T.here(s)[0] in X.CAVE and T.here(s)[1] in M.sight(s, T.here(s)[0]):
            return dict(a, do=f'The text box says "{quote}". A trainer is talking: press A once to read on. '
                        'The battle is starting; ask for a move when FIGHT / PKMN / ITEM / RUN appears.',
                        why='You cannot walk away after stepping into an unbeaten trainer\'s sight.', details=[])
        b = shop(A, s, question)
        if b:
            return dict(a, **b)
        if T.here(s) == ('ROUTE_3', (11, 6)) and not M.defeated(s, 'EVENT_BEAT_ROUTE_3_TRAINER_0') and re.search(
                r'hey.*met you|viridian forest', words, re.I):
            return dict(a, do=f'The text box says "{quote}". The Bug Catcher is talking: press A once to read on. '
                        'Do not walk away. Ask for a move when the battle menu opens.')
        if T.here(s)[0].endswith('_POKECENTER'):
            farewell = bool(re.search(r'hope to see|you again', words, re.I))
            heal_question = bool(re.search(r'heal', words, re.I) and re.search(r'\bYES\b', words))
            continuing = T.HEAL_TEXT.search(words) and not a['do'].startswith('Same screen')
            if farewell or heal_question or continuing:
                start = ('At the farewell, press B once to close it; do not press A again.' if farewell else
                         'This is the heal question: press A to say YES (if NO is selected, press up first). '
                         'Press A once per page until "We hope to see you again!", then press B once; do not press A again.'
                         if heal_question else 'Press A to go on, once per page. After "We hope to see you again!", '
                         'press B once to close it; do not press A again.')
                walk = T.exit_walk(A, s)
                return dict(a, do=f'The text box says "{quote}". ' + start +
                            (' Then walk to the door: ' + walk + '.' if walk else ' Then walk down to the door.'))
        return a
    out = dict(a, details=list(a.get('details', [])))
    do = out['do']
    # Short outside checkpoints must not continue with instructions for an interior not reached yet.
    if not T.here(s)[0].endswith('_POKECENTER'):
        def safe_inside(text):
            hit = re.search(r'\bInside: walk up to the nurse counter', text, re.I)
            if hit and not re.search(r'\(into \w+_POKECENTER\)', text[:hit.start()]):
                if text.startswith('Same answer three times without moving:'):
                    entry = next((re.search(r'\(into \w+_POKECENTER\)', d) for d in a.get('details', [])
                                  if re.search(r'\(into \w+_POKECENTER\)', d)), None)
                    if entry:
                        return text[:hit.start()] + entry[0] + '. ' + text[hit.start():]
                return text[:hit.start()].rstrip() + ' Then ask again at this checkpoint for the remaining way to the Center.'
            return text
        out['do'] = safe_inside(do)
        out['details'] = [safe_inside(d) for d in out['details']]
    # Missing targets occurred when no local trainer was left on the current map.
    if re.search(r'\btrain(?:ing)?\b|extra levels', do, re.I) and 'Boulder' in s['badges'] and 'mt_moon' not in s['story']['done'] \
            and not re.search(r'\b(?:until|to|target)[^.!?]{0,20}\b(?:L|level\s*)\d+', do):
        target = 13  # An intermediate training estimate from the replay, followed by a fresh readiness check.
        lead = T.lead(s)
        stop = (f' Train until about L{target} (estimate), then ask if you are ready for Mt. Moon.' if lead['level'] < target else
                f' You reached the training target of about L{target} (estimate); stop training and ask if you are ready for Mt. Moon.')
        out['do'] += stop
    return out
