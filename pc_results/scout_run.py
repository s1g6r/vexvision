r"""One scheduled run of the scout station. This is what the Windows task starts.

It wraps tools/pc/watch.py with the four things a repeating, unattended task needs:

1. **One at a time.** A run can take many hours, and on event weekends the task fires every two
   hours, so without this the runs would pile up and fight over the PC and over git. A lock file
   holds the pid; a run gives up quietly if another is alive. A lock left behind by a reboot or a
   crash is ignored once it is more than 20 hours old.
2. **A time budget** (default 10 hours). Some events are enormous -- the Speedway Signature
   stream alone is 7.7 hours of video across 236 matches, for one Illinois team -- and reading one
   of those to the end would take days, during which the lock would hold off every other run and a
   fresh Illinois event could sit unread all weekend. So a run stops when its time is up. Nothing
   is lost: finished matches are already on disk, watch.py skips them next time, and events are
   tried in order of how many Illinois teams played them, so a new Illinois event comes before the
   leftovers of a big out-of-state one.
3. **In step with GitHub.** The cloud side also commits to `pc-results`, so rebase on it before
   adding anything, otherwise watch.py's push is refused and results sit here unnoticed. Anything
   watch.py didn't get to push (because its time ran out mid-stream) is committed and pushed at
   the end.
4. **Tidy clips**, so the disk doesn't fill up over a season.

Console output, including any crash, goes to %LOCALAPPDATA%\vexvision\watch_console.log, which is
outside the repo on purpose so it is never committed. The readable log of what was found is
pc_results/LOG.md, which is pushed.

  python pc_results/scout_run.py [--budget-hours 10] [--no-push] [--region Illinois]
"""
import os, subprocess, sys, threading, time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOGDIR = os.path.join(os.environ.get("LOCALAPPDATA", HERE), "vexvision")
CONSOLE = os.path.join(LOGDIR, "watch_console.log")
LOCK = os.path.join(LOGDIR, "watch.lock")
STALE = 20 * 3600
PY = sys.executable

def say(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(CONSOLE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def alive(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out

def take_lock():
    if os.path.exists(LOCK):
        age = time.time() - os.path.getmtime(LOCK)
        try:
            pid = int(open(LOCK).read().split()[0])
        except Exception:
            pid = None
        if age < STALE and pid and alive(pid):
            say(f"another run (pid {pid}) is still going after {age / 3600:.1f} h; leaving it alone")
            return False
        say(f"clearing a stale lock ({age / 3600:.1f} h old)")
        os.remove(LOCK)
    with open(LOCK, "w") as f:
        f.write(f"{os.getpid()} {datetime.now():%Y-%m-%d %H:%M:%S}")
    return True

def run(cmd, what, budget=None):
    """Run a child and copy its output into the console log as it appears, not at the end:
    watch.py runs for hours, and a traceback is no use if it only shows up once it's over.
    With a budget (seconds), the whole child process tree is stopped when the time is up."""
    say(f"$ {' '.join(cmd)}")
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, bufsize=1, env=env, encoding="utf-8", errors="replace")
    timed_out = threading.Event()

    def guard():
        if timed_out.wait(budget):        # set early = the child finished on its own
            return
        timed_out.set()
        say(f"{what}: {budget / 3600:.1f} h budget used up, stopping it (it picks up where it left off next run)")
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)

    g = threading.Thread(target=guard, daemon=True) if budget else None
    if g:
        g.start()
    try:
        for line in p.stdout:
            say("  " + line.rstrip())
    finally:
        p.wait()
        was_timeout = timed_out.is_set()
        timed_out.set()                   # release the guard if the child finished first
    if p.returncode and not was_timeout:
        say(f"{what} exited {p.returncode}")
    return p.returncode

def git(*args):
    p = subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")

def push_leftovers():
    """watch.py pushes after each stream. If its time ran out mid-stream, the matches it did
    finish are on disk but uncommitted, so send them now rather than leaving them for tomorrow."""
    rc, out = git("status", "--porcelain", "--", "pc_results")
    if not out.strip():
        return
    say("pushing results watch.py didn't get to")
    for args in (("add", "pc_results"), ("commit", "-q", "-m", "Scout station results"),
                 ("push", "-q", "origin", "HEAD:pc-results")):
        rc, out = git(*args)
        if rc:
            say(f"  git {args[0]} failed: {out.strip()[:300]}")
            return

def main():
    argv = sys.argv[1:]
    budget = 10.0
    if "--budget-hours" in argv:
        i = argv.index("--budget-hours")
        budget = float(argv[i + 1]); del argv[i:i + 2]
    os.makedirs(LOGDIR, exist_ok=True)
    say(f"===== scheduled run starting (budget {budget:.1f} h) =====")
    # Everything below assumes pc-results is checked out: the rebase and the push both name it,
    # so on another branch this would rebase that branch onto pc-results and then push it there.
    # If someone has left the repo on main, do nothing and say so.
    rc, branch = git("rev-parse", "--abbrev-ref", "HEAD")
    branch = branch.strip()
    if branch != "pc-results":
        say(f"the repo is on '{branch}', not pc-results -- stopping. "
            f"Run `git checkout pc-results` in {ROOT} and this will pick up again by itself.")
        return
    if not take_lock():
        return
    try:
        run(["git", "pull", "--rebase", "--autostash", "-q", "origin", "pc-results"], "git pull")
        run([PY, os.path.join(ROOT, "tools", "pc", "watch.py")] + argv, "watch.py",
            budget=budget * 3600 if budget > 0 else None)
        if "--no-push" not in argv:
            push_leftovers()
        run([PY, os.path.join(HERE, "prune_clips.py")], "prune_clips.py")
    finally:
        if os.path.exists(LOCK):
            os.remove(LOCK)
        say("===== scheduled run finished =====")

if __name__ == "__main__":
    main()
