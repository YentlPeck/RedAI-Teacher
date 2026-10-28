"""Short post-Brock advice. Map-checked walks and battle estimates are not game tests."""
import re
import r11_maps as M

CAVE = {'MT_MOON_1F', 'MT_MOON_B1F', 'MT_MOON_B2F'}
TOWNS = {'CERULEAN_CITY', 'CERULEAN_GYM', 'CERULEAN_POKECENTER', 'CERULEAN_MART',
         'ROUTE_24', 'ROUTE_25', 'BILLS_HOUSE'}


def result(do, why, *details):
    return dict(do=do, why=why, details=list(details))


def goal_at(map_, pos):
    return lambda m, p: m == map_ and p == pos


def here(s):
    p = s['place']
    return p['map'], (p['x'], p['y'])


def has_fossil(A, s):
    return any(A._bag(s).get(i, 0) or M.defeated(s, 'EVENT_GOT_'+i) for i in ('DOME_FOSSIL', 'HELIX_FOSSIL'))


def walk(A, s, goal, label, max_maps=8, battle_flags=None):
    """Offer one local leg; stop BEFORE the first unbeaten battle if no bypass exists."""
    m, pos = here(s)
    if goal(m, pos):
        return result('You are at '+label+'. Look before interacting.', 'Check the person, door or ladder in front of you.')
    route = A.walk_to(s, goal, max_maps=max_maps, fallback=False)
    stop = None
    if not route:
        allowed = battle_flags if battle_flags is not None else {e for e in M.events() if e.startswith('EVENT_BEAT_')}
        flags = dict(s.get('teacher_events', {}), **{e: True for e in allowed})
        route = A.walk_to(dict(s, teacher_events=flags), goal, max_maps=max_maps, fallback=False)
        if route:
            dests = [step[0] for step in route['steps'][1:]] + [route['target']]
            for i, (dest_map, dest) in enumerate(dests):
                if dest in M.sight(s, dest_map):
                    src = route['steps'][i][0]
                    stop = (src, (dest_map, dest))
                    if src == (m, pos):
                        who, key = encounter(A, s, dest_map, dest)
                        estimate = forecast(A,s,[key]) if key else None
                        direction = next((d for d,(dx,dy) in A.W.STEP.items() if (pos[0]+dx,pos[1]+dy)==dest), 'forward')
                        return result('Stop here: '+direction+' starts '+who+'.',
                                      'Your team may win; choose the fight only after healing.' if estimate and estimate['ok'] and not recovery_reason(A, s) else 'Heal or strengthen your team before this battle.',
                                      'No safe bypass is checked from this tile. Walk unverified in a game.')
                    route = A.walk_to(s, lambda mm, pp: (mm, pp) == src, max_maps=max_maps, fallback=False)
                    break
    if not route:
        return result('Stop and look; I have no checked safe walk to '+label+' from this tile.',
                      'A trainer, moving person or blocked passage may be in the way.',
                      'Walk unverified. Ask again with your floor and coordinates.')
    words = A.walk_words(s, route)
    shown = words[:5]
    end = ' Then stop before the trainer and check readiness.' if stop else ' Then look and ask for the next checkpoint.'
    do = ('Next toward '+label+': '+', '.join(shown)+'.'+end) if shown else 'Look here before the next step toward '+label+'.'
    a = result(do, 'This walk avoids known unbeaten sight lines and visible people.',
                  'Walk unverified in a game; map tiles and warps checked.' +
                  (' More turns remain; ask again at the last shown coordinate.' if len(words)>5 else ''))
    if stop:
        who, _ = encounter(A,s,*stop[1])
        a['details'].append('Battle stop: '+who+' ahead. Recheck HP and PP at the checkpoint before stepping into sight.')
    return a


def encounter(A, s, map_, pos):
    for row in M.maps().get(map_,{}).get('objects',[]):
        if 'event' not in row or M.defeated(s,row['event']):
            continue
        dx,dy=M.STEP.get(row['facing'],(0,0))
        if pos in {(row['x']+dx*n,row['y']+dy*n) for n in range(1,row['sight']+1)}:
            cls,idx=row['trainer'].split(':')
            key=next((k for k in A.TEAMS if k.split(':')[1]==idx and re.sub('[^a-z]','',k.split(':')[0].lower())==cls.replace('_','').lower()),None)
            return cls.replace('_',' ').title()+f' at ({row["x"]},{row["y"]})',key
    if map_=='CERULEAN_CITY' and pos in ((30,7),(30,9)):
        return 'the Rocket thief','Rocket:5'
    if map_=='CERULEAN_CITY':
        return 'the Cerulean rival',{'SQUIRTLE':'Rival1:7','BULBASAUR':'Rival1:8','CHARMANDER':'Rival1:9'}.get(s.get('rival_starter'))
    return 'an unbeaten trainer battle',None


def team(A, s):
    return [A._party_mon(t, s['badges']) for t in s['team']]


def forecast(A, s, keys):
    """Separate fights, same party order and HP/PP. No free heals or invisible Potions."""
    mine = team(A, s)
    left, lines = 0, []
    for key in keys:
        win, left, _, mine = A.fight(mine, A.TEAMS[key]['party'], carry=True)
        name={'JrTrainerF:1':'gym trainer (Goldeen L19)','Misty:1':'Misty','SuperNerd:2':'Super Nerd'}.get(key,key.split(':')[0])
        lines.append(name + (': likely win' if win else ': likely loss'))
        if not win:
            break
    return dict(ok=bool(mine) and win and left >= .25 if keys else bool(mine),
                left=left, lines=lines, team=mine, keys=keys)


def recovery_reason(A, s):
    live = [t for t in s['team'] if t['hp'] > 0]
    if not live:
        return 'Your team has fainted. Let the blackout finish with A once, then look.'
    if any(t['status'] != 'ok' for t in live):
        return 'Cure status and heal before another trainer.'
    if any(t['hp']*2 < t['max_hp'] for t in live):
        return 'Heal first; your team is hurt.'
    if not any(A.MOVES.get(m['move'],{}).get('power',0)>0 for t in live for m in t['moves']):
        return 'Your team has no damaging moves; teach an attack or add a healthy attacker.'
    if not any(m['pp'] and A.MOVES.get(m['move'],{}).get('power',0)>0
               for t in live for m in t['moves']):
        return 'Restore PP at a Center before another fight.'
    return None


def heal(A, s):
    m, _ = here(s)
    sick = [t for t in s['team'] if t['hp'] > 0 and t['status'] == 'poisoned']
    bag = A._bag(s)
    if sick and bag.get('ANTIDOTE', 0):
        return result('Use an Antidote now, then heal HP and PP at a Center.',
                      'Poison takes 1 HP every four walking steps and can cause a blackout.')
    if m in ('MT_MOON_POKECENTER', 'CERULEAN_POKECENTER'):
        return result('Talk to the nurse across the counter; face her and press A once, then read on.',
                      'The Center restores HP and PP and cures status for free.')
    if m in CAVE and bag.get('ESCAPE_ROPE', 0):
        return result('Use your Escape Rope from ITEM, then look at the town where you arrive and heal.',
                      'In Red it returns to your last healing place: '+str(s.get('last_heal_map') or 'not known here')+'.',
                      'Your fossil stays in your bag. The Rope does not take you through the cave exit.')
    target = 'MT_MOON_POKECENTER' if m in CAVE or m == 'ROUTE_3' or (
        m == 'ROUTE_4' and s['place']['x'] < 22) else 'CERULEAN_POKECENTER'
    if m in ('PEWTER_CITY','PEWTER_MART'):
        target = 'PEWTER_POKECENTER'
    if m == 'ROUTE_3':
        nearest = A.walk_to(s, lambda mm,p:mm in ('PEWTER_POKECENTER','MT_MOON_POKECENTER'), max_maps=8, fallback=False)
        target = nearest['target'][0] if nearest else 'PEWTER_POKECENTER'
    route = A.walk_to(s, lambda mm, p: mm == target, max_maps=8, fallback=False)
    if sick:
        # The current four-step poison phase is unknown: reserve an immediate tick.
        cost = route['cost'] if route else 10**6
        survives = any(t['hp'] > cost//4+1 or t['status'] != 'poisoned' for t in s['team'] if t['hp']>0)
        if not survives:
            return result('Do not start the long walk: poison may black out your whole team.',
                          'You have no Antidote, and I cannot check a survivable walk to healing.',
                          'Use a Potion for breathing room if you have one; buy an Antidote when you can. An Escape Rope can shorten a cave retreat.')
    door = {'CERULEAN_POKECENTER':'city door (19,17)', 'PEWTER_POKECENTER':'Pewter door (13,25)', 'MT_MOON_POKECENTER':'Route 4 door (11,5)'}[target]
    a = walk(A, s, lambda mm, p: mm == target, target.replace('_',' ')+' ('+door+')')
    a['details'].append('Heal HP and PP and cure status at the nurse. Stop for any battle or moving person.')
    return a


def starter_tip(A, s):
    species = {t['species'] for t in s['team']}
    if species & {'BULBASAUR','IVYSAUR','VENUSAUR'}:
        return 'Lead a healed Grass starter with Vine Whip (Bulbasaur L13). Ivysaur L20-24 is an untested guess.'
    if species & {'CHARMANDER','CHARMELEON','CHARIZARD'}:
        return 'Fire is weak to Water. Oddish with Absorb is a reachable backup; L18-22 is an untested guess.'
    if species & {'SQUIRTLE','WARTORTLE','BLASTOISE'}:
        return 'Water resists Water both ways. Wartortle learns Bite at L24 (Normal in Red); L24+ alone is an untested guess.'
    return 'Oddish with Absorb resists Water. Its L18-22 target is an untested guess; use your actual HP and PP.'


def gym_plan(A, s):
    """Check the Swimmer bypass. Goldeen then Misty is the usual two-fight route."""
    # Pretend only the Goldeen trainer is defeated, to check the Swimmer bypass.
    flags = dict(s.get('teacher_events', {}), EVENT_BEAT_CERULEAN_GYM_TRAINER_0=True)
    r = A.walk_to(dict(s, teacher_events=flags), goal_at('CERULEAN_GYM', (4,3)), max_maps=6, fallback=False)
    keys = []
    if not r and not M.defeated(s, 'EVENT_BEAT_CERULEAN_GYM_TRAINER_1'):
        keys.append('Swimmer:1')
    if not M.defeated(s, 'EVENT_BEAT_CERULEAN_GYM_TRAINER_0'):
        keys.append('JrTrainerF:1')
    keys.append('Misty:1')
    return forecast(A, s, keys), r


def gym_walk(A,s):
    g, bypass = gym_plan(A,s)
    allowed = {'EVENT_BEAT_CERULEAN_GYM_TRAINER_0'}
    if not bypass:
        allowed.add('EVENT_BEAT_CERULEAN_GYM_TRAINER_1')
    if here(s)==('CERULEAN_GYM',(4,3)):
        return result('Face up and press A once to speak to Misty, after checking HP and PP.',
                      'Her Staryu L18 and Starmie L21 are one fight; Bill is optional.')
    a=walk(A,s,goal_at('CERULEAN_GYM',(4,3)),'Misty at (4,2), Gym door in town (30,19)',battle_flags=allowed)
    a['details'].append('Bill is optional. '+('Use the left path around the Swimmer; ' if bypass else '')+'stop for the Goldeen trainer and recheck HP and PP before Misty.')
    return a


def misty_advice(A, s):
    """R14 (G9): Misty readiness on the r13 fight model with a level target (r14_advice.misty). The R11 version
    below (old fight model, no level number) is kept for reference only."""
    import r14_advice
    return r14_advice.misty(A, s)


def misty_advice_r11(A, s):
    g, bypass = gym_plan(A, s)
    reason = recovery_reason(A, s)
    pots = sum(A._bag(s).get(k, 0) for k in A.HEAL)
    healthy = all(t['hp'] == t['max_hp'] and t['status'] == 'ok' for t in s['team'])
    if not g['ok']:
        do = 'Not ready for Misty: train or add a Water-resistant backup, then heal and recheck both gym fights.'
    elif reason or not healthy:
        do = 'Not ready for Misty yet: heal first and recheck both gym fights.'
    else:
        do = 'Your team looks ready for the gym trainer, then Misty.'
    # Keep immediate recovery visible without replacing the readiness answer.
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
    details = ['HP and PP carried between fights: '+', '.join(g['lines'])+'.',
               starter_tip(A, s)]
    if s['team']:
        foe = A._foe(A.TEAMS['Misty:1']['party'][-1])
        options = [(A.move_option(m['move'], m['pp'], mon, foe), mon['species'])
                   for mon in team(A,s) if mon['hp']>0 for m in mon['moves'] if m['pp']>0]
        options = [(o, sp) for o, sp in options if o and o['expect']>0]
        if options:
            o, sp = max(options, key=lambda v: v[0]['expect'])
            details.append(f'Lead choice: {sp} with {o["move"].replace("_"," ")}, if healthy. Check its Water risk.')
    weak = [t['species'] for t in s['team'] if A.type_mult('WATER', A._types_of(t['species']))>1]
    details.append('Staryu L18: Tackle, Water Gun. Starmie L21: Tackle, Water Gun, BubbleBeam; Speed 56. '+
                   ('Water is super effective on '+', '.join(weak)+'. ' if weak else '')+
                   'BubbleBeam may lower Speed; critical hits or misses can overturn this estimate.')
    details.append(f'Bag: {pots} healing items; money {s.get("money",0)}. '+
                   ('Aim for 3+ Potions for neutral damage (untested). ' if pots<3 else '')+
                   'Cerulean Mart: Potions, Antidotes, no Super Potions. Potions are not counted as free healing.')
    if bypass:
        details.append('Swimmer bypass: left of row 7, across row 5; walk unverified. Goldeen L19 has Peck and Supersonic. Heal/recheck before Misty.')
    else:
        details.append('No Swimmer bypass checked from here; his Horsea L16 and Shellder L16 are counted too.')
    why = ('The current HP/PP forecast does not safely clear the gym fights. ' if not g['ok'] else '')
    return result(do, why+'Bill is optional for the Cascade Badge. Estimate: your current party order; no critical hits or stat changes.', *details)


def rival(A, s):
    sp = s.get('rival_starter')
    key = {'SQUIRTLE':'Rival1:7', 'BULBASAUR':'Rival1:8', 'CHARMANDER':'Rival1:9'}.get(sp)
    if not key:
        return result('Heal before the north bridge; the rival starter is not known yet.',
                      'I cannot choose his team safely without the starter recorded in your game.')
    if M.defeated(s, 'EVENT_BEAT_CERULEAN_RIVAL'):
        return result('The Cerulean rival is already beaten; heal before the bridge trainers.', 'His battle flag is set.')
    g = forecast(A, s, [key])
    a = result('Heal first; stay south of the bridge.' if recovery_reason(A, s) else
               'Your team may beat the rival; heal HP and PP first.' if g['ok'] else
               'Train or strengthen your team before the rival; stay south of row 6.',
               f'His starter is {sp} L17. His other Pokemon are Pidgeotto L18, Abra L15 and Rattata L15.',
               'One full fight with your current HP/PP; estimate only. Pidgeotto and Rattata can use Quick Attack; Abra only has Teleport.')
    return a


def pickup(A, s, map_, pos, item):
    m, p = here(s)
    rows = M.maps()[map_]['objects']
    obj = next((r for r in rows if (r['x'],r['y'])==pos), None)
    seen = next((r for r in s.get('teacher_objects',{}).get(map_,[]) if obj and r['id']==obj['id']), {})
    if seen.get('hidden'):
        return result('That '+item+' has already been collected; continue toward the exit.', 'The item ball is hidden.')
    if len(s['bag'])>=20 and not A._bag(s).get(item,0):
        return result('Make a bag slot before collecting '+item+'.', 'A full bag prevents a new item; the ball stays there.')
    if m==map_ and abs(p[0]-pos[0])+abs(p[1]-pos[1])==1:
        direction = next(d.lower() for d, (dx,dy) in M.STEP.items() if (p[0]+dx,p[1]+dy)==pos)
        return result('Face '+direction+' and press A once for '+item+'; read the choice before confirming.',
                      f'The object is at {map_} ({pos[0]},{pos[1]}).')
    a = walk(A, s, lambda mm, pp: mm==map_ and abs(pp[0]-pos[0])+abs(pp[1]-pos[1])==1, item)
    a['details'].append(f'{item} is at {map_} ({pos[0]},{pos[1]}); stand beside it, face it, press A.')
    return a


def cave(A, s, q):
    m, pos = here(s)
    fossil = has_fossil(A,s)
    nerd = M.defeated(s, 'EVENT_BEAT_MT_MOON_EXIT_SUPER_NERD')
    if re.search(r'escape(?! rope ball)|retreat|back out|heal|poison|out of pp|lost',q):
        return heal(A,s)
    if 'moon stone' in q:
        return pickup(A,s,'MT_MOON_1F',(2,2),'MOON_STONE')
    for words, mm, xy, name in [('water gun','MT_MOON_1F',(5,32),'TM_WATER_GUN'),
                              ('rare candy','MT_MOON_1F',(35,31),'RARE_CANDY'),
                              ('mega punch','MT_MOON_B2F',(29,5),'TM_MEGA_PUNCH'),
                              ('escape rope ball','MT_MOON_1F',(36,23),'ESCAPE_ROPE'),
                              ('hp up','MT_MOON_B2F',(25,21),'HP_UP')]:
        if words in q:
            return pickup(A,s,mm,xy,name)
    if fossil:
        a=walk(A,s,goal_at('ROUTE_4',(24,5)),'the Route 4 cave exit')
        a['details'].insert(0,'Fossil taken: leave by B2F (5,7) -> B1F (23,3), then B1F (27,3) -> Route 4 (24,5). Do not restart the cave.')
        return a
    if 'rocket' in q:
        candidates=[r for r in M.maps()['MT_MOON_B2F']['objects'] if r.get('trainer','').startswith('ROCKET') and not M.defeated(s,r['event'])]
        row=min(candidates,key=lambda r:abs(r['x']-pos[0])+abs(r['y']-pos[1])) if candidates else None
        if not row:
            return result('The cave Rockets are beaten; continue toward the fossil.', 'Their battle flags are set.')
        g=forecast(A,s,['Rocket:'+row['trainer'].split(':')[1]])
        return result('Skip this Rocket if a checked path goes around his sight.' if g['ok'] else 'Heal or train before this Rocket.',
                      f'Rocket at ({row["x"]},{row["y"]}); '+('current team may win.' if g['ok'] else 'current team looks too weak.'),
                      'The Mega Punch and HP Up branches are optional. Keep HP and PP for the fossil guard; ask for the next ladder.')
    if nerd:
        return pickup(A,s,'MT_MOON_B2F',(13,6),'HELIX_FOSSIL')
    if re.search(r'super nerd|ready|can i beat',q) or m=='MT_MOON_B2F' and abs(pos[0]-12)+abs(pos[1]-9)<4 and not nerd:
        g=forecast(A,s,['SuperNerd:2'])
        return result('You may fight the Super Nerd: stand at (12,9), face up, press A once.' if g['ok'] and not recovery_reason(A, s) else 'Heal or train before the Super Nerd; stop before (13,8).',
                      'He has Grimer, Voltorb and Koffing, all L12. Current HP and PP counted; estimate only.',
                      'Disable, Screech and Smog/poison are not simulated. After winning, take one fossil at (12,6) or (13,6).')
    if nerd:
        return pickup(A,s,'MT_MOON_B2F',(13,6),'HELIX_FOSSIL')
    a=walk(A,s,goal_at('MT_MOON_B2F',(12,9)),'the fossil guard checkpoint (12,9) on B2F')
    a['details'].append('Exit route: 1F (5,5) -> B1F (5,5); B1F (21,17) -> main B2F (21,17). The 1F (17,11) ladder is the optional Mega Punch branch; return by the same ladders.')
    if 'fossil' in q:
        a['details'].append('Super Nerd stands at B2F (12,8), triggers at (13,8); take either fossil at (12,6)/(13,6) after winning.')
    return a


def oddish(A, s):
    owned=any(t['species'] in ('ODDISH','GLOOM','VILEPLUME') for t in s['team'])
    do='Train your Oddish and keep Absorb PP for Misty.' if owned else 'Oddish is optional: catch one in Route 24/25 grass, L12-14, with Absorb.'
    detail=starter_tip(A,s)
    if not M.defeated(s,'EVENT_BEAT_CERULEAN_RIVAL'):
        detail+=' Heal and check the rival before going north; the catch is beyond his trigger.'
    a = result(do,'Nugget Bridge and Bill are optional for Misty; use them for levels when your team needs them.',
               detail,'Butterfree: Confusion L12, Sleep Powder L17; Pidgey: Sand-Attack L5, Quick Attack L12. These are support, not guaranteed Starmie answers.')
    if not M.defeated(s,'EVENT_BEAT_CERULEAN_RIVAL'):
        a['details'].append(rival(A,s)['do'])
        return a
    grass = {mm:{p for p,t in A._grid(mm)['tile'].items() if t==0x52} for mm in ('ROUTE_24','ROUTE_25')}
    route = walk(A,s,lambda mm,p:p in grass.get(mm,set()),'Route 24/25 grass')
    a['details'] += [route['do']] + route['details']
    return a


def pewter_shop(A, s):
    # data/items/marts.asm, data/items/prices.asm, objects/Pewter{City,Mart}.asm.
    instructions = ('Stand at (2,5), press left once to face the clerk, press A and choose BUY. '
                    'Choose the item, set the quantity with up/down, press A and YES; B leaves the menu. '
                    'Only the clerk behind the counter sells items.')
    if s['place']['map'] == 'PEWTER_MART':
        a = result(instructions, 'Buy supplies here before leaving Pewter.')
    else:
        a = walk(A,s,lambda mm,p:mm=='PEWTER_MART','Pewter Mart, city door (23,17)')
        a['details'].append('Inside the Mart: '+instructions)
    a['details'] += [
        'Pewter stock/prices: Poke Ball 200, Potion 300, Escape Rope 550, Antidote 100, '
        'Burn Heal 250, Awakening 200, Parlyz Heal 200.',
        f'You have {s.get("money",0)}. Potions restore 20 HP; keep money for Antidotes. '
        'An Escape Rope is optional cave retreat insurance: buying it does not use it. '
        'Using it in a cave returns you to your last healing place, not the eastern exit.',
    ]
    return a


def answer(A, s, question):
    m,pos=here(s); q=(question or '').lower()
    active=m in CAVE|TOWNS|{'ROUTE_3','ROUTE_4','MT_MOON_POKECENTER'} or m in ('PEWTER_CITY','PEWTER_MART') and 'Boulder' in s['badges']
    if (m in ('ROUTE_3','ROUTE_4','MT_MOON_POKECENTER') and 'Boulder' not in s['badges']):
        return None
    if not active or s.get('battle'):
        return None
    readiness = (re.search(r'\bready\b|\breadiness\b', q) and re.search(r'\bmisty\b|\bgym\b', q)
                 or re.search(r'\bcan i (?:beat|defeat|fight|face|take on) (?:misty|(?:the )?gym)\b', q))
    if readiness:
        return misty_advice(A, s)
    if re.search(r'mankey',q):
        return result('Red has Mankey on Route 5, not Routes 3, 4 or 22.',
                      'Those are the Red wild tables. Route 5 is reachable south of Cerulean; Bill and Misty are not catch gates.',
                      'Mankey is not a Water counter. Oddish on Route 24/25 is the Grass option.')
    if not any(t['hp']>0 for t in s['team']):
        return result('Let the blackout finish with A once, then look and heal at the Center.',
                      'Your next walk must use your new town and tile; your fossil and badges are kept.')
    if 'no damaging moves' in (recovery_reason(A,s) or ''):
        return result(recovery_reason(A,s),'A Center restores PP for moves you already know.')
    if m in CAVE:
        if recovery_reason(A, s):
            return heal(A,s)
        return cave(A,s,q)
    purchase = bool(re.search(r'\b(buy|buying|purchase|shopping|shop|stock|prices?|mart)\b',q))
    if m in ('PEWTER_CITY','PEWTER_MART') and (purchase or m=='PEWTER_MART' and not q):
        return pewter_shop(A,s)
    if re.search(r'heal|center|centre|poison|retreat|escape|out of pp',q) or recovery_reason(A, s):
        return heal(A,s)
    target=A.named_place(question,s)
    if m=='PEWTER_MART' and not target:
        return pewter_shop(A,s)
    if target in ('PEWTER_CITY','PEWTER_MART','ROUTE_3','ROUTE_4'):
        return walk(A,s,lambda mm,p:mm==target,target.replace('_',' '))
    if m in ('PEWTER_CITY','PEWTER_MART','ROUTE_3','MT_MOON_POKECENTER') or m=='ROUTE_4' and pos[0]<22:
        a=walk(A,s,goal_at('ROUTE_4',(18,5)),'Mt. Moon entrance at Route 4 (18,5)')
        if m in ('PEWTER_CITY','PEWTER_MART','ROUTE_3'):   # R14 (G8): the Pewter line only where it is true
            a['details'].append('Leave Pewter east onto Route 3. Fight one trainer at a time only when healthy; heal at the entrance Center, Route 4 (11,5).')
        else:
            a['details'].append('This part of Route 4 has no way east: the only way to Cerulean is through Mt. Moon. Heal at the Center, Route 4 (11,5), before the cave.')
        return a
    if m=='ROUTE_4':
        return walk(A,s,lambda mm,p:mm=='CERULEAN_POKECENTER','Cerulean Center, city door (19,17)')
    if re.search(r'rival',q):
        return rival(A,s)
    if re.search(r'oddish|nugget|bridge|route[ _]?(24|25)|training|train|levels',q) and not re.search(r'back|return|ready.*misty',q):
        return oddish(A,s)
    if re.search(r'back|return',q) and m in ('ROUTE_24','ROUTE_25','BILLS_HOUSE'):
        a=walk(A,s,lambda mm,p:mm=='CERULEAN_POKECENTER','Cerulean Center via Route 25 west, Route 24 south')
        a['details'].append('Leave Bill by the south door, go west across Route 25, then south over Nugget Bridge. Stop before any unbeaten trainer.')
        return a
    if re.search(r'bill',q) and not re.search(r'optional|straight|skip|need|before',q) or (
            'Cascade' in s['badges'] and 'ss_ticket' not in s['story']['done'] and not question):
        a=walk(A,s,lambda mm,p:mm=='BILLS_HOUSE',"Bill's house, Route 25 door (45,3)")
        a['details'].append('Optional before Misty: five bridge trainers then Rocket, east through Route 25; help Bill with the computer and talk again for the S.S. Ticket, needed later.')
        return a
    if re.search(r'mart|buy|potion|antidote',q):
        a=walk(A,s,lambda mm,p:mm=='CERULEAN_MART','Cerulean Mart, city door (25,25)') if m!='CERULEAN_MART' else result('Talk to the clerk across the counter; choose BUY.','Read the item and quantity before confirming.')
        a['details'].append(f'Potions cost 300, Antidotes 100; you have {s.get("money",0)}. This Mart has no Super Potions.')
        return a
    if re.search(r'ready|lead|move|fight|beat|straight|should|bill|misty',q) and not re.search(r'where|door|how.*get',q):
        return misty_advice(A,s)
    if 'Cascade' in s['badges']:
        return None
    if re.search(r'where.*misty|gym.*door|where.*gym',q):
        a=walk(A,s,lambda mm,p:mm=='CERULEAN_GYM','Cerulean Gym, city door (30,19)') if m!='CERULEAN_GYM' else gym_walk(A,s)
        a['details'].append('Check readiness before the Goldeen trainer and Misty; Bill is optional.')
        return a
    if not gym_plan(A,s)[0]['ok']:
        return misty_advice(A,s)
    return gym_walk(A,s)
