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

OWN_NAMES = {"C": "the Center Goal", "SW": "its own bottom Alliance Goal", "WS": "its own left Alliance Goal",
             "NE": "the other alliance's top Goal", "EN": "the other alliance's right Goal",
             "NW": "the top-left neutral Goal", "WN": "the left neutral Goal", "ES": "the right neutral Goal",
             "SE": "the bottom-right neutral Goal"}
FLIP = {"C": "C", "SW": "NE", "WS": "EN", "NE": "SW", "EN": "WS", "NW": "SE", "WN": "ES", "ES": "WN", "SE": "NW"}

def goal_name(gname, alliance):
    """Name a goal as seen from the team's own side (own side at bottom left)."""
    return OWN_NAMES[gname if alliance == "red" else FLIP[gname]]

TOGGLE_NAMES = {"S": "its own bottom Toggle", "W": "its own left Toggle", "N": "the other alliance's top Toggle", "E": "the other alliance's right Toggle"}

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
    # speed, from samples where the robot was actually seen at both ends
    seen = me[:, 3] > 0.5
    v = []
    for i in range(len(t) - 1):
        if driver[i] and seen[i] and seen[i + 1] and 0 < t[i + 1] - t[i] <= 0.7:
            v.append(step[i] / (t[i + 1] - t[i]) / 304.8)
    v = np.array(v)
    moving = v[v > 0.5]
    # goal and toggle visits: in the zone at least 1 s, after being away at least 2 s
    visits = []
    for g in F.GOALS:
        inz = driver & (np.hypot(x - g.x, y - g.y) < NEAR_GOAL)
        k = goal_kind(g, al); name = goal_name(g.name, al)
        i, last_out = 0, -1e9
        while i < len(t):
            if inz[i]:
                j = i
                while j < len(t) and inz[j]:
                    j += 1
                if t[min(j, len(t) - 1)] - t[i] >= 1.0 and t[i] - last_out >= 2.0:
                    visits.append((float(t[i]), k, name))
                last_out = t[min(j, len(t) - 1)]; i = j
            else:
                i += 1
    visits.sort()
    starts = [v_[0] for v_ in visits]
    tv = 0
    for q, (qx, qy) in F.TOGGLES.items():
        inz = driver & (np.hypot(x - qx, y - qy) < NEAR_TOGGLE)
        tv += int(np.sum(inz[1:] & ~inz[:-1]))
    carry = rb.get("carry")
    if carry:
        own = carry["red"] if al == "red" else carry["blue"]; oth = carry["blue"] if al == "red" else carry["red"]
        tot = own + oth + carry["yellow"]
        carry = {"own": round(own / tot, 3), "yellow": round(carry["yellow"] / tot, 3), "other": round(oth / tot, 3)} if tot > 0.002 else None
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
        "top_fps": round(float(np.percentile(v, 95)), 2) if len(v) > 20 else None,
        "cruise_fps": round(float(np.median(moving)), 2) if len(moving) > 20 else None,
        "moving": round(float(len(moving) / max(1, len(v))), 3),
        "visits": [[round(a, 1), k, n_] for a, k, n_ in visits],
        "cycle_s": round(float(np.median(np.diff(starts))), 1) if len(starts) >= 3 else None,
        "toggle_visits": tv,
        "carry": carry,
    }

def describe_point(x, y):
    """Plain words for a spot on the field, own side at bottom left (metres)."""
    X, Y = x * 1000, y * 1000
    g = min(F.GOALS, key=lambda g: np.hypot(X - g.x, Y - g.y))
    if np.hypot(X - g.x, Y - g.y) < 600:
        return OWN_NAMES[g.name]
    q = min(F.TOGGLES, key=lambda k: np.hypot(X - F.TOGGLES[k][0], Y - F.TOGGLES[k][1]))
    if np.hypot(X - F.TOGGLES[q][0], Y - F.TOGGLES[q][1]) < 600:
        return TOGGLE_NAMES[q]
    if abs(X) + abs(Y) <= F.MIDFIELD_R:
        return "the Midfield"
    corner = ("left" if X < -900 else "right" if X > 900 else "middle") if abs(X) > abs(Y) else ("bottom" if Y < -900 else "top" if Y > 900 else "middle")
    side = "its own side" if X + Y < 0 else "the other side"
    return f"the {corner} of {side}" if corner != "middle" else side

def auton_steps(route):
    """Turn a 15 s route (own-side frame, 0.5 s samples) into a short list of places it stops at."""
    r = np.array(route)
    sp = np.r_[0, np.hypot(*np.diff(r, axis=0).T) / 0.5]
    steps, i = [], 1
    while i < len(r):
        if sp[i] < 0.25:
            j = i
            while j < len(r) and sp[j] < 0.25:
                j += 1
            if j - i >= 2:
                place = describe_point(*r[(i + j) // 2])
                if not steps or steps[-1][1] != place:
                    steps.append((round(i * 0.5, 1), place))
            i = j
        else:
            i += 1
    start = describe_point(*r[0]); end = describe_point(*r[-1])
    crosses = bool(np.any(r[:, 0] + r[:, 1] > 0.15))
    moved = float(np.sum(np.hypot(*np.diff(r, axis=0).T)))
    stops = [s_ for s_ in steps if s_[1] != start and s_[0] >= 1.5]   # a pause in the first second is still the start
    if stops and stops[-1][1] == end:
        stops = stops[:-1]
    return {"start": start, "stops": stops, "end": end, "crosses": crosses, "moved_m": round(moved, 1)}

def auton_text(st):
    if st["moved_m"] < 0.6:
        return f"stays at {st['start']}"
    if not st["stops"] and st["start"] == st["end"]:
        return f"works around {st['start']}" + (", crossing the Autonomous Line" if st["crosses"] else "")
    parts = [f"starts at {st['start']}"]
    for t_, p in st["stops"][:3]:
        parts.append(f"stops at {p} ({t_:.0f} s)")
    parts.append(f"ends at {st['end']}")
    txt = ", ".join(parts[:-1]) + " and " + parts[-1]
    if st["crosses"]:
        txt += ", crossing the Autonomous Line"
    return txt

def route_clusters(ms):
    """Group matches that ran (nearly) the same autonomous: mean distance under 0.45 m."""
    R = [(m, np.array(m["route"])) for m in ms if m["route"]]
    left, out = list(range(len(R))), []
    while left:
        D = np.array([[np.mean(np.hypot(*(R[i][1] - R[j][1]).T)) for j in left] for i in left])
        k = int(np.argmax((D < 0.45).sum(1) - 1e-3 * D.sum(1)))
        mem = [left[j] for j in range(len(left)) if D[k, j] < 0.45]
        out.append({"typical": R[left[k]][0], "members": [R[i][0] for i in mem]})
        left = [i for i in left if i not in mem]
    return out

def pct(v):
    return f"{round(v * 100)}%"

def mean(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None

def summarise(team, ms):
    out, sec = [], {}
    n = len(ms)
    # --- autonomous: which route it runs most, and what that route does
    cl = route_clusters(ms)
    if cl:
        seen = sum(len(c["members"]) for c in cl)
        routes = []
        for i, c in enumerate(cl):
            st = auton_steps(c["typical"]["route"])
            routes.append({"label": "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[min(i, 25)], "count": len(c["members"]), "typical": c["typical"]["id"],
                           "members": [m["id"] for m in c["members"]], "steps": st, "text": auton_text(st)})
        top = routes[0]
        if seen == 1:
            out.append(f"Autonomous (seen once): {top['text']}.")
        elif top["count"] >= 2:
            out.append(f"Most-run autonomous ({top['count']} of {seen} matches): {top['text']}.")
        else:
            out.append(f"Ran a different autonomous in each of the {seen} matches seen. In {top['members'][0] and 'one'}, it {top['text']}.".replace("In one, it", "In one it"))
        sec["auton"] = {"seen": seen, "routes": routes}
    # --- what it scores: which goals it goes to, how often, and what it carries
    vis = [m["visits"] for m in ms]
    per = np.mean([len(v) for v in vis])
    names = {}
    kinds = {"own": 0, "neutral": 0, "center": 0, "opp": 0}
    for v in vis:
        for _, k, nm in v:
            names[nm] = names.get(nm, 0) + 1; kinds[k] += 1
    fav = sorted(names, key=lambda k: -names[k])[:2]
    cyc = mean([m["cycle_s"] for m in ms])
    if per >= 1:
        km = {k: v / max(1, n) for k, v in kinds.items()}
        parts = [f"{km['own']:.0f} of its own Alliance Goals", f"{km['neutral']:.0f} neutral", f"{km['center']:.0f} at the Center Goal", f"{km['opp']:.0f} of the other alliance's"]
        parts = [p_ for p_, k in zip(parts, ["own", "neutral", "center", "opp"]) if round(km[k]) >= 1]
        txt = f"Works about {per:.0f} {'Goal' if round(per) == 1 else 'Goals'} a match ({', '.join(parts)})"
        if cyc:
            txt += f", moving to a new Goal every {cyc:.0f} s or so"
        txt += f". Its favourite is {fav[0]}"
        out.append(txt + ".")
    carry = [m["carry"] for m in ms if m.get("carry")]
    cm = None
    if len(carry) >= 1:
        cm = {k: float(np.mean([c[k] for c in carry])) for k in ("own", "yellow", "other")}
        big = max(cm, key=cm.get)
        cw = {"own": "its own colour", "yellow": "yellows", "other": "the other alliance's colour"}
        rest = [k for k in ("own", "yellow") if k != big]
        out.append(f"Mostly handles {cw[big]}: {pct(cm[big])} of the cone colour seen on the robot, {cw[rest[0]]} {pct(cm[rest[0]])} (a rough read from the video).")
    sec["scoring"] = {"visits_per_match": round(float(per), 1), "cycle_s": cyc, "by_kind": {k: round(v / max(1, n), 1) for k, v in kinds.items()},
                      "favourites": [[k, round(names[k] / n, 1)] for k in sorted(names, key=lambda k: -names[k])[:5]], "carry": cm}
    # --- the robot itself
    top_ = mean([m["top_fps"] for m in ms]); cru = mean([m["cruise_fps"] for m in ms]); mov = mean([m["moving"] for m in ms])
    sec["robot"] = {"top_fps": top_, "cruise_fps": cru, "moving": mov, "ft": mean([m["ft"] for m in ms]), "toggle_visits": mean([m["toggle_visits"] for m in ms])}
    # --- defence
    os_ = np.mean([m["other_side"] for m in ms]); no = np.mean([m["near_opp_their_side"] for m in ms])
    if os_ >= 0.55 and no >= 0.15:
        out.append(f"Plays defence: {pct(os_)} of driver control on the other side, often right up against an opponent.")
    elif os_ >= 0.45:
        out.append(f"Spends {pct(os_)} of driver control on the other side of the field.")
    elif os_ <= 0.15:
        out.append(f"Stays home: only {pct(os_)} of driver control on the other side.")
    else:
        out.append(f"Mostly plays its own side ({pct(1 - os_)} of driver control), crossing over now and then.")
    sec["defence"] = {"other_side": round(float(os_), 3), "near_opp_their_side": round(float(no), 3)}
    # --- toggles
    to = np.mean([m["toggles"]["own"] + m["toggles"]["opp"] for m in ms]); topp = np.mean([m["toggles"]["opp"] for m in ms])
    tv = sec["robot"]["toggle_visits"] or 0
    if to >= 0.3:
        which = "including the other alliance's" if topp >= 0.19 else "mostly its own"
        out.append(f"Goes after Toggles: about {tv:.0f} {'trip' if round(tv) == 1 else 'trips'} a match, {pct(to)} of driver control right by one, {which}.")
    elif to <= 0.1:
        out.append("Rarely goes to the Toggles.")
    else:
        out.append(f"Visits the Toggles now and then: about {tv:.0f} {'trip' if round(tv) == 1 else 'trips'} a match." if round(tv) >= 1 else "Visits the Toggles now and then, less than once a match.")
    sec["toggles"] = {"share": round(float(to), 3), "opp": round(float(topp), 3), "trips": tv}
    # --- endgame
    mid = np.mean([m["midfield_end"] for m in ms])
    if mid >= 0.5:
        out.append(f"Ends in the Midfield in {sum(m['midfield_end'] for m in ms)} of {n} {'match' if n == 1 else 'matches'}.")
    sec["endgame"] = {"midfield": round(float(mid), 3)}
    # --- quals vs elims
    q = [m for m in ms if not m["elim"]]; e = [m for m in ms if m["elim"]]
    if q and e:
        dq, de = np.mean([m["other_side"] for m in q]), np.mean([m["other_side"] for m in e])
        tq = np.mean([m["toggles"]["own"] + m["toggles"]["opp"] for m in q]); te = np.mean([m["toggles"]["own"] + m["toggles"]["opp"] for m in e])
        vq, ve = np.mean([len(m["visits"]) for m in q]), np.mean([len(m["visits"]) for m in e])
        bits = []
        if abs(de - dq) >= 0.1:
            bits.append(f"{'more' if de > dq else 'less'} time on the other side ({pct(dq)} → {pct(de)})")
        if abs(te - tq) >= 0.05:
            bits.append(f"{'more' if te > tq else 'less'} time at Toggles ({pct(tq)} → {pct(te)})")
        if abs(ve - vq) >= 2:
            bits.append(f"{'more' if ve > vq else 'fewer'} Goal visits ({vq:.0f} → {ve:.0f} a match)")
        out.append(("In eliminations it plays differently: " + ", ".join(bits) + ".") if bits else "Plays the same way in eliminations as in qualifications.")
        sec["split"] = {"quals": len(q), "elims": len(e)}
    return out, sec

def tags(sec):
    """A few words for what kind of robot this is, for lists and match cards."""
    t = []
    d = sec.get("defence", {}); g = sec.get("scoring", {}).get("by_kind", {}); tg = sec.get("toggles", {})
    if d.get("other_side", 0) >= 0.55 and d.get("near_opp_their_side", 0) >= 0.15:
        t.append("Plays defence")
    elif d.get("other_side", 1) <= 0.15:
        t.append("Stays home")
    if tg.get("share", 0) >= 0.35:
        t.append("Toggle runner")
    if g:
        k = max(g, key=g.get)
        if g[k] >= 1:
            t.append({"own": "Own Goals", "neutral": "Neutral Goals", "center": "Center Goal", "opp": "Their Goals"}[k])
    if sec.get("endgame", {}).get("midfield", 0) >= 0.5:
        t.append("Ends in Midfield")
    a = sec.get("auton")
    if a and a["routes"] and a["routes"][0]["steps"]["crosses"]:
        t.append("Auton crosses over")
    return t

def ranks(out):
    """How a team compares with every other tracked team (share of teams it beats)."""
    def rank(key, f, higher=True):
        vals = {t: f(r) for t, r in out.items() if f(r) is not None}
        xs = sorted(vals.values())
        for t, v in vals.items():
            below = sum(1 for x in xs if (x < v if higher else x > v))
            out[t]["sections"].setdefault("ranks", {})[key] = round(below / max(1, len(xs) - 1), 2) if len(xs) > 1 else None
    rank("top_fps", lambda r: r["sections"]["robot"]["top_fps"])
    rank("visits", lambda r: r["sections"]["scoring"]["visits_per_match"])
    rank("cycle", lambda r: r["sections"]["scoring"]["cycle_s"], higher=False)
    for t, r in out.items():
        k = r["sections"].get("ranks", {}).get("top_fps"); sp = r["sections"]["robot"]["top_fps"]
        if k is not None and sp:
            word = "One of the fastest robots we tracked" if k >= 0.8 else "Quicker than most robots we tracked" if k >= 0.6 else "Slower than most robots we tracked" if k <= 0.2 else "Middle of the pack for speed"
            r["summary"].insert(min(3, len(r["summary"])), f"{word}: faster than {round(k * 100)}% of the {len(out)} teams.")

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
        out[team] = {"n": len(ms), "summary": summary, "sections": sec, "matches": ms, "tags": tags(sec)}
    ranks(out)
    json.dump(out, open(a.out, "w"), separators=(",", ":"))
    print(len(out), "teams with a report")

if __name__ == "__main__":
    main()
