import numpy as np
from vexvision import field as F, track as T, teams as TM, events as E, reconcile as R

def test_quadrants_and_sides():
    assert F.quadrant_of(0, 0) == "mid"
    assert F.quadrant_of(0, 1500) == "N" and F.quadrant_of(1500, 0) == "E"
    assert F.quadrant_of(0, -1500) == "S" and F.quadrant_of(-1500, 0) == "W"
    for g in F.GOALS:
        assert F.quadrant_of(g.x, g.y) == g.quadrant, g
        if g.kind in ("red", "blue"):
            assert F.side_of(g.x, g.y) == g.kind
            assert F.QUADRANT_COLOR[g.quadrant] == g.kind

def test_scoring():
    halves = {"N": {"red": 0, "blue": 2, "yellow": 2}, "S": {"red": 3, "blue": 0, "yellow": 1}, "mid": {"yellow": 1}}
    toggles = {"N": "red", "S": "red"}
    red = F.alliance_score(halves, toggles, "blue", {"red": 0, "blue": 1}, "red", "red")
    blue = F.alliance_score(halves, toggles, "blue", {"red": 0, "blue": 1}, "red", "blue")
    assert red == 3 * 5 + 2 * 10 + 1 * 10 + F.PTS_AUTON_BONUS
    assert blue == 2 * 5 + 1 * 10 + 8

def simulate(seed=0, n=300, dt=0.25, noise=40, miss=0.2):
    rng = np.random.default_rng(seed)
    starts = [(-1300, -300), (-300, -1300), (1300, 300), (300, 1300)]
    pos = np.array(starts, float); vel = rng.normal(0, 400, (4, 2))
    truth = []
    for k in range(n):
        vel += rng.normal(0, 250, (4, 2)) * dt
        vel = np.clip(vel, -1200, 1200)
        pos = np.clip(pos + vel * dt, -1700, 1700)
        truth.append(pos.copy())
    dets = []
    for k, p in enumerate(truth):
        d = [(x + rng.normal(0, noise), y + rng.normal(0, noise), None) for x, y in p if rng.random() > miss]
        if k == 0:
            d = [(x, y, None) for x, y in p]
        rng.shuffle(d)
        dets.append(d)
    return truth, dets, dt

def test_tracker_keeps_identities():
    truth, dets, dt = simulate()
    tr = T.FourRobotTracker()
    for k, d in enumerate(dets):
        tr.step(k * dt, d)
    assert len(tr.tracks) == 4
    # each track should stay closest to the same true robot
    errs = []
    for t_ in tr.tracks:
        h = np.array([[x, y] for _, x, y, _ in t_.history])
        own = np.argmin([np.linalg.norm(np.array(truth[0][i]) - h[0]) for i in range(4)])
        e = np.linalg.norm(h - np.array([p[own] for p in truth[: len(h)]]), axis=1)
        errs.append(np.median(e))
    assert max(errs) < 120, errs
    assert {t_.alliance for t_ in tr.tracks} == {"red", "blue"}

def test_team_assignment_from_plates():
    reads = {0: [("2I45X", 0.8), ("2145X", 0.6)], 1: []}
    a, conf = TM.assign_alliance([0, 1], ["10B", "2145X"], reads)
    assert a == {0: "2145X", 1: "10B"} and conf > 0.9

def test_placement_and_credit():
    paths = {0: [(t, -600 + 0 * t, -1050, True) for t in np.arange(0, 20, 0.25)],
             1: [(t, 1200, 1200, True) for t in np.arange(0, 20, 0.25)]}
    alliances = {0: "red", 1: "blue"}
    goal_obs = {"SW": [(t, {"red": 0 if t < 10 else 2, "blue": 0, "yellow": 0}) for t in np.arange(0, 20, 0.25)]}
    ev = E.placements(goal_obs, paths, alliances)
    assert len(ev) == 1 and ev[0]["robot"] == 0 and ev[0]["halves"] == 2
    state = E.final_state(goal_obs, {}, paths, alliances, 19.9)
    rep = R.reconcile(ev, state, {"red": 25, "blue": 0})
    assert rep["vision_score"]["red"] == 10 and rep["gap"]["red"] == 15
    cr = R.credit(ev, state, alliances, rep)
    assert cr[0]["seen"] == 10 and abs(cr[0]["inferred"] - 15) < 1e-6

def test_mirror_symmetry_and_canonical():
    """The field maps onto itself across y = x with every goal keeping its colour,
    so a calibration and its mirror draw the same; canonical() picks the real one."""
    from vexvision import calibrate as C
    mirror = {(g.y, g.x): g.kind for g in F.GOALS}
    for g in F.GOALS:
        assert mirror[(g.x, g.y)] == g.kind
    # a plausible camera view
    cam = C._look_at_camera(1100.0, np.radians(-90), np.radians(35), 5200.0, 0, 0, 0, (1280, 720))
    H = C.h_from_camera(cam)
    assert C.signed_area(H) < 0
    Hm = H @ C.MIRROR
    assert C.signed_area(Hm) > 0
    assert np.allclose(C.canonical(Hm), H)
    # goal pixels are the same set either way
    a = sorted(map(tuple, np.round(C.to_img(H, C.GOAL_XY), 3)))
    b = sorted(map(tuple, np.round(C.to_img(Hm, C.GOAL_XY), 3)))
    assert np.allclose(a, b)
