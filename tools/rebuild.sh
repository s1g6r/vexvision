#!/bin/bash
# Merge new readings into the index, name robots, rebuild replays and reports.
cd /home/claude/vexvision
R=/home/claude/work/raw; S=site2/data/replays; V=/mnt/user-data/uploads/vexvisionstuff/videos
python3 -m tools.merge_index $S
python3 -m tools.event_names $R $S/index.json $R/names_hint.json /home/claude/work/reid > /tmp/names.log 2>&1; tail -3 /tmp/names.log
python3 -m tools.finalize $R $S $V --extra q19=/home/claude/work/raw_q19.json > /tmp/fin.log 2>&1; tail -2 /tmp/fin.log
python3 -m tools.mark_replays 2>&1 | tail -1
python3 -m tools.scout_report --raw $R --index $S/index.json --out site2/data/reports.json | tail -1
python3 -m tools.fetch_official 2>&1 | tail -1
python3 -m tools.official 2>&1 | tail -1
echo "$(date +%T) rebuilt"
python3 -m tools.pack_replays site2/data/replays
python3 -m tools.yt_links $R $S/index.json | tail -1
