"""Build the website's data from pipeline outputs.

  python tools/build_site_data.py --proposals proposals.jsonl --frames data/yt/frames \
      --videos data/yt/videos.json --ocr data/yt/ocr.json --facts facts.json --site site

Writes site/data/gallery.json (one record per calibrated frame), the frame
images at 960x540, and copies facts.json. Frames are chosen from confident
calibrations only (tape fit >= 0.6 and >= 5 goal detections agreeing), at most
two per video.
"""
import argparse, json, os, re, shutil, sys
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vexvision import overlay, field as F

GENERIC = re.compile(r"^(full finals?|finals?|semifinals?.*|elite local|spotlight|signature|final four|round of 16|"
                     r"vex v5.*|vex override|override|qualifiers?|elims?|[a-z ]*division|default)$", re.I)

def clean_event(t):
    t = re.sub(r"\s+", " ", t or "").strip(" -|:")
    t = re.sub(r"(?i)\b(vex\s*v5\s*)?(robotics\s+)?competition\b", "", t).strip(" -|:")
    return t

def event_name(title, ocr_title):
    """Event name: from the video title when it names one, else the overlay's title bar."""
    t = re.sub(r"\s+", " ", title or "")
    if re.search(r"\bskills\b", t, re.I) and not re.search(r"\b(qual|final|sf|qf|r16)\b", t, re.I):
        return "Skills run"
    head = t.split("|")[0]
    if ":" in head and not re.search(r"\b(qual|final)", head.split(":")[0], re.I):
        return clean_event(head.split(":")[0])[:60]
    for part in re.split(r"\s[|\-]\s|\s\|", t):
        p = clean_event(re.sub(r"\(.*?\)", "", part))
        if len(p) > 4 and not GENERIC.match(p) and not re.search(r"\b(qual|final|r16|qf|sf|vs)\b|\d{2,5}[A-Z]\b|#", p, re.I):
            return p[:60]
    o = clean_event(ocr_title)
    if o and len(o) >= 8 and " " in o and "/" not in o and not re.search(r"alliance|round|tied", o, re.I):
        return o[:60]
    return clean_event(t)[:60]

TEAM_OK = re.compile(r"^\d{2,5}[A-Z]$")

def cap_robots(rs):
    """A match has exactly four robots, two per alliance, each starting and mostly
    staying on its own side. Keep the most confident four, at most three per side
    (robots do cross the Autonomous Line during driver control)."""
    out, side = [], {"red": 0, "blue": 0}
    for r in sorted(rs, key=lambda r: -r["conf"]):
        sd = F.side_of(*r["floor"])
        if len(out) < 4 and side[sd] < 3:
            out.append(r); side[sd] += 1
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proposals", required=True); ap.add_argument("--frames", required=True)
    ap.add_argument("--videos", required=True); ap.add_argument("--ocr", required=True)
    ap.add_argument("--facts", required=True); ap.add_argument("--site", required=True)
    ap.add_argument("--per-video", type=int, default=2); ap.add_argument("--max", type=int, default=260)
    ap.add_argument("--q-min", type=float, default=0.6)
    a = ap.parse_args()
    vids = json.load(open(a.videos))
    ocr = json.load(open(a.ocr)) if os.path.exists(a.ocr) else {}
    recs = [json.loads(l) for l in open(a.proposals)]
    good = [r for r in recs if r.get("H") and r.get("q", 0) >= a.q_min and r.get("goal_agree", 0) >= 5]
    by_vid = {}
    for r in good:
        by_vid.setdefault(r["frame"][:11], []).append(r)
    chosen = []
    for vid, rs in by_vid.items():
        rs.sort(key=lambda r: (-sum(1 for x in r["robots"] if x["conf"] >= 0.35 and "floor" in x), -r["q"]))
        chosen += rs[: a.per_video]
    chosen.sort(key=lambda r: (-r["q"]))
    chosen = chosen[: a.max]
    os.makedirs(os.path.join(a.site, "data", "frames"), exist_ok=True)
    out = []
    for r in chosen:
        fn = r["frame"]; vid = fn[:11]; v = vids.get(vid, {})
        img = cv2.imread(os.path.join(a.frames, fn))
        if img is None:
            continue
        h, w = img.shape[:2]
        s = 960 / w
        small = cv2.resize(img, (960, int(round(h * s))), interpolation=cv2.INTER_AREA)
        cv2.imwrite(os.path.join(a.site, "data", "frames", fn), small, [cv2.IMWRITE_JPEG_QUALITY, 72])
        S = np.diag([s, s, 1.0])
        H = (S @ np.array(r["H"])).tolist()
        sc = lambda b: [round(x * s, 1) for x in b]
        robots = cap_robots([{"box": sc(x["box"]), "conf": round(x["conf"], 2), "floor": x["floor"]} for x in r["robots"]
                  if x["conf"] >= 0.35 and "floor" in x and max(abs(x["floor"][0]), abs(x["floor"][1])) < F.HALF + 150])
        goals = [{"box": sc(x["box"]), "conf": round(x["conf"], 2), "cls": x["cls"]} for x in r["goals"] if x["conf"] >= 0.25]
        rd = overlay.parse(ocr[fn], (w, h)) if fn in ocr else None
        rec = {"frame": fn, "img": f"data/frames/{fn}", "w": 960, "h": small.shape[0], "H": [[round(x, 8) for x in row] for row in H],
               "q": round(r["q"], 3), "video": vid, "title": v.get("title", ""), "channel": v.get("channel", ""),
               "event": event_name(v.get("title", ""), rd.event_title if rd else None), "robots": robots, "goals": goals}
        if rd:
            red = [t for t in rd.red if TEAM_OK.match(t)]; blue = [t for t in rd.blue if TEAM_OK.match(t)]
            rec.update({"match": rd.match, "red": red, "blue": blue, "clock": (f"{rd.clock//60}:{rd.clock%60:02d}" if rd.clock is not None else None)})
            if rd.red_score is not None and rd.blue_score is not None:
                rec["score"] = f"{rd.red_score}-{rd.blue_score}"
        if v.get("teams") and len(v["teams"]) == 4 and (len(rec.get("red") or []) + len(rec.get("blue") or [])) < 4:
            rec["red"], rec["blue"] = v["teams"][:2], v["teams"][2:]
        if not rec.get("match"):
            m = re.search(r"\b(Qual(?:ification)?|Q|R16|QF|SF|Finals?|F)\s*#?\s*(\d{1,3})(?:\s*-\s*(\d{1,2}))?", rec["title"], re.I)
            if m:
                rec["match"] = overlay._norm_match(m)
        out.append(rec)
    out.sort(key=lambda r: (r["event"] == "Skills run", -len(r["robots"]), -r["q"]))
    # featured: four robots placed, high fit, different events
    seen, feat = set(), 0
    for rec in out:
        if feat < 4 and len(rec["robots"]) >= 3 and rec["q"] >= 0.7 and rec["event"] not in seen and rec.get("match"):
            ev = rec["event"] if len(rec["event"]) <= 24 else rec["event"][:24].rsplit(" ", 1)[0]
            rec["featured"] = True; rec["short"] = f"{ev} · {rec['match']}"
            seen.add(rec["event"]); feat += 1
    json.dump(out, open(os.path.join(a.site, "data", "gallery.json"), "w"), separators=(",", ":"))
    shutil.copy(a.facts, os.path.join(a.site, "data", "facts.json"))
    print("gallery", len(out), "frames from", len({r['video'] for r in out}), "videos; featured", feat)

if __name__ == "__main__":
    main()
