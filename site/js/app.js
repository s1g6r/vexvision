import { GOALS, TOGGLES, TOGGLE_LEN, TILE, HALF, WALL, tapeSegments, allianceScore, quadrantOf, sideOf, QUADRANT_COLOR } from "./field.js";
import * as C from "./calib.js";
import { loadModel, detect } from "./detect.js";
import { initHero } from "./hero.js";

const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const NS = "http://www.w3.org/2000/svg";
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ---------- field map (SVG, field mm, y up) --------------------------------------- */
const octagon = (x, y, r) => Array.from({ length: 8 }, (_, i) => { const a = Math.PI / 8 + i * Math.PI / 4; return `${(x + r * Math.cos(a)).toFixed(0)},${(-y - r * Math.sin(a)).toFixed(0)}`; }).join(" ");
// Turn the map so the side of the field nearest the camera is at the bottom, like the video.
function viewRotation(H, w, h) {
  if (!H) return 0;
  const cam = C.cameraFromH(H, w, h), phi = Math.atan2(-cam.pos[1], cam.pos[0]) * 180 / Math.PI;
  return ((Math.round((90 - phi) / 90) * 90) % 360 + 360) % 360;
}
function fieldSVG(svg, { robots = [], matched = null, toggles = {}, trails = [], interactive = false, rot = 0, labels = null } = {}) {
  let s = `<g transform="rotate(${rot})">`;
  for (let i = -3; i < 3; i++) for (let j = -3; j < 3; j++) s += `<rect class="tile ${(i + j) & 1 ? "b" : ""}" x="${i * TILE}" y="${j * TILE}" width="${TILE}" height="${TILE}"/>`;
  for (const seg of tapeSegments(2)) { const a = seg[0], b = seg[seg.length - 1]; s += `<line class="tape" x1="${a[0]}" y1="${-a[1]}" x2="${b[0]}" y2="${-b[1]}" stroke-width="44"/>`; }
  s += `<rect class="wall" x="${-WALL - 17}" y="${-WALL - 17}" width="${2 * WALL + 34}" height="${2 * WALL + 34}" rx="40"/>`;
  for (const [q, [x, y]] of Object.entries(TOGGLES)) {
    const c = toggles[q], col = c === "red" ? "var(--red)" : c === "blue" ? "var(--blue)" : c === "yellow" ? "var(--pin)" : "light-dark(#9aa1ab,#6b737e)";
    const horiz = q === "N" || q === "S", L = TOGGLE_LEN;
    s += `<rect class="${interactive ? "tg-svg" : ""}" data-q="${q}" tabindex="${interactive ? 0 : -1}" role="${interactive ? "button" : "presentation"}" aria-label="${interactive ? `Toggle ${q}, ${c || "yellow"}` : ""}" x="${horiz ? x - L / 2 : x - 40}" y="${horiz ? -y - 40 : -y - L / 2}" width="${horiz ? L : 80}" height="${horiz ? 80 : L}" rx="40" fill="${col}" stroke="var(--panel)" stroke-width="16"/>`;
  }
  for (const g of GOALS) {
    const seen = matched && matched.has(g.name);
    s += `<polygon class="goal-${g.kind}" points="${octagon(g.x, g.y, g.kind === "center" ? 150 : 115)}" stroke="${seen ? "var(--pin)" : "var(--panel)"}" stroke-width="${seen ? 38 : 18}"/>`;
  }
  if (labels) {
    const at = { N: [0, 900], E: [900, 0], S: [0, -900], W: [-900, 0], mid: [0, -330] };
    for (const [q, txt] of Object.entries(labels)) {
      const [x, y] = at[q];
      s += `<text class="qlab" text-anchor="middle" x="${x}" y="${-y - 60}">${esc(txt.name)}</text>`;
      txt.parts.forEach((p, i) => { s += `<text class="qcount" text-anchor="middle" x="${x + (i - (txt.parts.length - 1) / 2) * 260}" y="${-y + 120}" fill="${p.c}">${esc(p.t)}</text>`; });
    }
  }
  for (const t of trails) s += `<polyline class="trail" stroke="${t.color}" points="${t.pts.map(p => `${p[0].toFixed(0)},${(-p[1]).toFixed(0)}`).join(" ")}"/>`;
  robots.forEach((r, i) => {
    const cls = r.alliance || "unknown", lab = r.label ?? String(i + 1), cl = v => Math.max(-HALF + 240, Math.min(HALF - 240, v));
    s += `<g class="robot ${cls}" data-i="${i}" transform="translate(${cl(r.x).toFixed(0)},${(-cl(r.y)).toFixed(0)})"><rect x="-228" y="-228" width="456" height="456" rx="90"/><text text-anchor="middle" dy="60" transform="rotate(${-rot})" font-size="${lab.length > 3 ? 150 : 190}">${esc(lab)}</text></g>`;
  });
  svg.innerHTML = s + "</g>";
}

/* ---------- frame overlay (canvas over the image) ---------------------------------- */
function drawOverlay(cv, w, h, { H, goals = [], robots = [] }) {
  cv.width = w; cv.height = h;
  const g = cv.getContext("2d");
  g.clearRect(0, 0, w, h);
  g.lineCap = "round"; g.lineJoin = "round";
  if (H) {
    const line = (pts, col, lw) => { g.beginPath(); pts.forEach(([u, v], i) => (i ? g.lineTo(u, v) : g.moveTo(u, v))); g.strokeStyle = col; g.lineWidth = lw; g.stroke(); };
    line([...C.fieldPolygon(H), C.fieldPolygon(H)[0]], "rgba(245,196,0,.95)", Math.max(2, w / 420));
    for (const seg of tapeSegments(12)) line(C.toImg(H, seg), "rgba(245,196,0,.9)", Math.max(1.5, w / 600));
    GOALS.forEach((gl, i) => {
      const [u, v] = C.toImg(H, [[gl.x, gl.y]])[0];
      g.beginPath(); g.arc(u, v, Math.max(4, w / 220), 0, 7);
      g.fillStyle = gl.kind === "red" ? "#e5484d" : gl.kind === "blue" ? "#2d7ff9" : "#111"; g.fill();
      g.lineWidth = 2; g.strokeStyle = "#fff"; g.stroke();
    });
  }
  g.lineWidth = Math.max(2, w / 500);
  for (const d of goals) { const [x0, y0, x1, y1] = d.box; g.strokeStyle = "rgba(255,255,255,.75)"; g.setLineDash([6, 5]); g.strokeRect(x0, y0, x1 - x0, y1 - y0); }
  g.setLineDash([]);
  robots.forEach((r, i) => {
    const [x0, y0, x1, y1] = r.box, rad = Math.min(14, (x1 - x0) / 5);
    g.strokeStyle = "#f5c400"; g.lineWidth = Math.max(3, w / 380);
    g.beginPath(); g.roundRect(x0, y0, x1 - x0, y1 - y0, rad); g.stroke();
    const tag = String(r.label ?? i + 1), fs = Math.max(14, w / 55);
    g.font = `700 ${fs}px "Barlow Condensed", sans-serif`;
    const tw = g.measureText(tag).width + fs * .7;
    g.fillStyle = "#f5c400"; g.beginPath(); g.roundRect(x0, Math.max(0, y0 - fs * 1.25), tw, fs * 1.2, fs * .6); g.fill();
    g.fillStyle = "#1a1500"; g.fillText(tag, x0 + fs * .35, Math.max(fs, y0 - fs * .3));
  });
}

/* ---------- data ------------------------------------------------------------------- */
let GALLERY = [], FACTS = null, HERO = null;
async function loadData() {
  try { const r = await fetch("data/hero.json"); if (r.ok) HERO = await r.json(); } catch {}
  try { const r = await fetch("data/gallery.json"); if (r.ok) GALLERY = await r.json(); } catch {}
  try { const r = await fetch("data/facts.json"); if (r.ok) FACTS = await r.json(); } catch {}
}

/* ---------- router ----------------------------------------------------------------- */
const VIEWS = ["home", "matches", "replay", "scoring"], ANCHORS = { analyze: "analyze", read: "read" };
let lastView = null;
function route() {
  const h = location.hash.slice(1);
  const v = VIEWS.includes(h) ? h : "home";
  document.querySelectorAll(".view").forEach(s => (s.hidden = s.dataset.view !== v));
  document.querySelectorAll(".top nav a").forEach(a => { if (a.getAttribute("href") === "#" + v) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  if (v === "matches") renderMatches();
  if (ANCHORS[h]) requestAnimationFrame(() => document.getElementById(ANCHORS[h]).scrollIntoView({ behavior: reduced ? "auto" : "smooth" }));
  else if (v !== lastView) window.scrollTo(0, 0);
  lastView = v;
}

/* ---------- analyze ---------------------------------------------------------------- */
let models = null;
async function getModels(status) {
  if (models) return models;
  status("Warming up (about 29 MB the first time)…");
  const ext = await fetch("models/goals.onnx", { method: "HEAD" }).then(r => (r.ok ? "onnx" : "json"), () => "json");
  const [goals, robots] = await Promise.all([
    loadModel(`models/goals.${ext}`, ["goal_red", "goal_blue", "goal_neutral", "goal_center"]),
    loadModel(`models/robots.${ext}`, ["robot"]),
  ]);
  models = { goals, robots };
  return models;
}

function showResult({ src, w, h, H, goals, robots, caption, matchedNames, quality = null }) {
  const img = $("#a-img");
  img.src = src; img.alt = caption || "Broadcast frame";
  drawOverlay($("#a-cv"), w, h, { H, goals, robots });
  fieldSVG($("#a-map"), { rot: viewRotation(H, w, h), robots: robots.filter(r => r.floor).map((r, i) => ({ x: r.floor[0], y: r.floor[1], label: r.label ?? String(i + 1), alliance: r.alliance })), matched: matchedNames });
  $("#a-cap").innerHTML = caption || "";
  const placed = robots.filter(r => r.floor);
  const inch = v => Math.round(v / 25.4);
  $("#a-read").innerHTML = `<h3>${placed.length ? `${placed.length} of 4 robots on the map` : H ? "No robots placed" : "Field not mapped"}</h3>
    <ul>${placed.map(r => `<li><b>${esc(r.label)}</b><span>${esc(quadName(quadrantOf(...r.floor)))}, ${sideOf(...r.floor)} side<small>${Math.abs(inch(r.floor[0]))} in ${r.floor[0] >= 0 ? "east" : "west"} and ${Math.abs(inch(r.floor[1]))} in ${r.floor[1] >= 0 ? "north" : "south"} of the centre goal</small></span></li>`).join("")}</ul>
`;
  if (!reduced) { const s = document.querySelector(".a-right"); s.animate([{ opacity: .35, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }], { duration: 380, easing: "cubic-bezier(.2,.7,.2,1)" }); }
}

// A match has exactly four robots on the field: keep the four most confident detections,
// with no more than three on one side of the Autonomous Line.
function capRobots(rs) {
  const out = [], side = { red: 0, blue: 0 };
  for (const r of [...rs].sort((a, b) => b.conf - a.conf)) {
    const sd = r.floor ? sideOf(...r.floor) : null;
    if (out.length >= 4 || (sd && side[sd] >= 3)) continue;
    out.push(r); if (sd) side[sd]++;
  }
  return out;
}

function matchedGoalNames(H, goals, w) {
  const set = new Set();
  if (!H) return set;
  for (const p of C.goalPoints(goals.map(d => ({ ...d, kind: d.cls.replace("goal_", "") })))) {
    GOALS.forEach(g => { const [u, v] = C.toImg(H, [[g.x, g.y]])[0]; if (g.kind === p[2] && Math.hypot(u - p[0], v - p[1]) < 0.03 * w) set.add(g.name); });
  }
  return set;
}

function showGalleryItem(it, extra = "") {
  const robots = capRobots(it.robots).map((r, i) => ({ ...r, label: String(i + 1) }));
  showResult({ src: it.img, w: it.w, h: it.h, H: it.H, goals: it.goals, robots, quality: it.q, matchedNames: matchedGoalNames(it.H, it.goals, it.w),
    caption: `${esc(it.event || it.title)}${it.match ? " · " + esc(it.match) : ""} · <a href="https://www.youtube.com/watch?v=${esc(it.video)}" target="_blank" rel="noopener">source video</a>${extra}` });
}

async function analyzeFile(file) {
  const status = (m, err, ok) => { const s = $("#status"); s.textContent = m; s.classList.toggle("err", !!err); s.classList.toggle("ok", !!ok); };
  const scan = $("#a-scan");
  if (!file || !file.type.startsWith("image/")) return status("That file is not an image. Use a PNG or JPG screenshot.", true);
  const url = URL.createObjectURL(file), im = new Image();
  im.src = url;
  try { await im.decode(); } catch { return status("Could not open that image.", true); }
  const w = im.naturalWidth, h = im.naturalHeight;
  $("#a-img").src = url; drawOverlay($("#a-cv"), w, h, {}); scan.classList.add("on");
  try {
    const m = await getModels(status);
    status("Looking for the robots…");
    const t0 = performance.now();
    const [goalsDet, robotsDet] = [await detect(m.goals, im, w, h, 0.1), await detect(m.robots, im, w, h, 0.35)];
    status("Placing them on the field…");
    await new Promise(r => setTimeout(r, 0));
    const res = calibrate(im, w, h, goalsDet);
    let robots = robotsDet.map(r => ({ ...r }));
    if (res) { const cam = C.cameraFromH(res.H, w, h); robots.forEach(r => { const p = C.robotFloor(r.box, res.H, cam); if (C.inField(...p)) r.floor = p; }); robots = robots.filter(r => r.floor); }
    robots = capRobots(robots).map((r, i) => ({ ...r, label: String(i + 1) }));
    scan.classList.remove("on");
    const secs = ((performance.now() - t0) / 1000).toFixed(1);
    showResult({ src: url, w, h, H: res?.H, goals: goalsDet, robots, quality: res?.quality ?? null, matchedNames: matchedGoalNames(res?.H, goalsDet, w),
      caption: `Your screenshot · read in ${secs} s` });
    document.querySelectorAll(".sample").forEach(b => b.setAttribute("aria-pressed", "false"));
    if (!res) status("Couldn't line up the field in that shot. Try a wider frame that shows most of the field.", true);
    else status(`${robots.length} robot${robots.length === 1 ? "" : "s"} placed on the field.`, false, true);
  } catch (e) {
    console.error(e); scan.classList.remove("on");
    status("This browser couldn't run the analyzer. Everything else on the site still works.", true);
  }
}

function calibrate(im, w, h, goalsDet) {
  const pts = C.goalPoints(goalsDet.map(d => ({ ...d, kind: d.cls.replace("goal_", "") })));
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

function initAnalyze() {
  const drop = $("#drop"), file = $("#file");
  drop.addEventListener("click", () => file.click());
  drop.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); file.click(); } });
  file.addEventListener("change", () => analyzeFile(file.files[0]));
  ["dragenter", "dragover"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", e => analyzeFile(e.dataTransfer.files[0]));
  document.addEventListener("paste", e => { const f = [...(e.clipboardData?.files || [])][0]; if (f && location.hash.replace("#", "") in { "": 1, analyze: 1 }) analyzeFile(f); });
  const picks = GALLERY.filter(g => g.featured).slice(0, 4);
  $("#samples").innerHTML = picks.map((p, i) => `<button class="sample" data-i="${i}" aria-pressed="${i === 0}"><img src="${esc(p.img)}" alt="" loading="lazy"><span><b>${esc(p.match)}</b><small>${esc(p.event)}</small></span></button>`).join("");
  $("#samples").addEventListener("click", e => {
    const b = e.target.closest(".sample"); if (!b) return;
    document.querySelectorAll(".sample").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
    showGalleryItem(picks[+b.dataset.i]); $("#status").textContent = "";
  });
  if (picks[0]) showGalleryItem(picks[0]);
  else fieldSVG($("#a-map"));
}

/* ---------- matches ---------------------------------------------------------------- */
let matchesInit = false;
function renderMatches() {
  if (!matchesInit) {
    matchesInit = true;
    const ev = [...new Set(GALLERY.map(g => g.event).filter(Boolean))].sort();
    $("#m-event").innerHTML += ev.map(e => `<option>${esc(e)}</option>`).join("");
    ["#m-team", "#m-event", "#m-robots"].forEach(s => $(s).addEventListener("input", renderMatches));
    $("#m-cards").addEventListener("click", e => { const c = e.target.closest(".card"); if (c) openDetail(GALLERY[+c.dataset.i]); });
  }
  const team = $("#m-team").value.trim().toUpperCase(), ev = $("#m-event").value, four = $("#m-robots").checked;
  const list = GALLERY.map((g, i) => [g, i]).filter(([g]) => (!team || [...(g.red || []), ...(g.blue || [])].some(t => t.startsWith(team))) && (!ev || g.event === ev) && (!four || capRobots(g.robots).length === 4));
  $("#m-count").textContent = `${GALLERY.length} moments from ${new Set(GALLERY.map(g => g.video)).size} matches, each with the robots on the field map.`;
  $("#m-empty").hidden = list.length > 0;
  renderCards($("#m-cards"), list.slice(0, 240));
}
function renderCards(el, list) {
  el.innerHTML = list.map(([g, i]) => `<button class="card" data-i="${i}">
      <div class="thumb"><img decoding="async" src="${esc(g.img)}" alt=""><svg class="mini" viewBox="-1950 -1950 3900 3900" data-mini="${i}"></svg></div>
      <div class="meta"><h3>${esc(g.match ? `${g.match} · ${g.event}` : g.event || "Match frame")}</h3><small>${capRobots(g.robots).length} of 4 robots on the map${g.clock ? ` · ${esc(g.clock)} left` : ""}</small>
      <div class="chips">${(g.red || []).map(t => `<span class="chip red">${esc(t)}</span>`).join("")}${(g.blue || []).map(t => `<span class="chip blue">${esc(t)}</span>`).join("")}${g.score ? `<span class="chip">${esc(g.score)}</span>` : ""}</div></div></button>`).join("");
  el.querySelectorAll("svg[data-mini]").forEach(s => { const g = GALLERY[+s.dataset.mini]; fieldSVG(s, { rot: viewRotation(g.H, g.w, g.h), robots: capRobots(g.robots).map(r => ({ x: r.floor[0], y: r.floor[1], label: "" })) }); });
}
function openDetail(g) {
  const d = $("#m-detail"), img = $("#d-img");
  const robots = capRobots(g.robots).map((r, i) => ({ ...r, label: String(i + 1) }));
  img.src = g.img; img.alt = `${g.event || ""} ${g.match || ""}`;
  d.showModal();
  drawOverlay($("#d-cv"), g.w, g.h, { H: g.H, goals: g.goals, robots });
  fieldSVG($("#d-map"), { rot: viewRotation(g.H, g.w, g.h), robots: robots.filter(r => r.floor).map(r => ({ x: r.floor[0], y: r.floor[1], label: r.label })), matched: matchedGoalNames(g.H, g.goals, g.w) });
  const pos = robots.filter(r => r.floor).map(r => `${r.label}: ${quadName(quadrantOf(...r.floor))}, ${sideOf(...r.floor)} side`).join(" · ") || "No robot placed";
  const rows = [["Event", g.event || g.title], ["Match", g.match || "not on screen"], ["Clock", g.clock ?? "not read"], ["Red", (g.red || []).join(" & ") || "not read"], ["Blue", (g.blue || []).join(" & ") || "not read"], ["Score on screen", g.score || "not shown"], ["Robots on the map", pos]];
  $("#d-info").innerHTML = rows.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("") + `<div><dt>Source</dt><dd><a href="https://www.youtube.com/watch?v=${esc(g.video)}" target="_blank" rel="noopener">${esc(g.channel || "YouTube")}</a></dd></div>`;
}
function quadName(q) { return { N: "North quadrant", E: "East quadrant", S: "South quadrant", W: "West quadrant", mid: "Midfield" }[q]; }

/* ---------- replay ----------------------------------------------------------------- */
let R = null, raf = 0;
function loadReplay(data, note) {
  if (!data || !Array.isArray(data.robots)) { $("#r-note").textContent = "That file is not a vexvision match file (it has no robots list)."; return; }
  const robots = data.robots.map(r => ({ ...r, path: (r.path || []).map(p => ({ t: p[0], x: p[1], y: p[2] })) }));
  const T = Math.max(1, ...robots.flatMap(r => r.path.map(p => p.t)));
  R = { data, robots, T, t: 0, playing: false };
  $("#r-note").textContent = note || "";
  ["#r-play", "#r-t"].forEach(s => ($(s).disabled = false));
  $("#r-t").max = Math.round(T * 10);
  const fmt = v => (v == null ? "" : v);
  $("#r-robots tbody").innerHTML = robots.map(r => `<tr><td>${esc(r.team || "#" + r.track)}</td><td><span class="chip ${r.alliance}">${esc(r.alliance)}</span></td><td class="n">${fmt(r.distance_ft)} ft</td><td class="n">${fmt(r.placements)}</td><td class="n">${fmt(r.toggles)}</td><td class="n">${fmt(r.points_seen)}</td><td class="n">${fmt(r.points_inferred)}</td><td>${r.ended_in_midfield ? "Yes" : "No"}</td></tr>`).join("");
  const ev = data.events || [];
  $("#r-events").innerHTML = ev.length ? ev.map((e, i) => `<li data-t="${e.t}" data-i="${i}"><time>${clock(e.t)}</time><span>${esc(describe(e))}</span></li>`).join("") : `<li><time></time><span>No scoring events in this file.</span></li>`;
  const sc = data.score_check || {};
  $("#r-check").innerHTML = sc.vision_score ? `<h3 style="margin-top:18px">Against the referees</h3><p>Camera: red ${sc.vision_score.red}, blue ${sc.vision_score.blue}.${sc.official ? ` Official: red ${sc.official.red}, blue ${sc.official.blue}. Missed by the camera: red ${sc.gap?.red ?? "?"}, blue ${sc.gap?.blue ?? "?"}.` : " No official score was given."}</p>` : "";
  drawReplay(0);
}
const clock = t => { const s = Math.max(0, Math.round(t)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
const describe = e => e.type === "placement" ? `${e.team || "Robot " + (e.robot ?? "?")} placed ${e.halves} ${e.colour} half${e.halves > 1 ? "s" : ""} on goal ${e.goal}${e.auton ? " (auton)" : ""}` : e.type === "toggle" ? `${e.team || "Robot " + (e.robot ?? "?")} flipped the ${e.quadrant} Toggle to ${e.to}` : e.type;
function posAt(path, t) {
  if (!path.length) return null;
  let i = path.findIndex(p => p.t >= t);
  if (i <= 0) return path[i === 0 ? 0 : path.length - 1];
  const a = path[i - 1], b = path[i], k = (t - a.t) / Math.max(1e-6, b.t - a.t);
  return { x: a.x + k * (b.x - a.x), y: a.y + k * (b.y - a.y) };
}
function drawReplay(t) {
  if (!R) return;
  R.t = t;
  const robots = R.robots.map(r => { const p = posAt(r.path, t); return p && { x: p.x, y: p.y, alliance: r.alliance, label: (r.team || "#" + r.track).slice(0, 6) }; }).filter(Boolean);
  const trails = R.robots.map(r => ({ color: r.alliance === "red" ? "var(--red)" : "var(--blue)", pts: r.path.filter(p => p.t <= t && p.t >= t - 8).map(p => [p.x, p.y]) }));
  fieldSVG($("#r-map"), { robots, trails, toggles: R.data.final_state?.toggles && t >= R.T - 0.5 ? R.data.final_state.toggles : {} });
  $("#r-t").value = Math.round(t * 10);
  $("#r-clock").textContent = clock(t);
  document.querySelectorAll("#r-events li[data-t]").forEach(li => li.classList.toggle("now", Math.abs(+li.dataset.t - t) < 1));
}
function initReplay() {
  $("#r-file").addEventListener("change", async e => { const f = e.target.files[0]; if (!f) return; try { loadReplay(JSON.parse(await f.text()), `Opened ${f.name}.`); } catch { $("#r-note").textContent = "That file could not be read as JSON."; } });
  $("#r-sample").addEventListener("click", async () => {
    try { const d = await (await fetch("data/sample_replay.json")).json(); loadReplay(d, "Practice file with made-up robots and team numbers. Not a real match."); }
    catch { $("#r-note").textContent = "The sample file is missing."; }
  });
  $("#r-t").addEventListener("input", e => drawReplay(+e.target.value / 10));
  $("#r-play").addEventListener("click", () => {
    if (!R) return;
    R.playing = !R.playing; $("#r-play").textContent = R.playing ? "Pause" : "Play";
    if (R.t >= R.T) R.t = 0;
    let last = performance.now();
    const step = now => { if (!R.playing) return; const nt = Math.min(R.T, R.t + (now - last) / 1000 * 2); last = now; drawReplay(nt); if (nt >= R.T) { R.playing = false; $("#r-play").textContent = "Play"; return; } raf = requestAnimationFrame(step); };
    cancelAnimationFrame(raf); raf = requestAnimationFrame(step);
  });
  $("#r-events").addEventListener("click", e => { const li = e.target.closest("li[data-t]"); if (li) drawReplay(+li.dataset.t); });
  fieldSVG($("#r-map"));
}

/* ---------- scoring ---------------------------------------------------------------- */
const S = { toggles: { N: "yellow", E: "yellow", S: "yellow", W: "yellow" }, halves: { N: {}, E: {}, S: {}, W: {}, mid: {} }, mid: { red: 0, blue: 0 } };
const QLAB = { N: "North quadrant", E: "East quadrant", S: "South quadrant", W: "West quadrant", mid: "Midfield" };
function renderScoring() {
  const col = { red: "var(--red)", blue: "var(--blue)", yellow: "light-dark(#a37f00,#f5c400)" };
  const labels = Object.fromEntries(["N", "E", "S", "W", "mid"].map(q => [q, { name: q === "mid" ? "" : q, parts: ["red", "blue", "yellow"].filter(c => S.halves[q][c]).map(c => ({ c: col[c], t: S.halves[q][c] })) }]));
  fieldSVG($("#s-map"), { labels, toggles: S.toggles, interactive: true, robots: [
    ...Array.from({ length: S.mid.red }, (_, i) => ({ x: [-330, 0][i], y: [0, -330][i], alliance: "red", label: "R" })),
    ...Array.from({ length: S.mid.blue }, (_, i) => ({ x: [330, 0][i], y: [0, 330][i], alliance: "blue", label: "B" })),
  ] });
  const midOwner = S.mid.red === S.mid.blue ? null : S.mid.red > S.mid.blue ? "red" : "blue", auton = $("#s-auton").value || null;
  $("#s-red").textContent = allianceScore(S.halves, S.toggles, midOwner, S.mid, auton, "red");
  $("#s-blue").textContent = allianceScore(S.halves, S.toggles, midOwner, S.mid, auton, "blue");
  $("#s-quads").innerHTML = ["N", "E", "S", "W", "mid"].map(q => `<div class="quad"><h3>${QLAB[q]}${q !== "mid" ? ` <button class="btn tg" data-tq="${q}">Toggle: ${S.toggles[q]}</button>` : ""}</h3>
    ${["red", "blue", "yellow"].map(c => `<div class="ctr"><span>${c} halves</span><button data-q="${q}" data-c="${c}" data-d="-1" aria-label="Fewer ${c} halves, ${QLAB[q]}">-</button><b>${S.halves[q][c] || 0}</b><button data-q="${q}" data-c="${c}" data-d="1" aria-label="More ${c} halves, ${QLAB[q]}">+</button></div>`).join("")}
    ${q === "mid" ? ["red", "blue"].map(a => `<div class="ctr"><span>${a} robots</span><button data-m="${a}" data-d="-1" aria-label="Fewer ${a} robots in the Midfield">-</button><b>${S.mid[a]}</b><button data-m="${a}" data-d="1" aria-label="More ${a} robots in the Midfield">+</button></div>`).join("") : `<p class="note" style="margin:6px 0 0">${QUADRANT_COLOR[q]} quadrant</p>`}</div>`).join("");
}
function initScoring() {
  const cycle = q => { const o = ["yellow", "red", "blue"]; S.toggles[q] = o[(o.indexOf(S.toggles[q]) + 1) % 3]; renderScoring(); };
  $("#s-map").addEventListener("click", e => { const t = e.target.closest("[data-q]"); if (t) cycle(t.dataset.q); });
  $("#s-map").addEventListener("keydown", e => { const t = e.target.closest("[data-q]"); if (t && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); cycle(t.dataset.q); } });
  $("#s-quads").addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.dataset.tq) return cycle(b.dataset.tq);
    if (b.dataset.m) { S.mid[b.dataset.m] = Math.max(0, Math.min(2, S.mid[b.dataset.m] + +b.dataset.d)); }
    else { const h = S.halves[b.dataset.q]; h[b.dataset.c] = Math.max(0, Math.min(60, (h[b.dataset.c] || 0) + +b.dataset.d)); }
    renderScoring();
  });
  $("#s-auton").addEventListener("change", renderScoring);
  $("#s-reset").addEventListener("click", () => { S.toggles = { N: "yellow", E: "yellow", S: "yellow", W: "yellow" }; S.halves = { N: {}, E: {}, S: {}, W: {}, mid: {} }; S.mid = { red: 0, blue: 0 }; $("#s-auton").value = ""; renderScoring(); });
  renderScoring();
}

/* ---------- home: stats, ticker, cards, how ---------------------------------------- */
function initHome() {
  // ticker of matches read
  const items = GALLERY.filter(g => g.match && (g.red || []).length === 2 && (g.blue || []).length === 2);
  const one = items.map(g => `<span class="tk"><em>${esc(g.match)}</em><span class="r">${esc(g.red.join(" "))}</span><span class="vs">vs</span><span class="b">${esc(g.blue.join(" "))}</span><span class="vs">${esc(g.event)}</span></span>`).join("");
  $("#ticker").innerHTML = one + one;
  // cards
  const four = GALLERY.map((g, i) => [g, i]).filter(([g]) => capRobots(g.robots).length >= 3);
  renderCards($("#home-cards"), four.slice(0, 6));
  $("#home-cards").addEventListener("click", e => { const c = e.target.closest(".card"); if (c) openDetail(GALLERY[+c.dataset.i]); });
  $("#m-close").addEventListener("click", () => $("#m-detail").close());
  // counters
  const io = new IntersectionObserver(es => es.forEach(en => {
    if (!en.isIntersecting) return;
    io.unobserve(en.target);
    const el = en.target, to = +el.dataset.count, dec = +(el.dataset.dec || 0), suf = el.dataset.suf || "";
    const fmt = v => (dec ? v.toFixed(dec) : Math.round(v).toLocaleString("en-US")) + suf;
    if (reduced) { el.textContent = fmt(to); return; }
    const t0 = performance.now(), d = 1300;
    const step = now => { const k = Math.min(1, (now - t0) / d), e = 1 - (1 - k) ** 3; el.textContent = fmt(to * e); if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }), { threshold: .4 });
  document.querySelectorAll("[data-count]").forEach(el => io.observe(el));
  if (HERO) initHero(HERO, viewRotation(HERO.H, HERO.w, HERO.h), reduced);
}

/* ---------- start ------------------------------------------------------------------ */
{
  await loadData();
  initAnalyze(); initReplay(); initScoring(); initHome();
  addEventListener("hashchange", route);
  route();
}
