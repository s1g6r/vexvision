# Scout station log (Sagar's gaming PC)

Plain log of what the PC did. Newest entries at the bottom of each day.

## 2026-11-20 — setup

- Cloned the repo to `C:\Users\sagar\vexvision`, branch `pc-results`.
- Git and Python were both already installed. Python on PATH is 3.14.3, which is too new for
  some of the wheels we need (onnxruntime, torch). The `py` launcher also had 3.12 and 3.11
  installed, so the virtual environment was built with **Python 3.12.10**
  (`C:\Users\sagar\AppData\Local\Python\pythoncore-3.12-64\python.exe -m venv .venv`).
  Nothing new had to be installed.
- Installed **CPU-only torch** first
  (`pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu`),
  then `pip install -r tools/pc/requirements.txt`. The CPU wheel is a few hundred MB instead of
  several GB, and this PC's graphics card is AMD so the CUDA build would never be used anyway.
  No code change; just the install order.
- Versions that landed: torch 2.15.0+cpu, numpy 2.5.4, opencv-python 5.1.0, ultralytics 8.4.216,
  onnxruntime 1.32.0, rapidocr-onnxruntime 1.4.4, yt-dlp 2026.10.26, scipy 1.18.1.
- `ffmpeg` is not on PATH; `stream_job.py` falls back to the one inside `imageio-ffmpeg`, which
  works. Nothing to fix.
- Git identity set for this repo only: Sagar Raut <rs1g6r@gmail.com>.
- `tools/pc/il_events.py` -> `pc_results/il_events.json`: 83 Illinois teams across 6 Override
  events (Lake Park 43, Great Lakes #1 35, Cornfield Clash 26, IPSD league 21, UND Signature 4,
  Speedway Signature 1). Same picture the Mac found.
- Listed the whole **Hawks Robotics** channel (13 uploads) instead of trusting a keyword search.
  Exactly five are Lake Park matches, and all five match the official alliances for event 64295:

  | video | match | red | blue |
  | --- | --- | --- | --- |
  | FP5f82usTmE | Qual 3 | 23880A 321H | 355C 355T |
  | sgnpkyrQgVA | Qual 15 | 321A 60172S | 12543M 321H |
  | aarbU3BLe5A | Qual 25 | 60300W 321G | 321E 321H |
  | h4Pg18iPkIM | Qual 35 | 321H 2360H | 355B 2360D |
  | ZTWAkN6Lzlo | R16 7-1 | 321H 38535A | 60441Y 60441C |

  The channel's other uploads are Niles, Alden-Hebron and Automate videos from last season, so
  there is no more Lake Park footage to find there.

### Smoke test

`stream_job.py --video FP5f82usTmE --event 64295 --prefix lp- --single --match "Qual 3"` printed
`Qual 3 done in 797s` and wrote `lp-qual3.perc.json.gz`. Nothing needed fixing; the pipeline ran
first time on Windows. It did better than the task file expected for a phone video: 419 of 432
frames calibrated, 1105 robot sightings, all nine goals read 71 times. There is no broadcast
overlay on these uploads, so `t_start` is empty and almost no licence plates were read -- the
teams come from the official results instead.

Pace, for planning: about **5.5x real time**, so roughly 13 minutes per 2.5-minute match, or about
40 minutes for a full 7-minute match window. One match at a time, which is the default, and leaves
the PC usable.

### What footage exists for the other events

Dry-ran `watch.py`'s search-and-verify on every remaining event without reading any matches.
The check (team numbers on screen must match the event's team list) behaved exactly as intended:

- **IPSD league (66342, 21 Illinois teams)** -- no footage. Four long videos came up in the search
  and all four were correctly rejected: they are other leagues (Rio Hondo, Caution Tape, Highland).
- **UND Signature at the Mall of America (64244, 4 Illinois teams)** -- no full stream. Only three
  clips of about three minutes, which are skipped as too short.
- **Speedway Signature (64359, 1 Illinois team)** -- streams do exist. Day 1 (7.7 hours) and the
  Final Four video (10.5 min) both verified; Day 2 (9 hours) did not verify and was rejected.

So the picture the Mac drew is right: once Great Lakes #1 and Cornfield Clash are done there, and
the five Lake Park uploads are done here, we will have essentially all the Illinois Override
footage that exists today.

### Scheduling

Registered a Windows task called **VexVision scout station**, running as Sagar, only when he is
logged on (running as SYSTEM instead would hide the GitHub credential, which lives in Sagar's own
Windows Credential Manager, and the push would fail).

- Every night at **11 pm**, and **every 2 hours** all day on **Saturdays and Sundays**.
- Program `C:\Users\sagar\vexvision\.venv\Scripts\python.exe`, arguments
  `pc_results\scout_run.py`, starting in the repo folder.
- "If the task is already running, do not start a new instance."

`scout_run.py` is a new file here that wraps `watch.py`; `watch.py` itself is untouched. It exists
because three things go wrong if a repeating task just calls `watch.py` directly:

1. **Runs pile up.** On a weekend the task fires every 2 hours but a run takes far longer, so
   several would be reading and committing at once. A lock file (pid, ignored after 20 hours so a
   reboot can't wedge it) keeps it to one.
2. **It would never come back to the Illinois events.** Speedway Day 1 is 7.7 hours of video over
   a 236-match event, for one Illinois team. Read to the end that is days of work, and the lock
   would hold off every other run meanwhile -- a new Illinois event could sit unread all weekend.
   So a run stops after **10 hours** (`--budget-hours`). Nothing is lost: finished matches stay on
   disk and are skipped next time, and because `watch.py` takes events in order of how many
   Illinois teams played them, a new Illinois event is always reached before the leftovers of a big
   out-of-state one.
3. **Pushes would start being refused.** The cloud side also commits to `pc-results`, so the run
   rebases on it first, and pushes anything `watch.py` didn't get to before its time ran out.

It also runs `prune_clips.py` afterwards (also new, also here): clips are only needed while a
match is being read, so it drops any older than a week, and keeps dropping the oldest while the
disk is under 50 GB free. The disk had 122 GB free at setup; one event's clips are roughly 16 GB.

Console output, including any crash, goes to `%LOCALAPPDATA%\vexvision\watch_console.log`, kept
outside the repo so it is never committed.

**To switch it off:** open Task Scheduler, find "VexVision scout station" in the top-level list,
right-click, Disable. Enable the same way.

### Hunting for footage the search in watch.py wouldn't find

`watch.py` searches on the event name, which finds full streams. Teams also upload their own
matches under titles that never mention the event, so I searched every one of the 83 Illinois team
numbers alongside "VEX Override" (83 searches) and followed up the two channels that came back.

**One more piece of Lake Park footage exists, and it is not usable.** `dBiVaR9JoUk`,
"333y + 355p vs 60441t + 60441y @ lake park vex" (2:24, uploader Jacob Gee). 333Y, 355P and 60441Y
are all Illinois teams at Lake Park, but **60441T never played Lake Park**, and no Lake Park match
has even three of those four teams. So it is a practice match, or a Lake Park event from an earlier
season. `stream_job` takes a match's teams from the official results, so there is nothing for it to
attach this to. Left alone deliberately -- worth knowing it exists if the game ever needs it.

**A channel that uploads whole elimination brackets, match by match.** "Robot Stats: VEX Scouting
& Matches" (`UCMBIfXh0oly6jgbt8iEHpTQ`), 2112 uploads, including 17 single-match videos for
Speedway Override 2026 and 16 for UND at the Mall of America. That looked like it might rescue the
two events with no usable stream -- but it doesn't, and the reason is worth writing down:

- At **UND (64244)** the Illinois teams are 355B, 355T, 355V and 355Z. They played 35 matches,
  and **not one of them was an elimination match**.
- At **Speedway (64359)** the only Illinois team is 355T, with 9 matches, again **no eliminations**.

Every one of those 33 uploads is an elimination match, so no Illinois team appears in any of them.
Nothing there. The channel has no Lake Park, Great Lakes or Cornfield uploads either.

### The two out-of-state events are mostly footage we don't want

This matters for how the PC spends the season. Speedway Day 1 (`zhGs-5gah_Y`, 7.7 hours) passes
the team-numbers-on-screen check, so `watch.py` will accept it and read **every** match in it.
That is on the order of **ten nights of this PC running flat out to reach nine matches** that have
an Illinois team in them. UND is the same shape: 35 useful matches out of 273.

It isn't harmful. `watch.py` takes events in order of how many Illinois teams played them, so a new
Illinois event is always reached before these leftovers, and finished matches are skipped, so the
work does converge. But it is about nine nights of reading nobody we are scouting.

So there is a new file here, `read_region.py`, which reads only the matches a region's teams
played. It is a wrapper, not a copy: it replaces `stream_job.official` with a version that hides
matches with nobody from the region in them, and then runs `stream_job` unchanged -- hidden matches
go down the path it already has for a match it has no teams for. Checked against all three events:
Lake Park keeps 80 of 80 (so on an Illinois event it does nothing at all), Speedway keeps 9 of 236,
UND keeps 35 of 273.

**It has not been run, and nothing has been changed to call it.** Reading only part of an event is
Sagar's call, not mine. If he wants it:

    .venv\Scripts\python.exe pc_results\read_region.py --video zhGs-5gah_Y --event 64359 --prefix e64359-0-

The prefix is the one `watch.py` would have used (`e<event>-<n>-`, n counting streams from 0), so a
later `watch.py` run skips those matches rather than reading them again under a second name. To
stop `watch.py` coming back for the rest afterwards, the stream can be marked handled in
`state.json`, or the event added to `DONE_ELSEWHERE` in `watch.py` the way Great Lakes and
Cornfield are.

### One thing to know about files written from PowerShell

`il_events.json` was first written with PowerShell's `Out-File -Encoding utf8`, which on Windows
PowerShell 5.1 adds a byte-order mark, and `json.load` refuses that. Rewritten without one. Worth
remembering if anything else on this PC ever writes JSON through the shell.
