"""Full scouting reports: how a team plays, from every match where we know which robot it is.

Everything here comes from the tracked paths, not from reading scores:
- autonomous: the 15-second route, where it starts, and whether it is the same route
  from match to match
- defence: driver-control time on the other side of the Autonomous Line, and time
  right next to an opponent robot
- toggles: time spent at a Toggle (own colour or the other alliance's)
- goals: time spent at each kind of Goal (own Alliance Goals, neutral Quadrant Goals,
  the Center Goal, the other alliance's Goals)
- endgame: where it is in the last 10 seconds
- quals and eliminations, side by side
Each finding carries "moments": (match id, seconds into the match) to watch it happen.

Writes site2/data/reports.json: {team: {"n", "matches": [...], "summary": [sentences],
"sections": {...}}}.
Usage: python -m tools.scout_report --raw DIR --index site2/data/replays/index.json --out site2/data/reports.json
"""
import argparse, json, os, re
import numpy as np
from vexvision import field as F
from tools.export_replay import smooth

SURE = 0.75
NEAR_GOAL = 450.0        # mm, robot centre to goal centre: working that goal
NEAR_TOGGLE = 520.0      # mm, robot centre to the toggle on the wall
NEAR_OPP = 760.0         # mm, centre to centre: bumping or blocking an opponent
AUTON = 15.0

def flip(x, y, alliance):
    """Turn the field so the team's own side is always where red's is."""
    return (x, y) if alliance == "red" else (-x, -y)

def path_of(r, track, t0):
    h = [(p[0] - t0, p[1], p[2], p[3]) for p in r["raw_tracks"][str(track)]]
    if len(h) < 10:
        return None
    sm = smooth(h)
    return np.array([[p[0], p[1] * 1000, p[2] * 1000, p[4]] for p in sm], float)   # t, x, y, seen

def goal_kind(g, alliance):
    if g.kind == "center":
        return "center"
    if g.kind == "neutral":
        return "neutral"
    return "own" if g.kind == alliance else "opp"

def match_features(r, rb, meta):
    t0 = r.get("t_start") or 0.0
    td = (r.get("t_driver") or (t0 + AUTON)) - t0
    me = path_of(r, rb["track"], t0)
    if me is None:
        return None
    others = {x["track"]: (x["alliance"], path_of(r, x["track"], t0)) for x in r["robots"] if x["track"] != rb["track"]}
    t, x, y = me[:, 0], me[:, 1], me[:, 2]
    dt = np.r_[np.diff(t), 0.0]
    auton = (t >= 0) & (t < AUTON)
    driver = (t >= td) & (t <= td + 105)
    al = rb["alliance"]
    # opponents' positions at my sample times
    opp_d = np.full(len(t), np.inf)
    for tr, (a2, p) in others.items():
        if a2 == al or p is None:
            continue
        ox = np.interp(t, p[:, 0], p[:, 1]); oy = np.interp(t, p[:, 0], p[:, 2])
        opp_d = np.minimum(opp_d, np.hypot(ox - x, oy - y))
    side = np.array([F.side_of(a, b) for a, b in zip(x, y)])
    other_side = side != al
    near_opp = opp_d < NEAR_OPP
    D = dt[driver].sum() or 1.0
    # goals and toggles, driver control
    gtime = {"own": 0.0, "neutral": 0.0, "center": 0.0, "opp": 0.0}
    gfirst = {}
    for g in F.GOALS:
        at = driver & (np.hypot(x - g.x, y - g.y) < NEAR_GOAL)
        k = goal_kind(g, al)
        gtime[k] += dt[at].sum()
        if at.any() and k not in gfirst:
            gfirst[k] = float(t[np.argmax(at)])
    ttime = {"own": 0.0, "opp": 0.0}; tfirst = {}
    for q, (qx, qy) in F.TOGGLES.items():
        at = driver & (np.hypot(x - qx, y - qy) < NEAR_TOGGLE)
        k = "own" if F.QUADRANT_COLOR[q] == al else "opp"
        ttime[k] += dt[at].sum()
        if at.any() and k not in tfirst:
            tfirst[k] = float(t[np.argmax(at)])
    # longest stretch on the other side, for a "watch" moment
    best, cur, start, best_t = 0.0, 0.0, None, None
    for i in np.flatnonzero(driver):
        if other_side[i]:
            if start is None:
                start = t[i]
            cur = t[i] - start
            if cur > best:
                best, best_t = cur, start
        else:
            start, cur = None, 0.0
    # autonomous route, turned to own side, resampled every 0.5 s
    ts = np.arange(0, AUTON + 0.01, 0.5)
    if auton.sum() >= 5 and t[auton][0] < 3:
        ax = np.interp(ts, t[auton], x[auton]); ay = np.interp(ts, t[auton], y[auton])
        fx, fy = flip(ax, ay, al)
        route = np.stack([fx, fy], 1)
    else:
        route = None
    end = (t >= td + 95) & (t <= td + 105)
    ex, ey = (x[end].mean(), y[end].mean()) if end.any() else (np.nan, np.nan)
    elim = bool(re.match(r"(QF|SF|R16|Final|Semifinal|Finals)", meta.get("match") or ""))
    step = np.hypot(np.diff(x), np.diff(y)); ok = step < 2500 * np.maximum(np.diff(t), 1e-3) * 1.5
    return {
        "id": meta["id"], "match": meta.get("match"), "event": meta.get("event"), "alliance": al, "elim": elim,
        "partner": next((x2["team"] for x2 in r["robots"] if x2["alliance"] == al and x2["track"] != rb["track"]), None),
        "driver_s": round(float(D), 1),
        "other_side": round(float(dt[driver & other_side].sum() / D), 3),
        "near_opp": round(float(dt[driver & near_opp].sum() / D), 3),
        "near_opp_their_side": round(float(dt[driver & near_opp & other_side].sum() / D), 3),
        "goals": {k: round(v / D, 3) for k, v in gtime.items()},
        "goal_first": gfirst,
        "toggles": {k: round(v / D, 3) for k, v in ttime.items()},
        "toggle_first": tfirst,
        "midfield_end": bool(np.isfinite(ex) and abs(ex) + abs(ey) <= F.MIDFIELD_R),
        "end": None if not np.isfinite(ex) else [round(float(v) / 1000, 2) for v in flip(ex, ey, al)],
        "ft": round(float(step[ok & driver[1:]].sum() / 304.8), 0),
        "defence_t": None if best_t is None else round(float(best_t), 1), "defence_len": round(float(best), 1),
        "route": None if route is None else [[round(float(a) / 1000, 2), round(float(b) / 1000, 2)] for a, b in route],
        "driver_at": round(float(td), 1),
    }

def describe_point(x, y):
    """Plain words for a spot on the field, own side at bottom left (metres)."""
    best = min(F.GOALS, key=lambda g: np.hypot(x * 1000 - g.x, y * 1000 - g.y))
    # name goals as seen from the team's own side (red frame)
    names = {"C": "the Center Goal", "SW": "its own bottom Alliance Goal", "WS": "its own left Alliance Goal",
             "NE": "the other alliance's top Goal", "EN": "the other alliance's right Goal",
             "NW": "the neutral Goal top-left", "WN": "the neutral Goal on the left", "ES": "the neutral Goal on the right",
             "SE": "the neutral Goal bottom-right"}
    d = np.hypot(x * 1000 - best.x, y * 1000 - best.y)
    if d < 700:
        return names[best.name]
    if abs(x) + abs(y) <= F.MIDFIELD_R / 1000:
        return "the Midfield"
    return "its own side" if x + y < 0 else "the other side"

def route_groups(ms):
    """Which matches ran (nearly) the same autonomous: pairwise mean distance < 0.45 m."""
    R = [(m, np.array(m["route"])) for m in ms if m["route"]]
    if len(R) < 2:
        return R, [m for m, _ in R], (R[0][0] if R else None)
    n = len(R); D = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            D[i, j] = np.mean(np.hypot(*(R[i][1] - R[j][1]).T))
    medoid = int(np.argmin(np.sum(D, 1)))
    same = [R[i][0] for i in range(n) if D[medoid, i] < 0.45]
    return R, same, R[medoid][0]

def pct(v):
    return f"{round(v * 100)}%"

def summarise(team, ms):
    out, sec = [], {}
    n = len(ms)
    # autonomous
    R, same, med = route_groups(ms)
    if med is not None:
        start = describe_point(*med["route"][0]); finish = describe_point(*med["route"][-1])
        moved = sum(np.hypot(*(np.diff(np.array(med["route"]), axis=0)).T))
        if len(R) == 1:
            out.append(f"Autonomous (seen once): starts by {start} and ends at {finish}.")
        elif len(same) >= 2 and len(same) >= 0.6 * len(R):
            out.append(f"Runs the same autonomous in {len(same)} of {len(R)} matches: starts by {start} and ends at {finish}.")
        elif moved < 0.6:
            out.append(f"Barely moves in autonomous in most matches.")
        else:
            out.append(f"Changes its autonomous from match to match ({len(R)} seen).")
        sec["auton"] = {"same": [m["id"] for m in same], "typical": med["id"], "start": start, "finish": finish, "seen": len(R)}
    # defence
    os_ = np.mean([m["other_side"] for m in ms]); no = np.mean([m["near_opp_their_side"] for m in ms])
    if os_ >= 0.3 and no >= 0.08:
        out.append(f"Plays defence: {pct(os_)} of driver control on the other side, much of it right up against an opponent.")
    elif os_ >= 0.3:
        out.append(f"Spends {pct(os_)} of driver control on the other side of the field.")
    elif os_ <= 0.12:
        out.append(f"Stays home: only {pct(os_)} of driver control on the other side.")
    else:
        out.append(f"Mostly plays its own side ({pct(1 - os_)} of driver control), crossing over now and then.")
    sec["defence"] = {"other_side": round(float(os_), 3), "near_opp_their_side": round(float(no), 3)}
    # toggles
    to = np.mean([m["toggles"]["own"] + m["toggles"]["opp"] for m in ms]); topp = np.mean([m["toggles"]["opp"] for m in ms])
    if to >= 0.08:
        which = "including the other alliance's" if topp >= 0.03 else "mostly its own"
        out.append(f"Goes after Toggles: {pct(to)} of driver control right by a Toggle, {which}.")
    elif to <= 0.02:
        out.append("Rarely goes to the Toggles.")
    sec["toggles"] = {"share": round(float(to), 3), "opp": round(float(topp), 3)}
    # goals
    gk = {k: float(np.mean([m["goals"][k] for m in ms])) for k in ("own", "neutral", "center", "opp")}
    top = max(gk, key=gk.get)
    words = {"own": "its own Alliance Goals", "neutral": "the neutral Quadrant Goals", "center": "the Center Goal", "opp": "the other alliance's Goals"}
    if sum(gk.values()) > 0.05:
        out.append(f"Works {words[top]} most ({pct(gk[top])} of driver control there).")
    sec["goals"] = {k: round(v, 3) for k, v in gk.items()}
    # endgame
    mid = np.mean([m["midfield_end"] for m in ms])
    if mid >= 0.5:
        out.append(f"Ends in the Midfield in {sum(m['midfield_end'] for m in ms)} of {n} matches.")
    sec["endgame"] = {"midfield": round(float(mid), 3)}
    # quals vs elims
    q = [m for m in ms if not m["elim"]]; e = [m for m in ms if m["elim"]]
    if q and e:
        dq, de = np.mean([m["other_side"] for m in q]), np.mean([m["other_side"] for m in e])
        tq = np.mean([m["toggles"]["own"] + m["toggles"]["opp"] for m in q]); te = np.mean([m["toggles"]["own"] + m["toggles"]["opp"] for m in e])
        bits = []
        if abs(de - dq) >= 0.1:
            bits.append(f"{'more' if de > dq else 'less'} time on the other side ({pct(dq)} in quals, {pct(de)} in elims)")
        if abs(te - tq) >= 0.05:
            bits.append(f"{'more' if te > tq else 'less'} time at Toggles ({pct(tq)} → {pct(te)})")
        out.append(("In eliminations it plays differently: " + " and ".join(bits) + ".") if bits else "Plays the same way in eliminations as in qualifications.")
        sec["split"] = {"quals": len(q), "elims": len(e)}
    return out, sec

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True); ap.add_argument("--index", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    idx = [x for x in json.load(open(a.index)) if not x.get("error") and (x.get("calibrated") or 0) >= 0.6]
    teams = {}
    for meta in idx:
        p = os.path.join(a.raw, meta["id"] + ".json")
        if not os.path.exists(p):
            continue
        r = json.load(open(p))
        for rb in r.get("robots", []):
            if not rb.get("team") or (rb.get("confidence") or 0) < SURE or rb.get("seen_share", 0) < 0.55:
                continue
            f = match_features(r, rb, meta)
            if f:
                teams.setdefault(rb["team"], []).append(f)
    out = {}
    for team, ms in teams.items():
        summary, sec = summarise(team, ms)
        out[team] = {"n": len(ms), "summary": summary, "sections": sec, "matches": ms}
    json.dump(out, open(a.out, "w"), separators=(",", ":"))
    print(len(out), "teams with a report")

if __name__ == "__main__":
    main()
