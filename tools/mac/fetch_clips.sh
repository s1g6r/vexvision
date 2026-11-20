#!/bin/bash
# Download match clips from one long livestream, many short pieces at a time (YouTube slows
# each single connection). Usage: fetch_clips.sh URL LIST OUTDIR [parallel]
# LIST lines: id start_seconds end_seconds. Safe to re-run: finished clips are skipped.
URL=$1; LIST=$2; OUT=$3; PAR=${4:-8}
export PATH="$HOME/.local/bin:$PATH"
mkdir -p "$OUT/parts"
direct() { yt-dlp -q -g -f "bv*[height<=720][ext=mp4]/b[height<=720]" "$URL" | head -1; }
SRC=$(direct); STAMP=$(date +%s)
while read -r id a b; do
  [ -e "$OUT/$id.mp4" ] && continue
  if [ $(( $(date +%s) - STAMP )) -gt 3600 ]; then SRC=$(direct); STAMP=$(date +%s); fi
  rm -f "$OUT/parts/$id"-*.mp4
  for ((s=a; s<b; s+=30)); do
    ( ffmpeg -nostdin -loglevel error -y -ss $s -i "$SRC" -t 30 -an -c copy "$OUT/parts/$id-$(printf %06d $s).mp4" ) &
    while [ $(jobs -rp | wc -l) -ge $PAR ]; do sleep 0.5; done
  done
  wait
  ls "$OUT/parts/$id"-*.mp4 | sed "s|^|file '|; s|$|'|" > "$OUT/parts/$id.txt"
  ffmpeg -nostdin -loglevel error -y -f concat -safe 0 -i "$OUT/parts/$id.txt" -c copy "$OUT/$id.tmp.mp4" && mv "$OUT/$id.tmp.mp4" "$OUT/$id.mp4"
  echo "$(date +%T) $id done"
done < "$LIST"
echo ALL DONE
