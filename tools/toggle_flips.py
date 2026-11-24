"""Find the moments a robot actually flips a Toggle, and add them to each replay.

A flip is counted only when all three hold:
  - the Toggle on that wall is seen changing colour during the match (changes less than 4 s apart
    are one flip, ending on the last colour),
  - a robot is touching it: its centre within half a metre of the Toggle from 2 s before the change
    to half a second after (the closest one gets the credit),
  - it ends fully on one colour as seen from the field (a half-turned, two-colour Toggle counts for
    no one; flips checked on the video that ended like that are in data/toggle_split.json),
  - the new colour stays: once robots have moved away (over 0.7 m), at least 80% of the next 15 s
    of readings show it, or, with nobody clear of it, it is read at least twice more.

Robots merely parked near a Toggle (defending it, or scoring on a Goal beside it) never count.
Only the Toggles the camera can see are read, so counts are a floor, not a total.
Checked by eye against match video: 20 of 20 on the Speedway stream, 19 of 20 on single-match uploads.

    python -m tools.toggle_flips RAW REPLAYS_DIR OUT_JSON
"""
import glob, json, os, sys
import numpy as np
from vexvision import events as E, field as F

TOUCH = 500.0     # mm, robot centre to the Toggle
CLEAR = 700.0     # mm, everyone further than this counts as "moved away"
GROUP = 4.0       # s, colour changes closer than this are one flip
HOLD = 0.8


def _pos(path, t):
    if not path or t < path[0][0] - 1 or t > path[-1][0] + 1:
        return None
    p = np.asarray(path, float)
    return np.interp(t, p[:, 0], p[:, 1]) * 1000, np.interp(t, p[:, 0], p[:, 2]) * 1000


def flips(perc, robots, split_end=frozenset()):
    """robots: replay robots (team, alliance, path in metres, t after the match starts)."""
    ts = perc.get("t_start")
    if ts is None:
        return []
    out = []
    for q, obs in (perc.get("toggle_obs") or {}).items():
        tx, ty = F.TOGGLES[q]
        ins = [(t, c) for t, c in obs if c and ts <= t <= ts + 122]
        ser = E.stable_series(ins, 0.75)
        ch = [(t1, c0, c1) for (_, c0), (t1, c1) in zip(ser, ser[1:])]
        groups = []
        for c in ch:
            if groups and c[0] - groups[-1][-1][0] <= GROUP:
                groups[-1].append(c)
            else:
                groups.append([c])

        def dists(t):
            res = []
            for i, r in enumerate(robots):
                p = _pos(r["path"], t - ts)
                if p is not None:
                    res.append((float(np.hypot(p[0] - tx, p[1] - ty)), i))
            return res

        for g in groups:
            t1, c_from, c_to = g[0][0], g[0][1], g[-1][2]
            if c_from == c_to:
                continue
            # ending half turned ("split", or found so on the video) is not a flip; it is kept as a
            # "half" so a robot that keeps leaving Toggles half turned can be spotted
            half = c_to == "split" or (q, round(t1 - ts, 2)) in split_end
            if not half and c_to not in ("red", "blue", "yellow"):
                continue
            near = [d for tt in np.arange(t1 - 2, g[-1][0] + 0.6, 1 / 3) for d in dists(tt)]
            if not near or min(near)[0] > TOUCH:
                continue
            wi = min(near)[1]; who = robots[wi]
            after = [(t, c) for t, c in ins if g[-1][0] < t <= g[-1][0] + 15]
            clear = [c for t, c in after if min([d for d, _ in dists(t)] or [9e9]) > CLEAR]
            if clear:
                if sum(c == c_to for c in clear) / len(clear) < HOLD:
                    continue
            elif sum(c == c_to for _, c in after) < 2:
                continue
            nxt = [t for t, c in ser if t > g[-1][0] and c != c_to]
            until = round(nxt[0] - ts, 2) if nxt else None
            out.append({"t": round(t1 - ts, 2), "until": until, "type": "half" if half else "flip", "q": q, "robot": wi, "team": who.get("team"), "alliance": who["alliance"], "to": c_to,
                        "theirs": F.QUADRANT_COLOR[q] != who["alliance"]})
    return sorted(out, key=lambda e: e["t"])


SPLIT = {}   # flips checked on the video that ended half turned (data/toggle_split.json)

def main(raw, rdir, out_path):
    sp = os.path.join(os.path.dirname(out_path), "toggle_split.json")
    SPLIT.update(json.load(open(sp)) if os.path.exists(sp) else {})
    allf, n = {}, 0
    for f in sorted(glob.glob(os.path.join(rdir, "*.json"))):
        mid = os.path.basename(f)[:-5]
        pp = os.path.join(raw, mid + ".perc.json")
        if mid == "index" or not os.path.exists(pp):
            continue
        R = json.load(open(f))
        if not isinstance(R, dict) or "robots" not in R:
            continue
        fl = flips(json.load(open(pp)), R["robots"], {(x["q"], x["t"]) for x in SPLIT.get(mid, [])})
        # the old colour-change events were unreliable and unused; flips replace them
        R["events"] = [e for e in R["events"] if e.get("type") not in ("toggle", "flip", "half")] + fl
        R["events"].sort(key=lambda e: e["t"])
        json.dump(R, open(f, "w"), separators=(",", ":"))
        allf[mid] = fl; n += sum(e["type"] == "flip" for e in fl)
    json.dump(allf, open(out_path, "w"), indent=0)
    print(f"{n} Toggle flips in {sum(1 for v in allf.values() if any(e['type'] == 'flip' for e in v))} of {len(allf)} matches,"
          f" {sum(e['type'] == 'half' for v in allf.values() for e in v)} left half turned")


if __name__ == "__main__":
    main(*sys.argv[1:4])
