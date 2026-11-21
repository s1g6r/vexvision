"""Pack every video thumbnail into a few sprite sheets (the artifact host allows 512 files).
Usage: python -m tools.pack_thumbs THUMB_DIR OUT_DIR  -> OUT_DIR/sheet-<n>.jpg + OUT_DIR/../thumbs.json"""
import json, os, sys
from PIL import Image

W, H, COLS, PER = 240, 135, 16, 320

def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    ids = sorted(f[:-4] for f in os.listdir(src) if f.endswith(".jpg") and not f.startswith("sheet-"))
    m = {}
    for n in range(0, len(ids), PER):
        chunk = ids[n:n + PER]; rows = (len(chunk) + COLS - 1) // COLS
        sheet = Image.new("RGB", (COLS * W, rows * H), (21, 20, 18))
        for i, k in enumerate(chunk):
            try:
                im = Image.open(os.path.join(src, k + ".jpg")).convert("RGB").resize((W, H))
            except Exception:
                continue
            sheet.paste(im, ((i % COLS) * W, (i // COLS) * H))
            m[k] = [n // PER, i % COLS, i // COLS, rows]
        sheet.save(os.path.join(out, f"sheet-{n // PER}.jpg"), quality=78, optimize=True, progressive=True)
    json.dump({"cols": COLS, "map": m}, open(os.path.join(os.path.dirname(out.rstrip("/")), "thumbs.json"), "w"), separators=(",", ":"))
    print(len(m), "thumbs in", (len(ids) + PER - 1) // PER, "sheets")

if __name__ == "__main__":
    main()
