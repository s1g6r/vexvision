"""Propose labels on unlabelled frames with the current models (resumable).

For every frame: detect goals and robots, calibrate from goals, score the tape
fit. Saves one JSON line per frame to proposals.jsonl. accept() then keeps
only confident results for the next training round:
- goals: calibration with tape fit >= q_min and >= 5 goal detections agreeing
- robots: frames where exactly four robots are found with conf >= r_min, all
  standing inside the field (so no robot in the frame is left unlabelled)
"""
import argparse, json, os, sys, time
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vexvision import calibrate as C, field as F
from vexvision.detect import Detector, goal_points
from vexvision.analyze import Calibrator, robot_floor_point

def propose(frames_dir, names, weights, out):
    det = Detector(weights, conf=0.1)
    done = set()
    if os.path.exists(out):
        for line in open(out):
            done.add(json.loads(line)["frame"])
    f = open(out, "a")
    t0 = time.time()
    for i, fn in enumerate(names):
        if fn in done:
            continue
        img = cv2.imread(os.path.join(frames_dir, fn))
        if img is None:
            continue
        dets = det(img)
        rec = {"frame": fn, "goals": [d for d in dets if d["cls"].startswith("goal")],
               "robots": [d for d in dets if d["cls"] == "robot"]}
        cal = Calibrator(det)
        try:
            ok = cal.solve(img, dets, min_q=0.3)
        except Exception as e:
            ok = False
        if ok:
            rec["H"] = cal.H.tolist(); rec["q"] = cal.quality
            pts = goal_points(dets)
            proj = C.to_img(cal.H, C.GOAL_XY)
            rec["goal_agree"] = int(sum(np.min(np.linalg.norm(proj - [u, v], axis=1)) < 0.03 * img.shape[1] for u, v, _ in pts))
            for r in rec["robots"]:
                p = robot_floor_point(r["box"], cal.H, cal.cam)
                r["floor"] = [round(float(p[0])), round(float(p[1]))]
        f.write(json.dumps(rec) + "\n"); f.flush()
        if i % 50 == 0:
            print(i, len(names), f"{time.time()-t0:.0f}s", flush=True)
    f.close()

def accept(proposals, q_min=0.6, agree_min=5, r_min=0.5):
    goals, robots = {}, {}
    for line in open(proposals):
        r = json.loads(line)
        if r.get("H") and r.get("q", 0) >= q_min and r.get("goal_agree", 0) >= agree_min:
            goals[r["frame"]] = r["H"]
        rb = [x for x in r["robots"] if x["conf"] >= r_min]
        weak = [x for x in r["robots"] if 0.2 <= x["conf"] < r_min]
        if len(rb) == 4 and not weak and r.get("H") and all(np.abs(x.get("floor", [9e9, 9e9])).max() < F.HALF + 150 for x in rb):
            robots[r["frame"]] = [[round(v) for v in x["box"]] for x in rb]
    return goals, robots

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True); ap.add_argument("--list", required=True)
    ap.add_argument("--weights", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    propose(a.frames, json.load(open(a.list)), a.weights, a.out)
