# Work log and decisions

## 2026-11-19 (night)

### Data
- **Override-only catalog** (`tools/catalog.py` → `data/catalog.json`): 266 Override videos and 189 teams.
  - Breakdown: 97 single matches with both alliances, 73 robot or pit videos, 19 skills runs and 35 event recaps.
  - The earlier "982 videos / 671 teams" count was wrong. Robot Stats titles like "Sugar Rush Sig" or "Mecha Mayhem Sig" don't name the game, and those events were last season (High Stakes).
  - This was checked by running the goal detector on frames from every video: those events essentially never show Override goals.
  - The old site's numbers were corrected.
- **Full match videos:** downloaded through Sagar's Mac (folder `vexvisionstuff`), 65 so far, 720p.
  - The cloud machine can't download from YouTube.
  - Background jobs on the Mac's shell stop when each call ends, so all heavy processing runs in the cloud.

### Models
- **Robot detector round 3:** 91 training frames and 316 boxes, about 4× round 2.
  - **Labelling:** round 2 proposed boxes on 432 Override frames. I reviewed 131 candidates by eye on contact sheets, kept 89 frames, and dropped wrong boxes (people, refs, the monitor).
  - **Held-out test set:** 24 frames from 15 videos that no training frame comes from (`data/robots_test.json`).
  - **Known bias:** the test boxes came from round 2's own predictions, which I only accepted or rejected. That favors round 2, especially on box-tightness metrics.

  | Model on the test set | Precision | Recall | mAP50 | mAP50-95 |
  |---|---|---|---|---|
  | robots r1 (old site) | 0.88 | 0.81 | 0.909 | 0.653 |
  | robots r2 | 0.91 | 0.92 | 0.972 | 0.929 (biased) |
  | **robots r3 (adopted)** | **0.96** | **0.99** | **0.992** | 0.769 |

- **Goal detector:** round 3 is in use. On a geometry-labelled test set (21 frames, 11 videos) it scores mAP50 0.686.
  - **Round 4 dataset:** 141 frames, built from calibrations that passed the tape check (fit ≥ 0.7, ≥ 5 goals agreeing) and were reviewed on sheets.
  - It isn't trained yet: the CPU is busy with match tracking.

### Tracking full matches
- **Bugs fixed**
  - Local video now decodes through ffmpeg, because OpenCV can't decode AV1, which most of the downloads are.
  - Calibration is now checked on every frame. Frames that don't match the field, like close-ups, replays or the results card, are skipped and the tracks coast through them. Before, robots jumped across the field after camera cuts.
  - Plate reading used the wrong robot list (an index mismatch once out-of-field detections were dropped).
- **Logging:** the calibration for every frame and each tracked robot's box once a second are now saved. The boxes are for training an alliance-colour model later.
- **Speed:** about 6–7 minutes per match on the cloud machine (2 cores).
  - The overlay and plate OCR now run every 2 s instead of every 1 s, since OCR was a third of the time.
- **Quality check:** `tools/track_check.py` draws every track back onto sampled frames.
  - Qual 19 (Great Planes): all four tracks stay on their robots for the whole match, with brief wobbles in collisions.
  - Speedway Final 1-1 (low camera, purple light, a monitor blocking part of the field) is looser.

### Site (new 3D site)
- **Replay:** a full match on the 3D field, with the broadcast stills in the corner carrying the same robots marked.
  - Controls: play, scrub and 1×/2×/4× speed.
  - Views: the broadcast camera, or orbit.
  - "Where they drove" shows a heatmap of each alliance.
- **Replay data:** the replay picker lists only matches with ≥ 60% of frames calibrated and robots seen ≥ 60% of the time.
- **Stills:** packed 48 to a sprite sheet, so each replay is about 5 files.
- **Scoring:** the model's own scoring isn't shown, because it isn't accurate enough yet. Qual 19's final score (73–55) comes from the broadcast's results card.
- **Screenshot analyzer:** the same detectors run in the browser (onnxruntime-web). The field is lined up and the screenshot is rebuilt in 3D from its own camera.
- **Team pages:** "Scouted by vexvision" shows distance driven per match, share of driver control on the opponent's side and in the Midfield, autonomous movement, and a heatmap, from every tracked match of that team.
  - Top speed is computed but not shown: at 3 frames/s with smoothing it reads low.

### Nov 20: tracker rewrite and honest names
- **What was wrong.** Drawing each track's robot crops over a match showed red tracks ending up on blue robots, and paths flying off the field.
  - The detector wasn't the cause. In Highlander R16 2-1 it finds all four robots in 90% of frames at 0.85–0.92 confidence.
  - The old tracker assumed 6 cm of floor-point noise and gentle acceleration. A robot that reversed fell outside its gate, coasted on its old velocity (sometimes out of the field) and then grabbed whatever detection was nearest.
- **New tracker** (`vexvision/track.py`):
  - A detection can only go to a robot that could have driven there since it was last seen: 35 cm of noise plus 2.3 m/s.
  - Distance is measured from the better of the predicted spot and the last sighting.
  - A lost robot slows to a stop where it was, and is clamped inside the walls.
  - Two boxes on one robot are merged.
  - Each box also gets a red-vs-blue reading, and there is a whole-match pass that exchanges a red and a blue track if, after they met, each kept reading as the other alliance. **Both are switched off.**
    - Checked by eye on Highlander Final 1-1, the repair pass moved the red robot (its 12125A plate is readable in the crops) onto a blue track for a minute. Without it, the red track keeps that robot.
    - The reading is a plain red/blue pixel count, and it mostly measures the cones a robot is carrying and its own red parts, not its alliance plate.
    - A proper plate-colour classifier could turn this back on.
- **Results** (new tracker, colour reading off)

  | Match | Robots seen (old → new) | Jumps over 2.5 m/s (old → new) |
  |---|---|---|
  | Highlander R16 2-1 | 0.93 → 0.97 | 8 → 0 |
  | Highlander Final 1-1 | 0.85 → 0.95 | 27 → 4 |
  | Highlander Final 1-3 | 0.81 → 0.81 | 25 → 3 |
  | Speedway Final 1-1 | 0.76 → 0.83 | 30 → 15 |

  - At Speedway, robots are hidden behind a monitor stand and people in front of the field, so fewer are seen there.
- **Perception logs.** The video pass now saves everything the models saw (`raw/<id>.perc.json`): every robot box with its floor point, colour reading and appearance, plus plate reads, goal and toggle reads, and the overlay.
  - `tools/retrack.py` redoes tracking, names, events and the replay export from those logs in seconds.
- **Replays.**
  - While a robot is hidden, it is drawn moving straight from where it was last seen to where it was found again.
  - Speed is capped at 7.5 ft/s, so a robot that was lost glides rather than teleports.
- **Names.** Which of an alliance's two robots is which team was a coin flip in every match except Qual 19 and two alliances whose plates were read.
  - On these streams the plates can't be read: OCR on 720p crops returned nothing, and on a 1080p download it still returned nothing.
  - Robots are now named only when plate reads decide it (confidence ≥ 0.75). Otherwise they show as Red 1 / Red 2, and their card says "20850G or 3150Z".
  - Team driving stats only count named matches. A team without any says so and still links to its replays.

### Nov 20: driver-control timing, autonomous routes, 2360A at Cornfield Clash
- **Driver control starts late.** There is a 15–75 s pause between autonomous and driver control while the field is reset and scored.
  - Replays had assumed 120 s straight and were cutting off the end of every match.
  - Driver-control start is now read off the broadcast clock (median of all "driver" clock reads), and playback skips the pause.
  - Videos that begin in driver control count back from the clock and mark autonomous as not seen.
- **Bugs found while the batch ran**
  - The score-series reader crashed whenever the overlay showed a score (read the wrong columns). Fixed. Analysis now keeps the perception log even if reasoning fails, so nothing has to be re-read from video.
  - Video ids starting with "-" broke the export call.
- **Team pages**
  - Every named match adds its 15-second autonomous path to a mini field.
  - Maps are turned so a team's own side is always the same corner, so red and blue matches add up.
- **2360A (Cornfield Clash Jr., Nov 7 2026).** No single-match uploads exist, only the 7.4-hour livestream.
  - Read the team panel of one 480p frame every 30 s (887 frames, fetched through the Mac in parallel bursts), and found 2360A in 10 matches: Quals 13, 26, 34, 40, 44, 50, two earlier quals, QF 3-1 and SF 2-1.
  - Cut those 10 stretches at 720p (in 30 s pieces, 20+ at a time, because YouTube throttles each connection) and tracked them like any other match (`tools/cc_run.py`).
  - **Naming 2360A.** The robot is black and purple, the only one like that at the event. A per-track "dark" score (share of very dark pixels in its boxes, during the match only) picks it: it led its partner by 1.4–3.5× in every match checked, and crop sheets confirm it.
  - Team pages list these matches and link to the right minute of the stream.
- **Hosting limit.** The site holds at most 512 files, so each match's broadcast stills are now one 8×24 sheet of 320×180 tiles (under iOS's 16.7 MP image limit) instead of 3–4 sheets.

### Nov 20 — deeper scouting reports

- **Autonomous routes** are grouped. Two matches count as the same route when the paths stay within 0.45 m of each other on average over the 15 s. Each route is written out step by step: where it starts, where it stops (a stop is at least 1 s below 0.25 m/s), where it ends, and whether it crosses the Autonomous Line. Places are named from the team's own side, for example "its own left Alliance Goal". The most-run route is listed first. For 2360A it was run in 4 of 6 matches.
- **Goals worked** counts a Goal visit when the robot is near a Goal for at least 1 s, after being away for at least 2 s. The report shows visits per match, which kind of Goal (own, neutral, Center, the other alliance's), the favourites, and the median time between visits.
- **Cone colours** come from the robot's box during driver control. For each colour (yellow, red, blue) we take the share of strongly coloured pixels above that robot's own quietest level (the 15th percentile), which removes its own paint. It is labelled rough on the site: alliance plates and flags still add a little of the robot's own colour. We are not using the placement events for this yet, because most of them have no team attached.
- **Speed** is the 95th percentile of frame-to-frame speed, using only frames where the robot was seen at both ends. The absolute numbers come out low (a median of about 2.3 ft/s), probably because of the 3 fps sampling and the tracker smoothing, so the site only shows each team's rank against all 61 tracked teams and never quotes ft/s.

### Nov 20 — official results, event prep, naming across matches

- **Official results.** The stats site (VexPredict) already publishes every Override event as JSON, so we read those files (`data/official/ev_<id>.json`, fetched from stats.2360arachnid.com through the Mac) and don't call the VEX API again. `tools/official.py` joins them to our matches: 68 of 74 matched. The other 6 come from events or matches the stats site doesn't list (Blank.'s Beginnings, and two matches named only "Finals").
- **The schedule beat the video titles.** Three matches had red and blue swapped in the YouTube titles: Mall of America Q56 and Q62, and Smoky Mountain Q77. Retracking now always takes team lists and scores from the official schedule.
- **Video score vs the real score** (67 matches): our score is off by 48 points per alliance on average (median 45), and too low by about 30. It picks the right winner 72% of the time, and the correlation with the real red score is 0.43. That is not good enough to show anywhere. Reading the Goals properly needs its own model trained on labelled stacks; that is still open.
- **Naming robots across a whole event** (`tools/event_names.py`). A robot looks the same in every match at one event. We embed crops of each robot with DINOv2-small (`tools/reid.py`, 112 px crops, about 30 per robot per match). Then, for every alliance, we pick the robot-to-team assignment that keeps each team's look most consistent across all its matches. The confidence check also tries swapping two partners everywhere they played together, so a pair that always played together stays unsure.
  - Hide-and-recover test: we hide one known name at a time and check whether the solver gets it back. At Cornfield it recovered 2360A in 7 of 8 matches. The eighth, Qual 16 with 2360V, is disputed: the crops show the tracker jumping between robots in that match.
  - On elimination-only streams it got about as many wrong as right, because partners never change there. So names from this step are only applied at events with at least 8 qualification matches on video, and only at confidence 0.9 or higher. Robots named for sure went from 84 to 94 of 292.
  - The real limit is the tracker. Crops show it sometimes following the wrong robot for a stretch, including a robot of the other colour. A per-frame look check inside the tracker is the next fix.
- **The Cornfield stream, mapped** (`data/cc_stream_titles.json`). Reading the match title in the corner every 30 s found all 54 qualifications and 11 elimination matches. A 50-minute stretch in the middle replays earlier matches (same frames); it is skipped. `tools/mac/fetch_clips.sh` with `data/cc_todo.txt` downloads the 55 matches we don't have yet, about 5 hours of video. It runs on the Mac.
- **Event prep page.** Pick an event and your team. It shows each of your matches with partner and opponent cards (official rank, record, points a match, skills, our tags and their most-run auton) and the stats site's pre-match chance to win. Under that is a pick list of every team at the event, ordered by rating and tagged by how it plays.
- **Report tags** (Plays defence, Stays home, Toggle runner, which Goals, Ends in Midfield, Auton crosses over). The thresholds were set from where teams fall: Toggle runner is the top 30% for time at Toggles. The summary thresholds were raised to match, because "Goes after Toggles" used to fire for almost everyone.

### Nov 20–21 — two whole events, the Mac and the PC

- **Cornfield Clash Fall (all 65 matches) and Great Lakes #1 (all 78).** The Cornfield clips were cut from the stream by match title (`data/cc_stream_titles.json`). The Great Lakes streams only open with YouTube's Android client, which gives 360p. Detection and calibration still work at that size (calibrated about 0.99).
- **The M4 Pro Mac did most of the reading.** `tools/mac/mac_perceive.py` plus a one-click start file run on macOS with the Apple GPU: 3 workers, about 6 minutes per match each, about 18 matches an hour. This machine did the rest from the other end of the list. The bridge shell on the Mac can't run anything longer than 3 minutes, so the Mac job runs in a normal Terminal window that Sagar started.
- **The gaming PC is a scout station** (`tools/pc/`, `docs/PC_TASK.md`). A Claude session on the PC set it up. It pushes results to the `pc-results` branch, and `ingest` pulls them here. So far it has read 5 Lake Park single-match uploads and part of the Speedway day-1 stream. Its matches have no replay stills, because we don't keep its video; they're flagged `replay: false` and only feed the reports.
- **Bug: wrong crops on 360p video.** The look-matching step cut robot crops using box coordinates from the 1280×720 frames we analyse, straight out of 360p video. Every Great Lakes crop was off. `tools/reid.py` now scales the boxes, and the Great Lakes looks were redone.
- **Naming across whole events, tested again** by hiding each known name and checking it comes back:
  - **Great Lakes:** at confidence 0.9 or higher, 8 of 9 came back right; the miss was a plate read the looks disagree with. 2360A came back right in 7 of 8 overall.
  - **Cornfield:** about 16 of 19 at 0.9 or higher.
  - Names are applied only at 0.9 or higher. Robots named for sure went from 94 of 292 to 436 of 844.
- **Duplicates:** the same match filmed twice (a single-match upload and a stream) is now kept once, the copy where the robots were seen best (`tools/merge_index.py`).
- **Artifact size cap:** one version can hold at most 256 MiB. The replay still sheets are now scaled to 3/4 and saved at JPEG quality 42, about 0.8 MB a sheet, for roughly 225 MiB in all. The picture in the corner of the replay is small, so this barely shows.
- **Result:** 213 matches, 117 teams with a report (up from 69). 2360A's report now covers 15 matches at Cornfield and Great Lakes; its most-run auton was run in 7 of 12.

### Nov 21–22 — Speedway day 1, Niles, and the move to GitHub Pages

- **Speedway day 1, all of it.** The day-1 stream (7.7 hours) was mapped by reading the match title on a frame every 30 s, which found 94 of the 96 qualifications. Each match was downloaded on the Mac as four pieces at once, because YouTube slows each connection to about real time, then read by the Mac job. Robots were named across the event from their looks: 276 of 376 named for sure. Qual 37 was dropped (its timing came out wrong and nothing could be placed) and Qual 68 failed to read.
- **The Mac job now waits for clips** that are still downloading instead of skipping them, so reading and downloading can run at the same time.
- **Niles (21 Nov).** No stream. The official schedule and results come straight from the stats site, which this machine can now reach, so `tools/fetch_official.py` refreshes them without the Mac. Hawks Robotics posted four phone videos; only Qual 22 had a steady enough view (calibrated 0.84, all four robots named). The other three were left out.
- **Upcoming Illinois events** are in the event list: Niles, Glenbrook South, Great Lakes #2 and #3, Cornfield Clash Winter, State. Before a schedule is out, the page shows "Teams to know": the strongest entrants we have on video, with their autons. Partner and opponent cards note auton clashes (same start tile, same Goals, races for a neutral or Center Goal).
- **GitHub Pages.** The site moved to https://s1g6r.github.io/vexvision/ (workflow `.github/workflows/pages.yml`, publishes `site2/` on every push to `main`). That removed the artifact host's 256 MiB and 512-file caps. Replay data is bundled into packs of up to 12 matches per event (`tools/pack_replays.py`); a replay loads its pack once.
- **Replays without stills** are allowed (the corner picture hides), for matches whose video we don't keep. Picker thumbnails now come from each replay's own stills (`tools/thumbs_from_stills.py`).
- **Result:** 307 matches tracked, 305 with a replay, 201 teams with a report.

### Nov 22 (overnight) — lighter, offline, and more for the scout in the stands

- **First visit is about 1.5 MB over the wire** (was about 10 MB). Picker thumbnails load only when scrolled into view, and a service worker (`site2/sw.js`) keeps the site working offline once it has loaded.
- **Match plan:** each of your matches on the event page draws all four robots' most-run autons on one field, opponents turned to their side.
- **Match strip:** a row of your matches that stays under the menu while you scroll them, with W/L marked and the first unplayed match marked "next". A 0–0 match before later played ones counts as replayed, not next.
- **Pick list:** sorts by rating, points, skills, matches on video, fit with your auton, or "Your mix": six sliders (rating, points, skills, speed, Goals worked, time on the other side), each scored as a percentile against the other teams at that event. Teams without video drop the video sliders and get a *. The sliders are saved on the device. The list downloads as a CSV with your notes.
- **Notes:** a box on every team page (including teams with results but no video), on reports and as a strip on cards, saved on the device; "Copy my notes for this event" puts them all on the clipboard.
- **Find teams by name** as well as number; teams with no video show up as "no video yet".
- **Results freshness:** `tools/fetch_official.py` writes `data/official/fetched.txt`; the event page says "Results checked …" in the reader's time.
- **Niles final re-read:** with the new video it calibrated (0.88) but the camera is behind the drivers: robots seen 42% of the time, none named for sure, no auton. Kept out.
- **Video for Illinois teams is used up.** The Hawks Robotics channel's Override uploads are all read; its other Niles and Lake Park uploads are from last season. Lake Park has only those 5 single-match uploads, IPSD and Glenbrook South have no video. More Illinois coverage now needs new video (a stream at Glenbrook South, or teams uploading), not more reading.
- **Checks on the live site:** every team page, every report and every event (with sample teams, every pick-list sort) loads with no errors or bad text (948 pages); all replays open.

### Nov 22 (morning) — quick reading, corrections, printing

- **Quick reading** (`analyze(..., quick=True)`, on by default in `mac_perceive.py` and `cc_run.py`; `VV_QUICK=0` turns it off). Once the overlay can be read, frames before autonomous are thinned to one in three (only in the first 120 s, in case the clock never shows), and after the driver clock runs out only the overlay is read, plus 8 s for the final Goals. The end time is the latest one any clock read gives, so a misread can only make it later.
  - **Speedway Qual 11 (stream clip, 330 s):** 490 frames instead of 996. Same t_start and driver start; robot paths differ by a median 9–50 mm; seen share and distance driven the same.
  - **Cornfield Qual 1 (single upload):** 677 frames instead of 720 (the match fills the clip). Paths differ by a median 1–11 mm; distance driven is about 10% lower because driving after the buzzer is no longer counted.
  - First try had a bug: a "driver 0:00" left on screen from the previous match ended the reading before it started. The end time now only comes from driver clocks after autonomous.
- **"Wrong team on a robot? Tell us"** under each replay opens a GitHub issue with the match and what the replay shows. Fixes go in `data/name_fixes.json` and are applied by `tools/event_names.py` as certain (`docs/NAME_FIXES.md`).
- **Print:** event pages and reports print as light sheets without the rest of the site.
- **Pick list "Mark picked"** for alliance selection: picked teams drop to the bottom and lose their number, so the best teams left stay on top. Saved per event on the device; "Clear picks" resets.
- **Speedway day 2** (stream KiElXboeVVc, 9 h): 1,089 frames grabbed on the Mac's shell in under 3 minutes; 117 qualification titles found, all matching the schedule. Clips came down from the Mac in about a minute each and were read here with quick reading by two workers (`tools/cloud_worker.sh`), about 6–7 matches an hour, ordered so matches with Illinois teams and thinly covered teams came first. 54 were read and published by midday (Qual 174 found no field); Speedway Qual 68 (day 1) was re-downloaded and read too. Speedway robots named for sure: 255 of 330 alliances. Speedway reports went from a median of 3 matches per team to 5. The other 62 windows are in `work/sw2/windows_todo.txt`, and `macjob/jobs_sw2.txt` is ready for the Mac job.
- Checked on the live site after the last batch: 948 team, report and event pages with no errors, all 54 day-2 replays open.

### Nov 22 (evening) — team plates from 1080p video

- **Why:** every match was read at 720p, where team plates are a few pixels tall; the old plate reader found almost nothing. At 1080p plates are readable whenever a robot is close to the camera.
- **How (`tools/plate_pass.py`):** download a 1080p cut of each match (`hd_fetch.sh` on the Mac), line it up with the first reading by the on-screen match clock (median of matched clock reads, 30–50 pairs a match), reuse the first reading's robot boxes and tracks, find red or blue plate-shaped patches inside each box, enlarge them 3× and read them. Boxes that overlap another robot are skipped. Reads are votes: a read only counts if it clearly matches one of the four teams in the match, and an alliance is settled when at least 2 reads agree and they outnumber the others 3 to 1 (`teams.plate_votes`).
- **Speed:** about 7 minutes a match here, about 10 minutes per worker on the Mac with 6 workers (`macjob/plates/`). All 147 Speedway matches done in about 5 hours, most of it on the Mac.
- **What it found:** plates settled 113 of Speedway's alliances. Where they did, the earlier names were right about 85% of the time; the rest were swapped (Qual 35, both alliances; Qual 63 blue; Qual 4 blue; and others).
- **Naming rule, tested:** hiding half of the plate-settled alliances, naming from plates plus looks alone got 77% right; keeping earlier names as anchors got 85%. So plates correct the alliances they can read and earlier names anchor the rest. Speedway now has 286 of 332 alliances named for sure (was 255) and a median of 6 matches per report (was 5).
- **Where it doesn't help:** Cornfield's camera looks straight down, so plates on robot sides barely show (1 read in a whole match). Great Lakes is 360p.
- **Also:** the "Gambler" tag (yellows are a big share of the cone colour on the robot, top sixth of teams, 2+ matches); plainer words ("Goal stops" instead of "Goals worked", "Mostly neutral Goals", "drawn with its own side at the bottom left"); team names under the numbers on replay cards.

### Nov 23 — the rest of Speedway day 2

- **All 117 day-2 qualification matches are in** (the last 61 read overnight and this morning). Your Mac read most of them (3 workers, 6–12 minutes a match), and the cloud worked from the other end of the list (2 workers, about 17 minutes a match). Each finished reading came here for tracking, robot looks and naming, and the Mac read team plates from the 1080p cuts right after.
- **Two downloads were broken** (Qual 138 and Qual 199: the file had no index, one only 4 MB). They were found by checking every clip with `ffprobe`, then downloaded again and read. A broken clip fails quietly (the reading just finds no field), so run that check before a batch.
- **The overnight gap:** the work only moves while Claude's turn is running, and the turn ended last night, so nothing was fed to the Mac for several hours. The morning run caught up.
- **Results:** Speedway now has 228 matches with replays, 395 of 450 alliances named for sure, and a median of 7 matches per team report (was 6). Every replay links to the YouTube stream at autonomous (421 of 421).
- **Checked live:** all 117 day-2 replays open with no errors.

### Nov 23 — Toggles: count real flips, not time nearby

- **Removed** everything built on time spent near a Toggle (the "Near a Toggle" meters, the Toggles % column, "Spends a lot of time at the Toggles"). A robot parked by a Toggle is usually defending it or scoring on the Goal next to it.
- **A flip** (`tools/toggle_flips.py`): the Toggle is seen changing colour during the match, a robot is touching it (within half a metre, from 2 s before to half a second after), and the new colour stays once robots move away. Changes under 4 s apart are one flip. The closest touching robot gets the credit.
- **Checked by eye** against match video, 4 frames per moment (3 s before to 4 s after):
  - single-match uploads (Highlander, Harbor Havoc, Blank's, some Speedway): 19 real of the 20 that could be judged, 3 couldn't be judged;
  - Speedway stream (1080p cuts): 20 of 20 real;
  - moments the rule throws out: 7 of 12 correctly thrown out, 3 real flips missed (two quick flips in a row, a flip to yellow, a lost robot — the first two are now handled).
  - A looser version (new colour just read twice) found 76 more but only about 13 of 17 judgeable were real, so it was not used.
- **Coverage:** the camera sees one or two of the four Toggles, so flips are a floor. 280 flips in 156 of 423 matches. The site never says a team "doesn't toggle".
- **Toggle runner** now means: at least 3 matches, 3+ flips seen, in 3+ different matches or in at least half of its matches. 13 teams (was 44, and 22 of those 44 were never seen flipping once).
- **Comes for your Toggles:** 2+ flips seen on the other alliance's Toggles. **Late:** most flips in the last 30 seconds.
- **Replay:** a seen flip lights that Toggle in the flipper's colour for about 2.5 s, the robot's label says "Toggled", and the play bar gets a mark.
- **Open question for Sagar:** the Toggle shows two colours from above (top face and the face toward the field). Which one is its set colour? Until that is answered the replay shows flips only, not which colour a Toggle is on.
- The old colour-change events in the replays (which also fired before and after the match during field reset) are replaced by these flips.

### Nov 23 (evening) — half-turned Toggles don't count

- Sagar: a Toggle only counts when the side facing the field is all one colour; a two-colour (half-turned) Toggle counts for no one.
- The Toggle reader already looks at the field-facing side and measures how much of it is one colour. A set Toggle reads 90–100%; half-turned ones read 50–70% (checked on the crops). Under 80% is now "split".
- **Old flips re-checked on video:** frames 3, 5 and 7 s after each flip, for the 175 flips whose video I could get (Speedway streams from the Mac, single-match uploads here). 143 ended fully set, 13 ended half turned and were dropped (`data/toggle_split.json`), 3 changed again, the rest couldn't be read. 267 flips remain.
- **Not re-checked:** the 105 Great Lakes flips. Their YouTube videos embed fine but would not download, and the downloader setting that might work was refused here, so they keep the earlier rule.
- **Future readings** store "split" instead of a colour (`readers.toggle_state`), and a change ending split is never a flip; the end-of-match Toggle owner also ignores split.
- **Replay:** after a seen flip the Toggle stays in the colour it was set to (red, blue or yellow) until the next seen change; Toggles never seen fully set keep the plain look.
- Toggle runner is still 13 teams (the dropped half-turns did not change who has it).
- **Half turns as a scouting signal** (Sagar's point: a team that leaves Toggles half turned can't control its toggling). Each "half" is kept per robot (`type: "half"` in the replays and `data/toggle_flips.json`). A report says "Has trouble controlling Toggles: left N of its M Toggle tries half turned" once N is at least 2 and at least a third of its tries. Today no team reaches that: the 13 half turns found so far are 13 different teams. Readings from now on record every half turn on a visible Toggle, so this will fill in.

### Nov 23–24 (overnight) — Highlander Summit from its two-day stream

- **What's in:** 177 Highlander matches now have replays from the stream (109 from day 1, 68 from day 2), on top of the single-match uploads that were already there. Where the same elimination match exists both ways, the site keeps the copy where the robots were seen best. Highlander has 310 of 375 alliances named for sure.
- **How:** the same steps as Speedway. Clips cut from the stream on the Mac, read on the Mac (a queue that picks up new matches as they're added), finished here (tracking, robot looks, naming), then team plates read on the Mac from 1080p cuts. All 193 windows got plates (177 of 188 tracked matches have plate reads).
- **Every replay links to the stream at autonomous** (Highlander added to `data/yt_starts.json`). Checked by hand on Qual 2, Qual 90 and Qual 150: each lands at 0:13–0:14 of autonomous.
- **Stream cut between fields.** In some windows the broadcast showed another field's match while this one was being played. A reading is kept only if, during its 2 minutes, the overlay names this match at least 60% of the time. Dropped: Qual 1, 6, 9, 17, 28, 36, 50 (and Round of 16 3-1, which has a single-match upload anyway). Tried again for Qual 36 and 50 with a fix that ignores other matches' clocks (`own_reads` in `vexvision/analyze.py`): Qual 36's autonomous was never shown, and Qual 50 only has driver control on screen with a score that doesn't match the official one, so both stay out.
- **Broken downloads:** three day-1 clips (Qual 38, 73, 87) came down incomplete because the Mac started reading a file while it was still being copied. Fixed by writing to a hidden `.part` file and renaming it when done (`fetch.sh`, `fetchc.sh`, `hd_fetch.sh`); all three were downloaded again and read.
- **Not in:** Finals 1-1 to 1-3 and Qual 137 (no window found in the stream).
- **Toggle flips:** 473 flips in 261 of 615 matches (201 of them from the Highlander stream). Spot check of 8 random Highlander flips on the stream video: all 8 are real changes. 6 of 8 clearly end in the colour the site says. The other 2 are on the Toggle nearest the camera, where you see two faces in two colours, so the colour is unclear. That's the same open question as before (which face is the set colour). Toggle runner is now 39 teams (was 13 before Highlander), because Highlander adds a lot of matches where the camera sees the Toggles well.
- **Mac disk:** 15 GB free of 461 GB. Highlander clips and 1080p cuts were deleted once done.
- **Team pages for stream-only teams:** a team seen only in event streams (no YouTube video with its number in the title) used to show "No Override video names this team yet" on its team page even when it had a scouting report and replays. Those team pages now show the report, the heat maps and the replay buttons. This affected many Speedway and Highlander teams.

### Nov 24 — Great Planes, GHOST Halloween, and the IPSD pilot

- **IPSD pilot (Sagar's next event).** The IPSD league has 21 teams (2360s, 8995s, 8780s). 12 already have scouting reports from Cornfield, Great Lakes and Lake Park video. The other 9 (8995M, R, S, Z; 8780B, C, D, F; 2360D) have only played at IPSD, which isn't streamed or uploaded anywhere. Plan: film the next IPSD night ourselves (one phone, high, whole field, one clip per match named by match number) and read it here. Illinois events in general are not livestreamed: only scattered single-match uploads exist (Niles West and Lake Park matches from 321H, for example).
- **Great Planes Signature (2-day stream):** 155 match windows found, all matching the official schedule. 140 replays are live after the other-field check. 258 of 278 alliances are named for sure (93%), the best of any event so far. A few matches were dropped because their autonomous was never labelled on the overlay (Qual 1, 20, 31, 50, 78, 104).
- **GHOST Halloween @ UT Austin (1-day stream, two fields, top-down camera):** 81 windows. The eliminations were read first (here on the cloud machine, from the end of the list), and the Mac reads the qualifications. The straight-down camera calibrates fine (about 0.9), but robots are rarely named for sure, because there are no readable plates from above. No plate reading for this event.
- **Smoky Mountain Forge:** its stream uses a low, wide camera with the field small in frame. Skipped for now.
- **Highlander half-turn re-check:** 199 Highlander flips were read before the half-turn rule reached the Mac. I re-checked them on stream frames 3, 5 and 7 s after each flip. The far Toggle (N) and the side ones read cleanly: 70 set, 0 half turned. The near Toggle (S) shows two faces to this camera, so its share can't separate "half turned" from "set". So the half-turn rule can't be applied to the near Toggle at Highlander, and nothing was dropped. This is the same open question as before (which face is the set colour).
- **Mac:** the reading code on the Mac was behind (half-turn rule, other-field clock fix). It's synced now, and the queue runs for 3 days instead of 12 hours. Stream addresses are refreshed after 4 hours (an expired one silently stopped the 1080p downloads for a while).
- **Feeding script** `vexvisionstuff/feed.sh` now feeds several events at once (event folders with `prefix`, `windowsN.txt`, `streamN.txt`, `noplates`), and `newids.sh` lists finished Mac readings. On this side, `work/ev_finish.sh DIR PREFIX` finishes them and runs the other-field check, which now also covers cloud readings.

### Nov 25 — Aiming at Worlds: the Signature events

- **The goal is Worlds.** Most Worlds teams play Signature events, and those are almost always streamed, so the plan is to read every Signature event with a stream. Upcoming Signature events are already in `tools/official.py` and `tools/catalog.py` (WAVE at WPI, Slugger, St. Andrews Bangkok, iSTEMn, PAS-VEX, LAUNCH, Sunshine Showdown, Sugar Rush), so each one can be read as soon as its stream goes up.
- **One World Signature @ UC Berkeley (Nov 21, 64 teams):** both days read, and 133 replays are live. The camera calibrates well (about 0.99), but its robots are small and far away, so plates almost never read (98 of 140 matches had none). Naming leans on looks: 138 of 266 alliances are named for sure. Dropped by the other-field check: Qual 10, 38, 58, 114; R16 3-1, 7-1, 8-1. The Final isn't in the stream window.
- **GHOST Halloween:** all 81 windows read, about 70 live.
- **Great Planes:** all readings in. The day-2 plates were stuck for a while (an expired stream address and the 1080p fetches losing their turn to newer events) and are being read now.
- **Not available:** Mall of America only has partial fan restreams, Harbor Havoc's stream is gone, and Smoky Mountain Forge's camera is low and far. Hong Kong may be in a "Hong Kong Open" stream (not checked yet).
- **Site now:** 952 replays, 421 teams with scouting reports.

### Nov 25 — Team pages and reports reworked for phones

- A friend tried the site on his phone and said the "go deeper" pages repeated the same things, some data seemed to be missing, and it wasn't clear which matches were used. The team page is now a short overview with one list of matches, and the report opens with what it's based on: matches played, on video and used, plus a line explaining every match left out. Each fact is said once, in the section it belongs to. Details in `docs/DESIGN.md`.
- Fixed a long-standing phone bug: the page could be dragged sideways because a table on the event prep page pushed the page wider than the screen.
