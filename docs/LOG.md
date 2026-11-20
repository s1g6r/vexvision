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
