"""Check what the camera saw against the referees' score, and say what it missed.

The official result (from the VEX Events API) gives each alliance's final
score. The broadcast's running score, when the producer shows one, gives the
score at every moment. Both are used as constraints:

1. Final check: score the vision field state with the game rules and compare
   with the official score. The gap is reported per alliance as points the
   camera missed (positive) or over-counted (negative).
2. Running score: every jump in an alliance's running score should line up
   with detected events at that time. Jumps with no matching event become
   "unseen" events at that moment, credited to the alliance robot that was
   nearest a goal, and marked as inferred.
3. Credit: each robot's points = points from its own events, plus a share of
   the alliance's unexplained points in proportion to its share of seen
   scoring. Inferred points are kept separate so a team page can show
   "seen" and "inferred" contributions honestly.
"""
import numpy as np
from . import field as F
from .events import nearest_robot, stable_series

def score_state(state, auton_winner=None, auton_bonus=F.PTS_AUTON_BONUS):
    out = {}
    for a in ("red", "blue"):
        out[a] = F.alliance_score(state["halves"], state["toggles"], state["mid_owner"],
                                  state["robots_in_mid"], auton_winner, a, auton_bonus)
    return out

def event_points(e, toggles_now):
    if e["type"] != "placement":
        return {}
    c = e["colour"]
    if c in ("red", "blue"):
        return {c: F.PTS_ALLIANCE_HALF * e["halves"]}
    owner = toggles_now.get(e["quadrant"])
    if owner in ("red", "blue"):
        return {owner: F.PTS_OWNED_YELLOW_HALF * e["halves"]}
    return {}

def score_jumps(running, hold=0.5):
    """running: [(t, red, blue)] -> {alliance: [(t, delta)]}"""
    out = {}
    for i, a in enumerate(("red", "blue")):
        ser = stable_series([(t, r[i + 1]) for t, *r in [(x[0], x[1], x[2]) for x in running] if r[i + 1] is not None], hold)
        out[a] = [(t1, v1 - v0) for (t0, v0), (t1, v1) in zip(ser, ser[1:]) if v1 != v0]
    return out

def reconcile(events, state, official, paths=None, alliances=None, running=None, auton_winner=None):
    est = score_state(state, auton_winner)
    report = {"vision_score": est, "official": official, "gap": {}, "inferred_events": []}
    for a in ("red", "blue"):
        if official and official.get(a) is not None:
            report["gap"][a] = official[a] - est[a]
    if running and paths is not None:
        jumps = score_jumps(running)
        toggles_now = dict(state["toggles"])
        for a, js in jumps.items():
            for t, d in js:
                near = [e for e in events if e["type"] == "placement" and abs(e["t"] - t) <= 2.0]
                seen = sum(event_points(e, toggles_now).get(a, 0) for e in near)
                missing = d - seen
                if missing > 0:
                    # credit to the alliance robot closest to any goal at that moment
                    best = None
                    for g in F.GOALS:
                        w = nearest_robot({k: v for k, v in paths.items() if alliances[k] == a}, alliances, (g.x, g.y), t, max_dist=800)
                        if w and (best is None or w[1] < best[1]):
                            best = (w[0], w[1], g.name)
                    report["inferred_events"].append({"t": t, "alliance": a, "points": missing,
                                                      "robot": best[0] if best else None,
                                                      "goal": best[2] if best else None})
    return report

def credit(events, state, alliances, report, paths=None):
    """Points per robot: seen (from its own events) and inferred (share of the gap)."""
    toggles = dict(state["toggles"])
    seen = {tid: 0.0 for tid in alliances}
    for e in events:
        if e.get("robot") is None:
            continue
        for a, p in event_points(e, toggles).items():
            if alliances.get(e["robot"]) == a:
                seen[e["robot"]] += p
    for tid in state.get("midfield_robots", []):
        seen[tid] += F.PTS_MIDFIELD_ROBOT
    inferred = {tid: 0.0 for tid in alliances}
    for ie in report.get("inferred_events", []):
        if ie["robot"] is not None:
            inferred[ie["robot"]] += ie["points"]
    for a in ("red", "blue"):
        gap = report.get("gap", {}).get(a)
        if gap is None:
            continue
        already = sum(inferred[t] for t in alliances if alliances[t] == a)
        # an over-count (negative gap) stays an alliance-level number; it isn't charged to robots
        rest = max(0.0, gap - already)
        mates = [t for t in alliances if alliances[t] == a]
        tot = sum(max(0, seen[t]) for t in mates)
        for t in mates:
            share = (seen[t] / tot) if tot > 0 else 1 / len(mates)
            inferred[t] += rest * share
    return {tid: {"seen": round(seen[tid], 1), "inferred": round(inferred[tid], 1)} for tid in alliances}
