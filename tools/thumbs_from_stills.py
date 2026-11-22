"""Make a picker thumbnail (data/thumbs/<match id>.jpg) for every replay that has broadcast stills
and no thumbnail yet, from the still about 25 s into the match.
Usage: python -m tools.thumbs_from_stills site2"""
import json, os, sys
from PIL import Image

site = sys.argv[1]
rep, th = os.path.join(site, "data/replays"), os.path.join(site, "data/thumbs")
packs = {}
n = 0
for e in json.load(open(os.path.join(rep, "index.json"))):
    i = e["id"]
    if not e.get("replay") or os.path.exists(os.path.join(th, i + ".jpg")):
        continue
    pk = e.get("pack")
    if pk:
        if pk not in packs:
            packs[pk] = json.load(open(os.path.join(rep, "pack", pk + ".json")))
        R = packs[pk].get(i)
    else:
        p = os.path.join(rep, i + ".json")
        R = json.load(open(p)) if os.path.exists(p) else None
    if not R or not R["stills"]["n"]:
        continue
    S = R["stills"]
    k = max(0, min(S["n"] - 1, int(25 - S["t0"])))
    per = S["cols"] * S["rows"]
    sheet = os.path.join(rep, i, f"s{k // per}.jpg")
    if not os.path.exists(sheet):
        continue
    im = Image.open(sheet)
    tw, tH = im.width // S["cols"], im.height // S["rows"]
    c, r = (k % per) % S["cols"], (k % per) // S["cols"]
    im.crop((c * tw, r * tH, (c + 1) * tw, (r + 1) * tH)).save(os.path.join(th, i + ".jpg"), quality=80)
    n += 1
print(n, "thumbnails made from stills")
