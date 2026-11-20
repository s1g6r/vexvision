"""The Override field, in millimetres, origin at field centre.

Axes follow the VEX GPS convention used in the official VEXcode VR Override
playground: +x to the right, +y up (towards the top wall) when the field is
drawn with the red Alliance Goals in the bottom-left. Goal and Toggle positions
are the published GPS coordinates; they sit on the 24" tile grid.

Layout facts used here (Override game manual glossary):
- 9 Goals: 1 tall neutral Center Goal, 4 short neutral Quadrant Goals,
  2 red and 2 blue Alliance Goals.
- 4 triangular Quadrants, split by the two white diagonals. Each holds two
  Goals and one Toggle, and is red or blue after its Alliance Goal.
- The Autonomous Line is the pair of white lines running along the red/blue
  diagonal (y = -x here) and around the Midfield.
- The Midfield is the centre square outlined by white tape. On the field it
  is a diamond: corners one tile (24") from centre along the axes, so a point
  is in the Midfield when |x| + |y| <= one tile. Measured from a calibrated
  top-down warp of a real broadcast frame (Speedway Signature, Qual 165).
"""
from dataclasses import dataclass
import numpy as np

TILE = 609.6                    # 24 in
HALF = 3 * TILE                 # 1828.8: half the 12 ft field (tile edge)
WALL = 1790.0                   # inner face of the perimeter (approx.)

@dataclass(frozen=True)
class Goal:
    name: str
    x: float
    y: float
    kind: str        # "center" | "neutral" | "red" | "blue"
    height: float    # mm, base height above the tiles
    quadrant: str    # "N" | "E" | "S" | "W" | "mid"

GOALS = [
    Goal("C",  0, 0, "center", 222.7, "mid"),
    Goal("NW", -600, 1200, "neutral", 146.5, "N"),
    Goal("NE", 600, 1200, "blue", 82.5, "N"),
    Goal("EN", 1200, 600, "blue", 82.5, "E"),
    Goal("ES", 1200, -600, "neutral", 146.5, "E"),
    Goal("SE", 600, -1200, "neutral", 146.5, "S"),
    Goal("SW", -600, -1200, "red", 82.5, "S"),
    Goal("WS", -1200, -600, "red", 82.5, "W"),
    Goal("WN", -1200, 600, "neutral", 146.5, "W"),
]
GOAL_BY_NAME = {g.name: g for g in GOALS}
GOAL_RADIUS = 75.0              # octagonal base, approx. half-width (mm)

# Toggle centres, one per wall. Each Toggle owns its Quadrant's yellow pins.
TOGGLES = {"N": (0.0, 1780.0), "E": (1780.0, 0.0), "S": (0.0, -1780.0), "W": (-1780.0, 0.0)}
TOGGLE_LEN = 656.2

QUADRANT_COLOR = {"N": "blue", "E": "blue", "S": "red", "W": "red"}

# Midfield and Autonomous Line tape, measured from calibrated frames because
# the manual's Appendix A drawings were not available.
MIDFIELD_R = TILE               # Midfield diamond: |x| + |y| <= MIDFIELD_R
AUTON_GAP = 25.0                # half-gap between the two Autonomous Line tapes (measured ~50 mm apart)

def quadrant_of(x, y):
    """Which Quadrant (or the Midfield) a field point is in."""
    if abs(x) + abs(y) <= MIDFIELD_R:
        return "mid"
    if y >= abs(x):
        return "N"
    if y <= -abs(x):
        return "S"
    return "E" if x > 0 else "W"

def side_of(x, y):
    """Which alliance's side of the Autonomous Line (y = -x) a point is on."""
    return "red" if x + y < 0 else "blue"

def tape_segments(n=60):
    """White tape centre-lines as a list of (N,2) polylines in field mm."""
    segs = []
    c = MIDFIELD_R / 2              # where a diagonal meets the Midfield diamond
    # Quadrant diagonal y = x (single tape), corner to Midfield on each side.
    for a, b in ((-WALL, -c), (c, WALL)):
        t = np.linspace(a, b, n)
        segs.append(np.stack([t, t], 1))
    # Autonomous Line: a pair of tapes along y = -x.
    for off in (-AUTON_GAP, AUTON_GAP):
        d = off / np.sqrt(2)
        for a, b in ((-WALL, -c), (c, WALL)):
            t = np.linspace(a, b, n)
            segs.append(np.stack([t + d, -t + d], 1))
    # Midfield diamond.
    r = MIDFIELD_R
    dm = np.array([[r, 0], [0, r], [-r, 0], [0, -r], [r, 0]])
    for i in range(4):
        segs.append(np.linspace(dm[i], dm[i + 1], n))
    return segs

def wall_outline():
    w = WALL
    return np.array([[-w, -w], [w, -w], [w, w], [-w, w]], float)

# ---- scoring (Override) -------------------------------------------------
# Point values from the official game page. The autonomous bonus has been
# listed as both 10 and 12 in different VEX documents; reconcile.py checks
# which one official scores agree with.
PTS_ALLIANCE_HALF = 5
PTS_OWNED_YELLOW_HALF = 10
PTS_MIDFIELD_ROBOT = 8
PTS_AUTON_BONUS = 12

def alliance_score(halves_by_quadrant, toggles, mid_yellow_owner, robots_in_mid, auton_winner, alliance,
                   auton_bonus=PTS_AUTON_BONUS):
    """Score for one alliance from a field state.

    halves_by_quadrant: {quadrant: {"red": n, "blue": n, "yellow": n}} scored pin halves
    toggles: {quadrant: "red" | "blue" | "yellow"}
    mid_yellow_owner: "red" | "blue" | None
    robots_in_mid: {"red": n, "blue": n}
    auton_winner: "red" | "blue" | "tie" | None
    """
    s = 0
    for q, h in halves_by_quadrant.items():
        s += PTS_ALLIANCE_HALF * h.get(alliance, 0)
        owner = mid_yellow_owner if q == "mid" else toggles.get(q)
        if owner == alliance:
            s += PTS_OWNED_YELLOW_HALF * h.get("yellow", 0)
    s += PTS_MIDFIELD_ROBOT * robots_in_mid.get(alliance, 0)
    if auton_winner == alliance:
        s += auton_bonus
    elif auton_winner == "tie":
        s += auton_bonus // 2
    return s

# ---- floor landmarks for calibration ---------------------------------------
# Points on the tiles that can be marked in a frame (or found by a detector).
def landmarks():
    r, c, w = MIDFIELD_R, MIDFIELD_R / 2, WALL
    pts = {g.name: (g.x, g.y) for g in GOALS}
    pts.update({
        "D_E": (r, 0), "D_N": (0, r), "D_W": (-r, 0), "D_S": (0, -r),        # Midfield diamond corners
        "J_NE": (c, c), "J_SW": (-c, -c), "J_NW": (-c, c), "J_SE": (c, -c),  # diagonals meet the diamond
        "K_NE": (w, w), "K_NW": (-w, w), "K_SE": (w, -w), "K_SW": (-w, -w),  # floor corners at the walls
    })
    return pts
LANDMARKS = landmarks()
