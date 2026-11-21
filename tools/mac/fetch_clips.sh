#!/bin/bash
# Download match clips from one long livestream, many short pieces at a time (YouTube slows
# each single connection). Usage: fetch_clips.sh URL LIST OUTDIR [parallel] [seconds budget]
# LIST lines: id start_seconds end_seconds. Safe to re-run: finished clips are skipped, and it
# stops starting new clips once the time budget is used (each call of the bridge shell is short).
URL=$1; LIST=$2; mkdir -p "$3/parts"; OUT=$(cd "$3" && pwd); PAR=${4:-10}; BUDGET=${5:-130}
export PATH="$HOME/.local/bin:$PATH"
T0=$(date +%s)
SRC=""; [ -s "$OUT/src.txt" ] && [ $(( T0 - $(stat -c %Y "$OUT/src.txt") )) -lt 3000 ] && SRC=$(cat "$OUT/src.txt")
if [ -z "$SRC" ]; then SRC=$(yt-dlp -q --no-warnings -g -f "bv*[height<=720][ext=mp4]/b[height<=720]" "$URL" 2>/dev/null | head -1); echo "$SRC" > "$OUT/src.txt"; fi
while read -r id a b; do
  [ -e "$OUT/$id.mp4" ] && continue
  [ $(( $(date +%s) - T0 )) -gt $BUDGET ] && { echo "budget used"; exit 0; }
  rm -f "$OUT/parts/$id"-*.mp4
  for ((s=a; s<b; s+=30)); do
    ( ffmpeg -nostdin -loglevel error -y -ss $s -i "$SRC" -t 30 -an -c copy "$OUT/parts/$id-$(printf %06d $s).mp4" ) &
    while [ $(jobs -rp | wc -l) -ge $PAR ]; do sleep 0.3; done
  done
  wait
  ls "$OUT/parts/$id"-*.mp4 | sed "s|^|file '|; s|$|'|" > "$OUT/parts/$id.txt"
  if ffmpeg -nostdin -loglevel error -y -f concat -safe 0 -i "$OUT/parts/$id.txt" -c copy "$OUT/$id.tmp.mp4"; then
    mv "$OUT/$id.tmp.mp4" "$OUT/$id.mp4"; rm -f "$OUT/parts/$id"-*.mp4; echo "$(date +%T) $id done"
  else echo "$id FAILED"; fi
done < "$LIST"
echo ALL DONE
