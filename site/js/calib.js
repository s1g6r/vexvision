// Pixels <-> field millimetres for one broadcast frame. Port of vexvision/calibrate.py
// (goal hypotheses, mirror fix, tape scoring, in-plane tape snap, camera recovery).
import { GOALS, WALL, HALF, tapeSegments } from "./field.js";
import { apply, inv3, homography, matMul, cross, norm3 } from "./linalg.js";

export const GOAL_XY = GOALS.map(g => [g.x, g.y]);
const GOAL_KIND = GOALS.map(g => g.kind);
const MIRROR = [[0, 1, 0], [1, 0, 0], [0, 0, 1]];

export const toImg = (H, pts) => pts.map(p => apply(H, p[0], p[1]));
export const toField = (H, pts) => toImg(inv3(H), pts);
export const fieldPolygon = (H, m = 0) => toImg(H, [[-WALL + m, -WALL + m], [WALL - m, -WALL + m], [WALL - m, WALL - m], [-WALL + m, WALL - m]]);

export function signedArea(H) {
  const p = fieldPolygon(H);
  let s = 0;
  for (let i = 0; i < 4; i++) { const [x0, y0] = p[i], [x1, y1] = p[(i + 1) % 4]; s += x0 * y1 - x1 * y0; }
  return s / 2;
}
// The field is mirror-symmetric across its red/blue diagonal, so a goal match can
// come out mirrored: same picture, camera under the floor. Swap x and y back.
export const canonical = H => (signedArea(H) > 0 ? matMul(H, MIRROR) : H);

function convex(p) {
  let sign = 0;
  for (let i = 0; i < p.length; i++) {
    const a = p[i], b = p[(i + 1) % p.length], c = p[(i + 2) % p.length];
    const z = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]);
    if (Math.abs(z) < 1e-9) continue;
    if (sign && Math.sign(z) !== sign) return false;
    sign = Math.sign(z);
  }
  return true;
}
export function plausible(H, w, h) {
  const p = fieldPolygon(H);
  if (!p.every(q => Number.isFinite(q[0]) && Number.isFinite(q[1]))) return false;
  if (!convex(p)) return false;
  const area = Math.abs(signedArea(H));
  return area > 0.05 * w * h && area < 4 * w * h;
}

// Goal box -> estimated base centre on the floor.
export function goalPoints(dets) {
  const cap = { red: 2, blue: 2, neutral: 4, center: 1 }, out = [];
  for (const kind of Object.keys(cap)) {
    dets.filter(d => d.kind === kind).sort((a, b) => b.conf - a.conf).slice(0, cap[kind])
      .forEach(d => { const [x0, y0, x1, y1] = d.box; out.push([(x0 + x1) / 2, y1 - 0.22 * (y1 - y0), kind]); });
  }
  return out;
}

function* combinations(n, k, start = 0, acc = []) {
  if (acc.length === k) { yield acc.slice(); return; }
  for (let i = start; i < n; i++) { acc.push(i); yield* combinations(n, k, i + 1, acc); acc.pop(); }
}
function* product(lists, i = 0, acc = []) {
  if (i === lists.length) { yield acc.slice(); return; }
  for (const v of lists[i]) { acc.push(v); yield* product(lists, i + 1, acc); acc.pop(); }
}

export function goalHypotheses(pts, w, h, top = 8) {
  if (pts.length < 4) return [];
  const tol = 0.03 * w;
  const allowed = pts.map(p => GOAL_KIND.map(k => p[2] == null || p[2] === k));
  const hyps = [];
  for (const quad of combinations(pts.length, 4)) {
    const cand = quad.map(i => allowed[i].map((ok, j) => (ok ? j : -1)).filter(j => j >= 0));
    for (const perm of product(cand)) {
      if (new Set(perm).size < 4) continue;
      const Hc = homography(perm.map(j => GOAL_XY[j]), quad.map(i => [pts[i][0], pts[i][1]]));
      if (!Hc || !plausible(Hc, w, h)) continue;
      const proj = toImg(Hc, GOAL_XY);
      let inl = 0, err = 0;
      pts.forEach((p, i) => {
        let m = Infinity;
        proj.forEach((q, j) => { if (allowed[i][j]) m = Math.min(m, Math.hypot(q[0] - p[0], q[1] - p[1])); });
        if (m < tol) inl++;
        err += Math.min(m, tol);
      });
      if (inl >= 4) hyps.push({ inl, err, H: Hc });
    }
  }
  hyps.sort((a, b) => b.inl - a.inl || a.err - b.err);
  const out = [];
  for (const hy of hyps) {
    const proj = toImg(hy.H, GOAL_XY), fp = [], ip = [];
    pts.forEach((p, i) => {
      let best = -1, bd = Infinity;
      proj.forEach((q, j) => { const d = Math.hypot(q[0] - p[0], q[1] - p[1]); if (allowed[i][j] && d < bd) { bd = d; best = j; } });
      if (bd < tol) { fp.push(GOAL_XY[best]); ip.push([p[0], p[1]]); }
    });
    let H = fp.length >= 4 ? homography(fp, ip) || hy.H : hy.H;
    H = canonical(H);
    const poly = fieldPolygon(H);
    if (out.every(o => fieldPolygon(o.H).some((q, k) => Math.hypot(q[0] - poly[k][0], q[1] - poly[k][1]) > 15))) out.push({ H, inl: hy.inl, fp, ip });
    if (out.length >= top) break;
  }
  return out;
}

// ---- tape: white, thin, low-saturation lines on the tiles --------------------------
// Works on a downscaled frame (scale s) for speed.
export function tapeMask(img, w, h, H, s) {
  // img: Uint8ClampedArray RGBA of size w x h (already downscaled)
  const n = w * h, gray = new Float32Array(n), sat = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    const r = img[4 * i], g = img[4 * i + 1], b = img[4 * i + 2], mx = Math.max(r, g, b), mn = Math.min(r, g, b);
    gray[i] = 0.299 * r + 0.587 * g + 0.114 * b;
    sat[i] = mx ? (255 * (mx - mn)) / mx : 0;
  }
  // local background via box blur (integral image), radius ~ 8 px at full res
  const R = Math.max(2, Math.round(8 * s)), I = new Float64Array((w + 1) * (h + 1));
  for (let y = 0; y < h; y++) { let row = 0; for (let x = 0; x < w; x++) { row += gray[y * w + x]; I[(y + 1) * (w + 1) + x + 1] = I[y * (w + 1) + x + 1] + row; } }
  const mask = new Uint8Array(n);
  const poly = H ? fieldPolygon(H, 60).map(([u, v]) => [u * s, v * s]) : null;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const x0 = Math.max(0, x - R), x1 = Math.min(w, x + R + 1), y0 = Math.max(0, y - R), y1 = Math.min(h, y + R + 1);
    const mean = (I[y1 * (w + 1) + x1] - I[y0 * (w + 1) + x1] - I[y1 * (w + 1) + x0] + I[y0 * (w + 1) + x0]) / ((x1 - x0) * (y1 - y0));
    const i = y * w + x;
    if (gray[i] - mean > 26 && sat[i] < 60 && gray[i] > 120) mask[i] = 1;
  }
  if (poly) for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (mask[y * w + x] && !inPoly(poly, x, y)) mask[y * w + x] = 0;
  return mask;
}
function inPoly(p, x, y) {
  let c = false;
  for (let i = 0, j = p.length - 1; i < p.length; j = i++)
    if ((p[i][1] > y) !== (p[j][1] > y) && x < ((p[j][0] - p[i][0]) * (y - p[i][1])) / (p[j][1] - p[i][1]) + p[i][0]) c = !c;
  return c;
}
// Two-pass chamfer distance transform.
export function distMap(mask, w, h) {
  const INF = 1e6, d = new Float32Array(w * h);
  for (let i = 0; i < w * h; i++) d[i] = mask[i] ? 0 : INF;
  const a = 1, b = Math.SQRT2;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const i = y * w + x; let v = d[i];
    if (x > 0) v = Math.min(v, d[i - 1] + a);
    if (y > 0) { v = Math.min(v, d[i - w] + a); if (x > 0) v = Math.min(v, d[i - w - 1] + b); if (x < w - 1) v = Math.min(v, d[i - w + 1] + b); }
    d[i] = v;
  }
  for (let y = h - 1; y >= 0; y--) for (let x = w - 1; x >= 0; x--) {
    const i = y * w + x; let v = d[i];
    if (x < w - 1) v = Math.min(v, d[i + 1] + a);
    if (y < h - 1) { v = Math.min(v, d[i + w] + a); if (x < w - 1) v = Math.min(v, d[i + w + 1] + b); if (x > 0) v = Math.min(v, d[i + w - 1] + b); }
    d[i] = v;
  }
  return d;
}
const TAPE = (() => {
  const pts = [];
  for (const seg of tapeSegments(2)) {
    const [a, b] = [seg[0], seg[seg.length - 1]], L = Math.hypot(b[0] - a[0], b[1] - a[1]), n = Math.max(2, Math.round(L / 25));
    for (let i = 0; i < n; i++) pts.push([a[0] + (b[0] - a[0]) * i / (n - 1), a[1] + (b[1] - a[1]) * i / (n - 1)]);
  }
  return pts;
})();

function sampleD(dt, w, h, H, s, cap) {
  let sum = 0, ok = 0, near = 0;
  for (const p of TAPE) {
    const [u, v] = apply(H, p[0], p[1]), x = Math.round(u * s), y = Math.round(v * s);
    if (x < 0 || y < 0 || x >= w || y >= h) { sum += cap; continue; }
    const dd = Math.min(cap, dt[y * w + x] / s);
    sum += dd; ok++;
    if (dd <= 4) near++;
  }
  return { mean: sum / TAPE.length, quality: ok > 20 ? near / ok : 0 };
}
export const fitQuality = (dt, w, h, H, s) => sampleD(dt, w, h, H, s, 99).quality;

// Nudge H by a small similarity on the field plane so the model tape sits on the tape.
export function snapToTape(H0, dt, w, h, s) {
  const Hof = ([tx, ty, th, ls]) => { const c = Math.cos(th), sn = Math.sin(th), k = Math.exp(ls); return matMul(H0, [[k * c, -k * sn, tx], [k * sn, k * c, ty], [0, 0, 1]]); };
  const cost = (p, cap) => sampleD(dt, w, h, Hof(p), s, cap).mean + (p[0] ** 2 + p[1] ** 2) / 250 ** 2 * 3 + (p[2] / 0.1) ** 2 * 3 + (p[3] / 0.05) ** 2 * 3;
  let p = [0, 0, 0, 0];
  for (const [cap, step] of [[20, [60, 60, 0.03, 0.03]], [10, [25, 25, 0.012, 0.012]], [5, [8, 8, 0.004, 0.004]]]) p = nelderMead(q => cost(q, cap), p, step, 160);
  const q0 = fitQuality(dt, w, h, H0, s), H1 = Hof(p), q1 = fitQuality(dt, w, h, H1, s);
  const ok = q1 > q0 + 0.03 && Math.abs(Math.exp(p[3]) - 1) < 0.15 && Math.abs(p[2]) < 0.087 && Math.hypot(p[0], p[1]) < 250;
  return ok ? { H: H1, quality: q1 } : { H: H0, quality: q0 };
}
function nelderMead(f, x0, step, iters) {
  const n = x0.length;
  let pts = [x0, ...step.map((s, i) => x0.map((v, j) => (j === i ? v + s : v)))].map(x => ({ x, f: f(x) }));
  for (let it = 0; it < iters; it++) {
    pts.sort((a, b) => a.f - b.f);
    const c = Array(n).fill(0);
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) c[j] += pts[i].x[j] / n;
    const worst = pts[n], at = t => c.map((v, j) => v + t * (worst.x[j] - v));
    const r = at(-1), fr = f(r);
    if (fr < pts[0].f) { const e = at(-2), fe = f(e); pts[n] = fe < fr ? { x: e, f: fe } : { x: r, f: fr }; }
    else if (fr < pts[n - 1].f) pts[n] = { x: r, f: fr };
    else { const k = at(0.5), fk = f(k); if (fk < worst.f) pts[n] = { x: k, f: fk }; else pts = pts.map((p, i) => (i ? { x: p.x.map((v, j) => pts[0].x[j] + 0.5 * (v - pts[0].x[j])), f: 0 } : p)).map(p => ({ x: p.x, f: f(p.x) })); }
  }
  pts.sort((a, b) => a.f - b.f);
  return pts[0].x;
}

// ---- camera from H (square pixels, centred principal point) -----------------------
export function cameraFromH(H, w, h) {
  const cx = w / 2, cy = h / 2;
  const Hn = matMul([[1, 0, -cx], [0, 1, -cy], [0, 0, 1]], H);
  const h1 = [Hn[0][0], Hn[1][0], Hn[2][0]], h2 = [Hn[0][1], Hn[1][1], Hn[2][1]], h3 = [Hn[0][2], Hn[1][2], Hn[2][2]];
  const c = [];
  const den = h1[2] * h2[2]; if (Math.abs(den) > 1e-12) c.push(-(h1[0] * h2[0] + h1[1] * h2[1]) / den);
  const den2 = h1[2] ** 2 - h2[2] ** 2; if (Math.abs(den2) > 1e-12) c.push((h2[0] ** 2 + h2[1] ** 2 - h1[0] ** 2 - h1[1] ** 2) / den2);
  const good = c.filter(v => Number.isFinite(v) && v > 0).sort((a, b) => a - b);
  const f = good.length ? Math.sqrt(good[Math.floor(good.length / 2)]) : 1.2 * w;
  const Kinv = (v) => [v[0] / f, v[1] / f, v[2]];
  let r1 = Kinv(h1), r2 = Kinv(h2), t = Kinv(h3);
  const lam = 1 / norm3(r1);
  r1 = r1.map(v => v * lam); r2 = r2.map(v => v * lam); t = t.map(v => v * lam);
  if (t[2] < 0) { r1 = r1.map(v => -v); r2 = r2.map(v => -v); t = t.map(v => -v); }
  const r3 = cross(r1, r2);
  const R = [[r1[0], r2[0], r3[0]], [r1[1], r2[1], r3[1]], [r1[2], r2[2], r3[2]]];
  // camera position = -R^T t
  const pos = [0, 1, 2].map(i => -(R[0][i] * t[0] + R[1][i] * t[1] + R[2][i] * t[2]));
  const project = (X, Y, Z) => {
    const cxyz = [0, 1, 2].map(i => R[i][0] * X + R[i][1] * Y + R[i][2] * Z + t[i]);
    return [f * cxyz[0] / cxyz[2] + cx, f * cxyz[1] / cxyz[2] + cy];
  };
  return { f, pos, project };
}

// Where a robot stands: bottom-centre of its box on the floor, pushed back half a robot
// away from the camera (the box bottom is the robot's near bumper).
export function robotFloor(box, H, cam) {
  const [x0, , x1, y1] = box;
  let [x, y] = toField(H, [[(x0 + x1) / 2, y1]])[0];
  const dx = x - cam.pos[0], dy = y - cam.pos[1], n = Math.hypot(dx, dy);
  if (n > 1) { x += (dx / n) * 230; y += (dy / n) * 230; }
  return [x, y];
}

export const inField = (x, y) => Math.abs(x) < HALF + 200 && Math.abs(y) < HALF + 200;
