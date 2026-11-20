"""Contact sheet that shows whether tracks follow the right robots: sampled
frames with every track's current position projected back into the image.

Usage: python -m tools.track_check result.json video.mp4 out.jpg [--n 12]
"""
import argparse, json, subprocess
import cv2, numpy as np
from vexvision import calibrate as C

COL = {"red": [(60, 60, 255), (0, 140, 255)], "blue": [(255, 120, 40), (255, 220, 0)]}

def grab(path, t):
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", "-vf", "scale=1280:720", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    buf = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(buf, np.uint8).reshape(720, 1280, 3).copy() if len(buf) == 1280 * 720 * 3 else None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("result"); ap.add_argument("video"); ap.add_argument("out"); ap.add_argument("--n", type=int, default=12)
    a = ap.parse_args()
    r = json.load(open(a.result))
    cl = r["cal_log"]; idx = np.linspace(0, len(cl) - 1, a.n).astype(int)
    alli = {str(x["track"]): x["alliance"] for x in r["robots"]}
    team = {str(x["track"]): x.get("team") or f"T{x['track']}" for x in r["robots"]}
    cells = []
    for i in idx:
        t, H = cl[i]; H = np.array(H)
        img = grab(a.video, t)
        if img is None: continue
        for tid, hist in r["raw_tracks"].items():
            p = min(hist, key=lambda h: abs(h[0] - t))
            if abs(p[0] - t) > 0.4: continue
            u, v = C.to_img(H, np.array([[p[1], p[2]]], float))[0]
            k = int(tid) % 2; c = COL[alli[tid]][k]
            cv2.circle(img, (int(u), int(v)), 12, c, 3)
            cv2.putText(img, team[tid] + ("" if p[3] else "?"), (int(u) + 14, int(v)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, c, 2)
        cv2.putText(img, f"t={t:.1f}", (10, 700), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cells.append(cv2.resize(img, (640, 360)))
    while len(cells) % 3: cells.append(np.zeros_like(cells[0]))
    rows = [np.hstack(cells[i:i + 3]) for i in range(0, len(cells), 3)]
    cv2.imwrite(a.out, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])

if __name__ == "__main__":
    main()
