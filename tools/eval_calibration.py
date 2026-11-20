"""How far off is automatic calibration? Compare against reviewed calibrations.

For each frame with a reference H (hand marks + tape, or reviewed), run the
detector-based calibration from scratch and measure, over a grid of points on
the tiles, how far apart the two answers put the same pixel (in inches).
"""
import argparse, json, os, sys
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vexvision import calibrate as C, field as F
from vexvision.detect import Detector
from vexvision.analyze import Calibrator

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True); ap.add_argument("--calib", required=True)
    ap.add_argument("--frames", required=True); ap.add_argument("--videos", required=True)
    a = ap.parse_args()
    det = Detector(a.weights, conf=0.2)
    cal = json.load(open(a.calib))
    vids = set(a.videos.split(","))
    g = np.linspace(-1500, 1500, 11)
    grid = np.array([[x, y] for x in g for y in g])
    rows = []
    for fn, c in sorted(cal.items()):
        if fn[:11] not in vids:
            continue
        img = cv2.imread(os.path.join(a.frames, fn))
        Href = np.array(c["H"])
        cb = Calibrator(det)
        ok = cb.solve(img, det(img))
        if not ok:
            rows.append((fn, None)); print(fn, "auto calibration failed"); continue
        px = C.to_img(Href, grid)
        back = C.to_field(cb.H, px)
        err_in = np.linalg.norm(back - grid, axis=1) / 25.4
        rows.append((fn, float(np.median(err_in))))
        print(fn, f"median {np.median(err_in):.1f} in, 90th pct {np.percentile(err_in, 90):.1f} in")
    good = [e for _, e in rows if e is not None]
    print(f"calibrated {len(good)}/{len(rows)} frames; median error {np.median(good):.1f} in" if good else "none calibrated")

if __name__ == "__main__":
    main()
