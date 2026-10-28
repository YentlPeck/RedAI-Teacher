"""Lean player loop (R17, 27 Oct 2026): one fresh model call per command, like PokéBench's runner.

Every turn the model gets ONE short prompt: fixed rules (LEAN_PROMPT.md, same meaning as PLAYER_PROMPT.md) + its own
notes (<= 600 characters, it rewrites them each turn) + the last 8 commands with a short result each + the newest
play.py view + the screenshot. No conversation is kept between calls. It answers strict JSON
{"command": "look|press|ask", "buttons": "...", "question": "...", "notes": "..."}; this loop runs exactly ONE play.py
command per turn as a subprocess (no shell). A bad reply is retried once on the same turn; a second bad reply counts
as a look. Stops on Done (Boulder Badge), when the budget is used, or after --max-commands commands in this session.

    python arena/lean_player.py RUN --model haiku|luna --group plain|teacher [--effort low|medium|high|xhigh|max]
                         [--budget 1000] [--max-commands N]

Models run on subscriptions only: Haiku through the headless claude CLI (clean flags, no tools, own
system prompt, image in a stream-json message), Luna through codex exec (-i image, read-only sandbox, user config and
tool features off). The player CLI runs in REDAI_PLAYER_CWD, an empty folder (no CLAUDE.md / AGENTS.md above it).
Log: RUN/lean.jsonl (one row per model call: prompt sha, reply, tokens, API price estimate); RUN/lean_totals.json.
Players never see experiment files: the prompt holds only the rules, notes, recent commands, view and screenshot.
"""
import argparse
import base64
import hashlib
import io
import json
import os
import re
import subprocess
import threading
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import settings  # noqa: E402
ROOT = settings.REPO
HERE = Path(__file__).resolve().parent
PLAY = HERE / "play.py"
PY = Path(sys.executable)
RUNS = settings.RUNS
PLAYER_CWD = settings.PLAYER_CWD
HISTORY = 8                      # recent commands shown
NOTES_MAX = 600                  # PokéBench notes cap
QUESTION_MAX = 300
MAX_PRESSES = 6
BUTTONS = {"up", "down", "left", "right", "a", "b", "start", "select"}
COOLDOWN = 1.1                   # guard.py refuses calls < 1 s after the previous one
MODEL_ERRORS_MAX = 3             # model errors in a row (CLI failed / no reply) before the loop stops
PLAY_ERRORS_MAX = 3              # play.py calls in a row that ran nothing before the loop stops
MODELS = {"haiku": "claude-haiku-5-5", "luna": "gpt-6-luna", "sonnet": "claude-sonnet-5-5", "terra": "gpt-6.1-terra"}
# r22: Sonnet runs like Haiku (claude -p), Terra like Luna (codex exec). PLAYER = the backend of this game.
PLAYER = "haiku"
KIND = {"haiku": "claude", "sonnet": "claude", "luna": "codex", "terra": "codex"}


def model_id(kind):
    """The model of this game for a claude/codex call; the default model of that kind when PLAYER is the other kind."""
    return MODELS[PLAYER] if KIND.get(PLAYER) == kind else MODELS["haiku" if kind == "claude" else "luna"]
# API list prices, $ per 1M tokens (we pay $0: subscriptions). Haiku 5.5: $0.10 in / $0.50 out (prompts <= 100K),
# cache read 0.1x, 5-min write 1.25x, 1-hour write 2x (claude-api skill table, cached 6 Oct 2026; the 1-hour write
# rate matches the CLI's own total_cost_usd in the 27 Oct probe). Luna: round b1 result ($0.10 in, $0.01 cached,
# $0.50 out; PokéBench models.yaml azure-gpt-6-luna).
RATES = {
    "haiku": dict(input=0.10, cached=0.01, cache_write_5m=0.125, cache_write_1h=0.20, output=0.50),
    "luna": dict(input=0.10, cached=0.01, cache_write_5m=0.10, cache_write_1h=0.10, output=0.50),
    # r22, PokéBench models.yaml (fetched copy 28 Oct): Sonnet 5.5 $2 in / $10 out, cache read 0.1x, writes 1.25x/2x;
    # Terra API rate at launch $1 in / $0.05 cached / $5 out.
    "sonnet": dict(input=2.00, cached=0.20, cache_write_5m=2.50, cache_write_1h=4.00, output=10.00),
    "terra": dict(input=1.00, cached=0.05, cache_write_5m=1.00, cache_write_1h=1.00, output=5.00),
}
POWER_ON_LINE = ("The game starts from power-on (the Game Freak logo): pick NEW GAME once to begin "
                 "(this first NEW GAME is allowed).")
ASK_LINE = ('- ask: ask a Pokémon Red teacher what to do next, where to go, which move to use, or if your team is '
            'ready. Put the question in "question". The answer comes back on your next turn.\n'
            '- GUIDE: the game view starts with a GUIDE line from the teacher, free, every turn: the step you are '
            'on, GO or PRESS = the buttons for your next command, THEN = the step after. It is rebuilt from the game '
            'each turn. Following it is the fast way; ask when it does not fit what you see. Copy the keys of the '
            'NEWEST GUIDE line, never keys from your notes: battle keys change every turn (the move list opens on '
            'your last move).\n')
DONE_MARK = "Done: you have the Boulder Badge"
COUNT_RE = re.compile(r"^Commands used: (\d+) of (\d+)\s*$", re.M)


class BadReply(Exception):
    pass


class ModelError(Exception):
    pass


# ---------------------------------------------------------------- prompt

def rules(group, budget, start="power-on"):
    """The fixed rules (system prompt). Plain and teacher differ only in the ask parts."""
    text = (HERE / "LEAN_PROMPT.md").read_text(encoding="utf-8")
    teacher = group == "teacher"
    start_line = POWER_ON_LINE if start == "power-on" else "The game starts from a saved game in progress."
    return (text.replace("{START_LINE}", start_line)
            .replace("{ASK_LINE}\n", (ASK_LINE if teacher else "") + "\n")
            .replace("{ASK_COUNT}", ", ask" if teacher else "")
            .replace("{ASK_CHOICE}", ' or "ask"' if teacher else "")
            .replace("{ASK_FIELD}", ' "question": "your question (ask only)",' if teacher else "")
            .replace("{BUDGET}", str(budget)))


def clean_view(out):
    """play.py output without the screenshot path and the count line (the loop states the count itself)."""
    keep = [l for l in out.splitlines() if not l.startswith("Screenshot: ") and not COUNT_RE.match(l)]
    return "\n".join(keep).strip()


def user_message(state, used, budget):
    notes = state["notes"] or "(no notes yet)"
    recent = state["history"][-HISTORY:]
    parts = ["YOUR NOTES (you wrote these on earlier turns; they are plans and guesses, the game view below is the "
             "truth):\n" + notes,
             "YOUR LAST COMMANDS (oldest first):\n" + ("\n".join(recent) if recent else "(none yet)")]
    if state.get("teacher"):
        parts.append(state["teacher"])
    parts.append(f"GAME VIEW NOW (you have used {used} of {budget} commands):\n{state['view']}")
    parts.append("The screenshot of the screen right now is attached. Take your turn: reply with the JSON object only.")
    return "\n\n".join(parts)


# ---------------------------------------------------------------- reply

def extract_json(text):
    """Strip a ```json fence, else take the first { .. last } (PokéBench _extract_json)."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t
        t = t.rsplit("```", 1)[0].strip()
        if t.lower().startswith("json"):
            t = t[4:].strip()
    i, j = t.find("{"), t.rfind("}")
    return t[i:j + 1] if i != -1 and j > i else t


def parse_buttons(text):
    if not isinstance(text, str):
        raise BadReply("buttons is not a string")
    out = []
    for tok in re.split(r"[\s,]+", text.strip().lower()):
        if not tok:
            continue
        if tok == "a*":                     # R17: A until the text ends or a choice shows (one press slot)
            out.append(tok)
            continue
        m = re.fullmatch(r"([a-z]+)(?:\*(\d{1,4}))?", tok)   # longer counts: unknown button
        if not m or m.group(1) not in BUTTONS or (m.group(2) is not None and int(m.group(2)) < 1):
            raise BadReply(f"unknown button '{tok}'")
        n = int(m.group(2) or 1)         # check the count before expanding it: "a*9999" must not fill memory
        if len(out) + n > MAX_PRESSES:
            raise BadReply(f"{len(out) + n} presses (at most {MAX_PRESSES})")
        out += [m.group(1)] * n
    if not out:
        raise BadReply("press without buttons")
    if len(out) > MAX_PRESSES:
        raise BadReply(f"{len(out)} presses (at most {MAX_PRESSES})")
    return text.strip().lower().replace(",", " ").split()


def parse_reply(text, group):
    """-> (play.py arguments after the run name, notes or None). Raises BadReply."""
    try:
        plan = json.loads(extract_json(text))
    except (json.JSONDecodeError, TypeError) as e:
        raise BadReply(f"not JSON: {e}")
    if not isinstance(plan, dict):
        raise BadReply("reply is not a JSON object")
    notes = plan.get("notes")
    notes = notes[:NOTES_MAX] if isinstance(notes, str) and notes.strip() else None
    cmd = plan.get("command")
    if cmd == "look":
        return ["look"], notes
    if cmd == "press":
        return ["press", *parse_buttons(plan.get("buttons"))], notes
    if cmd == "ask":
        if group != "teacher":
            raise BadReply("ask is not available in this game")
        q = plan.get("question")
        if not isinstance(q, str) or not q.strip():
            raise BadReply("ask without a question")
        return ["ask", " ".join(q.split())[:QUESTION_MAX]], notes
    raise BadReply(f"unknown command {cmd!r}")


def result_line(n, args, out, rc):
    """One short line for the recent-commands list."""
    what = args[0] if args[0] == "look" else (
        "press " + " ".join(args[1:]) if args[0] == "press" else f'ask "{args[1][:80]}"')
    if rc != 0 or not COUNT_RE.search(out or ""):
        msg = " ".join((out or "").split())[:160] or f"exit code {rc}"
        return f"{n}. {what} -> NOT RUN: {msg}"
    if args[0] == "ask":
        ans = " ".join(clean_view(out).split())
        return f"{n}. {what} -> teacher: {ans[:150]}{'...' if len(ans) > 150 else ''}"
    lines = clean_view(out).splitlines()
    bits = []
    place = next((l for l in lines if l.startswith("Place: ")), "")
    m = re.match(r"Place: (\S+) x=(\d+) y=(\d+).*facing (\w+)", place)
    bits.append(f"{m.group(1)} x={m.group(2)} y={m.group(3)} facing {m.group(4)}" if m else
                "no map yet (intro)" if place.startswith("Place: no map yet") else place[7:60])
    battle = next((l for l in lines if l.startswith("Battle ")), None)
    if battle:
        bits.append(battle[:80])
    text = next((l for l in lines if l.startswith("Screen text: ")), None)
    if text:
        bits.append("text: " + text[13:93] + ("..." if len(text) > 93 else ""))
    if any(l.startswith("TEACHER (") for l in lines):
        bits.append("teacher note")
    if DONE_MARK in out:
        bits.append("DONE")
    return f"{n}. {what} -> " + " | ".join(bits)


# ---------------------------------------------------------------- price

def price(backend, tok):
    """API price estimate in $. tok: input = all prompt tokens (cached and cache writes included)."""
    r = RATES[backend]
    cw5, cw1, cached = tok.get("cache_write_5m", 0), tok.get("cache_write_1h", 0), tok.get("cached", 0)
    fresh = max(0, tok.get("input", 0) - cached - cw5 - cw1)
    return (fresh * r["input"] + cached * r["cached"] + cw5 * r["cache_write_5m"] + cw1 * r["cache_write_1h"]
            + tok.get("output", 0) * r["output"]) / 1e6


# ---------------------------------------------------------------- models

def shot(run):
    """Screen 160x144 -> 480x432 nearest (PokéBench shrink_png size); saved as RUN/lean_screen.png."""
    from PIL import Image
    im = Image.open(run / "screen.png").convert("RGB").resize((480, 432), Image.NEAREST)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    data = buf.getvalue()
    (run / "lean_screen.png").write_bytes(data)
    return run / "lean_screen.png", hashlib.sha256(data).hexdigest()


def clean_env():
    env = dict(os.environ)
    for k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT",
              "CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD", "LEAN_PLAYER_TURN", "REFSTRAT_PACE", "HUNT_CONFIG"):
        env.pop(k, None)
    env.update(CLAUDE_CODE_DISABLE_AUTO_MEMORY="1", CLAUDE_CODE_DISABLE_ADVISOR_TOOL="1", PYTHONIOENCODING="utf-8")
    return env


# Each prompt is new, so a cache only adds 1-hour cache writes (2x the input price) for the per-turn part. Off:
# every token is plain input. Non-essential traffic off: otherwise the CLI sends each prompt a second time to
# Haiku to make a session title (seen with --debug api, 27 Oct).
HAIKU_ENV = {"DISABLE_PROMPT_CACHING": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}


def haiku_tokens(result):
    """Token counts of one claude -p call. The CLI's modelUsage (all requests of the call, the base of its own
    total_cost_usd) wins over the result usage: in the 27 Oct smoke the first call of a run had one extra hidden
    request (session title) that only modelUsage counts. Every model in modelUsage is summed (the audit flags non-Haiku models)."""
    mu = result.get("modelUsage") or {}
    if mu:
        tok = dict(input=0, cached=0, cache_write_5m=0, cache_write_1h=0, output=0, thinking=0)
        for m in mu.values():
            cw1 = m.get("cacheCreationEphemeral1hInputTokens", 0)
            cw5 = m.get("cacheCreationEphemeral5mInputTokens", 0)
            cw5 += max(0, m.get("cacheCreationInputTokens", 0) - cw1 - cw5)
            tok["input"] += m.get("inputTokens", 0) + m.get("cacheReadInputTokens", 0) + m.get("cacheCreationInputTokens", 0)
            tok["cached"] += m.get("cacheReadInputTokens", 0)
            tok["cache_write_5m"] += cw5
            tok["cache_write_1h"] += cw1
            tok["output"] += m.get("outputTokens", 0)
            tok["thinking"] += m.get("thinkingTokens", 0)
        return tok
    u = result.get("usage", {})
    cc = u.get("cache_creation") or {}
    cw1 = cc.get("ephemeral_1h_input_tokens", 0)
    cw5 = cc.get("ephemeral_5m_input_tokens", u.get("cache_creation_input_tokens", 0) - cw1)
    return dict(input=u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                + u.get("cache_read_input_tokens", 0),
                cached=u.get("cache_read_input_tokens", 0), cache_write_5m=cw5, cache_write_1h=cw1,
                output=u.get("output_tokens", 0),
                thinking=(u.get("output_tokens_details") or {}).get("thinking_tokens", 0))


CLAUDE_IDLE_S = 90       # r23: a claude call that sends nothing for this long is cut (see run_idle)


def run_idle(cmd, stdin_text, env, idle=CLAUDE_IDLE_S, total=600):
    """subprocess.run(capture_output) with an idle limit. r23 (28 Oct): Sonnet 5.5 calls sometimes send the thinking
    block and then nothing more, with the connection open, until the 600 s timeout (b7: about 1 call in 8). The CLI
    streams an event at least every few seconds while it works, so silence for `idle` s = a dead call. Raises
    subprocess.TimeoutExpired like subprocess.run; the loop then retries the same command."""
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         encoding="utf-8", errors="replace", cwd=PLAYER_CWD, env=env)
    out, err, seen = [], [], [time.time()]

    def pump(stream, sink):
        for line in stream:
            sink.append(line)
            seen[0] = time.time()

    readers = [threading.Thread(target=pump, args=(p.stdout, out), daemon=True),
               threading.Thread(target=pump, args=(p.stderr, err), daemon=True)]
    for r in readers:
        r.start()
    try:
        p.stdin.write(stdin_text)
        p.stdin.close()
    except OSError:
        pass
    start = time.time()
    while p.poll() is None:
        now = time.time()
        if now - seen[0] > idle or now - start > total:
            p.kill()
            p.wait()
            why = f"no output for {idle} s" if now - seen[0] > idle else f"over {total} s"
            raise subprocess.TimeoutExpired(cmd[:3] + [why], total, output="".join(out)[-2000:])
        time.sleep(0.5)
    for r in readers:
        r.join(5)
    return subprocess.CompletedProcess(cmd, p.returncode, "".join(out), "".join(err))


def call_haiku(system, user, image):
    """Headless claude CLI: clean flags, NO tools, our own system prompt, no saved session."""
    msg = {"type": "user", "message": {"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                     "data": base64.b64encode(Path(image).read_bytes()).decode()}},
        {"type": "text", "text": user}]}}
    # r21 (28 Oct): both models at the same --effort level (default high). No fast mode for either:
    # Codex runs with --ignore-user-config (no service_tier), and the CLI fast mode is Opus-only.
    cmd = [str(settings.claude_cli()), "-p", "--model", model_id("claude"), "--effort", EFFORT,
           "--settings", '{"autoMemoryEnabled": false, "claudeMdExcludes": ["**"]}', "--setting-sources", "user",
           "--strict-mcp-config", "--disable-slash-commands", "--tools", "", "--no-session-persistence",
           "--system-prompt", system, "--input-format", "stream-json", "--output-format", "stream-json", "--verbose"]
    p = run_idle(cmd, json.dumps(msg) + "\n", dict(clean_env(), **HAIKU_ENV))
    result, tools, init_tools = None, 0, None
    for line in p.stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            init_tools = ev.get("tools")
        if ev.get("type") == "assistant":
            tools += sum(1 for b in ev.get("message", {}).get("content", []) if b.get("type") == "tool_use")
        if ev.get("type") == "result":
            result = ev
    if result is None or result.get("is_error"):
        raise ModelError(f"claude rc={p.returncode}: {(result or {}).get('result') or p.stderr[-300:]}")
    tok = haiku_tokens(result)
    return dict(text=result.get("result") or "", tokens=tok, cli_cost_usd=result.get("total_cost_usd"),
                tool_calls=tools, tools_offered=init_tools, cli_model_usage=result.get("modelUsage"),
                cli_turns=result.get("num_turns"),
                isolation=([f"tools offered: {init_tools}"] if init_tools else [])
                + ([f"{tools} tool_use block(s)"] if tools else []))


def codex_path():
    try:
        return settings.codex_cli()
    except FileNotFoundError:
        pass
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"   # the Codex desktop app's copy
    found = sorted(base.glob("*/codex.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not found:
        raise ModelError("codex CLI not found: put it on PATH or set REDAI_CODEX")
    return found[0]


CODEX_OFF = ("shell_tool", "unified_exec", "multi_agent", "image_generation", "apps", "plugins", "browser_use",
             "computer_use", "goals", "skill_search", "tool_suggest", "sleep_tool", "hooks", "view_image",
             "code_mode_host", "code_mode_interrupt")
# Only settings Codex recognizes (it warns about unknown keys; any warning stops the turn, see call_luna).
CODEX_CONFIG = ("agents.max_depth=0", 'web_search="disabled"',
                "include_permissions_instructions=false", "include_environment_context=false",
                "include_collaboration_mode_instructions=false", "include_apps_instructions=false")
# Fix round (Sol R17 B1). The model catalog decides Codex's tool set: gpt-6-luna is "code_mode_only" (an `exec` JS
# tool) with v2 agent tools. Our own catalog entry: direct tools, v1 agents (removed by agents.max_depth=0), no
# apply_patch, no experimental tools, no node REPL. With the features above off, the tool list (codex debug
# prompt-input) is only request_user_input, which `codex exec` refuses ("not supported in exec mode").
CODEX_ALLOWED_TOOLS = {"request_user_input"}
CODEX_STDERR_OK = ("Reading prompt from stdin...",)


def codex_catalog(run, codex=None):
    """Write RUN/lean_codex_catalog.json: the installed Codex's gpt-6-luna entry with every tool source off."""
    p = subprocess.run([str(codex or codex_path()), "debug", "models"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=PLAYER_CWD, env=clean_env(), timeout=120)
    entry = next(m for m in json.loads(p.stdout)["models"] if m.get("slug") == model_id("codex"))
    entry = dict(entry, tool_mode="direct", multi_agent_version="v1", apply_patch_tool_type=None,
                 experimental_supported_tools=[], node_repl_disabled=True, supports_search_tool=False,
                 include_skills_usage_instructions=False, include_plugin_usage_instructions=False,
                 include_apps_usage_instructions=False)
    path = run / "lean_codex_catalog.json"
    path.write_text(json.dumps({"models": [entry]}, indent=1), encoding="utf-8")
    return path


def codex_flags(run, system):
    instr = run / "lean_codex_instructions.md"
    if not instr.exists() or instr.read_text(encoding="utf-8") != system:
        instr.write_text(system, encoding="utf-8")
    catalog = run / "lean_codex_catalog.json"
    flags = ["-c", "model=" + json.dumps(model_id("codex")), "-c", "model_catalog_json=" + json.dumps(str(catalog)),
             "-c", "model_instructions_file=" + json.dumps(str(instr))]
    for c in ("model_reasoning_effort=" + json.dumps(EFFORT),) + CODEX_CONFIG:
        flags += ["-c", c]
    for f in CODEX_OFF:
        flags += ["--disable", f]
    return flags


def codex_preflight(run, system):
    """Before a Luna session: render the exact prompt input locally (no model call, empty CODEX_HOME = no user
    config, like --ignore-user-config) and refuse to start if Codex would offer any tool but request_user_input."""
    codex = codex_path()
    codex_catalog(run, codex)
    home = run / "lean_codex_probe_home"
    home.mkdir(exist_ok=True)
    env = dict(clean_env(), CODEX_HOME=str(home))
    p = subprocess.run([str(codex), "debug", "prompt-input", *codex_flags(run, system), "preflight"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PLAYER_CWD, env=env,
                       timeout=120)
    items = json.loads(p.stdout)
    tools = sorted(t.get("name") for it in items if it.get("type") == "additional_tools"
                   for ns in it.get("tools", []) for t in ns.get("tools", [ns]))
    roles = [it.get("role") for it in items if it.get("type") == "message"]
    row = dict(t=time.time(), preflight="codex prompt-input", tools=tools, message_roles=roles,
               stderr=p.stderr.strip()[-500:])
    log(run, row)
    if set(tools) - CODEX_ALLOWED_TOOLS or p.stderr.strip():
        raise SystemExit(f"Luna isolation preflight failed: tools {tools}, stderr {p.stderr.strip()[-300:]!r}")
    return row


def codex_isolation(stdout, stderr):
    """Problems in one codex exec run: any tool item, any error/warning item, unexpected stderr.
    -> (problems, number of distinct tool items)."""
    problems, tool_ids = [], set()
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = ev.get("item") or {}
        kind = item.get("type")
        if ev.get("type", "").startswith("item.") and kind not in (None, "agent_message", "reasoning"):
            msg = item.get("message") or item.get("command") or item.get("tool") or ""
            problems.append(f"{ev['type']} {kind}: {str(msg)[:200]}")
            if kind != "error":
                tool_ids.add(item.get("id") or f"#{len(problems)}")
        elif ev.get("type") in ("error", "turn.failed"):
            problems.append(f"{ev['type']}: {json.dumps(ev)[:200]}")
    for line in stderr.splitlines():
        if line.strip() and line.strip() not in CODEX_STDERR_OK:
            problems.append(f"stderr: {line.strip()[:200]}")
    return problems, len(tool_ids)


def call_luna(system, user, image):
    """codex exec: user config ignored, no saved session, read-only sandbox, own catalog entry and features so no
    usable tool is offered; the rules replace Codex's base instructions; the turn part goes on stdin. Returns the
    isolation problems of this run (the loop treats any problem as a bad reply, before play.py)."""
    run = Path(image).parent
    if not (run / "lean_codex_catalog.json").exists():
        codex_catalog(run)
    out = run / "lean_codex_last.txt"
    cmd = [str(codex_path()), "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
           "-C", str(PLAYER_CWD), "-s", "read-only", *codex_flags(run, system),
           "--json", "-o", str(out), "-i", str(image)]
    p = subprocess.run(cmd, input=user, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=PLAYER_CWD, env=clean_env(), timeout=600)
    text, usage = None, None
    for line in p.stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = ev.get("item") or {}
        if ev.get("type") == "item.completed" and item.get("type") == "agent_message":
            text = item.get("text", "")
        if ev.get("type") == "turn.completed":
            usage = ev.get("usage", {})
    problems, tools = codex_isolation(p.stdout, p.stderr)
    if not problems and (usage is None or text is None):
        raise ModelError(f"codex rc={p.returncode}: {p.stderr[-300:]}")
    usage = usage or {}
    tok = dict(input=usage.get("input_tokens", 0), cached=usage.get("cached_input_tokens", 0),
               cache_write_5m=usage.get("cache_write_input_tokens", 0), cache_write_1h=0,
               output=usage.get("output_tokens", 0), thinking=usage.get("reasoning_output_tokens", 0))
    return dict(text=text or "", tokens=tok, cli_cost_usd=None, tool_calls=tools, tools_offered=None,
                isolation=problems)


BACKENDS = {"haiku": call_haiku, "luna": call_luna, "sonnet": call_haiku, "terra": call_luna}
# r21: reasoning effort for both backends (claude --effort / codex model_reasoning_effort; same five names).
EFFORTS = ("low", "medium", "high", "xhigh", "max", "ultra")      # ultra: Codex models only
EFFORT = "high"


# ---------------------------------------------------------------- play.py

def run_play(args, run_name, py, play, last_end):
    """Exactly one play.py command, no shell. Returns (rc, stdout, stderr, end time)."""
    wait = COOLDOWN - (time.time() - last_end)
    if wait > 0:
        time.sleep(wait)
    env = clean_env()
    env["LEAN_PLAYER_TURN"] = f"{run_name}-{uuid.uuid4().hex}"
    p = subprocess.run([str(py), str(play), args[0], run_name, *args[1:]], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=ROOT, env=env, timeout=600)
    return p.returncode, p.stdout or "", p.stderr or "", time.time()


def problem(err):
    """play.py's own message (SystemExit text goes to stderr) without library warnings."""
    return "\n".join(l for l in err.splitlines() if l.strip() and "Warning" not in l)


def used_of(out):
    m = list(COUNT_RE.finditer(out or ""))
    return (int(m[-1].group(1)), int(m[-1].group(2))) if m else None


# ---------------------------------------------------------------- loop

def log(run, row):
    with open(run / "lean.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def save_state(run, state):
    tmp = run / "lean_state.json.tmp"
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    tmp.replace(run / "lean_state.json")


def totals(run):
    rows = [json.loads(l) for l in (run / "lean.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    calls = [r for r in rows if "tokens" in r]
    tok = {k: sum(r["tokens"].get(k, 0) for r in calls)
           for k in ("input", "cached", "cache_write_5m", "cache_write_1h", "output", "thinking")}
    cmds = sum(1 for r in rows if r.get("counted"))
    cost = sum(r["price_usd"] for r in calls)
    cli = [r["cli_cost_usd"] for r in calls if r.get("cli_cost_usd") is not None]
    return dict(model_calls=len(calls), commands=cmds, bad_replies=sum(1 for r in rows if r.get("bad")),
                fallback_looks=sum(1 for r in rows if r.get("fallback")),
                model_errors=sum(1 for r in rows if r.get("model_error")),
                isolation_failures=sum(1 for r in rows if r.get("isolation")),
                tool_calls=sum(r.get("tool_calls", 0) for r in calls), tokens=tok, price_usd=round(cost, 6),
                cli_cost_usd=round(sum(cli), 6) if cli else None,
                per_command=dict(input=round(tok["input"] / cmds, 1), output=round(tok["output"] / cmds, 1),
                                 price_usd=round(cost / cmds, 7)) if cmds else None)


def start_run(run_name, backend, group, budget, py, play, runs):
    p = subprocess.run([str(py), str(play), "start", run_name, "--group", group, "--model", MODELS.get(backend, backend),
                        "--budget", str(budget), "--lean", *(["--guide"] if group == "teacher" else [])],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=ROOT, env=clean_env(), timeout=600)
    if p.returncode != 0 or not used_of(p.stdout):
        raise SystemExit(f"start failed: {p.stdout[-300:]} {p.stderr[-300:]}")
    run = runs / run_name
    state = dict(notes="", history=[], view=clean_view(p.stdout), teacher="", backend=backend, group=group,
                 effort=EFFORT, budget=budget, used=0, done=False)
    save_state(run, state)
    return run, state


def play_game(run_name, backend, group, budget=1000, max_commands=None, model_fn=None, py=PY, play=PLAY,
              runs=RUNS, sleep=time.sleep):
    """Run the loop. model_fn(system, user, image_path) -> dict(text, tokens, ...) (default: the backend)."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", run_name):
        raise SystemExit("run name: letters, digits, _ . - only")
    global PLAYER
    PLAYER = backend
    if EFFORT == "ultra" and BACKENDS.get(backend) is not call_luna:
        raise SystemExit("--effort ultra exists only for the Codex models (luna, terra)")
    model_fn = model_fn or BACKENDS[backend]
    PLAYER_CWD.mkdir(parents=True, exist_ok=True)
    run = runs / run_name
    if (run / "lean_state.json").exists():
        state = json.loads((run / "lean_state.json").read_text(encoding="utf-8"))
        if (state["backend"], state["group"], state.get("effort", "high")) != (backend, group, EFFORT):
            raise SystemExit("run exists with another model, group or effort")
        budget = state["budget"]
    elif run.exists():
        raise SystemExit(f"{run} exists but is not a lean run: use a new run name")
    else:
        run, state = start_run(run_name, backend, group, budget, py, play, runs)
    system = rules(group, budget)
    (run / "lean_system.txt").write_text(system, encoding="utf-8")
    system_sha = hashlib.sha256(system.encode()).hexdigest()
    if model_fn is call_luna:          # Sol R17 B1: prove the tool list before any Luna call of this session
        codex_preflight(run, system)
    session, model_errs, play_errs, last_end, stop = 0, 0, 0, 0.0, None
    while True:
        if state["done"]:
            stop = "done"
        elif state["used"] >= budget:
            stop = "budget"
        elif max_commands is not None and session >= max_commands:
            stop = "max-commands"
        if stop:
            break
        n = state["used"] + 1
        image, image_sha = shot(run)
        user = user_message(state, state["used"], budget)
        prompt_sha = hashlib.sha256(f"{system}\n\n{user}\n\nimage:{image_sha}".encode()).hexdigest()
        args, notes, fallback = None, None, False
        for attempt in (1, 2):
            t0 = time.time()
            row = dict(t=t0, n=n, attempt=attempt, backend=backend, model=MODELS.get(backend, backend), effort=EFFORT,
                       prompt_sha=prompt_sha, system_sha=system_sha, image_sha=image_sha, user=user)
            try:
                res = model_fn(system, user, image)
            except (ModelError, subprocess.TimeoutExpired, OSError) as e:
                model_errs += 1
                log(run, dict(row, model_error=str(e)[:500], seconds=round(time.time() - t0, 1)))
                if model_errs >= MODEL_ERRORS_MAX:
                    stop = "model-errors"
                    break
                sleep(15)
                continue
            model_errs = 0
            row.update(reply=res["text"], tokens=res["tokens"], price_usd=round(price(backend, res["tokens"]), 8)
                       if backend in RATES else 0.0, cli_cost_usd=res.get("cli_cost_usd"),
                       tool_calls=res.get("tool_calls", 0), seconds=round(time.time() - t0, 1))
            for k in ("tools_offered", "cli_model_usage", "cli_turns"):
                if res.get(k):
                    row[k] = res[k]
            try:
                if res.get("isolation"):       # Sol R17 B1: any tool event / isolation warning stops the turn
                    row["isolation"] = res["isolation"]
                    raise BadReply("isolation: " + "; ".join(res["isolation"])[:300])
                args, notes = parse_reply(res["text"], group)
                row["command"] = args
                last_row = row
                break
            except BadReply as e:
                row["bad"] = str(e)
                if attempt == 2:
                    args, fallback = ["look"], True
                    row.update(command=args, fallback="look")
                    last_row = row
                    break
                log(run, row)
        if stop:
            break
        if args is None:          # two model errors in this turn: try the turn again
            continue
        rc, out, err, last_end = run_play(args, run_name, py, play, last_end)
        count = used_of(out)
        counted = rc == 0 and count is not None and count[0] == n
        last_row.update(play_rc=rc, play_out=out, play_err=err, counted=counted,
                        used_after=count[0] if count else None)
        log(run, last_row)
        shown = out if counted else (problem(err) + "\n" + out).strip()
        state["history"].append(result_line(n, args, shown, rc if counted else (rc or 1))
                                + (" (your reply was not valid: counted as look)" if fallback else ""))
        state["history"] = state["history"][-HISTORY:]
        if notes is not None:
            state["notes"] = notes
        if counted:
            play_errs = 0
            session += 1
            state["used"] = count[0]
            if args[0] == "ask":
                state["teacher"] = f'TEACHER ANSWER (to your question "{args[1]}"):\n{clean_view(out)}'
            else:
                state["view"], state["teacher"] = clean_view(out), ""
            state["done"] = DONE_MARK in out
        else:
            play_errs += 1
            if count is not None:
                state["used"] = count[0]
            if DONE_MARK in out or DONE_MARK in err:
                state["done"] = True
            if play_errs >= PLAY_ERRORS_MAX:
                save_state(run, state)
                stop = "play-errors"
                break
        save_state(run, state)
    tot = dict(totals(run), stop=stop, used=state["used"], budget=budget, t=time.time())
    (run / "lean_totals.json").write_text(json.dumps(tot, indent=1), encoding="utf-8")
    return tot


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--model", choices=sorted(BACKENDS), required=True)
    ap.add_argument("--group", choices=["plain", "teacher"], required=True)
    ap.add_argument("--budget", type=int, default=1000)
    ap.add_argument("--effort", choices=EFFORTS, default="high", help="reasoning effort for both backends (r21)")
    ap.add_argument("--max-commands", type=int, default=None, help="stop after N commands in this session (smoke)")
    a = ap.parse_args()
    global EFFORT
    EFFORT = a.effort
    tot = play_game(a.run, a.model, a.group, a.budget, a.max_commands)
    print(json.dumps(tot, indent=1))


if __name__ == "__main__":
    main()
