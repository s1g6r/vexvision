"""Fold finished plate passes (Mac or cloud, {"log", "info"} per match) into the readings.
Usage: python -m tools.plates_merge RAW DIR [DIR ...]"""
import json, os, sys
from tools.plate_pass import save

raw = sys.argv[1]
n = 0
for d in sys.argv[2:]:
    for f in sorted(os.listdir(d)):
        if not f.endswith(".plates.json"):
            continue
        mid = f[:-12]
        if not os.path.exists(os.path.join(raw, mid + ".perc.json")):
            continue
        o = json.load(open(os.path.join(d, f)))
        save(raw, mid, o["log"], o["info"]); n += 1
print(n, "matches with plate reads")
