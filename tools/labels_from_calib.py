"""Rebuild goal labels and check images from data/calib_reference.json.

  python tools/labels_from_calib.py data/calib_reference.json data/yt/frames lab/
"""
import json, os, sys
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.landmarks_to_labels import write_frame

if __name__ == "__main__":
    cal, frames, out = sys.argv[1:4]
    n = 0
    for fn, c in json.load(open(cal)).items():
        img = cv2.imread(os.path.join(frames, fn))
        if img is not None:
            write_frame(fn, img, np.array(c["H"]), {}, out); n += 1
    print("wrote", n)
