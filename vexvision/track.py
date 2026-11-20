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

MAX_SPEED = 2500.0          # mm/s, a fast V5 drive is ~6 ft/s (1800 mm/s)

@dataclass
class Track:
    tid: int
    alliance: str
    x: np.ndarray                      # [px, py, vx, vy]
    P: np.ndarray
    team: str = None
    last_seen: float = 0.0
    history: list = dc_field(default_factory=list)   # (t, x, y, seen)
    feats: list = dc_field(default_factory=list)     # appearance vectors

    def predict(self, dt, q=4000.0):
        Fm = np.eye(4); Fm[0, 2] = Fm[1, 3] = dt
        G = np.array([[dt * dt / 2, 0], [0, dt * dt / 2], [dt, 0], [0, dt]])
        self.x = Fm @ self.x
        self.P = Fm @ self.P @ Fm.T + G @ G.T * q ** 2 * 0.01
        v = np.hypot(*self.x[2:])
        if v > MAX_SPEED:
            self.x[2:] *= MAX_SPEED / v

    def update(self, z, r=60.0):
        Hm = np.array([[1, 0, 0, 0], [0, 1, 0, 0.0]])
        S = Hm @ self.P @ Hm.T + np.eye(2) * r ** 2
        K = self.P @ Hm.T @ np.linalg.inv(S)
        self.x = self.x + K @ (z - Hm @ self.x)
        self.P = (np.eye(4) - K @ Hm) @ self.P

    def maha(self, z, r=60.0):
        Hm = np.array([[1, 0, 0, 0], [0, 1, 0, 0.0]])
        S = Hm @ self.P @ Hm.T + np.eye(2) * r ** 2
        d = z - Hm @ self.x
        return float(d @ np.linalg.solve(S, d))

class FourRobotTracker:
    def __init__(self, n_per_alliance=2, gate=16.0):
        self.n = n_per_alliance
        self.gate = gate
        self.tracks = []
        self.t = None

    def init(self, t, dets):
        """dets: list of (x, y, feat). Picks the best n per side of the Autonomous Line."""
        red = [d for d in dets if F.side_of(d[0], d[1]) == "red"]
        blue = [d for d in dets if F.side_of(d[0], d[1]) == "blue"]
        if len(red) < self.n or len(blue) < self.n:
            return False
        self.tracks = []
        for alliance, ds in (("red", red), ("blue", blue)):
            for d in ds[: self.n]:
                tr = Track(len(self.tracks), alliance, np.array([d[0], d[1], 0, 0.0]), np.diag([80.0 ** 2] * 2 + [500.0 ** 2] * 2))
                tr.last_seen = t; tr.history.append((t, d[0], d[1], True))
                if d[2] is not None:
                    tr.feats.append(d[2])
                self.tracks.append(tr)
        self.t = t
        return True

    def step(self, t, dets):
        """dets: list of (x, y, feat) floor positions in mm. Returns {tid: det index or None}."""
        if not self.tracks:
            self.init(t, dets)
            return {}
        dt = max(1e-3, t - self.t)
        self.t = t
        for tr in self.tracks:
            tr.predict(dt)
        assign = {}
        if dets:
            C = np.full((len(self.tracks), len(dets)), 1e6)
            for i, tr in enumerate(self.tracks):
                for j, d in enumerate(dets):
                    m = tr.maha(np.array(d[:2]))
                    if m < self.gate:
                        app = 0.0
                        if tr.feats and d[2] is not None:
                            f0 = np.mean(tr.feats[-20:], 0)
                            app = 1 - float(np.dot(f0, d[2]) / (np.linalg.norm(f0) * np.linalg.norm(d[2]) + 1e-9))
                        C[i, j] = m + 6.0 * app
            ri, ci = linear_sum_assignment(C)
            for i, j in zip(ri, ci):
                if C[i, j] < 1e6:
                    assign[self.tracks[i].tid] = j
        for tr in self.tracks:
            j = assign.get(tr.tid)
            if j is not None:
                d = dets[j]
                tr.update(np.array(d[:2])); tr.last_seen = t
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
