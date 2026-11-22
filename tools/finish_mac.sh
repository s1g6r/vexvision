#!/bin/bash
# Finish new Speedway readings from the Mac. Clips go to reidclips (robot looks) only:
# new matches get 3D replays without broadcast stills, to keep the site under its size cap.
mkdir -p /home/claude/work/sw/reidclips && cd /home/claude/work/sw/clips && for f in /mnt/user-data/uploads/vexvisionstuff/sw/clips/*.mp4; do [ -e $(basename $f) ] || ln -s $f .; done; cd /home/claude/work/sw/reidclips
for f in /mnt/user-data/uploads/vexvisionstuff/sw/clips/*.mp4 /mnt/user-data/uploads/vexvisionstuff/sw/small/*.mp4; do [ -e "$f" ] && { [ -e $(basename $f) ] || ln -s $f .; }; done
bash /home/claude/work/finish_new.sh
cd /home/claude/vexvision && ids=$(ls /home/claude/work/raw | grep -E "^e64359-1-qual[0-9]+\.json$" | sed 's/.json//' | tr '\n' ',')
python3 -m tools.reid /home/claude/work/raw /home/claude/work/reid /home/claude/work/sw/reidclips /mnt/user-data/uploads/vexvisionstuff/videos --ids=${ids%,} 2>&1 | grep -E "done|no video"
