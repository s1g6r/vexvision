"""Read team number plates for matches that are already read, from a 1080p copy of each match.

The first reading works at 720p, where plates are a few pixels tall and almost never readable.
At 1080p they often are, mostly while robots are set up before autonomous and whenever a robot
comes close to the camera. This pass reuses the robot boxes and tracks from the first reading
(no detector), looks for the red or blue plate inside each robot box, and reads it.

    python -m tools.plate_pass RAW HD_DIR OFFSETS.json ID [ID ...]

HD_DIR/<id>.mp4 is a 1080p cut of the match; OFFSETS.json says where in the first reading's
clip each cut starts ({id: seconds}). Reads are added to RAW/<id>.perc.json as plate_log
entries (so the normal finishing step uses them) and kept in RAW/<id>.plates.json.
"""
import json, os, re, sys, time
import cv2
import numpy as np
from vexvision import analyze as AN, overlay, stream

S = 1.5                      # the first reading's boxes are in 1280x720 pixels
MIN_H = 60                   # robot box height in 1080p pixels worth looking at
FPS = 2


def plate_blobs(crop):
    """Red or blue rectangles shaped like a licence plate inside a robot crop."""
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    red = ((hsv[..., 0] < 10) | (hsv[..., 0] > 170)) & (hsv[..., 1] > 110) & (hsv[..., 2] > 70)
    blue = (hsv[..., 0] > 100) & (hsv[..., 0] < 130) & (hsv[..., 1] > 110) & (hsv[..., 2] > 60)
    out = []
    for m in (red, blue):
        m = cv2.morphologyEx(m.astype(np.uint8) * 255, cv2.MORPH_CLOSE, np.ones((5, 9), np.uint8))
        n, _, st, _ = cv2.connectedComponentsWithStats(m)
        for i in range(1, n):
            x, y, w, h, a = st[i]
            if w >= 20 and h >= 7 and 1.4 <= w / h <= 8 and a >= 0.4 * w * h:
                out.append((x, y, w, h))
    return out


def read_crop(crop):
    reads = []
    for x, y, w, h in plate_blobs(crop):
        p = crop[max(0, y - 3):y + h + 3, max(0, x - 3):x + w + 3]
        p = cv2.resize(p, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        for it in overlay.ocr(p):
            t = it["text"].upper().replace(" ", "")
            for tok in re.findall(r"\d{1,5}[A-Z]?", t):
                if len(tok) >= 3:
                    reads.append((tok, round(it["conf"], 3)))
    return reads


def align(P, clip, guess):
    """Seconds to add to the 1080p cut's time to get the first reading's time, from the match clock.

    Both copies show the same on-screen clock. Every clock the first reading saw is matched
    with the 1080p frames showing the same period and clock; the true shift is within a second
    of each pair, so the median of the differences pins it to a fraction of a second."""
    ref = {}
    for t, r in P.get("overlay_reads", []):
        if r.get("clock") is not None and r.get("period") in ("auton", "driver"):
            ref.setdefault((r["period"], r["clock"]), []).append(t)
    if not ref:
        return guess, 0
    diffs = []
    for tc, img in stream.frames(clip, 0, 100, fps=2, size=(1280, 720)):
        r = overlay.read(img)
        for t in ref.get((r.period, r.clock), []):
            d = t - tc
            if abs(d - guess) < 15:
                diffs.append(d)
    if len(diffs) < 4:
        return guess, len(diffs)
    return float(np.median(diffs)), len(diffs)


def overlaps(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def compute(P, R, clip, offset):
    """Plate reads for one match: [(t, det index, [[text, conf], ...]), ...] and a summary."""
    tracker, assigns = AN.run_tracker(P["det_log"])
    rows_at = {round(t, 2): rows for t, rows, _ in P["det_log"]}
    A = {round(t, 2): a for t, a in assigns}
    times = sorted(A)
    t0 = (R.get("t_start") or 0) - 30
    t1 = (R["t_driver"] + 105 + 3) if R.get("t_driver") else (R.get("t_start") or 0) + 150
    log, nframes = [], 0
    dur = clip_seconds(clip)
    offset, npairs = align(P, clip, offset)
    for tc, img in stream.frames(clip, 0, dur, fps=FPS, size=(1920, 1080)):
        t = tc + offset
        if t < t0 or t > t1:
            continue
        # the first reading's frame nearest in time (it ran at 3 a second)
        i = int(np.searchsorted(times, t))
        cand = [times[k] for k in (i - 1, i) if 0 <= k < len(times)]
        if not cand:
            continue
        k = min(cand, key=lambda x: abs(x - t))
        if abs(k - t) > 0.2:
            continue
        a, rows = A[k], rows_at.get(k)
        if not rows:
            continue
        nframes += 1
        boxes = {j: [v * S for v in rows[j][3:7]] for tid, j in a.items() if j is not None}
        for tid, j in a.items():
            if j is None:
                continue
            b = boxes[j]
            if b[3] - b[1] < MIN_H:
                continue
            if any(overlaps(b, o) for jj, o in boxes.items() if jj != j):
                continue                     # two robots in one box: a plate could be either's
            x0, y0, x1, y1 = [int(v) for v in b]
            crop = img[max(0, y0):y1, max(0, x0):x1]
            if crop.size:
                rr = read_crop(crop)
                if rr:
                    log.append((k, j, [list(r) for r in rr]))
    info = {"frames": nframes, "reads": sum(len(e[2]) for e in log), "fps": FPS, "offset": round(offset, 2), "clock_pairs": npairs}
    return log, info


def save(raw, mid, log, info):
    """Add the reads to the match's perception log (kept apart from the first reading's own)."""
    pp = os.path.join(raw, mid + ".perc.json")
    P = json.load(open(pp))
    if "plate_log_720" not in P:
        P["plate_log_720"] = P.get("plate_log", [])
    P["plate_log"] = P["plate_log_720"] + [list(e) for e in log]
    P["plate_pass"] = info
    json.dump(P, open(pp, "w"))
    json.dump(log, open(os.path.join(raw, mid + ".plates.json"), "w"))


def run(mid, raw, clip, offset):
    P = json.load(open(os.path.join(raw, mid + ".perc.json")))
    R = json.load(open(os.path.join(raw, mid + ".json")))
    log, info = compute(P, R, clip, offset)
    save(raw, mid, log, info)
    return info


def clip_seconds(path):
    cap = cv2.VideoCapture(path)
    n, fps = cap.get(cv2.CAP_PROP_FRAME_COUNT), cap.get(cv2.CAP_PROP_FPS) or 30
    cap.release()
    return n / fps if n > 0 else 400


def main():
    raw, hd, offs = sys.argv[1], sys.argv[2], json.load(open(sys.argv[3]))
    for mid in sys.argv[4:]:
        clip = os.path.join(hd, mid + ".mp4")
        if not os.path.exists(clip):
            print(mid, "no 1080p clip"); continue
        t = time.time()
        info = run(mid, raw, clip, offs.get(mid, 0))
        print(mid, info, f"{time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
