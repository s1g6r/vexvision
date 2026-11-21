#!/bin/bash
# Pull results the gaming PC pushed to the pc-results branch and finish them here.
mkdir -p /home/claude/work/pc && cd /home/claude/work/pc
if [ ! -d repo ]; then git clone -q --depth 1 -b pc-results https://github.com/s1g6r/vexvision repo 2>/dev/null || { echo "no pc-results branch yet"; exit 0; }; fi
git -C repo pull -q 2>/dev/null
mkdir -p pc_results; cp repo/pc_results/*.meta.json pc_results/ 2>/dev/null; cp repo/pc_results/LOG.md pc_results/ 2>/dev/null
ids=""
for f in repo/pc_results/*.perc.json.gz; do
  [ -e "$f" ] || continue
  i=$(basename $f .perc.json.gz); [ -e /home/claude/work/raw/$i.perc.json ] && continue
  gunzip -c $f > /home/claude/work/raw/$i.perc.json && ids="$ids $i"
done
for g in /home/claude/work/pc/repo/pc_results/*.reid.json.gz; do
  [ -e "$g" ] || continue; i=$(basename $g .reid.json.gz)
  [ -e /home/claude/work/reid/$i.json ] || gunzip -c $g > /home/claude/work/reid/$i.json
done
cd /home/claude/vexvision; [ -n "$ids" ] && nice python3 -m tools.finish_perc /home/claude/work/raw site2/data/replays $ids 2>&1 | tail -3
echo "pc results: $(ls /home/claude/work/pc/repo/pc_results/*.perc.json.gz 2>/dev/null | wc -l)"
