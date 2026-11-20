"""Name robots across a whole event. A robot looks the same in every match it plays at one
event, and the official schedule says which teams were in each match. So for each team we
pick, in every match it played, the robot (of the two on its alliance) that looks most like
that team's robot in its other matches. A team that played with different partners is pinned
down this way; a pair that only ever played together stays unsure unless one of them is
already known (a known look, say).

Writes a hint file read by tools.retrack: {match id: {alliance: {"map": {track: team}, "confidence": c}}}.
Usage: python -m tools.event_names RAW_DIR INDEX OUT"""
import json, os, sys, random
from collections import defaultdict
import numpy as np

SURE = 0.75

def reid_desc(vs):
    """One look per robot from its crop embeddings: the mean of the crops closest to their
    own centre, so a stretch where the tracker briefly followed the wrong robot drops out."""
    V = np.array(vs)
    if len(V) < 4:
        return None
    m = V.mean(0); m /= np.linalg.norm(m)
    d = V @ m
    keep = V[d >= np.percentile(d, 35)]
    m = keep.mean(0)
    return m / np.linalg.norm(m)

def load(raw, idx, reid=None):
    """Per event, the decisions: one per (match, alliance) with two seen robots and two teams."""
    ev = defaultdict(list)
    for x in idx:
        p = os.path.join(raw, x["id"] + ".json")
        if not os.path.exists(p):
            continue
        r = json.load(open(p))
        if "robots" not in r:
            continue
        if reid:
            rp = os.path.join(reid, x["id"] + ".json")
            if not os.path.exists(rp):
                continue
            E = json.load(open(rp))
            for b in r["robots"]:
                b["desc"] = reid_desc(E.get(str(b["track"]), []))
        for a in ("red", "blue"):
            rb = [b for b in r["robots"] if b["alliance"] == a]
            teams = x.get(a) or []
            if len(rb) != 2 or len(teams) != 2 or any(b.get("desc") is None for b in rb):
                continue
            tA, tB = sorted(teams)
            # option 0: tA on the first robot; option 1: swapped
            cur = 0 if rb[0].get("team") == tA else 1
            anchor = cur if (rb[0].get("confidence") or 0) >= SURE else None
            ev[x["event"]].append({"match": x["id"], "alliance": a, "teams": (tA, tB), "tracks": (rb[0]["track"], rb[1]["track"]),
                                   "d": (np.asarray(rb[0]["desc"], float), np.asarray(rb[1]["desc"], float)), "x": cur, "anchor": anchor,
                                   "conf0": rb[0].get("confidence") or 0})
    return ev

def chosen(D, x):
    """(team, descriptor) pairs a decision puts forward under choice x."""
    tA, tB = D["teams"]; d0, d1 = D["d"]
    return [(tA, d0), (tB, d1)] if x == 0 else [(tA, d1), (tB, d0)]

def total(Ds, X):
    by = defaultdict(list)
    for D, x in zip(Ds, X):
        for t, d in chosen(D, x):
            by[t].append(d)
    c = 0.0
    for t, L in by.items():
        if len(L) > 1:
            M = np.array(L); c += float(np.sum(np.linalg.norm(M - M.mean(0), axis=1)))
    return c

def solve(Ds, restarts=12, seed=0):
    rng = random.Random(seed)
    best = None
    for r in range(restarts):
        X = [D["anchor"] if D["anchor"] is not None else (D["x"] if r == 0 else rng.randint(0, 1)) for D in Ds]
        for _ in range(30):
            changed = False
            for i in rng.sample(range(len(Ds)), len(Ds)):
                if Ds[i]["anchor"] is not None:
                    continue
                c = [total(Ds, X[:i] + [v] + X[i + 1:]) for v in (0, 1)]
                v = int(np.argmin(c))
                if v != X[i]:
                    X[i] = v; changed = True
            if not changed:
                break
        c = total(Ds, X)
        if best is None or c < best[0] - 1e-9:
            best = (c, X)
    return best[1]

def confidence(Ds, X, i, scale):
    """How much worse the best answer gets if this decision is flipped, either on its own or
    by swapping the two team names everywhere they played together (which is what an
    unpinned pair can do for free). Turned into 0.5..1 with a scale set from the data."""
    base = total(Ds, X)
    one = X[:i] + [1 - X[i]] + X[i + 1:]
    pair = set(Ds[i]["teams"])
    swap = [(1 - x) if (set(D["teams"]) == pair and D["anchor"] is None) else x for D, x in zip(Ds, X)]
    gaps = [total(Ds, one) - base]
    if any(set(D["teams"]) == pair and D["anchor"] is not None for D in Ds) is False:
        gaps.append(total(Ds, swap) - base)
    g = max(0.0, min(gaps))
    return 0.5 + 0.5 * (1 - np.exp(-g / scale))

def main():
    raw, idx_p, out = sys.argv[1:4]
    reid = sys.argv[4] if len(sys.argv) > 4 else None
    idx = json.load(open(idx_p))
    ev = load(raw, idx, reid)
    hint, scale = {}, 0.05
    quals = defaultdict(set)
    for x in idx:
        if (x.get("match") or "").startswith("Qual"):
            quals[x["event"]].add(x["id"])
    for e, Ds in ev.items():
        # Only where we have enough qualification matches: there partners change every match,
        # which is what pins a robot down. Elimination-only streams keep the same pairs and,
        # tested on known robots, got too many wrong.
        if len(Ds) < 2 or len(quals[e]) < 8:
            continue
        X = solve(Ds)
        for i, (D, x) in enumerate(zip(Ds, X)):
            c = 0.9 if D["anchor"] is not None else confidence(Ds, X, i, scale)
            tA, tB = D["teams"]; k0, k1 = D["tracks"]
            m = {k0: tA, k1: tB} if x == 0 else {k0: tB, k1: tA}
            if c >= 0.9:
                hint.setdefault(D["match"], {})[D["alliance"]] = {"map": m, "confidence": round(float(c), 3)}
        sure = sum(1 for D in Ds if D["alliance"] in hint.get(D["match"], {}))
        print(f"{e}: {sure} of {len(Ds)} alliances named for sure")
    json.dump(hint, open(out, "w"))

if __name__ == "__main__":
    main()
