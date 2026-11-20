"""Turn a tracked match (analyze-file output) into a replay the site can play.

Writes <out>/<id>.json with:
- robots: team, alliance and a smoothed path [[t, x, y, heading, seen], ...] in metres,
  t in seconds from the start of autonomous (negative before it)
- events: scoring events with the team that made them
- cams: broadcast camera pose (pos, quat, focal) about twice a second, so the 3D view can
  stand where the camera stood
- stills: the broadcast frame once a second (640x360 JPEGs in <out>/<id>/), so the site can show
  the real picture next to the rebuilt one

Usage: python -m tools.export_replay RESULT.json VIDEO.mp4 --out site2/data/replays --id ID --meta '{...}'
"""
import argparse, json, os, subprocess
import numpy as np
from tools.build_site2_data import pose

VMAX = 2300.0   # mm/s, about 7.5 ft/s: faster than any Override drive train really moves

def speed_limit(t, xy, vmax=VMAX):
    """A tracker can lose a robot and pick it up again across the field. Rather than
    letting the 3D robot jump, ramp it there at a believable top speed. Run the limiter
    forwards and backwards and average, so the ramp is centred on the jump."""
    def run(order):
        f = xy.copy()
        for a, b in zip(order, order[1:]):
            d = xy[b] - f[a]; lim = vmax * abs(t[b] - t[a]); n = np.hypot(*d)
            f[b] = f[a] + d * (lim / n) if n > lim else xy[b]
        return f
    idx = list(range(len(xy)))
    return (run(idx) + run(idx[::-1])) / 2

def fill_gaps(t, xy, seen, max_gap=8.0):
    """While a robot is hidden (behind a stack, a person or the edge of the shot),
    draw it moving straight from where it was last seen to where it was found again,
    instead of wherever the filter guessed."""
    xy = xy.copy()
    idx = np.flatnonzero(seen)
    for a, b in zip(idx, idx[1:]):
        if b - a > 1 and t[b] - t[a] <= max_gap:
            k = (t[a + 1:b] - t[a]) / (t[b] - t[a])
            xy[a + 1:b] = xy[a] + k[:, None] * (xy[b] - xy[a])
    return xy

def smooth(path, win=1.0):
    """path: [(t, x, y, seen)] at the analysis rate. Gaussian smoothing in time,
    seen points weighted far above coasting ones, then heading from velocity."""
    a = np.array([[p[0], p[1], p[2], 1.0 if p[3] else 0.15] for p in path], float)
    t, xy, w = a[:, 0], a[:, 1:3], a[:, 3]
    xy = fill_gaps(t, xy, w > 0.5)
    out = []
    sig = win / 2
    for i, ti in enumerate(t):
        k = np.exp(-0.5 * ((t - ti) / sig) ** 2) * w
        k[np.abs(t - ti) > 2 * win] = 0
        s = k.sum()
        p = (k[:, None] * xy).sum(0) / s if s > 0 else xy[i]
        out.append(p)
    out = np.clip(np.array(out), -1790 + 150, 1790 - 150)
    out = speed_limit(t, out)
    head = []
    for i in range(len(out)):
        j0, j1 = max(0, i - 2), min(len(out) - 1, i + 2)
        d = out[j1] - out[j0]
        head.append(np.arctan2(d[1], d[0]) if np.hypot(*d) > 40 else None)
    last = 0.0                                   # hold heading while stopped
    for i in range(len(head)):
        if head[i] is None:
            head[i] = last
        else:
            last = head[i]
    return [[round(float(ti), 2), round(float(p[0]) / 1000, 3), round(float(p[1]) / 1000, 3), round(float(h), 2), int(bool(sv))]
            for ti, p, h, sv in zip(t, out, head, a[:, 3] > 0.5)]

COLS, ROWS, SW, SH = 8, 6, 400, 225

def stills(video, out_dir, t0, t1):
    """One frame a second, packed 48 to a sheet (8 x 6 tiles of 400x225)."""
    import shutil, tempfile
    tmp = tempfile.mkdtemp()
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t0:.2f}", "-i", video, "-t", f"{t1 - t0:.2f}",
                    "-vf", f"fps=1,scale={SW}:{SH}", "-q:v", "5", os.path.join(tmp, "%03d.jpg")], check=True)
    files = sorted(f for f in os.listdir(tmp) if f.endswith(".jpg"))
    os.makedirs(out_dir, exist_ok=True)
    from PIL import Image
    per = COLS * ROWS
    for s in range(0, len(files), per):
        sheet = Image.new("RGB", (COLS * SW, ROWS * SH))
        for k, f in enumerate(files[s:s + per]):
            sheet.paste(Image.open(os.path.join(tmp, f)), ((k % COLS) * SW, (k // COLS) * SH))
        sheet.save(os.path.join(out_dir, f"s{s // per}.jpg"), quality=78)
    shutil.rmtree(tmp)
    return len(files)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("result"); ap.add_argument("video")
    ap.add_argument("--out", default="site2/data/replays"); ap.add_argument("--id", required=True)
    ap.add_argument("--meta", default="{}"); ap.add_argument("--no-stills", action="store_true")
    ap.add_argument("--keep-stills", action="store_true", help="reuse stills already cut for this replay")
    a = ap.parse_args()
    r = json.load(open(a.result))
    ts = r.get("t_start") or 0.0
    drv = (r.get("t_driver") or (ts + 15.0)) - ts      # driver control starts this long after autonomous did
    end = drv + 106.0
    alli = {str(x["track"]): x["alliance"] for x in r["robots"]}
    team = {str(x["track"]): x.get("team") for x in r["robots"]}
    robots = []
    for tid, hist in r["raw_tracks"].items():
        hist = [(p[0] - ts, p[1], p[2], p[3]) for p in hist]
        if r.get("t_start") is not None and "t_driver" in r:   # the match itself: after the buzzer people walk on and lift robots
            hist = [p for p in hist if -3.0 <= p[0] <= end]
        x = next(x for x in r["robots"] if str(x["track"]) == tid)
        robots.append({"team": team[tid], "alliance": alli[tid], "named": (x.get("confidence") or 0) >= 0.75, "path": smooth(hist),
                       "distance_ft": x.get("distance_ft"), "seen_share": x.get("seen_share"),
                       "points": x.get("points_seen"), "placements": x.get("placements")})
    cams, last = [], -9
    for t, H in r["cal_log"]:
        if t - last < 0.5:
            continue
        last = t
        p = pose(H, 1280, 720)
        cams.append([round(t - ts, 2), p["pos"], p["quat"], round(p["f"], 1)])
    t_first = min(p[0] for rb in robots for p in rb["path"])
    t_last = max(p[0] for rb in robots for p in rb["path"])
    n = 0
    old = os.path.join(a.out, a.id + ".json")
    s_abs = ts + t_first                      # video time of the first still
    if a.keep_stills and os.path.exists(old):
        o = json.load(open(old))["stills"]
        n, s_abs = o["n"], o.get("abs", ts + o["t0"])
    elif not a.no_stills:
        n = stills(a.video, os.path.join(a.out, a.id), ts + t_first, ts + t_last + 1)
    ev = [{k: e[k] for k in ("t", "type", "goal", "colour", "team", "auton") if k in e} for e in r["events"]
          if e["type"] in ("placement", "toggle")]
    out = {"id": a.id, **json.loads(a.meta), "t0": round(t_first, 2), "t1": round(t_last, 2), "driver": round(drv, 2), "auton_seen": r.get("auton_seen", True),
           "stills": {"n": n, "t0": round(s_abs - ts, 2), "abs": round(s_abs, 2), "dir": f"data/replays/{a.id}/", "cols": COLS, "rows": ROWS},
           "robots": robots, "events": ev, "cams": cams,
           "vision_score": r.get("score_check", {}).get("vision_score")}
    os.makedirs(a.out, exist_ok=True)
    json.dump(out, open(os.path.join(a.out, a.id + ".json"), "w"), separators=(",", ":"))
    print(a.id, "robots", len(robots), "cams", len(cams), "stills", n, "events", len(ev))

if __name__ == "__main__":
    main()
