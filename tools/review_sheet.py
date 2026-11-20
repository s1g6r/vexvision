"""Contact sheets for reviewing proposals by eye.

Each cell: the frame with robot boxes (numbered, conf shown) and, when the
frame calibrated, the field tape projected through its homography. A reviewer
marks cells by sheet/cell number; review_apply.py turns marks into labels.

Usage: python -m tools.review_sheet --props prop.jsonl --frames DIR --out DIR [--per 12]
"""
import argparse, json, os
import cv2, numpy as np
from vexvision import calibrate as C, field as F
MINC = 0.2

def draw(img, rec, w=480):
    s = w / img.shape[1]
    im = cv2.resize(img, (w, round(img.shape[0] * s)))
    if rec.get("H"):
        H = np.array(rec["H"])
        col = (80, 220, 80) if rec.get("q", 0) >= 0.6 else (0, 160, 255)
        for seg in F.tape_segments(30) + [np.vstack([F.wall_outline(), F.wall_outline()[:1]])]:
            p = C.to_img(H, np.asarray(seg, float)) * s
            cv2.polylines(im, [p.astype(np.int32).reshape(-1, 1, 2)], False, col, 1, cv2.LINE_AA)
    for i, r in enumerate(sorted(rec["robots"], key=lambda r: -r["conf"])):
        if r["conf"] < MINC:
            continue
        x0, y0, x1, y1 = [int(v * s) for v in r["box"]]
        c = (0, 255, 255) if r["conf"] >= 0.5 else (0, 120, 255)
        cv2.rectangle(im, (x0, y0), (x1, y1), c, 2)
        cv2.putText(im, f"{i}:{r['conf']:.2f}", (x0, max(12, y0 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, c, 2, cv2.LINE_AA)
    return im

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--props", required=True); ap.add_argument("--frames", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--per", type=int, default=12)
    ap.add_argument("--only", help="json list of frame names to include")
    ap.add_argument("--w", type=int, default=480); ap.add_argument("--minc", type=float, default=0.2); ap.add_argument("--cols", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    global MINC; MINC = a.minc
    recs = [json.loads(l) for l in open(a.props)]
    if a.only:
        keep = set(json.load(open(a.only))); recs = [r for r in recs if r["frame"] in keep]
    index = {}
    cols = a.cols
    for si in range(0, len(recs), a.per):
        chunk = recs[si:si + a.per]
        cells = []
        for ci, rec in enumerate(chunk):
            img = cv2.imread(os.path.join(a.frames, rec["frame"]))
            im = draw(img, rec, a.w)
            cv2.rectangle(im, (0, 0), (150, 22), (0, 0, 0), -1)
            q = f" q{rec['q']:.2f}" if rec.get("H") else " nocal"
            cv2.putText(im, f"#{ci}{q}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            cells.append(im)
            index[f"{si // a.per}:{ci}"] = rec["frame"]
        h = max(c.shape[0] for c in cells)
        cells = [cv2.copyMakeBorder(c, 0, h - c.shape[0], 0, 0, cv2.BORDER_CONSTANT) for c in cells]
        while len(cells) % cols:
            cells.append(np.zeros_like(cells[0]))
        rows = [np.hstack(cells[i:i + cols]) for i in range(0, len(cells), cols)]
        cv2.imwrite(os.path.join(a.out, f"sheet{si // a.per:02d}.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 82])
    json.dump(index, open(os.path.join(a.out, "index.json"), "w"), indent=0)
    print(len(recs), "frames,", (len(recs) + a.per - 1) // a.per, "sheets")

if __name__ == "__main__":
    main()
