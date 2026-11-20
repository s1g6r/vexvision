import { createField } from "./field3d.js";

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const STILL = new URLSearchParams(location.search).has("still"), SKIP = new URLSearchParams(location.search).has("rest");
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const ft = (m) => (m * 3.28084).toFixed(1);
const where = (r) => {
  const d = Math.hypot(r.x, r.y);
  const zone = Math.abs(r.x) + Math.abs(r.y) <= 0.6096 ? "In the midfield" : r.x + r.y < 0 ? "Red side" : "Blue side";
  return `${zone} · ${ft(d)} ft from centre`;
};

const [frames, videos] = await Promise.all([
  fetch("data/frames.json").then((r) => r.json()),
  fetch("data/videos.json").then((r) => r.json()).catch(() => []),
]);

/* ---------- a field view with an orbit you can drag ---------- */
function stageField(canvas, marks, frame, opts = {}) {
  const F = createField(canvas, { twin: true, ...opts });
  const { THREE } = F;
  let view = null, anim = null, orbit = null, dragging = false, visible = true, idle = opts.idle ?? 0;
  const target = new THREE.Vector3(...(opts.target || [0, 0.05, -0.05]));
  const labels = [];

  function setFrame(f) {
    frame = f; dirty = true;
    F.setRobots(f.robots);
    marks.innerHTML = "";
    labels.length = 0;
    f.robots.forEach((r, i) => {
      const el = document.createElement("div");
      el.className = "box " + (r.side || "");
      el.innerHTML = `<b>${esc(r.team || "Robot " + (i + 1))}</b>`;
      marks.appendChild(el);
      labels.push({ el, r });
    });
  }
  function orbitFrom(az, el, dist) { orbit = { az, el, dist }; return orbitView(); }
  function orbitView() {
    const { az, el, dist } = orbit, [w, h] = F.size, k = clamp(1.55 / (w / h), 1, 2.4);
    const p = new THREE.Vector3(Math.sin(az) * Math.cos(el), Math.sin(el), Math.cos(az) * Math.cos(el)).multiplyScalar(dist).add(target);
    const fov = 2 * Math.atan(Math.tan(((opts.fov || 32) * Math.PI) / 360) * k) * 180 / Math.PI;
    return F.freeView(p, target, fov);
  }
  function restFor(f) {                        // a three-quarter view from the same side as the broadcast camera
    const az = Math.atan2(f.pos[0], f.pos[2]) + (opts.swing ?? -0.62);
    return { az, el: opts.elev ?? 0.5, dist: opts.dist ?? 4.7 };
  }
  function fly(to, ms, done) {
    const from = view;
    if (!from || reduced || ms === 0) { view = to; F.apply(view); dirty = true; done && done(); return; }
    const t0 = performance.now();
    anim = (now) => {
      const t = clamp((now - t0) / ms, 0, 1);
      view = F.mix(from, to, ease(t));
      F.apply(view);
      if (t >= 1) { anim = null; done && done(); }
    };
  }
  function placeLabels(mode) {
    labels.forEach(({ el, r }, i) => {
      el.classList.toggle("pin", mode !== "photo");
      if (mode === "photo") {
        const [W, H] = F.size, s = Math.max(W / frame.w, H / frame.h), ox = (frame.w * s - W) / 2, oy = (frame.h * s - H) / 2;
        const [x0, y0, x1, y1] = r.box;
        Object.assign(el.style, { left: x0 * s - ox + "px", top: y0 * s - oy + "px", width: (x1 - x0) * s + "px", height: (y1 - y0) * s + "px" });
      } else {
        const [x, y] = F.project(r.x, r.y, 0.42);
        Object.assign(el.style, { left: x - 1 + "px", top: y + "px", width: "0px", height: "0px" });
      }
    });
  }
  let labelMode = "photo", dirty = true;
  function loop(now) {
    requestAnimationFrame(loop);
    if (!visible) return;
    let moved = false;
    if (anim) { anim(now); moved = true; }
    else if (orbit && !dragging && idle && !STILL) { orbit.az += idle; view = orbitView(); F.apply(view); moved = true; }
    if (!moved && !dirty) return;
    dirty = false;
    if (labelMode === "three" || anim) placeLabels(labelMode);
    F.render();
  }
  // drag to orbit
  let px = 0, py = 0;
  canvas.addEventListener("pointerdown", (e) => {
    if (!orbit || anim) return;
    dragging = true; px = e.clientX; py = e.clientY; canvas.setPointerCapture(e.pointerId); canvas.style.cursor = "grabbing";
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    orbit.az -= (e.clientX - px) * 0.006; orbit.el = clamp(orbit.el + (e.clientY - py) * 0.004, 0.18, 1.1);
    px = e.clientX; py = e.clientY; view = orbitView(); F.apply(view); dirty = true;
  });
  const up = () => { dragging = false; canvas.style.cursor = "grab"; };
  canvas.addEventListener("pointerup", up); canvas.addEventListener("pointercancel", up);
  canvas.style.cursor = "grab"; canvas.style.touchAction = "pan-y";
  new IntersectionObserver(([e]) => (visible = e.isIntersecting)).observe(canvas);
  addEventListener("resize", () => {
    F.resize();
    if (labelMode === "photo") { view = F.photoView(frame); }
    else if (orbit) view = orbitView();
    if (view) F.apply(view);
    placeLabels(labelMode); dirty = true;
  });
  setFrame(frame);
  view = F.photoView(frame); F.apply(view);
  requestAnimationFrame(loop);
  return {
    F, get frame() { return frame; },
    setFrame, placeLabels,
    setLabelMode(m) { labelMode = m; placeLabels(m); },
    toPhoto(ms, done) { orbit = null; labelMode = "photo"; fly(F.photoView(frame), ms, done); },
    toRest(ms, done, rest) { const o = rest || restFor(frame); orbit = o; const to = orbitView(); fly(to, ms, () => { done && done(); }); },
    snapPhoto() { orbit = null; view = F.photoView(frame); F.apply(view); dirty = true; },
    touch() { dirty = true; },
  };
}

/* ---------- hero: the real broadcast frame, then the same match in 3D ---------- */
const hero = $(".hero"), heroFrame = frames[0];
const photo = $("#h-photo"), hcanvas = $("#h-canvas"), hmarks = $("#h-marks");
photo.src = heroFrame.img;
const narrow = innerWidth < 760;
const H = stageField(hcanvas, hmarks, heroFrame, { idle: reduced ? 0 : 0.00045, fov: 30, target: narrow ? [0.1, -0.45, 0.2] : [-0.55, 0.55, 0.45] });
const heroRest = { az: -0.62, el: 0.4, dist: 6.4 };
$("#h-now").innerHTML = `On the field: <b>${esc(heroFrame.match)}, ${esc(heroFrame.event)}</b>, with ${esc(heroFrame.clock)} left. <span class="r">${heroFrame.red.join(" &amp; ")}</span> vs <span class="b">${heroFrame.blue.join(" &amp; ")}</span>`;

let timers = [];
function intro() {
  timers.forEach(clearTimeout); timers = [];
  const T = (ms, f) => timers.push(setTimeout(f, reduced || SKIP ? 0 : ms));
  hero.classList.remove("rest");
  photo.style.opacity = 1; hcanvas.style.transition = "none"; hcanvas.style.opacity = 0;
  H.snapPhoto(); H.setLabelMode("photo"); H.F.lineMat.opacity = 0;
  const boxes = [...hmarks.children];
  boxes.forEach((b) => b.classList.remove("on"));
  boxes.forEach((b, i) => T(250 + i * 120, () => b.classList.add("on")));            // the model finds the robots
  T(900, () => fadeLines(1, 450));                                                    // ... and the field
  T(1300, () => { hcanvas.style.transition = "opacity .7s ease"; hcanvas.style.opacity = 1; });
  T(1700, () => { photo.style.opacity = 0; boxes.forEach((b) => b.classList.remove("on")); fadeLines(0, 600); });
  T(1900, () => {
    H.toRest(reduced || SKIP ? 0 : 1900, () => { H.setLabelMode("three"); boxes.forEach((b) => b.classList.add("on")); }, { ...heroRest });
    hero.classList.add("rest");
  });
}
function fadeLines(to, ms) {
  const m = H.F.lineMat, from = m.opacity, t0 = performance.now();
  const step = (now) => { const t = clamp((now - t0) / ms, 0, 1); m.opacity = from + (to - from) * t; H.touch(); if (t < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}
const startIntro = () => { H.placeLabels("photo"); intro(); };
if (photo.complete) startIntro(); else photo.addEventListener("load", startIntro, { once: true });
$("#h-replay").addEventListener("click", intro);

// nav background after the hero
const nav = $("#nav");
new IntersectionObserver(([e]) => nav.classList.toggle("solid", !e.isIntersecting), { rootMargin: "-80px 0px 0px 0px" }).observe(hero);

/* ---------- ticker ---------- */
const tick = videos.filter((v) => v.k === "match" && v.r?.length === 2 && v.b?.length === 2).slice(0, 18)
  .map((v) => `<span class="tk"><span class="r">${v.r.join(" ")}</span><span class="v">vs</span><span class="b">${v.b.join(" ")}</span><small>${esc((v.e || "").replace(/ Signature$/, ""))} · ${esc(v.m || "")}</small></span>`).join("");
$("#ticker").innerHTML = tick + tick;

/* ---------- read a match ---------- */
const stage = $("#stage"), sphoto = $("#s-photo");
const S = stageField($("#s-canvas"), $("#s-marks"), frames[1] || frames[0], { idle: 0, fov: 32 });
let sMode = "photo", sIndex = 1;
function pickMatch(i) {
  sIndex = i; const f = frames[i];
  [...$("#matches").children].forEach((b, k) => b.setAttribute("aria-pressed", k === i));
  sphoto.src = f.img; sphoto.alt = `${f.match} at ${f.event}, as broadcast`;
  S.setFrame(f);
  setMode("photo", true);
  $("#s-tag").textContent = `${f.event} · ${f.match}${f.clock ? " · " + f.clock + " left" : ""}`;
  $("#s-vs").innerHTML = f.red.length || f.blue.length
    ? `<span class="r">${f.red.map(esc).join(" &amp; ")}</span><span class="m">vs</span><span class="b">${f.blue.map(esc).join(" &amp; ")}</span>` : "";
  $("#s-facts").innerHTML = f.robots.map((r, k) => `<div class="fact" style="--c:var(--${r.side || "mute"})"><div class="k"><i></i>${r.side ? (r.side === "red" ? "Red" : "Blue") + " alliance" : "Robot " + (k + 1)}</div><b>${esc(r.team || "Robot " + (k + 1))}</b><span>${where(r)}</span></div>`).join("");
  requestAnimationFrame(() => S.placeLabels("photo"));
}
function setMode(m, instant) {
  sMode = m;
  [...document.querySelectorAll(".seg button")].forEach((b) => b.setAttribute("aria-pressed", b.dataset.v === m));
  const boxes = [...$("#s-marks").children];
  if (m === "three") {
    S.snapPhoto(); S.setLabelMode("photo");
    stage.classList.add("three"); boxes.forEach((b) => b.classList.remove("on"));
    setTimeout(() => S.toRest(1500, () => { S.setLabelMode("three"); boxes.forEach((b) => b.classList.add("on")); }), instant || reduced ? 0 : 450);
  } else {
    boxes.forEach((b) => b.classList.remove("on"));
    const finish = () => { stage.classList.remove("three"); S.setLabelMode("photo"); setTimeout(() => boxes.forEach((b) => b.classList.add("on")), 300); };
    if (instant) { S.snapPhoto(); finish(); } else S.toPhoto(1100, finish);
  }
}
$("#matches").innerHTML = frames.map((f, i) => `<button type="button" aria-pressed="false"><img src="${f.img}" alt="" loading="lazy"><span><b>${esc(f.match)}</b><span>${esc(f.event)}</span></span></button>`).join("");
[...$("#matches").children].forEach((b, i) => b.addEventListener("click", () => pickMatch(i)));
document.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => b.dataset.v !== sMode && setMode(b.dataset.v)));
pickMatch(1 < frames.length ? 1 : 0);
// open on the rebuilt view the first time the section is seen
new IntersectionObserver(([e], o) => { if (e.isIntersecting) { o.disconnect(); setTimeout(() => sMode === "photo" && setMode("three"), 700); } }, { threshold: 0.5 }).observe(stage);

/* ---------- team lookup ---------- */
const T = new Map();
for (const v of videos) for (const t of v.tm || []) {
  if (!T.has(t)) T.set(t, { id: t, vids: [], with: new Map(), vs: new Map(), events: new Set() });
  const r = T.get(t); r.vids.push(v); if (v.e) r.events.add(v.e);
  if (v.k === "match" && v.r && v.b) {
    const mine = v.r.includes(t) ? v.r : v.b, other = mine === v.r ? v.b : v.r;
    for (const p of mine) if (p !== t) r.with.set(p, (r.with.get(p) || 0) + 1);
    for (const o of other) r.vs.set(o, (r.vs.get(o) || 0) + 1);
  }
}
const top = [...T.values()].sort((a, b) => b.vids.length - a.vids.length).slice(0, 6).map((t) => t.id);
$("#picks").innerHTML = `<span>Most filmed so far</span>` + top.map((t) => `<a href="#team-${t}">${t}</a>`).join("");
const yt = (id) => `https://www.youtube.com/watch?v=${id}`;
const rank = (m) => { const x = (m || "").match(/^(R16|QF|SF|Final) (\d+)-(\d+)/); if (x) return { R16: 1, QF: 2, SF: 3, Final: 4 }[x[1]] * 100 + +x[2]; const q = (m || "").match(/Qual (\d+)/); return q ? -1000 + +q[1] : 900; };
const tlink = (t, me) => `<a href="#team-${t}"${t === me ? ' style="color:var(--gold)"' : ""}>${t}</a>`;
function showTeam(id) {
  const t = T.get(id), out = $("#result");
  if (!t) {
    const near = [...T.keys()].filter((k) => k.startsWith(id.replace(/[A-Z]+$/, ""))).slice(0, 8);
    out.innerHTML = `<div class="empty"><p><b>No Override video names ${esc(id)} yet.</b> A team shows up once a match, reveal or skills video title includes its number.</p>${near.length ? `<div class="picks"><span>Same club</span>${near.map((k) => `<a href="#team-${k}">${k}</a>`).join("")}</div>` : ""}</div>`;
    return;
  }
  const matches = t.vids.filter((v) => v.k === "match").sort((a, b) => (a.e || "").localeCompare(b.e || "") || rank(a.m) - rank(b.m));
  const other = t.vids.filter((v) => v.k !== "match");
  const partners = [...t.with].sort((a, b) => b[1] - a[1]).slice(0, 4).map(([k]) => k);
  out.innerHTML = `<h3 class="tname disp">${esc(id)}</h3>
    <div class="tstats"><span><b>${matches.length}</b> match${matches.length === 1 ? "" : "es"} on video</span><span><b>${t.events.size}</b> event${t.events.size === 1 ? "" : "s"}</span>${partners.length ? `<span>Partnered with ${partners.map((p) => tlink(p)).join(", ")}</span>` : ""}</div>
    ${matches.map((v) => {
      const mine = v.r?.includes(id) ? ["r", v.r, v.b] : v.b?.includes(id) ? ["b", v.b, v.r] : null;
      return `<div class="mrow"><a class="th" href="${yt(v.id)}"><img src="data/thumbs/${v.id}.jpg" alt="" loading="lazy"></a><div><div class="ev">${esc(v.e || "")}</div><div class="rd">${esc(v.m || "Match")}</div>
      ${mine ? `<div class="al"><span class="side-${mine[0]}">${mine[0] === "r" ? "Red" : "Blue"}</span> with ${mine[1].filter((x) => x !== id).map((x) => tlink(x)).join(" & ") || "partner not named"} <span class="mute">vs</span> ${mine[2].map((x) => tlink(x)).join(" & ")}</div>` : ""}</div>
      <a class="w" href="${yt(v.id)}">Watch${v.l ? " · " + v.l : ""}</a></div>`;
    }).join("")}
    ${other.length ? `<div class="vids">${other.map((v) => `<a class="vid" href="${yt(v.id)}"><span class="th"><img src="data/thumbs/${v.id}.jpg" alt="" loading="lazy"></span>${esc(v.t)}<br><small>${esc(v.c)}</small></a>`).join("")}</div>` : ""}`;
}
const q = $("#q"), sugg = $("#sugg");
let list = [], cur = 0;
q.addEventListener("input", () => {
  const s = q.value.trim().toUpperCase();
  list = s ? [...T.values()].filter((t) => t.id.startsWith(s)).sort((a, b) => b.vids.length - a.vids.length).slice(0, 6) : [];
  cur = 0;
  sugg.innerHTML = list.map((t, i) => `<a href="#team-${t.id}" class="${i ? "" : "cur"}"><b>${t.id}</b><span class="mute">${t.vids.length} video${t.vids.length === 1 ? "" : "s"}</span></a>`).join("");
  sugg.classList.toggle("open", list.length > 0);
});
q.addEventListener("keydown", (e) => {
  if (!list.length || !["ArrowDown", "ArrowUp"].includes(e.key)) return;
  e.preventDefault(); cur = (cur + (e.key === "ArrowDown" ? 1 : list.length - 1)) % list.length;
  [...sugg.children].forEach((a, i) => a.classList.toggle("cur", i === cur));
});
q.addEventListener("blur", () => setTimeout(() => sugg.classList.remove("open"), 150));
$("#find").addEventListener("submit", (e) => {
  e.preventDefault();
  const s = q.value.trim().toUpperCase().replace(/\s+/g, "");
  if (!s) return q.focus();
  location.hash = "team-" + (list[cur] && !T.has(s) ? list[cur].id : s);
});
function route() {
  const h = decodeURIComponent(location.hash.slice(1));
  if (h.startsWith("team-")) { const id = h.slice(5).toUpperCase(); q.value = id; sugg.classList.remove("open"); showTeam(id); $("#teams").scrollIntoView({ behavior: reduced ? "auto" : "smooth" }); }
}
addEventListener("hashchange", route); route();
window.__ready = true; window.done = true;
