"""Refresh the official files that tools/official.py reads, straight from stats.2360arachnid.com.
Usage: python -m tools.fetch_official [--dir data/official]
Writes ev_<id>.json for every event in tools.official.EVENTS plus leaderboard.json.
A file is only replaced when the download parses as JSON, so a bad response never wipes good data."""
import argparse, json, os, sys, urllib.request

from tools.official import EVENTS

BASE = "https://stats.2360arachnid.com/data/override"


def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def save(raw, path):
    json.loads(raw)                    # raises on HTML error pages
    tmp = path + ".tmp"
    open(tmp, "wb").write(raw)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/official")
    a = ap.parse_args()
    os.makedirs(a.dir, exist_ok=True)
    ok = bad = 0
    for name, eid in sorted(EVENTS.items(), key=lambda x: x[1]):
        try:
            save(get(f"{BASE}/events/{eid}.json"), os.path.join(a.dir, f"ev_{eid}.json")); ok += 1
        except Exception as e:
            print(f"  {name} ({eid}): {e}", file=sys.stderr); bad += 1
    try:
        save(get(f"{BASE}/leaderboard.json"), os.path.join(a.dir, "leaderboard.json")); ok += 1
    except Exception as e:
        print(f"  leaderboard: {e}", file=sys.stderr); bad += 1
    if ok:
        import datetime
        open(os.path.join(a.dir, "fetched.txt"), "w").write(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + "\n")
    print(f"{ok} files refreshed, {bad} failed")


if __name__ == "__main__":
    main()
