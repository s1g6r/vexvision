#!/usr/bin/env bash
# Assemble the publishable website in build/site: the site source, the models as ONNX,
# and the onnxruntime-web files (pinned) so detection runs in the browser.
#   ./tools/build_site.sh            (needs: models/*.pt, node/npm, ultralytics)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/build/site"
ORT_VERSION=1.30.0
rm -rf "$OUT"; mkdir -p "$OUT/models" "$OUT/ort"
cp -r "$ROOT/site/index.html" "$ROOT/site/style.css" "$ROOT/site/js" "$ROOT/site/data" "$OUT/"
TMP="$(mktemp -d)"
for m in goals robots; do
  cp "$ROOT/models/$m.pt" "$TMP/$m.pt"
  (cd "$TMP" && yolo export model="$m.pt" format=onnx imgsz=960 simplify=True opset=12 >/dev/null 2>&1)
  python3 -c "import base64,json,sys; json.dump({'b64': base64.b64encode(open(sys.argv[1],'rb').read()).decode()}, open(sys.argv[2],'w'))" "$TMP/$m.onnx" "$OUT/models/$m.json"   # page host serves common web types only
done
(cd "$TMP" && npm pack "onnxruntime-web@$ORT_VERSION" >/dev/null 2>&1 && tar xzf "onnxruntime-web-$ORT_VERSION.tgz")
for f in ort.wasm.min.js ort-wasm-simd-threaded.mjs ort-wasm-simd-threaded.wasm; do cp "$TMP/package/dist/$f" "$OUT/ort/"; done
rm -rf "$TMP"
du -sh "$OUT"; find "$OUT" -type f | wc -l
