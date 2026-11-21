"""Flag index entries that have no replay file (matches read from a video we don't keep)."""
import json, os, sys
d = sys.argv[1] if len(sys.argv) > 1 else "site2/data/replays"
p = os.path.join(d, "index.json"); idx = json.load(open(p))
for x in idx:
    x["replay"] = os.path.exists(os.path.join(d, x["id"] + ".json"))
json.dump(idx, open(p, "w"), indent=0)
print(sum(not x["replay"] for x in idx), "without a replay")
