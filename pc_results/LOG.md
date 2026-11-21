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
  This one is a league in Naperville that runs **23 Oct 2026 to 11 Jan 2027**, which is why its
  status is "live" and why it only has 42 matches so far. More will appear through the winter, so
  it is right that `watch.py` keeps looking at it rather than marking it finished. No stream on
  YouTube or anywhere else I could find -- league meets usually aren't broadcast. 21 Illinois teams
  with no video is the single biggest hole in the scouting file, and it is not one the PC can fill.
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

### The gap this leaves, and the new reader that closes it

The task file told me to find the Lake Park single-match uploads by hand, because `watch.py` is
looking for event streams and throws away anything shorter than ten minutes. That is the right
call for a stream search, but it means **single-match uploads are never picked up automatically**,
and single-match uploads are how Illinois teams actually post their footage. Doing it by hand once
for Lake Park is fine; doing it for every event from now to March is not.

So there is a second new file, `read_uploads.py`. It does for any event what I did by hand for
Lake Park: searches on the event name and on the event's team numbers, keeps videos between 45
seconds and 10 minutes, pulls the team numbers out of the **title**, and reads the video only if
those are exactly the four teams of one official match at that event. That last part is the whole
point -- it is the same rule `watch.py` uses on streams, applied to titles, and it is what keeps
footage from other events out.

Checked against Lake Park, where I already knew the answer by hand. It found the same five Hawks
Robotics videos and put every one on the right match. It also left three near misses alone, all
correctly:

- `Kly3eAIHY4A` "Vex Lake Park Finals 333Y+355P vs 2360C+2360S"
- `dBiVaR9JoUk` "333y + 355p vs 60441t + 60441y @ lake park vex"
- `aGiy-a0WBpo` "Niles Finals 333Y 321R v 38535A 38535B"

333Y and 355P are never on the same alliance at Lake Park 64295, and 64295 is the only Lake Park
Override event there has ever been, so the first two are from last season's Lake Park (Push Back).
The third is a different event. None of them can be tied to an Override match, and none of them
was read.

One thing to know if you run it: searching a bare team number turns up anything that shares it --
"321A" also finds a long shelf of Schindler 321A elevator videos. They are harmless, and only a
genuine near miss (four team numbers in the title, three of them at the event) is now reported.

    .venv\Scripts\python.exe pc_results\read_uploads.py --event 65760 --prefix niles1- -n   # list only
    .venv\Scripts\python.exe pc_results\read_uploads.py --event 65760 --prefix niles1-       # and read

`-n` lists without reading or writing to this log. It is safe to re-run after an event posts more
uploads; matches already read are skipped.

### The Illinois season ahead

Checked what else is coming, because this is what the station is for. **A 38-team Illinois event
is tomorrow**, and there are seven more before the State Championship:

| date | event | id | teams |
| --- | --- | --- | --- |
| 2026-11-21 | Niles 219 / 333 / 321 Robotics | 65760 | 38 |
| 2026-12-05 | Glenbrook South HS | 64352 | 32 |
| 2027-01-03 | Great Lakes #2 | 65015 | 36 |
| 2027-01-16 | Niles 219 / 333 / 321 Robotics #2 | 65761 | 37 |
| 2027-01-30 | Illini Cornfield Clash Winter | 64756 | 32 |
| 2027-02-27 | Great Lakes #3 | 65016 | 32 |
| 2027-02-28 | Great Lakes Skills Only | 65017 | 13 |
| 2027-03-12 | Illinois State Championship | 65018 | 11 so far |

The IPSD league also keeps adding matches until 11 Jan.

Tomorrow is the first real test. The weekend schedule fires every 2 hours, so the station will
notice Niles as soon as its results go up and a stream exists. Niles is hosted by the 219/333/321
teams, and 321H is Hawks Robotics -- the channel that posted the Lake Park matches one at a time --
so it is quite likely tomorrow's footage shows up as short uploads rather than a stream. That is
exactly the case `watch.py` can't see, which is why `read_uploads.py` now exists. Worth running it
on 65760 on Sunday whatever the station finds.

### One thing to know about files written from PowerShell

`il_events.json` was first written with PowerShell's `Out-File -Encoding utf8`, which on Windows
PowerShell 5.1 adds a byte-order mark, and `json.load` refuses that. Rewritten without one. Worth
remembering if anything else on this PC ever writes JSON through the shell. The `.gitattributes`
added here says what is binary and what is text, so the `.json.gz` files can't be mangled on their
way to the cloud side; checked once by hand that a committed `.json.gz` is byte-identical to the
file on disk and still gunzips.
