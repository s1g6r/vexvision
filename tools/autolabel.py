"""Calibrate unlabelled frames with the current detector, for review.

For each frame: detect goals and robots, solve the field from goal positions,
snap to tape, and score the fit. Writes check images, a contact sheet per 12
frames, and proposals.json (H + robot boxes) for frames that pass review.
"""
import argparse, json, os, sys, glob, time
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vexvision import calibrate as C
from vexvision.detect import Detector
from vexvision.analyze import Calibrator

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True); ap.add_argument("--frames", required=True)
    ap.add_argument("--list", required=True, help="JSON list of frame file names")
    ap.add_argument("--out", required=True); ap.add_argument("--conf", type=float, default=0.2)
    a = ap.parse_args()
    det = Detector(a.weights, conf=a.conf)
    names = json.load(open(a.list))
    os.makedirs(os.path.join(a.out, "check"), exist_ok=True)
    props = {}
    tiles = []
    for fn in names:
        img = cv2.imread(os.path.join(a.frames, fn))
        if img is None:
            continue
        t = time.time()
        dets = det(img)
        cal = Calibrator(det)
        ok = cal.solve(img, dets)
        vis = img.copy()
        q = 0.0
        if ok:
            q = C.fit_quality(cal.H, C.tape_mask(img, cal.H))
            vis = C.draw(img, cal.H)
            props[fn] = {"H": cal.H.tolist(), "tape_q": q,
                         "robots": [[round(v) for v in d["box"]] for d in dets if d["cls"] == "robot"]}
        for d in dets:
            x0, y0, x1, y1 = map(int, d["box"])
            cv2.rectangle(vis, (x0, y0), (x1, y1), (0, 255, 0) if d["cls"] == "robot" else (255, 255, 0), 2)
        cv2.putText(vis, f"{len(tiles)} {fn[:11]} q={q:.2f}", (10, 40), 0, 1.2, (0, 0, 0), 5)
        cv2.putText(vis, f"{len(tiles)} {fn[:11]} q={q:.2f}", (10, 40), 0, 1.2, (0, 255, 255), 2)
        tiles.append(cv2.resize(vis, (426, 240)))
        print(fn, "ok" if ok else "no calibration", round(q, 3), f"{time.time()-t:.1f}s", flush=True)
    for s in range(0, len(tiles), 12):
        group = tiles[s:s + 12]
        while len(group) % 3:
            group.append(np.zeros_like(tiles[0]))
        rows = [np.hstack(group[i:i + 3]) for i in range(0, len(group), 3)]
        cv2.imwrite(os.path.join(a.out, f"sheet{s//12}.jpg"), np.vstack(rows))
    json.dump(props, open(os.path.join(a.out, "proposals.json"), "w"), indent=1)
    json.dump(names, open(os.path.join(a.out, "order.json"), "w"))

if __name__ == "__main__":
    main()
