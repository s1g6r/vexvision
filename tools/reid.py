"""Look signatures for every robot in every match, from a small pretrained image model
(DINOv2-small). For each match, up to N moments spread over the match; at each one the
frame is cut out once and every robot seen is cropped and embedded. Saved per match as
reid/<id>.json: {track: [[...384 floats...], ...]}.
Usage: python -m tools.reid RAW_DIR OUT_DIR VIDEO_DIR [more video dirs] [--ids a,b]"""
import json, os, sys, subprocess, tempfile
import numpy as np, torch
from PIL import Image

N = 28

def model():
    from transformers import AutoModel
    torch.set_num_threads(2)
    return AutoModel.from_pretrained("facebook/dinov2-small").eval()

MEAN = np.array([0.485, 0.456, 0.406]); STD = np.array([0.229, 0.224, 0.225])

def embed(m, crops):
    x = np.stack([(np.asarray(c.resize((112, 112)), float) / 255 - MEAN) / STD for c in crops]).transpose(0, 3, 1, 2)
    with torch.no_grad():
        h = m(pixel_values=torch.tensor(x, dtype=torch.float32)).last_hidden_state
    v = torch.cat([h[:, 0], h[:, 1:].mean(1)], 1).numpy()
    return v / np.linalg.norm(v, axis=1, keepdims=True)

def find_video(i, dirs):
    for d in dirs:
        p = os.path.join(d, i + ".mp4")
        if os.path.exists(p):
            return p

def run_match(m, raw, i, vid, out):
    r = json.load(open(os.path.join(raw, i + ".json")))
    if "robots" not in r:
        return
    t0 = r.get("t_start") or 0; t1 = (r.get("t_driver") or t0 + 15) + 105
    tids = [str(b["track"]) for b in r["robots"]]
    bl = [(t, b) for t, b in r["box_log"] if t0 <= t <= t1 + 2]
    if not bl:
        return
    pick = [bl[int(k)] for k in np.linspace(0, len(bl) - 1, min(N, len(bl)))]
    res = {k: [] for k in tids}
    with tempfile.TemporaryDirectory() as td:
        for t, boxes in pick:
            f = os.path.join(td, "f.jpg")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", vid, "-frames:v", "1", "-q:v", "2", f])
            if not os.path.exists(f):
                continue
            im = Image.open(f).convert("RGB"); crops, keys = [], []
            for k, b in boxes.items():
                x0, y0, x1, y1 = b
                if (x1 - x0) < 18 or (y1 - y0) < 18:
                    continue
                p = 0.08 * max(x1 - x0, y1 - y0)
                crops.append(im.crop((max(0, x0 - p), max(0, y0 - p), x1 + p, y1 + p))); keys.append(str(k))
            if crops:
                for k, v in zip(keys, embed(m, crops)):
                    res.setdefault(k, []).append([round(float(a), 4) for a in v])
            os.remove(f)
    json.dump(res, open(os.path.join(out, i + ".json"), "w"))

def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    raw, out, dirs = a[0], a[1], a[2:]
    ids = None
    for x in sys.argv:
        if x.startswith("--ids="):
            ids = x[6:].split(",")
    ids = ids or sorted(f[:-10] for f in os.listdir(raw) if f.endswith(".perc.json"))
    m = model()
    for i in ids:
        if os.path.exists(os.path.join(out, i + ".json")):
            continue
        vid = find_video(i, dirs)
        if not vid or not os.path.exists(os.path.join(raw, i + ".json")):
            print(i, "no video"); continue
        run_match(m, raw, i, vid, out); print(i, "done", flush=True)

if __name__ == "__main__":
    main()
