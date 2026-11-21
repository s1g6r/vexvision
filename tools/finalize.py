"""Bring every finished match up to date: merge shard indexes, redo reasoning from the
perception logs, recut stills that don't cover the match, rebuild team stats.
Usage: python -m tools.finalize RAW_DIR REPLAY_DIR VIDEO_DIR [--extra q19=raw_q19.json]"""
import json, os, subprocess, sys

def run(*a):
    subprocess.run([sys.executable, "-m", *a], check=False)

def main():
    raw, rep, vids = sys.argv[1:4]
    extra = sys.argv[sys.argv.index("--extra") + 1:] if "--extra" in sys.argv else []
    subprocess.run([sys.executable, "tools/merge_index.py", rep], check=False)
    idx = {x["id"]: x for x in json.load(open(os.path.join(rep, "index.json")))}
    have = [i for i in idx if os.path.exists(os.path.join(raw, i + ".perc.json"))]
    run("tools.retrack", raw, rep, *have)
    for i in have:
        p = os.path.join(rep, i + ".json")
        R = json.load(open(p)) if os.path.exists(p) else None
        if R and R["stills"]["n"] >= R["t1"] - R["stills"]["t0"]:
            continue
        if "robots" not in json.load(open(os.path.join(raw, i + ".json"))):
            continue
        if not os.path.exists(os.path.join(vids, i + ".mp4")):
            continue                      # read elsewhere (the PC): no video here to cut stills from
        e = idx[i]
        meta = {k: e.get(k) for k in ("event", "match", "red", "blue", "video")}
        run("tools.export_replay", os.path.join(raw, i + ".json"), os.path.join(vids, i + ".mp4"),
            "--out", rep, f"--id={i}", "--meta", json.dumps(meta))
    run("tools.team_stats", "--raw", raw, "--index", os.path.join(rep, "index.json"),
        "--out", os.path.join(os.path.dirname(rep.rstrip("/")), "team_stats.json"), "--extra", *extra)

if __name__ == "__main__":
    main()
