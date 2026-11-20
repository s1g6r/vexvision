// YOLO (Ultralytics) ONNX models in the browser with onnxruntime-web (WASM).
// Output layout: [1, 4 + classes, anchors] with cx, cy, w, h in input pixels.
const SIZE = 960;
let ortReady = null;

export function loadRuntime(base = new URL("ort/", location.href).href) {
  if (!ortReady) {
    ortReady = new Promise((resolve, reject) => {
      if (window.ort) return resolve(window.ort);
      const s = document.createElement("script");
      s.src = base + "ort.wasm.min.js";   // CPU (WASM) build only
      s.onload = () => {
        window.ort.env.wasm.wasmPaths = base;
        window.ort.env.wasm.numThreads = 1;
        resolve(window.ort);
      };
      s.onerror = () => reject(new Error("Could not load the model runtime"));
      document.head.appendChild(s);
    });
  }
  return ortReady;
}

export async function loadModel(url, names) {
  const ort = await loadRuntime();
  // On GitHub Pages the models are plain .onnx files; where a host serves only common
  // web types they ship as base64 inside .json.
  let bytes;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`model ${url}: ${res.status}`);
  if (url.endsWith(".json")) {
    const { b64 } = await res.json(), bin = atob(b64);
    bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  } else bytes = new Uint8Array(await res.arrayBuffer());
  const session = await ort.InferenceSession.create(bytes, { executionProviders: ["wasm"] });
  return { session, names };
}

// Letterbox an image/canvas into SIZE x SIZE, return the tensor data and the transform.
function letterbox(src, w, h) {
  const r = Math.min(SIZE / w, SIZE / h), nw = Math.round(w * r), nh = Math.round(h * r);
  const px = Math.floor((SIZE - nw) / 2), py = Math.floor((SIZE - nh) / 2);
  const c = document.createElement("canvas");
  c.width = SIZE; c.height = SIZE;
  const g = c.getContext("2d");
  g.fillStyle = "rgb(114,114,114)"; g.fillRect(0, 0, SIZE, SIZE);
  g.drawImage(src, px, py, nw, nh);
  const d = g.getImageData(0, 0, SIZE, SIZE).data, n = SIZE * SIZE, out = new Float32Array(3 * n);
  for (let i = 0; i < n; i++) { out[i] = d[4 * i] / 255; out[n + i] = d[4 * i + 1] / 255; out[2 * n + i] = d[4 * i + 2] / 255; }
  return { data: out, r, px, py };
}

function iou(a, b) {
  const x0 = Math.max(a[0], b[0]), y0 = Math.max(a[1], b[1]), x1 = Math.min(a[2], b[2]), y1 = Math.min(a[3], b[3]);
  const i = Math.max(0, x1 - x0) * Math.max(0, y1 - y0);
  return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-9);
}

export async function detect(model, src, w, h, conf = 0.2, iouThr = 0.5) {
  const ort = await loadRuntime();
  const lb = letterbox(src, w, h);
  const out = await model.session.run({ [model.session.inputNames[0]]: new ort.Tensor("float32", lb.data, [1, 3, SIZE, SIZE]) });
  const t = out[model.session.outputNames[0]], [, ch, n] = t.dims, v = t.data, nc = ch - 4;
  const dets = [];
  for (let i = 0; i < n; i++) {
    let best = 0, cls = 0;
    for (let c = 0; c < nc; c++) { const s = v[(4 + c) * n + i]; if (s > best) { best = s; cls = c; } }
    if (best < conf) continue;
    const cx = v[i], cy = v[n + i], bw = v[2 * n + i], bh = v[3 * n + i];
    const box = [(cx - bw / 2 - lb.px) / lb.r, (cy - bh / 2 - lb.py) / lb.r, (cx + bw / 2 - lb.px) / lb.r, (cy + bh / 2 - lb.py) / lb.r];
    dets.push({ box, conf: best, cls: model.names[cls] });
  }
  dets.sort((a, b) => b.conf - a.conf);
  const keep = [];
  for (const d of dets) if (keep.every(k => k.cls !== d.cls || iou(k.box, d.box) < iouThr)) keep.push(d);
  return keep;
}
