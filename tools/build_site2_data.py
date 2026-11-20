"""Export calibrated broadcast frames for the 3D site: camera pose recovered
from each frame's field homography, robot floor positions, and a guess at each
robot's alliance from its plate colours.

Usage: python -m tools.build_site2_data --out site2/data
"""
import argparse, json, os, shutil
import numpy as np
from PIL import Image
from vexvision.calibrate import camera_from_h

M = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]])  # field (x, y, z-up) -> three (x, y-up, z)

def pose(H, w, h):
    c = camera_from_h(np.array(H), (w, h))
    C = -c.R.T @ c.t
    R3 = M @ c.R.T @ np.diag([1, -1, -1])
    # rotation matrix -> quaternion (x, y, z, w)
    m = R3; tr = np.trace(m)
    if tr > 0:
        s = np.sqrt(tr + 1) * 2; q = [(m[2,1]-m[1,2])/s, (m[0,2]-m[2,0])/s, (m[1,0]-m[0,1])/s, s/4]
    else:
        i = int(np.argmax(np.diag(m)))
        if i == 0:
            s = np.sqrt(1+m[0,0]-m[1,1]-m[2,2])*2; q = [s/4, (m[0,1]+m[1,0])/s, (m[0,2]+m[2,0])/s, (m[2,1]-m[1,2])/s]
        elif i == 1:
            s = np.sqrt(1+m[1,1]-m[0,0]-m[2,2])*2; q = [(m[0,1]+m[1,0])/s, s/4, (m[1,2]+m[2,1])/s, (m[0,2]-m[2,0])/s]
        else:
            s = np.sqrt(1+m[2,2]-m[0,0]-m[1,1])*2; q = [(m[0,2]+m[2,0])/s, (m[1,2]+m[2,1])/s, s/4, (m[1,0]-m[0,1])/s]
    return {"f": float(c.K[0, 0]), "pos": (M @ C / 1000).round(4).tolist(), "quat": np.round(q, 6).tolist(), "height_m": float(C[2] / 1000)}

def alliance(img, box):
    x0, y0, x1, y1 = [int(v) for v in box]
    a = np.asarray(img.crop((x0, y0, x1, y1)).convert("RGB")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    red = ((r > 140) & (r > g + 60) & (r > b + 60)).sum()
    blue = ((b > 120) & (b > r + 50) & (b > g + 20)).sum()
    n = a.shape[0] * a.shape[1]
    if max(red, blue) < 0.01 * n or abs(red - blue) < 0.3 * max(red, blue):
        return None
    return "red" if red > blue else "blue"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gallery", default="build/site/data/gallery.json")
    ap.add_argument("--hero", default="build/site/data/hero.json")
    ap.add_argument("--src", default="build/site")
    ap.add_argument("--out", default="site2/data")
    ap.add_argument("--n", type=int, default=10)
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "frames"), exist_ok=True)
    out = []
    hero = json.load(open(a.hero))
    items = [dict(hero, featured=True, short=f"{hero['event']} · {hero['match']}", clock="1:03")]
    seen = {hero["video"]}
    for g in sorted(json.load(open(a.gallery)), key=lambda g: -g.get("q", 0)):
        if g["video"] in seen or len(g["robots"]) != 4:
            continue
        seen.add(g["video"]); items.append(g)
    for g in items[: a.n]:
        src = os.path.join(a.src, g["img"])
        img = Image.open(src)
        name = os.path.basename(g["img"])
        if img.width > 1280:
            img = img.resize((1280, round(img.height * 1280 / img.width)))
        img.convert("RGB").save(os.path.join(a.out, "frames", name), quality=86)
        p = pose(g["H"], g["w"], g["h"])
        if p["height_m"] < 0.4:
            continue
        robots = [{"x": r["floor"][0] / 1000, "y": r["floor"][1] / 1000,
                   "side": r.get("side") or alliance(img.resize((g["w"], g["h"])), r["box"]),
                   "box": [round(v, 1) for v in r["box"]]} for r in g["robots"]]
        out.append({"img": f"data/frames/{name}", "w": g["w"], "h": g["h"], **p, "robots": robots,
                    "red": g.get("red", []), "blue": g.get("blue", []), "match": g.get("match"),
                    "event": g.get("event"), "clock": g.get("clock"), "video": g["video"],
                    "overlay_x": g.get("overlay_x")})
    json.dump(out, open(os.path.join(a.out, "frames.json"), "w"), indent=1)
    for o in out:
        print(o["event"], o["match"], "cam h %.2fm f %.0f" % (o["height_m"], o["f"]), [r["side"] for r in o["robots"]])

if __name__ == "__main__":
    main()
