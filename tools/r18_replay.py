"""R18 replay check (no emulator): run the GUIDE over the logged states of finished games and report the steps found.

    python tools/r18_replay.py RUN_DIR [RUN_DIR ...] [--json OUT]

A play.py log row holds the place, story milestones, PokéBench milestones, money, battle/text flags; no team, bag or
screen. So the replay checks the step logic and the walks: which step each command would have shown, when each step
was first reached, how often the step went back (the player walked back), and whether a checked walk (GO) existed.
Steps that need team or bag facts (heal, train, Antidote) count as skipped here. Read only: run folders are not changed.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import read_state as R  # noqa: E402
import advise as A  # noqa: E402
import r18_guide as G  # noqa: E402

OUTDOOR = {n for i, n in R.MAPS.items() if i < len(A.TOWN_MAP)}


def replay(run_dir):
    rows = [json.loads(l) for l in (Path(run_dir) / "log.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    last_map, out, cache = None, [], {}
    for row in rows:
        if row.get("cmd") not in ("start", "press", "look"):
            continue
        s = G.state_from_row(row, last_map)
        bench = row.get("bench_milestones")
        f = G.facts(s, bench)
        i, st = G.current(f, s, A)
        mode = "battle" if s["battle"] else "text" if (s["text_box"] or s["intro"]) else "walk"
        go = None
        if st and mode == "walk":
            key = (st["id"], row["map"], row.get("x"), row.get("y"), last_map)
            if key not in cache:
                w = G.walk(st, s, A, None)
                cache[key] = None if w is None else w[1]
            go = cache[key]
        out.append(dict(n=row["n"], step=st["id"] if st else "done", index=(i + 1) if st else len(G.STEPS) + 1,
                        mode=mode, go_cost=go, map=row["map"]))
        if row["map"] in OUTDOOR:
            last_map = row["map"]
    return out


def summary(name, out):
    first, back, prev = {}, 0, 0
    for r in out:
        first.setdefault(r["step"], r["n"])
        if r["index"] < prev:
            back += 1
        prev = r["index"]
    walk = [r for r in out if r["mode"] == "walk" and r["step"] != "done"]
    return dict(run=name, commands=out[-1]["n"] if out else 0, steps_found=len(first),
                first_n={k: v for k, v in first.items()}, back_steps=back,
                rows_per_step=dict(Counter(r["step"] for r in out)),
                walk_rows=len(walk), walk_with_go=sum(1 for r in walk if r["go_cost"] is not None),
                walk_without_go=sorted({(r["map"], r["step"]) for r in walk if r["go_cost"] is None}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--json")
    a = ap.parse_args()
    res = [summary(Path(r).name, replay(r)) for r in a.runs]
    for s in res:
        print(f"{s['run']}: {s['commands']} commands, {s['steps_found']}/{len(G.STEPS)} steps found, "
              f"{s['back_steps']} step-backs, GO walk on {s['walk_with_go']}/{s['walk_rows']} walking rows")
        print("  first command per step: " + ", ".join(f"{k} n{v}" for k, v in s["first_n"].items()))
        if s["walk_without_go"]:
            print("  no checked walk at: " + "; ".join(f"{m} ({st})" for m, st in s["walk_without_go"]))
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
