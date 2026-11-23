"""Give every replay a link to its original YouTube video at the moment autonomous starts.

data/yt_starts.json says where each match's clip begins in its YouTube video ({id: [video, seconds]});
the reading says when autonomous starts in the clip. The result goes into the replay index as
"yt": [video, seconds].  Usage: python -m tools.yt_links RAW INDEX"""
import json, os, sys

raw, idx_p = sys.argv[1], sys.argv[2]
starts = json.load(open(os.path.join(os.path.dirname(__file__), "..", "data", "yt_starts.json")))
idx = json.load(open(idx_p))
n = 0
for x in idx:
    s = starts.get(x["id"])
    p = os.path.join(raw, x["id"] + ".json")
    if not s or not os.path.exists(p):
        continue
    ts = json.load(open(p)).get("t_start")
    if ts is None:
        continue
    x["yt"] = [s[0], max(0, int(s[1] + ts - 3))]      # a few seconds early, so the start isn't cut off
    n += 1
json.dump(idx, open(idx_p, "w"), indent=0)
print(n, "replays link to YouTube at autonomous")
