r"""Work through the Cornfield / Great Lakes backlog, committing and pushing as it goes.

The Mac indexed 65 Cornfield and 78 Great Lakes matches but tracked only 16 and 8 of them, so 118
matches at the two biggest Illinois events (26 and 35 Illinois teams) had never been read by
anything. `mac_backlog.json` is the work list, built from the Mac's own stream map, and
`read_windows.py` reads it. This wraps that with the things an unattended job needs: its own lock,
a push every few matches so results reach the cloud side as they appear rather than in one lump at
the end, and the same rebase-first habit as the nightly run.

Started by the Windows task "VexVision backlog", which has no schedule -- it is run on demand:

    Start-ScheduledTask -TaskName 'VexVision backlog'

Safe to stop and start again: finished matches are skipped, so it picks up where it left off.
Console output goes to %LOCALAPPDATA%\vexvision\backlog_console.log.
"""
import json, os, subprocess, sys, time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOGDIR = os.path.join(os.environ.get("LOCALAPPDATA", HERE), "vexvision")
CONSOLE = os.path.join(LOGDIR, "backlog_console.log")
LOCK = os.path.join(LOGDIR, "backlog.lock")
LIST = os.path.join(HERE, "mac_backlog.json")
STALE = 30 * 3600
PUSH_EVERY = 4                      # matches
PY = sys.executable

def say(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(CONSOLE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def alive(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                         capture_output=True, text=True).stdout
    return str(pid) in out

def take_lock():
    if os.path.exists(LOCK):
        age = time.time() - os.path.getmtime(LOCK)
        try:
            pid = int(open(LOCK).read().split()[0])
        except Exception:
            pid = None
        if age < STALE and pid and alive(pid):
            say(f"another backlog run (pid {pid}) is still going; leaving it alone")
            return False
        say(f"clearing a stale backlog lock ({age / 3600:.1f} h old)")
        os.remove(LOCK)
    with open(LOCK, "w") as f:
        f.write(f"{os.getpid()} {datetime.now():%Y-%m-%d %H:%M:%S}")
    return True

def git(*args):
    p = subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")

def push(msg):
    rc, out = git("status", "--porcelain", "--", "pc_results")
    if not out.strip():
        return
    git("pull", "--rebase", "--autostash", "-q", "origin", "pc-results")
    for args in (("add", "pc_results"), ("commit", "-q", "-m", msg),
                 ("push", "-q", "origin", "HEAD:pc-results")):
        rc, out = git(*args)
        if rc:
            say(f"  git {args[0]} failed: {out.strip()[:300]}")
            return
    say(f"  pushed: {msg}")

def left():
    work = json.load(open(LIST, encoding="utf-8"))
    return [w for w in work
            if not os.path.exists(os.path.join(ROOT, "pc_results", w["id"] + ".perc.json.gz"))]

def main():
    os.makedirs(LOGDIR, exist_ok=True)
    say("===== backlog run starting =====")
    rc, branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch.strip() != "pc-results":
        say(f"the repo is on '{branch.strip()}', not pc-results -- stopping")
        return
    if not take_lock():
        return
    try:
        todo = left()
        say(f"{len(todo)} matches still to read")
        while todo:
            batch = todo[:PUSH_EVERY]
            for w in batch:
                # One match per call, so a crash costs one match and the push cadence is ours.
                p = subprocess.run([PY, os.path.join(HERE, "read_windows.py"), LIST,
                                    "--only", w["id"]], cwd=ROOT,
                                   capture_output=True, text=True,
                                   env=dict(os.environ, PYTHONUNBUFFERED="1"))
                for line in (p.stdout or "").splitlines():
                    if "windows:" in line:
                        say("  " + line.split("windows:", 1)[1].strip())
                if p.returncode:
                    say(f"  {w['id']}: read_windows exited {p.returncode}")
                    for line in (p.stderr or "").splitlines()[-4:]:
                        say(f"    {line}")
            push(f"Backlog: {batch[0]['id']}..{batch[-1]['id']} from the Mac's stream map")
            after = left()
            if len(after) >= len(todo):              # nothing finished: stop rather than spin
                say("a whole batch produced nothing; stopping so it can be looked at")
                break
            todo = after
            say(f"{len(todo)} left")
        if not todo:
            say("backlog empty")
    finally:
        if os.path.exists(LOCK):
            os.remove(LOCK)
        push("Backlog progress")
        say("===== backlog run finished =====")

if __name__ == "__main__":
    main()
