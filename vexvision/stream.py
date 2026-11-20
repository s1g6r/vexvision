"""Read frames straight from a livestream or video URL, and find one match in it.

Nothing is downloaded in full: yt-dlp resolves the media URL, and ffmpeg seeks
into it over HTTP to grab single frames or a short clip.

Finding a match (same idea as reading the broadcast clock, but cheaper):
1. Probe the stream at even spacing (default every 6 minutes) and read the
   overlay's match name at each probe.
2. Matches are played in order, so the target lies between the last probe
   showing an earlier match and the first probe showing a later one. Bisect
   that window on the overlay until the target's name appears.
3. Walk forward in 3-second steps to the start of autonomous (clock reads 0:15
   in the auton period, or the overlay flips from "pre-match" to running).
A typical 7-hour stream takes about 70 frame grabs, under a minute on a home
connection.
"""
import json, re, shutil, subprocess
import numpy as np
import cv2
from . import overlay

ORDER = {"P": 0, "Q": 1, "R32": 2, "R16": 3, "QF": 4, "SF": 5, "F": 6}

def match_key(name):
    """'Q 12' -> (1, 12, 0); 'SF 2-1' -> (5, 2, 1). Used to order matches in time."""
    if not name:
        return None
    m = re.match(r"([A-Z0-9]+)\s*(\d+)(?:-(\d+))?", name.replace(" ", " "))
    if not m:
        return None
    kind = m.group(1)
    return (ORDER.get(kind, 9), int(m.group(2)), int(m.group(3) or 0))

def resolve(url, height=720):
    """Media URL + duration for a YouTube (or other) page URL, via yt-dlp."""
    if not shutil.which("yt-dlp"):
        raise RuntimeError("yt-dlp is not installed: pip install yt-dlp")
    fmt = f"bv*[height<={height}][vcodec^=avc1]/bv*[height<={height}]/b[height<={height}]/b"
    out = subprocess.run(["yt-dlp", "-f", fmt, "-J", "--no-warnings", url], capture_output=True, text=True, check=True)
    info = json.loads(out.stdout)
    if "requested_formats" in info:
        media = info["requested_formats"][0]["url"]
    else:
        media = info.get("url")
    return media, float(info.get("duration") or 0), info.get("title", "")

def grab(media, t, size=(1280, 720)):
    """One frame at time t (seconds) as a BGR array, or None."""
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", media, "-frames:v", "1",
           "-vf", f"scale={size[0]}:{size[1]}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.run(cmd, capture_output=True)
    n = size[0] * size[1] * 3
    if len(p.stdout) < n:
        return None
    return np.frombuffer(p.stdout[:n], np.uint8).reshape(size[1], size[0], 3).copy()

def frames(media, t0, dur, fps=8, size=(1280, 720)):
    """Yield (t, frame) for a clip, decoded once by a single ffmpeg process."""
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{t0:.2f}", "-i", media, "-t", f"{dur:.2f}",
           "-vf", f"fps={fps},scale={size[0]}:{size[1]}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = size[0] * size[1] * 3
    k = 0
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield t0 + k / fps, np.frombuffer(buf, np.uint8).reshape(size[1], size[0], 3)
        k += 1
    p.wait()

def video_frames(path, t0=0.0, dur=None, fps=8):
    """Same as frames() for a local file. ffmpeg decodes it, so AV1 and other
    codecs OpenCV cannot read still work."""
    if dur is None:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True).stdout.strip()
        dur = max(0.0, float(out or 0) - t0)
    yield from frames(path, t0, dur, fps=fps)

def read_at(media, t, valid=None):
    img = grab(media, t)
    if img is None:
        return None
    return overlay.read(img, valid)

def find_match(media, duration, target, step=360.0, valid=None, log=print):
    """Return (t_start_of_auton, overlay_read) for match `target` (e.g. 'Q 12'), or (None, None)."""
    tk = match_key(target)
    probes = []
    for t in np.arange(30.0, max(31.0, duration - 30), step):
        r = read_at(media, t, valid)
        k = match_key(r.match) if r else None
        probes.append((t, k, r))
        log(f"probe {t/60:6.1f} min: {r.match if r else None}")
        if k == tk:
            break
    lo, hi = 0.0, duration
    for t, k, r in probes:
        if k is None:
            continue
        if k < tk:
            lo = max(lo, t)
        elif k > tk:
            hi = min(hi, t)
    hit = next(((t, r) for t, k, r in probes if k == tk), None)
    # bisect between lo and hi on the overlay
    tries = 0
    while hit is None and hi - lo > 20 and tries < 30:
        tries += 1
        mid = (lo + hi) / 2
        r = read_at(media, mid, valid)
        k = match_key(r.match) if r else None
        log(f"bisect {mid/60:6.1f} min: {r.match if r else None}")
        if k is None:
            # nudge: look a little later for a frame with an overlay
            for dt in (15, 30, 45):
                r = read_at(media, mid + dt, valid)
                k = match_key(r.match) if r else None
                if k is not None:
                    mid += dt; break
        if k is None:
            lo = mid
        elif k == tk:
            hit = (mid, r)
        elif k < tk:
            lo = mid
        else:
            hi = mid
    if hit is None:
        return None, None
    # walk back to before the match, then forward to the start of auton
    t = hit[0]
    for _ in range(60):
        r = read_at(media, t - 10, valid)
        if r is None or match_key(r.match) != tk or (r.period == "driver" and r.clock and r.clock < 100):
            break
        t -= 10
    best = None
    for k in range(80):
        tt = t + 3 * k
        r = read_at(media, tt, valid)
        if r is None:
            continue
        if match_key(r.match) == tk and r.period == "auton" and r.clock is not None:
            # clock counts down from 15
            best = tt - (15 - r.clock)
            return best, r
        if match_key(r.match) == tk and r.period == "driver" and r.clock is not None:
            # missed auton on the clock: driver starts 15 s (+ ~2 s pause) after auton
            best = tt - (105 - r.clock) - 17
            return best, r
        if match_key(r.match) is not None and match_key(r.match) > tk:
            break
    return hit[0], hit[1]
