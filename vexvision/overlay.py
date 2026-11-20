"""Read the broadcast overlay: match name, period, clock, the four teams, scores.

VEX broadcasts are produced with Tournament Manager overlays that vary by
event producer, so this reader is layout-agnostic: it OCRs the frame once and
interprets the text by pattern and position instead of fixed pixel boxes.

- Match name: QUAL 165, Q12, R16 2-1, QF 1-1, SF 2-1, FINAL 1, FINALS 2 ...
- Clock: m:ss, plus AUTONOMOUS / DRIVER CONTROL / ENDGAME words near it.
- Teams: tokens like 2145X, under RED ALLIANCE / BLUE ALLIANCE headers.
  Overlays often print a rank next to a team ("32K 6"); when the event's
  team list is known, the reader keeps only valid team numbers.
- Scores: large numbers inside the alliance panels, when the producer shows them.
"""
import re
import numpy as np
from dataclasses import dataclass, field, asdict

MATCH_RE = re.compile(
    r"\b(QUAL(?:IFIER|IFICATION)?|Q|R16|R32|QF|SF|FINALS?|F|PRACTICE|P)\s*#?\s*(\d{1,3})(?:\s*-\s*(\d{1,2}))?\b", re.I)
CLOCK_RE = re.compile(r"\b([0-2]?\d)[:.](\d\d)\b")
TEAM_RE = re.compile(r"(?<![A-Z0-9])(\d{1,5}[A-Z])(?![A-Z])")
ROUND_NORM = {"QUAL": "Q", "QUALIFIER": "Q", "QUALIFICATION": "Q", "Q": "Q", "R16": "R16", "R32": "R32",
              "QF": "QF", "SF": "SF", "FINAL": "F", "FINALS": "F", "F": "F", "PRACTICE": "P", "P": "P"}

@dataclass
class OverlayRead:
    match: str = None          # normalised, e.g. "Q165", "SF2-1", "F1"
    period: str = None         # "auton" | "driver" | "pre" | "post" | None
    clock: int = None          # seconds left in the period
    red: list = field(default_factory=list)
    blue: list = field(default_factory=list)
    red_score: int = None
    blue_score: int = None
    event_title: str = None
    raw: list = field(default_factory=list)
    def as_dict(self):
        d = asdict(self); d.pop("raw"); return d

_ocr = None
def _engine():
    global _ocr
    if _ocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr = RapidOCR()
    return _ocr

def ocr(img):
    res, _ = _engine()(img)
    out = []
    for box, txt, conf in res or []:
        xs = [p[0] for p in box]; ys = [p[1] for p in box]
        out.append({"text": txt, "conf": float(conf), "x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys)})
    return out

def _norm_match(m):
    kind = ROUND_NORM.get(m.group(1).upper(), m.group(1).upper())
    s = f"{kind} {int(m.group(2))}"
    if m.group(3):
        s += f"-{int(m.group(3))}"
    return s

def split_team_token(tok, valid=None):
    """'32K6' -> '32K'; with a valid set, pick the valid prefix."""
    tok = tok.upper().replace(" ", "").replace("O", "0") if tok[:1].isdigit() else tok.upper()
    if valid:
        best = None
        for i in range(2, len(tok) + 1):
            if tok[:i] in valid:
                best = tok[:i]
        if best:
            return best
    m = re.match(r"^(\d{1,5}[A-Z])", tok)
    return m.group(1) if m else None

def parse(items, size, valid_teams=None):
    w, h = size
    r = OverlayRead(raw=items)
    # match name: prefer text in the top band
    cands = []
    for it in items:
        t = it["text"].replace("#", " ")
        t = re.sub(r"(?i)\b(QUAL|QF|SF|R16|FINALS?)(\d)", r"\1 \2", t)
        m = MATCH_RE.search(t)
        if m and len(m.group(1)) > 1 or (m and it["y0"] < 0.15 * h):
            cands.append((it["y0"] > 0.2 * h, -it["conf"], _norm_match(m)))
    if cands:
        r.match = sorted(cands)[0][2]
    # event title: longest text in the top band
    top = [it for it in items if it["y1"] < 0.08 * h and len(it["text"]) > 12]
    if top:
        r.event_title = max(top, key=lambda it: len(it["text"]))["text"]
    # period words
    words = " ".join(it["text"].upper().replace(" ", "") for it in items)
    if "AUTON" in words:
        r.period = "auton"
    elif "DRIVER" in words or "ENDGAME" in words:
        r.period = "driver"
    # clock: the largest m:ss text (by box height)
    clocks = []
    for it in items:
        m = CLOCK_RE.fullmatch(it["text"].strip().replace(" ", ""))
        if m and int(m.group(2)) < 60:
            secs = int(m.group(1)) * 60 + int(m.group(2))
            if secs <= 120:
                clocks.append((it["y1"] - it["y0"], secs))
    if clocks:
        r.clock = max(clocks)[1]
    # alliance panels: anchors "RED ALLIANCE" / "BLUE ALLIANCE"; else colour words
    anchors = {}
    for it in items:
        u = it["text"].upper().replace(" ", "")
        if "REDALLIANCE" in u or u == "RED":
            anchors.setdefault("red", it)
        if "BLUEALLIANCE" in u or u == "BLUE":
            anchors.setdefault("blue", it)
    teams = []
    for it in items:
        txt = it["text"].upper().replace(" ", "")
        if CLOCK_RE.fullmatch(txt) or MATCH_RE.fullmatch(txt):
            continue
        for tok in re.findall(r"\d{1,5}[A-Z]\d{0,3}", txt):
            t = split_team_token(tok, valid_teams)
            if t and (not valid_teams or t in valid_teams):
                teams.append((t, (it["x0"] + it["x1"]) / 2, (it["y0"] + it["y1"]) / 2, it))
    if "red" in anchors and "blue" in anchors:
        ra, ba = anchors["red"], anchors["blue"]
        vertical = abs(ra["y0"] - ba["y0"]) > abs(ra["x0"] - ba["x0"])
        for t, cx, cy, it in teams:
            if vertical:
                if abs(cx - (ra["x0"] + ra["x1"]) / 2) > 0.2 * w:
                    continue
                lo, hi = sorted([ra["y0"], ba["y0"]])
                side = ("red" if ra["y0"] < ba["y0"] else "blue") if lo <= cy < hi else ("blue" if ra["y0"] < ba["y0"] else "red") if cy >= hi else None
            else:
                side = "red" if abs(cx - ra["x0"]) < abs(cx - ba["x0"]) else "blue"
            if side and t not in r.red + r.blue:
                getattr(r, side).append(t)
    else:
        # fall back to pixel colour behind the text is not available here; keep order
        uniq = []
        for t, *_ in teams:
            if t not in uniq:
                uniq.append(t)
        if len(uniq) == 4:
            r.red, r.blue = uniq[:2], uniq[2:]
    r.red, r.blue = r.red[:2], r.blue[:2]
    # running scores: big bare numbers inside each alliance panel
    if "red" in anchors and "blue" in anchors and teams and len(r.red) == 2 and len(r.blue) == 2:
        th = np.median([it["y1"] - it["y0"] for _, _, _, it in teams])
        ra, ba = anchors["red"], anchors["blue"]
        vertical = abs(ra["y0"] - ba["y0"]) > abs(ra["x0"] - ba["x0"])
        cands = {"red": [], "blue": []}
        for it in items:
            txt = it["text"].strip()
            if not re.fullmatch(r"\d{1,3}", txt):
                continue
            hgt = it["y1"] - it["y0"]
            if hgt < 1.3 * th:
                continue
            cx, cy = (it["x0"] + it["x1"]) / 2, (it["y0"] + it["y1"]) / 2
            if vertical:
                if abs(cx - (ra["x0"] + ra["x1"]) / 2) > 0.2 * w:
                    continue
                lo, hi = sorted([ra["y0"], ba["y0"]])
                first = "red" if ra["y0"] < ba["y0"] else "blue"
                side = first if lo <= cy < hi else ("blue" if first == "red" else "red") if cy >= hi else None
            else:
                side = "red" if abs(cx - ra["x0"]) < abs(cx - ba["x0"]) else "blue"
            if side:
                cands[side].append((hgt, int(txt)))
        if cands["red"]:
            r.red_score = max(cands["red"])[1]
        if cands["blue"]:
            r.blue_score = max(cands["blue"])[1]
    return r

def read(img, valid_teams=None):
    h, w = img.shape[:2]
    return parse(ocr(img), (w, h), valid_teams)
