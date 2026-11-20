#!/bin/bash
# Copy the large files the 3D site needs but git doesn't keep: the ONNX models
# (as base64 JSON, since some hosts refuse .onnx) and the onnxruntime-web build.
set -e
cd "$(dirname "$0")/.."
mkdir -p site2/models site2/ort
python3 - <<'PY'
import base64, json
for n in ("goals", "robots"):
    b = open(f"models/{n}.onnx", "rb").read()
    json.dump({"b64": base64.b64encode(b).decode()}, open(f"site2/models/{n}.json", "w"))
PY
cp build/site/ort/* site2/ort/ 2>/dev/null || cp site/ort/* site2/ort/
echo done
