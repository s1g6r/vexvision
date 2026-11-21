"""Merge per-shard replay indexes (index_*.json) into index.json. The same match filmed twice
(a single-match upload and a stream) is kept once: the copy where the robots were seen best."""
import json, os, sys
d = sys.argv[1] if len(sys.argv) > 1 else "site2/data/replays"
seen, out = set(), []
for f in sorted(os.listdir(d)):
    if f.startswith("index") and f.endswith(".json"):
        for x in json.load(open(os.path.join(d, f))):
            if x["id"] not in seen:
                seen.add(x["id"]); out.append(x)
best = {}
for x in out:
    k = (x.get("event"), x.get("match"))
    if not x.get("match") or "error" in x:
        continue
    if k not in best or (x.get("seen") or 0) > (best[k].get("seen") or 0):
        best[k] = x
keep = [x for x in out if not x.get("match") or "error" in x or best.get((x.get("event"), x.get("match"))) is x]
json.dump(keep, open(os.path.join(d, "index.json"), "w"), indent=0)
print(len(keep), "matches in index,", len(out) - len(keep), "duplicates dropped")
