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
