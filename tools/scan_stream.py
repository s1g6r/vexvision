"""Read the match title on stream frames (one every 30 s) to find where each match is.
Usage: python -m tools.scan_stream FRAMES_DIR OUT.json
FRAMES_DIR holds <second>.jpg files grabbed from the stream (see docs/READ_AN_EVENT.md)."""
import glob, json, os, sys
from concurrent.futures import ProcessPoolExecutor
import cv2

def one(p):
    from vexvision import overlay
    from tools.pc.stream_job import norm
    img = cv2.imread(p)
    r = overlay.read(img) if img is not None else None
    return int(os.path.basename(p)[:-4]), (norm(r.match) if r else None), ((r.red, r.blue) if r else None)

def main():
    src, out = sys.argv[1], sys.argv[2]
    fs = sorted(glob.glob(os.path.join(src, "*.jpg")), key=lambda p: int(os.path.basename(p)[:-4]))
    with ProcessPoolExecutor(8) as ex:
        res = list(ex.map(one, fs, chunksize=8))
    json.dump(res, open(out, "w"))
    print(sum(1 for r in res if r[1]), "of", len(res), "frames had a readable match title")

if __name__ == "__main__":
    main()
