"""Read goal stacks and Toggles from a calibrated frame.

Both readers sample pixels at known 3D places: the vertical axis above each
goal base, and the top of each wall where its Toggle sits. Pixels are sorted
into the game colours (red, blue, yellow) by hue; everything else is ignored.

Goal stacks: Pins nest into Cups on a goal, so a stack is a column of coloured
pin halves (each about 82 mm tall: a 165 mm pin has two halves) between grey
or clear cups. Colour runs along the axis are converted to a count of halves
using the projected millimetres-per-pixel, so a yellow/yellow pin (one long
yellow run) counts as two yellow halves. Per-frame reads are noisy (robots
pass in front), so events.py only trusts counts that hold for a while.
Accuracy is not measured yet: there are no hand-counted stacks to test on.
This heuristic is the stand-in until a goal close-up model is trained from
stack counts made in the labeling tool (tools/label.html).

Toggles: the Toggle on top of each wall shows red, blue or yellow on the side
facing the field. The reader returns the dominant game colour on that strip.
"""
import cv2
import numpy as np
from . import field as F
from . import calibrate as C

HALF_MM = 82.0
WALL_TOP = 300.0

def colour_classes(hsv):
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    sat = (s > 110) & (v > 70)
    red = sat & ((h <= 8) | (h >= 168))
    yellow = sat & (h >= 18) & (h <= 38)
    blue = sat & (h >= 90) & (h <= 128)
    out = np.zeros(h.shape, np.uint8)       # 0 none, 1 red, 2 blue, 3 yellow
    out[red] = 1; out[blue] = 2; out[yellow] = 3
    return out

NAMES = {1: "red", 2: "blue", 3: "yellow"}

def _axis(H, cam, x, y, z0, z1, n):
    base = C.to_img(H, [[x, y]])[0]
    zs = np.linspace(z0, z1, n)
    up = cam.project(np.c_[np.full(n, x), np.full(n, y), zs]) - cam.project([[x, y, 0]])
    return base + up, zs

def read_stack(img, H, cam, goal, max_height=1600.0, step_mm=8.0, half_width_mm=22.0, max_lean_deg=25):
    """Count visible pin halves by colour on one goal. Returns ({colour: n}, debug).

    The column is found, not assumed: from the goal top, rays in a fan of
    +-max_lean_deg around the projected vertical are scored by how many
    game-coloured or cup-grey pixels they cross, and the best ray is read.
    This copes with leaning stacks and small errors in the camera's 'up'.
    """
    hgt, wid = img.shape[:2]
    n = int((max_height - goal.height) / step_mm)
    axis, zs = _axis(H, cam, goal.x, goal.y, goal.height, max_height, n)
    p0 = axis[0]
    up = axis[-1] - axis[0]
    L = np.linalg.norm(up)
    if not np.isfinite(L) or L < 5:
        return {"red": 0, "blue": 0, "yellow": 0}, {"runs": [], "axis_px": [p0.tolist(), p0.tolist()]}
    mm_per_px = (max_height - goal.height) / L
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    cls = colour_classes(hsv)
    grey = (hsv[..., 1] < 60) & (hsv[..., 2] > 60) & (hsv[..., 2] < 200)
    side_px = max(2.0, half_width_mm / mm_per_px)
    base_ang = np.arctan2(up[1], up[0])
    best = None
    for dang in np.radians(np.arange(-max_lean_deg, max_lean_deg + 0.1, 2.5)):
        ang = base_ang + dang
        dvec = np.array([np.cos(ang), np.sin(ang)]); nvec = np.array([-dvec[1], dvec[0]])
        ts = np.linspace(0, L, n)
        labels = np.zeros(n, np.uint8); fill = 0; gap = 0
        for i, t in enumerate(ts):
            votes = []
            for o in np.linspace(-side_px, side_px, 5):
                u, v = (p0 + dvec * t + nvec * o).round().astype(int)
                if 0 <= u < wid and 0 <= v < hgt:
                    votes.append(cls[v, u] if cls[v, u] else (9 if grey[v, u] else 0))
            col = [c for c in votes if c and c != 9]
            if len(col) >= 2:
                labels[i] = max(set(col), key=col.count)
            if sum(1 for c in votes if c) >= 3:
                fill += 1; gap = 0
            else:
                gap += 1
                if gap * step_mm > 60 or (i > 6 and fill < 0.5 * i):
                    labels[i - gap + 1:] = 0
                    break    # left the stack
        score = fill + 2 * (labels > 0).sum() - 0.5 * abs(np.degrees(dang))
        if best is None or score > best[0]:
            best = (score, labels, dvec)
    _, labels, dvec = best
    counts = {"red": 0, "blue": 0, "yellow": 0}
    runs = []
    i = 0
    while i < n:
        j = i
        while j < n and labels[j] == labels[i]:
            j += 1
        if labels[i]:
            length = (zs[min(j, n - 1)] - zs[i])
            if length >= 0.45 * HALF_MM:
                k = max(1, int(round(length / HALF_MM)))
                counts[NAMES[labels[i]]] += k
                runs.append((NAMES[labels[i]], float(zs[i]), float(length), k))
        i = j
    top = max([r[1] + r[2] for r in runs], default=goal.height)
    tip = p0 + dvec * ((top - goal.height) / mm_per_px)
    return counts, {"runs": runs, "top_mm": top, "axis_px": [p0.tolist(), tip.tolist()]}

def read_toggle(img, H, cam, quad, band_mm=(250.0, 340.0), min_px=25):
    x, y = F.TOGGLES[quad]
    d = np.array([1.0, 0]) if quad in "NS" else np.array([0, 1.0])
    pts = []
    for s in np.linspace(-0.45, 0.45, 25) * F.TOGGLE_LEN:
        for z in np.linspace(*band_mm, 5):
            px, py = np.array([x, y]) + d * s
            base = C.to_img(H, [[px, py]])[0]
            up = cam.project([[px, py, z]]) - cam.project([[px, py, 0]])
            pts.append(base + up[0])
    pts = np.array(pts).round().astype(int)
    hgt, wid = img.shape[:2]
    ok = (pts[:, 0] >= 0) & (pts[:, 0] < wid) & (pts[:, 1] >= 0) & (pts[:, 1] < hgt)
    if ok.sum() < min_px:
        return None, 0.0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    cls = colour_classes(hsv)[pts[ok, 1], pts[ok, 0]]
    cls = cls[cls > 0]
    if len(cls) < 0.25 * ok.sum():
        return None, 0.0
    vals, cnt = np.unique(cls, return_counts=True)
    best = vals[np.argmax(cnt)]
    return NAMES[int(best)], float(cnt.max() / len(cls))

# A Toggle counts only when the side facing the field is all one colour. Less than this share of
# one colour on that side is a half-turned ("split") Toggle, which doesn't count for anyone.
SPLIT = 0.8

def toggle_state(col, share):
    return col if col is None or share >= SPLIT else "split"

def read_frame(img, H, cam=None):
    cam = cam or C.camera_from_h(H, img.shape[1::-1])
    stacks = {g.name: read_stack(img, H, cam, g)[0] for g in F.GOALS}
    toggles = {q: toggle_state(*read_toggle(img, H, cam, q)) for q in F.TOGGLES}
    return stacks, toggles
