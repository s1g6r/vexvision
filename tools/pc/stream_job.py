"""Read every match in one YouTube event stream (or one single-match video) and save what was
seen, ready for the cloud side to finish. Works on Windows, macOS and Linux.

  python tools/pc/stream_job.py --video VIDEO_ID --event EVENT_ID --prefix lp- [--single]

--event is the VEX event id (the number in stats.2360arachnid.com/data/override/events/<id>.json);
it gives the official teams for each match. --prefix starts every match id (short, ends in "-").
--single treats the whole video as one match (for single-match uploads).

Writes pc_results/<id>.perc.json.gz and pc_results/<id>.meta.json. Safe to re-run: finished
matches are skipped. Needs: pip install -r tools/pc/requirements.txt
"""
import argparse, gzip, json, os, re, shutil, subprocess, sys, time, urllib.request
import numpy as np, cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from vexvision import analyze as AN, overlay
from vexvision.detect import Detector

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
STATS = "https://stats.2360arachnid.com/data/override/events/{}.json"

def ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

FF = ffmpeg()

def direct_url(video):
    """A direct stream URL (720p or less). Some streams only open with the Android client."""
    import yt_dlp
    for client in (None, "android"):
        opts = {"quiet": True, "no_warnings": True, "format": "bv*[height<=720][ext=mp4]/bv*[height<=720]/b[height<=720]/b"}
        if client:
            opts["extractor_args"] = {"youtube": {"player_client": [client]}}
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                info = y.extract_info(f"https://www.youtube.com/watch?v={video}", download=False)
            url = info.get("url") or (info.get("requested_formats") or [{}])[0].get("url")
            if url:
                return url, float(info.get("duration") or 0), info.get("title", "")
        except Exception as e:
            last = e
    raise SystemExit(f"Could not open video {video}: {last}")

def grab(url, t, w=1280):
    p = subprocess.run([FF, "-loglevel", "error", "-ss", f"{t:.1f}", "-i", url, "-frames:v", "1", "-f", "image2pipe",
                        "-vcodec", "png", "-"], capture_output=True, timeout=60)
    if not p.stdout:
        return None
    img = cv2.imdecode(np.frombuffer(p.stdout, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    return cv2.resize(img, (w, int(img.shape[0] * w / img.shape[1])))

def norm(key):
    """Overlay match key -> our match name: 'Q 7' -> 'Qual 7', 'QF 2-1' -> 'QF 2-1', 'F 1-1' -> 'Final 1-1'."""
    if not key:
        return None
    k = key.upper().replace("OF ", "QF ").strip()
    m = re.match(r"^Q(?:UAL)?\s*(\d+)$", k)
    if m:
        return f"Qual {int(m.group(1))}"
    m = re.match(r"^(R16|QF|SF|F|FINALS?)\s*(\d+)-(\d+)$", k)
    if m:
        r = {"F": "Final", "FINAL": "Final", "FINALS": "Final"}.get(m.group(1), m.group(1))
        return f"{r} {int(m.group(2))}-{int(m.group(3))}"
    m = re.match(r"^FINALS?\s*(\d+)$", k)
    if m:
        return f"Final 1-{int(m.group(1))}"
    return None

def scan(url, dur, step=30, log=print):
    """Read the match title in the corner every `step` seconds. Returns {match: [(t0, t1), ...]} runs."""
    from concurrent.futures import ThreadPoolExecutor
    runs, cur = {}, None
    ts = [float(t) for t in np.arange(0, max(dur - 5, 0), step)]
    pool = ThreadPoolExecutor(8)
    imgs = pool.map(lambda t: grab(url, t), ts)          # many downloads at once, read in order
    for t, img in zip(ts, imgs):
        name = None
        if img is not None:
            r = overlay.read(img)
            name = norm(r.match)
        if name and cur and cur[0] == name and t - cur[2] <= 2 * step:
            cur[2] = t
        elif name:
            cur = [name, t, t]; runs.setdefault(name, []).append(cur)
        else:
            cur = None
        if int(t) % 1800 == 0:
            log(f"  scanned {t / 60:.0f} of {dur / 60:.0f} min, {len(runs)} matches so far")
    return {k: [(a, b) for _, a, b in v] for k, v in runs.items()}

def official(event):
    try:
        e = json.load(urllib.request.urlopen(STATS.format(event), timeout=30))
    except Exception:
        return None, {}
    num = {t["id"]: t["number"] for t in e["teams"]}
    RN = {2: "Qual", 3: "QF", 4: "SF", 5: "Final", 6: "R16"}
    out = {}
    for m in e["matches"]:
        if m["round"] not in RN:
            continue
        nm = f"Qual {m['num']}" if m["round"] == 2 else f"{RN[m['round']]} {m['inst']}-{m['num']}"
        out[nm] = {"red": [num.get(t, str(t)) for t in m["red"]], "blue": [num.get(t, str(t)) for t in m["blue"]]}
    return e["name"], out

def cut(url, t0, dur, dst):
    subprocess.run([FF, "-loglevel", "error", "-y", "-ss", f"{t0:.1f}", "-i", url, "-t", f"{dur:.1f}", "-an", "-c", "copy", dst],
                   timeout=900)
    return os.path.exists(dst) and os.path.getsize(dst) > 100000

def frames(path, fps=3, size=(1280, 720)):
    p = subprocess.Popen([FF, "-loglevel", "error", "-i", path, "-vf", f"fps={fps},scale={size[0]}:{size[1]}",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    n, k = size[0] * size[1] * 3, 0
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield k / fps, np.frombuffer(buf, np.uint8).reshape(size[1], size[0], 3)
        k += 1
    p.wait()

_reid = None

def looks(P, mid, clip, out):
    """What each robot looks like (crop embeddings), so the cloud side can tell partners apart
    across a whole event. Saved as <id>.reid.json.gz next to the results."""
    global _reid
    try:
        from tools import reid as RE
        if _reid is None:
            _reid = RE.model()
        rawdir = os.path.join(out, "raw"); os.makedirs(rawdir, exist_ok=True)
        json.dump(AN.reason(json.loads(json.dumps(P, default=float))), open(os.path.join(rawdir, mid + ".json"), "w"), default=float)
        tmp = os.path.join(out, "reid_tmp"); os.makedirs(tmp, exist_ok=True)
        RE.run_match(_reid, rawdir, mid, clip, tmp)
        src = os.path.join(tmp, mid + ".json")
        if os.path.exists(src):
            with open(src) as f, gzip.open(os.path.join(out, mid + ".reid.json.gz"), "wt") as g:
                g.write(f.read())
    except Exception as e:
        print(f"  looks for {mid} failed: {e}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True); ap.add_argument("--event", required=True, type=int)
    ap.add_argument("--prefix", required=True); ap.add_argument("--single", action="store_true")
    ap.add_argument("--match", help="match name for --single when the overlay can't be read, e.g. 'Qual 25'")
    ap.add_argument("--out", default=os.path.join(ROOT, "pc_results"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True); clips = os.path.join(a.out, "clips"); os.makedirs(clips, exist_ok=True)
    url, dur, title = direct_url(a.video)
    ev_name, off = official(a.event)
    print(f"{title} ({dur / 60:.0f} min) at {ev_name}")
    if a.single:
        name = a.match
        if not name:
            for t in (dur * 0.3, dur * 0.5, dur * 0.7):
                img = grab(url, t)
                name = norm(overlay.read(img).match) if img is not None else None
                if name:
                    break
        if not name:
            raise SystemExit("Couldn't read the match name; pass --match")
        windows = {name: (0.0, dur)}
    else:
        runs = scan(url, dur, log=print)
        windows = {}
        for name, R in runs.items():
            t0, t1 = max(R, key=lambda r: r[1] - r[0])          # longest run; replays of old matches are shorter
            a0 = max(0.0, t0 - 60); windows[name] = (a0, min(a0 + 420, t1 + 150) - a0)
    det = Detector(",".join(os.path.join(ROOT, "tools", "pc", w) for w in ("goals.pt", "robots.pt")))
    todo = sorted(windows.items(), key=lambda kv: kv[1][0])
    print(f"{len(todo)} matches found")
    for name, (t0, length) in todo:
        mid = a.prefix + name.lower().replace(" ", "")
        dst = os.path.join(a.out, mid + ".perc.json.gz")
        if os.path.exists(dst):
            continue
        teams = off.get(name)
        if not teams:
            print(f"  {name}: not in the official results, skipped"); continue
        clip = os.path.join(clips, mid + ".mp4")
        if not os.path.exists(clip) and not cut(url, t0, length, clip):
            url, _, _ = direct_url(a.video)                    # links expire after a few hours
            if not cut(url, t0, length, clip):
                print(f"  {name}: download failed"); continue
        t = time.time()
        res = AN.analyze(frames(clip), det, teams=teams, log=lambda *x: None)
        P = res.pop("perception"); P["looks"] = {"2360A": "black"}
        with gzip.open(dst + ".tmp", "wt") as f:
            json.dump(P, f, default=float, separators=(",", ":"))
        os.replace(dst + ".tmp", dst)
        looks(P, mid, clip, a.out)
        json.dump({"id": mid, "event": ev_name, "event_id": a.event, "match": name, **teams, "stream": a.video,
                   "start": round(t0), "length": round(length), "title": title},
                  open(os.path.join(a.out, mid + ".meta.json"), "w"))
        print(f"  {name} done in {time.time() - t:.0f}s")

if __name__ == "__main__":
    main()
