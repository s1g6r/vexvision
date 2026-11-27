"""Exit 0 when site2/data/official.json differs from the committed copy in anything but the refresh time.
Keeps the scheduled refresh from publishing a new version when no result, schedule or rating changed."""
import json, subprocess, sys

def body(raw):
    d = json.loads(raw); d.pop("fetched", None); return d

try:
    old = subprocess.run(["git", "show", "HEAD:site2/data/official.json"], capture_output=True, check=True).stdout
except subprocess.CalledProcessError:
    sys.exit(0)
sys.exit(0 if body(old) != body(open("site2/data/official.json", "rb").read()) else 1)
