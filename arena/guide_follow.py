"""R18 smoke: a scripted player (no model) that only follows the GUIDE line, from power-on.

    python arena/guide_follow.py RUN [--max-commands 150] [--start-state PATH]

Starts a new lean + guided teacher run with play.py (one emulator at a time, play.py opens PyBoy with an empty 32 KB
ram_file), then each turn presses the keys after "GO:" or "PRESS:" in the newest GUIDE line (look when none).
Writes RUN/follow.jsonl (n, keys, guide step, place) and prints a short summary: last step, PokéBench milestones.
"""
import argparse
import json
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import settings  # noqa: E402
HERE = Path(__file__).resolve().parent
ROOT = settings.REPO
PLAY = HERE / "play.py"
PY = Path(sys.executable)
RUNS = settings.RUNS
TOKEN = re.compile(r"^(?:a\*|(?:up|down|left|right|a|b|start|select)(?:\*\d+)?)$")


def keys_from(guide_line):
    """The button tokens right after GO: or PRESS: (the first one in the line); [] if none. Sol R18: no silent
    trimming; the keys must pass the real lean parser (max 6 presses), else the run stops with an error."""
    import lean_player
    m = re.search(r"\b(?:GO|PRESS): (.*)", guide_line or "")
    out = []
    for tok in (m.group(1).split() if m else []):
        if not TOKEN.match(tok):
            break
        out.append(tok)
    if out:
        lean_player.parse_buttons(" ".join(out))      # raises BadReply on more than 6 presses
    return out


def call(args, run):
    import os
    env = dict(os.environ, LEAN_PLAYER_TURN=f"{run}-{uuid.uuid4().hex}")
    p = subprocess.run([str(PY), str(PLAY), args[0], run, *args[1:]], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=ROOT, env=env, timeout=600)
    return p.returncode, p.stdout, p.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--max-commands", type=int, default=150)
    ap.add_argument("--start-state", help="saved game to start from (a check of one situation); default power-on")
    a = ap.parse_args()
    run = RUNS / a.run
    if run.exists():
        raise SystemExit(f"{run} exists: use a new run name")
    rc, out, err = call(["start", "--group", "teacher", "--model", "scripted-follower", "--budget",
                         str(a.max_commands), "--lean", "--guide",
                         *(["--start-state", a.start_state] if a.start_state else [])], a.run)
    if rc:
        raise SystemExit(err[-500:])
    last = out
    for n in range(1, a.max_commands + 1):
        line = next((l for l in last.splitlines() if l.startswith("GUIDE")), "")
        try:
            keys = keys_from(line)
        except Exception as e:                       # lean_player.BadReply: the guide gave an invalid command
            print(f"n{n}: invalid guide keys: {e} | {line[:200]}")
            break
        time.sleep(1.05)             # guard cooldown
        rc, out, err = call(["press", *keys] if keys else ["look"], a.run)
        row = json.loads((run / "log.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        with open(run / "follow.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(n=n, keys=keys, rc=rc, guide=line, err=err[-300:] if rc else "",
                                     step=row.get("guide"), map=row.get("map"), x=row.get("x"), y=row.get("y")),
                                ensure_ascii=False) + "\n")
        if rc:
            print(f"n{n}: play.py rc {rc}: {err[-300:]}")
            break
        last = out
        if "Done: you have the Boulder Badge" in out:
            break
    rows = [json.loads(l) for l in (run / "log.jsonl").read_text(encoding="utf-8").splitlines()]
    print(json.dumps(dict(commands=len(rows) - 1, last_step=rows[-1].get("guide"), map=rows[-1].get("map"),
                          bench=rows[-1].get("bench_milestones"), story=rows[-1].get("done")), ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
