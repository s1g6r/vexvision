"""Finish matches whose frames were read elsewhere (the Mac): tracking, names, replay, index entry.
Usage: python -m tools.finish_perc RAW_DIR REPLAY_DIR id[@manifest@clipdir] ..."""
import json, os, subprocess, sys
from vexvision import analyze as AN

from tools.official import EVENTS
SHORT = {v: k for k, v in EVENTS.items()}
MANS = {"gl-": ("/home/claude/work/gl/matches.json", "/home/claude/work/gl/clips"),
        "cc-": ("/home/claude/work/cc/matches2.json", "/home/claude/work/cc/clips")}

def main():
    raw, rep = sys.argv[1:3]
    idx_p = os.path.join(rep, "index_mac.json")
    index = json.load(open(idx_p)) if os.path.exists(idx_p) else []
    for mid in sys.argv[3:]:
        if mid[:3] in MANS:
            man, clips = MANS[mid[:3]]
            m = {x["id"]: x for x in json.load(open(man))}[mid]
        else:                                   # read on the PC: its meta file sits next to the results
            m = json.load(open(os.path.join("/home/claude/work/pc/pc_results", mid + ".meta.json")))
            m["event"] = SHORT.get(m.get("event_id"), m["event"])
            clips = "/home/claude/work/pc/clips"
        P = json.load(open(os.path.join(raw, mid + ".perc.json")))
        res = AN.reason(P)
        json.dump(res, open(os.path.join(raw, mid + ".json"), "w"), default=float)
        e = {k: m[k] for k in ("event", "match", "red", "blue")}; e["id"] = mid; e["video"] = mid
        if "robots" in res:
            e["calibrated"] = round(len(res["cal_log"]) / max(1, res["frames"]), 2)
            e["seen"] = round(sum(r["seen_share"] for r in res["robots"]) / 4, 2)
            e["named"] = sum(1 for r in res["robots"] if r.get("team"))
            e["sure"] = sum(1 for r in res["robots"] if (r.get("confidence") or 0) >= 0.75)
            meta = {k: e[k] for k in ("event", "match", "red", "blue", "video")}
            clip = os.path.join(clips, mid + ".mp4")
            if os.path.exists(clip):
                subprocess.run([sys.executable, "-m", "tools.export_replay", os.path.join(raw, mid + ".json"), clip,
                                "--out", rep, f"--id={mid}", "--meta", json.dumps(meta)], check=False)
        else:
            e["error"] = res.get("error")
        index = [x for x in index if x["id"] != mid] + [e]
        json.dump(index, open(idx_p, "w"), indent=0)
        print(mid, e.get("seen"), e.get("sure"), e.get("error"), flush=True)

if __name__ == "__main__":
    main()
