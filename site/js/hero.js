// The opening sequence: a real broadcast frame, the tape traced, the robots tagged, then the
// same pixels laid flat onto the field using the frame's own homography. Scroll drives it.
import { WALL, tapeSegments, quadrantOf } from "./field.js";
const quadrant = f => quadrantOf(f[0], f[1]);
import * as C from "./calib.js";
import { homography } from "./linalg.js";

const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const span = (p, a, b) => clamp((p - a) / (b - a));
const ease = t => (t < .5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
const lerp = (a, b, t) => a + (b - a) * t;
const matrix3d = H => `matrix3d(${H[0][0]},${H[1][0]},0,${H[2][0]},${H[0][1]},${H[1][1]},0,${H[2][1]},0,0,1,0,${H[0][2]},${H[1][2]},0,${H[2][2]})`;
const NS = "http://www.w3.org/2000/svg";

function clipX(poly, xmax) {
  const out = [];
  for (let i = 0; i < poly.length; i++) {
    const a = poly[i], b = poly[(i + 1) % poly.length], ina = a[0] <= xmax, inb = b[0] <= xmax;
    if (ina) out.push(a);
    if (ina !== inb) { const t = (xmax - a[0]) / (b[0] - a[0]); out.push([xmax, a[1] + t * (b[1] - a[1])]); }
  }
  return out;
}

export function initHero(data, rotation, reduced) {
  const $ = s => document.querySelector(s);
  const hero = $("#hero"), world = $("#h-world"), warp = $("#h-warp"), full = $("#h-full"), img = $("#h-img");
  const over = $("#h-over"), top = $("#h-top"), copy = $("#h-copy"), bar = $("#h-bar"), hint = $("#h-hint");
  const phases = [...document.querySelectorAll("#h-phases li")];
  const { w, h, H } = data;
  full.src = img.src = data.img;
  for (const el of [world, warp]) { el.style.width = w + "px"; el.style.height = h + "px"; }
  over.setAttribute("viewBox", `0 0 ${w} ${h}`); top.setAttribute("viewBox", `0 0 ${w} ${h}`);

  // field outline in the frame, and the clip that keeps only the carpet once it starts to move
  const P0 = C.fieldPolygon(H);
  // keep only the carpet, and cut away the broadcast's score panel where it covers the field
  let clipPoly = C.fieldPolygon(H, -140);
  if (data.overlay_x) clipPoly = clipX(clipPoly, data.overlay_x);
  warp.style.clipPath = `polygon(${clipPoly.map(([u, v]) => `${u.toFixed(1)}px ${v.toFixed(1)}px`).join(",")})`;

  // where the field corners end up: a square, turned so the camera side is at the bottom
  const L = 0.86 * h, cx = w / 2, cy = h / 2, th = rotation * Math.PI / 180;
  const sq = ([fx, fy]) => { const x = fx / WALL, y = -fy / WALL; return [cx + (L / 2) * (x * Math.cos(th) - y * Math.sin(th)), cy + (L / 2) * (x * Math.sin(th) + y * Math.cos(th))]; };
  const Q = [[-WALL, -WALL], [WALL, -WALL], [WALL, WALL], [-WALL, WALL]].map(sq);

  // overlay drawn in frame pixels (it warps with the frame)
  let s = "";
  tapeSegments(30).forEach(seg => { const pts = C.toImg(H, seg); s += `<path class="trace" pathLength="1" stroke-width="5" d="M${pts.map(p => p.map(v => v.toFixed(1)).join(",")).join("L")}"/>`; });
  s += `<path class="trace" pathLength="1" stroke-width="6" d="M${[...P0, P0[0]].map(p => p.map(v => v.toFixed(1)).join(",")).join("L")}"/>`;
  data.goals.forEach(g => (s += `<circle class="goalpt" cx="${g.uv[0]}" cy="${g.uv[1]}" r="0"/>`));
  data.robots.forEach((r, i) => {
    const [x0, y0, x1, y1] = r.box;
    s += `<g class="rob" opacity="0"><rect class="rbox" x="${x0}" y="${y0}" width="${x1 - x0}" height="${y1 - y0}" rx="14"/><rect class="rtag" x="${x0}" y="${y0 - 40}" width="${i > 8 ? 72 : 46}" height="36" rx="12"/><text class="rtxt" x="${x0 + 13}" y="${y0 - 12}">${i + 1}</text></g>`;
  });
  over.innerHTML = s;
  const traces = [...over.querySelectorAll(".trace")], goalpts = [...over.querySelectorAll(".goalpt")], robs = [...over.querySelectorAll(".rob")];
  traces.forEach(t => { t.style.strokeDasharray = "1"; t.style.strokeDashoffset = "1"; });

  // tokens ride on the floor: each robot's floor point, pushed through the same warp
  const floorPx = data.robots.map(r => C.toImg(H, [r.floor])[0]);
  top.innerHTML = data.robots.map((r, i) => `<g class="tok" opacity="0"><circle class="ring" r="34"/><rect x="-24" y="-24" width="48" height="48" rx="14"/><text text-anchor="middle" y="12">${i + 1}</text></g>`).join("");
  const toks = [...top.querySelectorAll(".tok")];
  const end = document.querySelector("#h-end");
  if (end) {
    const q = r => ({ N: "North quadrant", E: "East quadrant", S: "South quadrant", W: "West quadrant", mid: "Midfield" })[quadrant(r.floor)];
    const inch = v => Math.abs(Math.round(v / 25.4));
    end.querySelector("ul").innerHTML = data.robots.map((r, i) => `<li><b>${i + 1}</b><span>${q(r)}<small>${inch(r.floor[0])} in ${r.floor[0] >= 0 ? "east" : "west"}, ${inch(r.floor[1])} in ${r.floor[1] >= 0 ? "north" : "south"} of centre</small></span></li>`).join("");
  }

  let vw = 0, vh = 0, fit0 = null, fit1 = null;
  function layout() {
    vw = innerWidth; vh = innerHeight;
    const portrait = vw < vh * 0.9;
    const s0 = portrait ? (1.75 * vw) / w : Math.max(vw / w, vh / h);
    const ctr = C.toImg(H, [[0, 0]])[0];
    fit0 = { s: s0, tx: vw / 2 - (portrait ? ctr[0] : w / 2) * s0, ty: vh / 2 - (portrait ? ctr[1] : h / 2) * s0 + (portrait ? vh * 0.12 : 0) };
    const side = Math.min(vw * (portrait ? 0.9 : 0.5), vh - (portrait ? 250 : 210));
    const s1 = side / L, centreX = portrait ? vw / 2 : vw * 0.6;
    fit1 = { s: s1, tx: centreX - cx * s1, ty: (portrait ? vh * 0.56 : vh / 2 + 28) - cy * s1 };
    frame();
  }

  let raf = 0, lastP = -1;
  function progress() {
    const r = hero.getBoundingClientRect(), total = hero.offsetHeight - vh;
    return clamp(-r.top / Math.max(1, total));
  }
  function frame() {
    raf = 0;
    const p = reduced ? 1 : progress();
    if (p === lastP && fit0) return;
    lastP = p;
    const k = ease(span(p, .5, .86));
    // camera: zoom from full-bleed frame to the field square
    const f = { s: lerp(fit0.s, fit1.s, k), tx: lerp(fit0.tx, fit1.tx, k), ty: lerp(fit0.ty, fit1.ty, k) };
    world.style.transform = `translate(${f.tx}px,${f.ty}px) scale(${f.s})`;
    // the floor itself: from camera view to top-down
    const Pk = P0.map((q, i) => [lerp(q[0], Q[i][0], k), lerp(q[1], Q[i][1], k)]);
    const G = homography(P0, Pk);
    warp.style.transform = matrix3d(G);
    full.style.opacity = String(1 - span(p, .44, .62));
    full.style.filter = `brightness(${1 - .45 * span(p, .08, .3)})`;
    // tape trace and goals
    const tp = span(p, .12, .32);
    traces.forEach((t, i) => (t.style.strokeDashoffset = String(1 - clamp(tp * 1.4 - i * .04))));
    goalpts.forEach((g, i) => g.setAttribute("r", String(9 * ease(span(p, .22 + i * .01, .3 + i * .01)) * (1 - span(p, .55, .7)))));
    // robot boxes appear, then hand over to the tokens as the floor tilts
    robs.forEach((g, i) => g.setAttribute("opacity", String(span(p, .32 + i * .025, .38 + i * .025) * (1 - span(p, .5, .6)))));
    toks.forEach((t, i) => {
      const [u, v] = floorPx[i], d = G[2][0] * u + G[2][1] * v + G[2][2];
      const x = (G[0][0] * u + G[0][1] * v + G[0][2]) / d, y = (G[1][0] * u + G[1][1] * v + G[1][2]) / d;
      t.setAttribute("transform", `translate(${x.toFixed(1)},${y.toFixed(1)}) scale(${(0.95 / f.s).toFixed(3)})`);
      t.setAttribute("opacity", String(span(p, .48, .56)));
      t.querySelector(".ring").setAttribute("opacity", String(span(p, .86, .92) * (1 - span(p, .92, 1)) || 0));
    });
    over.querySelectorAll(".trace").forEach(t => (t.style.opacity = String(1 - .55 * span(p, .55, .8))));
    // copy and captions
    copy.style.opacity = String(1 - span(p, .04, .12));
    copy.style.transform = `translateY(${-30 * span(p, .04, .12)}px)`;
    copy.style.pointerEvents = p > .1 ? "none" : "";
    hint.style.opacity = String(1 - span(p, 0, .04));
    const idx = p < .08 ? -1 : p < .2 ? 0 : p < .32 ? 1 : p < .48 ? 2 : p < .86 ? 3 : (vw < 700 ? 4 : -1);
    phases.forEach((li, i) => li.classList.toggle("on", i === idx));
    bar.style.width = (p * 100).toFixed(2) + "%";
    if (end) { const e = span(p, .86, .95); end.style.opacity = String(e); end.style.transform = `translateY(${(1 - e) * 16}px)`; }
  }
  const req = () => { if (!raf) raf = requestAnimationFrame(frame); };
  addEventListener("scroll", req, { passive: true });
  addEventListener("resize", layout);
  if (reduced) { hero.style.height = "100vh"; }
  img.decode?.().catch(() => {}).finally(layout);
  layout();
}
