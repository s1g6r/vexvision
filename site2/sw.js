// Keeps vexvision usable on bad event wifi: the page and the data you've opened stay on the device.
// Everything is fetched fresh when the network answers and served from the device when it doesn't.
const CACHE = "vexvision-v1";
const SHELL = ["./", "index.html", "js/main.js", "js/options.js", "js/replay.js", "js/field3d.js", "js/analyze.js",
  "js/vendor/three.module.js", "js/vendor/three.core.js",
  "data/official.json", "data/reports.json", "data/team_stats.json", "data/videos.json", "data/thumbs.json", "data/replays/index.json",
  "fonts/big-shoulders-display-latin-800-normal.woff2", "fonts/big-shoulders-display-latin-900-normal.woff2",
  "fonts/geist-latin-400-normal.woff2", "fonts/geist-latin-500-normal.woff2", "fonts/geist-latin-600-normal.woff2"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {}).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin || req.headers.has("range")) return;
  // Network first, so updates show at once; the copy on the device is the fallback when the network fails.
  e.respondWith(caches.open(CACHE).then(async (c) => {
    try {
      const res = await fetch(req);
      if (res.ok && res.type === "basic") c.put(req, res.clone());
      return res;
    } catch (err) {
      const hit = await c.match(req, { ignoreSearch: true });
      if (hit) return hit;
      throw err;
    }
  }));
});
