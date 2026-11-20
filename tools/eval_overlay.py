"""Score the overlay reader against video titles (which name the match and teams).

A frame counts only if it shows a live match overlay (the reader found a match
name or two teams per alliance). Title parsing: "Qual 165", "QF #2-1",
"Finals 2", plus team numbers like 2145X.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vexvision import overlay

TITLE_MATCH = re.compile(r"\b(Qual(?:ification)?|Q|R16|QF|SF|Finals?|F)\s*#?\s*(\d{1,3})(?:\s*-\s*(\d{1,2}))?", re.I)

def title_match(t):
    m = TITLE_MATCH.search(t)
    return overlay._norm_match(m) if m else None

def main(root):
    vids = json.load(open(os.path.join(root, "videos.json")))
    ocr = json.load(open(os.path.join(root, "ocr.json")))
    n = {"frames": 0, "match_cmp": 0, "match_ok": 0, "team_cmp": 0, "team_ok": 0, "team_read": 0,
         "alliance_cmp": 0, "alliance_ok": 0, "clock": 0}
    bad = []
    for vid, v in vids.items():
        tm = title_match(v["title"])
        tteams = set(t.upper() for t in v.get("teams", []))
        for p in v.get("frames", []):
            k = os.path.basename(p)
            if k not in ocr:
                continue
            r = overlay.parse(ocr[k], (1280, 720))
            if not (r.match or (len(r.red) == 2 and len(r.blue) == 2)):
                continue
            n["frames"] += 1
            n["clock"] += r.clock is not None
            if tm and r.match:
                n["match_cmp"] += 1
                ok = r.match.replace(" ", "") == tm.replace(" ", "")
                n["match_ok"] += ok
                if not ok: bad.append((k, "match", r.match, tm, v["title"][:70]))
            if len(tteams) == 4:
                got = set(r.red + r.blue)
                n["team_cmp"] += 4; n["team_read"] += len(got)
                n["team_ok"] += len(got & tteams)
                # alliance split check from titles like "A & B vs C & D"
                m = re.search(r"(\w+)\s*(?:&|and|,)\s*(\w+)\s*vs\.?\s*(\w+)\s*(?:&|and|,)\s*(\w+)", v["title"])
                if m and len(r.red) == 2 and len(r.blue) == 2:
                    a1, a2 = {m.group(1).upper(), m.group(2).upper()}, {m.group(3).upper(), m.group(4).upper()}
                    n["alliance_cmp"] += 1
                    n["alliance_ok"] += {frozenset(r.red), frozenset(r.blue)} == {frozenset(a1), frozenset(a2)}
                if got - tteams: bad.append((k, "teams", sorted(got), sorted(tteams), v["title"][:70]))
    print(json.dumps(n, indent=1))
    pct = lambda a, b: f"{100*a/max(1,b):.1f}% ({a}/{b})"
    print("match name right:", pct(n["match_ok"], n["match_cmp"]))
    print("teams found (of 4 in title):", pct(n["team_ok"], n["team_cmp"]), " wrong reads:", n["team_read"] - n["team_ok"])
    print("alliances split right:", pct(n["alliance_ok"], n["alliance_cmp"]))
    print("clock read:", pct(n["clock"], n["frames"]))
    for b in bad[:25]:
        print(b)

if __name__ == "__main__":
    main(sys.argv[1])
