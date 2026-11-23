import { createField } from "./field3d.js";
import { mountReplay } from "./replay.js";
import { analyzeImage } from "./analyze.js";

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

const [frames, videos, TS] = await Promise.all([
  fetch("data/frames.json").then((r) => r.json()),
  fetch("data/videos.json").then((r) => r.json()).catch(() => []),
  fetch("data/team_stats.json").then((r) => (r.ok ? r.json() : {})).catch(() => ({})),
]);
const OFF = await fetch("data/official.json").then((r) => (r.ok ? r.json() : null)).catch(() => null) || { matches: {}, teams: {}, events: {} };
const TH = await fetch("data/thumbs.json").then((r) => (r.ok ? r.json() : null)).catch(() => null);
const thumb = (id) => {
  const t = TH?.map?.[id];
  if (!t) return `<img src="data/thumbs/${id}.jpg" alt="" loading="lazy">`;
  const [n, c, r, rows] = t, C = TH.cols;
  return `<span class="spr" data-bg="data/sheets/sheet-${n}.jpg" style="background-size:${C * 100}% ${rows * 100}%;background-position:${C > 1 ? (c / (C - 1)) * 100 : 0}% ${rows > 1 ? (r / (rows - 1)) * 100 : 0}%"></span>`;
};
// Thumbnail sheets load only when a thumbnail comes near the screen.
let sprPending = false;
function sprScan() {
  sprPending = false;
  const H = innerHeight + 400, W = innerWidth + 400;
  document.querySelectorAll(".spr[data-bg]").forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.bottom > -400 && r.top < H && r.right > -400 && r.left < W && (r.width || r.height)) { el.style.backgroundImage = `url(${el.dataset.bg})`; el.removeAttribute("data-bg"); }
  });
}
const watchSpr = () => { if (!sprPending) { sprPending = true; requestAnimationFrame(sprScan); } };
addEventListener("scroll", watchSpr, { capture: true, passive: true });
addEventListener("resize", watchSpr);
new MutationObserver(watchSpr).observe(document.body, { childList: true, subtree: true });
const IDX = await fetch("data/replays/index.json").then((r) => (r.ok ? r.json() : [])).catch(() => []);
const NOREP = new Set(IDX.filter((x) => x.replay === false).map((x) => x.id));
const REP = await fetch("data/reports.json").then((r) => (r.ok ? r.json() : {})).catch(() => ({}));

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
window.__S = S;
let sMode = "photo", sIndex = 1;
function pickMatch(i) {
  sIndex = i; const f = frames[i];
  $("#matches").querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.i === String(i)));
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
  [...document.querySelectorAll("#read .seg button")].forEach((b) => b.setAttribute("aria-pressed", b.dataset.v === m));
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
function renderMatchList() {
  $("#matches").innerHTML = `<button type="button" class="mine" id="own" aria-pressed="false"><span class="up">Your screenshot</span><span><b>Try your own</b><span>Drop, paste or pick a broadcast frame</span></span></button>` +
    frames.map((f, i) => `<button type="button" aria-pressed="false" data-i="${i}"><img src="${f.img}" alt="" loading="lazy"><span><b>${esc(f.match)}</b><span>${esc(f.event)}</span></span></button>`).join("");
  $("#matches").querySelectorAll("[data-i]").forEach((b) => b.addEventListener("click", () => pickMatch(+b.dataset.i)));
  $("#own").addEventListener("click", () => $("#own-file").click());
}
renderMatchList();
const ownStatus = (m, err) => { const s = $("#own-status"); s.textContent = m; s.classList.toggle("err", !!err); s.hidden = !m; };
async function useFile(file) {
  if (!file || !file.type.startsWith("image/")) return ownStatus("That isn't an image. Use a PNG or JPG screenshot of a broadcast.", true);
  $("#read").scrollIntoView({ behavior: reduced ? "auto" : "smooth" });
  stage.classList.add("busy");
  try {
    const f = await analyzeImage(file, (m) => ownStatus(m));
    stage.classList.remove("busy");
    if (f.error) { sphoto.src = f.url; stage.classList.remove("three"); $("#s-marks").innerHTML = ""; return ownStatus(f.error, true); }
    const at = frames.findIndex((x) => x.mine);
    if (at >= 0) frames.splice(at, 1);
    frames.unshift(f); renderMatchList(); pickMatch(0);
    ownStatus(f.robots.length ? `Found ${f.robots.length} robot${f.robots.length === 1 ? "" : "s"} and lined up the field. Switch to "Rebuilt in 3D" to walk around it.` : "Lined up the field but didn't find robots in this shot.");
    setTimeout(() => setMode("three"), 600);
  } catch (e) {
    console.error(e); stage.classList.remove("busy");
    ownStatus("This browser couldn't run the models. The rest of the site still works.", true);
  }
}
$("#own-file").addEventListener("change", (e) => useFile(e.target.files[0]));
["dragenter", "dragover"].forEach((t) => stage.addEventListener(t, (e) => { e.preventDefault(); stage.classList.add("over"); }));
["dragleave", "drop"].forEach((t) => stage.addEventListener(t, (e) => { e.preventDefault(); stage.classList.remove("over"); }));
stage.addEventListener("drop", (e) => useFile(e.dataTransfer.files[0]));
document.addEventListener("paste", (e) => { const f = [...(e.clipboardData?.files || [])][0]; if (f) useFile(f); });
document.querySelectorAll("#read .seg button").forEach((b) => b.addEventListener("click", () => b.dataset.v !== sMode && setMode(b.dataset.v)));
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
const pct = (v) => `${Math.round(v * 100)}%`;
/* ---------- your own notes, kept on this device ---------- */
const NOTES = (() => { try { return JSON.parse(localStorage.getItem("vv-notes") || "{}"); } catch { return {}; } })();
const saveNotes = () => { try { localStorage.setItem("vv-notes", JSON.stringify(NOTES)); } catch {} };
const noteBox = (id) => `<div class="notes"><label for="note-${esc(id)}">Your notes on ${esc(id)}</label>
  <textarea id="note-${esc(id)}" data-note="${esc(id)}" rows="3" placeholder="What you saw in the pits or from the stands: drivetrain, intake, what they told you. Saved on this device only.">${esc(NOTES[id] || "")}</textarea></div>`;
document.addEventListener("click", async (e) => {
  const b = e.target.closest(".copy-notes"); if (!b) return;
  const ev = OFF.events[b.dataset.ev];
  const text = `${(ev.short || ev.name).replace(/ \(Fall 2026\)$/, "")}, ${ev.date}\n\n` + ev.teams.filter((t) => NOTES[t.n]).map((t) => `${t.n}${t.name ? ` (${t.name})` : ""}: ${NOTES[t.n].trim()}`).join("\n\n");
  try { await navigator.clipboard.writeText(text); b.textContent = "Copied"; } catch { b.textContent = "Couldn't copy here"; }
  setTimeout(() => (b.textContent = "Copy my notes for this event"), 2000);
});
document.addEventListener("input", (e) => {
  const t = e.target.closest?.("textarea[data-note]"); if (!t) return;
  const v = t.value.trim(); if (v) NOTES[t.dataset.note] = t.value; else delete NOTES[t.dataset.note]; saveNotes();
});
function scoutBlock(id) {
  const st = TS[id];
  if (!st) return "";
  const watch = `<div class="scout-replays">${st.matches.filter((m) => !NOREP.has(m.id)).map((m) => `<button type="button" class="btn ghost" data-replay="${esc(m.id)}">Watch ${esc(m.match || "match")} in 3D</button>`).join("")}</div>`;
  if (!st.n) {
    return `<div class="scout"><div class="scout-head"><b>Tracked by vexvision</b><span>in ${st.matches.length} match${st.matches.length === 1 ? "" : "es"}</span></div>
    <p class="scout-note">We follow both robots on ${esc(id)}'s alliance in these matches, but the stream is too small to read robot plates, so we can't yet say which one is ${esc(id)}. Driving stats show up once a match names it.</p>${watch}</div>`;
  }
  const tiles = [
    ["Driven per match", `${Math.round(st.ft_per_match)} ft`, "Distance along its tracked path"],
    ["On the other side", pct(st.opp_side), "Of driver control past the Autonomous Line"],
    ["In the Midfield", pct(st.midfield), "Of driver control inside the diamond"],
    ["Autonomous", `${Math.round(st.auton_ft)} ft`, "Moved in the first 15 seconds"],
  ];
  const rep = REP[id];
  const W = rep ? watchouts(rep) : [];
  const brief = rep ? `${rep.tags?.length ? `<div class="tags" style="margin-bottom:12px">${rep.tags.map((x) => `<span class="tag">${esc(x)}</span>`).join("")}</div>` : ""}<ul class="brief">${rep.summary.slice(0, 3).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    ${W.length ? `<p class="scout-note" style="margin:0 0 6px"><b style="color:var(--ink)">Watch for</b></p><ul class="watch-list" style="margin-bottom:18px">${W.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    <a class="btn solid report-btn" href="#report-${esc(id)}">Full scouting report</a>` : "";
  return `<div class="scout"><div class="scout-head"><b>Scouted by vexvision</b><span>from ${st.n} match${st.n === 1 ? "" : "es"} where we could name it</span></div>${brief}
    <div class="scout-grid"><div class="scout-maps">
      <figure><canvas class="heat" width="240" height="240" data-team="${esc(id)}" aria-label="Where ${esc(id)} drives"></canvas><figcaption>Where it drives</figcaption></figure>
      ${st.autons?.length ? `<figure><canvas class="heat auton" width="240" height="240" data-team="${esc(id)}" aria-label="${esc(id)}'s autonomous routes"></canvas><figcaption>Autonomous routes, ${st.autons.length} match${st.autons.length === 1 ? "" : "es"}</figcaption></figure>` : ""}
      <p class="scout-note small">Turned so its own side is always bottom left.</p></div>
    <div class="scout-tiles">${tiles.map(([k, v, d]) => `<div class="fact"><div class="k">${k}</div><b>${v}</b><span>${d}</span></div>`).join("")}</div></div>
    ${watch}</div>`;
}
function fieldLines(g, W) {
  g.strokeStyle = "rgba(239,233,221,.55)"; g.lineWidth = 1.5;
  const P = (x, y) => [(x / 1.8288 + 1) / 2 * W, (1 - (y / 1.8288 + 1) / 2) * W];
  const line = (pts) => { g.beginPath(); pts.forEach((p, i) => { const [u, v] = P(...p); i ? g.lineTo(u, v) : g.moveTo(u, v); }); g.stroke(); };
  line([[-1.79, -1.79], [-0.3, -0.3]]); line([[0.3, 0.3], [1.79, 1.79]]); line([[-1.79, 1.79], [-0.3, 0.3]]); line([[0.3, -0.3], [1.79, -1.79]]);
  line([[0.61, 0], [0, 0.61], [-0.61, 0], [0, -0.61], [0.61, 0]]);
  g.strokeRect(1, 1, W - 2, W - 2);
  return P;
}
function drawAutons(c, st) {
  const g = c.getContext("2d"), W = c.width;
  g.fillStyle = "#1c1a17"; g.fillRect(0, 0, W, W);
  const P = fieldLines(g, W);
  const col = ["#f2c230", "#ef3b45", "#4c86ff", "#5fd08a", "#c792ea", "#ff9e57"];
  st.autons.forEach((a, i) => {
    g.strokeStyle = col[i % col.length]; g.lineWidth = 2.5; g.lineJoin = "round"; g.globalAlpha = 0.9;
    g.beginPath(); a.path.forEach(([x, y], j) => { const [u, v] = P(x, y); j ? g.lineTo(u, v) : g.moveTo(u, v); }); g.stroke();
    const [u0, v0] = P(...a.path[0]); g.fillStyle = col[i % col.length]; g.beginPath(); g.arc(u0, v0, 4.5, 0, 7); g.fill();
    const [u1, v1] = P(...a.path[a.path.length - 1]); g.beginPath(); g.arc(u1, v1, 3, 0, 7); g.lineWidth = 2; g.stroke();
  });
  g.globalAlpha = 1;
}
function drawHeat(c, st) {
  if (c.classList.contains("auton")) return REP[c.dataset.team] && c.classList.contains("big") ? drawRoutes(c, REP[c.dataset.team]) : drawAutons(c, st);
  const g = c.getContext("2d"), W = c.width, n = st.heat.length, k = W / n;
  g.fillStyle = "#1c1a17"; g.fillRect(0, 0, W, W);
  const red = true;                         // turned to its own side, which sits where red's does
  const off = document.createElement("canvas"); off.width = off.height = n;
  const og = off.getContext("2d"), im = og.createImageData(n, n), col = red ? [239, 59, 69] : [76, 134, 255];
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    const v = st.heat[i][j], o = (i * n + j) * 4;
    im.data[o] = col[0]; im.data[o + 1] = col[1]; im.data[o + 2] = col[2]; im.data[o + 3] = Math.min(255, Math.pow(v, 0.4) * 460);
  }
  og.putImageData(im, 0, 0);
  g.imageSmoothingEnabled = true; g.imageSmoothingQuality = "high"; g.filter = "blur(4px)";
  g.drawImage(off, 0, 0, W, W); g.filter = "none";
  const P = fieldLines(g, W);
  for (const [x, y, c2] of [[-0.6, -1.2, "#ef3b45"], [-1.2, -0.6, "#ef3b45"], [0.6, 1.2, "#4c86ff"], [1.2, 0.6, "#4c86ff"]]) { const [u, v] = P(x, y); g.fillStyle = c2; g.beginPath(); g.arc(u, v, 4, 0, 7); g.fill(); }
}

/* ---------- official results ---------- */
const ord = (n) => { const s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); };
const statsLink = (id) => OFF.teams[id]?.id ? `https://stats.2360arachnid.com/#/team/${OFF.teams[id].id}` : "https://stats.2360arachnid.com";
const shortEv = (n) => (n || "").replace(/:.*$/, "").replace(/ VEX V5 Robotics Competition.*$/, "");
function officialBlock(id) {
  const o = OFF.teams[id]; if (!o) return "";
  const s = o.season || {}, evs = o.events.filter((e) => e.played);
  const avg = evs.length ? evs.reduce((a, e) => a + e.avg_scored * e.played, 0) / evs.reduce((a, e) => a + e.played, 0) : null;
  const tiles = [
    ["Season rank", s.rank ? `${ord(s.rank)}` : "–", s.of ? `of ${s.of.toLocaleString()} High School teams` : ""],
    ["Record", s.record || "–", s.matches ? `${s.matches} matches this season` : ""],
    ["Points a match", avg != null ? Math.round(avg) : "–", evs.length ? `Its alliance's average at the events below` : "No results yet"],
    ["Best skills", s.skills ?? "–", "Driver plus programming"],
  ];
  return `<div class="off"><div class="off-head"><b>Official results</b><span>${esc(o.name || "")}${s.region ? ` · ${esc(s.region)}` : ""}</span><a href="${statsLink(id)}">More on stats.2360arachnid.com</a></div>
    <div class="off-tiles">${tiles.map(([k, v, d]) => `<div class="fact"><div class="k">${k}</div><b>${v}</b><span>${d}</span></div>`).join("")}</div>
    ${o.events.length ? `<div class="scroll"><table class="cmp"><thead><tr><th>Event</th><th class="n">Rank</th><th class="n">Record</th><th class="n">Scored</th><th class="n">Allowed</th></tr></thead><tbody>
    ${o.events.map((e) => `<tr><td>${OFF.events[e.event_id] ? `<a href="#event-${e.event_id}-${esc(id)}">${esc(shortEv(e.event))}</a>` : esc(shortEv(e.event))}<small style="display:block;color:var(--mute)">${esc(e.date)}</small></td><td class="n">${e.rank ? `${ord(e.rank)} of ${e.teams}` : "–"}</td><td class="n">${esc(e.record || "–")}</td><td class="n">${e.avg_scored != null ? Math.round(e.avg_scored) : "–"}</td><td class="n">${e.avg_allowed != null ? Math.round(e.avg_allowed) : "–"}</td></tr>`).join("")}
    </tbody></table></div>` : ""}</div>`;
}
/* ---------- event prep ---------- */
const evList = Object.entries(OFF.events).sort((a, b) => b[1].date.localeCompare(a[1].date));
$("#prep-ev").innerHTML = evList.map(([k, e]) => `<option value="${k}">${esc(e.short.replace(/ \(Fall 2026\)$/, ""))} · ${esc(e.date)}${e.matches.length ? "" : " · no schedule yet"}</option>`).join("");
const cornfield = evList.find(([, e]) => /Cornfield/.test(e.short) && e.matches.length);
if (cornfield) $("#prep-ev").value = cornfield[0];
$("#prep-team").value = "2360A";
$("#prep-form").addEventListener("submit", (e) => { e.preventDefault(); location.hash = `event-${$("#prep-ev").value}-${$("#prep-team").value.trim().toUpperCase()}`; });
function watchouts(R) {
  const S = R.sections || {}, out = [];
  const r0 = S.auton?.routes?.[0];
  if (r0?.steps?.crosses) out.push("Their auton crosses the Autonomous Line");
  const d = S.defence || {};
  if (d.other_side >= 0.55 && d.near_opp_their_side >= 0.15) out.push(`Expect them on your side: ${pct(d.other_side)} of driver control there`);
  const tg = S.toggles || {};
  if (tg.opp >= 0.19) out.push(`Comes for your Toggles: ${pct(tg.opp)} of driver control by them`);
  else if (tg.share >= 0.35) { const k = Math.round(tg.trips || 0); out.push(k >= 3 ? `Lives at the Toggles: about ${k} trips a match` : `Spends ${pct(tg.share)} of driver control by a Toggle`); }
  const fav = S.scoring?.favourites?.[0];
  if (fav && fav[1] >= 1) out.push(`Goes to ${fav[0].replace(/^its own/, "their own")} most`);
  if (S.endgame?.midfield >= 0.5) out.push("Ends in the Midfield");
  return out.slice(0, 3);
}
/* how two autonomous routes meet: partners share a start or a Goal, opponents race to the same neutral Goal */
const GOALN = { C: "the Center Goal", SW: "its own bottom Alliance Goal", WS: "its own left Alliance Goal", NE: "the other alliance's top Goal", EN: "the other alliance's right Goal", NW: "the top-left neutral Goal", WN: "the left neutral Goal", ES: "the right neutral Goal", SE: "the bottom-right neutral Goal" };
const GKEY = Object.fromEntries(Object.entries(GOALN).map(([k, v]) => [v, k]));
const GFLIP = { C: "C", SW: "NE", WS: "EN", NE: "SW", EN: "WS", NW: "SE", WN: "ES", ES: "WN", SE: "NW" };
const shortGoal = (k) => GOALN[k].replace(/^its own /, "your ").replace(/^the other alliance's /, "their ");
function autonGoals(n) {
  const r = REP[n]?.sections?.auton?.routes?.[0]; if (!r) return null;
  const st = r.steps, all = [...st.stops.map(([, p]) => p), st.end].filter((p) => GKEY[p]);
  return { start: st.start, goals: new Set(all.map((p) => GKEY[p])), moved: st.moved_m };
}
function autonClash(me, other, partner) {
  const a = autonGoals(me), b = autonGoals(other);
  if (!a || !b || a.moved < 0.6 || b.moved < 0.6) return null;
  if (partner) {
    if (a.start === b.start) return `Both autons start at ${a.start.replace(/^its own /, "your own ")}. Agree on who takes that tile.`;
    const both = [...a.goals].filter((g) => b.goals.has(g));
    return both.length ? `Both autons go to ${both.map(shortGoal).join(" and ")}. Check they don't collide.` : "Your autons don't overlap.";
  }
  const theirs = new Set([...b.goals].map((g) => GFLIP[g]));
  const race = [...a.goals].filter((g) => theirs.has(g) && (g === "C" || /neutral/.test(GOALN[g])));
  return race.length ? `Races you to ${race.map(shortGoal).join(" and ")} in auton.` : null;
}
const nOn = (R) => { const k = R.n ?? R.matches?.length ?? 0; return `${k} match${k === 1 ? "" : "es"}`; };
function teamCard(n, side, ev, me, partner) {
  const t = ev.teams.find((x) => x.n === n) || {}, R = REP[n];
  const A = R?.sections?.auton, route = A?.routes?.[0];
  const autonLine = route ? `<div class="line"><b>Auton${A.seen > 1 ? ` · ran it ${route.count} of ${A.seen}` : " · seen once"}:</b> ${esc(route.text)}.${A.routes.length > 1 ? ` <span class="role">${A.routes.length - 1} other route${A.routes.length > 2 ? "s" : ""} seen.</span>` : ""}</div>` : "";
  const W = R ? watchouts(R) : [];
  const clash = me ? autonClash(me, n, partner) : null;
  if (clash) W.unshift(clash);
  return `<div class="tc ${side}"><div class="n"><a href="#team-${esc(n)}">${esc(n)}</a><small>${esc(t.name || "")}</small></div>
    <div class="role">${t.rank ? `${ord(t.rank)} here · ` : ""}${esc(t.record || "")}${t.avg != null ? ` · ${Math.round(t.avg)} points a match` : ""}${t.skills ? ` · skills ${t.skills}` : ""}</div>
    ${R?.tags?.length ? `<div class="tags">${R.tags.map((x) => `<span class="tag">${esc(x)}</span>`).join("")}</div>` : ""}
    ${route ? `<div class="tc-auton"><canvas class="heat auton big" width="200" height="200" data-team="${esc(n)}" aria-label="${esc(n)}'s autonomous routes"></canvas>${autonLine}</div>` : ""}
    ${W.length ? `<ul class="watch-list">${W.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    ${NOTES[n] ? `<div class="tc-note"><b>Your note:</b> ${esc(NOTES[n].length > 160 ? NOTES[n].slice(0, 157) + "…" : NOTES[n])}</div>` : ""}
    ${R ? `<div class="tc-links">${route ? watchBtn({ id: route.typical }, -1, "Watch their auton") : ""}<a class="more" href="#report-${esc(n)}">Full report</a></div><div class="role tc-src">From ${nOn(R)} on video</div>` : `<div class="role">Not on video yet</div>`}</div>`;
}
/* ---------- match plan: all four most-run autons on one field ---------- */
const PLAN_COL = { me: "#f2c230", partner: "#5fd08a", opp1: "#ef6b8a", opp2: "#b48cff" };
function typicalPath(n) {
  const R = REP[n], r = R?.sections?.auton?.routes?.[0]; if (!r) return null;
  const m = R.matches.find((x) => x.id === r.typical && x.route?.length);
  return m ? { path: m.route, count: r.count, seen: R.sections.auton.seen } : null;
}
function planBlock(me, partner, op) {
  const who = [[me, "me", false], [partner, "partner", false], [op[0], "opp1", true], [op[1], "opp2", true]].filter(([n]) => n);
  const have = who.filter(([n]) => typicalPath(n));
  if (have.length < 2) return "";
  const data = esc(JSON.stringify(have.map(([n, k, flip]) => [n, k, flip])));
  return `<div class="pm-plan"><canvas class="plan" width="220" height="220" data-plan="${data}" aria-label="Most-run autons of the teams in this match"></canvas>
    <div><b class="pm-plan-h">Autons in this match</b><ul class="pm-legend">${who.map(([n, k]) => `<li><i style="background:${PLAN_COL[k]}"></i>${esc(n)}${typicalPath(n) ? "" : ` <span class="role">not seen</span>`}</li>`).join("")}</ul>
    <p class="role">Your side is bottom left. Each line is that team's most-run auton; a filled dot is where it starts.</p></div></div>`;
}
function drawPlan(c) {
  const g = c.getContext("2d"), W = c.width;
  g.fillStyle = "#1c1a17"; g.fillRect(0, 0, W, W);
  const P = fieldLines(g, W);
  JSON.parse(c.dataset.plan).forEach(([n, k, flip]) => {
    const t = typicalPath(n); if (!t) return;
    const pts = t.path.map(([x, y]) => flip ? [-x, -y] : [x, y]);
    g.strokeStyle = PLAN_COL[k]; g.fillStyle = PLAN_COL[k]; g.lineWidth = 3; g.lineJoin = "round"; g.globalAlpha = 0.95;
    g.beginPath(); pts.forEach(([x, y], j) => { const [u, v] = P(x, y); j ? g.lineTo(u, v) : g.moveTo(u, v); }); g.stroke();
    const [u0, v0] = P(...pts[0]); g.beginPath(); g.arc(u0, v0, 5, 0, 7); g.fill();
    const [u1, v1] = P(...pts[pts.length - 1]); g.beginPath(); g.arc(u1, v1, 3.5, 0, 7); g.lineWidth = 2; g.stroke();
  });
  g.globalAlpha = 1;
}
/* ---------- pick list ---------- */
const PICK_SORTS = [["rating", "Rating"], ["avg", "Points"], ["skills", "Skills"], ["video", "Most on video"], ["fit", "Fits with you"], ["mix", "Your mix"]];
/* your own mix: each slider weighs one thing, compared only with the other teams at this event */
const MIX_KEYS = [["rating", "Rating", (t) => t.rating], ["avg", "Points a match", (t) => t.avg], ["skills", "Skills", (t) => t.skills],
  ["speed", "Speed on video", (t) => REP[t.n]?.sections?.robot?.top_fps], ["goals", "Trips to Goals", (t) => REP[t.n]?.sections?.scoring?.visits_per_match],
  ["defence", "Time on the other side", (t) => REP[t.n]?.sections?.defence?.other_side]];
const MIX = (() => { try { return { rating: 2, avg: 2, skills: 1, speed: 1, goals: 1, defence: 0, ...JSON.parse(localStorage.getItem("vv-mix") || "{}") }; } catch { return { rating: 2, avg: 2, skills: 1, speed: 1, goals: 1, defence: 0 }; } })();
function mixScores(ev) {
  const pct = {};
  MIX_KEYS.forEach(([k, , f]) => {
    const vals = ev.teams.map((t) => f(t)).filter((v) => v != null).sort((a, b) => a - b);
    pct[k] = (v) => v == null || vals.length < 2 ? null : vals.filter((x) => x < v).length / (vals.length - 1);
  });
  const out = {};
  ev.teams.forEach((t) => {
    let sum = 0, w = 0, miss = 0;
    MIX_KEYS.forEach(([k, , f]) => { const wt = +MIX[k] || 0; if (!wt) return; const p = pct[k](f(t)); if (p == null) { miss += wt; return; } sum += wt * p; w += wt; });
    out[t.n] = w ? { score: sum / w, part: miss > 0 } : { score: -1, part: true };
  });
  return out;
}
const mixPanel = () => `<div class="pick-mix" id="pick-mix"><p class="role">Slide each one to say how much it matters to you. Teams are compared only with the others at this event; where we have no video for a team, the video sliders are left out of its score and its Mix is marked *.</p>
  ${MIX_KEYS.map(([k, label]) => `<label><span>${label}</span><output>${["Off", "A little", "Some", "A lot"][MIX[k]]}</output><input type="range" min="0" max="3" step="1" value="${MIX[k]}" data-mix="${k}"></label>`).join("")}</div>`;
function pickFit(me, n) {
  if (!me || n === me) return null;
  const a = autonGoals(me), b = autonGoals(n);
  if (!a || !b) return null;
  if (a.start === b.start) return { ok: false, text: "Same start tile" };
  if (a.moved >= 0.6 && b.moved >= 0.6 && [...a.goals].some((g) => b.goals.has(g))) return { ok: false, text: "Same auton Goals" };
  return { ok: true, text: "Autons fit" };
}
/* teams already picked during alliance selection, per event, on this device */
const TAKEN = (() => { try { return JSON.parse(localStorage.getItem("vv-taken") || "{}"); } catch { return {}; } })();
const saveTaken = () => { try { localStorage.setItem("vv-taken", JSON.stringify(TAKEN)); } catch {} };
const evId = (ev) => Object.keys(OFF.events).find((k) => OFF.events[k] === ev);
const curSort = () => document.querySelector(".pick-sort button[aria-pressed=true]")?.dataset.sort || "rating";
function pickTable(ev, me, key) {
  const tk = new Set(TAKEN[evId(ev)] || []);
  const val = { rating: (t) => t.rating ?? -1, avg: (t) => t.avg ?? -1, skills: (t) => t.skills ?? -1, video: (t) => REP[t.n] ? (REP[t.n].n ?? 0) : -1,
    fit: (t) => { if (t.n === me) return -1e9; const f = pickFit(me, t.n); return (f ? (f.ok ? 2 : 0.5) : REP[t.n] ? 1 : 0) * 1000 + (t.rating ?? 0); },
    mix: (t) => MS[t.n].score }[key];
  const MS = key === "mix" ? mixScores(ev) : null;
  const list = [...ev.teams].sort((a, b) => tk.has(a.n) - tk.has(b.n) || val(b) - val(a));
  let rank = 0;
  return `<table class="pick"><thead><tr><th class="n">#</th><th>Team</th><th class="n">Rating</th><th class="n">Record</th><th class="n">Points</th><th class="n">Skills</th>${MS ? '<th class="n">Mix</th>' : ""}<th>How it plays</th>${me && REP[me] ? "<th>With you</th>" : ""}<th><span class="sr">Picked</span></th></tr></thead><tbody>
    ${list.map((t) => { const f = pickFit(me, t.n), gone = tk.has(t.n); return `<tr class="${t.n === me ? "me" : ""}${gone ? " taken" : ""}"><td class="n">${gone ? "–" : ++rank}</td><td><b><a href="#team-${esc(t.n)}">${esc(t.n)}</a></b><small style="display:block;color:var(--mute)">${esc(t.name || "")}</small></td><td class="n">${t.rating != null ? Math.round(t.rating) : "–"}</td><td class="n">${esc(t.record || "–")}</td><td class="n">${t.avg != null ? Math.round(t.avg) : "–"}</td><td class="n">${t.skills ?? "–"}</td>${MS ? `<td class="n">${MS[t.n].score >= 0 ? Math.round(MS[t.n].score * 100) + (MS[t.n].part ? "<small>*</small>" : "") : "–"}</td>` : ""}
      <td>${REP[t.n] ? `<div class="tags">${(REP[t.n].tags.length ? REP[t.n].tags : ["Scouted"]).map((x) => `<span class="tag">${esc(x)}</span>`).join("")}</div>` : `<span class="role" style="color:var(--mute);font-size:13px">Not on video yet</span>`}</td>${me && REP[me] ? `<td>${f ? `<span class="fit ${f.ok ? "ok" : "no"}">${f.text}</span>` : `<span class="role" style="color:var(--mute);font-size:13px">–</span>`}</td>` : ""}<td>${t.n === me ? "" : `<button type="button" class="take" data-n="${esc(t.n)}" aria-pressed="${gone}">${gone ? "Picked" : "Mark picked"}</button>`}</td></tr>`; }).join("")}
    </tbody></table>`;
}
document.addEventListener("click", (e) => {
  const b = e.target.closest(".take, .take-clear"); if (!b) return;
  const w = document.getElementById("pick-wrap"), eid = w.dataset.ev;
  if (b.classList.contains("take-clear")) delete TAKEN[eid];
  else { const set = new Set(TAKEN[eid] || []); set.has(b.dataset.n) ? set.delete(b.dataset.n) : set.add(b.dataset.n); TAKEN[eid] = [...set]; }
  saveTaken();
  w.innerHTML = pickTable(OFF.events[eid], w.dataset.me || null, curSort());
  const c = document.querySelector(".take-clear"); if (c) c.hidden = !(TAKEN[eid] || []).length;
});
document.addEventListener("click", (e) => {
  const b = e.target.closest(".pick-sort button"); if (!b) return;
  const w = document.getElementById("pick-wrap"), ev = OFF.events[w.dataset.ev];
  b.parentNode.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
  w.innerHTML = pickTable(ev, w.dataset.me || null, b.dataset.sort);
  const mp = document.getElementById("pick-mix-slot"); if (mp) mp.innerHTML = b.dataset.sort === "mix" ? mixPanel() : "";
});
/* the pick list as it is sorted now, with your notes, as a CSV any spreadsheet opens */
document.addEventListener("click", (e) => {
  const b = e.target.closest(".pick-csv"); if (!b) return;
  const w = document.getElementById("pick-wrap"), ev = OFF.events[w.dataset.ev], me = w.dataset.me || null;
  const key = document.querySelector(".pick-sort button[aria-pressed=true]")?.dataset.sort || "rating";
  const MS = key === "mix" ? mixScores(ev) : null;
  const order = [...w.querySelectorAll("tbody tr td:nth-child(2) a")].map((a) => a.textContent);
  const byN = Object.fromEntries(ev.teams.map((t) => [t.n, t]));
  const q = (v) => { v = v == null ? "" : String(v); return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v; };
  const head = ["Rank", "Team", "Name", "Rating", "Record", "Points a match", "Skills", ...(MS ? ["Your mix"] : []), "How it plays", "Matches on video", ...(me && REP[me] ? ["With " + me] : []), "Picked", "Your notes"];
  const rows = order.map((n, i) => { const t = byN[n], f = pickFit(me, n);
    return [(TAKEN[w.dataset.ev] || []).includes(n) ? "" : i + 1, n, t.name, t.rating != null ? Math.round(t.rating) : "", t.record, t.avg != null ? Math.round(t.avg) : "", t.skills, ...(MS ? [MS[n].score >= 0 ? Math.round(MS[n].score * 100) : ""] : []),
      REP[n] ? (REP[n].tags.join("; ") || "Scouted") : "", REP[n]?.n ?? 0, ...(me && REP[me] ? [f ? f.text : ""] : []), (TAKEN[w.dataset.ev] || []).includes(n) ? "Yes" : "", NOTES[n] || ""]; });
  const csv = "\ufeff" + [head, ...rows].map((r) => r.map(q).join(",")).join("\r\n");
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  a.download = `pick list ${(ev.short || "event").replace(/ \(Fall 2026\)$/, "")}${me ? " " + me : ""}.csv`; document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
});
document.addEventListener("input", (e) => {
  const r = e.target.closest?.("input[data-mix]"); if (!r) return;
  MIX[r.dataset.mix] = +r.value; r.previousElementSibling.textContent = ["Off", "A little", "Some", "A lot"][+r.value];
  try { localStorage.setItem("vv-mix", JSON.stringify(MIX)); } catch {}
  const w = document.getElementById("pick-wrap"); w.innerHTML = pickTable(OFF.events[w.dataset.ev], w.dataset.me || null, "mix");
});
/* a row of your matches to jump between; the first one without a score is marked as next */
function jumpStrip(mine, me) {
  if (mine.length < 2) return "";
  const played = (m) => m.rs != null && (m.rs || m.bs);
  let last = -1; mine.forEach((m, i) => { if (played(m)) last = i; });
  const next = last + 1 < mine.length ? last + 1 : -1;
  return `<nav class="pm-jump" aria-label="Jump to a match">${mine.map((m, i) => {
    const red = m.r.includes(me), my = red ? m.rs : m.bs, th = red ? m.bs : m.rs, done = m.rs != null && (m.rs || m.bs);
    const res = done ? (my > th ? "W" : my < th ? "L" : "T") : "";
    return `<button type="button" data-pm="${i}" class="${i === next ? "next" : ""}${res ? " r-" + res : ""}">${esc(m.m.replace(/^Qual(ifier|ification)? #?/i, "Q"))}${res ? ` <small>${res}</small>` : i === next ? " <small>next</small>" : ""}</button>`;
  }).join("")}</nav>`;
}
document.addEventListener("click", (e) => {
  const b = e.target.closest(".pm-jump button"); if (!b) return;
  document.getElementById("pm-" + b.dataset.pm)?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
});
function showEvent(eid, me) {
  const ev = OFF.events[eid], out = $("#prep-out");
  if (!ev) { out.innerHTML = `<div class="empty"><p><b>We don't have that event yet.</b></p></div>`; return; }
  $("#prep-ev").value = eid; if (me) $("#prep-team").value = me;
  const mine = me ? ev.matches.filter((m) => m.r.includes(me) || m.b.includes(me)) : [];
  const onVideo = ev.teams.filter((t) => REP[t.n]).length;
  const list = [...ev.teams].sort((a, b) => (b.rating ?? -1) - (a.rating ?? -1));
  const known = list.filter((t) => t.n !== me && REP[t.n]?.sections?.auton).slice(0, 6);
  out.innerHTML = `<h3 class="tname disp" style="font-size:clamp(48px,7vw,96px)">${esc(ev.short.replace(/ \(Fall 2026\)$/, ""))}</h3>
    <div class="tstats"><span>${esc(ev.date)}</span><span><b>${ev.teams.length}</b> teams</span><span><b>${onVideo}</b> scouted on video</span>${OFF.fetched ? `<span>Results checked ${esc(new Date(OFF.fetched).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }))}</span>` : ""}</div>
    <div class="ev-acts"><button type="button" class="btn ghost" onclick="print()">Print this page</button>${ev.teams.some((t) => NOTES[t.n]) ? `<button type="button" class="btn ghost copy-notes" data-ev="${esc(eid)}">Copy my notes for this event</button>` : ""}</div>
    ${me && !ev.teams.some((t) => t.n === me) ? `<p class="scout-note">${esc(me)} isn't on this event's team list.</p>` : ""}
    ${me && ev.teams.some((t) => t.n === me) ? (mine.length ? `<div class="pm-sec"><h4 class="disp" style="font-size:34px;margin:30px 0 4px">${esc(me)}'s matches</h4>` + jumpStrip(mine, me) + mine.map((m, mi) => {
      const red = m.r.includes(me), al = red ? m.r : m.b, op = red ? m.b : m.r, side = red ? "r" : "b", oside = red ? "b" : "r";
      const partner = al.filter((x) => x !== me);
      const done = m.rs != null && (m.rs || m.bs);
      const my = red ? m.rs : m.bs, th = red ? m.bs : m.rs;
      const win = m.p != null ? (red ? m.p : 1 - m.p) : null;
      return `<div class="pm" id="pm-${mi}"><div class="pm-head"><b>${esc(m.m)}</b><span>${red ? "Red" : "Blue"} alliance${win != null ? ` · ${Math.round(win * 100)}% to win going in` : ""}</span>${done ? `<span class="res">${my > th ? "Won" : my < th ? "Lost" : "Tied"} ${my}–${th}</span>` : ""}</div>
        ${planBlock(me, partner[0], op)}
        <div class="pm-grid">${partner.map((p) => teamCard(p, side, ev, me, true)).join("")}${op.map((o) => teamCard(o, oside, ev, me, false)).join("")}</div></div>`;
    }).join("") + "</div>" : `<p class="scout-note">The match schedule for this event isn't out yet.${known.length ? "" : " The pick list below is ready now."}</p>`) : ""}
    ${!mine.length && known.length ? `<h4 class="disp" style="font-size:34px;margin:30px 0 4px">Teams to know</h4>
      <p class="scout-note">The strongest teams here that we've watched, so you know their autons before the schedule comes out.</p>
      <div class="pm-grid know">${known.map((t) => teamCard(t.n, "", ev, me && ev.teams.some((x) => x.n === me) ? me : null, false)).join("")}</div>` : ""}
    <h4 class="disp" style="font-size:34px;margin:40px 0 12px">Pick list</h4>
    <p class="scout-note">Every team here. Rating is from going into the event; tags come from the matches we've watched.${me && REP[me] ? ` "With you" compares each team's most-run auton with ${esc(me)}'s.` : ""}</p>
    <div class="pick-sort" role="group" aria-label="Sort the pick list">${PICK_SORTS.filter(([k]) => k !== "fit" || (me && REP[me])).map(([k, label]) => `<button type="button" data-sort="${k}" aria-pressed="${k === "rating"}">${label}</button>`).join("")}</div>
    <div id="pick-mix-slot"></div>
    <p class="scout-note pick-help">During alliance selection, mark each team as it's picked: the best teams left move to the top. <button type="button" class="take-clear" ${(TAKEN[eid] || []).length ? "" : "hidden"}>Clear picks</button></p>
    <div class="scroll" id="pick-wrap" data-ev="${esc(eid)}" data-me="${esc(me || "")}">${pickTable(ev, me, "rating")}</div>
    <button type="button" class="btn ghost pick-csv" style="margin-top:16px">Download the pick list as a spreadsheet</button>`;
}
/* ---------- full scouting report ---------- */
const mmss2 = (s) => { s = Math.max(0, Math.round(s)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
const watchBtn = (m, t, label) => NOREP.has(m.id) ? "" : `<button type="button" class="watch" data-replay="${esc(m.id)}" ${t != null ? `data-t="${(+t).toFixed(1)}"` : ""}>${esc(label)}</button>`;
const bar = (v, cls = "") => `<span class="bar ${cls}"><i style="width:${Math.min(100, Math.round(v * 100))}%"></i></span><b class="num">${pct(v)}</b>`;
function showReport(id) {
  const R = REP[id], st = TS[id], out = $("#result");
  if (!R) { out.innerHTML = `<div class="empty"><p><b>No scouting report for ${esc(id)} yet.</b> A report needs at least one match where we can tell which robot is ${esc(id)}.</p><a class="btn ghost" href="#team-${esc(id)}">Back to ${esc(id)}</a></div>`; return; }
  const ms = R.matches, S = R.sections;
  const events = [...new Set(ms.map((m) => (m.event || "").replace(/ \(Fall 2026\)$/, "")))];
  const typical = S.auton ? ms.find((m) => m.id === S.auton.typical) : null;
  const sum = (m) => m.goals.own + m.goals.neutral + m.goals.center + m.goals.opp;
  const avg = (f, list = ms) => list.reduce((a, m) => a + f(m), 0) / Math.max(1, list.length);
  const q = ms.filter((m) => !m.elim), e = ms.filter((m) => m.elim);
  const rows = [
    ["On the other side", (m) => m.other_side, "Share of driver control past the Autonomous Line"],
    ["Up against an opponent there", (m) => m.near_opp_their_side, "On their side and within a robot's length of one of them"],
    ["Near a Toggle", (m) => m.toggles.own + m.toggles.opp, "Within half a metre of either alliance's Toggle on the wall"],
    ["Near the other alliance's Toggles", (m) => m.toggles.opp, ""],
    ["At a Goal", sum, "Parked right next to a Goal"],
    ["Ends in the Midfield", (m) => (m.midfield_end ? 1 : 0), "Where it is in the last 10 seconds"],
  ];
  const RC = ["#f2c230", "#4c86ff", "#5fd08a", "#c792ea", "#ff9e57", "#ef3b45"];
  const A = S.auton, SC = S.scoring || {}, RB = S.robot || {}, RK = S.ranks || {};
  const byId = Object.fromEntries(ms.map((m) => [m.id, m]));
  const autonHtml = A ? A.routes.map((r, i) => `<div class="variant">
      <div class="v-head"><i style="background:${RC[i % 6]}"></i><b>Route ${r.label}</b><span>${r.count === 1 ? "run once" : `run in ${r.count} of ${A.seen} matches`}${i === 0 && r.count > 1 ? " · most run" : ""}</span></div>
      <ol class="steps"><li>Starts at ${esc(r.steps.start)}</li>${r.steps.moved_m < 0.6 ? "<li>Barely moves</li>" : r.steps.stops.map(([t, p]) => `<li>Stops at ${esc(p)} <small>${t.toFixed(0)} s</small></li>`).join("") + `<li>Ends at ${esc(r.steps.end)}</li>`}${r.steps.crosses ? "<li>Crosses the Autonomous Line</li>" : ""}</ol>
      <div class="watches">${r.members.map((mid) => byId[mid] ? watchBtn(byId[mid], -1, byId[mid].match) : "").join("")}</div></div>`).join("") : `<p class="cap">Not seen yet.</p>`;
  const kinds = SC.by_kind || {}, ktot = Object.values(kinds).reduce((a, v) => a + v, 0) || 1;
  const KN = { own: "Its own Alliance Goals", neutral: "Neutral Goals", center: "Center Goal", opp: "The other alliance's Goals" };
  const cm = SC.carry;
  const rankLine = (k, label, sub) => RK[k] != null ? `<div class="meter"><span class="k">${label}<small>${sub}</small></span>${bar(RK[k])}</div>` : "";
  out.innerHTML = `<div class="report">
    <a class="back" href="#team-${esc(id)}">Back to ${esc(id)}</a>
    <div class="rep-head"><span class="kicker">Scouting report</span><h3 class="tname disp">${esc(id)}</h3>
      <p class="rep-sub">From ${ms.length} match${ms.length === 1 ? "" : "es"} where we could tell which robot is ${esc(id)}${events.length ? `, at ${events.map(esc).join(", ")}` : ""}${q.length && e.length ? ` (${q.length} qualification${q.length === 1 ? "" : "s"}, ${e.length} elimination${e.length === 1 ? "" : "s"})` : e.length ? " (eliminations)" : ""}. It comes from where the robot drove and what it carried, so it says how a team plays rather than its exact score.</p></div>
    ${noteBox(id)}
    ${OFF.teams[id] ? `<section class="rep-sec">${officialBlock(id).replace('<div class="off">', '<div>')}</section>` : ""}
    <section class="rep-sec"><h4>How they play</h4><ul class="plays">${R.summary.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></section>
    <section class="rep-sec rep-grid">
      <div><h4>Autonomous routes</h4><canvas class="heat auton big" width="360" height="360" data-team="${esc(id)}" aria-label="${esc(id)}'s autonomous routes"></canvas>
        <p class="cap">Drawn with its own side at the bottom left. A filled dot is where it starts.</p></div>
      <div class="variants">${autonHtml}</div>
    </section>
    <section class="rep-sec rep-grid">
      <div><h4>Trips to Goals</h4>
        <div class="bignums"><div><b>${SC.visits_per_match != null ? Math.round(SC.visits_per_match) : "–"}</b><span>trips to a Goal a match</span></div><div><b>${SC.cycle_s ? Math.round(SC.cycle_s) + " s" : "–"}</b><span>between trips</span></div><div><b>${RB.toggle_visits != null ? Math.round(RB.toggle_visits) : "–"}</b><span>Toggle trips a match</span></div></div>
        <div class="meters">${["own", "neutral", "center", "opp"].map((k) => `<div class="meter"><span class="k">${KN[k]}<small>${(kinds[k] ?? 0).toFixed(1)} a match</small></span>${bar((kinds[k] ?? 0) / ktot)}</div>`).join("")}</div>
        <p class="cap">A trip is any time the robot sits next to a Goal for a second or more. The video shows where it went, not what it scored.</p>
        ${SC.favourites?.length ? `<p class="cap">Goes back to most: ${SC.favourites.slice(0, 3).map(([g, v]) => `${esc(g)} (${v.toFixed(1)} a match)`).join(", ")}.</p>` : ""}</div>
      <div><h4>Cone colours on the robot</h4>${cm ? `<div class="colours"><span class="c-own" style="flex:${cm.own}"></span><span class="c-yel" style="flex:${cm.yellow}"></span><span class="c-oth" style="flex:${cm.other}"></span></div>
        <div class="meters"><div class="meter"><span class="k">Its own colour</span>${bar(cm.own, "own")}</div><div class="meter"><span class="k">Yellow</span>${bar(cm.yellow, "yel")}</div><div class="meter"><span class="k">The other alliance's colour</span>${bar(cm.other, "oth")}</div></div>
        <p class="cap">A rough read of the colour on and around the robot during driver control. Its own paint is removed, but plates and flags still count a little.</p>` : `<p class="cap">Not enough clear views of the robot yet.</p>`}
        <h4 class="mt">The robot</h4><div class="meters">
        ${rankLine("top_fps", "Top speed", "Faster than this share of the robots we tracked")}
        ${rankLine("visits", "Trips to Goals", "More than this share of the robots we tracked")}
        ${rankLine("cycle", "Time between trips", "Quicker than this share of the robots we tracked")}
        ${RB.moving != null ? `<div class="meter"><span class="k">Time spent moving<small>Share of driver control</small></span>${bar(RB.moving)}</div>` : ""}</div>
        ${RB.ft ? `<p class="cap">Drives about ${Math.round(RB.ft)} ft a match.</p>` : ""}</div>
    </section>
    <section class="rep-sec rep-grid">
      <div><h4>Where it drives</h4>${st && st.heat ? `<canvas class="heat big" width="360" height="360" data-team="${esc(id)}" aria-label="Where ${esc(id)} drives"></canvas><p class="cap">Every second of driver control it was seen, drawn with its own side at the bottom left.</p>` : ""}</div>
      <div><h4>Driver control, on average</h4><div class="meters">${rows.map(([k, f, d]) => `<div class="meter"><span class="k">${k}${d ? `<small>${d}</small>` : ""}</span>${bar(avg(f))}</div>`).join("")}</div></div>
    </section>
    ${q.length && e.length ? `<section class="rep-sec"><h4>Qualifications vs eliminations</h4><div class="scroll"><table class="cmp"><thead><tr><th></th><th>Quals (${q.length})</th><th>Elims (${e.length})</th></tr></thead><tbody>
      ${rows.slice(0, 5).map(([k, f]) => `<tr><td>${k}</td><td class="n">${pct(avg(f, q))}</td><td class="n">${pct(avg(f, e))}</td></tr>`).join("")}
      <tr><td>Trips to Goals per match</td><td class="n">${Math.round(avg((m) => m.visits.length, q))}</td><td class="n">${Math.round(avg((m) => m.visits.length, e))}</td></tr>
      <tr><td>Driven per match</td><td class="n">${Math.round(avg((m) => m.ft, q))} ft</td><td class="n">${Math.round(avg((m) => m.ft, e))} ft</td></tr></tbody></table></div></section>` : ""}
    <section class="rep-sec"><h4>Match by match</h4><div class="scroll"><table class="mtab"><thead><tr><th>Match</th><th>With</th><th>Auton</th><th class="n">Score</th><th class="n">Goals</th><th class="n">Other side</th><th class="n">Toggles</th><th class="n">Driven</th><th>Watch</th></tr></thead><tbody>
      ${ms.map((m) => { const ri = A ? A.routes.findIndex((r) => r.members.includes(m.id)) : -1; return `<tr><td><b>${esc(m.match)}</b><small>${esc((m.event || "").replace(/ Signature$| \(Fall 2026\)$/, ""))}</small></td>
        <td><span class="side-${m.alliance[0]}">${m.alliance === "red" ? "Red" : "Blue"}</span> ${esc(m.partner || "")}</td>
        <td>${ri >= 0 ? `<span class="rt"><i style="background:${RC[ri % 6]}"></i>${A.routes[ri].label}</span>` : "–"}</td>
        <td class="n">${(() => { const o = OFF.matches[m.id]; if (!o || o.rs == null) return "–"; const my = m.alliance === "red" ? o.rs : o.bs, th = m.alliance === "red" ? o.bs : o.rs; return `<span style="color:${my > th ? "#7fd99a" : my < th ? "#f08a8a" : "inherit"}">${my}–${th}</span>`; })()}</td>
        <td class="n">${m.visits.length}</td><td class="n">${pct(m.other_side)}</td><td class="n">${pct(m.toggles.own + m.toggles.opp)}</td><td class="n">${Math.round(m.ft)} ft</td>
        <td class="w">${watchBtn(m, -1, "Auton")}${watchBtn(m, m.driver_at, "Driver")}${m.defence_len >= 4 ? watchBtn(m, m.defence_t, "Crossing over") : ""}${m.toggle_first.opp != null ? watchBtn(m, m.toggle_first.opp, "Their Toggle") : ""}</td></tr>`; }).join("")}
    </tbody></table></div></section>
  </div>`;
}
function drawRoutes(c, R) {
  const g = c.getContext("2d"), W = c.width;
  g.fillStyle = "#1c1a17"; g.fillRect(0, 0, W, W);
  const P = fieldLines(g, W);
  const col = ["#f2c230", "#ef3b45", "#4c86ff", "#5fd08a", "#c792ea", "#ff9e57"];
  const col2 = ["#f2c230", "#4c86ff", "#5fd08a", "#c792ea", "#ff9e57", "#ef3b45"], routes = R.sections.auton?.routes || [];
  R.matches.filter((m) => m.route).forEach((m) => {
    const i = Math.max(0, routes.findIndex((r) => r.members.includes(m.id)));
    g.strokeStyle = col2[i % 6]; g.lineWidth = m.id === routes[i]?.typical ? 4 : 2; g.lineJoin = "round"; g.globalAlpha = m.id === routes[i]?.typical ? 0.95 : 0.55;
    g.beginPath(); m.route.forEach(([x, y], j) => { const [u, v] = P(x, y); j ? g.lineTo(u, v) : g.moveTo(u, v); }); g.stroke();
    const [u0, v0] = P(...m.route[0]); g.fillStyle = col2[i % 6]; g.beginPath(); g.arc(u0, v0, 5, 0, 7); g.fill();
  });
  g.globalAlpha = 1;
}

function showTeam(id) {
  const t = T.get(id), out = $("#result");
  if (!t && OFF.teams[id]) { out.innerHTML = `<h3 class="tname disp">${esc(id)}</h3>${officialBlock(id)}<p class="scout-note">No Override video names ${esc(id)} yet.</p>${noteBox(id)}`; return; }
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
    ${officialBlock(id)}
    ${noteBox(id)}
    ${scoutBlock(id)}
    ${matches.map((v) => {
      const mine = v.r?.includes(id) ? ["r", v.r, v.b] : v.b?.includes(id) ? ["b", v.b, v.r] : null;
      return `<div class="mrow"><a class="th" href="${v.u || yt(v.id)}">${thumb(v.id)}</a><div><div class="ev">${esc(v.e || "")}</div><div class="rd">${esc(v.m || "Match")}</div>
      ${mine ? `<div class="al"><span class="side-${mine[0]}">${mine[0] === "r" ? "Red" : "Blue"}</span> with ${mine[1].filter((x) => x !== id).map((x) => tlink(x)).join(" & ") || "partner not named"} <span class="mute">vs</span> ${mine[2].map((x) => tlink(x)).join(" & ")}</div>` : ""}</div>
      <a class="w" href="${v.u || yt(v.id)}">Watch${v.l ? " · " + v.l : ""}</a></div>`;
    }).join("")}
    ${other.length ? `<div class="vids">${other.map((v) => `<a class="vid" href="${v.u || yt(v.id)}"><span class="th">${thumb(v.id)}</span>${esc(v.t)}<br><small>${esc(v.c)}</small></a>`).join("")}</div>` : ""}`;
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-replay]"); if (!b) return;
  document.getElementById("replay").scrollIntoView({ behavior: reduced ? "auto" : "smooth" });
  loadReplay(b.dataset.replay, true, b.dataset.t != null ? +b.dataset.t : null);
});
const drawNew = () => { document.querySelectorAll("canvas.heat:not([data-drawn])").forEach((c) => { c.dataset.drawn = 1; drawHeat(c, TS[c.dataset.team]); }); document.querySelectorAll("canvas.plan:not([data-drawn])").forEach((c) => { c.dataset.drawn = 1; drawPlan(c); }); };
for (const el of [document.getElementById("result"), document.getElementById("prep-out")]) new MutationObserver(drawNew).observe(el, { childList: true, subtree: true });
const q = $("#q"), sugg = $("#sugg");
let list = [], cur = 0;
q.addEventListener("input", () => {
  const s = q.value.trim().toUpperCase();
  const ids = new Set([...T.keys(), ...Object.keys(OFF.teams || {})]);
  const nm = (id) => OFF.teams?.[id]?.name || "";
  list = s ? [...ids].map((id) => ({ id, by: id.startsWith(s) ? 2 : s.length >= 3 && nm(id).toUpperCase().includes(s) ? 1 : 0, v: T.get(id)?.vids.length || 0 }))
    .filter((x) => x.by).sort((a, b) => b.by - a.by || b.v - a.v || a.id.localeCompare(b.id, undefined, { numeric: true })).slice(0, 6) : [];
  cur = 0;
  sugg.innerHTML = list.map((t, i) => `<a href="#team-${t.id}" class="${i ? "" : "cur"}"><b>${t.id}</b><span class="mute">${esc(nm(t.id))}${nm(t.id) ? " · " : ""}${t.v ? `${t.v} video${t.v === 1 ? "" : "s"}` : "no video yet"}</span></a>`).join("");
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
  location.hash = "team-" + (T.has(s) || OFF.teams?.[s] || !list[cur] ? s : list[cur].id);
});
/* scroll a section into view and keep it there while content above it is still loading,
   unless the reader starts scrolling on their own */
let landTimer = null;
function land(el) {
  el.scrollIntoView({ behavior: reduced ? "auto" : "smooth" });
  clearInterval(landTimer);
  let left = 12; const stop = () => { clearInterval(landTimer); ["wheel", "touchstart", "keydown"].forEach((k) => removeEventListener(k, stop)); };
  ["wheel", "touchstart", "keydown"].forEach((k) => addEventListener(k, stop, { passive: true, once: true }));
  landTimer = setInterval(() => {
    const top = el.getBoundingClientRect().top;
    if (Math.abs(top - 72) > 40) el.scrollIntoView({ behavior: "auto" });
    if (--left <= 0) stop();
  }, 250);
}
function route() {
  const h = decodeURIComponent(location.hash.slice(1));
  document.body.dataset.print = h.startsWith("event-") ? "prep" : h.startsWith("team-") || h.startsWith("report-") ? "teams" : "";
  if (h.startsWith("event-")) { const [, eid, ...rest] = h.split("-"); showEvent(eid, rest.join("-").toUpperCase() || null); land($("#prep")); return; }
  if (h.startsWith("report-")) { const id = h.slice(7).toUpperCase(); q.value = id; showReport(id); land($("#result")); return; }
  if (h.startsWith("team-")) { const id = h.slice(5).toUpperCase(); q.value = id; sugg.classList.remove("open"); showTeam(id); land($("#result")); }
}
addEventListener("hashchange", route); route();
if (!location.hash.startsWith("#event-") && cornfield) showEvent(cornfield[0], "2360A");
const rpRoot = document.getElementById("rp");
rpRoot.addEventListener("replay-meta", (e) => { const R = e.detail;
  document.getElementById("rp-sub").innerHTML = `${esc(R.match)} at ${esc(R.event)}: <span style="color:var(--red)">${R.red.join(" &amp; ")}</span> vs <span style="color:var(--blue)">${R.blue.join(" &amp; ")}</span>, followed for the whole match from one YouTube video.${R.stills && R.stills.n ? " The broadcast plays in the corner with the same four robots marked, so you can check it against the real thing." : ""}${R.robots.some((r) => r.named === false) ? " Robot plates are too small to read on this stream, so partners we can't tell apart are shown as Red 1 and Red 2." : ""} <a class="rp-fix" href="${fixLink(R)}" target="_blank" rel="noopener">Wrong team on a robot? Tell us</a>`; });
/* a prefilled GitHub issue: which match, what the replay shows, and room to say what's wrong */
function fixLink(R) {
  const k = { red: 0, blue: 0 };
  const who = (R.robots || []).map((r) => { const a = r.alliance === "blue" ? "blue" : "red"; k[a]++;
    return `- ${a === "blue" ? "Blue" : "Red"} ${k[a]}: ${r.named ? r.team : `not named (${(R[a] || []).join(" or ")})`}`; }).join("\n");
  const body = `Match: ${R.match} at ${R.event} (${R.id})\n\nWhat the replay shows:\n${who}\n\nWhat's wrong (for example "the robot marked 2360A is really 2360C", and the time in the match if it helps):\n\n`;
  return `https://github.com/s1g6r/vexvision/issues/new?title=${encodeURIComponent(`Wrong robot name: ${R.match}, ${R.event}`)}&body=${encodeURIComponent(body)}`;
}
let current = null;
async function loadReplay(id, autoplay, start = null) {
  if (current) { current.destroy(); const c = rpRoot.querySelector("canvas"), n = c.cloneNode(); c.replaceWith(n); }
  rpRoot.querySelector(".rp-play").replaceWith(rpRoot.querySelector(".rp-play").cloneNode(true));
  rpRoot.querySelectorAll(".rp-view button, .rp-speed button, .rp-heat").forEach((b) => b.replaceWith(b.cloneNode(true)));
  rpRoot.querySelector(".rp-range").replaceWith(rpRoot.querySelector(".rp-range").cloneNode(true));
  document.querySelectorAll("#rp-list button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.id === id));
  const pk = IDX.find((x) => x.id === id)?.pack;
  current = await mountReplay(rpRoot, pk ? `data/replays/pack/${pk}.json#${id}` : `data/replays/${id}.json`, { reduced, autoplay, start, names: Object.fromEntries(Object.entries(OFF.teams || {}).map(([k, v]) => [k, v.name])) });
}
Promise.resolve(IDX).then((idx) => {
  const good = idx.filter((x) => !x.error && x.replay !== false && x.calibrated >= 0.6 && x.seen >= 0.6);
  // Matches we could put names on come first: eliminations before qualifications.
  const rank = (x) => (/^SF|^Final/.test(x.match || "") ? 0 : /^QF/.test(x.match || "") ? 1 : /^R16/.test(x.match || "") ? 2 : 3);
  const ours = (x) => ((x.red || []).concat(x.blue || [])).includes("2360A") ? 0 : 1;
  const named = good.filter((x) => (x.sure || 0) >= 2).sort((a, b) => (b.sure || 0) - (a.sure || 0) || ours(a) - ours(b) || rank(a) - rank(b));
  const rest = good.filter((x) => (x.sure || 0) < 2 && x.video !== "FSpOd3gBuqM");
  const list = [...named, { id: "q19", event: "Great Planes Signature", match: "Qual 19", video: "FSpOd3gBuqM" }, ...rest];
  const first = list[0].id;
  loadReplay(first).catch((e) => console.error(e));
  const el = document.getElementById("rp-list");
  if (list.length > 1) {
    el.innerHTML = list.map((x) => `<button type="button" data-id="${x.id}" aria-pressed="${x.id === first}">${thumb(TH?.map?.[x.id] ? x.id : x.video)}<span><b>${esc(x.match || "Match")}</b><span>${esc((x.event || "").replace(/ Signature$/, "").replace(/^Illini /, "").replace(/ \(Fall 2026\)$/, ""))}</span></span></button>`).join("");
    el.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => loadReplay(b.dataset.id, true)));
    watchSpr(el);
  }
});
watchSpr(document);
if ("serviceWorker" in navigator && location.protocol === "https:") navigator.serviceWorker.register("sw.js").catch(() => {});
window.__ready = true; window.done = true;
