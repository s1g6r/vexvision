"""The home page's opening frame: a hand-checked frame (hand-marked calibration and
hand-drawn robot boxes), so the first thing a visitor sees is right."""
import json, os, sys, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vexvision import calibrate as C, field as F, overlay
from vexvision.analyze import robot_floor_point

def main(frame_dir, fn, site):
    img = cv2.imread(os.path.join(frame_dir, fn)); h, w = img.shape[:2]
    H = np.array(json.load(open("data/calib_reference.json"))[fn]["H"])
    cam = C.camera_from_h(H, (w, h))
    boxes = json.load(open("data/robots.json"))[fn]
    ov = overlay.read(img)
    robots = []
    for b in boxes:
        p = robot_floor_point(b, H, cam)
        robots.append({"box": b, "floor": [round(float(p[0])), round(float(p[1]))], "side": F.side_of(*p)})
    goals = []
    for g in F.GOALS:
        u, v = C.to_img(H, [[g.x, g.y]])[0]
        goals.append({"name": g.name, "kind": g.kind, "uv": [round(float(u), 1), round(float(v), 1)]})
    os.makedirs(os.path.join(site, "data"), exist_ok=True)
    cv2.imwrite(os.path.join(site, "data", "hero.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    json.dump({"img": "data/hero.jpg", "w": w, "h": h, "H": H.tolist(), "robots": robots, "goals": goals,
               "match": ov.match, "red": ov.red, "blue": ov.blue, "event": "Great Planes Signature Event",
               "video": fn[:11], "overlay_x": 1088}, open(os.path.join(site, "data", "hero.json"), "w"))
    print(ov.match, ov.red, ov.blue, [r["side"] for r in robots])

if __name__ == "__main__":
    main(*sys.argv[1:4])
