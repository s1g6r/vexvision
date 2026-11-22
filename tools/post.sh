#!/bin/bash
# After a rebuild: shrink new stills, add thumbnails, pack, then commit and push (GitHub Pages deploys on push).
cd /home/claude/vexvision/site2
python3 - <<'PY'
from PIL import Image;import glob,json,os,subprocess
for f in glob.glob('data/replays/*/s*.jpg'):
    im=Image.open(f)
    if im.width>2000: im.resize((im.width*3//4,im.height*3//4),Image.LANCZOS).save(f,quality=42,optimize=True)
m=json.load(open('data/thumbs.json'))['map']
dirs=['/home/claude/work/sw/clips','/home/claude/work/sw/reidclips','/mnt/user-data/uploads/vexvisionstuff/videos','/home/claude/work/nw/clips']
for e in json.load(open('data/replays/index.json')):
    i=e['id']; v=e.get('video') or i
    if v in m or i in m or os.path.exists(f'data/thumbs/{v}.jpg') or os.path.exists(f'data/thumbs/{i}.jpg'): continue
    src=next((f'{d}/{i}.mp4' for d in dirs if os.path.exists(f'{d}/{i}.mp4')),None)
    if src: subprocess.run(['ffmpeg','-v','error','-y','-ss','30','-i',src,'-frames:v','1','-vf','scale=480:270',f'data/thumbs/{v}.jpg'])
PY
cd .. && python3 -m tools.thumbs_from_stills site2 && python3 -m tools.pack_thumbs site2/data/thumbs site2/data/sheets && python3 -m tools.pack_replays site2/data/replays
git add -A site2 && git -c user.name="Sagar Raut" -c user.email="rs1g6r@gmail.com" commit -qm "${1:-Update scouting data}" && git push -q origin HEAD && git log --oneline -1
