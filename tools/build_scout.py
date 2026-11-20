"""Turn data/catalog.json into the compact data file the scout site loads,
and copy each video's thumbnail beside it.

Usage: python -m tools.build_scout --out build/scout [--thumbs DIR]
"""
import argparse, json, os, re, shutil

SIG = {"Great Planes", "Harbor Havoc", "Highlander Summit", "Smoky Mountain Forge", "Speedway",
       "Mall of America", "Hong Kong"}
ALIAS = {"GHOST Halloween Override UT Austin": "GHOST Halloween Spotlight", "Lobstah Bowl": "Lobstah Bowl"}

def norm_event(e):
    if not e:
        return None
    e = ALIAS.get(e, e)
    if e in SIG:
        e += " Signature"
    return e

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="data/catalog.json")
    ap.add_argument("--out", default="build/scout")
    ap.add_argument("--thumbs", default="/home/claude/scout/thumbs")
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "thumbs"), exist_ok=True)
    vids = []
    for v in json.load(open(a.catalog)):
        e = norm_event(v.get("event"))
        row = {"id": v["id"], "t": v["title"].strip(), "c": v.get("channel") or "", "k": v["kind"],
               "e": e, "s": slug(e) if e else None, "m": v.get("match"), "r": v.get("red"), "b": v.get("blue"),
               "tm": v["teams"], "l": v.get("length")}
        vids.append({k: x for k, x in row.items() if x not in (None, [], "")})
        src = os.path.join(a.thumbs, v["id"] + ".jpg")
        if os.path.exists(src):
            shutil.copy(src, os.path.join(a.out, "thumbs", v["id"] + ".jpg"))
    with open(os.path.join(a.out, "videos.json"), "w") as f:
        f.write("[\n" + ",\n".join(json.dumps(v, separators=(",", ":")) for v in vids) + "\n]\n")
    print(len(vids), "videos,", len({t for v in vids for t in v.get("tm", [])}), "teams")

if __name__ == "__main__":
    main()
