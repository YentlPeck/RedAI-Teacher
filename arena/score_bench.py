"""PokéBench-style score for arena games (R16). Read only: opens no emulator and writes no file.

Per game: the furthest of the 10 milestones and the first command of each one (from the bench_milestones list
that play.py logs on every row). Rank: furthest milestone first, then fewer commands to reach it.
Our command n compares to PokéBench turn n (qwen_red.py checks state_after with the turn that produced it).

Run: python arena/score_bench.py RUN [RUN ...]        (games in REDAI_RUNS, default ~/redai-runs)
     add --json for the full result
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench  # noqa: E402
import settings  # noqa: E402

ARENA = settings.RUNS
ACCEPTED = {"look", "press", "ask"}


def summarize(rows, budget=1000):
    """First command of each milestone within the budget; rows are a play.py log."""
    first, used = {}, 0
    for row in rows:
        if row.get("cmd") in ACCEPTED:
            used += 1
            if used > budget:
                break
        elif row.get("cmd") != "start":
            continue                   # resume markers are not commands
        for key in row.get("bench_milestones", []):
            if key not in bench.KEYS:
                raise ValueError(f"unknown milestone {key!r}")
            first.setdefault(key, used)
        if bench.FINAL in first:
            break
    index = max((bench.KEYS.index(k) for k in first), default=-1)
    key = bench.KEYS[index] if index >= 0 else None
    # furthest_index: rung 1-10 on the ladder, 0 = no milestone
    return dict(furthest_index=index + 1, furthest_key=key, furthest_label=bench.LABELS.get(key),
                furthest_command=first.get(key), first_command={k: first[k] for k in bench.KEYS if k in first},
                commands_used=min(used, budget), beat_brock=bench.FINAL in first)


def rank_key(result):
    """Further is better; at the same milestone fewer commands is better (no milestone: all tie)."""
    cmd = result["furthest_command"]
    return (-result["furthest_index"], cmd if cmd is not None else float("inf"))


def score_game(folder):
    folder = Path(folder)
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (folder / "log.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return dict(run=folder.name, group=meta.get("group"), model=meta.get("model", ""),
                start=meta.get("start"), budget=meta.get("budget"),
                rules_ok=meta.get("start") == "power-on" and meta.get("budget") == 1000,
                **summarize(rows, meta.get("budget") or 1000))


def ranking(results):
    return sorted(results, key=rank_key)


def table(results):
    lines = ["rank  run                       model          furthest (of 10)              command"]
    for i, r in enumerate(ranking(results), 1):
        lines.append(f"{i:<5} {r['run']:<25} {r['model'][:14]:<14} {r['furthest_index']:>2} "
                     f"{(r['furthest_label'] or 'none'):<27} {r['furthest_command'] if r['furthest_command'] is not None else '-'}"
                     + ("" if r["rules_ok"] else "   (not PokéBench rules)"))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    results = [score_game(ARENA / r) for r in a.runs]
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(ranking(results), indent=1, ensure_ascii=False) if a.json else table(results))


if __name__ == "__main__":
    main()
