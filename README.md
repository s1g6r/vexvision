# vexvision

Turns VEX V5RC **Override** match video into scouting data: where every robot
drove, who placed which pins, who flipped which Toggle, who parked in the
Midfield, and how that adds up to the referees' score. Built for team 2360A
Arachnid, to sit next to [VexPredict](https://stats.2360arachnid.com).

## How the existing tools do it

**scout.questionative.dev** (invite-only, runs on its owner's computer). Its
landing page lays out an 8-step pipeline, with its own accuracy claims:

| Step | What it does | Their number |
|---|---|---|
| 1. Find the match | Reads the broadcast clock and match name to find one match in a long stream | under 30 s |
| 2. Watch | YOLO11 model trained on hand-labelled VEX footage: robots, goals, pins, cups, Toggles, 4 frames/s | ~3.5x real time |
| 3. Map the field | Goals in view are matched to their known positions, so pixels map to inches, even when the camera pans | |
| 4. Track robots | Followed frame to frame from their starting tiles: paths, distance, time in zones, defence | auton found by motion |
| 5. Read the goals | A placement is a goal's piece count rising and holding; a close-up model says which pieces | 89% of placements found |
| 6. Read the Toggles | Wall Toggle colours voted over a short window; a flip goes to the robot at that wall | 85% of flips found, 79% to the right team |
| 7. Name the teams | Licence plates read in the match; each robot's look remembered across an event | 97% on plate-checked robots |
| 8. Check the score | The broadcast's running score and the official result show what the camera missed | |

It also claims 70% of this season's winners called before the match, 14,373
teams rated, 2,090 competitions and 2,691 matches analysed (Nov 2026), plus a
pick list, team graphics and Instagram match reels.

**@vrc.ai on Instagram is the same product.** Its reels ("The most detailed
VEX scouting system, powered by machine learning", early-access form) carry the
`scout.questionative.dev` watermark. The posts show match cards with an "AI"
rating per team, a 2D field view, play-by-play, a momentum line, and a
September demo of "auto field calibration" on an untuned model.

## How vexvision does it, and where it is meant to beat Scout

The same stages, with choices that use what VEX rules guarantee:

1. **Exactly four robots.** The tracker keeps four tracks for the whole match
   instead of creating and dropping them, so robots touching or hiding behind
   a stack can't swap or multiply.
2. **Alliance for free.** Robots must start on their own side of the Autonomous
   Line, so the two on the red side are red from the first frame.
3. **Team names as a two-way choice.** The schedule (or the overlay) says which
   two teams are on each alliance, so naming robots is one yes/no per alliance.
   One good plate read settles it; a robot with no readable plate is named by
   elimination. Plate reads are matched with an edit distance, so "2I45X"
   still votes for 2145X.
4. **Calibration from goals, refined by tape.** Goals give the view; the white
   tape (diagonals, Midfield diamond, Autonomous Line) then nudges the field
   in its own plane. Tape alone can't be trusted: tested here, a free fit to
   the tape matched it well while shrinking the whole field.
5. **The referees' score as a constraint.** The running score on the
   broadcast (read by OCR when the producer shows it) and the official final
   score are used to find unseen scoring and credit it to the nearest robot of
   that alliance. Seen and inferred points are reported separately.
6. **Predictions are already ahead.** VexPredict calls 78.8% of match winners
   on held-out data (Push Back, 37,364 High School matches), against Scout's
   stated 70%.

## What has been measured (real Override broadcasts, Nov 2026)

Data: the auto-generated 1280x720 frames YouTube keeps for every video (3 per
video), from 123 Override match videos across about 15 events. See
`tools/collect_youtube_frames.py` and `tools/collect_channel.py`.

RESULTS_TABLE

Not measured yet, because it needs full match video (see "Run it on a Mac"):
tracking accuracy, placement and Toggle event recall, plate reading on
robots, and the score check. The goal-stack reader is a colour heuristic until
a goal close-up model is trained from stack counts made in the labeling tool.

## Run it on a Mac

```bash
./setup_mac.sh                      # ffmpeg, a Python venv, the libraries
source .venv/bin/activate

# where does Qual 12 start in a 7-hour stream? (reads the overlay, ~70 frame grabs)
python -m vexvision find "https://www.youtube.com/watch?v=VIDEO_ID" "Q 12"

# analyse it: JSON (paths, events, per-team stats, score check) + a field map PNG
python -m vexvision analyze "https://www.youtube.com/watch?v=VIDEO_ID" "Q 12" \
    --weights models/goals.pt,models/robots.pt --out out/ \
    --official '{"red": 112, "blue": 95}'

# one frame, to check calibration and detection
python -m vexvision frame some_frame.jpg --weights models/goals.pt,models/robots.pt
```

## Make the models better (the part that matters most)

The models in `models/` were trained on 32 frames (goals) and 14 frames
(robots). More labelled data is the biggest lever.

1. **Robots from video, no hand labels:** cut a match clip
   (`yt-dlp --download-sections "*1:23:00-1:25:10" URL -o clip.mp4`), calibrate
   one frame, then `python -m tools.video_autolabel clip.mp4 --H calib.json --out data/auto_robots`.
   Moving blobs the size of an 18-inch robot become robot boxes. Check
   `data/auto_robots/check/` before training.
2. **Goals and stack counts by hand:** open `tools/label.html` in a browser,
   load frames, click goal bases and tape corners, draw robot boxes, type the
   stack counts. Export, then `python tools/import_labels.py vexvision-labels.json`.
3. **Turn marks into labels:** `python tools/landmarks_to_labels.py data/landmarks.json FRAMES_DIR lab/`
   then `python -m tools.propagate FRAMES_DIR lab/` (spreads each calibration to
   other frames from the same camera).
4. **Let the model label more, then review:** `python tools/autolabel.py --weights models/goals.pt ...`
   writes contact sheets; keep the frames that line up.
5. **Train** (Apple GPU): `yolo detect train data=ds/data.yaml model=models/goals.pt imgsz=960 epochs=100 device=mps`

## Repo map

| Path | What it is |
|---|---|
| `vexvision/field.py` | Override field in mm: goals, Toggles, tape, Midfield diamond, scoring rules |
| `vexvision/overlay.py` | Broadcast overlay reader: match name, period, clock, teams, running score |
| `vexvision/calibrate.py` | Pixels to field: from goals, tape snap, camera recovery, frame-to-frame transfer |
| `vexvision/detect.py` | YOLO wrapper (goal and robot models together) |
| `vexvision/track.py` | Four-robot tracker, path stats |
| `vexvision/teams.py` | Plate reads + appearance, two-way team assignment per alliance |
| `vexvision/readers.py` | Goal stack and Toggle readers |
| `vexvision/events.py` | Placements, Toggle flips, Midfield, final field state |
| `vexvision/reconcile.py` | Check against official / running score, credit per robot |
| `vexvision/stream.py` | Seek into streams without downloading; find a match |
| `vexvision/analyze.py` | One match end to end |
| `tools/` | Data collection, labeling tool, training data, evaluation |
| `data/` | Hand marks (`landmarks.json`), robot boxes (`robots.json`) |
| `models/` | Trained weights |

## Decisions and open questions

- **Field geometry.** Goal and Toggle positions are VEX's published GPS
  coordinates. The Midfield (a diamond, corners 24" from centre) and the
  Autonomous Line (two tapes ~50 mm apart) were measured from calibrated
  frames because the manual's field drawings weren't reachable. Measured
  diamond radius 608-631 mm across four frames against 609.6 mm in the model.
- **Autonomous bonus.** VEX's game page says 12 points; the manual glossary
  excerpt says 10. `field.PTS_AUTON_BONUS` is 12; the score check against
  official results will show which is right.
- **Toggle height.** Read at 250-340 mm above the tiles (top of the wall),
  checked by projecting onto calibrated frames.
- **Training data from YouTube thumbnails.** These are frames YouTube already
  serves publicly; the full-video steps download nothing beyond the frames
  ffmpeg reads while seeking.
