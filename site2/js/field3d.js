// A procedural VEX Override field, built in metres, that can be viewed from the
// exact camera a broadcast frame was shot with. Field axes follow the GPS
// convention (x right, y toward the far wall); three.js uses y up, so a field
// point (x, y) sits at (x, 0, -y).
import * as THREE from "./vendor/three.module.js";

const TILE = 0.6096, WALL = 1.79, HALF = 3 * TILE;
const GOALS = [
  ["C", 0, 0, "center", 0.2227], ["NW", -0.6, 1.2, "neutral", 0.1465], ["NE", 0.6, 1.2, "blue", 0.0825],
  ["EN", 1.2, 0.6, "blue", 0.0825], ["ES", 1.2, -0.6, "neutral", 0.1465], ["SE", 0.6, -1.2, "neutral", 0.1465],
  ["SW", -0.6, -1.2, "red", 0.0825], ["WS", -1.2, -0.6, "red", 0.0825], ["WN", -1.2, 0.6, "neutral", 0.1465],
];
const COL = { red: 0xd8262e, blue: 0x1f63d6, yellow: 0xf2c230, ink: 0x111214 };

function rng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }
const at = (x, y, h = 0) => new THREE.Vector3(x, h, -y);

function canvasTex(w, h, draw, srgb = true) {
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

// Foam tiles, their seams and the white tape, painted into one texture.
function floorTexture(base = 112, seam = "rgba(40,42,45,.55)", tapeCol = "#f4f4f1") {
  const N = 2048, s = N / (2 * HALF);
  const px = (x, y) => [(x + HALF) * s, (HALF - y) * s];
  return canvasTex(N, N, (g) => {
    const r = rng(7);
    for (let i = 0; i < 6; i++) for (let j = 0; j < 6; j++) {
      const v = base + Math.round((r() - 0.5) * 6);
      g.fillStyle = `rgb(${v - 4},${v},${v + 3})`;
      g.fillRect(i * N / 6, j * N / 6, N / 6, N / 6);
    }
    const img = g.getImageData(0, 0, N, N), d = img.data;          // foam grain
    for (let i = 0; i < d.length; i += 4) { const n = (r() - 0.5) * 14; d[i] += n; d[i + 1] += n; d[i + 2] += n; }
    g.putImageData(img, 0, 0);
    g.strokeStyle = seam; g.lineWidth = 3;            // tile seams with puzzle tabs
    for (let k = 1; k < 6; k++) {
      const p = k * N / 6;
      for (const vert of [true, false]) {
        g.beginPath();
        for (let t = 0; t <= N; t += N / 48) {
          const wob = Math.sin(t / N * 6 * Math.PI * 8) > 0.6 ? 7 : 0;
          vert ? g.lineTo(p + wob, t) : g.lineTo(t, p + wob);
        }
        g.stroke();
      }
    }
    const tape = (pts, w) => {
      g.strokeStyle = tapeCol; g.lineWidth = w * s; g.lineCap = "butt"; g.beginPath();
      pts.forEach(([x, y], i) => { const [u, v] = px(x, y); i ? g.lineTo(u, v) : g.moveTo(u, v); });
      g.stroke();
    };
    const c = TILE / 2, m = TILE, gap = 0.025 / Math.SQRT2;
    tape([[-WALL, -WALL], [-c, -c]], 0.05); tape([[c, c], [WALL, WALL]], 0.05);
    for (const o of [-gap, gap]) { tape([[-WALL + o, WALL + o], [-c + o, c + o]], 0.024); tape([[c + o, -c + o], [WALL + o, -WALL + o]], 0.024); }
    tape([[m, 0], [0, m], [-m, 0], [0, -m], [m, 0]], 0.05);
  });
}

function perforated(color = "#c9ced3") {
  return canvasTex(256, 64, (g, w, h) => {
    g.fillStyle = color; g.fillRect(0, 0, w, h);
    g.fillStyle = "rgba(255,255,255,.18)"; g.fillRect(0, 0, w, 6);
    g.fillStyle = "#2a2d31";
    for (let x = 8; x < w; x += 16) g.fillRect(x, h / 2 - 4, 8, 8);
  });
}

function checker() {
  const t = canvasTex(512, 16, (g, w, h) => {
    for (let i = 0; i < w / 8; i++) for (let j = 0; j < 2; j++) { g.fillStyle = (i + j) % 2 ? "#111" : "#f2f2f2"; g.fillRect(i * 8, j * 8, 8, 8); }
  });
  t.wrapS = THREE.RepeatWrapping; t.repeat.set(4, 1);
  return t;
}

function coneGeometry() {
  const pts = [[0.0, 0], [0.046, 0], [0.047, 0.006], [0.036, 0.012], [0.026, 0.07], [0.014, 0.096], [0.0, 0.1]];
  return new THREE.LatheGeometry(pts.map(([r, y]) => new THREE.Vector2(r, y)), 24);
}

export function createField(canvas, opts = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio, opts.maxDpr || 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = opts.shadowType ?? THREE.PCFShadowMap;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.05, 60);

  // light cards for reflections on metal, in place of an HDR file
  const pm = new THREE.PMREMGenerator(renderer), env = new THREE.Scene();
  env.background = new THREE.Color(0x2b2b2e);
  for (const [x, y, z, w, h, c] of [[0, 6, 0, 9, 9, 0xffffff], [6, 2, 0, 3, 6, 0xffe2c4], [-6, 2, 2, 3, 5, 0x9fb7ff], [0, 2, -7, 10, 2, 0xffffff]]) {
    const card = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: c, side: THREE.DoubleSide }));
    card.position.set(x, y, z); card.lookAt(0, 0, 0); env.add(card);
  }
  scene.environment = pm.fromScene(env, 0.04).texture;
  scene.environmentIntensity = opts.envIntensity ?? 0.32;

  if (opts.fog !== false) scene.fog = new THREE.Fog(opts.fogColor ?? 0x0e0d0c, 5.5, 12);
  scene.add(new THREE.HemisphereLight(0xfff4e6, 0x1a1816, 0.35));
  const pool = new THREE.SpotLight(0xfff0dc, 22, 16, 0.5, 0.65, 1.5);
  pool.position.set(-1.6, 6.2, 2.2); pool.castShadow = false; pool.shadow.mapSize.set(1024, 1024); pool.shadow.bias = -0.0003; pool.shadow.normalBias = 0.02;
  pool.shadow.camera.near = 3; pool.shadow.camera.far = 10; pool.target.position.set(0, 0, 0); scene.add(pool, pool.target);
  const key = new THREE.DirectionalLight(0xffe9cf, 2.6);
  key.position.set(-3.4, 4.0, 2.4); key.castShadow = true;
  Object.assign(key.shadow.camera, { left: -2.8, right: 2.8, top: 2.8, bottom: -2.8, near: 0.5, far: 14 });
  key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02;
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xbfd2ff, 0.7); rim.position.set(3, 3, -4); scene.add(rim);

  const world = new THREE.Group(); scene.add(world);

  // floor, with a dark apron outside the walls
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(2 * HALF, 2 * HALF),
    new THREE.MeshStandardMaterial({ map: opts.twin ? floorTexture(44, "rgba(0,0,0,.6)", "#efe9dd") : floorTexture(), roughness: opts.twin ? 0.7 : 0.92, metalness: 0 }));
  floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; world.add(floor);
  const apronTex = canvasTex(512, 512, (g, w, h) => { const gr = g.createRadialGradient(w / 2, h / 2, w * 0.12, w / 2, h / 2, w / 2);
    gr.addColorStop(0, "rgba(40,38,36,1)"); gr.addColorStop(0.55, "rgba(22,21,20,.9)"); gr.addColorStop(1, "rgba(14,13,12,0)"); g.fillStyle = gr; g.fillRect(0, 0, w, h); });
  const apron = new THREE.Mesh(new THREE.CircleGeometry(4.2, 48), new THREE.MeshStandardMaterial({ map: apronTex, transparent: true, roughness: 0.95, depthWrite: false }));
  apron.rotation.x = -Math.PI / 2; apron.position.y = -0.003; apron.receiveShadow = true;
  if (opts.apron !== false) world.add(apron);

  // perimeter: clear panels, aluminium posts, checker trim
  const panelMat = new THREE.MeshPhysicalMaterial({ color: 0xf3f6f8, roughness: 0.15, metalness: 0, transmission: 0, transparent: true, opacity: opts.twin ? 0.12 : 0.38, depthWrite: false });
  const railMat = new THREE.MeshStandardMaterial({ color: 0xd9dde1, metalness: 0.85, roughness: 0.32 });
  const trimMat = new THREE.MeshStandardMaterial({ map: checker(), roughness: 0.6 });
  const wallH = 0.29;
  for (let k = 0; k < 4; k++) {
    const side = new THREE.Group(); side.rotation.y = k * Math.PI / 2; world.add(side);
    const panel = new THREE.Mesh(new THREE.BoxGeometry(2 * HALF, wallH, 0.008), panelMat);
    panel.position.set(0, wallH / 2, -HALF - 0.004); side.add(panel);
    const trim = new THREE.Mesh(new THREE.BoxGeometry(2 * HALF + 0.04, 0.022, 0.026), trimMat);
    trim.position.set(0, wallH + 0.011, -HALF - 0.004); trim.castShadow = true; side.add(trim);
    const base = new THREE.Mesh(new THREE.BoxGeometry(2 * HALF, 0.03, 0.04), railMat);
    base.position.set(0, 0.015, -HALF - 0.01); side.add(base);
    for (let i = -3; i <= 3; i++) {
      const post = new THREE.Mesh(new THREE.BoxGeometry(0.025, wallH + 0.03, 0.025), railMat);
      post.position.set(i * TILE, (wallH + 0.03) / 2, -HALF - 0.02); post.castShadow = true; side.add(post);
    }
    // toggle on this wall
    const tog = new THREE.Group(); tog.position.set(0, 0, -HALF + 0.07); side.add(tog);
    const bar = new THREE.Mesh(new THREE.BoxGeometry(0.656, 0.05, 0.06), new THREE.MeshStandardMaterial({ color: 0x1b1c1f, roughness: 0.5 }));
    bar.position.y = 0.06; bar.castShadow = true; tog.add(bar);
    for (const x of [-0.24, 0.24]) {
      const pin = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.026, 0.08, 16), new THREE.MeshStandardMaterial({ color: COL.yellow, roughness: 0.45 }));
      pin.position.set(x, 0.12, 0); pin.castShadow = true; tog.add(pin);
    }
  }

  // goals: octagonal pedestals with stacks of cones
  const coneGeo = coneGeometry();
  const mats = {
    body: new THREE.MeshStandardMaterial({ color: 0x2c2e33, roughness: 0.55 }),
    red: new THREE.MeshStandardMaterial({ color: COL.red, roughness: 0.5 }),
    blue: new THREE.MeshStandardMaterial({ color: COL.blue, roughness: 0.5 }),
    yellow: new THREE.MeshStandardMaterial({ color: COL.yellow, roughness: 0.45 }),
    grey: new THREE.MeshStandardMaterial({ color: 0x6d7076, roughness: 0.5 }),
  };
  const r = rng(11);
  const cone = (kind) => {
    const g = new THREE.Group();
    const m = new THREE.Mesh(coneGeo, mats[kind]); m.castShadow = true; m.receiveShadow = true; g.add(m);
    const tip = new THREE.Mesh(new THREE.CylinderGeometry(0.004, 0.017, 0.03, 16), mats.yellow);
    tip.position.y = 0.088; tip.castShadow = true; g.add(tip);
    return g;
  };
  for (const [, x, y, kind, h] of GOALS) {
    const g = new THREE.Group(); g.position.copy(at(x, y)); world.add(g);
    const ped = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.08, h, 8), new THREE.MeshStandardMaterial({ color: 0x141518, roughness: 0.5, metalness: 0.1 }));
    ped.position.y = h / 2; ped.rotation.y = Math.PI / 8; ped.castShadow = true; ped.receiveShadow = true; g.add(ped);
    const band = new THREE.Mesh(new THREE.CylinderGeometry(0.083, 0.083, 0.03, 8), kind === "red" ? mats.red : kind === "blue" ? mats.blue : mats.body);
    band.position.y = 0.015; band.rotation.y = Math.PI / 8; band.castShadow = true; g.add(band);
    const n = kind === "center" ? 5 : 1 + Math.floor(r() * 4);
    for (let i = 0; i < n; i++) {
      const c = cone(["grey", "grey", "red", "blue"][Math.floor(r() * 4)]);
      c.position.y = h + i * 0.045; c.rotation.y = r() * 6.28; g.add(c);
    }
  }
  // loose cones on the tiles, kept clear of goals
  const loose = new THREE.Group(); world.add(loose);
  for (let i = 0; i < 26; i++) {
    let x, y, ok = false;
    for (let tries = 0; tries < 30 && !ok; tries++) {
      x = (r() - 0.5) * 3.2; y = (r() - 0.5) * 3.2;
      ok = GOALS.every(([, gx, gy]) => Math.hypot(gx - x, gy - y) > 0.2);
    }
    const c = cone(["grey", "red", "blue", "grey"][Math.floor(r() * 4)]);
    c.position.copy(at(x, y));
    if (r() < 0.55) { c.rotation.z = Math.PI / 2; c.rotation.y = r() * 6.28; c.position.y = 0.046; }
    loose.add(c);
  }

  // robots: perforated aluminium C-channel, omni wheels, motors, a lift and an intake
  const robots = new THREE.Group(); world.add(robots);
  const P = 0.0127;                                        // VEX hole pitch, 1/2 inch
  const holeTex = canvasTex(64, 64, (g) => { g.fillStyle = "#fff"; g.fillRect(0, 0, 64, 64); g.fillStyle = "#000"; g.fillRect(20, 20, 24, 24); }, false);
  holeTex.wrapS = holeTex.wrapT = THREE.RepeatWrapping;
  const aluMat = (tint) => new THREE.MeshStandardMaterial({ color: tint, metalness: 0.55, roughness: 0.38, alphaMap: holeTex, alphaTest: 0.5, side: THREE.DoubleSide });
  const metal = { silver: aluMat(0xdfe3e7), dark: aluMat(0xaab1b8) };
  const solid = (c, r = 0.5, m = 0) => new THREE.MeshStandardMaterial({ color: c, roughness: r, metalness: m });
  const motorMat = solid(0x26282c, 0.45, 0.1), capMat = solid(0x9aa0a6, 0.4, 0.6), tireMat = solid(0x1c1d20, 0.9);
  const rollerMat = solid(0x2f3135, 0.7), flexMat = solid(0x3a8f4f, 0.75), screenMat = solid(0x0d2b45, 0.25, 0.2);
  function plateGeo(lx, ly, lz) {                          // thin box whose holes keep a real pitch
    const g = new THREE.BoxGeometry(lx, ly, lz), uv = g.attributes.uv, n = g.attributes.normal;
    for (let i = 0; i < uv.count; i++) {
      const ax = Math.abs(n.getX(i)), ay = Math.abs(n.getY(i));
      const [du, dv] = ax > 0.5 ? [lz, ly] : ay > 0.5 ? [lx, lz] : [lx, ly];
      uv.setXY(i, uv.getX(i) * du / P, uv.getY(i) * dv / P);
    }
    return g;
  }
  // a C-channel along local x: web plus two flanges
  function channel(len, mat, w = 0.0254, f = 0.0127) {
    const g = new THREE.Group();
    const web = new THREE.Mesh(plateGeo(len, 0.0016, w), mat); g.add(web);
    for (const s of [-1, 1]) { const fl = new THREE.Mesh(plateGeo(len, f, 0.0016), mat); fl.position.set(0, f / 2, s * w / 2); g.add(fl); }
    g.traverse(o => { o.castShadow = true; o.receiveShadow = true; });
    return g;
  }
  function plateTex(text, side) {
    const bg = side === "red" ? "#d32630" : side === "blue" ? "#1d5fd0" : "#35383e";
    const t = canvasTex(256, 64, (g, w, h) => { g.fillStyle = bg; g.fillRect(0, 0, w, h);
      if (text) { g.fillStyle = "#fff"; g.font = "800 46px Arial Black, Arial, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(text, w / 2, h / 2 + 2); } });
    return t;
  }
  function robot(rb, seed) {
    const q = rng(seed), g = new THREE.Group();
    const put = (obj, x, y, z, rx = 0, ry = 0, rz = 0) => { obj.position.set(x, y, z); obj.rotation.set(rx, ry, rz); g.add(obj); return obj; };
    const mesh = (geo, mat) => { const m = new THREE.Mesh(geo, mat); m.castShadow = true; m.receiveShadow = true; return m; };
    const L = 0.38 + q() * 0.06, W = 0.36 + q() * 0.06, H = 0.3 + q() * 0.14, z0 = 0.045;
    const mat = q() < 0.7 ? metal.silver : metal.dark;
    // drive: two rails per side, cross members, 3 omni wheels a side
    for (const s of [-1, 1]) {
      for (const inset of [0.012, 0.075]) put(channel(L, mat), 0, z0, s * (W / 2 - inset), Math.PI / 2 * s, 0, 0);
      for (const e of [-1, 0, 1]) {
        const x = e * (L / 2 - 0.055), zz = s * (W / 2 - 0.044);
        put(mesh(new THREE.CylinderGeometry(0.0508, 0.0508, 0.03, 28), tireMat), x, 0.0508, zz, Math.PI / 2);
        put(mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.034, 12), capMat), x, 0.0508, zz, Math.PI / 2);
        for (let k = 0; k < 10; k++) {                       // omni rollers
          const a = k / 10 * Math.PI * 2, rr = mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.018, 8), rollerMat);
          put(rr, x + Math.cos(a) * 0.05, 0.0508 + Math.sin(a) * 0.05, zz + s * 0.017, 0, 0, a);
        }
      }
      put(mesh(new THREE.CylinderGeometry(0.027, 0.027, 0.05, 16), motorMat), -L / 2 + 0.11, 0.075, s * (W / 2 - 0.12), Math.PI / 2);
      put(mesh(new THREE.CylinderGeometry(0.027, 0.027, 0.05, 16), motorMat), L / 2 - 0.11, 0.075, s * (W / 2 - 0.12), Math.PI / 2);
      // towers and a four-bar lift
      const tx = -L / 2 + 0.06 + q() * 0.04, zz = s * (W / 2 - 0.1);
      for (const dx of [0, 0.05]) put(channel(H, mat), tx + dx, z0 + H / 2, zz, 0, 0, Math.PI / 2);
      const ang = -0.25 - q() * 0.45, arm = 0.26 + q() * 0.08;
      for (const dy of [0, -0.07]) {
        const a = channel(arm, mat, 0.0254, 0.0127); a.rotation.z = ang;
        a.position.set(tx + 0.03 + Math.cos(ang) * arm / 2, z0 + H - 0.02 + dy + Math.sin(ang) * arm / 2, zz + s * 0.03); g.add(a);
      }
      // license plate
      const plate = mesh(new THREE.PlaneGeometry(0.2, 0.05), new THREE.MeshStandardMaterial({ map: plateTex(rb.team, rb.side), roughness: 0.55 }));
      put(plate, 0.02, 0.105, s * (W / 2 + 0.006), 0, s > 0 ? 0 : Math.PI, 0);
    }
    for (const x of [-L / 2 + 0.01, -0.02, L / 2 - 0.01]) put(channel(W - 0.02, mat), x, z0 + 0.01, 0, 0, Math.PI / 2, 0);
    const tx = -L / 2 + 0.085;
    put(channel(W - 0.18, mat), tx, z0 + H + 0.01, 0, 0, Math.PI / 2, 0);
    // intake: shaft with flex wheels at the front
    const iy = 0.1 + q() * 0.06;
    put(mesh(new THREE.CylinderGeometry(0.004, 0.004, W - 0.08, 6), capMat), L / 2 + 0.01, iy, 0, Math.PI / 2);
    for (let i = 0; i < 5; i++) put(mesh(new THREE.CylinderGeometry(0.028, 0.028, 0.025, 16), flexMat), L / 2 + 0.01, iy, -W / 2 + 0.08 + i * (W - 0.16) / 4, Math.PI / 2);
    // brain, battery, air tank
    put(mesh(new THREE.BoxGeometry(0.12, 0.022, 0.075), motorMat), -0.02, 0.1, 0);
    put(mesh(new THREE.BoxGeometry(0.075, 0.003, 0.05), screenMat), -0.02, 0.112, 0);
    put(mesh(new THREE.BoxGeometry(0.11, 0.035, 0.06), solid(0x8f1d24, 0.5)), 0.09, 0.095, -0.05);
    if (q() < 0.6) put(mesh(new THREE.CylinderGeometry(0.022, 0.022, 0.13, 16), solid(0xd8dadc, 0.25, 0.3)), 0.06, 0.1, 0.08, 0, 0, Math.PI / 2);
    // a carried cone on some robots
    if (q() < 0.5) { const c = cone(["grey", "red", "blue"][Math.floor(q() * 3)]); c.position.set(L / 2 - 0.04, 0.12, 0); g.add(c); }
    g.userData.height = H + z0;
    return g;
  }
  function setRobots(list) {
    robots.clear();
    list.forEach((rb, i) => {
      const m = robot(rb, 31 + i * 17 + Math.round(rb.x * 100));
      m.position.copy(at(rb.x, rb.y));
      m.rotation.y = Math.atan2(-rb.x, rb.y) + Math.PI / 2 + (i - 1.5) * 0.4;   // roughly facing centre
      m.userData.side = rb.side;
      robots.add(m);
    });
  }

  // field lines the model "reads", drawn on top when aligning to a photo
  const lineMat = new THREE.LineBasicMaterial({ color: COL.yellow, transparent: true, opacity: 0, depthTest: false });
  const lines = new THREE.Group(); lines.renderOrder = 10; world.add(lines);
  const seg = (pts) => { const g = new THREE.BufferGeometry().setFromPoints(pts.map(([x, y]) => at(x, y, 0.004))); lines.add(new THREE.Line(g, lineMat)); };
  { const c = TILE / 2, m = TILE; seg([[-WALL, -WALL], [-c, -c]]); seg([[c, c], [WALL, WALL]]); seg([[-WALL, WALL], [-c, c]]); seg([[c, -c], [WALL, -WALL]]);
    seg([[m, 0], [0, m], [-m, 0], [0, -m], [m, 0]]); seg([[-WALL, -WALL], [WALL, -WALL], [WALL, WALL], [-WALL, WALL], [-WALL, -WALL]]); }

  // camera handling: a "view" is {pos, quat, fov, ofs:{fw,fh,x,y}} so a broadcast camera
  // (cropped like object-fit: cover) and a free camera interpolate smoothly
  let W = 1, H = 1;
  function photoView(frame) {
    const s = Math.max(W / frame.w, H / frame.h), fw = frame.w * s, fh = frame.h * s;
    return { pos: new THREE.Vector3(...frame.pos), quat: new THREE.Quaternion(...frame.quat),
      fov: THREE.MathUtils.radToDeg(2 * Math.atan(frame.h / 2 / frame.f)), ofs: { fw, fh, x: (fw - W) / 2, y: (fh - H) / 2 } };
  }
  function freeView(pos, look, fov) {
    const c = new THREE.PerspectiveCamera(); c.position.copy(pos); c.lookAt(look);
    return { pos: pos.clone(), quat: c.quaternion.clone(), fov, ofs: { fw: W, fh: H, x: 0, y: 0 } };
  }
  function apply(v) {
    camera.position.copy(v.pos); camera.quaternion.copy(v.quat); camera.fov = v.fov;
    camera.aspect = v.ofs.fw / v.ofs.fh;
    camera.setViewOffset(v.ofs.fw, v.ofs.fh, v.ofs.x, v.ofs.y, W, H);
    camera.updateProjectionMatrix();
  }
  function mix(a, b, t) {
    return { pos: a.pos.clone().lerp(b.pos, t), quat: a.quat.clone().slerp(b.quat, t), fov: a.fov + (b.fov - a.fov) * t,
      ofs: { fw: a.ofs.fw + (b.ofs.fw - a.ofs.fw) * t, fh: a.ofs.fh + (b.ofs.fh - a.ofs.fh) * t, x: a.ofs.x + (b.ofs.x - a.ofs.x) * t, y: a.ofs.y + (b.ofs.y - a.ofs.y) * t } };
  }
  function resize() {
    const r = canvas.getBoundingClientRect(); W = Math.max(1, r.width); H = Math.max(1, r.height);
    renderer.setSize(W, H, false);
  }
  resize();

  return {
    THREE, scene, camera, renderer, world, robots, lines, lineMat,
    setRobots, photoView, freeView, apply, mix, resize,
    get size() { return [W, H]; },
    render() { renderer.render(scene, camera); },
    project(x, y, h = 0) { const v = at(x, y, h).project(camera); return [(v.x + 1) / 2 * W, (1 - v.y) / 2 * H]; },
    dispose() { renderer.dispose(); pm.dispose(); },
  };
}
