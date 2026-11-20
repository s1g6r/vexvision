"""Add every Override upload from a YouTube channel to the frame index.

Channels like VEX Vault and Robot Stats upload each match as its own short
video, so their upload lists are the richest source of single-match frames.
Usage: python -m tools.collect_channel --out data/yt "@handle" ...
"""
import argparse, json, os, re, sys, urllib.request
from tools.collect_youtube_frames import get, is_override, TEAM_RE

def channel_videos(handle_or_url, pages=6):
    url = handle_or_url if handle_or_url.startswith("http") else f"https://www.youtube.com/{handle_or_url}/videos"
    html = get(url).decode("utf-8", "ignore")
    key = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
    ver = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', html)
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html)
    if not m:
        return []
    data = json.loads(m.group(1))
    out, conts = [], []
    def walk(o):
        if isinstance(o, dict):
            vr = o.get("videoRenderer") or o.get("gridVideoRenderer")
            if vr and "videoId" in vr:
                t = vr.get("title", {})
                title = t.get("simpleText") or "".join(r.get("text", "") for r in t.get("runs", []))
                out.append({"id": vr["videoId"], "title": title,
                            "length": vr.get("lengthText", {}).get("simpleText"),
                            "published": vr.get("publishedTimeText", {}).get("simpleText")})
            lv = o.get("lockupViewModel")
            if lv and lv.get("contentId") and lv.get("contentType", "").endswith("VIDEO"):
                meta = lv.get("metadata", {}).get("lockupMetadataViewModel", {})
                out.append({"id": lv["contentId"], "title": meta.get("title", {}).get("content", "")})
            ci = o.get("continuationCommand")
            if ci and "token" in ci:
                conts.append(ci["token"])
            for x in o.values():
                walk(x)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(data)
    for _ in range(pages):
        if not (conts and key and ver):
            break
        tok = conts.pop()
        body = json.dumps({"context": {"client": {"clientName": "WEB", "clientVersion": ver.group(1)}},
                           "continuation": tok}).encode()
        req = urllib.request.Request(f"https://www.youtube.com/youtubei/v1/browse?key={key.group(1)}",
                                     data=body, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        try:
            walk(json.loads(urllib.request.urlopen(req, timeout=30).read()))
        except Exception as e:
            print("continuation failed", e); break
    seen, uniq = set(), []
    for v in out:
        if v["id"] not in seen:
            seen.add(v["id"]); uniq.append(v)
    return uniq

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/yt")
    ap.add_argument("--pages", type=int, default=6)
    ap.add_argument("channels", nargs="+")
    a = ap.parse_args()
    idx = os.path.join(a.out, "videos.json")
    videos = json.load(open(idx)) if os.path.exists(idx) else {}
    for ch in a.channels:
        vs = channel_videos(ch, a.pages)
        new = 0
        for v in vs:
            if is_override(v) and v["id"] not in videos:
                v["teams"] = TEAM_RE.findall(v["title"]); v["channel"] = ch; v["frames"] = []
                videos[v["id"]] = v; new += 1
        print(ch, len(vs), "videos,", new, "new Override")
    json.dump(videos, open(idx, "w"), indent=1)

if __name__ == "__main__":
    main()
