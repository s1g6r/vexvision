"""Make robot training labels from a match video by motion, no hand labelling.

The broadcast camera is static during a match, so anything that moves inside
the field is a robot or a game piece. Pieces are small; robots are about an
18-inch cube. For a calibrated clip this script:
1. builds a median background from frames across the match,
2. marks pixels that differ from it inside the field (projected up to 20 in),
3. keeps blobs whose size matches an 18 x 18 x 18 in box at that floor spot,
4. writes YOLO labels (class 0 = robot) and a check image every N frames.
Review the check images before training on them: crowds leaning over the
wall and referees can make false blobs near the perimeter.

  python -m tools.video_autolabel match.mp4 --H calib.json --out data/auto_robots
"""
import argparse, json, os, sys
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vexvision import calibrate as C, field as F, stream

def expected_box(H, cam, x, y, size=457.0):
    s = size / 2
    corners = [(x + dx, y + dy, z) for dx in (-s, s) for dy in (-s, s) for z in (0, size)]
    base = C.to_img(H, [[c[0], c[1]] for c in corners])
    up = cam.project(corners) - cam.project([(c[0], c[1], 0) for c in corners])
    p = base + up
    return p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--H", required=True, help="calib JSON with key 'H' (or a frame entry)")
    ap.add_argument("--out", required=True); ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--dur", type=float, default=125); ap.add_argument("--every", type=float, default=2.0)
    a = ap.parse_args()
    cj = json.load(open(a.H))
    H = np.array(cj["H"] if "H" in cj else next(iter(cj.values()))["H"])
    frames = list(stream.video_frames(a.video, a.start, a.dur, fps=2))
    if len(frames) < 10:
        sys.exit("clip too short")
    imgs = [f for _, f in frames]
    bg = np.median(np.stack(imgs[:: max(1, len(imgs) // 40)]), 0).astype(np.uint8)
    h, w = bg.shape[:2]
    cam = C.camera_from_h(H, (w, h))
    region = np.zeros((h, w), np.uint8)
    W = F.WALL
    floor = C.to_img(H, [[-W, -W], [W, -W], [W, W], [-W, W]])
    up = cam.project([[-W, -W, 500], [W, -W, 500], [W, W, 500], [-W, W, 500]]) - cam.project([[-W, -W, 0], [W, -W, 0], [W, W, 0], [-W, W, 0]])
    cv2.fillPoly(region, [np.vstack([floor, floor + up]).astype(np.int32)], 1)
    hull = cv2.convexHull(np.vstack([floor, floor + up]).astype(np.int32))
    region[:] = 0; cv2.fillPoly(region, [hull], 1)
    os.makedirs(os.path.join(a.out, "images"), exist_ok=True); os.makedirs(os.path.join(a.out, "labels"), exist_ok=True)
    os.makedirs(os.path.join(a.out, "check"), exist_ok=True)
    stem = os.path.splitext(os.path.basename(a.video))[0]
    n = 0
    for t, img in frames[:: max(1, int(a.every * 2))]:
        diff = cv2.absdiff(cv2.GaussianBlur(img, (5, 5), 0), cv2.GaussianBlur(bg, (5, 5), 0)).max(2)
        fg = ((diff > 35) & (region > 0)).astype(np.uint8)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
        k, lab, st, _ = cv2.connectedComponentsWithStats(fg)
        boxes = []
        for i in range(1, k):
            x, y, bw, bh, area = st[i]
            foot = C.to_field(H, [[x + bw / 2, y + bh]])[0]
            if np.abs(foot).max() > F.HALF:
                continue
            ex = expected_box(H, cam, *foot)
            ew, eh = ex[2] - ex[0], ex[3] - ex[1]
            if 0.45 * ew < bw < 2.2 * ew and 0.45 * eh < bh < 2.2 * eh and area > 0.25 * bw * bh:
                boxes.append((x, y, x + bw, y + bh))
        if not boxes:
            continue
        name = f"{stem}_{t:07.2f}"
        cv2.imwrite(os.path.join(a.out, "images", name + ".jpg"), img)
        open(os.path.join(a.out, "labels", name + ".txt"), "w").write(
            "".join(f"0 {(x0+x1)/2/w:.5f} {(y0+y1)/2/h:.5f} {(x1-x0)/w:.5f} {(y1-y0)/h:.5f}\n" for x0, y0, x1, y1 in boxes))
        vis = img.copy()
        for x0, y0, x1, y1 in boxes:
            cv2.rectangle(vis, (x0, y0), (x1, y1), (0, 255, 0), 2)
        cv2.imwrite(os.path.join(a.out, "check", name + ".jpg"), cv2.resize(vis, None, fx=0.5, fy=0.5))
        n += 1
    print("wrote", n, "labelled frames to", a.out)

if __name__ == "__main__":
    main()
