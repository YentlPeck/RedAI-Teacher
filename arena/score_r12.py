"""Read-only R11 accepted-row scorer; no emulator or scratch-script imports.

Usage: python arena/score_r12.py ORDER_FILE --wave segment|full
Order: eight RUN GROUP MODEL lines, adjacent matched plain/teacher pairs.
Early finals need RUN: stopped/finished/... in sibling *_notes.txt, as in R10.
After a resume only RUN: AFTER resume finished; ... finalizes an early AFTER.
JSON goes to stdout. Freeze order, inputs and threshold arguments before play.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import settings  # noqa: E402

ARENA = settings.RUNS
ACCEPTED = {"look", "press", "ask"}
RESUME_MESSAGE = "Continue playing with the same commands until all {budget} commands are used."
# reference/pokered/constants/map_constants.asm and constants/ram_constants.asm.
ROUTE_4, CERULEAN_CITY = 0x0F, 0x03
MT_MOON_B1F = 0x3C
CASCADE_MASK = 1 << 1
WAVES = {"segment": (650, 500), "full": (1200, 950)}
# Frozen from states/post_brock_pewter.json, checked against the two state files.
# A budget change must never promote segment evidence to a full game.
WAVE_STARTS = {
    "full": ("teacher/arena/start.state", "9ab602dbf9643cd7250f4bd5aa8bfe0696e5ccdf2d1faa788acacf7ad435f7dd"),
    "segment": ("teacher/dev-r23/states/post_brock_pewter.state", "8e38582ef77211be6260b609207f79dc913279328308732e1b56c02dd53788e7"),
}
ROOT = settings.REPO


def validate_start(game, wave):
    expected_path, expected_hash = WAVE_STARTS[wave]
    path = Path(str(game.get("start", "")).replace("\\", "/"))
    resolved = path.resolve() if path.is_absolute() else (ROOT / path).resolve()
    if resolved != (ROOT / expected_path).resolve() or game.get("start_sha256") != expected_hash:
        raise ValueError(f"{game.get('run', '')}: wrong {wave} wave start provenance")


def verified_exit(edge):
    return (edge.get("source") == [MT_MOON_B1F, 27, 3]
            and edge.get("destination") == [ROUTE_4, 24, 5]
            and edge.get("cause") == "doorway")


def read_order(path):
    games = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        parts = line.split("#", 1)[0].split()
        if not parts:
            continue
        if len(parts) != 3:
            raise ValueError(f"{path}:{line_no}: expected RUN GROUP MODEL")
        run, group, model = parts
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", run) or run in (".", ".."):
            raise ValueError(f"unsafe run name: {run}")
        if group not in ("plain", "teacher"):
            raise ValueError(f"unknown group: {group}")
        games.append(dict(run=run, group=group, model=model))
    validate_pairs(games)
    return games


def validate_pairs(games):
    if len(games) != 8 or len({g["run"] for g in games}) != 8:
        raise ValueError("expected eight distinct games")
    for a, b in zip(games[::2], games[1::2]):
        if {a["group"], b["group"]} != {"plain", "teacher"} or a["model"] != b["model"]:
            raise ValueError("adjacent pairs need one plain and one teacher game of the same model")


def completion_evidence(run, notes, after_resume=False):
    short = re.sub(r"-(?:haiku|luna)-(?:plain|teacher)$", "", run)
    names = "|".join(re.escape(n) for n in sorted({run, short}, key=len, reverse=True))
    for line in reversed(notes.splitlines()):
        match = re.match(rf"^\s*(?:{names})\s*([:|])(.*)$", line, re.I)
        if not match:
            continue
        tail = match[2].strip()
        if after_resume:
            if re.match(r"AFTER resume finished(?:\s|;|$)", tail, re.I) and match[1] == ":":
                return line.strip()
        elif (re.search(r"\b(?:done|finished|completed|stopped|ended)\b", tail, re.I)
              or match[1] == "|" and re.search(r"\b\d+\s+(?:cmds|commands)\b", tail, re.I)):
            return line.strip()
    return None


def read_segments(path, budget):
    """Validate sequence, accepted rows and the one zero-cost neutral resume (R10 rules)."""
    rows, marker, boundary, warnings = [], None, None, []
    lines = [line for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    for index, line in enumerate(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            if index == len(lines) - 1:
                warnings.append("Partial final JSON row; game kept in progress")
                break
            raise ValueError(f"{path}:{index + 1}: invalid interior JSON") from error
        if not isinstance(row, dict):
            raise ValueError(f"{path}: expected an object")
        if row.get("cmd") == "resume":
            used = len(rows) - 1
            if marker is not None or not 0 <= used < budget:
                raise ValueError(f"{path}: invalid or repeated resume marker")
            if (row.get("n") != used or row.get("accepted_commands") != used
                    or row.get("resume_index") != 1 or row.get("budget") != budget
                    or row.get("message") != RESUME_MESSAGE.format(budget=budget)
                    or not row.get("player_ref") or not row.get("stop_ref")):
                raise ValueError(f"{path}: malformed resume marker")
            if any(row.get(k) != rows[-1].get(k) for k in ("map", "done")):
                raise ValueError(f"{path}: resume changes game observations")
            marker, boundary = row, used
            continue
        if type(row.get("n")) is not int or row["n"] != len(rows):
            raise ValueError(f"{path}: n must be consecutive from zero")
        if row.get("cmd") not in ({"start"} if not rows else ACCEPTED):
            raise ValueError(f"{path}: unexpected/rejected command row")
        if not isinstance(row.get("map"), str) or not isinstance(row.get("done"), list):
            raise ValueError(f"{path}: missing map/done")
        if type(row.get("map_id")) is not int or not 0 <= row["map_id"] <= 255:
            raise ValueError(f"{path}: missing/invalid map_id")
        for name, map_id in (("ROUTE_4", ROUTE_4), ("CERULEAN_CITY", CERULEAN_CITY), ("MT_MOON_B1F", MT_MOON_B1F)):
            if (row["map"] == name) != (row["map_id"] == map_id):
                raise ValueError(f"{path}: map name/id mismatch")
        if rows and (type(row.get("badges_byte")) is not int or not 0 <= row["badges_byte"] <= 255):
            raise ValueError(f"{path}: missing/invalid raw badges_byte")
        transitions = row.get("map_transitions", [])
        if not isinstance(transitions, list) or any(
                not isinstance(edge, dict)
                or any(not isinstance(edge.get(k), list) or len(edge[k]) != 3
                       or any(type(v) is not int or not 0 <= v <= 255 for v in edge[k])
                       for k in ("source", "destination"))
                or edge.get("cause") not in (None, "doorway", "escape_warp", "blackout")
                for edge in transitions):
            raise ValueError(f"{path}: invalid/ambiguous map transitions; coordinates required")
        rows.append(row)
    if not rows:
        warnings.append("No complete start row yet; game kept in progress")
    return (rows[0] if rows else None), rows[1:], warnings, marker, boundary


def progress(rows, start, budget, evidence=None, warnings=()):
    capped = rows[:budget]
    complete = not warnings and (len(rows) >= budget or evidence is not None)
    first = {}
    for row in capped:
        map_id = row["map_id"]
        # data/maps/objects/Route4.asm: warp 3 -> MT_MOON_B1F warp 8 (24,5).
        # Require verified doorway evidence, even if later presses in this command
        # move on. Map IDs/end-of-command coordinates cannot distinguish a Rope.
        if any(verified_exit(edge) for edge in row.get("map_transitions", [])):
            first.setdefault("T1", row["n"])
        if map_id == CERULEAN_CITY:
            first.setdefault("T2", row["n"])
        if row["badges_byte"] & CASCADE_MASK:
            first.setdefault("T3", row["n"])
    ts = {key: first.get(key, budget if complete else None) for key in ("T1", "T2", "T3")}
    return dict(status="complete" if complete else "in progress", commands_used=len(capped),
                commands_logged=len(rows), completion_evidence=(f"{budget} command rows logged" if len(rows) >= budget else evidence),
                early_stop=(len(capped) < budget if complete else None),
                first_arrivals_observed=first, **ts,
                C=sum(ts.values()) / 3 if complete else None,
                badge_by_cap=(True if "T3" in first else False if complete else None),
                asks=sum(row["cmd"] == "ask" for row in capped), warnings=list(warnings))


def score_game(game, arena=ARENA, notes="", expected_budget=None):
    folder = arena / game["run"]
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    budget = meta["budget"]
    if type(budget) is not int or budget <= 0 or expected_budget is not None and budget != expected_budget:
        raise ValueError(f"{folder}: invalid/mixed wave budget")
    if any(meta.get(k) != game[k] for k in ("group", "model")):
        raise ValueError(f"{folder}: order/meta group or model mismatch")
    if (not isinstance(meta.get("start"), str) or not meta["start"]
            or not isinstance(meta.get("start_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", meta["start_sha256"])):
        raise ValueError(f"{folder}: missing/invalid start provenance")
    wave = next((w for w, (cap, _) in WAVES.items() if cap == budget), None)
    if wave is None:
        raise ValueError(f"{folder}: unregistered wave budget")
    validate_start(dict(meta, run=game["run"]), wave)
    path = folder / "log.jsonl"
    if not path.is_file():
        empty = progress([], None, budget)
        empty.update(status="missing", commands_used=None, commands_logged=None, asks=None)
        return dict(game, budget=budget, start=meta["start"], start_sha256=meta["start_sha256"],
                    before=empty, after=dict(empty), resume=None)
    start, rows, warnings, marker, boundary = read_segments(path, budget)
    if start and any(start.get(k) != meta.get(k) for k in ("budget", "start", "start_sha256")):
        raise ValueError(f"{folder}: init/meta budget or start provenance mismatch")
    after = progress(rows, start, budget, completion_evidence(game["run"], notes, marker is not None), warnings)
    before = (progress(rows[:boundary], start, budget, "stopped at logged first-stop boundary")
              if marker else dict(after))
    return dict(game, budget=budget, start=meta.get("start"), start_sha256=meta.get("start_sha256"),
                before=before, after=after, resume=marker)


def summarize(games, label, mean_c_max, pair_wins_min=3, teacher_badges_min=1):
    teachers = [g[label] for g in games if g["group"] == "teacher"]
    complete = all(g[label]["status"] == "complete" for g in games)
    teacher_complete = all(g["status"] == "complete" for g in teachers)
    mean = sum(g["C"] for g in teachers) / 4 if teacher_complete else None
    pairs = []
    for index in range(0, 8, 2):
        pair = games[index:index + 2]
        plain = next(g for g in pair if g["group"] == "plain")
        teacher = next(g for g in pair if g["group"] == "teacher")
        finished = all(g[label]["status"] == "complete" for g in pair)
        pairs.append(dict(pair=index // 2 + 1, plain=plain["run"], teacher=teacher["run"],
                          plain_C=plain[label]["C"], teacher_C=teacher[label]["C"],
                          teacher_wins=teacher[label]["C"] < plain[label]["C"] if finished else None))
    wins = sum(p["teacher_wins"] is True for p in pairs)
    badges = sum(g["badge_by_cap"] is True for g in teachers)
    conditions = dict(teacher_mean_C=mean <= mean_c_max if mean is not None else None,
                      pair_wins=wins >= pair_wins_min if complete else None,
                      teacher_badges=badges >= teacher_badges_min if teacher_complete else None)
    return dict(verdict="PENDING" if not complete else "KEEP" if all(conditions.values()) else "REWORK/DROP",
                teacher_mean_C=mean, teacher_pair_wins=wins, teacher_badges_by_cap=badges,
                plain_badges_by_cap=sum(g[label]["badge_by_cap"] is True for g in games if g["group"] == "plain"),
                complete_games=sum(g[label]["status"] == "complete" for g in games),
                pairs=pairs, conditions=conditions)


def make_report(games, wave, mean_c_max=None, pair_wins_min=3, teacher_badges_min=1):
    validate_pairs(games)
    budget, default_threshold = WAVES[wave]
    if any(g["budget"] != budget for g in games):
        raise ValueError("mixed/wrong wave budgets")
    for a, b in zip(games[::2], games[1::2]):
        if a.get("start_sha256") != b.get("start_sha256"):
            raise ValueError("paired games have unequal starting states")
    for game in games:
        validate_start(game, wave)
    threshold = default_threshold if mean_c_max is None else mean_c_max
    if not math.isfinite(threshold) or threshold < 0 or not 0 <= pair_wins_min <= 4 or not 0 <= teacher_badges_min <= 4:
        raise ValueError("invalid KEEP thresholds")
    before = summarize(games, "before", threshold, pair_wins_min, teacher_badges_min)
    after = summarize(games, "after", threshold, pair_wins_min, teacher_badges_min)
    return dict(round=11, wave=wave, budget=budget, expected_start=WAVE_STARTS[wave][0],
                expected_start_sha256=WAVE_STARTS[wave][1], primary="after", verdict=after["verdict"],
                thresholds=dict(mean_C_max=threshold, pair_wins_min=pair_wins_min, teacher_badges_min=teacher_badges_min),
                before=before, after=after, games=games, resumes=sum(g["resume"] is not None for g in games))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("order_file", type=Path)
    ap.add_argument("--arena", type=Path, default=ARENA)
    ap.add_argument("--notes", type=Path)
    ap.add_argument("--wave", choices=WAVES, required=True)
    ap.add_argument("--mean-c-max", type=float)
    ap.add_argument("--pair-wins-min", type=int, default=3)
    ap.add_argument("--teacher-badges-min", type=int, default=1)
    args = ap.parse_args()
    try:
        order = args.order_file.expanduser().resolve()
        games = read_order(order)
        notes_path = args.notes or order.with_name(order.stem.replace("_order", "") + "_notes.txt")
        notes = notes_path.read_text(encoding="utf-8-sig") if notes_path.is_file() else ""
        scored = [score_game(g, args.arena.expanduser().resolve(), notes, WAVES[args.wave][0]) for g in games]
        report = make_report(scored, args.wave, args.mean_c_max, args.pair_wins_min, args.teacher_badges_min)
        report.update(order_file=str(order), notes_file=str(notes_path))
        print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError) as error:
        ap.exit(2, f"score_r12: {error}\n")


if __name__ == "__main__":
    main()
