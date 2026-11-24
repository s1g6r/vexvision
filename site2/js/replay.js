// Full-match replay: the tracked robots drive around the 3D field in time with
// the broadcast, which plays as stills in the corner with the same robots marked.
import { createField } from "./field3d.js";

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const mmss = (s) => { s = Math.max(0, Math.round(s)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
const AUTON = 15;

function sample(path, t) {                          // binary search + linear interpolation
  let lo = 0, hi = path.length - 1;
  if (t <= path[0][0]) return path[0];
  if (t >= path[hi][0]) return path[hi];
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (path[m][0] <= t) lo = m; else hi = m; }
  const a = path[lo], b = path[hi], k = (t - a[0]) / (b[0] - a[0] || 1);
  let dh = b[3] - a[3]; if (dh > Math.PI) dh -= 2 * Math.PI; if (dh < -Math.PI) dh += 2 * Math.PI;
  return [t, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k, a[3] + dh * k, k < 0.5 ? a[4] : b[4]];
}
function camAt(cams, t) {
  let best = cams[0];
  for (const c of cams) { if (c[0] <= t) best = c; else break; }
  return best;
}
const zoneName = (x, y) => Math.abs(x) + Math.abs(y) <= 0.6096 ? "Midfield" : (x + y < 0 ? "Red side" : "Blue side");

const PACKS = new Map();
async function loadData(url) {
  const [file, id] = url.split("#");
  if (!id) return fetch(file).then((r) => r.json());
  if (!PACKS.has(file)) PACKS.set(file, fetch(file).then((r) => r.json()));
  return (await PACKS.get(file))[id];
}

export async function mountReplay(root, url, { reduced = false, autoplay = false, start = null, names = {} } = {}) {
  const R = await loadData(url);
  root.dispatchEvent(new CustomEvent("replay-meta", { detail: R, bubbles: true }));
  const $ = (s) => root.querySelector(s);
  const canvas = $("canvas"), labels = $(".rp-labels"), pip = $(".rp-pip .rp-still"), pipMarks = $(".rp-pip .rp-pipmarks");
  const F = createField(canvas, { twin: true });
  const { THREE } = F;
  // A robot is shown by team number only once we know which of the alliance's two
  // it is. Otherwise it is "Red 1" / "Red 2" and its card names both possibilities.
  const robots = R.robots.map((r) => ({ ...r, side: r.alliance, named: r.named !== false && !!r.team }));
  const idx = { red: 0, blue: 0 };
  for (const r of robots) {
    const n = ++idx[r.side];
    const pair = (R[r.side] || []).filter(Boolean);
    r.label = r.named ? r.team : `${r.side === "red" ? "Red" : "Blue"} ${n}`;
    r.maybe = r.named ? null : pair.length === 2 ? pair : null;
  }
  F.setRobots(robots.map((r) => ({ x: r.path[0][1], y: r.path[0][2], side: r.side, team: r.named ? r.team : "" })));
  const meshes = F.robots.children;

  // trails: a fading ribbon over the last few seconds of each path
  const TRAIL = 5, N = 60;
  const trails = robots.map((r) => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(N * 2 * 3), 3));
    g.setAttribute("color", new THREE.BufferAttribute(new Float32Array(N * 2 * 4), 4));
    const idx = []; for (let i = 0; i < N - 1; i++) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
    g.setIndex(idx);
    const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, depthWrite: false, side: THREE.DoubleSide }));
    m.renderOrder = 2; m.frustumCulled = false; F.world.add(m);
    return { g, col: new THREE.Color(r.side === "red" ? 0xff4550 : 0x4c86ff) };
  });
  function drawTrails(t) {
    robots.forEach((r, i) => {
      const { g, col } = trails[i], P = g.attributes.position.array, C = g.attributes.color.array;
      for (let k = 0; k < N; k++) {
        const tk = t - TRAIL + (TRAIL * k) / (N - 1);
        const p = sample(r.path, Math.max(r.path[0][0], tk)), q = sample(r.path, Math.max(r.path[0][0], tk + 0.05));
        let dx = q[1] - p[1], dy = q[2] - p[2]; const n = Math.hypot(dx, dy) || 1; dx /= n; dy /= n;
        const w = 0.012 + 0.03 * (k / (N - 1));
        for (const s of [-1, 1]) {
          const j = (k * 2 + (s > 0 ? 1 : 0));
          P[j * 3] = p[1] - dy * w * s; P[j * 3 + 1] = 0.006; P[j * 3 + 2] = -(p[2] + dx * w * s);
          C[j * 4] = col.r; C[j * 4 + 1] = col.g; C[j * 4 + 2] = col.b; C[j * 4 + 3] = tk < r.path[0][0] ? 0 : Math.pow(k / (N - 1), 1.6) * 0.85;
        }
      }
      g.attributes.position.needsUpdate = true; g.attributes.color.needsUpdate = true;
    });
  }

  // heatmap: where each alliance spent the match, painted on a plane just above the floor
  const heatTex = (() => {
    const N = 256, c = document.createElement("canvas"); c.width = c.height = N;
    const g = c.getContext("2d"), HALF = 1.8288, toPx = (v) => ((v + HALF) / (2 * HALF)) * N;
    for (const side of ["red", "blue"]) {
      const grid = new Float32Array(N * N), rr = 7;
      for (const r of robots.filter((x) => x.side === side)) for (const p of r.path) {
        if (p[0] < 0 || !p[4]) continue;
        const cx = toPx(p[1]), cy = N - toPx(p[2]);
        for (let y = Math.max(0, cy - rr | 0); y < Math.min(N, cy + rr); y++) for (let x = Math.max(0, cx - rr | 0); x < Math.min(N, cx + rr); x++) {
          const d2 = ((x - cx) ** 2 + (y - cy) ** 2) / (rr * rr); if (d2 < 1) grid[y * N + x] += (1 - d2) ** 2;
        }
      }
      let mx = 0; for (const v of grid) mx = Math.max(mx, v);
      const img = g.getImageData(0, 0, N, N), col = side === "red" ? [255, 69, 80] : [76, 134, 255];
      for (let i = 0; i < N * N; i++) {
        const a = Math.min(1, Math.pow(grid[i] / (mx || 1), 0.6) * 1.25);
        if (a <= 0.02) continue;
        const k = i * 4, A = img.data[k + 3] / 255, out = a + A * (1 - a);
        for (let j = 0; j < 3; j++) img.data[k + j] = (col[j] * a + img.data[k + j] * A * (1 - a)) / out;
        img.data[k + 3] = out * 255;
      }
      g.putImageData(img, 0, 0);
    }
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
  })();
  const heat = new THREE.Mesh(new THREE.PlaneGeometry(2 * 1.8288, 2 * 1.8288), new THREE.MeshBasicMaterial({ map: heatTex, transparent: true, opacity: 0, depthWrite: false, toneMapped: false, blending: THREE.AdditiveBlending }));
  heat.rotation.x = -Math.PI / 2; heat.position.y = 0.005; heat.renderOrder = 1; F.world.add(heat);
  let heatOn = false, heatA = 0;
  const heatBtn = $(".rp-heat");
  heatBtn.addEventListener("click", () => { heatOn = !heatOn; heatBtn.setAttribute("aria-pressed", heatOn); });

  // scoring flashes at goals
  const GOALS = { C: [0, 0], NW: [-0.6, 1.2], NE: [0.6, 1.2], EN: [1.2, 0.6], ES: [1.2, -0.6], SE: [0.6, -1.2], SW: [-0.6, -1.2], WS: [-1.2, -0.6], WN: [-1.2, 0.6] };
  const ringGeo = new THREE.RingGeometry(0.09, 0.115, 40);
  const flashes = R.events.filter((e) => e.type === "placement" && GOALS[e.goal]).map((e) => {
    const team = robots.find((r) => r.team && r.team === e.team);
    const m = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({ color: team?.side === "blue" ? 0x4c86ff : team?.side === "red" ? 0xff4550 : 0xf2c230, transparent: true, opacity: 0, depthWrite: false }));
    m.rotation.x = -Math.PI / 2; m.position.set(GOALS[e.goal][0], 0.008, -GOALS[e.goal][1]); m.renderOrder = 3; F.world.add(m);
    return { e, m };
  });

  // Toggle flips: from a seen flip the Toggle shows the colour it was set to, until we see it
  // change again; the robot that flipped it says so on its label for a moment. A Toggle we
  // haven't seen fully set keeps the plain look. Only flips we actually saw are in the data.
  const TOG = { N: [0, -1.759, 0], S: [0, 1.759, 0], E: [1.759, 0, 1], W: [-1.759, 0, 1] };
  const barGeo = new THREE.BoxGeometry(0.68, 0.075, 0.085);
  const flipEvents = R.events.filter((e) => e.type === "flip" && TOG[e.q] && robots[e.robot]);
  const flipGlows = flipEvents.map((e) => {
    const col = { red: 0xff4550, blue: 0x4c86ff, yellow: 0xf2c230 }[e.to] ?? (e.alliance === "blue" ? 0x4c86ff : 0xff4550);
    const m = new THREE.Mesh(barGeo, new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0, depthWrite: false, toneMapped: false }));
    const [x, z, rot] = TOG[e.q]; m.position.set(x, 0.065, z); if (rot) m.rotation.y = Math.PI / 2; m.renderOrder = 4; F.world.add(m);
    return { e, m };
  });
  const FLIP_SHOW = 2.6;

  // labels
  labels.innerHTML = robots.map((r) => `<div class="pin ${r.side}"><b>${esc(r.label)}<span class="tg">Toggled</span></b></div>`).join("");
  pipMarks.innerHTML = robots.map((r) => `<i class="${r.side}"></i>`).join("");
  const pins = [...labels.children], pmarks = [...pipMarks.children];

  // the team cards under the stage
  $(".rp-teams").innerHTML = robots.map((r) => r.named
    ? `<div class="rp-team" style="--c:var(--${r.side})"><div class="k"><i></i>${r.side === "red" ? "Red" : "Blue"}</div><b>${esc(r.team)}${names[r.team] ? `<small class="tn">${esc(names[r.team])}</small>` : ""}</b><span class="z"></span><span class="d"></span></div>`
    : `<div class="rp-team unsure" style="--c:var(--${r.side})"><div class="k"><i></i>${esc(r.label)}</div><b>${r.maybe ? `${esc(r.maybe[0])}<small>or</small>${esc(r.maybe[1])}` : "Not named"}</b><span class="z"></span><span class="d"></span></div>`).join("");
  const cards = [...root.querySelectorAll(".rp-team")];
  const dist = robots.map((r) => {                      // cumulative distance along each path (m)
    const c = [0]; for (let i = 1; i < r.path.length; i++) c.push(c[i - 1] + Math.hypot(r.path[i][1] - r.path[i - 1][1], r.path[i][2] - r.path[i - 1][2]));
    return c;
  });

  // scrubber: event ticks
  const t0 = Math.max(R.t0, -3), t1 = R.t1, span = t1 - t0;
  const DRV = R.driver ?? AUTON;                         // driver control start, seconds after autonomous started
  const ticks = $(".rp-ticks");
  const a0 = Math.max(0, -t0), a1 = Math.max(a0, AUTON - t0);   // the autonomous band, kept inside the bar
  ticks.innerHTML = a1 > a0 ? `<span class="auton" style="left:${(a0 / span) * 100}%;width:${((Math.min(a1, span) - a0) / span) * 100}%"></span>` : "";
  ticks.insertAdjacentHTML("beforeend", flipEvents.filter((e) => e.t >= t0 && e.t <= t1)
    .map((e) => `<span class="flip ${e.alliance}" style="left:${((e.t - t0) / span) * 100}%"></span>`).join(""));
  const range = $(".rp-range");
  range.min = t0; range.max = t1; range.step = 0.1;

  // camera: follow the broadcast camera, or orbit
  let mode = "broadcast", orbit = { az: -0.7, el: 0.55, dist: 5.2 }, dragging = false;
  const frameFor = (c) => ({ w: 1280, h: 720, f: c[3], pos: c[1], quat: c[2] });
  function orbitView() {
    const [w, h] = F.size, k = clamp(1.55 / (w / h), 1, 2.4);
    const p = new THREE.Vector3(Math.sin(orbit.az) * Math.cos(orbit.el), Math.sin(orbit.el), Math.cos(orbit.az) * Math.cos(orbit.el)).multiplyScalar(orbit.dist);
    const fov = (2 * Math.atan(Math.tan((32 * Math.PI) / 360) * k) * 180) / Math.PI;
    return F.freeView(p, new THREE.Vector3(0, 0.05, 0), fov);
  }
  let view = F.photoView(frameFor(R.cams[0])), blendFrom = null, blendT = 1;
  function setMode(m) {
    if (m === mode) return;
    blendFrom = view; blendT = 0; mode = m;
    root.querySelectorAll(".rp-view button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.v === m));
    root.classList.toggle("is-orbit", m === "orbit");
  }
  root.querySelectorAll(".rp-view button").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.v)));
  let px = 0, py = 0;
  canvas.addEventListener("pointerdown", (e) => { if (mode !== "orbit") setMode("orbit"); dragging = true; px = e.clientX; py = e.clientY; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    orbit.az -= (e.clientX - px) * 0.006; orbit.el = clamp(orbit.el + (e.clientY - py) * 0.004, 0.2, 1.15); px = e.clientX; py = e.clientY;
  });
  const up = () => (dragging = false);
  canvas.addEventListener("pointerup", up); canvas.addEventListener("pointercancel", up);
  canvas.style.touchAction = "pan-y";

  // playback
  let t = start != null ? clamp(start, t0, t1) : Math.max(t0, -1), playing = false, speed = 1, last = 0, visible = false, started = false;
  const play = $(".rp-play");
  function setPlaying(p) { playing = p; play.textContent = p ? "Pause" : "Play"; }
  play.addEventListener("click", () => { if (t >= t1 - 0.05) t = t0; setPlaying(!playing); });
  range.addEventListener("input", () => { t = +range.value; });
  root.querySelectorAll(".rp-speed button").forEach((b) => b.addEventListener("click", () => {
    speed = +b.dataset.s; root.querySelectorAll(".rp-speed button").forEach((x) => x.setAttribute("aria-pressed", x === b));
  }));
  const io = new IntersectionObserver(([e]) => {
    visible = e.isIntersecting;
    if (visible && !started && (!reduced || autoplay)) { started = true; setPlaying(true); }
  }, { threshold: 0.35 });
  io.observe(canvas);
  addEventListener("resize", () => F.resize());

  const clock = $(".rp-clock"), pipCard = $(".rp-pip");
  pipCard.hidden = !(R.stills && R.stills.n);          // matches kept without broadcast stills (to save space)
  let stillIdx = -1;
  const helper = new THREE.PerspectiveCamera(30, 16 / 9, 0.05, 60);

  let dead = false;
  function frame(now) {
    if (dead) return;
    requestAnimationFrame(frame);
    const dt = Math.min(0.1, (now - last) / 1000); last = now;
    if (!visible) return;
    if (playing) {
      t += dt * speed;
      if (t > (R.auton_seen === false ? t0 + 2 : AUTON + 2) && t < DRV - 2) t = DRV - 2;      // skip the field reset between autonomous and driver control
      if (t >= t1) { t = t1; setPlaying(false); }
    }
    range.value = t;
    $(".rp-fill").style.width = `${((t - t0) / span) * 100}%`;

    // robots and trails
    robots.forEach((r, i) => {
      const p = sample(r.path, t);
      meshes[i].position.set(p[1], 0, -p[2]);
      meshes[i].rotation.y = p[3];
      cards[i].querySelector(".z").textContent = zoneName(p[1], p[2]);
      let j = 0; while (j < r.path.length - 1 && r.path[j + 1][0] <= t) j++;
      cards[i].querySelector(".d").textContent = `${Math.round(dist[i][j] * 3.28084)} ft driven`;
    });
    drawTrails(t);
    heatA += ((heatOn ? 1 : 0) - heatA) * Math.min(1, dt * 6); heat.material.opacity = heatA;
    flashes.forEach(({ e, m }) => { const a = t - e.t; m.material.opacity = a >= 0 && a < 1.2 ? 1 - a / 1.2 : 0; m.scale.setScalar(1 + Math.max(0, a) * 1.6); });
    const flipping = new Set();
    flipGlows.forEach(({ e, m }) => {
      const a = t - e.t, held = a >= 0 && (e.until == null || t < e.until);
      m.material.opacity = held ? (a < 0.25 ? a / 0.25 : 0.92) : 0;
      m.scale.set(1, held && a < 0.6 ? 1 + (0.6 - a) * 1.2 : 1, 1);
      if (a >= 0 && a < FLIP_SHOW) flipping.add(e.robot);
    });
    pins.forEach((p, i) => p.classList.toggle("flipped", flipping.has(i)));

    // camera
    const target = mode === "broadcast" ? F.photoView(frameFor(camAt(R.cams, t)), F.size[1] > F.size[0] * 0.7) : (!dragging && !reduced && (orbit.az += 0.0006 * (playing ? 1 : 0.3)), orbitView());
    if (blendT < 1) { blendT = Math.min(1, blendT + dt / 1.1); const k = blendT < 0.5 ? 4 * blendT ** 3 : 1 - (-2 * blendT + 2) ** 3 / 2; view = F.mix(blendFrom, target, k); }
    else view = target;
    F.apply(view);
    F.render();

    // labels over the 3D robots
    robots.forEach((r, i) => {
      const p = meshes[i].position, [x, y] = F.project(p.x, -p.z, 0.45);
      pins[i].style.transform = `translate(${x}px, ${y}px)`;
    });

    // clock
    clock.innerHTML = R.final && t >= t1 - 9 ? `<b>Final</b> <span style="color:var(--red)">${R.final.red}</span> – <span style="color:var(--blue)">${R.final.blue}</span>` : R.auton_seen === false && t < DRV ? `<b>Before driver control</b>` : t < 0 ? `<b>Starting</b>` : t < AUTON ? `<b>Autonomous</b> ${mmss(AUTON - t)}` : t < DRV ? `<b>Between periods</b>` : `<b>Driver control</b> ${mmss(105 - (t - DRV))}`;

    // broadcast still, with the tracked robots marked on it
    const si = clamp(Math.floor(t - R.stills.t0), 0, R.stills.n - 1);
    if (si !== stillIdx && R.stills.n) {
      stillIdx = si; const per = R.stills.cols * R.stills.rows, k = si % per;
      pip.style.backgroundImage = `url(${R.stills.dir}s${Math.floor(si / per)}.jpg)`;
      pip.style.backgroundSize = `${R.stills.cols * 100}% ${R.stills.rows * 100}%`;
      pip.style.backgroundPosition = `${((k % R.stills.cols) / (R.stills.cols - 1)) * 100}% ${(Math.floor(k / R.stills.cols) / (R.stills.rows - 1)) * 100}%`;
    }
    const c = camAt(R.cams, t);
    helper.position.set(...c[1]); helper.quaternion.set(...c[2]); helper.fov = (2 * Math.atan(360 / c[3]) * 180) / Math.PI; helper.updateProjectionMatrix(); helper.updateMatrixWorld();
    const pw = pipCard.clientWidth, ph = pw * 9 / 16;
    robots.forEach((r, i) => {
      const p = meshes[i].position.clone(); p.y = 0.2; p.project(helper);
      const ok = Math.abs(p.x) < 1.05 && Math.abs(p.y) < 1.05 && p.z < 1;
      pmarks[i].style.opacity = ok ? 1 : 0;
      pmarks[i].style.transform = `translate(${((p.x + 1) / 2) * pw}px, ${((1 - p.y) / 2) * ph}px)`;
    });
  }
  for (let k = 0; k * R.stills.cols * R.stills.rows < R.stills.n; k++) new Image().src = `${R.stills.dir}s${k}.jpg`;   // preload sheets
  requestAnimationFrame((n) => { last = n; frame(n); });
  return {
    setPlaying, seek: (x) => (t = x), get t() { return t; },
    destroy() { dead = true; io.disconnect(); F.renderer.forceContextLoss(); F.dispose(); },
  };
}
