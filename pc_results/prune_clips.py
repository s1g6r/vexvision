"""Tidy up pc_results/clips. Clips are only needed while a match is being read.

Deletes clips older than a week, and if the disk is still under 50 GB free, keeps deleting the
oldest ones until it isn't. A clip whose .perc.json.gz already exists can always be re-cut from
YouTube if it is ever wanted again.

  python pc_results/prune_clips.py [--days 7] [--free-gb 50]
"""
import argparse, os, shutil, time

CLIPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clips")

def free_gb(path):
    return shutil.disk_usage(path).free / 1024 ** 3

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=7)
    ap.add_argument("--free-gb", type=float, default=50)
    a = ap.parse_args()
    if not os.path.isdir(CLIPS):
        return
    files = []
    for n in os.listdir(CLIPS):
        p = os.path.join(CLIPS, n)
        if os.path.isfile(p):
            files.append((os.path.getmtime(p), os.path.getsize(p), p))
    files.sort()
    cut = time.time() - a.days * 86400
    freed = gone = 0
    for mtime, size, p in files:
        if mtime < cut:
            os.remove(p); freed += size; gone += 1
    files = [f for f in files if f[0] >= cut]
    while files and free_gb(CLIPS) < a.free_gb:
        _, size, p = files.pop(0)
        os.remove(p); freed += size; gone += 1
    if gone:
        print(f"pruned {gone} clips, {freed / 1024 ** 3:.1f} GB, {free_gb(CLIPS):.0f} GB free")

if __name__ == "__main__":
    main()
