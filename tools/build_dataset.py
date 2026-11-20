"""Assemble a YOLO dataset from labelled frames, holding out whole videos for validation."""
import argparse, glob, os, shutil, yaml

NAMES = {0: "goal_red", 1: "goal_blue", 2: "goal_neutral", 3: "goal_center"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True); ap.add_argument("--frames", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--val-videos", default="")
    ap.add_argument("--names", default="")
    a = ap.parse_args()
    val = set(v for v in a.val_videos.split(",") if v)
    names = NAMES if not a.names else {i: n for i, n in enumerate(a.names.split(","))}
    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        os.makedirs(os.path.join(a.out, sub), exist_ok=True)
    n = {"train": 0, "val": 0}
    for lab in glob.glob(os.path.join(a.labels, "*.txt")):
        stem = os.path.basename(lab)[:-4]
        split = "val" if stem[:11] in val else "train"
        img = os.path.join(a.frames, stem + ".jpg")
        if not os.path.exists(img):
            continue
        shutil.copy(img, os.path.join(a.out, "images", split, stem + ".jpg"))
        shutil.copy(lab, os.path.join(a.out, "labels", split, stem + ".txt"))
        n[split] += 1
    yaml.safe_dump({"path": os.path.abspath(a.out), "train": "images/train", "val": "images/val", "names": names},
                   open(os.path.join(a.out, "data.yaml"), "w"))
    print(n)

if __name__ == "__main__":
    main()
