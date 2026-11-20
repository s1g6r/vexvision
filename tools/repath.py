"""Rebuild the robot paths of already exported replays from their raw results,
without re-cutting the broadcast stills. Usage: repath.py RAW_DIR REPLAY_DIR [ids...]"""
import json, os, sys
from tools.export_replay import smooth

raw, rep = sys.argv[1], sys.argv[2]
ids = sys.argv[3:] or [f[:-5] for f in os.listdir(rep) if f.endswith(".json") and not f.startswith("index")]
for i in ids:
    rp, rr = os.path.join(rep, i + ".json"), os.path.join(raw, i + ".json")
    if not (os.path.exists(rp) and os.path.exists(rr)):
        print(i, "skipped"); continue
    R, r = json.load(open(rp)), json.load(open(rr))
    ts = r.get("t_start") or 0.0
    by = {str(x["track"]): x for x in r["robots"]}
    paths = {tid: smooth([(p[0] - ts, p[1], p[2], p[3]) for p in h]) for tid, h in r["raw_tracks"].items() if tid in by}
    order = [tid for tid in r["raw_tracks"] if tid in by]
    if len(order) != len(R["robots"]):
        print(i, "robot count differs, skipped"); continue
    for rb, tid in zip(R["robots"], order):
        rb["path"] = paths[tid]
    json.dump(R, open(rp, "w"), separators=(",", ":"))
    print(i, "ok")
