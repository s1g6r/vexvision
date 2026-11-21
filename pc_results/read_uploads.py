r"""Find and read single-match uploads for one event.

`watch.py` only takes videos longer than ten minutes, because it is looking for event streams. The
other kind of footage is a team posting one match at a time -- the Hawks Robotics Lake Park videos
are exactly this -- and those are two or three minutes long, so the station never sees them. The
task file handled Lake Park by hand. This does the same job for any event, which matters because
there are seven more Illinois events between now and March, starting with Niles on 21 Nov.

How a video is trusted. The same way `watch.py` trusts a stream: the teams have to match the
official results. Here the team numbers come out of the **title**, and they must be exactly the
four teams of one official match at that event. Anything that matches no match, or more than one,
is listed and left alone. That is what keeps a video from a different event out -- a Lake Park
search also turns up "333y + 355p vs 60441t + 60441y @ lake park vex", whose four teams are not
any Lake Park match, and it is correctly left alone.

  python pc_results\read_uploads.py --event 64295 --prefix lp-          # read what it finds
  python pc_results\read_uploads.py --event 65760 --prefix niles1- -n   # just list, read nothing

With no --prefix it uses `u<event>-`. Already-read matches are skipped, so it is safe to re-run
after an event adds more uploads.
"""
import argparse, json, os, re, subprocess, sys, urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "pc"))
sys.path.insert(0, ROOT)
import stream_job as S
import watch as W

TEAM = re.compile(r"(?<![A-Z0-9])(\d{1,5}[A-Z])(?![A-Z0-9])", re.I)
MIN_SECONDS, MAX_SECONDS = 45, 600

QUIET = False          # a dry run prints but doesn't write to the shared log

def log(msg):
    line = f"- {datetime.now():%Y-%m-%d %H:%M} uploads: {msg}"
    print(line, flush=True)
    if QUIET:
        return
    with open(os.path.join(ROOT, "pc_results", "LOG.md"), "a", encoding="utf-8") as f:
        f.write(line + "\n")

def queries(ev_name, teams):
    """Event-name searches, plus the team numbers that host events tend to upload under."""
    short = W.short(ev_name)
    qs = [f"{short} VEX Override match", f"{short} VEX Q", f"{short} robotics vs"]
    qs += [f"{t} {short}" for t in teams]
    return qs

def search(q, n=20):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True,
            "extractor_args": {"youtube": {"player_client": ["android"]}}}
    with yt_dlp.YoutubeDL(opts) as y:
        r = y.extract_info(f"ytsearch{n}:{q}", download=False)
    return [(e["id"], e.get("title") or "", e.get("duration") or 0,
             e.get("uploader") or e.get("channel") or "") for e in r.get("entries") or []]

def match_for(title, off):
    """The one official match whose four teams are exactly the title's teams, or None."""
    nums = {t.upper() for t in TEAM.findall(title)}
    if len(nums) < 4:
        return None, nums
    hits = [m for m, s in off.items() if set(s["red"] + s["blue"]) == nums]
    return (hits[0] if len(hits) == 1 else None), nums

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", required=True, type=int)
    ap.add_argument("--prefix")
    ap.add_argument("--hosts", default="", help="comma-separated team numbers to search as well")
    ap.add_argument("-n", "--dry-run", action="store_true")
    a = ap.parse_args()
    prefix = a.prefix or f"u{a.event}-"
    global QUIET
    QUIET = a.dry_run

    ev_name, off = S.official(a.event)
    if not off:
        log(f"event {a.event} has no official results yet; nothing to match uploads against")
        return
    full = W.get(f"events/{a.event}.json")
    ev_teams = [t["number"] for t in full["teams"]]
    hosts = [h.strip().upper() for h in a.hosts.split(",") if h.strip()]
    log(f"event {a.event} {W.short(ev_name)}: {len(off)} official matches, {len(ev_teams)} teams")

    seen, found, rejected = {}, {}, []
    for q in queries(ev_name, hosts or ev_teams[:12]):
        try:
            res = search(q)
        except Exception as e:
            log(f"search failed for {q!r}: {e}"); continue
        for vid, title, dur, up in res:
            if vid in seen:
                continue
            seen[vid] = True
            if not (MIN_SECONDS <= (dur or 0) <= MAX_SECONDS):
                continue
            name, nums = match_for(title, off)
            if not name:
                # Searching a bare team number drags in anything that shares it -- "321A" also
                # finds a shelf of Schindler 321A elevator videos. Only a near miss is worth
                # reporting: four team numbers in the title, three of them at this event.
                if len(nums & set(ev_teams)) >= 3:
                    rejected.append((vid, title, sorted(nums)))
                continue
            found.setdefault(name, (vid, title, up))

    for vid, title, nums in rejected:
        log(f"  left alone, teams {nums} are not one match here: {vid} {title[:60]!r}")
    if not found:
        log("  no single-match uploads matched an official match")
        return
    log(f"  {len(found)} upload(s) matched: " + ", ".join(sorted(found)))

    for name in sorted(found):
        vid, title, up = found[name]
        mid = prefix + name.lower().replace(" ", "")
        if os.path.exists(os.path.join(ROOT, "pc_results", mid + ".perc.json.gz")):
            log(f"  {name} already read")
            continue
        log(f"  {name} <- {vid} '{title[:60]}' by {up}")
        if a.dry_run:
            continue
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "pc", "stream_job.py"),
                        "--video", vid, "--event", str(a.event), "--prefix", prefix,
                        "--single", "--match", name], cwd=ROOT)

if __name__ == "__main__":
    main()
