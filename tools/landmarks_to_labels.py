"""Turn marked landmarks into calibrations, detector labels and check images.

landmarks.json: {"<frame file>": {"<landmark>": [u, v], ...}, ...}
Landmark names are in vexvision.field.LANDMARKS (goal names, D_*, J_*, K_*).

For each frame: solve H from the marks, snap it to the tape with the marks as
anchors (so the fit can't wander), recover the camera, then project all nine
goals as 3D octagonal cylinders to get their boxes. Writes calib.json, YOLO
label files and a check image per frame.
"""
import json, os, sys, argparse
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vexvision import field as F, calibrate as C

GOAL_CLASS = {"red": 0, "blue": 1, "neutral": 2, "center": 3}

def goal_box(cam, g, H, z_extra=0.0):
    """Box around a goal base: the floor ring comes from H (exact on the tiles),
    the vertical extent from the camera (only its 'up' direction is used)."""
    ang = np.linspace(0, 2 * np.pi, 9)[:-1] + np.pi / 8
    ring = np.c_[g.x + F.GOAL_RADIUS * np.cos(ang), g.y + F.GOAL_RADIUS * np.sin(ang)]
    base = C.to_img(H, ring)
    up = cam.project(np.c_[ring, np.full(8, g.height + z_extra)]) - cam.project(np.c_[ring, np.zeros(8)])
    pts = np.vstack([base, base + up])
    return pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()

def solve(marks, img, refine=True):
    names = [n for n in marks if n in F.LANDMARKS]
    fp = np.array([F.LANDMARKS[n] for n in names], float)
    ip = np.array([marks[n] for n in names], float)
    H0, _ = cv2.findHomography(fp, ip, 0)
    if H0 is None:
        return None, {}
    if C.signed_area(H0) > 0:
        raise ValueError("marks give a mirrored field: check goal names (N is the quadrant with NW neutral + NE blue)")
    info = {"n_marks": len(names), "mark_err0": float(np.linalg.norm(C.to_img(H0, fp) - ip, axis=1).mean())}
    H = H0
    if refine:
        H, more = C.snap_to_tape(H0, img, anchors=(fp, ip))
        info.update(more)
    return H, info

def write_frame(fn, img, H, marks, out):
    h, w = img.shape[:2]
    cam = C.camera_from_h(H, (w, h))
    vis = C.draw(img, H)
    lines = []
    for g in F.GOALS:
        x0, y0, x1, y1 = goal_box(cam, g, H)
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w - 1, x1), min(h - 1, y1)
        if x1 - x0 < 4 or y1 - y0 < 4:
            continue
        lines.append(f"{GOAL_CLASS[g.kind]} {(x0+x1)/2/w:.5f} {(y0+y1)/2/h:.5f} {(x1-x0)/w:.5f} {(y1-y0)/h:.5f}")
        cv2.rectangle(vis, (int(x0), int(y0)), (int(x1), int(y1)), (0, 255, 0), 1)
    for n, (u, v) in marks.items():
        cv2.drawMarker(vis, (int(u), int(v)), (0, 0, 255), cv2.MARKER_TILTED_CROSS, 10, 2)
    os.makedirs(os.path.join(out, "labels"), exist_ok=True); os.makedirs(os.path.join(out, "check"), exist_ok=True)
    open(os.path.join(out, "labels", fn.rsplit(".", 1)[0] + ".txt"), "w").write("\n".join(lines) + "\n")
    cv2.imwrite(os.path.join(out, "check", fn), vis)
    return cam

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("landmarks"); ap.add_argument("frames_dir"); ap.add_argument("out")
    ap.add_argument("--no-refine", action="store_true")
    a = ap.parse_args()
    marks = json.load(open(a.landmarks))
    p = os.path.join(a.out, "calib.json")
    calib = json.load(open(p)) if os.path.exists(p) else {}
    for fn, m in marks.items():
        img = cv2.imread(os.path.join(a.frames_dir, fn))
        if img is None or len(m) < 4:
            continue
        H, info = solve(m, img, not a.no_refine)
        if H is None:
            continue
        cam = write_frame(fn, img, H, m, a.out)
        info.update({"focal": float(cam.K[0, 0]), "source": "marks"})
        calib[fn] = {"H": H.tolist(), **info}
        print(fn, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in info.items()})
    os.makedirs(a.out, exist_ok=True)
    json.dump(calib, open(p, "w"), indent=1)

if __name__ == "__main__":
    main()
