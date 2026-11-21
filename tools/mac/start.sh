#!/bin/bash
# Reads every queued match on this Mac. Leave the window open; it keeps the Mac awake.
cd "$(dirname "$0")"
[ -d vexvision ] || tar xzf code.tgz
if [ ! -d .venv ]; then
  echo "Setting up (one time, a few minutes)..."
  python3 -m venv .venv && . .venv/bin/activate && pip install -q --upgrade pip && pip install -q ultralytics rapidocr-onnxruntime opencv-python scipy numpy imageio-ffmpeg || { echo "Setup failed"; exit 1; }
else
  . .venv/bin/activate
fi
python3 -c "import imageio_ffmpeg" 2>/dev/null || pip install -q imageio-ffmpeg
DEV=$(python3 -c "import torch;print('mps' if torch.backends.mps.is_available() else 'cpu')")
CORES=$(sysctl -n hw.perflevel0.physicalcpu 2>/dev/null || sysctl -n hw.ncpu)
N=$(( CORES / 3 )); [ $N -lt 1 ] && N=1; [ $N -gt 3 ] && N=3
echo "Using $DEV with $N workers ($CORES fast cores). Progress goes to log.txt"
for ((k=0; k<N; k++)); do VV_DEVICE=$DEV caffeinate -i python3 mac_perceive.py jobs.txt out $k $N >> log.txt 2>&1 & done
wait
echo "All done" | tee -a log.txt
