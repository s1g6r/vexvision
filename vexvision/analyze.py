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
    """Field calibration across a broadcast.

    Broadcasts cut between a few fixed wide cameras and close-ups or replays.
    A close-up has plenty of white lines, so a tape fit alone happily accepts
    a wrong calibration there. So a calibration is only *trusted* for a frame
    when the tape fits, most of the field's tape is in view, and the detected
    goals sit where it puts them. Trusted calibrations are kept in a small
    bank (one per camera); each frame first tries the bank, then a small pan
    from the best one, then a fresh solve. Frames that pass none of these are
    skipped and the robot tracks coast through them.
    """
    def __init__(self, detector, min_q=0.45, min_cov=0.55, min_agree=3, bank_size=4):
        self.det = detector
        self.H = None; self.cam = None; self.ref = None; self.quality = None
        self.min_q, self.min_cov, self.min_agree, self.bank_size = min_q, min_cov, min_agree, bank_size
        self.bank = []                               # [H, cam, ref, hits]

    def _trust(self, H, img, pts, need_agree):
        """Score H on this frame, or None when it can't be trusted. Goal agreement
        counts most: on light or purple-lit tiles the tape is faint and a tape fit
        alone is weak evidence either way."""
        size = img.shape[1::-1]
        if H is None or not C.plausible(H, size) or C.coverage(H, size) < self.min_cov:
            return None
        q = C.fit_quality(H, C.tape_mask(img, H))
        agree = C.goal_agreement(H, pts, size[0])
        if len(pts) >= 4:                            # enough goals in view to check against
            ok = (agree >= 4 and q >= 0.25) or (agree >= 3 and q >= self.min_q)
        else:                                        # goals hidden: only a known camera with a clear tape fit
            ok = not need_agree and q >= 0.55
        return (agree + q) if ok else None

    def _use(self, H, img, q, entry=None):
        size = img.shape[1::-1]
        if entry is None:
            entry = [H, C.camera_from_h(H, size), img.copy(), 0]
            self.bank.append(entry)
            if len(self.bank) > self.bank_size:
                self.bank.sort(key=lambda e: -e[3]); self.bank.pop()
        entry[3] += 1
        self.H, self.cam, self.ref, self.quality = entry[0], entry[1], entry[2], q
        return True

    def solve(self, img, dets, min_q=None):
        """Calibrate from goal detections: try the best goal-to-layout matchings,
        snap each to the tape, keep the one the tape agrees with most."""
        pts = goal_points(dets)
        size = img.shape[1::-1]
        best = None
        for H, inl, fp, ip in C.goal_hypotheses(pts, size):
            Hs, _ = C.snap_to_tape(H, img, anchors=(np.array(fp), np.array(ip)) if len(fp) >= 4 else None)
            q = self._trust(Hs, img, pts, need_agree=True)
            if q is None or (min_q is not None and q < min_q):
                continue
            score = q + 0.02 * inl          # q already includes goal agreement
            if best is None or score > best[0]:
                best = (score, q, Hs)
        if best is None:
            return False
        return self._use(best[2], img, best[1])

    def update(self, t, img, dets):
        """True when self.H describes this frame."""
        pts = goal_points(dets)
        cands = []
        for e in self.bank:                          # a fixed camera seen before
            q = self._trust(e[0], img, pts, need_agree=False)
            if q is not None:
                cands.append((q, e))
        if cands:
            q, e = max(cands, key=lambda c: c[0])
            return self._use(e[0], img, q, e)
        if self.bank:                                # the camera panned or zoomed a little
            e = max(self.bank, key=lambda e: e[3])
            Hb, _ = C.transfer(e[0], e[2], img)
            q = self._trust(Hb, img, pts, need_agree=True)
            if q is not None:
                return self._use(Hb, img, q)
        return self.solve(img, dets)

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
    det_log = []                       # per calibrated frame: (t, [[x, y, conf, x0, y0, x1, y1, colour], ...], [feat, ...])
    plate_log = []                     # (t, det index, [(text, conf), ...])
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
        rows, feats = [], []
        for d in robots:
            p = robot_floor_point(d["box"], H, cam)
            if np.all(np.abs(p) < F.HALF + 200):
                f = TM.colour_feature(img, d["box"])
                rows.append([round(float(p[0])), round(float(p[1])), round(d["conf"], 3)] + [round(v) for v in d["box"]]
                            + [round(TM.alliance_colour(img, d["box"]), 3)])
                feats.append(None if f is None else [round(float(v), 4) for v in f])
        det_log.append((round(t, 2), rows, feats))
        if t - last_plate >= every_plate:
            last_plate = t
            for j, r in enumerate(rows):
                reads = read_plates(img, r[3:7])
                if reads:
                    plate_log.append((round(t, 2), j, reads))
        if t - last_read >= every_read:
            last_read = t
            for g in F.GOALS:
                c, _ = readers.read_stack(img, H, cam, g)
                goal_obs[g.name].append((t, c))
            for q in F.TOGGLES:
                col, share = readers.read_toggle(img, H, cam, q)
                toggle_obs[q].append((t, col))
    perception = {"det_log": det_log, "plate_log": plate_log, "goal_obs": goal_obs, "toggle_obs": toggle_obs,
                  "running": running, "overlay_reads": overlay_reads, "teams": teams, "t_start": t_start,
                  "cal_log": cal_log, "frames": n, "seconds": round(time.time() - t0w, 1)}
    out = reason(perception, official=official)
    out["perception"] = perception
    return out

def run_tracker(det_log):
    tracker = T.FourRobotTracker()
    assigns = []
    cols = [r[7] for _, rows, _ in det_log for r in rows]
    mid = float(np.median(cols)) if cols else 0.0       # some fields and robots read redder overall
    for t, rows, feats in det_log:
        dets = [(r[0], r[1], None if f is None else np.asarray(f), r[7] - mid, r[2]) for r, f in zip(rows, feats)]
        assigns.append((t, tracker.step(t, dets)))
    repair_swaps(tracker, assigns, det_log, mid)
    return tracker, assigns

def repair_swaps(tracker, assigns, det_log, mid, near=700.0, z_min=5.0, max_swaps=6, log=None):
    """Second look at the whole match. When a red and a blue robot meet, the tracker
    can come away with them exchanged. Each alliance's robots read redder or bluer on
    average, so if after some meeting a red track has kept reading blue (and the blue
    track red), exchange the two from that meeting on."""
    if not tracker.tracks:
        return []
    by_t = {round(t, 2): i for i, (t, _) in enumerate(assigns)}
    rows = [r for _, r, _ in det_log]
    tr = tracker.tracks
    n = len(tr[0].history)
    if any(len(x.history) != n for x in tr):
        return []
    ts = [h[0] for h in tr[0].history]
    fi = [by_t.get(round(t, 2)) for t in ts]
    def col(k, i):                              # centred colour of what track k matched at history step i, or None
        f = fi[i]
        if f is None:
            return None
        j = assigns[f][1].get(tr[k].tid)
        return None if j is None else rows[f][j][7] - mid
    done = []
    for _ in range(max_swaps):
        best = None
        for a in range(len(tr)):
            for b in range(len(tr)):
                if tr[a].alliance != "red" or tr[b].alliance != "blue":
                    continue
                C = [(col(a, i), col(b, i)) for i in range(n)]
                # suffix sums of evidence for "a and b are exchanged from step i on"
                gain, cnt = np.zeros(n + 1), np.zeros(n + 1)
                for i in range(n - 1, -1, -1):
                    ca, cb = C[i]
                    g = 0.0; c = 0
                    if ca is not None: g -= ca; c += 1      # a is red: a blue-looking box is evidence of a swap
                    if cb is not None: g += cb; c += 1
                    gain[i] = gain[i + 1] + g; cnt[i] = cnt[i + 1] + c
                # a swap has to start where they met, and ends either where they met again or at the end
                E = [i for i in range(1, n - 5) if np.hypot(tr[a].history[i][1] - tr[b].history[i][1],
                                                             tr[a].history[i][2] - tr[b].history[i][2]) <= near]
                ends = E + [n]
                for i in E:
                    for j in ends:
                        if j <= i:
                            continue
                        c = cnt[i] - cnt[j]
                        if c < 20:
                            continue
                        z = (gain[i] - gain[j]) / (0.35 * np.sqrt(c))
                        if z > z_min and (best is None or z > best[0]):
                            best = (z, a, b, i, j)
        if best is None:
            break
        z, a, b, i, j = best
        A, B = tr[a], tr[b]
        A.history[i:j], B.history[i:j] = B.history[i:j], A.history[i:j]
        t_end = ts[j] if j < n else 1e18
        for f in range(len(assigns)):
            if ts[i] - 1e-6 <= assigns[f][0] < t_end - 1e-6:
                m = assigns[f][1]
                ja, jb = m.get(A.tid), m.get(B.tid)
                m.pop(A.tid, None); m.pop(B.tid, None)
                if jb is not None: m[A.tid] = jb
                if ja is not None: m[B.tid] = ja
        done.append((round(ts[i], 2), round(ts[j - 1], 2), A.tid, B.tid, round(float(z), 1)))
    tracker.swaps = done
    return done

def reason(P, official=None):
    """Everything after perception: tracking, team names, events, score check.
    Runs from a saved perception log in seconds, so the tracker can be improved
    without re-reading the video."""
    goal_obs, toggle_obs, running, teams, t_start = P["goal_obs"], P["toggle_obs"], P["running"] or [], P["teams"], P["t_start"]
    overlay_reads, cal_log, n, t0w = P["overlay_reads"], P["cal_log"], P["frames"], time.time()
    tracker, assigns = run_tracker(P["det_log"])
    rows_at = {round(t, 2): rows for t, rows, _ in P["det_log"]}
    who = {}                                       # (t, det index) -> tid
    box_log, last_box = [], -1e9
    for t, a in assigns:
        for tid, j in a.items():
            if j is not None:
                who[(round(t, 2), j)] = tid
        if t - last_box >= 1.0 and a:
            last_box = t
            box_log.append((round(t, 2), {tid: rows_at[round(t, 2)][j][3:7] for tid, j in a.items() if j is not None}))
    plates = {}
    for t, j, reads in P["plate_log"]:
        tid = who.get((round(t, 2), j))
        if tid is not None:
            plates.setdefault(tid, []).extend([tuple(r) for r in reads])
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
    return {"teams": teams, "t_start": t_start, "frames": n, "seconds_to_run": P.get("seconds"),
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
