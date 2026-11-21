# Task for the Claude running on Sagar's gaming PC

You are setting up and running the **vexvision scout station** on this Windows PC (Ryzen 7600X3D, 16 GB RAM; its AMD graphics card isn't used). Sagar asked for this. The PC stays on, so the station can keep running for the rest of the season.

## What it does
`tools/pc/watch.py` looks for new VEX Override events that Illinois teams played (from the public data at stats.2360arachnid.com). For each one it:
1. Finds the event's YouTube livestream.
2. Checks that the team numbers on screen match the event's official team list.
3. Reads every match with `tools/pc/stream_job.py`, which runs object detection and field calibration on 3 frames a second.
4. Pushes the results (`pc_results/*.perc.json.gz` and `*.meta.json`) to the `pc-results` branch of github.com/s1g6r/vexvision.

Another Claude session, in the cloud, pulls that branch and builds the replays, scouting reports and website.

## Steps
1. **Check Python and Git.** Run `python --version` and `git --version`. If either is missing, tell Sagar and stop. He installs Python 3.11 or 3.12 from python.org (with "Add python.exe to PATH" ticked) and Git from git-scm.com.
2. **Clone and set up:**
   - `git clone https://github.com/s1g6r/vexvision` and `cd vexvision`
   - `python -m venv .venv` and `.venv\Scripts\activate`
   - `pip install -r tools/pc/requirements.txt`
3. **Git identity**, for this repo only:
   - `git config user.name "Sagar Raut"`
   - `git config user.email rs1g6r@gmail.com`

   Do **not** add any AI author, co-author or "generated with" lines to commits. If `git push` asks for a login, Sagar signs in to GitHub in the window that opens.
4. **Branch:** `git checkout -b pc-results` (or `git checkout pc-results` if it already exists on the remote).
5. **Smoke test** on one Lake Park single-match upload:

   `python tools/pc/stream_job.py --video FP5f82usTmE --event 64295 --prefix lp- --single --match "Qual 3"`

   It should print "Qual 3 done in …s" and write `pc_results/lp-qual3.perc.json.gz`. If it fails, fix it, then write down what you changed in `pc_results/LOG.md`. Most likely causes are a missing package, the ffmpeg path, or a yt-dlp format.

   A phone video with no score overlay may come out with few robots seen. That's fine: the point here is only that the pipeline runs.
6. **First full run:** `python tools/pc/watch.py`. It can take hours. Leave it running and check `pc_results/LOG.md`.
7. **Make it automatic:** create a Windows Task Scheduler task that runs `watch.py` every day at 11 pm, and every 2 hours on Saturdays and Sundays.
   - Program: `<repo>\.venv\Scripts\python.exe`
   - Arguments: `tools\pc\watch.py`
   - Start in: the repo folder
   - Set it to run whether or not anyone is logged in, if Windows allows that without a password prompt; otherwise "only when logged in" is fine.
   - Tell Sagar how to turn it off: open Task Scheduler, find the task, then Disable.
8. **Lake Park single-match uploads** (the Lake Park event, 64295, has no full stream). Search YouTube for "Lake Park Q" uploads by the channel Hawks Robotics. Read each one with:

   `stream_job.py --video ID --event 64295 --prefix lp- --single --match "<match name from the title>"`

   Then commit and push to `pc-results`.

## Rules
- Only add files under `pc_results/`. Don't change the tracking code, the website or `main`. If the code needs a fix to run on Windows, make the smallest change possible and describe it in `pc_results/LOG.md`.
- Never commit video files. `pc_results/clips/` is ignored. Delete clips older than a week if the disk gets below 50 GB free.
- Keep Sagar's PC usable: run at most 2 matches at a time. One at a time is the default.
- When you finish setup, tell Sagar in plain words what is running, when it runs, and how to stop it.
