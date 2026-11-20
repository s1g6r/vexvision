// Compare the browser calibration with the Python pipeline on real frames.
// usage: node calib.test.mjs proposals.jsonl frames_dir [n]
import fs from "fs";
import jpeg from "jpeg-js";
import * as C from "../js/calib.js";
import { apply, inv3 } from "../js/linalg.js";

const [, , propPath, framesDir, nArg] = process.argv;
const lines = fs.readFileSync(propPath, "utf8").trim().split("\n").map(l => JSON.parse(l)).filter(r => r.H && r.q >= 0.6);
const N = Math.min(+nArg || 25, lines.length);
const grid = []; for (let x = -1500; x <= 1500; x += 300) for (let y = -1500; y <= 1500; y += 300) grid.push([x, y]);
const errs = []; let failed = 0; let t0 = Date.now();
for (const r of lines.slice(0, N)) {
  const raw = jpeg.decode(fs.readFileSync(`${framesDir}/${r.frame}`), { useTArray: true });
  const W = raw.width, Hh = raw.height, s = 0.5, w = Math.round(W * s), h = Math.round(Hh * s);
  const small = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const si = (Math.floor(y / s) * W + Math.floor(x / s)) * 4, di = (y * w + x) * 4; for (let k = 0; k < 4; k++) small[di + k] = raw.data[si + k]; }
  const dets = r.goals.map(g => ({ box: g.box, conf: g.conf, kind: g.cls.replace("goal_", "") }));
  const pts = C.goalPoints(dets);
  let best = null;
  for (const hy of C.goalHypotheses(pts, W, Hh)) {
    const dt = C.distMap(C.tapeMask(small, w, h, hy.H, s), w, h);
    const sn = C.snapToTape(hy.H, dt, w, h, s);
    if (!C.plausible(sn.H, W, Hh)) continue;
    const score = sn.quality + 0.02 * hy.inl;
    if (!best || score > best.score) best = { ...sn, score };
  }
  if (!best || best.quality < 0.4) { failed++; continue; }
  const Hp = r.H, inv = inv3(best.H);
  const e = grid.map(([x, y]) => { const [u, v] = apply(Hp, x, y); const [X, Y] = apply(inv, u, v); return Math.hypot(X - x, Y - y) / 25.4; }).sort((a, b) => a - b);
  errs.push(e[Math.floor(e.length / 2)]);
}
errs.sort((a, b) => a - b);
console.log(`frames ${N}, JS failed ${failed}, median of per-frame median error vs Python: ${errs[Math.floor(errs.length / 2)]?.toFixed(2)} in, worst ${errs.at(-1)?.toFixed(1)} in, ${((Date.now() - t0) / N).toFixed(0)} ms/frame`);
const bad = errs.filter(e => e > 6).length;
if (failed > N * 0.2 || bad > N * 0.15) { console.error("FAIL"); process.exit(1); } else console.log("PASS");
