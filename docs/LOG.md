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
