"""Merge an export from tools/label.html into data/landmarks.json, data/robots.json, data/stacks.json."""
import json, os, sys

def merge(path, key, src):
    d = json.load(open(path)) if os.path.exists(path) else {}
    for k, v in src.items():
        if v:
            d[k] = v
    json.dump(d, open(path, "w"), indent=0)
    return len(d)

if __name__ == "__main__":
    lab = json.load(open(sys.argv[1]))
    root = sys.argv[2] if len(sys.argv) > 2 else "data"
    for key, fn in (("landmarks", "landmarks.json"), ("robots", "robots.json"), ("stacks", "stacks.json")):
        print(fn, merge(os.path.join(root, fn), key, lab.get(key, {})))
