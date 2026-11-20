"""Analyse one match: frames in, scouting data out.

Per frame (default 6 fps):
  overlay -> match name, clock, teams, running score (when shown)
  detector -> robots and goals
  calibration -> kept from the previous frame while the tape still fits;
                 re-solved from detected goals when the camera moves
  tracker -> four robot tracks in field mm
Every 0.5 s: goal stacks and Toggles are read; every 1 s: licence plates.
After the match: placement / Toggle events, final field state, a check
against the official score, credit per robot, team names on each track.
"""
import time
import numpy as np
import cv2
from . import field as F, calibrate as C, overlay, readers, track as T, teams as TM, events as E, reconcile as RC
from .detect import goal_points

ROBOT_HALF_DEPTH = 230.0     # mm from a robot's front bumper to its centre

class Calibrator:
    def __init__(self, detector, recheck_every=2.0, min_q=0.35):
        self.det = detector
        self.H = None
        self.cam = None
        self.last_check = -1e9
        self.recheck_every, self.min_q = recheck_every, min_q
        self.ref = None

    def solve(self, img, dets, min_q=0.4):
        """Calibrate from goal detections: try the best goal-to-layout matchings,
        snap each to the tape, keep the one the tape agrees with most."""
        pts = goal_points(dets)
        size = img.shape[1::-1]
        best = None
        for H, inl, fp, ip in C.goal_hypotheses(pts, size):
            Hs, _ = C.snap_to_tape(H, img, anchors=(np.array(fp), np.array(ip)) if len(fp) >= 4 else None)
            if not C.plausible(Hs, size):
                continue
            q = C.fit_quality(Hs, C.tape_mask(img, Hs))
            score = q + 0.02 * inl
            if best is None or score > best[0]:
                best = (score, q, Hs)
        if best is None or best[1] < min_q:
            return False
        H = best[2]
        self.H, self.cam, self.ref = H, C.camera_from_h(H, size), img.copy()
        self.quality = best[1]
        return True

    def update(self, t, img, dets):
        """True when self.H describes this frame. Every frame is checked against
        the tape, so a cut to a close-up or replay is caught right away; those
        frames return False and the tracks coast instead of jumping."""
        self.last_check = t
        if self.H is None:
            return self.solve(img, dets)
        q = C.fit_quality(self.H, C.tape_mask(img, self.H))
        if q >= self.min_q:
            self.quality = q
            return True
        Hb, cc = C.transfer(self.H, self.ref, img)       # camera panned or zoomed
        if Hb is not None and C.plausible(Hb, img.shape[1::-1]):
            qb = C.fit_quality(Hb, C.tape_mask(img, Hb))
            if qb >= self.min_q:
                self.H, self.cam, self.ref, self.quality = Hb, C.camera_from_h(Hb, img.shape[1::-1]), img.copy(), qb
                return True
        old = (self.H, self.cam, self.ref, getattr(self, "quality", None))
        if self.solve(img, dets):
            return True
        self.H, self.cam, self.ref, self.quality = old
        return False

def robot_floor_point(box, H, cam):
    x0, y0, x1, y1 = box
    p = C.to_field(H, [[(x0 + x1) / 2, y1]])[0]
    cxy = cam.position[:2]
    d = p - cxy
    n = np.linalg.norm(d)
    if n > 1:
        p = p + d / n * ROBOT_HALF_DEPTH
    return p

def read_plates(img, box):
    x0, y0, x1, y1 = [int(v) for v in box]
    h = y1 - y0
    crop = img[max(0, y0 + int(0.35 * h)):y1, max(0, x0):x1]
    if crop.size == 0 or crop.shape[0] < 12:
        return []
    crop = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    out = []
    for it in overlay.ocr(crop):
        for tok in __import__("re").findall(r"\d{1,5}[A-Z]", it["text"].upper().replace(" ", "")):
            out.append((tok, it["conf"]))
    return out

def analyze(frames, detector, teams=None, official=None, valid_teams=None, fps_hint=6, log=print,
            every_overlay=2.0, every_plate=2.0, every_read=1.0):
    """frames: iterable of (t, img). teams: {"red": [a, b], "blue": [c, d]} (from schedule or overlay)."""
    cal = Calibrator(detector)
    tracker = T.FourRobotTracker()
    goal_obs = {g.name: [] for g in F.GOALS}
    toggle_obs = {q: [] for q in F.TOGGLES}
    plates = {}
    running = []
    overlay_reads = []
    cal_log = []
    box_log = []; last_box = -1e9
    t_start = None
    last_read = -1e9; last_plate = -1e9; last_ov = -1e9
    n = 0
    t0w = time.time()
    for t, img in frames:
        n += 1
        if t - last_ov >= every_overlay:
            last_ov = t
            r = overlay.read(img, valid_teams)
            overlay_reads.append((t, r.as_dict()))
            if r.red_score is not None or r.blue_score is not None:
                running.append((t, r.red_score, r.blue_score))
            if teams is None and len(r.red) == 2 and len(r.blue) == 2:
                teams = {"red": r.red, "blue": r.blue}
            if t_start is None and r.period == "auton" and r.clock is not None:
                t_start = t - (15 - r.clock)
        dets = detector(img)
        if not cal.update(t, img, dets):
            continue
        H, cam = cal.H, cal.cam
        cal_log.append((round(t, 2), np.round(H, 8).tolist()))
        robots = [d for d in dets if d["cls"] == "robot"]
        pts = []
        for d in robots:
            p = robot_floor_point(d["box"], H, cam)
            if np.all(np.abs(p) < F.HALF + 200):
                pts.append((p[0], p[1], TM.colour_feature(img, d["box"])))
        kept = [d for d in robots if np.all(np.abs(robot_floor_point(d["box"], H, cam)) < F.HALF + 200)]
        assign = tracker.step(t, pts)
        if t - last_box >= 1.0 and assign:
            last_box = t
            box_log.append((round(t, 2), {tid: [round(v) for v in kept[j]["box"]] for tid, j in assign.items() if j is not None and j < len(kept)}))
        if tracker.tracks and t - last_plate >= every_plate:
            last_plate = t
            inv = {}
            for tid, j in assign.items():
                inv[j] = tid
            for j, d in enumerate(kept):          # indices match pts / assign
                if j in inv:
                    reads = read_plates(img, d["box"])
                    if reads:
                        plates.setdefault(inv[j], []).extend(reads)
        if t - last_read >= every_read:
            last_read = t
            for g in F.GOALS:
                c, _ = readers.read_stack(img, H, cam, g)
                goal_obs[g.name].append((t, c))
            for q in F.TOGGLES:
                col, share = readers.read_toggle(img, H, cam, q)
                toggle_obs[q].append((t, col))
    if not tracker.tracks:
        return {"error": "no calibration or robots found", "frames": n}
    if t_start is None:
        t_start = start_by_motion(tracker)
    t_end = t_start + 15 + 105 + 2 if t_start is not None else max(p[0] for tr in tracker.tracks for p in tr.history)
    paths = {tr.tid: tr.history for tr in tracker.tracks}
    alliances = {tr.tid: tr.alliance for tr in tracker.tracks}
    auton_end = (t_start or 0) + 15
    ev = E.placements(goal_obs, paths, alliances, auton_end=auton_end) + E.toggle_flips(toggle_obs, paths, alliances, auton_end=auton_end)
    ev.sort(key=lambda e: e["t"])
    state = E.final_state(goal_obs, toggle_obs, paths, alliances, t_end)
    report = RC.reconcile(ev, state, official, paths, alliances, running or None)
    cred = RC.credit(ev, state, alliances, report)
    names = {}
    if teams:
        for a in ("red", "blue"):
            tids = [tr.tid for tr in tracker.tracks if tr.alliance == a]
            if len(tids) == 2 and len(teams.get(a, [])) == 2:
                m, conf = TM.assign_alliance(tids, teams[a], plates)
                for tid, team in m.items():
                    names[tid] = {"team": team, "confidence": round(conf, 3)}
    robots_out = []
    for tr in tracker.tracks:
        st = T.path_stats(tr, t_start, t_end)
        au = T.path_stats(tr, t_start, auton_end)
        robots_out.append({
            "track": tr.tid, "alliance": tr.alliance, **names.get(tr.tid, {"team": None}),
            "points_seen": cred[tr.tid]["seen"], "points_inferred": cred[tr.tid]["inferred"],
            "placements": sum(1 for e in ev if e.get("robot") == tr.tid and e["type"] == "placement"),
            "toggles": sum(1 for e in ev if e.get("robot") == tr.tid and e["type"] == "toggle"),
            "ended_in_midfield": tr.tid in state["midfield_robots"],
            "auton_moved_ft": round(au.get("distance_ft", 0), 1),
            **{k: (round(v, 1) if isinstance(v, float) else v) for k, v in st.items()},
            "path": [(round(p[0] - (t_start or 0), 2), round(p[1]), round(p[2])) for p in tr.history[::2]],
        })
    for e in ev:
        if e.get("robot") is not None:
            e["team"] = names.get(e["robot"], {}).get("team")
        e["t"] = round(e["t"] - (t_start or 0), 2)
    return {"teams": teams, "t_start": t_start, "frames": n, "seconds_to_run": round(time.time() - t0w, 1),
            "robots": robots_out, "events": ev, "final_state": state, "score_check": report,
            "overlay": overlay_reads[-1][1] if overlay_reads else None,
            "cal_log": cal_log, "box_log": box_log, "raw_tracks": {tr.tid: [(round(p[0], 2), round(p[1]), round(p[2]), p[3]) for p in tr.history] for tr in tracker.tracks}}

def start_by_motion(tracker, thresh=150.0):
    """Auton start = first moment the robots, together, have moved > thresh mm from their spots."""
    hs = [tr.history for tr in tracker.tracks]
    if not hs or not hs[0]:
        return None
    ts = [p[0] for p in hs[0]]
    for i, t in enumerate(ts):
        moved = 0
        for h in hs:
            if i < len(h):
                moved += np.hypot(h[i][1] - h[0][1], h[i][2] - h[0][2])
        if moved > thresh * 2:
            # step back to the start of that movement
            return ts[max(0, i - 2)]
    return ts[0]
