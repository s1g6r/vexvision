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

**For the cloud side, about these five Lake Park matches.** `docs/LOG.md` (Nov 20) says replay
timing now comes off the broadcast clock -- the median of the "driver" clock reads -- because
driver control starts 15-75 s after autonomous. These uploads are phone video of the field with
**no overlay at all**: no match name, no clock, no scores, no alliance panels. So every one of
them comes back with `t_start: null` and an empty `running` series. `overlay_reads` is there but
carries nothing usable: on Qual 3, 40 of its 48 reads are entirely blank and the other 8 have only
a `clock` value and no period word. **Don't trust those 8.** There is no overlay on screen for
them to have come from, so they are OCR finding an m:ss-shaped thing somewhere in the gym; the
clock filter only asks for m:ss under two minutes. `t_start` needs a period word as well as a
clock, which is why it is correctly null rather than wrong. They are
single-match uploads that start at the beginning of the match, so counting from t=0 is the only
option here, and the pause before driver control will have to be assumed rather than measured.
Licence plates are no better: 3 to 8 reads across a whole match, same as the Mac found on its
streams, so these matches will not name themselves either -- and with only 4 qualification matches
on video, Lake Park is under the 8-match floor `tools/event_names.py` needs. Teams and sides are
correct regardless: they come from the official schedule, not the titles, which matters because
`docs/LOG.md` records three titles elsewhere that had red and blue the wrong way round.

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

### Worth a decision: the two biggest Illinois events are on the Mac, and most of them aren't read

`watch.py` has `DONE_ELSEWHERE = {64351: "cc-", 65014: "gl-"}`, so this PC deliberately leaves
Cornfield Clash and Great Lakes #1 alone. Those are the **two biggest Illinois events in the data**
-- 26 and 35 Illinois teams, against 43 at Lake Park -- and on `main` the Mac's own work list says
how far it has got: `data/cc_todo.txt` lists **55 of Cornfield's 65 matches still to read**, about
5 hours of video, each with its start and end second already worked out from
`data/cc_stream_titles.json`. `docs/LOG.md` says that list is downloaded and tracked by
`tools/mac/fetch_clips.sh`, on the Mac.

I have not touched them, and won't without being asked -- the task file gives them to the Mac, and
if both machines read the same match we get duplicate ids (`cc-qual1` and so on) going to the cloud
side from two places. But it is the biggest piece of Illinois scouting still outstanding, and this
PC is the better machine for it: it is dedicated, it stays on, and its pace is now measured. At
5.5x real time, 5 hours of Cornfield video is about **27 hours of reading** -- two nights of the
schedule that is now running, or less if it runs during the day too.

If that is wanted, the hard part is already done: the time windows exist, so it needs a short
script here that cuts each window and tracks it, plus removing 64351 from `DONE_ELSEWHERE` or
agreeing that the Mac stops. Say the word and I will write it.

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

**Checked, not just registered.** With the first full run already going, I started the task by
hand. It launched, reported `LastTaskResult: 0`, and did exactly the right thing -- found the lock
and wrote "another run (pid 1952) is still going after 0.1 h; leaving it alone". So the task's
python path, working directory and user context are all correct, and the no-double-up behaviour is
proven rather than assumed.

**And then the recovery got tested for real, by accident.** At 19:43 the tools I was running the
first pass under were cleaned up from underneath it, and both the Lake Park batch and the watch run
were killed mid-match -- no Python left, and a lock file still on disk naming a dead process. That
is exactly the reboot-or-crash case the lock was written for, and it behaved: the next run logged
"clearing a stale lock (0.5 h old)" and carried straight on. Nothing was lost but the two matches
that were in flight (Lake Park R16 7-1 and Speedway Qual 1); their clips were already downloaded,
finished matches were skipped, and both were simply read again.

The lesson worth keeping: **the scheduled task is the durable way to run this, not a session.** A
long pass started from a terminal dies with the terminal. Started through Task Scheduler, it is
detached and survives. So the restart was done with `Start-ScheduledTask`, which is also how to
kick off a pass by hand at any time:

    Start-ScheduledTask -TaskName 'VexVision scout station'

Tonight's 11 pm trigger will skip while that one is still going, which is correct.

### A real bug in watch.py, found by being interrupted

Worth reading properly, because it defeats the whole point of an always-on station and the fix in
`watch.py` is one line.

`watch.py` decides about a video and saves that decision straight away:

    state["videos"][vid] = "event stream" if ok else "not this event"
    json.dump(state, open(sp, "w"), indent=1)

and only adds the video to the event's `streams` list after the event is finished. In between, it
hands the video to `stream_job.py`, which for a long stream runs for hours. Stop the run in that
gap and the video is left marked "event stream" with nothing read -- and the next pass does

    if vid in state["videos"]:
        continue

so it is **never looked at again**. The event isn't marked complete either, so it just sits there
looking unfinished forever while its only stream is permanently invisible.

This is not hypothetical. It happened on the first run here. Speedway Day 1 (`zhGs-5gah_Y`) was
accepted, scanned, **96 matches found**, and then the run was killed while reading the first one.
state.json came back with `videos["zhGs-5gah_Y"] = "event stream"` and
`events["64359"]["streams"] = []`. All 96 matches were written off by one interrupted run.

And the 10-hour budget turns bad luck into certainty: a 96-match stream cannot be read in one
night, so every night would end inside that gap, and a long stream would only ever get its first
night's worth of matches.

**What I did about it, without touching `watch.py`.** `scout_run.py` now forgets the "event stream"
verdicts before each run, so a half-read stream is always looked at again. Re-reading is cheap and
correct: `stream_job` re-scans the titles (about 11 minutes for a 7.7-hour stream) and skips every
match it has already written, so a long stream creeps forward a night at a time until it is done.
The "too short" and "not this event" verdicts are kept, because those are settled facts about a
video and re-checking them costs real time. Events genuinely finished are marked `complete` and
skipped before their videos are ever considered, so dropping their entries costs nothing. Tested
against the real state.json: 2 stream verdicts dropped, the other 26 verdicts and every `complete`
flag untouched, and running it twice changes nothing the second time.

**The proper fix, for whoever owns `watch.py`:** record the verdict only once `stream_job` has
actually come back, or better, keep the match count alongside it so a part-read stream can be told
from a finished one. Something like moving the `state["videos"][vid] = ...` write to after the
`subprocess.run(...)` call, and keeping the "not this event" case where it is.

**One thing left over from this.** The restarted run skipped Day 1 (it was already in `videos`) and
went to the next accepted video, the 11-minute "Final Four" (`ME5jv9cAaJg`, 2 matches). When it
finishes, `watch.py` will see a done event with a non-empty `streams` list and mark Speedway
**complete** -- on the strength of 2 matches out of 96, and those two are the semifinal and final,
which have no Illinois team in them. A complete event is skipped before the repair can help, so
once this run ends I will clear that one flag by hand so Day 1 gets read. Noted here because it is
the one piece of state on this PC that I edited rather than let the tools write.

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

This matters for how the PC spends the season, and the first full run has now measured it rather
than guessed. Speedway Day 1 (`zhGs-5gah_Y`, 7.7 hours) passed the team-numbers-on-screen check,
`watch.py` accepted it, and the title scan found **96 matches** in it. Nine of those have an
Illinois team (355T). At the measured pace of about 40 minutes per full match window that is
roughly **64 hours of reading, about six nights of the schedule, to get nine useful matches** --
just under 10% of the work is footage of anyone we are scouting. With the region filter it is
about six hours. UND is the same shape on paper: 35 useful matches out of 273.

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
- 2026-11-20 19:16 event 64295 Lake Park (2026-10-24, 43 Illinois teams)
- 2026-11-20 19:16 event 66342 IPSD Invitational League (2026-10-23, 21 Illinois teams)
- 2026-11-20 19:18 event 64244 University of North Dakota Signature at the Mall of America (2026-08-06, 4 Illinois teams)
- 2026-11-20 19:18 event 64359 Speedway (2026-09-18, 1 Illinois teams)
- 2026-11-20 19:19   reading zhGs-5gah_Y 'Speedway: Override VEX V5 Signature Event - Day 1 (Live Stream Presented by Allegion)' (461 min)
- 2026-11-20 19:44 event 64295 Lake Park (2026-10-24, 43 Illinois teams)
- 2026-11-20 19:44 event 66342 IPSD Invitational League (2026-10-23, 21 Illinois teams)
- 2026-11-20 19:44 event 64244 University of North Dakota Signature at the Mall of America (2026-08-06, 4 Illinois teams)
- 2026-11-20 19:44 event 64359 Speedway (2026-09-18, 1 Illinois teams)
- 2026-11-20 19:44   reading ME5jv9cAaJg 'Speedway 2026: Final Four | Semifinals & Finals | VEX V5 Override' (11 min)
