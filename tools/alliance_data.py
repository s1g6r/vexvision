"""Labelled robot crops for an alliance-colour classifier, for free.

In a tracked match every robot's alliance is known (it starts on its own side
of the Autonomous Line), and box_log has its box once a second. Cropping those
boxes from the video gives red/blue examples with no hand labelling. Only
tracks seen most of the match are used, so identity swaps rarely leak in.

Usage: python -m tools.alliance_data --raw DIR --videos DIR --out DIR [--per 25]
"""
import argparse, json, os, random, subprocess
import numpy as np
from PIL import Image

def grab(video, t):
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", "-vf", "scale=1280:720",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    b = subprocess.run(cmd, capture_output=True).stdout
    return Image.fromarray(np.frombuffer(b, np.uint8).reshape(720, 1280, 3)) if len(b) == 1280 * 720 * 3 else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True); ap.add_argument("--videos", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--per", type=int, default=25)
    a = ap.parse_args()
    random.seed(0)
    meta = []
    for f in sorted(os.listdir(a.raw)):
        vid = f[:-5]; r = json.load(open(os.path.join(a.raw, f)))
        if "box_log" not in r or not os.path.exists(os.path.join(a.videos, vid + ".mp4")):
            continue
        alli = {str(x["track"]): x["alliance"] for x in r["robots"] if x.get("seen_share", 0) >= 0.6}
        logs = [b for b in r["box_log"] if b[1]]
        for t, boxes in random.sample(logs, min(a.per, len(logs))):
            img = None
            for tid, box in boxes.items():
                if tid not in alli:
                    continue
                x0, y0, x1, y1 = box
                if (x1 - x0) < 24 or (y1 - y0) < 24:
                    continue
                img = img or grab(os.path.join(a.videos, vid + ".mp4"), t)
                if img is None:
                    break
                d = os.path.join(a.out, alli[tid]); os.makedirs(d, exist_ok=True)
                name = f"{vid}_{t:.0f}_{tid}.jpg"
                img.crop((x0, y0, x1, y1)).resize((96, 96)).save(os.path.join(d, name), quality=90)
                meta.append({"file": f"{alli[tid]}/{name}", "video": vid})
        print(vid, len(meta), flush=True)
    json.dump(meta, open(os.path.join(a.out, "meta.json"), "w"))

if __name__ == "__main__":
    main()
