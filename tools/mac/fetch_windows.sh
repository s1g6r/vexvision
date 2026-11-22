#!/bin/bash
# fetch_windows.sh WINDOWS.txt STREAM_URL_FILE OUT_DIR [N]
# Downloads the next N missing match clips, each in 4 pieces at once (YouTube slows every single connection
# to about real time). Run it again until every clip is there. Get the stream URL with:
#   yt-dlp -g -f "bv*[height<=720][vcodec^=avc1][protocol^=http]" <youtube url> > url.txt
WIN=$1; export U=$(cat "$2"); OUT=$3; N=${4:-8}
export W=$HOME/scratch/parts; mkdir -p "$W" "$OUT"
piece(){ [ -s $W/$1.mp4 ] && return; timeout 140 ffmpeg -v error -y -ss $2 -t $3 -i "$U" -c copy -an -f mp4 $W/$1.part && mv $W/$1.part $W/$1.mp4; }
export -f piece
todo=$(while read id s l; do [ -s "$OUT/$id.mp4" ] || echo "$id $s $l"; done < "$WIN" | head -$N)
echo "$todo" | while read id s l; do [ -n "$id" ] || continue; q=$(( (l + 3) / 4 )); for i in 0 1 2 3; do echo "$id.$i $((s + i*q)) $q"; done; done | xargs -P 32 -n 3 bash -c 'piece "$0" "$1" "$2"'
echo "$todo" | while read id s l; do [ -n "$id" ] || continue
  ok=1; : > $W/$id.txt; for i in 0 1 2 3; do [ -s $W/$id.$i.mp4 ] || ok=0; echo "file '$W/$id.$i.mp4'" >> $W/$id.txt; done
  [ $ok = 1 ] && ffmpeg -v error -y -f concat -safe 0 -i $W/$id.txt -c copy $W/$id.all.mp4 && mv $W/$id.all.mp4 "$OUT/$id.mp4" && echo "$id ok" && rm -f $W/$id.*
done
