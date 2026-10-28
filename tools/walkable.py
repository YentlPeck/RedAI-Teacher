"""Round 6: which tiles of a map a player can walk on, from the game's own map data (reference/pokered), and the
shortest real path between two tiles (breadth-first search).

Why: off the record's path the teacher said "go to (2,22)", a straight line through trees (forest walk, 21 Oct).
How the game decides (pokered): a map is blocks of 4x4 tiles; one walking square is 2x2 tiles; the game checks the
lower-left tile of the square against the tileset's walkable list (collision_tile_ids.asm). Some tile pairs may not
be crossed (pair_collision_tile_ids.asm, elevation in forests and caves). Ledges (ledge_tiles.asm, outdoors) can only
be jumped down / left / right and move the player two squares. People and item balls that stand still block a square.
"""
import functools
import re
from collections import deque
from pathlib import Path

import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import settings  # noqa: E402

P = settings.POKERED
STEP = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
LEDGE_FACING = {"SPRITE_FACING_DOWN": "down", "SPRITE_FACING_LEFT": "left", "SPRITE_FACING_RIGHT": "right"}


def _camel(const):
    return "".join(w.capitalize() for w in const.split("_"))


def _tile_lists(text, macro):
    """Tile lists can share labels or fall through db bytes into the next list."""
    lists, active = {}, []
    for line in text.splitlines():
        line = line.split(";", 1)[0]
        label = re.match(r"^(\.\w+):", line)
        if label:
            active.append(label[1])
            lists[label[1]] = set()
        elif active:
            tiles = {int(h, 16) for h in re.findall(r"\$([0-9a-fA-F]{2})", line)}
            for lab in active:
                lists[lab].update(tiles)
            if re.match(rf"\s*{macro}\b", line):
                active = []
    return lists


@functools.lru_cache(None)
def _tables():
    txt = (P / "constants" / "tileset_constants.asm").read_text()
    tilesets = re.findall(r"^\s*const (\w+)", txt, re.M)
    names = re.findall(r"^\s*tileset (\w+),", (P / "data" / "tilesets" / "tileset_headers.asm").read_text(), re.M)
    blocks, labels = {}, []
    for line in (P / "gfx" / "tilesets.asm").read_text().splitlines():
        labels += re.findall(r"(\w+)_Block::", line)
        m = re.search(r'INCBIN "(gfx/blocksets/[^"]+)"', line)
        if m and labels:
            for lab in labels:
                blocks[lab] = m.group(1)
            labels = []
        elif not line.strip().endswith("::") and "_Block::" not in line:
            labels = [] if "INCBIN" in line else labels
    coll, labs = {}, []
    for line in (P / "data" / "tilesets" / "collision_tile_ids.asm").read_text().splitlines():
        labs += re.findall(r"^(\w+)_Coll::", line)
        if "coll_tiles" in line and labs and "MACRO" not in line:
            coll.update({lab: {int(h, 16) for h in re.findall(r"\$([0-9a-fA-F]{2})", line)} for lab in labs})
            labs = []
    warp_text = (P / "data/tilesets/warp_tile_ids.asm").read_text()
    warp_lists = _tile_lists(warp_text, "warp_tiles")
    warps = {ts: set(warp_lists[lab]) for ts, lab in
             zip(tilesets, re.findall(r"^\s*dw (\.\w+)", warp_text, re.M))}
    door_text = (P / "data/tilesets/door_tile_ids.asm").read_text()
    door_lists = _tile_lists(door_text, "door_tiles")
    for ts, lab in re.findall(r"dbw\s+(\w+),\s*(\.\w+)", door_text):
        warps[ts].update(door_lists[lab])
    pairs = {}
    for ts, a, b in re.findall(r"db (\w+), \$([0-9A-Fa-f]{2}), \$([0-9A-Fa-f]{2})",
                               (P / "data" / "tilesets" / "pair_collision_tile_ids.asm").read_text()):
        pairs.setdefault(ts, set()).update({(int(a, 16), int(b, 16)), (int(b, 16), int(a, 16))})
    ledges = [(LEDGE_FACING[f], int(s, 16), int(t, 16)) for f, s, t in
              re.findall(r"db (SPRITE_FACING_\w+),\s*\$(\w\w), \$(\w\w)", (P / "data" / "tilesets" / "ledge_tiles.asm").read_text())]
    dims = {c: (int(w), int(h)) for c, w, h in
            re.findall(r"map_const (\w+),\s*(\d+),\s*(\d+)", (P / "constants" / "map_constants.asm").read_text())}
    blk, labs = {}, []
    for line in (P / "maps.asm").read_text().splitlines():
        labs += re.findall(r"(\w+)_Blocks:", line)
        m = re.search(r'INCBIN "(maps/[^"]+\.blk)"', line)
        if m:
            blk.update({lab: m.group(1) for lab in labs})
            labs = []
    return dict(tilesets=tilesets, names=names, blocks=blocks, coll=coll, warps=warps,
                pairs=pairs, ledges=ledges, dims=dims, blk=blk)


@functools.lru_cache(None)
def grid(map_const):
    """Per square (x, y): the tile id the game checks, plus the squares that people / item balls block.
    None if the map's data cannot be found."""
    t = _tables()
    if map_const not in t["dims"]:
        return None
    name = None
    for f in (P / "data" / "maps" / "headers").glob("*.asm"):
        m = re.search(r"map_header (\w+), (\w+), (\w+)", f.read_text())
        if m and m.group(2) == map_const:
            name, tileset = m.group(1), m.group(3)
            break
    if not name or name not in t["blk"]:
        return None
    ts_name = t["names"][t["tilesets"].index(tileset)]
    bst = (P / t["blocks"][ts_name]).read_bytes()
    w, h = t["dims"][map_const]
    blocks = (P / t["blk"][name]).read_bytes()
    if len(blocks) != w * h:          # label / size mismatch: better no answer than a wrong one
        return None
    tile = {}
    for y in range(h * 2):
        for x in range(w * 2):
            b = blocks[(y // 2) * w + x // 2]
            tile[(x, y)] = bst[b * 16 + (2 * (y % 2) + 1) * 4 + 2 * (x % 2)]
    obj = (P / "data" / "maps" / "objects" / f"{name}.asm")
    people, balls = set(), set()
    if obj.exists():
        for x, y, sprite, move in re.findall(r"object_event\s+(\d+),\s*(\d+),\s*(\w+),\s*(\w+)", obj.read_text()):
            if move == "STAY":
                (balls if sprite == "SPRITE_POKE_BALL" else people).add((int(x), int(y)))
    return dict(tile=tile, w=w * 2, h=h * 2, walk=t["coll"][ts_name], warp=t["warps"][tileset],
                pairs=t["pairs"].get(tileset, set()),
                ledges=t["ledges"] if tileset == "OVERWORLD" else [], people=people | balls, balls=balls)


def moves(g, p, people=True, blocked=()):
    """Squares reachable from p in one press: (direction, new square). people=False: only item balls block, not
    people (they move, hide, get up or are boulders; our record game knows where they really were)."""
    here = g["tile"].get(p)
    g = g if people else dict(g, people=g["balls"])
    for d, (dx, dy) in STEP.items():
        q = (p[0] + dx, p[1] + dy)
        if q not in g["tile"] or q in blocked:
            continue
        nt = g["tile"][q]
        if any(d == f and here == s and nt == lt for f, s, lt in g["ledges"]):
            j = (q[0] + dx, q[1] + dy)
            if j in g["tile"] and g["tile"][j] in g["walk"] and j not in g["people"] and j not in blocked:
                yield d, j
            continue
        if nt in g["walk"] and q not in g["people"] and (here, nt) not in g["pairs"]:
            yield d, q


def path(map_const, start, goals, people=True, blocked=()):
    """Shortest list of presses from start to the nearest of goals (a set of squares); None if no way is known."""
    g = grid(map_const)
    goals = set(goals)
    if not g or start not in g["tile"]:
        return None
    seen, todo = {start: None}, deque([start])
    while todo:
        p = todo.popleft()
        if p in goals:
            out = []
            while seen[p]:
                d, p = seen[p]
                out.append(d)
            return out[::-1]
        for d, q in moves(g, p, people, blocked):
            if q not in seen:
                seen[q] = (d, p)
                todo.append(q)
    return None


def legs(presses, start):
    """["up", "up", "left"] -> ["up 2 to (x,y)", "left 1 to (x,y)"]; a ledge jump moves two squares."""
    out, (x, y) = [], start
    g = None
    for d in presses:
        dx, dy = STEP[d]
        x, y = x + dx, y + dy
        if out and out[-1][0] == d:
            out[-1] = (d, out[-1][1] + 1, (x, y))
        else:
            out.append((d, 1, (x, y)))
    return [f"{d} {n} to ({p[0]},{p[1]})" for d, n, p in out]
