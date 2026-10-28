"""The arena: a small command tool an AI agent uses to play Pokémon Red (Phase 2, step 4).

Each command loads the game, does one thing, saves the game and prints what the player sees. One emulator runs only
while a command runs. Both modes show the same game view; `ask` requires a teacher.

    python arena/play.py start RUN --group plain|teacher [--budget 1000] [--model NAME] [--start-state PATH]
                                         (no --start-state = fresh power-on boot at the Game Freak logo, R16)
    python arena/play.py look RUN                       what you see now (also saves screen.png)
    python arena/play.py press RUN up up a right*3 b    press buttons (max 6 per command)
    python arena/play.py ask RUN "what should I do?"    ask the teacher
    python arena/play.py score RUN                      show the saved report
    (R17) start ... --lean: the run is driven by arena/lean_player.py, one model call per command; each command must
    carry the loop's one-time turn key in the LEAN_PLAYER_TURN environment variable.
    (R18) start ... --guide (teacher group only): every start / look / press view begins with a GUIDE block
    (tools/r18_guide.py, built from RAM each time); the old automatic TEACHER notes are not shown in guided runs.

Buttons: up down left right a b start select; "right*3" = right 3 times. A direction walks one tile (or turns /
bumps when blocked). R17: "a*" (one press slot) = press A until the text box closes or a choice / menu / battle
decision shows (a filled cursor), waiting for stable text before each A, at most 30 A; it never presses A once the
box is closed, so it never talks to the same person again (PokéBench's a_until_dialog_end). Runs live in REDAI_RUNS/RUN/ (default ~/redai-runs; game.state, screen.png, log.jsonl, meta.json).
R16 (PokéBench rules): every row logs the PokéBench milestones reached so far (bench.py); after the Boulder Badge
the game is done and no more commands run. No battery save is ever read or written (ram_file is an empty buffer).
"""
import argparse
import io
import hashlib
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import settings  # noqa: E402
ROOT = settings.REPO
ROM_RAM = settings.ROM_RAM
import read_state as R  # noqa: E402
import guard  # noqa: E402  (one command at a time, round 5 on; arena/ is on sys.path when run as a script)
import bench  # noqa: E402  (R16: PokéBench milestones)

ARENA = settings.RUNS
START = settings.START_STATE
BUTTONS = {"up", "down", "left", "right", "a", "b", "start", "select"}
MAX_PRESSES = 6                    # R16: PokéBench allows at most 6 actions per turn
BOOT_FRAMES = 360                  # R16: power-on until the Game Freak logo shows (copyright screen ends ~frame 280)
DEFAULT_BUDGET = 1000              # R16: PokéBench turn budget
FACING = {0: "down", 4: "up", 8: "left", 12: "right"}
ACCEPTED_COMMANDS = {"look", "press", "ask"}
RESUME_MESSAGE = "Continue playing with the same commands until all {budget} commands are used."
LEAN_ENV = "LEAN_PLAYER_TURN"      # R17: per-turn key from arena/lean_player.py
A_STAR = "a*"                      # R17 (round b2): A until the text ends or a choice shows, one press slot
A_STAR_CAP = 30                    # hard cap of A presses inside one a*
SETTLE_FRAMES = 10                 # the screen text and cursor must stay the same this long before the next A
SETTLE_MAX = 240                   # never wait longer than this for stable text (animations, the title screen)
CURSOR = 0xED                      # "▶" (constants/charmap.asm): menus, YES/NO, naming and battle menus draw it


def lean_key(run):
    """R17: guard key for runs started with --lean, else None (old runs and normal players: unchanged).

    The lean loop starts every play.py call as a subprocess of one loop process, so all calls share one outer
    shell and guard.py would refuse the second one. The loop gives each turn a fresh key instead; the guard still
    refuses a second call with the same key (one command per turn), parallel calls (lock) and calls < 1 s apart."""
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
    if meta.get("player") != "lean":
        return None
    token = os.environ.get(LEAN_ENV, "")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{8,120}", token):
        raise SystemExit("This game is played through lean_player.py only. No command was used.")
    return f"lean:{token}"


def use_lean_key(run, key):
    """R17 fix round: refuse a turn key that any earlier call used (guard.py only compares with the LAST key).
    Called while holding the guard lock, so check-and-record cannot race. The refusal goes to blocked.jsonl
    through guard (not a command); used keys are kept in lean_keys.txt (never rewritten, only appended)."""
    used = run / "lean_keys.txt"
    seen = set(used.read_text(encoding="utf-8").split()) if used.exists() else set()
    if key in seen:
        guard._refuse(run, time.time(), key, "this turn key was used before")
    with open(used, "a", encoding="utf-8") as fh:
        fh.write(key + "\n")


def history_rows(run):
    return [json.loads(line) for line in (run / "log.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def commands_used(rows):
    return sum(row.get("cmd") in ACCEPTED_COMMANDS for row in rows)


def count_line(run):
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
    return f"Commands used: {commands_used(history_rows(run))} of {meta['budget']}"


def resume(run, player_ref, stop_ref):
    """Coordinator only: record the first stop before sending the one fixed reminder.

    References identify the saved player session/thread and original final response for audit.
    No emulator, game state, meta, cooldown or teacher context is opened or reset.
    """
    if not guard._take_lock(run / "busy.lock"):
        raise SystemExit("Cannot resume while a command is running")
    try:
        rows = history_rows(run)
        meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
        used = commands_used(rows)
        if bench.finished(rows):
            raise SystemExit("The game is done (Boulder Badge): no resume")
        if any(r.get("cmd") == "resume" for r in rows):
            raise SystemExit("The one neutral resume is already recorded; do not send another")
        budget = meta["budget"]
        if not isinstance(budget, int) or budget <= 0 or used >= budget:
            raise SystemExit(f"Neutral resume requires an unfinished {budget}-command game")
        message = RESUME_MESSAGE.format(budget=budget)
        if not player_ref or not stop_ref:
            raise SystemExit("Resume requires the original player reference and first-stop evidence")
        last = rows[-1]
        log(run, dict(n=used, cmd="resume", resume_index=1, accepted_commands=used, t=time.time(),
                      map=last["map"], done=last["done"], budget=budget, message=message, **bench.last_fields(rows),
                      player_ref=player_ref, stop_ref=stop_ref))
        print(message)
    finally:
        guard._drop_lock(run / "busy.lock")


class Game:
    """Opens the run's saved game in a headless PyBoy and saves it back on close."""

    def __init__(self, run, fresh=False):
        from pyboy import PyBoy
        self.run = run
        # ram_file: never let PyBoy write red.gb.ram next to the ROM (fresh boots would load that save)
        self.gb = PyBoy(str(settings.ROM), window="null", sound_emulated=False, ram_file=io.BytesIO(bytes(0x8000)))
        self.gb.set_emulation_speed(0)
        if not fresh:                      # R16: fresh = power-on boot, nothing loaded
            with open(run / "game.state", "rb") as fh:
                self.gb.load_state(fh)
        self.m = self.gb.memory
        self.map_transitions = []
        self.transition_cause = None

    def close(self, save=True):
        try:
            if save:
                tmp = self.run / "game.state.tmp"
                with open(tmp, "wb") as fh:
                    self.gb.save_state(fh)
                tmp.replace(self.run / "game.state")
                self.gb.screen.image.save(self.run / "screen.png")
        finally:
            self.gb.stop(save=False)

    def tick(self, n=1):
        # Observe the existing frames, including warps hidden inside one press/batch.
        # No extra emulator frames are added. Special-warp flags may clear during loading.
        for _ in range(n):
            before = self.where()
            warp_before = tuple(self.m[R.A(k)] for k in
                                ("wWarpedFromWhichMap", "wWarpedFromWhichWarp", "wDestinationWarpID"))
            flags = self.m[R.A("wStatusFlags6" if "wStatusFlags6" in R.SYM else "wd732")]
            if self.m[R.A("wIsInBattle")] == 0xFF:
                self.transition_cause = "blackout"
            elif flags & (1 << 6):  # BIT_ESCAPE_WARP: Rope/Dig, special_warps.asm
                self.transition_cause = "escape_warp"
            self.gb.tick(1, True)
            after = self.where()
            if before[0] != after[0]:
                cause = self.transition_cause
                source, destination = before, after
                # WarpFound2 stores zero-based warp IDs (home/overworld.asm).
                # Require freshly written doorway registers: stale registers cannot
                # turn Rope/blackout into an exit. Coordinates can lag by a frame.
                warp_after = tuple(self.m[R.A(k)] for k in
                                   ("wWarpedFromWhichMap", "wWarpedFromWhichWarp", "wDestinationWarpID"))
                doorway = (cause is None and before[0] == 60 and after[0] == 15
                           and warp_after == (60, 7, 2) and warp_before != warp_after)
                if doorway:
                    cause = "doorway"
                    # MtMoonB1F.asm warp 8 -> Route4.asm warp 3.
                    source = (60, 27, 3)
                    destination = (15, 24, 5)
                edge = dict(source=list(source), destination=list(destination), cause=cause)
                if doorway:
                    edge["observed_source"] = list(before)
                    edge["observed_destination"] = list(after)
                self.map_transitions.append(edge)
                self.transition_cause = None

    def where(self):
        return self.m[0xD35E], self.m[0xD362], self.m[0xD361]

    def press(self, button):
        """One press. A direction is held until the player moves (max 30 frames), then the step is finished.
        After a door / map change it waits for the new map to fade in (otherwise the screenshot and the
        coordinates lag one step behind; step 4 players reported this)."""
        self.transition_cause = None
        map_before = self.m[0xD35E]
        self._press(button)
        if self.m[0xD35E] != map_before:
            self.tick(60)

    def screen_sig(self):
        return tuple(screen_text(self.m)), CURSOR in self.m[0xC3A0:0xC3A0 + 360]

    def settle(self):
        """Wait until the screen text and cursor stop changing (text printing done); False if it never settles."""
        last, same = None, 0
        for _ in range(SETTLE_MAX):
            sig = self.screen_sig()
            same = same + 1 if sig == last else 0
            last = sig
            if same >= SETTLE_FRAMES:
                return True
            self.tick()
        return False

    def text_waits(self):
        """Plain text waits for A: no filled cursor (choice, menu, battle decision), and a box is still open
        (intro pages, battle text, or the overworld font flag that CloseTextDisplay clears, home/text_script.asm)."""
        if CURSOR in self.m[0xC3A0:0xC3A0 + 360]:
            return False
        if in_intro(self.m) or self.m[R.A("wIsInBattle")]:
            return True
        # overworld: the font flag AND visible words; a stale flag over a plain map must never send an A (a new talk)
        return bool(self.m[R.A("wFontLoaded")] & 1) and bool(screen_text(self.m))

    def a_star(self):
        """R17: A until the text box closes or a choice shows. Returns the number of A presses (0..A_STAR_CAP).
        Fix round (Sol R17 final B3): if the screen does not settle within SETTLE_MAX frames, stop without another A
        (a late choice could otherwise be pressed)."""
        n = 0
        while n < A_STAR_CAP and self.settle() and self.text_waits():
            self.press("a")
            n += 1
        return n

    def menu_open(self):
        """R18: a menu or text is on screen (intro, or the font flag with visible words or a cursor)."""
        if in_intro(self.m):
            return True
        return bool(self.m[R.A("wFontLoaded")] & 1) and (bool(screen_text(self.m))
                                                          or CURSOR in self.m[0xC3A0:0xC3A0 + 360])

    def _press(self, button):
        # R18 (smoke 4 n143): a direction held 30 frames in a list menu auto-repeats (one 'down' moved two Mart
        # entries). In menus and text a direction is a tap like the other buttons; walking is unchanged.
        if button in ("up", "down", "left", "right") and not self.m[0xD057] and not self.menu_open():
            before = self.where()
            self.gb.button_press(button)
            for _ in range(30):
                self.tick()
                if self.where() != before:
                    break
            self.gb.button_release(button)
            for _ in range(24):            # let the walk finish (wWalkCounter back to 0)
                self.tick()
                if self.m[0xCFC5] == 0:
                    break
            self.tick(2)
        else:
            self.gb.button_press(button)
            self.tick(6)
            self.gb.button_release(button)
            self.tick(45)


def screen_text(m):
    """The text on screen (wTileMap, 20 x 18 tiles) decoded with the game's charmap; only rows that look like text."""
    rows = []
    for r in range(18):
        tiles = m[0xC3A0 + r * 20:0xC3A0 + r * 20 + 20]
        line = "".join(R.CHARS.get(t, " ") if t >= 0x7F else " " for t in tiles)   # below $7F: map graphics
        clean = re.sub(r"[^A-Za-z0-9'!?.,:;()\-é ]", " ", line).rstrip()
        if re.search(r"ABCDEFGH|abcdefgh|QRSTUVWX|qrstuvwx", clean):
            continue      # R16: the title screen's logo tiles ($80-$FF in order) decode as the alphabet
        if len(re.findall(r"[A-Za-z]", clean)) >= 3:
            rows.append(clean.strip())
    return rows


def view(g, run):
    """What a player sees: no goals, no advice (the same for both groups)."""
    s = R.state_from_pyboy(g.gb)
    p = s["place"]
    if in_intro(g.m):
        # R16: before the first map loads (logo, title, Oak's talk, naming) RAM holds no real place yet.
        s = dict(s, intro=True, text_box=True)
        out = ["Place: no map yet (power-on: intro, title screen or Professor Oak's talk before the game starts). "
               f"Badges: {len(s['badges'])}. Money: {s['money']}."]
    else:
        out = [f"Place: {p['map']} x={p['x']} y={p['y']} (x grows to the right, y grows down), facing "
               f"{FACING.get(g.m[0xC109], '?')}. Badges: {len(s['badges'])}. Money: {s['money']}."]
    for t in s["team"]:
        out.append(f"- {t['species']} L{t['level']} {t['hp']}/{t['max_hp']} HP {t['status']}: "
                   + ", ".join(f"{mv['move']} ({mv['pp']} PP)" for mv in t["moves"]))
    if not s["team"]:
        out.append("Team: none yet.")
    out.append("Bag: " + (", ".join(f"{b['item']} x{b['count']}" for b in s["bag"]) or "empty."))
    b = s["battle"]
    if b and b["kind"] != "lost":
        e = b.get("enemy")
        out.append(f"Battle ({b['kind']}): " + (f"enemy {e['species']} L{e['level']} {e['hp']}/{e['max_hp']} HP "
                                                f"{e['status']}" if e else "starting"))
    text = screen_text(g.m)
    if text:
        out.append("Screen text: " + " / ".join(text))
    out.append(f"Screenshot: {run / 'screen.png'}")
    return s, "\n".join(out)


def in_intro(m):
    """R16: no map header loaded yet (wCurMapWidth is 0 from power-on until the first map loads after Oak's talk)."""
    return m[R.A("wCurMapWidth")] == 0


def log(run, entry):
    with open(run / "log.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def parse_buttons(tokens):
    out = []
    for tok in tokens:
        if tok.lower() == A_STAR:            # R17: one press slot
            out.append(A_STAR)
            continue
        mt = re.fullmatch(r"([a-z]+)(?:\*(\d{1,4}))?", tok.lower())   # longer counts: unknown
        if not mt or mt.group(1) not in BUTTONS:
            raise SystemExit(f"unknown button '{tok}'. Use: {' '.join(sorted(BUTTONS))} (e.g. right*3), or a*")
        n = int(mt.group(2) or 1)        # check the count before expanding it: "a*9999" must not fill memory
        if len(out) + n > MAX_PRESSES:
            raise SystemExit(f"at most {MAX_PRESSES} presses per command")
        out += [mt.group(1)] * n
    if len(out) > MAX_PRESSES:
        raise SystemExit(f"at most {MAX_PRESSES} presses per command")
    return out


def refuse(run, a, why, message):
    """R16 (Sol R16 B2): log a refused request for the audit, then stop. Not a command: log.jsonl, game.state and
    the accepted count stay unchanged. Same file and fields as guard.py's batch refusals, plus the reason kind."""
    with open(run / "blocked.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.time(), "key": None, "why": why, "argv": sys.argv[1:], "cmd": a.cmd,
                            "keys": list(a.rest), "message": message}, ensure_ascii=False) + "\n")
    raise SystemExit(message)


def stuck_count(run):
    """Press commands in a row (look / ask skipped) that ended where they started, outside battle and text."""
    n = 0
    for r in reversed([json.loads(l) for l in open(run / "log.jsonl", encoding="utf-8")]):
        if r["cmd"] in ("look", "ask", "resume"):
            continue
        if r["cmd"] != "press" or r.get("moved") or r.get("battle") or r.get("text"):
            break
        n += 1
    return n


def run_dir(name):
    d = ARENA / name
    if not (d / "game.state").exists():
        raise SystemExit(f"no game '{name}': start it first")
    return d


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["start", "look", "press", "ask", "score", "resume"])
    ap.add_argument("run")
    ap.add_argument("rest", nargs="*")
    ap.add_argument("--group", choices=["plain", "teacher"])
    ap.add_argument("--model", default="")
    ap.add_argument("--player-ref", help="original player session reference for resume")
    ap.add_argument("--stop-ref", help="saved first final response reference for resume")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="commands allowed (look, press, ask); default 1000")
    ap.add_argument("--start-state", type=Path, default=None,
                    help="saved game to start from (test fixture); default: fresh power-on boot")
    ap.add_argument("--lean", action="store_true", help="R17: run driven by arena/lean_player.py")
    ap.add_argument("--guide", action="store_true", help="R18: GUIDE block on every view (teacher group only)")
    a = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", a.run):
        raise SystemExit("run name: letters, digits, _ . - only")
    if ROM_RAM.exists():
        logging.getLogger(__name__).debug("ROM-side save detected: %s", ROM_RAM)
        raise SystemExit("Game tool unavailable. No command was used.")

    if a.cmd == "start":
        d = ARENA / a.run
        if d.exists():
            raise SystemExit(f"{d} exists: never overwrite a game, use a new run name")
        if not a.group:
            raise SystemExit("--group plain|teacher is required")
        if a.budget <= 0:
            raise SystemExit("--budget must be positive")
        if a.guide and a.group != "teacher":
            raise SystemExit("--guide needs --group teacher")
        if a.start_state is None:          # R16: PokéBench rule, fresh boot; no state or save file is read
            data, start_path, start_hash = None, "power-on", None
        else:
            start = a.start_state.expanduser().resolve()
            data = start.read_bytes()
            start_path = str(start.relative_to(ROOT)) if start.is_relative_to(ROOT) else str(start)
            start_hash = hashlib.sha256(data).hexdigest()
        d.mkdir(parents=True)
        if data is not None:
            (d / "game.state").write_bytes(data)
        (d / "meta.json").write_text(json.dumps({"group": a.group, "model": a.model, "started": time.time(),
                                                 "budget": a.budget,
                                                 "start": start_path, "start_sha256": start_hash,
                                                 **({"player": "lean"} if a.lean else {}),
                                                 **({"guide": True} if a.guide else {})}), encoding="utf-8")
        g = Game(d, fresh=data is None)
        g.tick(BOOT_FRAMES if data is None else 300)   # logo / the room fades in (input after about 3-4 s)
        s, text = view(g, d)
        fields = bench.fields(g.m)
        gd = guide_block(s, g.m, None, fields, False) if a.guide else None
        g.close()
        log(d, {"n": 0, "cmd": "start", "t": time.time(), "map": s["place"]["map"],
                "map_id": s["place"]["map_id"], "done": s["story"]["done"],
                "budget": a.budget, "start": start_path, "start_sha256": start_hash,
                "intro": bool(s.get("intro")), **fields, **guide_fields(gd)})
        if gd:
            print(gd["text"])
        print(text)
        print(count_line(d))
        return

    d = run_dir(a.run)
    if a.cmd == "score":
        try:
            return score(d)
        finally:
            print(count_line(d))
    if a.cmd == "resume":
        try:
            return resume(d, a.player_ref, a.stop_ref)
        finally:
            print(count_line(d))
    # Refuse batched calls before anything is read, counted or saved (round 5 on; the same for both groups).
    key = lean_key(d) or guard.shell_key()      # R17: lean runs use the loop's per-turn key
    try:
        guard.check(d, key=key)
    except guard.Blocked:
        print(count_line(d))
        raise
    try:
        if key.startswith("lean:"):
            try:
                use_lean_key(d, key)      # R17 fix round: every turn key works once, ever (Sol R17)
            except guard.Blocked:
                print(count_line(d))
                raise
        play(a, d)
    finally:
        guard.release(d, key=key)


def score(d):
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    rows = [r for r in history_rows(d) if r["cmd"] != "resume"]
    last = rows[-1]
    print(json.dumps({"group": meta["group"], "model": meta["model"], "commands": commands_used(rows),
                      "milestones": len(last["done"]), "done": last["done"], "map": last["map"],
                      # a blackout halves your money; logged money exists from game 3 on (20 Oct)
                      "blackouts": sum(1 for r in rows if r.get("lost")) + sum(
                          1 for a, b in zip(rows, rows[1:]) if a.get("money") and b.get("money") is not None
                          and b["money"] <= a["money"] // 2 + 1 and b["money"] < a["money"]),
                      "asks": sum(1 for r in rows if r["cmd"] == "ask"),
                      "no_move_commands": sum(1 for r in rows if r["cmd"] == "press" and not r.get("moved")),
                      "bench": bench.last_fields(rows).get("bench_milestones", [])}))


def teacher_context(rows):
    """Teacher-only purpose travels in the run log; old logs start with an empty context."""
    return dict(next((r["teacher_context"] for r in reversed(rows) if "teacher_context" in r), {}))


def teacher_state(s, m):
    """Private observation for advice only; view() and both player prompts stay unchanged."""
    import advise
    if s["battle"]:
        return dict(s, teacher_ui=advise.battle_ui(m, s))
    tiles = list(m[R.A("wTileMap"):R.A("wTileMap") + 360])
    return dict(s, teacher_story=advise.story_memory(m, s),
                teacher_screen=dict(rows=screen_text(m), cursor=any(t in (0xed, 0xec) for t in tiles)))


def observe_walk(context, before, after, button, quiet):
    """Two failed directional presses confirm a temporary blocker; a first press may only turn the player.
    Keep a short occupancy memory through sidesteps; expire it or refresh from observed sprites."""
    import advise
    recent = [dict(r, ttl=r['ttl']-1) for r in context.get('walk_occupancy', []) if r['ttl']>1]
    context['walk_occupancy'] = recent
    if not quiet or before != after:
        context.pop("walk_block", None)
        return
    if button not in advise.W.STEP:
        return
    map_id, x, y = before
    dx, dy = advise.W.STEP[button]
    key = dict(map=R.MAPS.get(map_id, map_id), at=[x, y], direction=button, tile=[x + dx, y + dy])
    old = context.get("walk_block", {})
    count = min(3, old.get("count", 0) + 1) if all(old.get(k) == v for k, v in key.items()) else 1
    context["walk_block"] = dict(key, count=count, noted=old.get("noted", False) if count > 1 else False)
    if count >= 2:
        recent = [r for r in recent if (r['map'],r['tile']) != (key['map'],key['tile'])]
        context['walk_occupancy'] = (recent + [dict(map=key['map'],tile=key['tile'],ttl=6)])[-8:]


def observe_text(context, s):
    """At most six recent press observations, not asks/looks. Count a reopened identical dialogue too."""
    if s["battle"]:
        context.pop("text_loop", None)
        return False
    p = s["place"]
    at = [p["map"], p["x"], p["y"], s["story"]["done"]]
    old = context.get("text_loop", {})
    if old.get("at") != at:
        old = {}
    signature = " / ".join(s.get("teacher_screen", {}).get("rows", []))[:800] if s.get("text_box") else ""
    recent = (old.get("recent", []) + [signature])[-6:]
    repeats = recent.count(signature) if signature else 0
    noted = old.get("noted")
    context["text_loop"] = dict(at=at, recent=recent, repeats=repeats, noted=noted)
    if repeats >= 3 and noted != signature:
        context["text_loop"]["noted"] = signature
        return True
    return False


def quiet_walk(m):
    """Only infer collisions when walking is under player control, outside battle and text."""
    return not (m[R.A("wIsInBattle")] or m[R.A("wFontLoaded")] & 1 or m[R.A("wJoyIgnore")]
                or m[R.A("wStatusFlags5" if "wStatusFlags5" in R.SYM else "wd730")] & 1)
    # BIT_SCRIPTED_NPC_MOVEMENT = 0 (constants/ram_constants.asm); wd730 is its name in the older symbol file.


def battle_note(s, context):
    """Once per distinct menu choice/faint/danger in this battle, not on every button or cursor move."""
    import advise
    b = s["battle"]
    if not b:
        context.pop("battle_seen", None)
        return None
    if s.get("teacher_ui", {}).get("phase", "unknown") == "unknown" and b["kind"] != "lost":
        return None
    a = advise.answer(s, context=context)
    me, foe = b.get("yours") or {}, b.get("enemy") or {}
    key = json.dumps([s.get("teacher_ui", {}).get("phase"), me.get("species"), foe.get("species"),
                      a["details"][0] if a["details"] else a["do"], me.get("hp") == 0,
                      me.get("hp", 1) * 3 <= me.get("max_hp", 0), "knock you out" in a["why"]])
    seen = list(context.get("battle_seen", []))
    if key in seen:
        return None
    context["battle_seen"] = (seen + [key])[-24:]
    return advise.note(a)


def play(a, d):
    try:
        return _play(a, d)
    finally:
        print(count_line(d))


def _play(a, d):
    if a.cmd == "press":
        try:
            parse_buttons(a.rest)  # Refuse before opening a game or writing an accepted command.
        except SystemExit as stop:
            msg = str(stop)
            refuse(d, a, "too many presses" if msg.startswith("at most") else "unknown button", msg)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    with open(d / "log.jsonl", encoding="utf-8") as fh:
        history = [json.loads(line) for line in fh]
    n = commands_used(history) + 1
    if bench.finished(history):        # R16: nothing runs after the Boulder Badge
        refuse(d, a, "game done", bench.DONE_MESSAGE)
    if meta.get("budget") and n > meta["budget"]:   # games 1-7 of 20 Oct had no hard limit (scored at 200)
        refuse(d, a, "budget used", f"Your {meta['budget']} commands are used up. Stop and write your report.")
    prev_bench = bench.last_fields(history)
    context = teacher_context(history) if meta["group"] == "teacher" else None
    if a.cmd == "ask":
        if meta["group"] != "teacher":
            refuse(d, a, "no teacher", "this game has no teacher")
        import advise
        g = Game(d)
        s = R.state_from_pyboy(g.gb)
        if in_intro(g.m):
            s = dict(s, intro=True, text_box=True)
        s = teacher_state(s, g.m)
        ans = advise.answer(s, " ".join(a.rest) or None, stuck=stuck_count(d), context=context)
        badges_byte = g.m[R.A("wObtainedBadges")]
        fields = bench.fields(g.m, prev_bench)
        # Sol R18 minor: guided asks log the guide of this screen too (not printed: the view shows it)
        gd = guide_block(s, g.m, context, fields, False) if meta.get("guide") else None
        g.close(save=False)
        log(d, {"n": n, "cmd": "ask", "q": " ".join(a.rest), "t": time.time(), "map": s["place"]["map"],
                "map_id": s["place"]["map_id"], "badges_byte": badges_byte,
                "done": s["story"]["done"], "answer": ans["do"], "teacher_context": context,
                "intro": bool(s.get("intro")), **fields, **guide_fields(gd)})
        print(advise.text(ans))
        return
    g = Game(d)
    before = g.where()
    prev = next((r for r in reversed(history) if r["cmd"] not in ("ask", "resume")), {})
    lost = False
    a_star = []
    if a.cmd == "press":
        for bt in parse_buttons(a.rest):
            if bt == A_STAR:                 # R17: A until the text ends or a choice shows
                a_star.append(g.a_star())
                lost |= g.m[0xD057] == 0xFF
                continue
            walk_before = g.where() if context is not None else None
            quiet_before = quiet_walk(g.m) if context is not None else False
            g.press(bt)
            if context is not None:
                observe_walk(context, walk_before, g.where(), bt, quiet_before and quiet_walk(g.m))
            lost |= g.m[0xD057] == 0xFF
    s, text = view(g, d)
    extra_note = None
    new_place_answer = None
    recovery = None
    if context is not None:
        import advise
        s = teacher_state(s, g.m)
        extra_note = battle_note(s, context) if a.cmd == "press" else None
        if not s["battle"]:
            context.pop("battle_seen", None)
        if context.get("purpose") == "train" and (s["battle"] or prev.get("battle")):
            context["training_check"] = True
        if a.cmd == "press":
            if observe_text(context, s):
                recovery = ("repeated text", advise.note(advise.answer(s, context=context)))
            bump = context.get("walk_block", {})
            if not s["battle"] and not s.get("text_box") and bump.get("count", 0) >= 2 and not bump.get("noted"):
                bump["noted"] = True
                recovery = ("blocked walk", "Observed blocker: the last direction did not move you. "
                            + advise.text(advise.answer(s, context=context)))
            if context.get("training_check") and not s["battle"] and not s.get("text_box"):
                context.pop("training_check")
                recovery = ("training check", advise.note(advise.answer(s, context=context)))
        game_began = prev.get("intro") and not s.get("intro")      # R16: the first map just loaded
        if a.cmd == "press" and not s["battle"] and not s.get("text_box") and (s["place"]["map_id"] != before[0]
                                                                             or game_began):
            new_place_answer = advise.answer(s, context=context)
        if a.cmd == "press" and not s["battle"]:
            step = advise.story_step(s)
            step_id = step[0] if step else None
            if not s.get("text_box"):
                old_step = context.get("story_step")
                context["story_step"] = step_id
                if old_step and step_id != old_step and not recovery and not new_place_answer:
                    recovery = ("story step", advise.note(advise.answer(s, context=context)))
    badges_byte = g.m[R.A("wObtainedBadges")]
    fields = bench.fields(g.m, prev_bench)
    guided = bool(meta.get("guide")) and context is not None
    gd = guide_block(s, g.m, context, fields, a.cmd == "press") if guided else None
    g.close()
    log(d, {"n": n, "cmd": a.cmd, "keys": a.rest, "t": time.time(), "map": s["place"]["map"],
            "map_id": s["place"]["map_id"], "map_transitions": g.map_transitions, "badges_byte": badges_byte,
            "x": s["place"]["x"], "y": s["place"]["y"], "done": s["story"]["done"],
            "moved": (s["place"]["map_id"], s["place"]["x"], s["place"]["y"]) != before, "lost": lost,
            "money": s["money"], "team_hp": [t["hp"] for t in s["team"]], "battle": bool(s["battle"]),
            "text": bool(s.get("text_box")),
            "sick": [t["species"] for t in s["team"] if t["status"] == "poisoned" and t["hp"] > 0],
            "intro": bool(s.get("intro")), **fields,
            **({"a_star": a_star} if a_star else {}),
            **({"teacher_context": context} if context is not None else {}), **guide_fields(gd)})
    if gd and bench.FINAL not in fields["bench_milestones"]:
        print(gd["text"])
    print(text)
    if bench.FINAL in fields["bench_milestones"]:
        print("\n" + bench.DONE_MESSAGE)
        return
    if guided:          # R18: the GUIDE replaces the automatic notes (b2: a stale "wait for the menu" note)
        return
    if extra_note:
        print("\nTEACHER (battle choice): " + extra_note)
        auto(d, n, "battle choice", extra_note)
    if recovery:
        print(f"\nTEACHER ({recovery[0]}): " + recovery[1])
        auto(d, n, *recovery)
    # Teacher group only: after every STUCK presses without moving (outside battle and text), the teacher speaks up
    # by itself (round 3: one player pressed B 186 times next to the stairs and asked only twice). Costs no command.
    # Round 6: on entering a new map the teacher says the way there in one line (players stopped asking in Viridian
    # Forest). Every automatic note is also written to auto.jsonl for the audit.
    if meta["group"] == "teacher" and a.cmd == "press" and not s["battle"] and not s.get("text_box") and not recovery:
        import advise
        k = stuck_count(d)
        if k and k % advise.STUCK == 0:
            note = advise.text(advise.answer(s, None, stuck=k, context=context))
            print(f"\nTEACHER (you have not moved in {k} commands):\n" + note)
            auto(d, n, "stuck", note)
        elif new_place_answer is not None:      # a new map, or (R16) the first map after the intro
            note = advise.note(new_place_answer)       # context was updated before logging this command
            print(f"\nTEACHER (new place, {s['place']['map']}): {note}")
            auto(d, n, "new place", note)
        elif advise.poison_line(s) and (not prev.get("sick") or prev.get("battle") or prev.get("text")):
            # round 7: poisoned and now free to walk (after a battle, or newly): say it once (t9-6, t9-7)
            note = advise.poison_line(s)
            print(f"\nTEACHER (poison): {note}")
            auto(d, n, "poison", note)


def guide_block(s, m, context, fields, moving):
    """R18: the GUIDE block for this view (teacher state, raw screen rows, PokéBench milestones, run context)."""
    import r18_guide
    if not s.get("battle") and "teacher_story" not in s:
        s = teacher_state(s, m)
    if not s.get("battle") and not s.get("text_box") and not s.get("intro"):
        s = dict(s, teacher_scene=not quiet_walk(m))     # a script moves you (Oak's escort): walking is ignored
    b = s.get("battle") or {}
    menu = (s.get("teacher_ui") or {}).get("phase") in ("commands", "moves")
    if b.get("kind") == "wild" and b.get("enemy") is None and menu and \
            m[R.A("wCurEnemyLVL")] == m[R.A("wEnemyMonLevel")]:
        # smoke 3 n49-n150: in a real wild fight wCurOpponent reads 0 once the menu shows, so read_state calls the
        # enemy unknown and the guide said "a* until the menu shows" 100 times. The visible battle menu proves the
        # enemy is loaded (guide only; read_state and the old answers are unchanged).
        foe = dict(R._mon(m, "wEnemyMon"), flags=R._flags(m, "Enemy"))
        s = dict(s, battle=dict(b, enemy=foe))
    return r18_guide.guide(s, context=context, bench=fields.get("bench_milestones"),
                           rows=r18_guide.raw_rows(m), moving=moving)


def guide_fields(gd):
    """R18: the guide step logged per command (log.jsonl)."""
    if not gd:
        return {}
    return {"guide": {"step": gd["step"], "index": gd["index"], "mode": gd["mode"]}, "guide_text": gd["text"]}


def auto(run, n, kind, note):
    with open(run / "auto.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"n": n, "kind": kind, "t": time.time(), "note": note}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
