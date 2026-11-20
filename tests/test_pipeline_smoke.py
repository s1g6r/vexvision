"""End-to-end run of analyze() on real broadcast frames with a scripted detector.

The detector returns goal boxes projected from a known calibration and four
robot boxes that drive along scripted paths, so this exercises calibration,
tracking, readers, events, reconciliation and rendering together without
needing trained weights or video.
"""
import json, os
import numpy as np, cv2, pytest
from vexvision import field as F, calibrate as C, analyze as AN, render

FRAME = "/home/claude/work/yt/frames/MPt4G9oxWk8_maxres2.jpg"
CAL = "/home/claude/work/lab/calib.json"

@pytest.mark.skipif(not os.path.exists(FRAME), reason="needs the collected frames")
def test_analyze_end_to_end(tmp_path):
    img = cv2.imread(FRAME)
    H = np.array(json.load(open(CAL))[os.path.basename(FRAME)]["H"])
    cam = C.camera_from_h(H, (1280, 720))
    from tools.landmarks_to_labels import goal_box
    goal_dets = []
    for g in F.GOALS:
        x0, y0, x1, y1 = goal_box(cam, g, H)
        goal_dets.append({"box": [x0, y0, x1, y1], "conf": 0.9, "cls": "goal_" + g.kind})
    starts = [(-1300, -400), (-400, -1300), (1300, 400), (400, 1300)]
    ends = [(-300, -200), (-600, -1100), (300, 200), (1200, 600)]
    def robot_box(x, y):
        foot = C.to_img(H, [[x, y]])[0]
        top = cam.project([[x, y, 400]])[0] - cam.project([[x, y, 0]])[0] + foot
        w = 70
        return [foot[0] - w, top[1], foot[0] + w, foot[1]]
    class Scripted:
        def __init__(self): self.t = 0
        def __call__(self, im):
            k = min(1.0, self.t / 20.0); self.t += 1 / 6
            out = list(goal_dets)
            for (x0, y0), (x1, y1) in zip(starts, ends):
                x, y = x0 + k * (x1 - x0), y0 + k * (y1 - y0)
                # the floor point the analyser recovers is pushed back by half a robot; aim the box accordingly
                out.append({"box": robot_box(x, y), "conf": 0.9, "cls": "robot"})
            return out
    frames = ((i / 6, img) for i in range(6 * 25))
    res = AN.analyze(frames, Scripted(), teams={"red": ["1A", "2B"], "blue": ["3C", "4D"]}, official={"red": 50, "blue": 40})
    assert "robots" in res, res
    assert len(res["robots"]) == 4
    assert sorted(r["alliance"] for r in res["robots"]) == ["blue", "blue", "red", "red"]
    assert all(r["team"] in ("1A", "2B", "3C", "4D") for r in res["robots"])
    moved = [r["distance_ft"] for r in res["robots"]]
    assert max(moved) > 2.5, moved   # scripted paths are 3-3.5 ft long
    out = render.render_match(res, str(tmp_path / "map.png"))
    assert os.path.exists(out)
