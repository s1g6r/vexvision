"""Always-on scout station. Run it once a day (and every hour or two on event weekends):
finds new Override events with Illinois teams, looks for their YouTube streams, checks a stream
really is that event (the team numbers on screen must match the official team list), reads
every match with stream_job.py, and pushes the results to the pc-results branch.

  python tools/pc/watch.py [--region Illinois] [--no-push]

State lives in pc_results/state.json, a plain log in pc_results/LOG.md."""
import argparse, json, os, re, subprocess, sys, time, urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "pc_results")
BASE = "https://stats.2360arachnid.com/data/override"
get = lambda p: json.load(urllib.request.urlopen(f"{BASE}/{p}", timeout=30))
DONE_ELSEWHERE = {64351: "cc-", 65014: "gl-"}       # already read on the Mac

def log(msg):
    line = f"- {datetime.now():%Y-%m-%d %H:%M} {msg}"
    print(line, flush=True)
    with open(os.path.join(OUT, "LOG.md"), "a", encoding="utf-8") as f:
        f.write(line + "\n")

def short(name):
    s = re.split(r":", name or "")[0]
    s = re.sub(r"\b(VEX|V5|Robotics|Competition|RC|Override|High School|Teams?|Middle School|and)\b", " ", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()

def search(q, n=15):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True,
            "extractor_args": {"youtube": {"player_client": ["android"]}}}
    with yt_dlp.YoutubeDL(opts) as y:
        r = y.extract_info(f"ytsearch{n}:{q}", download=False)
    return [(e["id"], e.get("title") or "", e.get("duration") or 0) for e in r.get("entries") or []]

def candidates(ev):
    s = short(ev["name"]); words = [w.lower() for w in s.split() if len(w) > 3][:3]
    seen, out = set(), []
    for q in (f"{s} VEX", f"{s} VEX V5 Override", f"{s} robotics livestream {ev['date'][:4]}"):
        try:
            res = search(q)
        except Exception as e:
            log(f"search failed for '{q}': {e}"); continue
        for vid, title, dur in res:
            t = title.lower()
            if vid in seen or not any(w in t for w in words):
                continue
            seen.add(vid); out.append((vid, title, dur))
    return out

def verify(vid, event_teams):
    """A stream is the event if team numbers read off the screen are on the event's team list."""
    import stream_job as S
    from vexvision import overlay
    url, dur, _ = S.direct_url(vid)
    hits = tries = 0
    for frac in (0.2, 0.35, 0.5, 0.65, 0.8):
        img = S.grab(url, dur * frac)
        if img is None:
            continue
        r = overlay.read(img); nums = r.red + r.blue
        if len(nums) >= 2:
            tries += 1; hits += sum(1 for n in nums if n in event_teams) >= max(2, len(nums) - 1)
    return tries >= 2 and hits >= tries - 1, dur

def update_code():
    """Pick up fixes pushed to main (the cloud side improves these scripts)."""
    subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=ROOT)
    subprocess.run(["git", "merge", "-q", "--no-edit", "-X", "theirs", "origin/main"], cwd=ROOT)

def push(msg):
    for cmd in (["git", "add", "pc_results"], ["git", "commit", "-q", "-m", msg],
                ["git", "pull", "-q", "--rebase", "origin", "pc-results"],
                ["git", "push", "-q", "origin", "HEAD:pc-results"]):
        subprocess.run(cmd, cwd=ROOT)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--region", default="Illinois"); ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()
    update_code()
    os.makedirs(OUT, exist_ok=True)
    sp = os.path.join(OUT, "state.json")
    state = json.load(open(sp)) if os.path.exists(sp) else {"events": {}, "videos": {}}
    teams = [t for t in get("leaderboard.json") if t.get("region") == a.region]
    meta = {e["id"]: e for e in get("meta.json")["events"]}
    from collections import Counter
    c = Counter()
    for t in teams:
        try:
            c.update(get(f"teams/{t['id']}.json").get("events", []))
        except Exception:
            pass
        time.sleep(0.1)
    for eid, n in c.most_common():
        ev = meta.get(eid)
        if not ev or ev.get("status") not in ("done", "live") or eid in DONE_ELSEWHERE:
            continue
        st = state["events"].setdefault(str(eid), {"name": ev["name"], "streams": [], "checked": None})
        if st.get("complete"):
            continue
        full = get(f"events/{eid}.json"); event_teams = {t["number"] for t in full["teams"]}
        log(f"event {eid} {short(ev['name'])} ({ev['date']}, {n} {a.region} teams)")
        for vid, title, dur in candidates(ev):
            if vid in state["videos"]:
                continue
            if dur and dur < 600:
                state["videos"][vid] = "too short"; continue          # single-match uploads: see TASK notes
            ok, dur = verify(vid, event_teams)
            state["videos"][vid] = "event stream" if ok else "not this event"
            json.dump(state, open(sp, "w"), indent=1)
            if not ok:
                continue
            log(f"  reading {vid} '{title}' ({dur / 60:.0f} min)")
            prefix = f"e{eid}-{len(st['streams'])}-"
            st["streams"].append(vid)
            subprocess.run([sys.executable, os.path.join(HERE, "stream_job.py"), "--video", vid, "--event", str(eid),
                            "--prefix", prefix], cwd=ROOT)
            if not a.no_push:
                push(f"Results for {short(ev['name'])} from {vid}")
        st["checked"] = datetime.now().isoformat(timespec="minutes")
        if ev.get("status") == "done" and st["streams"]:
            st["complete"] = True
        json.dump(state, open(sp, "w"), indent=1)
    if not a.no_push:
        push("Scout station state")

if __name__ == "__main__":
    main()
