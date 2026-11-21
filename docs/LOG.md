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
