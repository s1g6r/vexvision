// Override field model in millimetres, origin at the field centre, +y toward the
// top wall when the red Alliance Goals are bottom-left (VEX GPS convention).
// Mirrors vexvision/field.py.
export const TILE = 609.6, HALF = 3 * TILE, WALL = 1790;
export const MIDFIELD_R = TILE, AUTON_GAP = 25;
export const GOALS = [
  { name: "C", x: 0, y: 0, kind: "center", h: 222.7, q: "mid" },
  { name: "NW", x: -600, y: 1200, kind: "neutral", h: 146.5, q: "N" },
  { name: "NE", x: 600, y: 1200, kind: "blue", h: 82.5, q: "N" },
  { name: "EN", x: 1200, y: 600, kind: "blue", h: 82.5, q: "E" },
  { name: "ES", x: 1200, y: -600, kind: "neutral", h: 146.5, q: "E" },
  { name: "SE", x: 600, y: -1200, kind: "neutral", h: 146.5, q: "S" },
  { name: "SW", x: -600, y: -1200, kind: "red", h: 82.5, q: "S" },
  { name: "WS", x: -1200, y: -600, kind: "red", h: 82.5, q: "W" },
  { name: "WN", x: -1200, y: 600, kind: "neutral", h: 146.5, q: "W" },
];
export const TOGGLES = { N: [0, 1780], E: [1780, 0], S: [0, -1780], W: [-1780, 0] };
export const TOGGLE_LEN = 656.2;
export const QUADRANT_COLOR = { N: "blue", E: "blue", S: "red", W: "red" };
export const PTS = { allianceHalf: 5, ownedYellowHalf: 10, midfieldRobot: 8, autonBonus: 12 };

export function quadrantOf(x, y) {
  if (Math.abs(x) + Math.abs(y) <= MIDFIELD_R) return "mid";
  if (y >= Math.abs(x)) return "N";
  if (y <= -Math.abs(x)) return "S";
  return x > 0 ? "E" : "W";
}
export const sideOf = (x, y) => (x + y < 0 ? "red" : "blue");

export function tapeSegments(n = 40) {
  const segs = [], c = MIDFIELD_R / 2, lin = (a, b) => Array.from({ length: n }, (_, i) => a + (b - a) * i / (n - 1));
  for (const [a, b] of [[-WALL, -c], [c, WALL]]) segs.push(lin(a, b).map(t => [t, t]));
  for (const off of [-AUTON_GAP, AUTON_GAP]) {
    const d = off / Math.SQRT2;
    for (const [a, b] of [[-WALL, -c], [c, WALL]]) segs.push(lin(a, b).map(t => [t + d, -t + d]));
  }
  const r = MIDFIELD_R, dm = [[r, 0], [0, r], [-r, 0], [0, -r], [r, 0]];
  for (let i = 0; i < 4; i++) segs.push(lin(0, 1).map(t => [dm[i][0] + (dm[i + 1][0] - dm[i][0]) * t, dm[i][1] + (dm[i + 1][1] - dm[i][1]) * t]));
  return segs;
}

// Score one alliance. halves: {quadrant: {red, blue, yellow}}, toggles: {quadrant: colour}
export function allianceScore(halves, toggles, midOwner, robotsInMid, autonWinner, alliance) {
  let s = 0;
  for (const [q, h] of Object.entries(halves)) {
    s += PTS.allianceHalf * (h[alliance] || 0);
    const owner = q === "mid" ? midOwner : toggles[q];
    if (owner === alliance) s += PTS.ownedYellowHalf * (h.yellow || 0);
  }
  s += PTS.midfieldRobot * (robotsInMid[alliance] || 0);
  if (autonWinner === alliance) s += PTS.autonBonus;
  else if (autonWinner === "tie") s += PTS.autonBonus / 2;
  return s;
}
