"""Spread calibrations to the other frames of each calibrated video, then write labels.

For each video with a calibrated frame, align its other frames to it (ECC) and
snap to tape. Frames whose alignment correlation is low (camera cut, replay,
title card) are skipped.
"""
import json, os, sys, glob
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vexvision import calibrate as C
from tools.landmarks_to_labels import write_frame

def main(frames_dir, out, min_q=0.45):
    calib = json.load(open(os.path.join(out, "calib.json")))
    added = {}
    for fn, c in calib.items():
        if c.get("source", "marks") != "marks":
            continue
        vid = fn[:11]
        img_a = cv2.imread(os.path.join(frames_dir, fn))
        H_a = np.array(c["H"])
        for p in sorted(glob.glob(os.path.join(frames_dir, vid + "_*.jpg"))):
            fb = os.path.basename(p)
            if fb in calib or fb in added:
                continue
            img_b = cv2.imread(p)
            H_b, cc = C.transfer(H_a, img_a, img_b)
            if H_b is None or not C.plausible(H_b, img_b.shape[1::-1]):
                print(fb, "skip: no alignment"); continue
            # moving robots lower ECC correlation, so judge by how much the field moved
            # and how well the carried calibration fits this frame's tape
            corners = C.field_polygon(H_a)
            moved = float(np.abs(C.field_polygon(H_b) - corners).max())
            H_b, info = C.snap_to_tape(H_b, img_b)
            q = max(info["tape_q0"], info["tape_q1"] if info["snap"] else 0)
            if moved > 60 or q < min_q:
                print(fb, "skip cc", round(cc, 3), "moved", round(moved), "q", round(q, 3)); continue
            info["moved_px"] = moved
            info.update({"source": "transfer:" + fn, "cc": cc})
            added[fb] = {"H": H_b.tolist(), **info}
            write_frame(fb, img_b, H_b, {}, out)
            print(fb, "cc", round(cc, 3), {k: round(v, 3) if isinstance(v, float) else v for k, v in info.items() if k != "source"})
    calib.update(added)
    json.dump(calib, open(os.path.join(out, "calib.json"), "w"), indent=1)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
