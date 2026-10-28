"""One command at a time: block batched play.py calls (round 5 on; same rule for both groups).

Round 4 (21 Oct): Luna sent batches of up to 50 calls about 1 s apart and wasted its game; the round 3 Luna games
did it too. Three checks, all before the call counts as a command:
  1. lock      - another call on the same game is still running (parallel calls);
  2. same shell - this call comes from the same shell command as the previous one (a loop in one command);
  3. cooldown  - the previous call ended (or was refused) less than COOLDOWN seconds ago (a tool-level loop; real
                 turns need 1.4 s+). Refused calls restart the cooldown, so a fast loop gets nothing through.
A script that sleeps between calls in separate shell commands still gets through: the audit looks for regular timing.
A persistent shell session (one shell process for many commands) would be refused after its first call; our players
(Claude Code Bash tool, Codex shell) start a new shell per command (checked live 21 Oct, Sol GD1).
"""
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

COOLDOWN = 1.0
# Processes that sit between the player's agent and play.py inside one shell command. The outermost one is "the
# shell command" (the venv python.exe is a launcher that starts the real python, so python appears twice).
SHELLS = {"python.exe", "pythonw.exe", "py.exe", "powershell.exe", "pwsh.exe", "cmd.exe", "bash.exe", "sh.exe",
          "dash.exe", "zsh.exe", "env.exe", "timeout.exe", "wsl.exe"}


class Blocked(SystemExit):
    pass


def _processes():
    """pid -> (parent pid, exe name) for all processes (Windows Toolhelp snapshot)."""
    class PE(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k.CreateToolhelp32Snapshot(2, 0)          # TH32CS_SNAPPROCESS
    out, e = {}, PE()
    e.dwSize = ctypes.sizeof(PE)
    ok = k.Process32FirstW(snap, ctypes.byref(e))
    while ok:
        out[e.th32ProcessID] = (e.th32ParentProcessID, e.szExeFile.lower())
        ok = k.Process32NextW(snap, ctypes.byref(e))
    k.CloseHandle(snap)
    return out


def _started(pid):
    """Creation time of a process (guards against a reused pid), or 0 if it cannot be read."""
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.restype = wintypes.HANDLE
    h = k.OpenProcess(0x1000, False, pid)            # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return 0
    t = [wintypes.FILETIME() for _ in range(4)]
    ok = k.GetProcessTimes(h, *[ctypes.byref(x) for x in t])
    k.CloseHandle(h)
    return (t[0].dwHighDateTime << 32 | t[0].dwLowDateTime) if ok else 0


def outer_shell(procs, pid):
    """The outermost shell-like ancestor of pid (walking up while the parent is still a shell or python)."""
    top, seen = pid, set()
    while True:
        seen.add(top)
        parent = procs.get(top, (0, ""))[0]
        if parent in seen or parent not in procs or procs[parent][1] not in SHELLS:
            return top
        top = parent


def shell_key():
    if os.name != "nt":
        return f"{os.getsid(0)}"
    procs = _processes()
    top = outer_shell(procs, os.getpid())
    return f"{top}:{_started(top)}"


def _write(path, data):
    """Atomic write (Sol GD1: a reader must never see a half-written file)."""
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    for _ in range(50):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:                      # Windows: another process has it open for a moment
            time.sleep(0.02)
    os.replace(tmp, path)


def _read(path):
    for _ in range(50):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (PermissionError, json.JSONDecodeError):
            time.sleep(0.02)
    return json.loads(path.read_text(encoding="utf-8"))


_held = {}   # lock path -> open file; the OS lock lives as long as this handle (or this process)


def _take_lock(lock):
    """True if we now hold the OS lock on busy.lock. The OS frees it when the holder exits or crashes, so there is no
    stale lock to take over (Sol GD2: taking over a dead call's lock could race). The file is never deleted."""
    f = open(lock, "a+b")
    for _ in range(10):        # Windows frees a dead holder's lock after a short delay; a live command holds it longer
        try:
            if os.name == "nt":
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            _held[lock] = f
            return True
        except OSError:
            time.sleep(0.05)
    f.close()
    return False


def _drop_lock(lock):
    f = _held.pop(lock, None)
    if f is None:
        return
    if os.name == "nt":
        import msvcrt
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    f.close()


def check(run, now=None, key=None):
    """Raise Blocked (with a short message for the player) if this call is part of a batch. Else take the lock.

    Call release(run, key) when the command is done. last_call.json is only written while holding the lock.
    """
    now = time.time() if now is None else now
    key = shell_key() if key is None else key
    lock = run / "busy.lock"
    if not _take_lock(lock):
        _refuse(run, now, key, "another command on this game is still running")
    last = run / "last_call.json"
    if last.exists():
        prev = _read(last)
        last_try = max(prev["end"], prev.get("refused", 0))
        why = ("several play.py calls in one shell command" if prev["key"] == key else
               "the previous command ended less than 1 second ago" if now - last_try < COOLDOWN else None)
        if why:
            _write(last, dict(prev, refused=now))            # refusals restart the cooldown
            _drop_lock(lock)
            _refuse(run, now, key, why)
    return lock


def release(run, key=None, now=None):
    """Write the end time and free the lock. Only the lock holder writes last_call.json (Sol GD2)."""
    lock = run / "busy.lock"
    if lock not in _held:
        return
    key = shell_key() if key is None else key
    try:
        _write(run / "last_call.json", {"key": key, "end": time.time() if now is None else now})
    finally:
        _drop_lock(lock)


def _refuse(run, now, key, why):
    with open(run / "blocked.jsonl", "a", encoding="utf-8") as f:     # for the audit; not a command
        f.write(json.dumps({"t": now, "key": key, "why": why, "argv": sys.argv[1:]}) + "\n")
    raise Blocked(f"NOT RUN ({why}). Run one command at a time, each as its own shell command, and read its "
                  "result before the next. This did not count as a command.")
