"""Scouting numbers per team from every tracked match.

Reads the raw tracking results (analyze output) listed in the replay index and
writes site2/data/team_stats.json:
  {team: {"matches": [{id, event, match, alliance}], "n": n,
          "ft_per_match": ..., "top_speed_fps": ..., "opp_side": share of driver
          control spent past the Autonomous Line, "midfield": share in the
          Midfield, "auton_ft": distance moved in autonomous,
          "heat": 24x24 occupancy grid (row 0 = far wall, field seen from the red side)}}
Only tracks whose robot was seen at least 55% of the time and matches with at
least 60% of frames calibrated count.

Usage: python -m tools.team_stats --raw DIR --index site2/data/replays/index.json --out site2/data/team_stats.json
"""
import argparse, json, os
import numpy as np
from vexvision import field as F
from tools.export_replay import smooth

G = 24
SURE = 0.75      # naming confidence needed before a robot's driving counts toward its team

def stats_for(track, alliance, t0):
    h = [p for p in track if p[0] >= t0]
    if len(h) < 10:
        return None
    sm = smooth(h)                       # same smoothing as the replay, so jitter isn't counted as driving
    a = np.array([[p[0], p[1] * 1000, p[2] * 1000, p[4]] for p in sm], float)
    t, x, y, seen = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    dt = np.diff(t); step = np.hypot(np.diff(x), np.diff(y))
    ok = step < 2500 * np.maximum(dt, 1e-3) * 1.5
    dist = step[ok].sum() / 304.8
    sp = step[ok] / np.maximum(dt[ok], 1e-3)
    top = float(np.percentile(sp, 95)) / 304.8 if len(sp) else 0.0
    auton = (t - t0) < 15
    driver = ~auton
    side = np.array([F.side_of(xi, yi) for xi, yi in zip(x, y)])
    opp = float(np.mean(side[driver] != alliance)) if driver.any() else 0.0
    mid = float(np.mean([abs(xi) + abs(yi) <= F.MIDFIELD_R for xi, yi in zip(x[driver], y[driver])])) if driver.any() else 0.0
    au = step[(t[1:] - t0) < 15][ok[(t[1:] - t0) < 15]].sum() / 304.8
    heat = np.zeros((G, G))
    for xi, yi, s in zip(x, y, seen):
        if not s:
            continue
        i = int(np.clip((F.HALF - yi) / (2 * F.HALF) * G, 0, G - 1)); j = int(np.clip((xi + F.HALF) / (2 * F.HALF) * G, 0, G - 1))
        heat[i, j] += 1
    return {"ft": dist, "top": top, "opp": opp, "mid": mid, "auton_ft": au, "heat": heat, "seen": float(seen.mean())}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True); ap.add_argument("--index", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--extra", nargs="*", default=[], help="id=raw.json pairs for replays outside the index")
    a = ap.parse_args()
    idx = json.load(open(a.index)) if os.path.exists(a.index) else []
    items = [(x, os.path.join(a.raw, x["id"] + ".json")) for x in idx if not x.get("error") and x.get("calibrated", 0) >= 0.6]
    for e in a.extra:
        k, p = e.split("=", 1); meta = json.loads(open(p.replace(".json", ".meta.json")).read()) if os.path.exists(p.replace(".json", ".meta.json")) else {}
        items.append(({"id": k, **meta}, p))
    teams = {}
    for meta, path in items:
        if not os.path.exists(path):
            continue
        r = json.load(open(path))
        t0 = r.get("t_start") or 0
        for rb in r.get("robots", []):
            if not rb.get("team"):
                continue
            T = teams.setdefault(rb["team"], {"matches": [], "_s": []})
            sure = (rb.get("confidence") or 0) >= SURE
            T["matches"].append({"id": meta["id"], "event": meta.get("event"), "match": meta.get("match"),
                                 "alliance": rb["alliance"], "named": sure})
            if not sure or rb.get("seen_share", 0) < 0.55:
                continue     # only count a robot's driving once we know which of the two it was
            s = stats_for(r["raw_tracks"][str(rb["track"])], rb["alliance"], t0)
            if s:
                T["_s"].append(s)
    out = {}
    for team, T in teams.items():
        S = T["_s"]
        if not S:
            out[team] = {"matches": T["matches"], "n": 0}
            continue
        heat = sum(s["heat"] for s in S); heat = heat / (heat.max() or 1)
        out[team] = {"matches": T["matches"], "n": len(S),
                     "ft_per_match": round(float(np.mean([s["ft"] for s in S])), 1),
                     "top_speed_fps": round(float(np.median([s["top"] for s in S])), 1),
                     "opp_side": round(float(np.mean([s["opp"] for s in S])), 3),
                     "midfield": round(float(np.mean([s["mid"] for s in S])), 3),
                     "auton_ft": round(float(np.mean([s["auton_ft"] for s in S])), 1),
                     "heat": [[round(float(v), 2) for v in row] for row in heat]}
    json.dump(out, open(a.out, "w"), separators=(",", ":"))
    print(len(out), "teams from", len(items), "matches")

if __name__ == "__main__":
    main()
