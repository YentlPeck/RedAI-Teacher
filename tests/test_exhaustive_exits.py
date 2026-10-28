"""Replay answer() words on pokered grids, without an emulator or edited WRAM files."""
import copy
import json
import re
import subprocess
import sys
import time
import unittest
from collections import deque
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import settings  # noqa: E402
import advise as A
import read_state as R

MAPS = ("REDS_HOUSE_2F", "REDS_HOUSE_1F", "PALLET_TOWN", "OAKS_LAB", "ROUTE_1",
        "VIRIDIAN_CITY", "VIRIDIAN_MART", "VIRIDIAN_POKECENTER", "ROUTE_2",
        "VIRIDIAN_FOREST_SOUTH_GATE", "VIRIDIAN_FOREST", "VIRIDIAN_FOREST_NORTH_GATE",
        "PEWTER_CITY", "PEWTER_POKECENTER", "PEWTER_MART", "PEWTER_GYM")
COORD = re.compile(r"\((-?\d+),(-?\d+)\)")
MOVE = re.compile(r"\b(up|down|left|right) (\d+)\b|\bjump (up|down|left|right)\b")
PREFIXES = ("Our route on this map, from where you stand: ", "The way out, from where you stand: ",
            "The way to the training grass (ROUTE_2), from where you stand: ",
            "The checked bypass to Brock: ")


@contextmanager
def static_caches():
    """Memoize unchanged collision queries and pure team calculations, never answers/routes.

    gym1_plan appends to check['lines'], so each cached calculation needs a fresh copy.
    The same real party, badges and keys give the same fight result at every square.
    """
    moves, check, brock, sig_dist = A.W.moves, A.gym1_check, A.brock_route, A._sig_dist
    grids, fights, routes, components, signatures = {}, {}, {}, {}, {}
    graphs, distances = {}, {}
    read_text, source_text, reference = Path.read_text, {}, R.REF / "pokered"

    def cached_source(path, *args, **kwargs):
        if not path.is_relative_to(reference):
            return read_text(path, *args, **kwargs)
        key = (path, args, tuple(sorted(kwargs.items())))
        if key not in source_text:
            source_text[key] = read_text(path, *args, **kwargs)
        return source_text[key]

    def cached_moves(g, p, people=True, blocked=()):
        key = (id(g), p, people, frozenset(blocked))
        if key not in grids:
            grids[key] = tuple(moves(g, p, people=people, blocked=blocked))
        return iter(grids[key])

    def cached_check(state, margin=0.25, keys=None):
        key = (json.dumps([state["team"], state["badges"]], sort_keys=True), margin, tuple(keys or A.GYM1))
        if key not in fights:
            fights[key] = check(state, margin, keys)
        return copy.deepcopy(fights[key])

    def cached_sig(sig, prog):
        key = (id(sig), tuple(prog["done"]), tuple(prog["keys"]))
        if key not in signatures:
            signatures[key] = sig_dist(sig, prog)
        return signatures[key]

    def cached_path(map_, start, goals, people=True, blocked=()):
        """Same BFS result, with reverse distances shared by all starting squares.

        Follow the original direction order at every distance, preserving BFS ties.
        Edges are the real W.moves calls, including one-way ledges and NPC policy.
        """
        g = A.W.grid(map_)
        goals = frozenset(goals)
        if not g or start not in g["tile"]:
            return None
        key = (id(g), people, frozenset(blocked))
        if key not in graphs:
            forward, reverse = {}, {}
            for at in g["tile"]:
                forward[at] = tuple(cached_moves(g, at, people, blocked))
                for _, q in forward[at]:
                    reverse.setdefault(q, []).append(at)
            graphs[key] = forward, reverse
        forward, reverse = graphs[key]
        dk = (key, goals)
        if dk not in distances:
            dist = {q: 0 for q in goals if q in g["tile"]}
            todo = deque(dist)
            while todo:
                q = todo.popleft()
                for at in reverse.get(q, ()):
                    if at not in dist:
                        dist[at] = dist[q] + 1
                        todo.append(at)
            distances[dk] = dist
        dist = distances[dk]
        if start not in dist:
            return None
        out, at = [], start
        while dist[at]:
            d, at = next((d, q) for d, q in forward[at] if dist.get(q) == dist[at] - 1)
            out.append(d)
        return out

    def cached_brock(state):
        """Reuse real shortest-path suffixes; a failed strongly connected region stays failed.

        Only the same source map/LAST_MAP/blockers share results. Every cached positive
        route was produced by brock_route, and is independently replayed below if displayed.
        """
        m, p = state["place"]["map"], (state["place"]["x"], state["place"]["y"])
        key = (m, state["place"].get("last_map"), json.dumps(state.get("teacher_blocked", {}), sort_keys=True))
        known = routes.setdefault(key, {})
        if p in known:
            return copy.deepcopy(known[p])
        r = brock(state)
        known[p] = r
        if r:
            for i, ((src, at), _) in enumerate(r["steps"]):
                if src != m:
                    continue
                steps = r["steps"][i:]
                presses, out = [], None
                for ((map_, _), how) in steps:
                    if map_ != m:
                        break
                    if how[0] == "move":
                        presses.append(how[1])
                    else:
                        out = how
                        if how[0] == "edge":
                            presses.append(A.EDGE_WORD[how[2]][1])
                        break
                known[at] = dict(r, cost=len(steps), steps=steps, presses=presses, exit=out,
                                 maps=list(dict.fromkeys([m] + [s[0][0] for s in steps] + [r["target"][0]])))
        else:
            if key not in components:
                g = A.W.grid(m)
                blocked = {tuple(q) for q in state.get("teacher_blocked", {}).get(m, [])}
                if m == "PEWTER_GYM":
                    blocked |= {(x, 6) for x in range(3, 9)}
                warps = {(x, y) for x, y, _ in A._objects(m)[0]}
                forward, reverse = {}, {}
                for at, tile in g["tile"].items():
                    if tile not in g["walk"] or at in blocked:
                        continue
                    forward[at] = []
                    for d, q in cached_moves(g, at, blocked=blocked):
                        if q in warps and A._warp_on_entry(g, q, d):
                            continue
                        forward[at].append(q)
                        reverse.setdefault(q, []).append(at)
                components[key] = forward, reverse

            def reachable(graph):
                seen, todo = {p}, [p]
                for at in todo:
                    for q in graph.get(at, []):
                        if q not in seen:
                            seen.add(q)
                            todo.append(q)
                return seen

            forward, reverse = components[key]
            for at in reachable(forward) & reachable(reverse):
                known[at] = None
        return copy.deepcopy(r)

    with patch.object(A.W, "moves", cached_moves), patch.object(A, "gym1_check", cached_check), \
            patch.object(A, "brock_route", cached_brock), patch.object(A.W, "path", cached_path), \
            patch.object(A, "_sig_dist", cached_sig), patch.object(Path, "read_text", cached_source):
        yield


def states():
    before = R.state_from_wram((settings.fixture("start.wram")).read_bytes())
    starter = R.state_from_wram((settings.fixture("record-1831000065-v2/split-01.wram")).read_bytes())
    brock = R.state_from_wram((settings.fixture("record-1831000065-v2/split-02.wram")).read_bytes())
    dex = copy.deepcopy(brock)
    # A later, healthy party also exercises the gym-entry rather than training branch.
    ready = R.state_from_wram((settings.fixture("record-1831000065-v2/split-03.wram")).read_bytes())
    ready["story"] = copy.deepcopy(brock["story"])
    ready["badges"] = []
    for s in (before, starter, dex, ready):
        s.update(battle=None, text_box=False, part=1)
    return {"before_oak": before, "after_starter": starter, "after_pokedex": dex, "brock_next": ready}


def transition(map_, p, d):
    """Independent one-press oracle: collision first, then listed warp/edge-mat rules."""
    g = A.W.grid(map_)
    warps = {(x, y): t for x, y, t in A._objects(map_)[0]}
    dx, dy = A.W.STEP[d]
    q = dict(A.W.moves(g, p, people=False)).get(d)
    if q is not None:
        outward = (q[0] + dx, q[1] + dy) not in g["tile"]
        edge = q[0] in (0, g["w"] - 1) or q[1] in (0, g["h"] - 1)
        if q in warps and (g["tile"][q] in g["warp"] or not edge or outward):
            return q, warps[q]
        return q, None
    q = p[0] + dx, p[1] + dy
    if q not in g["tile"]:
        if p in warps:
            return p, warps[p]
        side = {"up": "north", "down": "south", "left": "west", "right": "east"}[d]
        connection = A._conns(map_).get(side)
        if connection:
            target, shift = connection
            tg = A.W.grid(target)
            dest = {"up": (p[0] + shift, tg["h"] - 1), "down": (p[0] + shift, 0),
                    "left": (tg["w"] - 1, p[1] + shift), "right": (0, p[1] + shift)}[d]
            if tg["tile"].get(dest) in tg["walk"]:
                return p, target
    raise AssertionError(f"blocked {d} from {p}")


def replay(map_, pos, text, must_exit=False, target=None):
    assert "go to (" not in text, "route teleports to an unchecked rejoin"
    presses = [(m[1] or m[3], int(m[2]) if m[2] else 1, m.start()) for m in MOVE.finditer(text)]
    count = sum(n for _, n, _ in presses)
    index, left = 0, None
    for d, n, _ in presses:
        for _ in range(n):
            pos, left = transition(map_, pos, d)
            index += 1
            if left and index != count:
                raise AssertionError(f"left early at {pos} via {d}: {index}/{count}")
    if must_exit and not left:
        raise AssertionError(f"route stopped at {pos} without leaving")
    if target and left not in (target, "LAST_MAP"):
        raise AssertionError(f"route leaves for {left}, expected {target}")
    return pos, left


def validate(s, a):
    map_ = s["place"]["map"]
    pos = s["place"]["x"], s["place"]["y"]
    exits = [d for d in a["details"] if d.startswith("The way to ") and
             (": walk off the " in d or "stairs / door at" in d)]
    declared_targets = []
    for line in exits:
        expected = re.search(r"first through (\w+)", line) or re.match(r"The way to (\w+)", line)
        expected = expected[1]
        declared_targets.append(expected)
        tile = tuple(map(int, COORD.search(line).groups()))
        if "stairs / door at" in line:
            assert tile in {(x, y) for x, y, _ in A._objects(map_)[0]}, f"invented warp {tile}"
            coords = list(COORD.finditer(line))
            stand = tuple(map(int, coords[1].groups()))
            step = re.search(r"walk (up|down|left|right) onto it", line)[1]
            _, target = transition(map_, stand, step)
            assert target, f"exit text does not leave from {stand} via {step} onto {tile}"
            assert (tile[0], tile[1], expected) in A._exits(map_, s["place"].get("last_map")), \
                f"warp {tile} does not lead to {expected}"
        else:
            side = re.search(r"\((north|south|east|west)\) edge", line)[1]
            _, target = transition(map_, tile, A.EDGE_WORD[side][1])
            assert target, f"invalid connected edge {tile}"
            assert target == expected, f"edge goes to {target}, not {expected}"
    route_count = 0
    for line in a["details"]:
        prefix = next((p for p in PREFIXES if line.startswith(p)), None)
        if prefix:
            # Story actions and local Brock walks intentionally stop inside the map.
            must_exit = bool(exits) or prefix != PREFIXES[0] and prefix != PREFIXES[3] or bool(
                re.search(r"\((out the door|into [A-Z]|off the (north|south|east|west) edge)", line))
            assert " ..." not in line or not must_exit, "exit route was truncated"
            replay(map_, pos, line[len(prefix):], must_exit=must_exit,
                   target=declared_targets[0] if len(declared_targets) == 1 else None)
            route_count += 1
    assert not exits or route_count, "exit text has no route"
    return route_count, len(exits)


def audit(shard=None, shards=12):
    global LAST_AUDIT
    start = time.perf_counter()
    if shard is None:
        # Short unit-test workers; no games or emulator processes. Each keeps
        # the verification runner's PyBoy / write guards and its own static caches.
        runner = Path(__file__).with_name("exit_worker.py")

        def run(i):
            mode = "worker-baseline" if Path(A.__file__).name == "north-gate-original-v8.py" else "worker"
            p = subprocess.run([sys.executable, "-B", str(runner), mode, str(i), str(shards)],
                               capture_output=True, text=True, check=True)
            return json.loads(p.stdout)

        with ThreadPoolExecutor(max_workers=shards) as pool:
            results = list(pool.map(run, range(shards)))
        failures = [f for r in results for f in r["failures"]]
        coverage = {}
        for r in results:
            for c in r["coverage"]:
                row = coverage.setdefault((c["map"], c["stage"]), dict(c, squares=0, routes=0, exits=0))
                for k in ("squares", "routes", "exits"):
                    row[k] += c[k]
        LAST_AUDIT = dict(elapsed_seconds=round(time.perf_counter() - start, 3), maps=len(MAPS),
                          cases=sum(r["cases"] for r in results), coverage=list(coverage.values()), failures=failures,
                          failed_cases=len(failures), failed_squares=len({(f["map"], tuple(f["pos"])) for f in failures}),
                          failed_maps=sorted({f["map"] for f in failures}), unit_workers=shards)
        return LAST_AUDIT
    presets, failures, coverage = states(), [], []
    ids = {name: id_ for id_, name in R.MAPS.items()}
    with static_caches():
        for map_ in MAPS:
            g = A.W.grid(map_)
            assert g is not None, map_
            # Include squares occupied by NPCs: they can move/hide. Item balls are fixed obstacles.
            squares = [p for p, tile in g["tile"].items() if tile in g["walk"] and p not in g["balls"]]
            # Exhaust every square in the stage where this map is normally used.
            # Other stages sample every warp, its approaches, record turns and a
            # central square. The gym also exhausts ready/unready party branches;
            # Pewter City uses the gym-bound party and samples the training branch.
            full = (("before_oak",) if map_ in ("REDS_HOUSE_2F", "REDS_HOUSE_1F", "PALLET_TOWN") else
                    ("after_starter",) if map_ in ("OAKS_LAB", "ROUTE_1", "VIRIDIAN_MART") else
                    ("after_pokedex", "brock_next") if map_ == "PEWTER_GYM" else
                    ("brock_next",) if map_ == "PEWTER_CITY" else
                    ("after_pokedex",))
            samples = {squares[len(squares) // 2]}
            for x, y, _ in A._objects(map_)[0]:
                samples.add((x, y))
                samples.update((x + dx, y + dy) for dx, dy in A.W.STEP.values())
            samples.update(tuple(p[:2]) for w in A.WALKS if w["map"] == map_ for p in w["points"])
            samples &= set(squares)
            for stage, base in presets.items():
                points = (squares if stage in full else sorted(samples))[shard::shards]
                routes = exits = 0
                for pos in points:
                    s = copy.deepcopy(base)
                    last = ("ROUTE_2" if "GATE" in map_ or map_ == "VIRIDIAN_FOREST" else
                            "PEWTER_CITY" if map_.startswith("PEWTER_") else
                            "VIRIDIAN_CITY" if map_.startswith("VIRIDIAN_") else "PALLET_TOWN")
                    s["place"].update(map=map_, map_id=ids[map_], x=pos[0], y=pos[1], last_map=last)
                    a = A.answer(s)
                    try:
                        r, e = validate(s, a)
                        routes += r
                        exits += e
                    except (AssertionError, KeyError, TypeError) as exc:
                        failures.append(dict(map=map_, pos=pos, stage=stage, error=str(exc), answer=a))
                coverage.append(dict(map=map_, stage=stage, squares=len(points), routes=routes, exits=exits))
    LAST_AUDIT = dict(elapsed_seconds=round(time.perf_counter() - start, 3), maps=len(MAPS),
                cases=sum(c["squares"] for c in coverage), coverage=coverage, failures=failures,
                failed_cases=len(failures), failed_squares=len({(f["map"], tuple(f["pos"])) for f in failures}),
                failed_maps=sorted({f["map"] for f in failures}))
    return LAST_AUDIT


class ExhaustiveExits(unittest.TestCase):
    def test_static_caches_preserve_real_answers(self):
        presets = states()
        cases = (("before_oak", "REDS_HOUSE_2F", (7, 1)),
                 ("before_oak", "REDS_HOUSE_1F", (4, 7)),
                 ("after_starter", "VIRIDIAN_CITY", (20, 30)),
                 ("after_pokedex", "VIRIDIAN_FOREST_NORTH_GATE", (4, 7)),
                 ("after_pokedex", "VIRIDIAN_FOREST", (1, 19)),
                 ("after_pokedex", "PEWTER_CITY", (18, 30)),
                 ("brock_next", "PEWTER_GYM", (4, 10)))
        for stage, map_, pos in cases:
            with self.subTest(stage=stage, map=map_):
                s = copy.deepcopy(presets[stage])
                s["place"].update(map=map_, x=pos[0], y=pos[1], last_map="ROUTE_2")
                expected = A.answer(s)
                with static_caches():
                    self.assertEqual(A.answer(s), expected)

    def test_replay_rejects_sideways_mat_entry_without_the_outward_press(self):
        with self.assertRaises(AssertionError):
            replay("REDS_HOUSE_1F", (4, 7), "left 1 to (3,7)", must_exit=True)
        self.assertEqual(replay("REDS_HOUSE_1F", (4, 7), "left 1 to (3,7), down 1 (out the door)",
                                must_exit=True)[1], "LAST_MAP")

    def test_every_walkable_square_before_brock(self):
        states()                  # skips here when the fixtures are missing (the workers would fail)
        result = audit()
        self.assertFalse(result["failures"], json.dumps({k: v for k, v in result.items() if k != "coverage"})[:16000])

    def test_reported_north_gate_positions_with_original_party(self):
        s = states()["after_pokedex"]
        for pos in ((4, 7), (4, 6), (3, 4), (5, 7), (5, 1), (4, 2), (5, 0)):
            with self.subTest(pos=pos):
                s["place"].update(map="VIRIDIAN_FOREST_NORTH_GATE", x=pos[0], y=pos[1], last_map="ROUTE_2")
                a = A.answer(s)
                validate(s, a)
                self.assertIn("door at (5,0)", " ".join(a["details"]))


if __name__ == "__main__":
    unittest.main()
