"""Map broadcast pixels to field millimetres.

A calibration is a homography H (field mm on the tile plane -> image pixels)
plus a pinhole camera recovered from it, so points above the tiles (goal tops,
Toggles, robot centres) can be projected too.

How a frame is calibrated:
1. An initial H comes from goal keypoints (from the detector, matched to the
   known goal layout with RANSAC), from the previous frame, or from a one-off
   4-point click per camera.
2. `refine` snaps the field model onto the white tape: it minimises the
   distance from projected tape centre-lines to tape pixels found in the
   frame (a chamfer fit), with a robust loss so robots and pieces covering
   the tape don't drag the fit.
3. `fit_quality` reports the share of projected tape that lands on tape. A
   calibration below the threshold is not trusted.
"""
from dataclasses import dataclass, field as dc_field
import itertools
import cv2
import numpy as np
from scipy.optimize import least_squares
from . import field as F

def to_img(H, pts):
    pts = np.asarray(pts, np.float64).reshape(-1, 2)
    p = np.c_[pts, np.ones(len(pts))] @ H.T
    return p[:, :2] / p[:, 2:3]

def to_field(H, pts):
    return to_img(np.linalg.inv(H), pts)

def field_polygon(H, margin=0.0):
    w = F.WALL - margin
    return to_img(H, [[-w, -w], [w, -w], [w, w], [-w, w]])

# ---- tape pixels ----------------------------------------------------------
def tape_mask(img, H=None, overlay_boxes=()):
    """Thin bright low-saturation lines on the tiles (white tape)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17))
    th = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, k)
    m = ((th > 28) & (hsv[..., 1] < 60)).astype(np.uint8)
    # drop large bright blobs (walls, signs): tape is thin
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    keep = np.zeros_like(m)
    for i in range(1, n):
        x, y, w, h, a = st[i]
        fill = a / max(1, w * h)
        if a >= 12 and (fill < 0.45 or a < 120):
            keep[lab == i] = 1
    if H is not None:
        poly = np.zeros_like(keep)
        cv2.fillPoly(poly, [field_polygon(H, 60).astype(np.int32)], 1)
        keep &= poly
    for (x0, y0, x1, y1) in overlay_boxes:
        keep[int(y0):int(y1), int(x0):int(x1)] = 0
    return keep

def tape_points(step_mm=25.0):
    pts = []
    for seg in F.tape_segments():
        L = np.linalg.norm(seg[-1] - seg[0])
        n = max(2, int(L / step_mm))
        t = np.linspace(0, 1, n)[:, None]
        pts.append(seg[0] * (1 - t) + seg[-1] * t)
    return np.vstack(pts)

_TAPE = tape_points()

def _dist_map(mask):
    return cv2.distanceTransform((1 - mask).astype(np.uint8), cv2.DIST_L2, 5)

def _sample(dt, uv, cap):
    h, w = dt.shape
    u, v = uv[:, 0], uv[:, 1]
    inside = (u >= 0) & (u < w - 1) & (v >= 0) & (v < h - 1)
    out = np.full(len(uv), cap, float)
    ui, vi = u[inside], v[inside]
    x0, y0 = np.floor(ui).astype(int), np.floor(vi).astype(int)
    fx, fy = ui - x0, vi - y0
    d = (dt[y0, x0] * (1 - fx) * (1 - fy) + dt[y0, x0 + 1] * fx * (1 - fy)
         + dt[y0 + 1, x0] * (1 - fx) * fy + dt[y0 + 1, x0 + 1] * fx * fy)
    out[inside] = np.minimum(d, cap)
    return out, inside

def fit_quality(H, mask, tol=4.0):
    dt = _dist_map(mask)
    uv = to_img(H, _TAPE)
    d, inside = _sample(dt, uv, 99)
    if inside.sum() < 20:
        return 0.0
    return float((d[inside] <= tol).mean())

def line_pixels(mask, min_len=35, max_pts=2500, seed=0):
    """Pixels on long straight tape segments (drops clutter from robots and pieces)."""
    segs = cv2.HoughLinesP(mask.astype(np.uint8) * 255, 1, np.pi / 360, threshold=30,
                           minLineLength=min_len, maxLineGap=6)
    if segs is None:
        return np.zeros((0, 2)), np.zeros_like(mask)
    clean = np.zeros_like(mask)
    for x0, y0, x1, y1 in np.asarray(segs).reshape(-1, 4):
        cv2.line(clean, (int(x0), int(y0)), (int(x1), int(y1)), 1, 2)
    clean &= mask.astype(clean.dtype) | cv2.dilate(mask.astype(np.uint8), np.ones((3, 3), np.uint8))
    ys, xs = np.nonzero(clean)
    pts = np.c_[xs, ys].astype(float)
    if len(pts) > max_pts:
        pts = pts[np.random.default_rng(seed).choice(len(pts), max_pts, replace=False)]
    return pts, clean

def _render_model(H, shape, thick=2):
    r = np.zeros(shape[:2], np.uint8)
    for seg in F.tape_segments(20):
        uv = to_img(H, seg)
        if np.all(np.isfinite(uv)) and np.abs(uv).max() < 1e5:
            cv2.polylines(r, [uv.astype(np.int32)], False, 1, thick)
    return r

def refine(H0, img=None, mask=None, extra=None, caps=(40, 15, 6), two_sided=True):
    """Snap H onto the tape with a robust two-sided chamfer fit.

    Model->image: projected tape centre-lines should land on tape pixels.
    Image->model: long tape segments inside the field should be explained by
    the model (this stops the fit from shrinking the field onto a few lines).
    extra: optional (field_pts, img_pts, weight) anchors such as goal bases.
    """
    if mask is None:
        mask = tape_mask(img, H0)
    lp, clean = line_pixels(mask)
    dt = _dist_map(clean if clean.any() else mask)
    H = H0 / H0[2, 2]
    shape = mask.shape
    for cap in caps:
        dtb = cv2.GaussianBlur(dt, (0, 0), max(1.0, cap / 8))
        def res(p):
            Hp = np.append(p, 1.0).reshape(3, 3)
            d, _ = _sample(dtb, to_img(Hp, _TAPE), cap)
            r = [d]
            if two_sided and len(lp):
                inv = _dist_map(_render_model(Hp, shape))
                d2, _ = _sample(inv, lp, cap)
                r.append(d2 * np.sqrt(len(_TAPE) / len(lp)) * 0.7)
            if extra is not None:
                fp, ip, wgt = extra
                r.append(wgt * (to_img(Hp, fp) - ip).ravel())
            return np.concatenate(r)
        sol = least_squares(res, H.ravel()[:8], loss="soft_l1", f_scale=cap / 4,
                            x_scale="jac", diff_step=1e-4, max_nfev=200)
        H = np.append(sol.x, 1.0).reshape(3, 3)
    return H

def fit_score(H, mask):
    """Symmetric agreement in [0,1]: share of model tape on tape, and of tape on model."""
    lp, clean = line_pixels(mask)
    a = fit_quality(H, clean if clean.any() else mask)
    if not len(lp):
        return a
    inv = _dist_map(_render_model(H, mask.shape))
    d, _ = _sample(inv, lp, 99)
    b = float((d <= 4).mean())
    return 2 * a * b / max(1e-9, a + b)

# ---- camera from homography -------------------------------------------------
@dataclass
class Camera:
    K: np.ndarray
    R: np.ndarray
    t: np.ndarray
    def project(self, pts3):
        """Field mm (x, y, z up) -> pixels."""
        P = np.asarray(pts3, float).reshape(-1, 3)
        c = (self.R @ P.T + self.t.reshape(3, 1)).T
        uv = (self.K @ c.T).T
        return uv[:, :2] / uv[:, 2:3]
    @property
    def position(self):
        return (-self.R.T @ self.t).ravel()

def camera_from_h(H, size):
    """Recover K (square pixels, centred principal point), R, t from H."""
    w, h = size
    cx, cy = w / 2, h / 2
    Hn = np.array([[1, 0, -cx], [0, 1, -cy], [0, 0, 1]]) @ H
    h1, h2 = Hn[:, 0], Hn[:, 1]
    # orthogonality constraints with K = diag(f, f, 1)
    num = -(h1[0] * h2[0] + h1[1] * h2[1])
    den = h1[2] * h2[2]
    f2_a = num / den if abs(den) > 1e-12 else np.nan
    den2 = h1[2] ** 2 - h2[2] ** 2
    f2_b = (h2[0] ** 2 + h2[1] ** 2 - h1[0] ** 2 - h1[1] ** 2) / den2 if abs(den2) > 1e-12 else np.nan
    cands = [v for v in (f2_a, f2_b) if np.isfinite(v) and v > 0]
    f = float(np.sqrt(np.median(cands))) if cands else 1.2 * w
    K = np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]])
    B = np.linalg.inv(K) @ H
    lam = 1 / np.linalg.norm(B[:, 0])
    r1, r2, t = lam * B[:, 0], lam * B[:, 1], lam * B[:, 2]
    if t[2] < 0:
        r1, r2, t = -r1, -r2, -t
    R = np.c_[r1, r2, np.cross(r1, r2)]
    U, _, Vt = np.linalg.svd(R)
    R = U @ Vt
    if np.linalg.det(R) < 0:
        R[:, 2] *= -1
    return Camera(K, R, t)

# ---- initial calibration from goal keypoints ----------------------------------
GOAL_XY = np.array([[g.x, g.y] for g in F.GOALS])
GOAL_KIND = [g.kind for g in F.GOALS]

def goal_hypotheses(dets, img_size, min_inliers=4, tol_px=None, top=8):
    """dets: list of (u, v, kind) goal base centres; kind in red/blue/neutral/center/None.

    Tries assignments of detections to the known goals that respect colour,
    using 4-point hypotheses, and returns the best few distinct homographies
    (by inliers, then error), each refitted on its inliers. Colour removes the
    180-degree ambiguity of the layout; the caller picks among hypotheses by
    how well the tape fits.
    """
    if len(dets) < 4:
        return []
    tol_px = tol_px or 0.03 * img_size[0]
    uv = np.array([[d[0], d[1]] for d in dets], float)
    kinds = [d[2] for d in dets]
    def ok(i, j):
        k = kinds[i]
        return k is None or k == GOAL_KIND[j]
    allowed = np.array([[ok(i, j) for j in range(9)] for i in range(len(dets))])
    hyps = []
    di = range(len(dets))
    for quad in itertools.combinations(di, 4):
        cand = [np.nonzero(allowed[i])[0] for i in quad]
        for perm in itertools.product(*cand):
            if len(set(perm)) < 4:
                continue
            src = GOAL_XY[list(perm)].astype(np.float32)
            dst = uv[list(quad)].astype(np.float32)
            try:
                Hc = cv2.getPerspectiveTransform(src, dst)
            except cv2.error:
                continue
            if not np.all(np.isfinite(Hc)) or not plausible(Hc, img_size):
                continue
            proj = to_img(Hc, GOAL_XY)
            d = np.linalg.norm(proj[None, :, :] - uv[:, None, :], axis=2)
            d[~allowed] = 1e9
            m = d.min(1)
            inl = int((m < tol_px).sum())
            if inl >= min_inliers:
                hyps.append((inl, float(np.minimum(m, tol_px).sum()), Hc))
    hyps.sort(key=lambda h: (-h[0], h[1]))
    out = []
    for inl, err, Hc in hyps:
        proj = to_img(Hc, GOAL_XY)
        pairs = []
        for i in di:
            d = np.linalg.norm(proj - uv[i], axis=1)
            d[~allowed[i]] = 1e9
            j = int(np.argmin(d))
            if d[j] < tol_px:
                pairs.append((GOAL_XY[j], uv[i]))
        Hl = None
        if len(pairs) >= 4:
            Hl, _ = cv2.findHomography(np.array([p[0] for p in pairs], np.float32), np.array([p[1] for p in pairs], np.float32), 0)
        H = canonical(Hl if Hl is not None else Hc)
        # distinct from the ones kept already?
        if all(np.abs(field_polygon(H) - field_polygon(o[0])).max() > 15 for o in out):
            out.append((H, inl, [p[0] for p in pairs], [p[1] for p in pairs]))
        if len(out) >= top:
            break
    return out

def h_from_goals(dets, img_size, min_inliers=4, tol_px=None):
    hs = goal_hypotheses(dets, img_size, min_inliers, tol_px, top=1)
    return (hs[0][0], hs[0][1]) if hs else (None, 0)

MIRROR = np.array([[0, 1.0, 0], [1.0, 0, 0], [0, 0, 1.0]])

def signed_area(H):
    p = field_polygon(H)
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))

def canonical(H):
    """The Override field is mirror-symmetric across its red/blue diagonal (y = x):
    goals, tape and Midfield all map onto same-coloured copies. So goal matching
    can return a mirrored H that draws identically but puts the camera under the
    floor (heights then project downwards). Swap x and y to get the real one."""
    return H @ MIRROR if signed_area(H) > 0 else H

def plausible(H, img_size):
    """Reject degenerate fits: field must be in front of the camera, mostly in frame, convex."""
    poly = field_polygon(H)
    if not np.all(np.isfinite(poly)):
        return False
    if not cv2.isContourConvex(poly.astype(np.float32).reshape(-1, 1, 2)):
        return False
    area = cv2.contourArea(poly.astype(np.float32))
    w, h = img_size
    return 0.05 * w * h < area < 4.0 * w * h

# ---- drawing -------------------------------------------------------------------
def draw(img, H, color=(0, 255, 255)):
    vis = img.copy()
    for seg in F.tape_segments():
        cv2.polylines(vis, [to_img(H, seg).astype(np.int32)], False, color, 2)
    cv2.polylines(vis, [field_polygon(H).astype(np.int32)], True, (255, 0, 255), 2)
    for g in F.GOALS:
        u, v = to_img(H, [[g.x, g.y]])[0]
        c = {"red": (0, 0, 255), "blue": (255, 0, 0), "neutral": (40, 40, 40), "center": (255, 255, 255)}[g.kind]
        cv2.circle(vis, (int(u), int(v)), 6, c, -1)
    return vis

# ---- fully automatic calibration: camera search -------------------------------
# A broadcast camera sits outside the field looking down at it. Search over
# a physical camera (focal length, azimuth, elevation, distance, aim point,
# roll) instead of a free homography: every candidate is a real view, so the
# fit cannot collapse or shear the field.

def _look_at_camera(f, az, el, dist, ax, ay, roll, size):
    w, h = size
    tgt = np.array([ax, ay, 0.0])
    pos = tgt + dist * np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
    z = tgt - pos; z /= np.linalg.norm(z)                 # camera forward
    up = np.array([0, 0, 1.0])
    x = np.cross(z, up); x /= np.linalg.norm(x)          # camera right
    y = np.cross(z, x)                                    # camera down
    R = np.stack([x, y, z])
    if roll:
        c, s = np.cos(roll), np.sin(roll)
        R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]]) @ R
    t = -R @ pos
    K = np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1.0]])
    return Camera(K, R, t)

def h_from_camera(cam):
    P = cam.K @ np.c_[cam.R, cam.t]
    return P[:, [0, 1, 3]] / P[2, 3]

def _params_to_h(p, size):
    f, az, el, dist, ax, ay, roll = p
    return h_from_camera(_look_at_camera(np.exp(f), az, el, np.exp(dist), ax, ay, roll, size))

_COARSE = tape_points(80.0)
_OUTLINE = np.vstack([np.linspace(a, b, 25) for a, b in zip(F.wall_outline(), np.roll(F.wall_outline(), -1, 0))])

def _batch_project(Hs, pts):
    p = np.c_[pts, np.ones(len(pts))]
    q = np.einsum("nij,kj->nki", Hs, p)
    return q[..., :2] / q[..., 2:3], q[..., 2]

def auto_calibrate(img, mask=None, overlay_boxes=(), top=12, verbose=False):
    """Find the field in a frame with no initial guess. Returns (H, score) or (None, 0)."""
    h, w = img.shape[:2]
    size = (w, h)
    if mask is None:
        mask = tape_mask(img, None, overlay_boxes)
    lp, clean = line_pixels(mask)
    if len(lp) < 50:
        return None, 0.0
    dt = _dist_map(clean)
    cap = 25.0
    # where the tape is gives the aim point and rough scale
    cu, cv = np.median(lp, 0)
    spread = np.percentile(lp[:, 0], 95) - np.percentile(lp[:, 0], 5)
    cands = []
    for logf in np.log(np.geomspace(0.6 * w, 2.4 * w, 7)):
        f = np.exp(logf)
        for el in np.radians(np.arange(12, 76, 6)):
            # distance so the tape spread (~ field diagonal width) roughly matches
            for k in (0.7, 1.0, 1.4):
                dist = k * f * 2.6 * F.WALL / max(spread, 50)
                for az in np.radians(np.arange(0, 360, 4)):
                    cands.append((logf, az, el, np.log(dist), 0.0, 0.0, 0.0))
    cands = np.array(cands)
    Hs = np.stack([_params_to_h(p, size) for p in cands])
    # shift each candidate so the field centre lands near the tape median
    c0, _ = _batch_project(Hs, np.zeros((1, 2)))
    shift = np.array([cu, cv]) - c0[:, 0, :]
    T = np.tile(np.eye(3), (len(Hs), 1, 1)); T[:, 0, 2] = shift[:, 0]; T[:, 1, 2] = shift[:, 1]
    Hs = T @ Hs
    uv, depth = _batch_project(Hs, _COARSE)
    ok = (depth > 0) & (uv[..., 0] >= 0) & (uv[..., 0] < w - 1) & (uv[..., 1] >= 0) & (uv[..., 1] < h - 1)
    ui = np.clip(uv[..., 0], 0, w - 1).astype(int); vi = np.clip(uv[..., 1], 0, h - 1).astype(int)
    d = np.where(ok, np.minimum(dt[vi, ui], cap), cap)
    cost = d.mean(1)
    order = np.argsort(cost)[: top * 4]
    # rescore the best with the two-sided score, keep diverse ones
    scored = []
    for i in order:
        Hc = Hs[i]
        if not plausible(Hc, size):
            continue
        scored.append((fit_score(Hc, clean), i))
    scored.sort(reverse=True)
    best = (None, 0.0)
    for s0, i in scored[:top]:
        Hr = refine_camera(Hs[i], clean, size)
        s = fit_score(Hr, clean)
        if verbose:
            print(f"cand {i} coarse {s0:.3f} -> {s:.3f}")
        if s > best[1]:
            best = (Hr, s)
    return best

def refine_camera(H0, mask, size, caps=(25, 10, 5)):
    """Refine a homography through a physical camera, then a light free polish."""
    cam = camera_from_h(H0, size)
    w, h = size
    pos = cam.position
    fwd = cam.R[2]
    # aim point: where the optical axis meets the floor
    s = -pos[2] / fwd[2] if abs(fwd[2]) > 1e-6 else 3000
    tgt = pos + s * fwd
    rel = pos - tgt
    dist = np.linalg.norm(rel)
    el = np.arcsin(np.clip(rel[2] / dist, -1, 1))
    az = np.arctan2(rel[1], rel[0])
    p0 = np.array([np.log(cam.K[0, 0]), az, el, np.log(dist), tgt[0], tgt[1], 0.0])
    lp, clean = line_pixels(mask)
    dt = _dist_map(clean if clean.any() else mask)
    for cap in caps:
        dtb = cv2.GaussianBlur(dt, (0, 0), max(1.0, cap / 6))
        def res(p):
            Hp = _params_to_h(p, size)
            d, _ = _sample(dtb, to_img(Hp, _TAPE), cap)
            r = [d]
            if len(lp):
                inv = _dist_map(_render_model(Hp, mask.shape))
                d2, _ = _sample(inv, lp, cap)
                r.append(0.6 * d2 * np.sqrt(len(_TAPE) / len(lp)))
            return np.concatenate(r)
        try:
            sol = least_squares(res, p0, loss="soft_l1", f_scale=cap / 4, diff_step=1e-3, max_nfev=150)
            p0 = sol.x
        except Exception:
            break
    return _params_to_h(p0, size)

def refine_similarity(H0, mask, extra=None, caps=(20, 10, 5), max_shift=250.0):
    """Correct H by a small similarity on the field plane (shift, turn, scale).

    Perspective comes from the landmarks; the tape only nudges the field in its
    own plane. This keeps the fit from shrinking or shearing the field, which a
    free 8-parameter tape fit does when much of the tape is covered.
    """
    lp, clean = line_pixels(mask)
    dt = _dist_map(clean if clean.any() else mask)
    def H_of(p):
        tx, ty, th, ls = p
        c, s, k = np.cos(th), np.sin(th), np.exp(ls)
        S = np.array([[k * c, -k * s, tx], [k * s, k * c, ty], [0, 0, 1.0]])
        return H0 @ S
    p = np.zeros(4)
    for cap in caps:
        dtb = cv2.GaussianBlur(dt, (0, 0), max(1.0, cap / 6))
        def res(q):
            Hq = H_of(q)
            d, _ = _sample(dtb, to_img(Hq, _TAPE), cap)
            r = [d, [q[0] / max_shift * 3, q[1] / max_shift * 3, q[2] / 0.1 * 3, q[3] / 0.05 * 3]]
            if extra is not None:
                fp, ip, wgt = extra
                r.append(wgt * (to_img(Hq, fp) - ip).ravel())
            return np.concatenate(r)
        p = least_squares(res, p, loss="soft_l1", f_scale=cap / 4, diff_step=1e-3, max_nfev=200).x
    return H_of(p), p

def snap_to_tape(H0, img, anchors=None, min_gain=0.03):
    """Apply refine_similarity only when it clearly helps and stays physical."""
    mask = tape_mask(img, H0)
    q0 = fit_quality(H0, mask)
    extra = (anchors[0], anchors[1], 0.15) if anchors is not None else None
    H1, p = refine_similarity(H0, mask, extra=extra)
    q1 = fit_quality(H1, mask)
    ok = (q1 > q0 + min_gain and abs(np.exp(p[3]) - 1) < 0.15 and abs(np.degrees(p[2])) < 5
          and np.hypot(p[0], p[1]) < 250 and plausible(H1, img.shape[1::-1]))
    info = {"tape_q0": q0, "tape_q1": q1, "snap": bool(ok), "snap_scale": float(np.exp(p[3]))}
    return (H1 if ok else H0), info

def transfer(H_a, img_a, img_b, field_margin=200):
    """Carry a calibration to another frame from the same camera (small pan/zoom ok).

    Aligns the two frames inside the field area with ECC (homography motion) at
    half resolution. Returns (H_b, correlation) or (None, cc).
    """
    ga = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY); gb = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY)
    s = 0.5
    ga = cv2.resize(ga, None, fx=s, fy=s); gb = cv2.resize(gb, None, fx=s, fy=s)
    m = np.zeros_like(ga)
    cv2.fillPoly(m, [(field_polygon(H_a, -field_margin) * s).astype(np.int32)], 255)
    W = np.eye(3, dtype=np.float32)
    try:
        cc, W = cv2.findTransformECC(ga, gb, W, cv2.MOTION_HOMOGRAPHY,
                                     (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), m, 5)
    except cv2.error:
        return None, 0.0
    Sm = np.diag([s, s, 1.0])
    Wf = np.linalg.inv(Sm) @ W.astype(float) @ Sm      # maps a-pixels -> b-pixels
    return canonical(Wf @ H_a), float(cc)
