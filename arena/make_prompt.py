"""Fill PLAYER_PROMPT.md for one arena game. The plain and teacher prompts differ only in the `ask` lines.

Run: python arena/make_prompt.py RUN [plain|teacher [BUDGET]]
Optional legacy arguments assert metadata values; they never override the run.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import settings  # noqa: E402
ROOT = settings.REPO
ARENA = settings.RUNS
START = settings.START_STATE
POWER_ON = "power-on"             # R16: play.py start without --start-state
ASK = ('    {PY} arena/play.py ask {RUN} "your question"   <- a Pokémon Red teacher: ask what to do next, '
       'where to go, which move to use, or if your team is ready\n')


def prompt(run, group=None, budget=None):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", run) or run in (".", ".."):
        raise ValueError("unsafe run name")
    meta = json.loads((ARENA / run / "meta.json").read_text(encoding="utf-8"))
    if group is not None and group != meta["group"]:
        raise ValueError("group differs from the run")
    if budget is not None and budget != meta["budget"]:
        raise ValueError("budget differs from the run")
    group, budget = meta["group"], meta["budget"]
    if group not in ("plain", "teacher") or type(budget) is not int or budget <= 0:
        raise ValueError("run needs a valid group and positive budget")
    if meta["start"] == POWER_ON:      # R16: PokeBench rules, fresh boot
        start_line = ("The game starts from power-on (the Game Freak logo): pick NEW GAME once to begin "
                      "(this first NEW GAME is allowed).")
    else:
        start = Path(meta["start"])
        if not start.is_absolute():
            start = ROOT / start
        start_line = ("The game has already started: you stand in your bedroom "
                      "(Red's room, upstairs in your house in Pallet Town)."
                      if start.resolve() == START.resolve() else
                      "The game starts from a saved game in progress.")
    text = Path(__file__).with_name("PLAYER_PROMPT.md").read_text(encoding="utf-8")
    text = text.replace("{ASK_LINE}\n", (ASK if group == "teacher" else "") + "\n")
    text = text.replace("{ASK_COUNT}", ", ask" if group == "teacher" else "")
    return (text.replace("{ROOT}", str(ROOT)).replace("{PY}", "python")
            .replace("{RUN}", run).replace("{BUDGET}", str(budget)).replace("{START_LINE}", start_line))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run")
    ap.add_argument("group", nargs="?", choices=("plain", "teacher"))
    ap.add_argument("budget", nargs="?", type=int)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    print(prompt(args.run, args.group, args.budget))
