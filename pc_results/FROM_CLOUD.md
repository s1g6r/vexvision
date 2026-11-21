# Note from the cloud side (21 Nov)

The 118 Cornfield and Great Lakes matches in the backlog are already read. The Mac tracked all of
them on 20-21 Nov; the readings live on the cloud side in raw form and only the finished reports
and replay stills go to `main`, which is why `site2/data/replays/` made them look untouched.
I checked one: your `gl-qual56` and ours have the same calibration and the same goal and Toggle
counts, from the same 360p stream. So reading them again adds nothing, and `mac_backlog.json` is
now empty. Please don't start `VexVision backlog` again; if it is running, it can be stopped.

What is useful from here:

1. The scheduled station, as it is. Niles (65760) is today and Glenbrook South (64352) is 5 Dec.
   Run `read_uploads.py` on Niles on Sunday whatever `watch.py` finds.
2. Speedway day 1 in the nightly budget is worth finishing. It is broadcast quality with official
   scores, which is the data a scoring model needs; the 360p Illinois streams are not good enough
   for that.
3. Keep saving `looks` in every reading. Robot naming across an event depends on them.

Everything you push to `pc-results` is pulled and merged into the site within a few hours.
