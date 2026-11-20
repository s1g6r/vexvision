"""Repack replay stills into one big sheet per match (8 x 24 tiles of 320x180, under
iOS's 16.7 MP image limit), so a whole site fits in fewer files.
Usage: python -m tools.repack_stills REPLAY_DIR"""
import json, os, sys
from PIL import Image
COLS, ROWS, W, H = 8, 24, 320, 180
rep = sys.argv[1]
removed = []
for f in sorted(os.listdir(rep)):
    if not f.endswith(".json") or f.startswith("index"):
        continue
    p = os.path.join(rep, f); R = json.load(open(p)); S = R["stills"]
    if S.get("rows") == ROWS or not S.get("n"):
        continue
    d = os.path.join(rep, f[:-5]); per = S["cols"] * S["rows"]
    sheets = sorted([x for x in os.listdir(d) if x.endswith(".jpg")], key=lambda x: int(x[1:-4]))
    tiles = []
    for sh in sheets:
        im = Image.open(os.path.join(d, sh)); tw, th = im.width // S["cols"], im.height // S["rows"]
        for k in range(per):
            if len(tiles) >= S["n"]:
                break
            x, y = (k % S["cols"]) * tw, (k // S["cols"]) * th
            tiles.append(im.crop((x, y, x + tw, y + th)).resize((W, H), Image.LANCZOS))
    out_n = 0
    for s in range(0, len(tiles), COLS * ROWS):
        sheet = Image.new("RGB", (COLS * W, ROWS * H))
        for k, t in enumerate(tiles[s:s + COLS * ROWS]):
            sheet.paste(t, ((k % COLS) * W, (k // COLS) * H))
        sheet.save(os.path.join(d, f"n{out_n}.jpg"), quality=74); out_n += 1
    for sh in sheets:
        os.remove(os.path.join(d, sh)); removed.append(f"data/replays/{f[:-5]}/{sh}")
    for k in range(out_n):
        os.rename(os.path.join(d, f"n{k}.jpg"), os.path.join(d, f"s{k}.jpg"))
        removed = [r for r in removed if r != f"data/replays/{f[:-5]}/s{k}.jpg"]
    S.update({"n": len(tiles), "cols": COLS, "rows": ROWS})
    json.dump(R, open(p, "w"), separators=(",", ":"))
    print(f[:-5], len(sheets), "->", out_n)
json.dump(removed, open("/tmp/stills_removed.json", "w"))
print(len(removed), "old sheet files gone")
