#!/usr/bin/env bash
# Re-download the 369 Override frames used to train and test (YouTube's own 1280x720 thumbnails).
set -euo pipefail
mkdir -p data/yt
cp -n data/videos.json data/yt/videos.json || true
python -m tools.collect_youtube_frames --out data/yt
