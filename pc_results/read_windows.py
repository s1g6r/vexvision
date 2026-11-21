r"""Read a list of known match windows out of event streams.

Why this exists. `stream_job.py` finds matches itself by scanning a stream's overlay, which is the
right thing when nothing is known about the stream. But for Cornfield Clash and Great Lakes #1 the
Mac has already done that work and the answers are committed on `main`: `data/cc_todo.txt` gives
each Cornfield match's start and end second, and `site2/data/videos.json` gives a start second for
every Cornfield and Great Lakes match. What is missing is the reading, not the finding -- the Mac
indexed 65 Cornfield and 78 Great Lakes matches but has tracked only 16 and 8 of them.

So this takes a work list of windows and reads them, skipping any already done. It reuses
`stream_job`'s own machinery for everything that matters -- the direct URL, the ffmpeg cut, the
frame feed, the detector, `analyze` -- so a match read here is a match read exactly as `watch.py`
would have read it, and the output files are the same shape.

Teams always come from the **official results**, looked up by match name, never from the work list.
`docs/LOG.md` records three video titles elsewhere that had red and blue the wrong way round, so
the schedule is the only safe source.

  python pc_results\read_windows.py pc_results\mac_backlog.json
  python pc_results\read_windows.py pc_results\mac_backlog.json --only cc      # ids starting "cc"
  python pc_results\read_windows.py pc_results\mac_backlog.json -n             # list, read nothing

The work list is a JSON list of {id, stream, start, length, event_id, match}.
"""
import argparse, gzip, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "pc"))
sys.path.insert(0, ROOT)
import stream_job as S
from vexvision import analyze as AN
from vexvision.detect import Detector

from datetime import datetime

def log(msg, quiet=False):
    line = f"- {datetime.now():%Y-%m-%d %H:%M} windows: {msg}"
    print(line, flush=True)
    if not quiet:
        with open(os.path.join(ROOT, "pc_results", "LOG.md"), "a", encoding="utf-8") as f:
            f.write(line + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("list")
    ap.add_argument("--only", default="", help="only ids starting with this")
    ap.add_argument("--out", default=os.path.join(ROOT, "pc_results"))
    ap.add_argument("-n", "--dry-run", action="store_true")
    a = ap.parse_args()

    work = json.load(open(a.list, encoding="utf-8"))
    if a.only:
        work = [w for w in work if w["id"].startswith(a.only)]
    clips = os.path.join(a.out, "clips")
    os.makedirs(clips, exist_ok=True)

    todo = [w for w in work if not os.path.exists(os.path.join(a.out, w["id"] + ".perc.json.gz"))]
    log(f"{len(work)} in the list, {len(work) - len(todo)} already read, {len(todo)} to go",
        quiet=a.dry_run)
    if a.dry_run:
        for w in todo:
            print(f"   {w['id']:16} {w['stream']}  {w['start']}s +{w['length']}s  {w['match']}")
        return
    if not todo:
        return

    # One official-results fetch per event, and one detector for the whole run.
    off = {}
    for eid in sorted({w["event_id"] for w in todo}):
        name, matches = S.official(eid)
        off[eid] = (name, matches)
        log(f"event {eid} {name[:50] if name else '?'}: {len(matches)} official matches")
    det = Detector(",".join(os.path.join(ROOT, "tools", "pc", w) for w in ("goals.pt", "robots.pt")))

    urls = {}
    for w in todo:
        mid, vid = w["id"], w["stream"]
        ev_name, matches = off[w["event_id"]]
        teams = matches.get(w["match"])
        if not teams:
            log(f"  {mid}: '{w['match']}' is not in the official results, skipped")
            continue
        clip = os.path.join(clips, mid + ".mp4")
        if not os.path.exists(clip):
            if vid not in urls:
                urls[vid] = S.direct_url(vid)[0]
            if not S.cut(urls[vid], w["start"], w["length"], clip):
                urls[vid] = S.direct_url(vid)[0]          # links expire after a few hours
                if not S.cut(urls[vid], w["start"], w["length"], clip):
                    log(f"  {mid}: download failed")
                    continue
        t = time.time()
        res = AN.analyze(S.frames(clip), det, teams=teams, log=lambda *x: None)
        P = res.pop("perception")
        P["looks"] = {"2360A": "black"}
        dst = os.path.join(a.out, mid + ".perc.json.gz")
        with gzip.open(dst + ".tmp", "wt") as f:
            json.dump(P, f, default=float, separators=(",", ":"))
        os.replace(dst + ".tmp", dst)
        json.dump({"id": mid, "event": ev_name, "event_id": w["event_id"], "match": w["match"],
                   **teams, "stream": vid, "start": w["start"], "length": w["length"],
                   "source": "windows from the Mac's stream map"},
                  open(os.path.join(a.out, mid + ".meta.json"), "w"))
        log(f"  {mid} ({w['match']}) done in {time.time() - t:.0f}s")

if __name__ == "__main__":
    main()
