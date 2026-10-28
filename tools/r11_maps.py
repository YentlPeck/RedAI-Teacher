"""Read-only map facts and conservative trainer/occupancy checks from pokered.

Coordinates use walking squares, not block coordinates. Unknown flags mean unbeaten.
No emulator is imported here. See macros/scripts/maps.asm and trainer_sight.asm.
"""
import functools
import json
import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import settings  # noqa: E402

ROOT = settings.REPO
SRC = settings.POKERED
CHECKED = ('Route3', 'Route4', 'MtMoon1F', 'MtMoonB1F', 'MtMoonB2F',
           'CeruleanCity', 'CeruleanPokecenter', 'CeruleanMart', 'CeruleanGym',
           'Route24', 'Route25', 'BillsHouse', 'MtMoonPokecenter',
           'ViridianForest', 'ViridianForestSouthGate', 'ViridianForestNorthGate', 'PewterGym')
STEP = {'UP': (0, -1), 'DOWN': (0, 1), 'LEFT': (-1, 0), 'RIGHT': (1, 0)}


@functools.lru_cache(None)
def maps():
    out = {}
    for name in CHECKED:
        header = (SRC / f'data/maps/headers/{name}.asm').read_text()
        const = re.search(r'map_header \w+, (\w+),', header)[1]
        obj = (SRC / f'data/maps/objects/{name}.asm').read_text()
        script = (SRC / f'scripts/{name}.asm').read_text()
        pointers = dict((b, a) for a, b in re.findall(r'dw_const\s+(\w+),\s*(TEXT_\w+)', script))
        rows = []
        for i, raw in enumerate(re.findall(r'^\s*object_event\s+([^;\n]+)', obj, re.M), 1):
            a = [v.strip() for v in raw.split(',')]
            row = dict(id=i, x=int(a[0]), y=int(a[1]), sprite=a[2], movement=a[3], facing=a[4], text=a[5])
            if len(a) == 7:
                row['item'] = a[6]
            if len(a) == 8:
                row['trainer'] = a[6].removeprefix('OPP_') + ':' + a[7]
                text_label = pointers.get(a[5], '')
                body = re.search(r'^' + re.escape(text_label) + r':\n(.*?)(?=^\w+:|\Z)', script, re.M | re.S)
                ref = re.search(r'ld hl, (\w+TrainerHeader\d+)', body[1]) if body else None
                trainer = re.search(r'^' + re.escape(ref[1]) + r':\n\s*trainer (\w+), (\d+),', script, re.M) if ref else None
                if trainer:
                    row.update(event=trainer[1], sight=int(trainer[2]))
            rows.append(row)
        warps = [dict(x=int(x), y=int(y), target=t, warp=int(n)) for x, y, t, n in
                 re.findall(r'warp_event\s+(\d+),\s*(\d+),\s*(\w+),\s*(\d+)', obj)]
        out[const] = dict(source=f'data/maps/objects/{name}.asm', script=f'scripts/{name}.asm',
                          header=f'data/maps/headers/{name}.asm', objects=rows, warps=warps)
    return out


def events():
    return {r['event'] for m in maps().values() for r in m['objects'] if 'event' in r} | {
        'EVENT_BEAT_MT_MOON_EXIT_SUPER_NERD', 'EVENT_GOT_DOME_FOSSIL', 'EVENT_GOT_HELIX_FOSSIL',
        'EVENT_BEAT_CERULEAN_RIVAL', 'EVENT_BEAT_CERULEAN_ROCKET_THIEF', 'EVENT_BEAT_ROUTE24_ROCKET', 'EVENT_GOT_NUGGET'}


def defeated(state, event):
    return state.get('teacher_events', {}).get(event, False)


def refresh_context(state, context):
    """Forget an observed person's old collision square when that person moves/hides."""
    map_ = state['place']['map']
    if map_ not in state.get('teacher_objects', {}):
        return
    current = state['teacher_objects'][map_]
    previous = {r['id']: r for r in context.get('sprite_positions', {}).get(map_, [])}
    moved = {(r['x'],r['y']) for i,r in previous.items() if any(
        n['id']==i and (n.get('hidden') or (n['x'],n['y'])!=(r['x'],r['y'])) for n in current)}
    context['walk_occupancy'] = [r for r in context.get('walk_occupancy', [])
                                 if r['map']!=map_ or tuple(r['tile']) not in moved]
    bump=context.get('walk_block', {})
    if bump.get('map')==map_ and tuple(bump.get('tile', [])) in moved:
        context.pop('walk_block', None)
    context['sprite_positions']={map_: current}


def sight(state, map_):
    """All unbeaten sight rays, plus coordinate-triggered fights. No wall assumption."""
    blocked = set()
    observed = {r['id']: r for r in state.get('teacher_objects', {}).get(map_, [])}
    for row in maps().get(map_, {}).get('objects', []):
        if 'event' not in row or defeated(state, row['event']):
            continue
        live = observed.get(row['id'], row)
        if live.get('hidden'):
            continue
        dx, dy = STEP.get(live.get('facing', row['facing']), (0, 0))
        blocked.update((live['x'] + dx*n, live['y'] + dy*n) for n in range(1, row['sight']+1))
    if map_ == 'MT_MOON_B2F' and not defeated(state, 'EVENT_BEAT_MT_MOON_EXIT_SUPER_NERD'):
        blocked.add((13, 8))
    if map_ == 'CERULEAN_CITY' and not defeated(state, 'EVENT_BEAT_CERULEAN_RIVAL'):
        blocked.update(((20, 6), (21, 6)))
    if map_ == 'CERULEAN_CITY' and not defeated(state, 'EVENT_BEAT_CERULEAN_ROCKET_THIEF'):
        blocked.update(((30, 7), (30, 9)))
    if map_ == 'ROUTE_24' and not defeated(state, 'EVENT_BEAT_ROUTE24_ROCKET'):
        blocked.add((10, 15))
    return blocked


def grid(state, map_, base):
    """Replace initial sprite squares with observed squares; hidden balls stop blocking."""
    if not base:
        return base
    people, balls = set(base['people']), set(base['balls'])
    rows = {r['id']: r for r in maps().get(map_, {}).get('objects', [])}
    for live in state.get('teacher_objects', {}).get(map_, []):
        row = rows.get(live['id'])
        if row:
            people.discard((row['x'], row['y']))
            balls.discard((row['x'], row['y']))
        if not live.get('hidden'):
            tile = (live['x'], live['y'])
            people.add(tile)
            if row and (row['sprite'] in ('SPRITE_POKE_BALL', 'SPRITE_FOSSIL')):
                balls.add(tile)
    if map_ == 'MT_MOON_B2F' and (defeated(state, 'EVENT_GOT_DOME_FOSSIL') or defeated(state, 'EVENT_GOT_HELIX_FOSSIL') or any(b['item'] in ('DOME_FOSSIL','HELIX_FOSSIL') and b.get('count',0)>0 for b in state.get('bag',[]))):
        # If no live visibility exists, the completed fossil scene removes both fossils.
        for row in rows.values():
            if row['sprite'] == 'SPRITE_FOSSIL' and not any(r['id']==row['id'] for r in state.get('teacher_objects', {}).get(map_, [])):
                people.discard((row['x'],row['y']))
                balls.discard((row['x'],row['y']))
    # Include moving people at their initial positions when no observation exists.
    observed_ids = {r['id'] for r in state.get('teacher_objects', {}).get(map_, [])}
    for row in rows.values():
        if row['id'] not in observed_ids and row['movement'] == 'WALK':
            people.add((row['x'], row['y']))
    return base if people==base["people"] and balls==base["balls"] else dict(base, people=people, balls=balls)


def memory(m, R, state):
    """Current map sprite coordinates and toggle flags. Off-screen is NOT hidden.

    Both symbol spellings are supported: checked-in sym predates the source rename.
    SpriteStateData2 +4/+5 includes the four-square border (ram/wram.asm).
    """
    event_flags = {e: R.event(m, e) for e in events() if e in R.EVENTS}
    map_ = state['place']['map']
    flag_name = 'wToggleableObjectFlags' if 'wToggleableObjectFlags' in R.SYM else 'wMissableObjectFlags'
    list_name = 'wToggleableObjectList' if 'wToggleableObjectList' in R.SYM else 'wMissableObjectList'
    hidden = {}
    for n in range(17):
        i = m[R.A(list_name)+2*n]
        if i == 255:
            break
        bit = m[R.A(list_name)+2*n+1]
        hidden[i] = bool(m[R.A(flag_name)+bit//8] & (1 << (bit%8)))
    live = []
    for row in maps().get(map_, {}).get('objects', []):
        i = row['id']
        if i > min(15, m[R.A('wNumSprites')]):
            continue
        one, two = R.A('wSpriteStateData1')+16*i, R.A('wSpriteStateData2')+16*i
        if not m[one]:
            continue  # transient/uninitialised data is unknown, never a proved hidden item
        x, y = m[two+5]-4, m[two+4]-4
        live.append(dict(id=i, x=x, y=y, hidden=hidden.get(i, False),
                         facing={0:'DOWN',4:'UP',8:'LEFT',12:'RIGHT'}.get(m[one+9], row['facing'])))
    return dict(teacher_events=event_flags, teacher_objects={map_: live})


if __name__ == '__main__':
    out = settings.KB / 'map_facts.json'
    out.write_text(json.dumps(maps(), indent=2)+'\n', encoding='utf-8')
    print(f'{len(maps())} maps -> {out}')
