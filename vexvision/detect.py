"""YOLO detector wrapper. Classes: goal_red, goal_blue, goal_neutral, goal_center, robot."""
import numpy as np

GOAL_KIND = {"goal_red": "red", "goal_blue": "blue", "goal_neutral": "neutral", "goal_center": "center"}

class Detector:
    """One or more YOLO models (e.g. a goal model and a robot model) run as one detector."""
    def __init__(self, weights, imgsz=960, conf=0.25, device=None):
        from ultralytics import YOLO
        ws = weights if isinstance(weights, (list, tuple)) else [w for w in str(weights).split(",") if w]
        self.models = [YOLO(w) for w in ws]
        self.imgsz, self.conf, self.device = imgsz, conf, device

    def __call__(self, img):
        out = []
        for m in self.models:
            r = m.predict(img, imgsz=self.imgsz, conf=self.conf, verbose=False, device=self.device)[0]
            for b, c, k in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy(), r.boxes.cls.cpu().numpy()):
                out.append({"box": b.tolist(), "conf": float(c), "cls": m.names[int(k)]})
        return out

def goal_points(dets):
    """Goal boxes -> (u, v, kind) estimates of the base centre on the floor."""
    pts = []
    for d in dets:
        kind = GOAL_KIND.get(d["cls"])
        if not kind:
            continue
        x0, y0, x1, y1 = d["box"]
        pts.append(((x0 + x1) / 2, y1 - 0.22 * (y1 - y0), kind, d["conf"]))
    # keep the most confident few of each kind (there are at most 2 red, 2 blue, 4 neutral, 1 centre)
    cap = {"red": 2, "blue": 2, "neutral": 4, "center": 1}
    out = []
    for kind, n in cap.items():
        ks = sorted([p for p in pts if p[2] == kind], key=lambda p: -p[3])[:n]
        out += [(u, v, k) for u, v, k, _ in ks]
    return out
