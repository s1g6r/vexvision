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
