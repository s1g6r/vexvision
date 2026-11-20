"""Track every downloaded match video and export a replay for each (resumable).

For each video in the catalog that exists in --videos and has no result yet:
analyze it (models loaded once), save the raw result, export the replay with
the catalog's event/match/teams, and add a line to the index with quality
numbers (share of frames calibrated, share of time each robot was seen) so the
site can show only the ones that tracked well.

Usage: python -m tools.batch_replays --videos DIR --weights G.pt,R.pt --raw DIR --out site2/data/replays
"""
import argparse, json, os, subprocess, sys, time
import numpy as np
from vexvision import analyze as AN, stream
from vexvision.detect import Detector

PRIORITY = ["Highlander", "Harbor Havoc", "Great Planes", "Blank", "Mall of America", "Smoky", "Silk Road", "GHOST", "Speedway"]

def order(cat):
    def key(v):
        e = v.get("e") or v.get("event") or ""
        p = next((i for i, k in enumerate(PRIORITY) if k.lower() in e.lower()), len(PRIORITY))
        return (p, e, v.get("match") or "")
    return sorted(cat, key=key)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="data/catalog.json"); ap.add_argument("--videos", required=True)
    ap.add_argument("--weights", required=True); ap.add_argument("--raw", required=True)
    ap.add_argument("--out", default="site2/data/replays"); ap.add_argument("--fps", type=float, default=3)
    ap.add_argument("--limit", type=int, default=999)
    ap.add_argument("--shard", default="0/1", help="i/n: this process takes every n-th match starting at i")
    a = ap.parse_args()
    os.makedirs(a.raw, exist_ok=True); os.makedirs(a.out, exist_ok=True)
    cat = [v for v in json.load(open(a.catalog)) if v["kind"] == "match" and v.get("red") and v.get("blue")
           and len(v["red"]) == 2 and len(v["blue"]) == 2 and os.path.exists(os.path.join(a.videos, v["id"] + ".mp4"))]
    det = Detector(a.weights)
    si, sn = map(int, a.shard.split("/"))
    idx_path = os.path.join(a.out, "index.json" if sn == 1 else f"index_{si}.json")
    index = json.load(open(idx_path)) if os.path.exists(idx_path) else []
    done = set()
    for f in os.listdir(a.out):                     # matches any shard already finished
        if f.startswith("index") and f.endswith(".json"):
            done |= {x["id"] for x in json.load(open(os.path.join(a.out, f)))}
    n = 0
    for k, v in enumerate(order(cat)):
        if k % sn != si or v["id"] in done or n >= a.limit:
            continue
        n += 1
        path = os.path.join(a.videos, v["id"] + ".mp4")
        raw = os.path.join(a.raw, v["id"] + ".json")
        t0 = time.time()
        teams = {"red": v["red"], "blue": v["blue"]}
        try:
            if not os.path.exists(raw):
                res = AN.analyze(stream.video_frames(path, 0, None, fps=a.fps), det, teams=teams)
                perc = res.pop("perception", None)
                if perc is not None:      # what the models saw, so tracking can be redone without the video
                    json.dump(perc, open(raw.replace(".json", ".perc.json"), "w"), default=float, separators=(",", ":"))
                json.dump(res, open(raw, "w"), default=float)
            res = json.load(open(raw))
        except Exception as e:
            print(v["id"], "failed", e, flush=True)
            index.append({"id": v["id"], "error": str(e)[:200]}); json.dump(index, open(idx_path, "w"), indent=0)
            continue
        entry = {"id": v["id"], "event": v.get("event"), "match": v.get("match"), "red": v["red"], "blue": v["blue"],
                 "video": v["id"], "seconds": round(time.time() - t0)}
        if "robots" not in res:
            entry["error"] = res.get("error")
        else:
            entry["calibrated"] = round(len(res["cal_log"]) / max(1, res["frames"]), 2)
            entry["seen"] = round(float(np.mean([r["seen_share"] for r in res["robots"]])), 2)
            entry["named"] = sum(1 for r in res["robots"] if r.get("team"))
            meta = {k: entry[k] for k in ("event", "match", "red", "blue", "video")}
            subprocess.run([sys.executable, "-m", "tools.export_replay", raw, path, "--out", a.out, "--id", v["id"],
                            "--meta", json.dumps(meta)], check=False)
        index.append(entry)
        json.dump(index, open(idx_path, "w"), indent=0)
        print(json.dumps(entry), flush=True)

if __name__ == "__main__":
    main()
