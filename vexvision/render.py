"""Draw a match as a top-down field map: robot paths, scoring events, final Toggles."""
import cv2
import numpy as np
from . import field as F

def field_canvas(px=720, margin=20):
    s = (px - 2 * margin) / (2 * F.HALF)
    img = np.full((px, px, 3), 235, np.uint8)
    def P(x, y):
        return int(margin + (x + F.HALF) * s), int(margin + (F.HALF - y) * s)
    cv2.rectangle(img, P(-F.HALF, F.HALF), P(F.HALF, -F.HALF), (90, 90, 90), 2)
    for i in range(-2, 3):
        cv2.line(img, P(i * F.TILE, -F.HALF), P(i * F.TILE, F.HALF), (215, 215, 215), 1)
        cv2.line(img, P(-F.HALF, i * F.TILE), P(F.HALF, i * F.TILE), (215, 215, 215), 1)
    for seg in F.tape_segments(10):
        cv2.polylines(img, [np.array([P(x, y) for x, y in seg], np.int32)], False, (255, 255, 255), 3)
    for g in F.GOALS:
        c = {"red": (60, 60, 220), "blue": (220, 120, 40), "neutral": (40, 40, 40), "center": (20, 20, 20)}[g.kind]
        cv2.circle(img, P(g.x, g.y), 9 if g.kind != "center" else 12, c, -1)
    return img, P

def render_match(result, path):
    img, P = field_canvas()
    for r in result["robots"]:
        col = (60, 60, 220) if r["alliance"] == "red" else (220, 120, 40)
        pts = np.array([P(x, y) for _, x, y in r["path"]], np.int32)
        if len(pts) > 1:
            cv2.polylines(img, [pts], False, col, 2, cv2.LINE_AA)
            cv2.circle(img, tuple(pts[0]), 6, col, 2)
            cv2.circle(img, tuple(pts[-1]), 6, col, -1)
            label = r.get("team") or f"#{r['track']}"
            cv2.putText(img, label, (pts[-1][0] + 8, pts[-1][1] - 6), 0, 0.55, (0, 0, 0), 3)
            cv2.putText(img, label, (pts[-1][0] + 8, pts[-1][1] - 6), 0, 0.55, col, 1)
    for e in result["events"]:
        if e["type"] == "placement":
            g = F.GOAL_BY_NAME[e["goal"]]
            cv2.circle(img, P(g.x, g.y), 16, (0, 200, 255), 1)
    for q, c in result["final_state"]["toggles"].items():
        x, y = F.TOGGLES[q]
        col = {"red": (60, 60, 220), "blue": (220, 120, 40), "yellow": (0, 210, 240)}.get(c, (120, 120, 120))
        d = np.array([1, 0]) if q in "NS" else np.array([0, 1])
        a = np.array([x, y]) - d * F.TOGGLE_LEN / 2; b = np.array([x, y]) + d * F.TOGGLE_LEN / 2
        cv2.line(img, P(*a), P(*b), col, 6)
    cv2.imwrite(path, img)
    return path
