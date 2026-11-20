"""Add matches cut from a full-day event stream to the site's video list, so team
pages list them and link to the right moment of the stream.
Usage: python -m tools.add_stream_matches MANIFEST STREAM_ID CHANNEL SITE_VIDEOS_JSON"""
import json, sys
man, stream_id, channel, path = sys.argv[1:5]
vids = [v for v in json.load(open(path)) if not v["id"].startswith("cc-")]
for m in json.load(open(man)):
    tm = m["red"] + m["blue"]
    vids.append({"id": m["id"], "t": f"{m['event']} - {m['match']} ({' & '.join(m['red'])} vs {' & '.join(m['blue'])})",
                 "c": channel, "k": "match", "e": m["event"].replace(" (Fall 2026)", ""), "s": "cornfield-clash-jr-fall-2026",
                 "m": m["match"], "r": m["red"], "b": m["blue"], "tm": tm, "l": "",
                 "u": f"https://www.youtube.com/watch?v={stream_id}&t={int(m['start']) + 60}s"})
json.dump(vids, open(path, "w"), separators=(",", ":"))
print(len(vids), "videos")
