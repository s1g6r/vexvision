"""Turn per-frame observations into scoring events credited to robots.

Inputs per frame (from detection and the goal / Toggle readers):
- goal_obs[goal] = [(t, {"red": n, "blue": n, "yellow": n}), ...] visible pin halves on that goal
- toggle_obs[quad] = [(t, "red" | "blue" | "yellow" | "split" | None), ...]  ("split": half turned, counts for no one;
  readings made before Nov 23 have no "split")
- robot paths from track.py: {tid: [(t, x, y, seen), ...]} plus {tid: alliance}

Events:
- placement: a goal's half count for a colour rises and holds (default 0.75 s),
  credited to the robot nearest the goal just before the rise, preferring the
  alliance that owns that pin colour (red/yellow pins are red's, blue/yellow
  are blue's, yellow/yellow can be anyone's).
- toggle: a Toggle's colour changes and holds, credited to the robot closest
  to that wall, preferring the alliance of the new colour.
- midfield: robots inside the Midfield diamond when the match ends.
"""
import numpy as np
from . import field as F

def stable_series(obs, hold=0.75):
    """Collapse noisy (t, value) readings into (t_start, value) runs that held >= hold s."""
    runs = []
    cur, start, last_t = None, None, None
    for t, v in obs:
        if v != cur:
            if cur is not None and last_t - start >= hold:
                runs.append((start, cur))
            cur, start = v, t
        last_t = t
    if cur is not None and last_t is not None and last_t - start >= hold:
        runs.append((start, cur))
    # merge consecutive equal runs separated by short blips
    merged = []
    for t, v in runs:
        if not merged or merged[-1][1] != v:
            merged.append((t, v))
    return merged

def robot_pos(paths, tid, t):
    h = paths[tid]
    ts = np.array([p[0] for p in h])
    if len(ts) == 0:
        return None
    i = int(np.clip(np.searchsorted(ts, t), 1, len(ts) - 1))
    (ta, xa, ya, _), (tb, xb, yb, _) = h[i - 1], h[i]
    w = 0 if tb == ta else (t - ta) / (tb - ta)
    w = min(1, max(0, w))
    return xa + w * (xb - xa), ya + w * (yb - ya)

def nearest_robot(paths, alliances, point, t, window=1.5, prefer=None, max_dist=900):
    best = None
    for tid in paths:
        ds = []
        for dt in np.linspace(-window, 0, 7):
            p = robot_pos(paths, tid, t + dt)
            if p is not None:
                ds.append(np.hypot(p[0] - point[0], p[1] - point[1]))
        if not ds:
            continue
        d = min(ds)
        if prefer and alliances.get(tid) != prefer:
            d += 350          # soft preference, not a hard rule
        if d <= max_dist and (best is None or d < best[1]):
            best = (tid, d)
    return best

COLOUR_OWNER = {"red": "red", "blue": "blue", "yellow": None}

def placements(goal_obs, paths, alliances, hold=0.75, auton_end=15.0):
    events = []
    for gname, obs in goal_obs.items():
        g = F.GOAL_BY_NAME[gname]
        for colour in ("red", "blue", "yellow"):
            ser = stable_series([(t, h.get(colour, 0)) for t, h in obs], hold)
            for (t0, v0), (t1, v1) in zip(ser, ser[1:]):
                if v1 > v0:
                    who = nearest_robot(paths, alliances, (g.x, g.y), t1, prefer=COLOUR_OWNER[colour])
                    events.append({"type": "placement", "t": t1, "goal": gname, "colour": colour,
                                   "halves": v1 - v0, "quadrant": g.quadrant,
                                   "robot": who[0] if who else None, "dist_mm": round(who[1]) if who else None,
                                   "auton": t1 <= auton_end})
                elif v1 < v0:
                    events.append({"type": "removal", "t": t1, "goal": gname, "colour": colour,
                                   "halves": v0 - v1, "quadrant": g.quadrant, "auton": t1 <= auton_end})
    return sorted(events, key=lambda e: e["t"])

def toggle_flips(toggle_obs, paths, alliances, hold=0.75, auton_end=15.0):
    events = []
    for q, obs in toggle_obs.items():
        ser = stable_series([(t, c) for t, c in obs if c], hold)
        tx, ty = F.TOGGLES[q]
        for (t0, c0), (t1, c1) in zip(ser, ser[1:]):
            if c1 == "split":
                continue
            who = nearest_robot(paths, alliances, (tx, ty), t1, prefer=c1 if c1 in ("red", "blue") else None, max_dist=1100)
            events.append({"type": "toggle", "t": t1, "quadrant": q, "from": c0, "to": c1,
                           "robot": who[0] if who else None, "auton": t1 <= auton_end})
    return events

def midfield_at(paths, t):
    out = {}
    for tid in paths:
        p = robot_pos(paths, tid, t)
        if p is not None and abs(p[0]) + abs(p[1]) <= F.MIDFIELD_R:
            out[tid] = True
    return out

def final_state(goal_obs, toggle_obs, paths, alliances, t_end):
    """Field state at the end of the match from the last stable readings."""
    halves = {}
    for gname, obs in goal_obs.items():
        q = F.GOAL_BY_NAME[gname].quadrant
        last = [h for t, h in obs if t <= t_end][-5:]
        if not last:
            continue
        hq = halves.setdefault(q, {"red": 0, "blue": 0, "yellow": 0})
        for c in hq:
            hq[c] += int(np.median([h.get(c, 0) for h in last]))
    toggles = {}
    for q, obs in toggle_obs.items():
        vals = [c for t, c in obs if t <= t_end and c][-7:]
        if vals:
            toggles[q] = max(set(vals), key=vals.count)
    in_mid = midfield_at(paths, t_end)
    robots_mid = {"red": 0, "blue": 0}
    for tid in in_mid:
        robots_mid[alliances[tid]] += 1
    mid_owner = None if robots_mid["red"] == robots_mid["blue"] else max(robots_mid, key=robots_mid.get)
    return {"halves": halves, "toggles": toggles, "robots_in_mid": robots_mid, "mid_owner": mid_owner,
            "midfield_robots": sorted(in_mid)}
