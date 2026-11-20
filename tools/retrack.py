"""Redo tracking, naming and events from saved perception logs (raw/<id>.perc.json)
and re-export the replays, keeping the stills already cut. Takes seconds per match.
Usage: python -m tools.retrack RAW_DIR REPLAY_DIR [ids...]"""
import json, os, subprocess, sys
import numpy as np
from vexvision import analyze as AN

def main():
    raw, rep = sys.argv[1], sys.argv[2]
    ids = sys.argv[3:] or sorted(f[:-10] for f in os.listdir(raw) if f.endswith(".perc.json"))
    idx_p = os.path.join(rep, "index.json")
    index = {x["id"]: x for x in json.load(open(idx_p))} if os.path.exists(idx_p) else {}
    for i in ids:
        P = json.load(open(os.path.join(raw, i + ".perc.json")))
        res = AN.reason(P)
        json.dump(res, open(os.path.join(raw, i + ".json"), "w"), default=float)
        if "robots" not in res:
            print(i, res.get("error")); continue
        e = index.get(i)
        if e:
            e["seen"] = round(float(np.mean([r["seen_share"] for r in res["robots"]])), 2)
            e["named"] = sum(1 for r in res["robots"] if r.get("team"))
            e["sure"] = sum(1 for r in res["robots"] if (r.get("confidence") or 0) >= 0.75)
            meta = {k: e.get(k) for k in ("event", "match", "red", "blue", "video")}
        else:
            meta = {}
        vid = os.path.join("/mnt/user-data/uploads/vexvisionstuff/videos", i + ".mp4")
        subprocess.run([sys.executable, "-m", "tools.export_replay", os.path.join(raw, i + ".json"), vid,
                        "--out", rep, "--id", i, "--meta", json.dumps(meta), "--keep-stills"], check=False)
        print(i, "seen", e and e["seen"], [(r["team"], r.get("confidence"), r["seen_share"]) for r in res["robots"]])
    if index:
        json.dump(list(index.values()), open(idx_p, "w"), indent=0)

if __name__ == "__main__":
    main()
