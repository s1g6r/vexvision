"""Build the Override video catalog: every match, reveal and skills video we can
find on YouTube, with event, match name and alliances parsed out of the title.

Only Override (2026-27) videos are kept. A title must say Override, or come from
a 2026 event stream (some Robot Stats match titles leave the game name out).
Older seasons that share channels with Override (High Stakes events like Sugar
Rush or Mecha Mayhem) are dropped.

Usage: python -m tools.catalog --out data/catalog.json [--seed data/yt/videos.json]
"""
import argparse, json, os, re, time
from tools.collect_youtube_frames import search
from tools.collect_channel import channel_videos

QUERIES = [
    "vex override qual", "vex override match", "vex override finals", "vex override semifinals",
    "vex override quarterfinals", "vex override round of 16", "vex override signature event",
    "override signature qual", "vex override reveal", "vex override robot reveal",
    "vex override skills", "vex override driver skills", "vex override auton",
    "vex v5 override 2026", "override 2026 final four", "speedway override", "great planes signature override",
    "highlander summit 2026", "mall of america override", "MOA signature override", "smoky mountain forge override",
    "harbor havoc 2026 vex", "hong kong signature override", "lobstah bowl override", "blank's beginnings override",
    "ghost halloween override", "override elite local", "vex override vex vault", "robot stats override",
    "vex override worlds reveal", "vex override early season", "vex override tournament", "v5rc override",
    "override 256 skills", "vex override teaser", "vex override match highlights", "vex override full match",
]
CHANNELS = ["@vexroboticsvault", "@robotstats"]
TEAM = r"\d{1,5}[A-Z]"
TEAM_RE = re.compile(rf"\b({TEAM})\b")
MATCH_RE = re.compile(
    r"\b(Qual(?:ification)?s?\s*#?\d+|Q\s?\d+|R16\s*#?\d+-\d+|QF\s*#?\d+-\d+|SF\s*#?\d+-\d+|"
    r"Final\s*#?\d+-\d+|Full Finals|Finals?|Semi-?Finals?|Quarter-?finals?|Round of 16)\b", re.I)

VEX = re.compile(r"\bvex|\bv5|\bvrc\b|v5rc|signature|\bsig\b|robot|\bqual|\bfinal|\bauton|skills|reveal|\b\d{1,5}[A-Z]\b", re.I)
JUNK = re.compile(r"push back|high stakes|world championship|vex u\b|vex iq|fortnite|song|music|mashup|zombies|murder drones|toyota", re.I)

def is_override(title):
    t = title.lower()
    if JUNK.search(title) or not VEX.search(title):
        return False
    return "override" in t or bool(re.search(r"\b2026\b", t) and re.search(r"\bsig\b|signature|summit|havoc|opener", t))

def alliances(title):
    """Pull 'A & B vs C & D' (or 'A vs B') out of a title. Team names between
    numbers ('471B Moonshot vs 2623K Kingsman') are allowed."""
    m = re.search(rf"({TEAM})(?:\s+[^&|()]*?)?\s*(?:&|,)\s*({TEAM})[^|()]*?\bvs\.?\s*({TEAM})(?:\s+[^&|()]*?)?\s*(?:&|,)\s*({TEAM})", title)
    if m:
        return [m.group(1), m.group(2)], [m.group(3), m.group(4)]
    m = re.search(rf"\b({TEAM})\b[^|&()]*?\bvs\.?\s*({TEAM})\b", title)
    if m:
        return [m.group(1)], [m.group(2)]
    return None, None

def kind(title, red):
    t = title.lower()
    if red:
        return "match"
    if "reveal" in t or "teaser" in t or "showcase" in t or "pits & parts" in t or "explanation" in t:
        return "robot"
    if "skill" in t or re.search(r"\b\d{2,3} (point|pts)", t):
        return "skills"
    if "final four" in t or "finals collection" in t or "recap" in t or "matches" in t:
        return "event"
    if MATCH_RE.search(title):
        return "match"
    return "other"

EVENT_HINTS = [
    ("Speedway", "Speedway Signature"), ("Great Planes", "Great Planes Signature"),
    ("Highlander Summit", "Highlander Summit Signature"), ("Harbor Havoc", "Harbor Havoc Signature"),
    ("Smoky Mountain", "Smoky Mountain Forge Signature"), ("SmokyMountain", "Smoky Mountain Forge Signature"),
    ("Mall of America", "Mall of America Signature"), ("MOA", "Mall of America Signature"),
    ("Blank.'s Beginnings", "Blank.'s Beginnings"), ("Lobstah Bowl", "Lobstah Bowl"),
    ("Hong Kong Signature", "Hong Kong Signature"), ("HK SIG", "Hong Kong Signature"),
    ("Silk Road Link", "The Silk Road Link"), ("GHOST", "GHOST Halloween Spotlight"),
    ("Tri-Valley", "Tri-Valley"), ("War Eagle", "War Eagle"),
]

def event(title):
    m = re.match(r"^(.+?)(?: 2026)?:\s*Final Four", title)
    if m:
        return m.group(1).strip()
    for k, name in EVENT_HINTS:
        if k.lower() in title.lower():
            return name
    return None

def match_name(title):
    m = MATCH_RE.search(title)
    if not m:
        return None
    s = m.group(1)
    s = re.sub(r"^Qual(?:ification)?s?\s*#?", "Qual ", s, flags=re.I)
    s = re.sub(r"^Q\s?(\d+)", r"Qual \1", s)
    s = re.sub(r"\s*#\s*", " ", s)
    return s.strip()

def parse(v):
    t = v["title"]
    red, blue = alliances(t)
    teams = sorted(set(TEAM_RE.findall(t)) - {"2026", "256"}) if not red else red + blue
    return {**v, "event": event(t), "match": match_name(t), "red": red, "blue": blue,
            "kind": kind(t, red), "teams": teams}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/catalog.json")
    ap.add_argument("--seed", default="data/yt/videos.json")
    ap.add_argument("--pages", type=int, default=25)
    a = ap.parse_args()
    found = {}
    if os.path.exists(a.seed):
        for k, v in json.load(open(a.seed)).items():
            found[k] = {x: v.get(x) for x in ("id", "title", "channel", "length", "published")}
    for h in CHANNELS:
        try:
            for v in channel_videos(h, pages=a.pages):
                found.setdefault(v["id"], {**v, "channel": h})
        except Exception as e:
            print("channel failed", h, e)
    for q in QUERIES:
        for short in (True, False):
            try:
                for v in search(q, short=short):
                    found.setdefault(v["id"], v)
            except Exception as e:
                print("search failed", q, e)
            time.sleep(0.4)
    keep = [parse(v) for v in found.values() if is_override(v["title"])]
    keep.sort(key=lambda v: (v["kind"] != "match", v["event"] or "~", v["title"]))
    json.dump(keep, open(a.out, "w"), indent=0)
    from collections import Counter
    print(len(found), "seen,", len(keep), "Override;", Counter(v["kind"] for v in keep))
    print(len({t for v in keep for t in v["teams"]}), "teams")

if __name__ == "__main__":
    main()
