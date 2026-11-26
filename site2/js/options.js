/* Layout options under trial. Loaded only when the address has ?prep=b, ?team=c and so on (or ?try).
   Each area keeps its current version as option A; this file adds the others. Once one option per area is chosen,
   it moves into main.js and the rest of this file goes. */
const V = window.VV;
const { $, esc, OFF, REP, TS, ALT, UI } = V;

export const AREAS = {
  prep: { name: "Event prep: your matches", opts: { a: "As it is", b: "Each team once", c: "One match at a time" } },
  pick: { name: "Event prep: pick list", opts: { a: "As it is", b: "Cards on phones", c: "Short rows on phones" } },
  team: { name: "Team page and report", opts: { a: "Overview + report", b: "One page, tabs", c: "One page, fold-out sections" } },
  rp: { name: "Replay picker", opts: { a: "As it is", b: "Search and events" } },
  read: { name: "Read a frame", opts: { a: "As it is", b: "Plainer robot list", c: "Folded away" } },
  evpick: { name: "Event list", opts: { a: "As it is", b: "Grouped by played and coming up" } },
};
const reg = (area, key, impl) => { (ALT[area] ||= {})[key] = impl; };

/* ---------- shared bits ---------- */
const GOAL_FIRST = (r) => [...r.steps.stops.map(([, p]) => p), r.steps.end].find((p) => V.GKEY[p]);
const theirs = (s) => s.replace(/^its own/, "their own");
function autonGist(n) {
  const A = REP[n]?.sections?.auton, r = A?.routes?.[0];
  if (!r) return "";
  const how = A.seen === 1 ? "seen once" : `${r.count} of ${A.seen}`;
  if (r.steps.moved_m < 0.6) return `Auton barely moves (${how})`;
  return `Auton to ${theirs(GOAL_FIRST(r) || r.steps.end)} (${how})`;
}
const recLine = (t) => [t.rank ? `${V.ord(t.rank)} here` : "", t.record || "", t.avg != null ? `${Math.round(t.avg)} a match` : ""].filter(Boolean).join(" · ");
const shortM = (m) => m.replace(/^Qual(ifier|ification)? #?/i, "Q");
const PLAN_NOTE = `<p class="opt-note">On every field picture your side is at the bottom left. Each line is a team's most-run auton, and the filled dot is where it starts.</p>`;
const planNoCaption = (me, partner, op) => V.planBlock(me, partner, op).replace(/<p class="role">Your side is bottom left\.[^<]*<\/p>/, "");

/* a team card said once: the auton is described in one line, so the "watch for" list skips the auton */
function cardOnce(n, side, ev, me, extra = "") {
  const t = ev.teams.find((x) => x.n === n) || {}, R = REP[n];
  const A = R?.sections?.auton, route = A?.routes?.[0];
  const W = R ? V.watchouts(R).filter((x) => !/^Auton/.test(x)) : [];
  return `<div class="tc ${side}" id="tm-${esc(n)}"><div class="n"><a href="#team-${esc(n)}">${esc(n)}</a><small>${esc(t.name || "")}</small></div>
    <div class="role">${esc(recLine(t))}${t.skills ? ` · skills ${t.skills}` : ""}</div>
    ${extra}
    ${R?.tags?.length ? `<div class="tags">${R.tags.map((x) => `<span class="tag">${esc(x)}</span>`).join("")}</div>` : ""}
    ${route ? `<div class="tc-auton"><canvas class="heat auton big" width="200" height="200" data-team="${esc(n)}" aria-label="${esc(n)}'s autonomous routes"></canvas><div class="line"><b>Auton${A.seen > 1 ? `, ${route.count} of ${A.seen}` : ", seen once"}:</b> ${esc(route.text)}.${A.routes.length > 1 ? ` <span class="role">${A.routes.length - 1} other route${A.routes.length > 2 ? "s" : ""}.</span>` : ""}</div></div>` : ""}
    ${W.length ? `<ul class="watch-list">${W.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    ${V.NOTES[n] ? `<div class="tc-note"><b>Your note:</b> ${esc(V.NOTES[n].length > 160 ? V.NOTES[n].slice(0, 157) + "…" : V.NOTES[n])}</div>` : ""}
    ${R ? `<div class="tc-links">${route ? V.watchBtn({ id: route.typical }, -1, "Watch their auton") : ""}<a class="more" href="#team-${esc(n)}">Team page</a></div><div class="role tc-src">From ${V.nOn(R)} on video</div>` : `<div class="role">Not on video yet</div>`}</div>`;
}

/* ---------- Event prep B: each match is short, and each team's card is shown once ---------- */
reg("prep", "b", {
  matches(ev, me, mine) {
    const meets = new Map();
    mine.forEach((m, mi) => { const v = V.matchView(m, me);
      v.partner.forEach((p) => { if (!meets.has(p)) meets.set(p, { side: v.side, list: [] }); meets.get(p).list.push([mi, "with"]); });
      v.op.forEach((o) => { if (!meets.has(o)) meets.set(o, { side: v.oside, list: [] }); meets.get(o).list.push([mi, "against"]); }); });
    const row = (n, side, clash) => { const t = ev.teams.find((x) => x.n === n) || {}, R = REP[n];
      return `<li class="who ${side}"><div><span class="who-n"><a href="#team-${esc(n)}">${esc(n)}</a><small>${esc(t.name || "")}</small></span>
        <span class="who-l">${esc(recLine(t))}</span>
        ${R ? `<span class="who-l">${R.tags?.[0] ? `<b>${esc(R.tags[0])}</b> · ` : ""}${esc(autonGist(n) || "No auton seen")}</span>` : `<span class="who-l mute">Not on video yet</span>`}
        ${clash ? `<span class="who-c">${esc(clash)}</span>` : ""}</div>
        <button type="button" class="watch" data-goto="tm-${esc(n)}">Card</button></li>`; };
    const matchesHtml = mine.map((m, mi) => { const v = V.matchView(m, me);
      return `<div class="pm pm-b" id="pm-${mi}"><div class="pm-head"><b>${esc(m.m)}</b><span>${v.red ? "Red" : "Blue"} alliance${v.win != null ? ` · ${Math.round(v.win * 100)}% to win going in` : ""}</span>${v.done ? `<span class="res">${v.res} ${v.my}–${v.th}</span>` : ""}</div>
        <div class="pm-b-body">${planNoCaption(me, v.partner[0], v.op)}
        <ul class="who-list">${v.partner.map((p) => row(p, v.side, V.autonClash(me, p, true))).join("")}${v.op.map((o) => row(o, v.oside, V.autonClash(me, o, false))).join("")}</ul></div></div>`; }).join("");
    const cards = [...meets].map(([n, { side, list }]) => {
      const w = list.filter(([, k]) => k === "with").map(([i]) => i), a = list.filter(([, k]) => k === "against").map(([i]) => i);
      const link = (i) => `<button type="button" class="lnk" data-goto="pm-${i}">${esc(shortM(mine[i].m))}</button>`;
      const extra = `<div class="meets">${w.length ? `<span>With you in ${w.map(link).join(", ")}</span>` : ""}${a.length ? `<span>Against you in ${a.map(link).join(", ")}</span>` : ""}</div>`;
      return cardOnce(n, side, ev, me, extra); }).join("");
    return `<div class="pm-sec"><h4 class="disp" style="font-size:34px;margin:30px 0 4px">${esc(me)}'s matches</h4>${V.jumpStrip(mine, me)}${PLAN_NOTE}${matchesHtml}</div>
      <div class="pm-sec"><h4 class="disp" style="font-size:34px;margin:40px 0 4px">Who you'll meet</h4>
      <p class="scout-note">Every partner and opponent once, in the order you meet them.</p><div class="pm-grid know">${cards}</div></div>`;
  },
});

/* ---------- Event prep C: one match at a time, the next one first ---------- */
let pcState = null;
function pcPanel() {
  const { ev, me, mine, i } = pcState, m = mine[i], v = V.matchView(m, me);
  return `<div class="pm pm-c"><div class="pm-head"><b>${esc(m.m)}</b><span>${v.red ? "Red" : "Blue"} alliance${v.win != null ? ` · ${Math.round(v.win * 100)}% to win going in` : ""}</span>${v.done ? `<span class="res">${v.res} ${v.my}–${v.th}</span>` : ""}</div>
    ${planNoCaption(me, v.partner[0], v.op)}
    <div class="pm-grid">${v.partner.map((p) => cardOnce(p, v.side, ev, me, clashLine(V.autonClash(me, p, true)))).join("")}${v.op.map((o) => cardOnce(o, v.oside, ev, me, clashLine(V.autonClash(me, o, false)))).join("")}</div>
    <div class="pc-step">${i > 0 ? `<button type="button" class="btn ghost" data-pc="${i - 1}">Back to ${esc(shortM(mine[i - 1].m))}</button>` : "<span></span>"}${i < mine.length - 1 ? `<button type="button" class="btn ghost" data-pc="${i + 1}">On to ${esc(shortM(mine[i + 1].m))}</button>` : ""}</div></div>`;
}
const clashLine = (c) => c ? `<div class="who-c">${esc(c)}</div>` : "";
function pcTabs() {
  const { me, mine, i } = pcState;
  return mine.map((m, k) => { const v = V.matchView(m, me), res = v.done ? v.res[0] : "";
    return `<button type="button" role="tab" data-pc="${k}" aria-selected="${k === i}" class="${k === pcState.next ? "next" : ""}${res ? " r-" + res : ""}">${esc(shortM(m.m))}${res ? ` <small>${res}</small>` : k === pcState.next ? " <small>next</small>" : ""}</button>`; }).join("");
}
reg("prep", "c", {
  matches(ev, me, mine) {
    let last = -1; mine.forEach((m, k) => { if (m.rs != null && (m.rs || m.bs)) last = k; });
    const next = last + 1 < mine.length ? last + 1 : -1;
    pcState = { ev, me, mine, i: next >= 0 ? next : 0, next };
    return `<div class="pm-sec"><h4 class="disp" style="font-size:34px;margin:30px 0 4px">${esc(me)}'s matches</h4>
      <nav class="pm-jump pc-tabs" role="tablist" aria-label="Your matches">${pcTabs()}</nav>${PLAN_NOTE}<div id="pc-panel">${pcPanel()}</div></div>`;
  },
});
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-pc]"); if (!b || !pcState) return;
  pcState.i = +b.dataset.pc;
  document.querySelector(".pc-tabs").innerHTML = pcTabs();
  document.getElementById("pc-panel").innerHTML = pcPanel();
  document.querySelector(`.pc-tabs [data-pc="${pcState.i}"]`)?.scrollIntoView({ block: "nearest", inline: "center" });
  if (b.closest(".pc-step")) document.querySelector(".pc-tabs").scrollIntoView({ block: "start" });
});
/* printing in option C still gives every match, not only the one on screen */
addEventListener("beforeprint", () => { const el = document.getElementById("pc-panel"); if (!el || !pcState) return; const keep = pcState.i;
  el.innerHTML = pcState.mine.map((_, k) => { pcState.i = k; return pcPanel(); }).join(""); pcState.i = keep; });
addEventListener("afterprint", () => { const el = document.getElementById("pc-panel"); if (el && pcState) el.innerHTML = pcPanel(); });
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-goto]"); if (!b) return;
  const el = document.getElementById(b.dataset.goto); if (!el) return;
  el.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash");
});

/* ---------- Pick list: read the rows the current table would show, then lay them out another way ---------- */
function pickRows(ev, me, key) {
  const tpl = document.createElement("template"); tpl.innerHTML = V.pickTable(ev, me, key);
  const heads = [...tpl.content.querySelectorAll("thead th")].map((th) => th.textContent.trim());
  const col = (name) => heads.indexOf(name);
  return { heads, rows: [...tpl.content.querySelectorAll("tbody tr")].map((tr) => { const td = [...tr.children];
    const cell = (name) => col(name) >= 0 ? td[col(name)] : null;
    return { n: tr.dataset.pickN, cls: tr.className, r: td[0].textContent.trim(), name: td[1].querySelector("small")?.textContent || "",
      rating: cell("Rating")?.textContent.trim(), record: cell("Record")?.textContent.trim(), avg: cell("Points")?.textContent.trim(), skills: cell("Skills")?.textContent.trim(),
      mix: cell("Mix")?.innerHTML, how: cell("How it plays")?.innerHTML, fit: cell("With you")?.innerHTML, take: td[td.length - 1].innerHTML }; }), table: tpl.innerHTML };
}
const dash = (v) => v && v !== "–" ? v : "–";
reg("pick", "b", (ev, me, key) => {
  const { rows, table } = pickRows(ev, me, key);
  return `<div class="pick-b">${table}<ol class="pk-cards">${rows.map((x) => `<li class="pk-card ${x.cls}">
    <div class="pk-top"><span class="pk-r">${esc(x.r)}</span><div class="pk-t"><a href="#team-${esc(x.n)}">${esc(x.n)}</a><small>${esc(x.name)}</small></div><span class="pk-rt"><b>${esc(dash(x.rating))}</b><small>rating</small></span></div>
    <div class="pk-nums">${esc(dash(x.record))} · ${esc(dash(x.avg))} points · skills ${esc(dash(x.skills))}${x.mix ? ` · mix ${x.mix}` : ""}</div>
    <div class="pk-how">${x.how || ""}${x.fit && !/>–</.test(x.fit) ? x.fit : ""}${x.take ? `<span class="pk-act">${x.take}</span>` : ""}</div></li>`).join("")}</ol></div>`;
});
reg("pick", "c", (ev, me, key) => {
  const { rows, heads } = pickRows(ev, me, key);
  return `<div class="pk-c">${V.pickTable(ev, me, key).replace(/ data-pick-n="[^"]*"/g, "")}<div class="pk-c-head" aria-hidden="true"><span>#</span><span>Team</span><span>Rating</span><span></span></div>${rows.map((x) => `<details class="pk-row ${x.cls}" data-pick-n="${esc(x.n)}">
    <summary><span class="pk-r">${esc(x.r)}</span><span class="pk-t"><b>${esc(x.n)}</b><small>${esc(x.name)}</small></span><span class="pk-rt">${esc(dash(x.rating))}</span><span class="pk-act">${x.take}</span></summary>
    <div class="pk-more"><dl><div><dt>Record</dt><dd>${esc(dash(x.record))}</dd></div><div><dt>Points a match</dt><dd>${esc(dash(x.avg))}</dd></div><div><dt>Skills</dt><dd>${esc(dash(x.skills))}</dd></div>${x.mix ? `<div><dt>Your mix</dt><dd>${x.mix}</dd></div>` : ""}</dl>
    <div class="pk-how">${x.how || ""}${x.fit && !/>–</.test(x.fit) ? x.fit : ""}</div><a class="more" href="#team-${esc(x.n)}">Team page</a></div></details>`).join("")}</div>`;
});
/* in option C the Mark picked button sits in the row's summary: don't let it fold the row open */
document.addEventListener("click", (e) => { if (e.target.closest(".pk-row summary .take")) e.preventDefault(); }, true);

/* ---------- Team page B: one page with tabs ---------- */
function teamHead(id) {
  const rows = V.coverage(id).rows, pc = new Map();
  for (const r of rows) { const mine = r.red?.includes(id) ? r.red : r.blue?.includes(id) ? r.blue : []; for (const p of mine) if (p !== id) pc.set(p, (pc.get(p) || 0) + 1); }
  const partners = [...pc].sort((a, b) => b[1] - a[1]).slice(0, 4).map(([k]) => k);
  return `<h3 class="tname disp">${esc(id)}</h3>${OFF.teams[id]?.name ? `<p class="rep-sub">${esc(OFF.teams[id].name)}</p>` : ""}
    ${partners.length ? `<div class="tstats"><span>Partnered with ${partners.map((p) => V.tlink(p)).join(", ")}</span></div>` : ""}`;
}
const known = (id) => V.T.get(id) || OFF.teams[id] || TS[id];
const unknown = (id) => `<div class="empty"><p><b>No Override video names ${esc(id)} yet.</b> A team shows up once a match, reveal or skills video title includes its number.</p></div>`;
function scoutSummary(id) {
  const R = REP[id], st = TS[id];
  if (!st?.n || !R) return st ? `<p class="scout-note">We follow ${esc(id)}'s alliance in ${st.matches.length} match${st.matches.length === 1 ? "" : "es"}, but we can't yet tell which robot is ${esc(id)}.</p>` : "";
  const W = V.watchouts(R);
  return `${R.tags?.length ? `<div class="tags">${R.tags.map((x) => `<span class="tag">${esc(x)}</span>`).join("")}</div>` : ""}${W.length ? `<ul class="watch-list">${W.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}`;
}
function usedList(P) { return `<details class="used"><summary>The ${P.n} match${P.n === 1 ? "" : "es"} used for scouting</summary><ul class="ml cards">${P.cards}</ul></details>`; }
let tbState = null;
function tbRender(tab) {
  const { id, P, cov } = tbState; tbState.tab = tab;
  const tabs = [["overview", "Overview"], P?.A ? ["auton", "Auton"] : null, P ? ["driving", "Driving"] : null, ["matches", "Matches"]].filter(Boolean);
  const panel = {
    overview: () => `${V.officialBlock(id)}<div class="scout"><div class="scout-head"><b>Scouting</b></div>${scoutSummary(id)}${cov.html}</div>${V.noteBox(id)}`,
    auton: () => P.auton,
    driving: () => P.goals + P.driver + P.robot,
    matches: () => `${cov.rows.length ? V.matchList(id, cov.rows, 999) : `<p class="scout-note">No Override video of ${esc(id)} yet.</p>`}${P ? usedList(P) : ""}`,
  }[tab]();
  $("#result").innerHTML = `<div class="tb">${teamHead(id)}<div class="tb-tabs" role="tablist" aria-label="${esc(id)}">${tabs.map(([k, l]) => `<button type="button" role="tab" data-tb="${k}" aria-selected="${k === tab}">${esc(l)}</button>`).join("")}</div>
    <div class="tb-panel" role="tabpanel">${panel}</div></div>`;
}
reg("team", "b", {
  team(id, tab = "overview") { if (!known(id)) { $("#result").innerHTML = unknown(id); return; } tbState = { id, P: V.reportParts(id), cov: V.coverage(id) }; tbRender(tab); },
  report(id) { ALT.team.b.team(id, REP[id]?.sections?.auton ? "auton" : "driving"); },
});
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-tb]"); if (!b || !tbState) return;
  tbRender(b.dataset.tb);
  const top = document.querySelector(".tb-tabs"); if (top.getBoundingClientRect().top < 60) top.scrollIntoView({ block: "start" });
});

/* ---------- Team page C: one page, every section folds open in place ---------- */
function foldTeam(id, open) {
  if (!known(id)) { $("#result").innerHTML = unknown(id); return; }
  const P = V.reportParts(id), cov = V.coverage(id), o = OFF.teams[id], S = P?.R?.sections || {};
  const off = o?.season ? [o.season.rank ? `${V.ord(o.season.rank)} of ${o.season.of?.toLocaleString() || "?"}` : "", o.season.record].filter(Boolean).join(" · ") : "";
  const kinds = P?.kinds || {}, top = Object.entries(kinds).sort((a, b) => b[1] - a[1])[0];
  const KN = { own: "own Alliance Goals", neutral: "neutral Goals", center: "the Center Goal", opp: "the other alliance's Goals" };
  const rk = S.ranks?.top_fps;
  const fold = (title, sub, body, isOpen) => `<details class="fold"${isOpen ? " open" : ""}><summary><b>${title}</b>${sub ? `<span>${esc(sub)}</span>` : ""}</summary><div class="fold-body">${body}</div></details>`;
  const A = P?.A;
  $("#result").innerHTML = `<div class="tf">${teamHead(id)}
    <div class="scout tf-sum">${scoutSummary(id) || `<p class="scout-note">No scouting for ${esc(id)} yet.</p>`}</div>
    ${o ? fold("Official results", off, V.officialBlock(id), open) : ""}
    ${A ? fold("Autonomous", A.seen === 1 ? "Seen once" : `Route ${A.routes[0].label} in ${A.routes[0].count} of ${A.seen} matches`, P.auton, open) : ""}
    ${P ? fold("Which Goals and what it carries", top && P.ktot > 1 ? `Most often ${KN[top[0]]}` : "", P.goals, open) : ""}
    ${P ? fold("Driver control", S.defence?.other_side != null ? `${V.pct(S.defence.other_side)} of it on the other side` : "", P.driver, open) : ""}
    ${P ? fold("The robot", rk != null ? `Faster than ${V.pct(rk)} of robots we tracked` : "", P.robot, open) : ""}
    ${fold("Matches", `${cov.rows.length} on video, ${cov.named} used for scouting`, `${cov.html}${cov.rows.length ? V.matchList(id, cov.rows) : ""}${P ? usedList(P) : ""}`, false)}
    ${V.noteBox(id)}</div>`;
}
reg("team", "c", { team: (id) => foldTeam(id, false), report: (id) => foldTeam(id, true) });

/* ---------- Replay picker B: find a match by team or event instead of a strip of 900 ---------- */
reg("rp", "b", (el, list, load, first) => {
  const evs = new Map(); list.forEach((x) => { const e = V.evName(x.event || "").replace(/ Signature$/, "") || "Other"; evs.set(e, (evs.get(e) || 0) + 1); });
  const evOrder = [...evs.keys()].sort((a, b) => V.evDate(b).localeCompare(V.evDate(a)));
  el.className = "rpf"; el.removeAttribute("role");
  el.innerHTML = `<div class="rpf-bar"><label class="sr" for="rpf-q">Find a replay</label><input id="rpf-q" placeholder="Team number, like 2360A" spellcheck="false" autocomplete="off">
    <select id="rpf-ev" aria-label="Event"><option value="">All ${list.length} matches</option>${evOrder.map((e) => `<option value="${esc(e)}">${esc(e)} (${evs.get(e)})</option>`).join("")}</select></div>
    <p class="rpf-count" id="rpf-count" role="status"></p><div class="matches rp-list" id="rpf-res" role="group" aria-label="Pick a replay"></div><button type="button" class="btn ghost" id="rpf-more" hidden>Show more</button>`;
  let shown = 12;
  const draw = () => {
    const q = $("#rpf-q").value.trim().toUpperCase(), e = $("#rpf-ev").value;
    let hit = list.filter((x) => (!e || (V.evName(x.event || "").replace(/ Signature$/, "") || "Other") === e) && (!q || (x.red || []).concat(x.blue || []).some((t) => t.startsWith(q))));
    if (q || e) hit = hit.sort((a, b) => V.evDate(b.event).localeCompare(V.evDate(a.event)) || V.rank(a.match) - V.rank(b.match));
    $("#rpf-count").textContent = q || e ? `${hit.length} match${hit.length === 1 ? "" : "es"}${q ? ` with ${q}` : ""}${e ? ` at ${e}` : ""}` : "Best-read matches first. Type a team to find theirs.";
    $("#rpf-res").innerHTML = hit.slice(0, shown).map((x) => `<button type="button" data-id="${x.id}" aria-pressed="false">${V.rpThumb(x)}<span><b>${esc(x.match || "Match")}</b><span>${esc((x.red || []).join(" & "))}${x.red ? " vs " : ""}${esc((x.blue || []).join(" & "))}</span><span>${esc(V.evName(x.event || "").replace(/ Signature$/, ""))}</span></span></button>`).join("") || `<p class="scout-note">No replay with that team yet.</p>`;
    $("#rpf-more").hidden = hit.length <= shown;
    V.watchSpr();
  };
  el.addEventListener("input", (ev) => { if (ev.target.id === "rpf-q") { shown = 12; draw(); } });
  el.addEventListener("change", (ev) => { if (ev.target.id === "rpf-ev") { shown = 12; draw(); } });
  el.addEventListener("click", (ev) => {
    if (ev.target.closest("#rpf-more")) { shown += 24; draw(); return; }
    const b = ev.target.closest("#rpf-res button"); if (!b) return;
    el.querySelectorAll("#rpf-res button").forEach((x) => x.setAttribute("aria-pressed", x === b));
    load(b.dataset.id, true);
  });
  draw();
});

/* ---------- Read a frame B: one plain line per robot ---------- */
function readFacts() {
  const box = $("#s-facts"), i = +($("#matches [aria-pressed=true]")?.dataset.i ?? 1), f = V.frames[i];
  if (!f || box.dataset.plain === String(i)) return;
  box.dataset.plain = String(i); box.classList.add("plain");
  const half = (r) => { const z = V.where(r).split(" · "); return `${z[0].replace("Red side", "on the red half").replace("Blue side", "on the blue half").replace("In the midfield", "in the midfield")}, ${z[1].replace("from centre", "from the centre")}`; };
  box.innerHTML = `<ul class="rf">${f.robots.map((r, k) => `<li style="--c:var(--${r.side || "mute"})"><i></i><b>${esc(r.team || `Robot ${k + 1}`)}</b><span>${r.side ? `${r.side === "red" ? "Red" : "Blue"} alliance` : "Alliance not read"}, ${esc(half(r))}</span></li>`).join("")}</ul>`;
}
reg("read", "b", () => {
  const p = document.querySelector("#read .head p");
  if (p) p.textContent = "Pick a broadcast frame, then flip between what the camera saw and the field rebuilt from it. Drag to walk around. Your own screenshot works too.";
  new MutationObserver(() => { if ($("#s-facts .rf")) return; delete $("#s-facts").dataset.plain; readFacts(); }).observe($("#s-facts"), { childList: true });
  readFacts();
});
/* ---------- Read a frame C: the home page already shows a rebuilt field twice, so this one waits behind a button ---------- */
reg("read", "c", () => {
  const sec = $("#read"), wrap = sec.querySelector(".wrap");
  const t = document.createElement("div"); t.className = "read-teaser";
  t.innerHTML = `<h2 class="disp">Try it on one frame</h2><p>Pick a broadcast screenshot, or drop in your own, and flip between the camera and the field rebuilt from it.</p><button type="button" class="btn ghost">Open the frame reader</button>`;
  wrap.prepend(t); sec.classList.add("folded");
  t.querySelector("button").addEventListener("click", () => { sec.classList.remove("folded"); t.remove(); dispatchEvent(new Event("resize")); V.pickMatch(1); });
});

/* ---------- Event list B: played events and coming-up events in their own groups ---------- */
reg("evpick", "b", (evList) => {
  const opt = ([k, e]) => `<option value="${k}">${esc(e.short.replace(/ \(Fall 2026\)$/, ""))} · ${esc(e.date)}</option>`;
  const played = evList.filter(([, e]) => e.matches.some((m) => m.rs != null && (m.rs || m.bs)));
  const sched = evList.filter(([, e]) => e.matches.length && !played.some(([, p]) => p === e));
  const later = evList.filter(([, e]) => !e.matches.length).reverse();
  return [[`Schedule out`, sched], [`Played, with results`, played], [`Coming up, no schedule yet`, later]].filter(([, l]) => l.length).map(([g, l]) => `<optgroup label="${g}">${l.map(opt).join("")}</optgroup>`).join("");
});

/* ---------- a small panel to switch options while comparing ---------- */
const bar = document.createElement("div");
bar.className = "opt-bar";
const url = (area, k) => { const q = new URLSearchParams(location.search); if (k === "a") q.delete(area); else q.set(area, k); q.set("try", "1"); return `?${q}${location.hash}`; };
bar.innerHTML = `<button type="button" class="opt-toggle" aria-expanded="false">Layout options</button><div class="opt-panel" hidden>
  ${Object.entries(AREAS).map(([area, { name, opts }]) => `<div class="opt-area"><span>${esc(name)}</span><div class="seg">${Object.entries(opts).map(([k, l]) => `<a href="${url(area, k)}" aria-current="${(UI[area] || "a") === k}" title="${esc(l)}">${k.toUpperCase()}<small>${esc(l)}</small></a>`).join("")}</div></div>`).join("")}
  <a class="opt-all" href="options.html">See every option side by side</a></div>`;
document.body.append(bar);
bar.querySelector(".opt-toggle").addEventListener("click", (e) => { const p = bar.querySelector(".opt-panel"); p.hidden = !p.hidden; e.currentTarget.setAttribute("aria-expanded", !p.hidden); });
addEventListener("hashchange", () => bar.querySelectorAll(".opt-area a").forEach((a) => { const h = a.getAttribute("href").split("#")[0]; a.setAttribute("href", h + location.hash); }));

/* ---------- styles for the options above ---------- */
const css = document.createElement("style");
css.textContent = `
.opt-note{color:var(--mute);font-size:14px;line-height:1.5;margin:10px 0 0;max-width:70ch}
.pm-b-body{display:grid;grid-template-columns:220px 1fr;gap:18px;align-items:start}
.pm-b .pm-plan{display:block}.pm-b .pm-plan canvas{width:100%;max-width:220px}
.who-list{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.who{display:flex;gap:12px;justify-content:space-between;align-items:center;background:var(--panel2);border-radius:16px;padding:12px 14px;border-left:3px solid var(--line)}
.who.r{border-left-color:var(--red)}.who.b{border-left-color:var(--blue)}
.who > div{display:grid;gap:3px;min-width:0}
.who-n{display:flex;gap:8px;align-items:baseline}.who-n a{font:800 22px "Big Shoulders Display",sans-serif;color:var(--ink);text-decoration:none}.who-n small{color:var(--mute);font-size:12.5px}
.who-l{font-size:13.5px;color:#c9c2b5;line-height:1.4}.who-l b{color:#f4d77a;font-weight:600}.who-l.mute{color:var(--mute)}
.who-c{font-size:13.5px;color:#f4d77a;line-height:1.4}
.meets{display:flex;flex-direction:column;gap:2px;font-size:13.5px;color:#c9c2b5}
.lnk{all:unset;cursor:pointer;color:var(--ink);text-decoration:underline;text-underline-offset:3px}
.lnk:focus-visible{outline:2px solid var(--gold);border-radius:4px}
.flash{animation:optflash 1.2s ease}@keyframes optflash{0%{box-shadow:0 0 0 2px var(--gold)}100%{box-shadow:0 0 0 0 transparent}}
.pc-tabs button[aria-selected=true]{background:var(--ink);color:#0c0b0a;border-color:var(--ink)}.pc-tabs button[aria-selected=true] small{color:#0c0b0a}
.pc-step{display:flex;justify-content:space-between;gap:10px;margin-top:16px;flex-wrap:wrap}
.pick-b .pk-cards{display:none;list-style:none;margin:0;padding:0;gap:10px}
.pk-card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:14px;display:grid;gap:8px}
.pk-card.me{border-color:rgba(242,194,48,.5)}.pk-card.taken{opacity:.45}
.pk-top{display:grid;grid-template-columns:28px 1fr auto;gap:10px;align-items:center}
.pk-r{font:800 20px "Big Shoulders Display",sans-serif;color:var(--mute)}
.pk-t{display:grid}.pk-t a,.pk-t b{font:800 22px "Big Shoulders Display",sans-serif;color:var(--ink);text-decoration:none}.pk-t small{color:var(--mute);font-size:12.5px}
.pk-rt{display:grid;justify-items:end}.pk-rt b{font:800 26px/1 "Big Shoulders Display",sans-serif}.pk-rt small{color:var(--mute);font-size:11.5px}
.pk-nums{font-size:13.5px;color:#c9c2b5}
.pk-how{display:flex;flex-wrap:wrap;gap:6px;align-items:center}.pk-card .pk-act{margin-left:auto}.pk-how .tags{display:contents}
@media(max-width:640px){.pick-b table{display:none}.pick-b .pk-cards{display:grid}.pm-b-body{grid-template-columns:1fr}.pm-b .pm-plan,.pm-c .pm-plan{display:grid;grid-template-columns:132px 1fr;gap:14px;align-items:center}.pm-b .pm-plan canvas,.pm-c .pm-plan canvas{width:132px;height:132px}}
.pk-c{display:grid;gap:6px}.pk-c-head,.pk-row{display:none}
@media(max-width:640px){.pk-c > table{display:none}.pk-c-head{display:grid}.pk-row{display:block}}
.pk-c-head,.pk-row summary{display:grid;grid-template-columns:32px minmax(0,1fr) 60px auto;gap:10px;align-items:center}
.pk-c-head{font-size:12.5px;color:var(--mute);padding:0 14px}.pk-c-head span:nth-child(3){text-align:right}
.pk-row{background:var(--panel);border:1px solid var(--line);border-radius:16px}
.pk-row summary{padding:10px 14px;cursor:pointer;list-style:none}.pk-row summary::-webkit-details-marker{display:none}
.pk-row summary:focus-visible{outline:2px solid var(--gold);border-radius:16px}
.pk-row .pk-rt{font:800 22px "Big Shoulders Display",sans-serif;text-align:right;display:block}
.pk-row.me{border-color:rgba(242,194,48,.5)}.pk-row.taken{opacity:.45}
.pk-more{padding:0 14px 14px 56px;display:grid;gap:10px}
.pk-more dl{display:grid;grid-template-columns:repeat(auto-fit,minmax(90px,1fr));gap:8px;margin:0}.pk-more dt{color:var(--mute);font-size:12px}.pk-more dd{margin:0;font-weight:600}
.pk-act .take{white-space:nowrap}
@media(max-width:640px){.pk-more{padding-left:14px}}
.tb-tabs{position:sticky;top:64px;z-index:5;display:flex;gap:6px;overflow-x:auto;padding:10px 0;margin:18px 0 8px;background:var(--bg);scrollbar-width:none}
.tb-tabs::-webkit-scrollbar{display:none}
.tb-tabs button{flex:none;font:600 14.5px Geist,sans-serif;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:10px 16px;cursor:pointer}
.tb-tabs button[aria-selected=true]{background:var(--ink);color:#0c0b0a;border-color:var(--ink)}
.tb-tabs button:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
.tb-panel > .rep-sec:first-child{margin-top:12px}
.tf-sum{margin:18px 0 8px}
.fold{margin-top:12px;border-radius:20px;background:var(--panel);border:1px solid var(--line)}
.fold > summary{list-style:none;cursor:pointer;padding:16px 18px;display:grid;gap:2px}
.fold > summary::-webkit-details-marker{display:none}
.fold > summary b{font:800 24px "Big Shoulders Display",sans-serif;display:flex;justify-content:space-between;gap:10px}
.fold > summary b::after{content:"+";color:var(--mute);font:500 22px Geist,sans-serif}
.fold[open] > summary b::after{content:"–"}
.fold > summary span{color:var(--mute);font-size:14px}
.fold > summary:focus-visible{outline:2px solid var(--gold);border-radius:20px}
.fold-body{padding:0 18px 18px}
.fold-body > .rep-sec{margin-top:0;padding:0;border:0;background:none}
.fold-body > .rep-sec > div:first-child > h4:first-child,.fold-body > .rep-sec > h4:first-child{display:none}
.fold-body .off{margin:0}
.rpf-bar{display:flex;gap:10px;flex-wrap:wrap}
.rpf-bar input,.rpf-bar select{flex:1 1 220px;min-height:48px;border-radius:999px;border:1px solid var(--line);background:var(--panel);color:var(--ink);font:500 16px Geist,sans-serif;padding:0 18px}
.rpf-count{color:var(--mute);font-size:14px;margin:12px 0 8px}
#rpf-res button > span > span{display:block}
#rpf-more{margin:10px 0 18px}
.rf{list-style:none;margin:0;padding:0;display:grid;gap:8px;grid-column:1/-1}
.rf li{display:grid;grid-template-columns:12px auto 1fr;gap:10px;align-items:baseline;font-size:14.5px;color:#c9c2b5}
.rf i{width:10px;height:10px;border-radius:50%;background:var(--c)}.rf b{font:800 20px "Big Shoulders Display",sans-serif;color:var(--ink)}
#s-facts.plain{display:block}
#read.folded .wrap > :not(.read-teaser){display:none}
.read-teaser{display:grid;gap:12px;justify-items:start;max-width:60ch}
.read-teaser h2{font-size:clamp(36px,5vw,56px);margin:0}.read-teaser p{color:#c9c2b5;font-size:17px;line-height:1.5;margin:0}
.opt-bar{position:fixed;left:14px;bottom:14px;z-index:60;font:500 14px Geist,sans-serif;max-width:calc(100vw - 28px)}
.opt-toggle{all:unset;cursor:pointer;background:var(--gold);color:#111;font-weight:700;padding:11px 16px;border-radius:999px;box-shadow:0 6px 24px rgba(0,0,0,.5)}
.opt-toggle:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.opt-panel{position:absolute;left:0;bottom:54px;width:min(420px,calc(100vw - 28px));max-height:70vh;overflow:auto;background:var(--panel2);border:1px solid var(--line);border-radius:20px;padding:14px;display:grid;gap:12px;box-shadow:0 12px 40px rgba(0,0,0,.6)}
.opt-panel[hidden]{display:none}
.opt-area{display:grid;gap:6px}.opt-area > span{color:var(--mute);font-size:13px}
.opt-area .seg{display:flex;flex-wrap:wrap;gap:4px;border-radius:16px}
.opt-area .seg a{flex:1 1 0;min-width:84px;text-decoration:none;color:var(--mute);padding:8px 10px;border-radius:12px;display:grid;gap:2px;font-weight:700}
.opt-area .seg a small{font-weight:500;font-size:11.5px;line-height:1.3}
.opt-area .seg a[aria-current=true]{background:var(--ink);color:#0c0b0a}
.opt-all{color:var(--ink);font-size:14px}
@media print{.opt-bar,.pc-tabs,.pc-step{display:none!important}}
`;
document.head.append(css);
