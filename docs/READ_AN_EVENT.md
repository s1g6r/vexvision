# Reading a whole event from its stream

This is how Speedway day 1 (96 matches, a 7.7-hour stream) was read on 21–22 Nov 2026. It needs the Mac (or any machine
with the models and `tools/mac/`) for downloading and reading, and this repo for everything after.

## 1. Find where each match is in the stream

Grab one frame every 30 s on the Mac (the stream URL from yt-dlp lasts a few hours):

```
yt-dlp -g -f "bv*[height<=720][vcodec^=avc1][protocol^=http]" https://www.youtube.com/watch?v=<stream> > url.txt
mkdir -p f; seq 0 30 <stream length> | xargs -P 20 -I{} sh -c 'timeout 40 ffmpeg -v error -y -ss {} -i "$(cat url.txt)" -frames:v 1 -vf scale=1280:-2 -q:v 4 f/{}.jpg'
tar cf frames.tar f
```

Bring `frames.tar` here, unpack it, then:

```
python -m tools.scan_stream <frames dir> titles.json
python -m tools.stream_windows titles.json <official event id> <stream id> <id prefix> <out dir>
```

That reads the match title in the corner of every frame, takes the longest run of each title as the match, and writes
`windows.txt`, `jobs.txt` (for the Mac job) and `matches.json` (for `finish_perc.py`). Each window starts 60 s before the
title first shows and runs to 150 s after it last shows, at most 7 minutes.

## 2. Download the clips on the Mac

```
tools/mac/fetch_windows.sh windows.txt url.txt ~/vexvisionstuff/<prefix>/clips 8
```

Each call downloads up to 8 clips, each in four pieces at once, because YouTube slows every connection to about real
time. Eight clips take about 80 s. Run it again until every clip is there.

## 3. Read them on the Mac

Copy `jobs.txt` into `~/vexvisionstuff/macjob/` and double-click **Start vexvision.command**. Three workers read the
matches with the Apple GPU, about 5 to 10 minutes per match each. The job waits for clips that are still downloading,
so steps 2 and 3 can run together. Results land in `macjob/out/<id>.perc.json`.

## 4. Finish them here

Stage the `perc.json` files and their clips into this machine, then:

```
tools/finish_mac.sh       # tracking, names from plates, replays with broadcast stills, robot looks
tools/rebuild.sh          # names across the event, reports, official results
tools/post.sh "message"   # thumbnails, packs, commit and push; GitHub Pages is live a minute later
```

`finish_perc.py` needs to know which manifest a match id belongs to (see `MANS` and the Speedway case in it). Delete the
staged clips once a match has its replay and looks; they are copies and take a lot of space.

## Numbers from Speedway day 1

- 96 titles found, all matching the official schedule.
- Download: about 9 GB for 94 clips, about 25 minutes with the 4-piece trick.
- Reading: 94 matches in about 9 hours of Mac time spread over the evening (slower while the Mac was on battery).
- Robots named for sure after naming across the event: 276 of 376.

## Reading in the cloud instead (Speedway day 2, 22 Nov)

When the Mac job isn't running, the cloud machine can read the clips itself, more slowly:

1. Grab frames and download clips on the Mac's shell exactly as above (steps 1 and 2); on 22 Nov all 1,089 frames of a
   9-hour stream came down in under three minutes, and clips in about a minute each.
2. Order the windows so the most useful matches come first (Illinois teams, then teams with the fewest matches on video)
   and save them as `windows_todo.txt` next to `matches.json`.
3. Stage clips into this machine a few at a time and run two workers:
   `tools/cloud_worker.sh 0 2 <dir>` and `tools/cloud_worker.sh 1 2 <dir>`. Each one reads its clips with quick reading
   as they arrive, works out the robot looks, and deletes the staged copy.
4. Every couple of hours: `rebuild.sh`, then `post.sh "message"`.

## Streams that cut between fields (Highlander, 23–24 Nov)

Highlander's stream switched between fields, so a match's window often shows the clock of a match on another field.
Three things guard against it:

- **Downloads land whole.** Clips are written to a hidden `.part` file next to the target and renamed when done, and
  every clip's length is checked against its window (90% or more). Before this, the Mac sometimes read a file that was
  still being copied and found no field.
- **The match start ignores other matches.** When the overlay's teams can be read (three or more) and fewer than two
  of them are in this match, that clock is not used for the start or for driver control (`own_reads` in
  `vexvision/analyze.py`, and the same check while reading).
- **Readings are checked after finishing.** During the 2 minutes of the match, the overlay must name this match at
  least 60% of the time it names any match. Readings that fail are dropped from the site and listed in a `bad.txt`.

A match whose autonomous never appears on the stream can't be recovered this way: it was not shown.

**The queue.** `macjob/mac_queue.py` rereads `jobs_queue.txt` on every pass, so new matches can be appended while it
runs. A small loop on the Mac's shell keeps about 9 clips waiting, deletes clips once their reading is finished here,
and, once the readings are done, keeps the 1080p cuts coming for the plate reader.
