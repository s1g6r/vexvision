"""Which robot is which team.

Alliance is known from the starting side (see track.py), so inside each
alliance there are only two ways to assign the two teams. Evidence for each
assignment is combined in log-odds:

1. Licence plates: VEX robots carry alliance-coloured plates with the team
   number. Every OCR read of a plate on a track is a vote, weighted by OCR
   confidence and by how well the read matches each of the two candidates
   (edit distance, so "2145X" read as "2I45X" still counts).
2. Appearance across the event: a team brings the same robot to every match.
   Each track's average appearance vector is compared with what the team
   looked like in the event's other, already-resolved matches.

Unlike a free plate reader, the answer is always one of the two teams that
the schedule says are on that alliance, so a single good plate read settles
the match, and a robot with no readable plate is still named by elimination.
"""
import numpy as np

def edit_distance(a, b):
    a, b = a.upper(), b.upper()
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[-1]

CONFUSABLE = str.maketrans({"O": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2", "G": "6"})

def read_likelihood(read, team, conf):
    """log-likelihood that an OCR read came from this team's plate."""
    r = read.upper().replace(" ", "")
    t = team.upper()
    # compare digits leniently, the trailing letter strictly
    rd, td = r[:-1].translate(CONFUSABLE), t[:-1]
    d = edit_distance(rd, td) + (0 if r[-1:] == t[-1:] else 1)
    p_match = conf * np.exp(-1.5 * d)
    return np.log(p_match + 1e-3)

def assign_alliance(tracks, teams, plate_reads, appearance=None):
    """Assign two teams to two tracks of one alliance.

    tracks: [tid_a, tid_b]; teams: [team_1, team_2]
    plate_reads: {tid: [(text, conf), ...]}
    appearance: optional {tid: {team: similarity in [-1, 1]}}
    Returns ({tid: team}, confidence 0.5..1).
    """
    a, b = tracks
    t1, t2 = teams
    def score(tid, team):
        s = sum(read_likelihood(txt, team, c) for txt, c in plate_reads.get(tid, []))
        if appearance and tid in appearance and team in appearance[tid]:
            s += 4.0 * appearance[tid][team]
        return s
    keep = score(a, t1) + score(b, t2)
    swap = score(a, t2) + score(b, t1)
    p_keep = 1 / (1 + np.exp(np.clip(swap - keep, -50, 50)))
    if p_keep >= 0.5:
        return {a: t1, b: t2}, float(p_keep)
    return {a: t2, b: t1}, float(1 - p_keep)

class AppearanceBank:
    """Per-team appearance memory across an event's matches."""
    def __init__(self):
        self.bank = {}
    def add(self, team, feat, weight=1.0):
        f = np.asarray(feat, float)
        if team in self.bank:
            s, w = self.bank[team]
            self.bank[team] = (s + weight * f, w + weight)
        else:
            self.bank[team] = (weight * f, weight)
    def similarity(self, feat, team):
        if team not in self.bank:
            return 0.0
        s, w = self.bank[team]
        m = s / w
        f = np.asarray(feat, float)
        return float(np.dot(m, f) / (np.linalg.norm(m) * np.linalg.norm(f) + 1e-9))

def colour_feature(img, box, bins=8):
    """Simple appearance vector: hue/sat histogram of the robot box (centre region)."""
    import cv2
    x0, y0, x1, y1 = [int(v) for v in box]
    h, w = img.shape[:2]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    crop = img[y0:y1, x0:x1]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [bins, 4], [0, 180, 0, 256]).ravel()
    v = cv2.calcHist([hsv], [2], None, [4], [0, 256]).ravel()
    f = np.r_[hist, v].astype(float)
    return f / (np.linalg.norm(f) + 1e-9)

def alliance_colour(img, box):
    """How red (+1) or blue (-1) a robot box looks: alliance plates are saturated
    red or blue, and robots mostly carry their own alliance's cones. Noisy on one
    frame, useful averaged over a track."""
    import cv2
    x0, y0, x1, y1 = [int(v) for v in box]
    h, w = img.shape[:2]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return 0.0
    hsv = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    hh, ss, vv = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    vivid = (ss > 110) & (vv > 70)
    red = float(np.count_nonzero(vivid & ((hh < 8) | (hh > 170))))
    blue = float(np.count_nonzero(vivid & (hh >= 100) & (hh <= 125)))
    return (red - blue) / (red + blue + 0.02 * hsv.shape[0] * hsv.shape[1])

LOOKS = {
    # hue bins of colour_feature are 22.5 deg (OpenCV 0-180) wide: 5 = 112-135, 6 = 135-157
    "purple": {"hue": (6,), "min_sat": 1},
}

def look_score(feat, look):
    """Share of a box's colourful pixels that fall in a team's signature colour.
    "black": share of the box's pixels that are dark (brightness under 64)."""
    if look == "black":
        v = np.asarray(feat, float)[32:36]
        return float(v[0] / (v.sum() + 1e-9))
    L = LOOKS[look]
    f = np.asarray(feat, float)[:32].reshape(8, 4)
    total = f[:, L["min_sat"]:].sum()
    if total <= 0:
        return 0.0
    return float(f[list(L["hue"]), L["min_sat"]:].sum() / total)
