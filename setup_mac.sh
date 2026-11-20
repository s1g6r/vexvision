#!/usr/bin/env bash
# One-time setup on a Mac (Apple Silicon or Intel). Run from the repo folder:  ./setup_mac.sh
set -euo pipefail
if ! command -v ffmpeg >/dev/null; then
  if command -v brew >/dev/null; then brew install ffmpeg; else echo "Install Homebrew (https://brew.sh) then rerun, or install ffmpeg yourself."; exit 1; fi
fi
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python - <<'PY'
import torch
print("PyTorch", torch.__version__, "| Apple GPU (mps):", torch.backends.mps.is_available())
PY
echo
echo "Done. Next time, start with:  source .venv/bin/activate"
