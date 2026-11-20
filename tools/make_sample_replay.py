"""Write the website's sample replay: the end-to-end test match (scripted robots on a
real broadcast frame). It exercises every stage, but it is not a real match."""
import json, os, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vexvision import field as F, calibrate as C, analyze as AN
from tools.landmarks_to_labels import goal_box

def main(frame, calib, out):
    img = cv2.imread(frame)
    H = np.array(json.load(open(calib))[os.path.basename(frame)]["H"])
    cam = C.camera_from_h(H, (1280, 720))
    goals = [{"box": list(goal_box(cam, g, H)), "conf": 0.9, "cls": "goal_" + g.kind} for g in F.GOALS]
    # scripted drives: auton runs to goals, then driver period moves, two end in the Midfield
    way = [
        [(-1300, -400), (-800, -700), (-650, -1050), (-300, -300), (-200, -150)],
        [(-400, -1300), (-1000, -800), (-1150, -650), (-900, -200), (-1300, 300)],
        [(1300, 400), (900, 700), (700, 1100), (500, 400), (150, 200)],
        [(400, 1300), (1000, 900), (1150, 650), (1300, -300), (900, -900)],
    ]
    T = 60.0
    def pos(k, t):
        w = way[k]; u = min(0.999, t / T) * (len(w) - 1); i = int(u); f = u - i
        return w[i][0] + f * (w[i + 1][0] - w[i][0]), w[i][1] + f * (w[i + 1][1] - w[i][1])
    def rb(x, y):
        foot = C.to_img(H, [[x, y]])[0]
        top = cam.project([[x, y, 400]])[0] - cam.project([[x, y, 0]])[0] + foot
        return [foot[0] - 70, top[1], foot[0] + 70, foot[1]]
    class Scripted:
        t = 0.0
        def __call__(self, im):
            t = self.t; self.t += 1 / 6
            # boxes put the floor point at the robot centre; the analyser adds half a robot, so aim 230 mm nearer
            out = list(goals)
            for k in range(4):
                x, y = pos(k, t)
                d = np.array([x, y]) - cam.position[:2]; d /= np.linalg.norm(d)
                out.append({"box": rb(x - d[0] * 230, y - d[1] * 230), "conf": 0.9, "cls": "robot"})
            return out
    res = AN.analyze(((i / 6, img) for i in range(int(6 * T))), Scripted(),
                     teams={"red": ["1A", "2B"], "blue": ["3C", "4D"]})
    res["note"] = "Scripted test match on a real frame (MPt4G9oxWk8, Blank's Beginnings). Not a real match."
    json.dump(res, open(out, "w"), default=float)
    print("robots", [(r["team"], r["distance_ft"], r["ended_in_midfield"]) for r in res["robots"]])

if __name__ == "__main__":
    main(*sys.argv[1:4])
