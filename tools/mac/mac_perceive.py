"""Read matches on this Mac: detection, calibration and everything seen per frame, saved as
<id>.perc.json for the cloud side to finish (tracking, names, replays).
Usage: python3 mac_perceive.py JOBS OUTDIR [worker k of n]
JOBS lines: id <tab> clip path <tab> teams json"""
import json, os, sys, time, shutil, subprocess
import cv2, numpy as np
from vexvision import analyze as AN
from vexvision.detect import Detector

def ffmpeg_exe():
    for c in (shutil.which("ffmpeg"), os.path.expanduser("~/.homebrew/bin/ffmpeg"), "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if c and os.path.exists(c):
            return c
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None

FF = ffmpeg_exe()
# look closely only at the match itself once the on-screen clock is read (about twice as fast on stream clips)
QUICK = os.environ.get("VV_QUICK", "1") != "0"

def frames(path, fps=3, size=(1280, 720)):
    """ffmpeg when it can decode the clip (the Cornfield clips are AV1), OpenCV otherwise."""
    if FF:
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
        if k > 0:
            return
    yield from frames_cv(path, fps, size)

def frames_cv(path, fps=3, size=(1280, 720)):
    cap = cv2.VideoCapture(path)
    src = cap.get(cv2.CAP_PROP_FPS) or 30
    i, k = 0, 0
    while True:
        if not cap.grab():
            break
        if i / src + 1e-6 >= k / fps:
            ok, img = cap.retrieve()
            if not ok:
                break
            yield k / fps, cv2.resize(img, size)
            k += 1
        i += 1
    cap.release()

def main():
    jobs, out = sys.argv[1], sys.argv[2]
    k, n = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (0, 1)
    os.makedirs(out, exist_ok=True)
    dev = os.environ.get("VV_DEVICE") or None
    det = Detector("goals.pt,robots.pt", device=dev)
    lines = [l.rstrip("\n").split("\t") for l in open(jobs) if l.strip()]
    todo = [x for j, x in enumerate(lines) if j % n == k]
    idle = 0
    while todo and idle < 1800:            # clips can still be arriving: wait up to 30 min for the next one
        left = []
        for mid, clip, teams in todo:
            dst = os.path.join(out, mid + ".perc.json")
            clip = os.path.expanduser(clip)
            if os.path.exists(dst):
                continue
            if not os.path.exists(clip):
                left.append((mid, clip, teams)); continue
            t0 = time.time()
            res = AN.analyze(frames(clip), det, teams=json.loads(teams), log=lambda *a: None, quick=QUICK)
            P = res.pop("perception")
            json.dump(P, open(dst + ".tmp", "w"), default=float, separators=(",", ":"))
            os.replace(dst + ".tmp", dst)
            print(time.strftime("%H:%M:%S"), mid, f"{time.time() - t0:.0f}s", flush=True)
            idle = 0
        if len(left) == len(todo):
            time.sleep(20); idle += 20
        todo = left

if __name__ == "__main__":
    main()
