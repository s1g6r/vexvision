"""Follow the four robots through a match, in field coordinates.

A VEX match has exactly four robots on the field (two per alliance) from the
first second to the last, so this tracker keeps exactly four tracks instead of
creating and deleting them like a generic multi-object tracker. That removes
the identity swaps generic trackers make when robots touch or hide behind a
goal stack.

- Positions are floor points in mm (bottom-centre of a robot box, mapped by H).
- Each track is a constant-velocity Kalman filter.
- Each frame, detections are matched to tracks with the Hungarian algorithm on
  a gated Mahalanobis cost; a robot that isn't seen keeps coasting.
- Alliance comes free at the start: robots must start on their own side of
  the Autonomous Line (<SG1>), so the two on the red side are red.
"""
from dataclasses import dataclass, field as dc_field
import numpy as np
from scipy.optimize import linear_sum_assignment
from . import field as F

MAX_SPEED = 2500.0          # mm/s, cap on the filter's velocity
REACH = 2300.0              # mm/s, how far a robot can plausibly have gone since it was last seen
NOISE = 350.0               # mm, floor-point noise: box bottoms jitter and robots overhang
INSIDE = F.HALF - 150       # robot centres stay this far inside the walls

@dataclass
class Track:
    tid: int
    alliance: str
    x: np.ndarray                      # [px, py, vx, vy]
    P: np.ndarray
    team: str = None
    last_seen: float = 0.0
    last_pos: np.ndarray = None
    colour: float = 0.0                # running red(+)/blue(-) evidence of what it has been matched to
    history: list = dc_field(default_factory=list)   # (t, x, y, seen)
    feats: list = dc_field(default_factory=list)     # appearance vectors

    def predict(self, dt, t, accel=3000.0):
        Fm = np.eye(4); Fm[0, 2] = Fm[1, 3] = dt
        G = np.array([[dt * dt / 2, 0], [0, dt * dt / 2], [dt, 0], [0, dt]])
        self.x = Fm @ self.x
        self.P = Fm @ self.P @ Fm.T + G @ G.T * accel ** 2
        if t - self.last_seen > 0.4:            # unseen: stop guessing it keeps driving
            self.x[2:] *= np.exp(-dt / 0.5)
        v = np.hypot(*self.x[2:])
        if v > MAX_SPEED:
            self.x[2:] *= MAX_SPEED / v
        self.x[:2] = np.clip(self.x[:2], -INSIDE, INSIDE)

    def update(self, z, r=150.0):
        Hm = np.array([[1, 0, 0, 0], [0, 1, 0, 0.0]])
        S = Hm @ self.P @ Hm.T + np.eye(2) * r ** 2
        K = self.P @ Hm.T @ np.linalg.inv(S)
        self.x = self.x + K @ (z - Hm @ self.x)
        self.P = (np.eye(4) - K @ Hm) @ self.P
        self.x[:2] = np.clip(self.x[:2], -INSIDE, INSIDE)

    def sign(self):
        return 1.0 if self.alliance == "red" else -1.0

def _dedupe(dets, r=260.0):
    """Two boxes on one robot happen when an arm or a held stack looks like a second robot."""
    keep = []
    for k in sorted(range(len(dets)), key=lambda k: -(dets[k][4] if len(dets[k]) > 4 else 1)):
        if all(np.hypot(dets[k][0] - dets[m][0], dets[k][1] - dets[m][1]) > r for m in keep):
            keep.append(k)
    return keep

class FourRobotTracker:
    """Exactly four tracks for the whole match.

    Matching cost per (track, detection) is distance in metres, measured from the
    better of the predicted position and where the robot was last seen, plus an
    appearance term and an alliance-colour term. A detection is only allowed if the
    robot could have driven there since it was last seen. A robot that is lost
    slows to a stop where it was rather than coasting off the field."""
    def __init__(self, n_per_alliance=2, w_app=0.6, w_col=0.0):
        self.n = n_per_alliance
        self.w_app, self.w_col = w_app, w_col
        self.tracks = []
        self.t = None

    def init(self, t, dets):
        """dets: list of (x, y, feat[, colour, conf]). Picks the best n per side of the Autonomous Line."""
        dets = [dets[k] for k in _dedupe(dets)]
        red = [d for d in dets if F.side_of(d[0], d[1]) == "red"]
        blue = [d for d in dets if F.side_of(d[0], d[1]) == "blue"]
        if len(red) < self.n or len(blue) < self.n:
            return False
        self.tracks = []
        for alliance, ds in (("red", red), ("blue", blue)):
            for d in ds[: self.n]:
                tr = Track(len(self.tracks), alliance, np.array([d[0], d[1], 0, 0.0]), np.diag([150.0 ** 2] * 2 + [300.0 ** 2] * 2))
                tr.last_seen = t; tr.last_pos = np.array(d[:2], float); tr.history.append((t, d[0], d[1], True))
                if d[2] is not None:
                    tr.feats.append(d[2])
                self.tracks.append(tr)
        self.t = t
        return True

    def cost(self, tr, d, t):
        z = np.array(d[:2], float)
        dist = min(np.linalg.norm(z - tr.x[:2]), np.linalg.norm(z - tr.last_pos))
        reach = NOISE + REACH * (t - tr.last_seen)
        if dist > reach:
            return None
        c = dist / 1000.0
        if tr.feats and d[2] is not None:
            f0 = np.mean(tr.feats[-20:], 0)
            c += self.w_app * (1 - float(np.dot(f0, d[2]) / (np.linalg.norm(f0) * np.linalg.norm(d[2]) + 1e-9)))
        if len(d) > 3 and d[3] is not None:
            c += self.w_col * max(0.0, -tr.sign() * float(d[3]))      # a blue-looking box for a red track costs
        return c

    def step(self, t, dets):
        """dets: list of (x, y, feat[, colour, conf]) floor positions in mm. Returns {tid: det index or None}."""
        if not self.tracks:
            self.init(t, dets)
            return {}
        dt = max(1e-3, t - self.t)
        self.t = t
        for tr in self.tracks:
            tr.predict(dt, t)
        keep = _dedupe(dets) if dets else []
        assign = {}
        if keep:
            C = np.full((len(self.tracks), len(keep)), 1e6)
            for i, tr in enumerate(self.tracks):
                for jj, j in enumerate(keep):
                    c = self.cost(tr, dets[j], t)
                    if c is not None:
                        C[i, jj] = c
            ri, ci = linear_sum_assignment(C)
            for i, jj in zip(ri, ci):
                if C[i, jj] < 1e6:
                    assign[self.tracks[i].tid] = keep[jj]
        for tr in self.tracks:
            j = assign.get(tr.tid)
            if j is not None:
                d = dets[j]
                if t - tr.last_seen > 0.6:              # re-found after a gap: restart from the detection
                    tr.x = np.array([d[0], d[1], 0.0, 0.0]); tr.P = np.diag([150.0 ** 2] * 2 + [300.0 ** 2] * 2)
                else:
                    tr.update(np.array(d[:2], float))
                tr.last_seen = t; tr.last_pos = np.array(d[:2], float)
                if len(d) > 3 and d[3] is not None:
                    tr.colour = 0.9 * tr.colour + 0.1 * float(d[3])
                if d[2] is not None:
                    tr.feats.append(d[2]); tr.feats = tr.feats[-60:]
            tr.history.append((t, float(tr.x[0]), float(tr.x[1]), j is not None))
        return assign

def path_stats(track, t0=None, t1=None):
    """Distance driven, time in each quadrant/midfield, time on the opponent side."""
    h = [p for p in track.history if (t0 is None or p[0] >= t0) and (t1 is None or p[0] <= t1)]
    if len(h) < 2:
        return {}
    dist = 0.0
    zones = {}
    opp = 0.0
    for (ta, xa, ya, _), (tb, xb, yb, _) in zip(h, h[1:]):
        step = np.hypot(xb - xa, yb - ya)
        if step < MAX_SPEED * (tb - ta) * 1.5:
            dist += step
        z = F.quadrant_of(xa, ya)
        zones[z] = zones.get(z, 0.0) + (tb - ta)
        if F.side_of(xa, ya) != track.alliance:
            opp += tb - ta
    return {"distance_ft": dist / 304.8, "zone_seconds": zones, "opponent_side_seconds": opp,
            "seen_share": float(np.mean([p[3] for p in h]))}
