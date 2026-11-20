"""OCR the overlay of the frames in a list (skipping cached ones)."""
import json, os, sys, cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vexvision import overlay
frames, names, cache_p = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
for i, n in enumerate(names):
    if n in cache: continue
    img = cv2.imread(os.path.join(frames, n))
    if img is not None:
        cache[n] = overlay.ocr(img)
    if i % 20 == 0: json.dump(cache, open(cache_p, "w")); print(i, len(names), flush=True)
json.dump(cache, open(cache_p, "w")); print("done", len(cache))
