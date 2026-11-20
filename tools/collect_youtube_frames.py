"""Collect real Override match frames from YouTube's auto-generated thumbnails.

YouTube stores three frames from every video (at 25/50/75%) as 1280x720 JPEGs.
For short single-match uploads these are frames from mid-match, which makes
them a free source of real broadcast frames for building and testing the
vision model. Titles often name the four teams, which gives weak labels for
team-number reading.

Usage: python -m tools.collect_youtube_frames --out data/yt --queries-file q.txt
"""
import argparse, json, os, re, time, urllib.parse, urllib.request

UA = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}
SHORT = "EgIYAQ%253D%253D"  # filter: under 4 minutes

def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def search(query, short=True):
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
    if short:
        url += "&sp=" + SHORT
    html = get(url).decode("utf-8", "ignore")
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html)
    if not m:
        return []
    data = json.loads(m.group(1))
    out = []
    def walk(o):
        if isinstance(o, dict):
            if "videoRenderer" in o:
                v = o["videoRenderer"]
                title = "".join(r.get("text", "") for r in v.get("title", {}).get("runs", []))
                out.append({
                    "id": v["videoId"], "title": title,
                    "length": v.get("lengthText", {}).get("simpleText"),
                    "published": v.get("publishedTimeText", {}).get("simpleText"),
                    "channel": "".join(r.get("text", "") for r in v.get("ownerText", {}).get("runs", [])),
                })
            for x in o.values():
                walk(x)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(data)
    return out

def is_override(v):
    t = v["title"].lower()
    return "override" in t and "push back" not in t

TEAM_RE = re.compile(r"\b(\d{1,5}[A-Z])\b")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/yt")
    ap.add_argument("--queries-file")
    ap.add_argument("--max-videos", type=int, default=400)
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "frames"), exist_ok=True)
    idx_path = os.path.join(a.out, "videos.json")
    videos = json.load(open(idx_path)) if os.path.exists(idx_path) else {}
    queries = [q.strip() for q in open(a.queries_file)] if a.queries_file else []
    for q in queries:
        if not q or len(videos) >= a.max_videos:
            continue
        try:
            res = search(q)
        except Exception as e:
            print("search failed", q, e); continue
        new = 0
        for v in res:
            if is_override(v) and v["id"] not in videos:
                v["teams"] = TEAM_RE.findall(v["title"])
                v["query"] = q
                videos[v["id"]] = v; new += 1
        print(f"{q!r}: {len(res)} results, {new} new Override videos (total {len(videos)})")
        json.dump(videos, open(idx_path, "w"), indent=1)
        time.sleep(1.0)
    got = 0
    for vid, v in videos.items():
        v.setdefault("frames", [])
        for k in ("maxres1", "maxres2", "maxres3"):
            p = os.path.join(a.out, "frames", f"{vid}_{k}.jpg")
            if os.path.exists(p):
                if p not in v["frames"]: v["frames"].append(p)
                continue
            try:
                b = get(f"https://i.ytimg.com/vi/{vid}/{k}.jpg", 15)
                open(p, "wb").write(b); v["frames"].append(p); got += 1
            except Exception:
                pass
    json.dump(videos, open(idx_path, "w"), indent=1)
    print("downloaded", got, "frames;", sum(len(v["frames"]) for v in videos.values()), "total")

if __name__ == "__main__":
    main()
