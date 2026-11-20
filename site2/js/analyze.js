// "Try your own screenshot": find goals and robots with the ONNX models, line the
// field up from the goals and the white tape, then return a frame the 3D view can
// stand in (camera pose in three.js metres) with the robots placed on the floor.
import * as C from "./ml/calib.js";
import { loadModel, detect } from "./ml/detect.js";
import * as THREE from "./vendor/three.module.js";

let models = null;
async function getModels(status) {
  if (models) return models;
  status("Loading the models, about 29 MB the first time…");
  const [goals, robots] = await Promise.all([
    loadModel("models/goals.json", ["goal_red", "goal_blue", "goal_neutral", "goal_center"]),
    loadModel("models/robots.json", ["robot"]),
  ]);
  return (models = { goals, robots });
}

function calibrate(im, w, h, goalsDet) {
  const pts = C.goalPoints(goalsDet.map((d) => ({ ...d, kind: d.cls.replace("goal_", "") })));
  const hyps = C.goalHypotheses(pts, w, h);
  if (!hyps.length) return null;
  const s = Math.min(1, 640 / w), sw = Math.round(w * s), sh = Math.round(h * s);
  const c = document.createElement("canvas"); c.width = sw; c.height = sh;
  const g = c.getContext("2d"); g.drawImage(im, 0, 0, sw, sh);
  const px = g.getImageData(0, 0, sw, sh).data;
  let best = null;
  for (const hy of hyps) {
    const dt = C.distMap(C.tapeMask(px, sw, sh, hy.H, s), sw, sh);
    const sn = C.snapToTape(hy.H, dt, sw, sh, s);
    if (!C.plausible(sn.H, w, h)) continue;
    const score = sn.quality + 0.02 * hy.inl;
    if (!best || score > best.score) best = { ...sn, score };
  }
  return best && best.quality >= 0.35 ? best : null;
}

// field (mm, z up) camera -> three.js pose, same convention as tools/build_site2_data.py
function pose(cam) {
  const { R } = cam;                                   // rows: camera axes in field coords
  const M = [[1, 0, 0], [0, 0, 1], [0, -1, 0]];
  const Rt = [0, 1, 2].map((i) => [0, 1, 2].map((j) => R[j][i]));   // R^T
  const D = [1, -1, -1];
  const R3 = M.map((mr) => [0, 1, 2].map((j) => D[j] * (mr[0] * Rt[0][j] + mr[1] * Rt[1][j] + mr[2] * Rt[2][j])));
  const m4 = new THREE.Matrix4().set(R3[0][0], R3[0][1], R3[0][2], 0, R3[1][0], R3[1][1], R3[1][2], 0, R3[2][0], R3[2][1], R3[2][2], 0, 0, 0, 0, 1);
  const q = new THREE.Quaternion().setFromRotationMatrix(m4);
  const p = cam.pos;
  return { pos: [p[0] / 1000, p[2] / 1000, -p[1] / 1000], quat: [q.x, q.y, q.z, q.w] };
}

function plateSide(im, box, w, h) {                     // red or blue plates in the lower half of the box
  const [x0, y0, x1, y1] = box.map(Math.round), bw = Math.max(1, x1 - x0), bh = Math.max(1, y1 - y0);
  const c = document.createElement("canvas"); c.width = 48; c.height = 24;
  const g = c.getContext("2d"); g.drawImage(im, x0, y0 + bh * 0.4, bw, bh * 0.6, 0, 0, 48, 24);
  const d = g.getImageData(0, 0, 48, 24).data; let red = 0, blue = 0;
  for (let i = 0; i < d.length; i += 4) {
    const r = d[i], gg = d[i + 1], b = d[i + 2];
    if (r > 140 && r > gg + 60 && r > b + 60) red++;
    if (b > 120 && b > r + 50 && b > gg + 20) blue++;
  }
  const n = 48 * 24;
  if (Math.max(red, blue) < 0.01 * n || Math.abs(red - blue) < 0.3 * Math.max(red, blue)) return null;
  return red > blue ? "red" : "blue";
}

export async function analyzeImage(file, status) {
  const url = URL.createObjectURL(file), im = new Image();
  im.src = url; await im.decode();
  const w = im.naturalWidth, h = im.naturalHeight;
  const m = await getModels(status);
  status("Looking for the goals and robots…");
  const t0 = performance.now();
  const goalsDet = await detect(m.goals, im, w, h, 0.1);
  const robotsDet = await detect(m.robots, im, w, h, 0.35);
  status("Lining up the field…");
  await new Promise((r) => setTimeout(r, 0));
  const cal = calibrate(im, w, h, goalsDet);
  if (!cal) return { error: "Couldn't line up the field in that shot. Try a wider broadcast frame that shows most of the field.", url, w, h };
  const cam = C.cameraFromH(cal.H, w, h);
  let robots = robotsDet.map((r) => ({ ...r, floor: C.robotFloor(r.box, cal.H, cam) })).filter((r) => C.inField(...r.floor));
  robots.sort((a, b) => b.conf - a.conf);
  robots = robots.slice(0, 4).map((r) => ({ x: r.floor[0] / 1000, y: r.floor[1] / 1000, box: r.box, side: plateSide(im, r.box, w, h) }));
  return { img: url, w, h, f: cam.f, ...pose(cam), robots, red: [], blue: [], match: "Your screenshot", event: `read in ${((performance.now() - t0) / 1000).toFixed(1)} s`, clock: null, mine: true };
}
