"""Track clips cut from a full-day event stream (not separate match videos).
Usage: python -m tools.cc_run MANIFEST CLIP_DIR RAW_DIR REPLAY_DIR [ids...]
MANIFEST: [{id, event, match, red, blue}]; clips are CLIP_DIR/<id>.mp4.
A team's known robot colour can be given with --look 2360A=purple."""
import json, os, subprocess, sys
from vexvision import analyze as AN, stream
from vexvision.detect import Detector

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--look")]
    looks = dict(a[len("--look="):].split("=", 1) for a in sys.argv[1:] if a.startswith("--look="))
    man, clips, raw, rep = args[:4]
    only = set(args[4:])
    det = Detector("/home/claude/work/runs/goals_r3/weights/best.pt,/home/claude/work/robots_r4.pt")
    idx_p = os.path.join(rep, "index_cc.json")
    index = json.load(open(idx_p)) if os.path.exists(idx_p) else []
    for m in json.load(open(man)):
        if only and m["id"] not in only:
            continue
        clip = os.path.join(clips, m["id"] + ".mp4")
        if not os.path.exists(clip):
            print(m["id"], "no clip"); continue
        res = AN.analyze(stream.video_frames(clip, 0, None, fps=3), det, teams={"red": m["red"], "blue": m["blue"]})
        P = res.pop("perception"); P["looks"] = looks
        json.dump(P, open(os.path.join(raw, m["id"] + ".perc.json"), "w"), default=float, separators=(",", ":"))
        res = AN.reason(json.loads(json.dumps(P, default=float)))
        json.dump(res, open(os.path.join(raw, m["id"] + ".json"), "w"), default=float)
        e = {k: m[k] for k in ("id", "event", "match", "red", "blue")}
        e["video"] = m.get("video", m["id"])
        if "robots" in res:
            e["calibrated"] = round(len(res["cal_log"]) / max(1, res["frames"]), 2)
            e["seen"] = round(sum(r["seen_share"] for r in res["robots"]) / 4, 2)
            e["named"] = sum(1 for r in res["robots"] if r.get("team"))
            meta = {k: e[k] for k in ("event", "match", "red", "blue", "video")}
            subprocess.run([sys.executable, "-m", "tools.export_replay", os.path.join(raw, m["id"] + ".json"), clip,
                            "--out", rep, f"--id={m['id']}", "--meta", json.dumps(meta)], check=False)
        else:
            e["error"] = res.get("error")
        thumb = os.path.join(os.path.dirname(rep.rstrip("/")), "thumbs", m["id"] + ".jpg")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "60", "-i", clip, "-frames:v", "1",
                        "-vf", "scale=320:180", "-q:v", "5", thumb], check=False)
        index = [x for x in index if x["id"] != m["id"]] + [e]
        json.dump(index, open(idx_p, "w"), indent=0)
        print(json.dumps(e), [(r["team"], r.get("confidence")) for r in res.get("robots", [])], flush=True)

if __name__ == "__main__":
    main()
