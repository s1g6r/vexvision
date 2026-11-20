"""Merge per-shard replay indexes (index_*.json) into index.json."""
import json, os, sys
d = sys.argv[1] if len(sys.argv) > 1 else "site2/data/replays"
seen, out = set(), []
for f in sorted(os.listdir(d)):
    if f.startswith("index") and f.endswith(".json"):
        for x in json.load(open(os.path.join(d, f))):
            if x["id"] not in seen:
                seen.add(x["id"]); out.append(x)
json.dump(out, open(os.path.join(d, "index.json"), "w"), indent=0)
print(len(out), "matches in index")
