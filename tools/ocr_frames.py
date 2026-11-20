"""OCR every collected frame once and cache the results (used for evaluation and frame selection)."""
import json, os, sys
import cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vexvision import overlay

def main(root):
    vids = json.load(open(os.path.join(root, "videos.json")))
    out_p = os.path.join(root, "ocr.json")
    cache = json.load(open(out_p)) if os.path.exists(out_p) else {}
    n = 0
    for vid, v in vids.items():
        for p in v.get("frames", []):
            k = os.path.basename(p)
            if k in cache:
                continue
            img = cv2.imread(p)
            if img is None:
                continue
            cache[k] = overlay.ocr(img)
            n += 1
            if n % 25 == 0:
                json.dump(cache, open(out_p, "w")); print(n, flush=True)
    json.dump(cache, open(out_p, "w"))
    print("done", len(cache))

if __name__ == "__main__":
    main(sys.argv[1])
