#!/bin/bash
# cloud_worker.sh K N DIR : read every Nth clip of a stream (ids in DIR/windows_todo.txt, manifest DIR/matches.json)
# as it is staged from the Mac, with quick reading, then robot looks, then delete the staged copy.
# Run two (K=0 and K=1, N=2) on the 2-core cloud machine; about 5 matches an hour between them.
K=$1; N=$2; D=${3:-/home/claude/work/sw2}
C=${CLIPS:-/mnt/user-data/uploads/vexvisionstuff/sw2/clips}
cd /home/claude/vexvision
i=0
for id in $(awk '{print $1}' $D/windows_todo.txt); do
  i=$((i+1)); [ $(( (i-1) % N )) = $K ] || continue
  [ -s /home/claude/work/reid/$id.json ] && continue
  w=0; while [ ! -s $C/$id.mp4 ] && [ $w -lt 5400 ]; do sleep 30; w=$((w+30)); done
  [ -s $C/$id.mp4 ] || { echo "$(date +%T) $id never arrived"; continue; }
  sleep 10
  VV_QUICK=1 python3 -m tools.cc_run $D/matches.json $C /home/claude/work/raw site2/data/replays $id 2>&1 | grep -v "^\[" | tail -n 1 | cut -c1-300
  [ -s /home/claude/work/raw/$id.json ] && python3 -m tools.reid /home/claude/work/raw /home/claude/work/reid $C --ids=$id 2>&1 | tail -n 1
  echo "$(date +%T) $id done"
  rm -f $C/$id.mp4
done
