"""Join the official results (published by the stats site) to the matches we track.

Reads data/official/ev_<event id>.json (stats.2360arachnid.com/data/override/events/<id>.json)
and the season leaderboard, and writes site2/data/official.json:
  matches: our match id -> official teams and scores
  teams:   team number -> season numbers plus per-event numbers
"""
import datetime
import argparse, json, re, glob, os
from collections import defaultdict

EVENTS = {  # our event names -> official event id
    "Illini Cornfield Clash Jr. (Fall 2026)": 64351, "Great Planes Signature": 64813,
    "Mall of America Signature": 64244, "The Silk Road Link": 64392, "Tri-Valley": 64632,
    "Highlander Summit Signature": 64246, "Speedway Signature": 64359,
    "GHOST Halloween Spotlight": 65564, "Harbor Havoc Signature": 64926,
    "Smoky Mountain Forge Signature": 64846, "Great Lakes #1": 65014, "Lake Park": 64295, "IPSD League": 66342,
    "Cornfield Clash Winter": 64756,
    "Niles": 65760, "Glenbrook South": 64352, "Great Lakes #2": 65015, "Great Lakes #3": 65016,
    "Illinois State Championship": 65018,
    "One World Signature": 64557, "Hong Kong Signature": 64288,
    # coming Signature events (the Worlds field plays these; read them as their streams go up)
    "WAVE at WPI Signature": 65280, "Slugger Signature": 64727, "St. Andrews Bangkok Signature": 64498,
    "iSTEMn Signature": 64435, "PAS-VEX Signature": 64562, "LAUNCH Signature": 64247,
    "Sunshine Showdown Signature": 64952, "Sugar Rush Signature": 64671,
}
ROUND = {"Qual": 2, "QF": 3, "SF": 4, "Final": 5, "R16": 6}

def parse_match(name):
    m = re.match(r"Qual (\d+)$", name or "")
    if m:
        return 2, 1, int(m.group(1))
    m = re.match(r"(R16|QF|SF|Final) (\d+)-(\d+)$", name or "")
    if m:
        return ROUND[m.group(1)], int(m.group(2)), int(m.group(3))
    return None

def load_events(d):
    out = {}
    for f in glob.glob(os.path.join(d, "ev_*.json")):
        e = json.load(open(f)); out[e["id"]] = e
    return out

def event_numbers(e):
    """Per-team numbers from one event's matches: average points scored and allowed, wins."""
    num = {t["id"]: t["number"] for t in e["teams"]}
    agg = defaultdict(lambda: {"scored": [], "allowed": [], "elim": 0})
    for m in e["matches"]:
        if m.get("rs") is None or m.get("bs") is None or (m["rs"] == 0 and m["bs"] == 0):
            continue
        for side, own, opp in (("red", m["rs"], m["bs"]), ("blue", m["bs"], m["rs"])):
            for tid in m[side]:
                a = agg[num.get(tid, str(tid))]; a["scored"].append(own); a["allowed"].append(opp)
                if m["round"] != 2:
                    a["elim"] += 1
    return num, agg

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--official", default="data/official")
    ap.add_argument("--index", default="site2/data/replays/index.json")
    ap.add_argument("--leaderboard", default="data/official/leaderboard.json")
    ap.add_argument("--out", default="site2/data/official.json")
    a = ap.parse_args()
    E = load_events(a.official)
    idx = json.load(open(a.index))
    matches, teams = {}, {}
    for r in idx:
        eid = EVENTS.get(r.get("event")); pm = parse_match(r.get("match"))
        if not eid or eid not in E or not pm:
            continue
        e = E[eid]; num = {t["id"]: t["number"] for t in e["teams"]}
        hit = [m for m in e["matches"] if (m["round"], m["inst"], m["num"]) == pm]
        if not hit:
            continue
        m = hit[0]
        matches[r["id"]] = {"event_id": eid, "red": [num.get(t, str(t)) for t in m["red"]], "blue": [num.get(t, str(t)) for t in m["blue"]],
                            "rs": m.get("rs"), "bs": m.get("bs")}
    for eid, e in E.items():
        num, agg = event_numbers(e)
        for t in e["teams"]:
            n = t["number"]; g = agg.get(n)
            ev = {"event_id": eid, "event": e["name"], "date": e["date"], "rank": t.get("rank"), "record": t.get("record"),
                  "wp": t.get("wp"), "ap": t.get("ap"), "sp": t.get("sp"), "skills": t.get("skills"), "rating": t.get("rating_now"),
                  "teams": len(e["teams"])}
            if g and g["scored"]:
                ev["avg_scored"] = round(sum(g["scored"]) / len(g["scored"]), 1)
                ev["avg_allowed"] = round(sum(g["allowed"]) / len(g["allowed"]), 1)
                ev["played"] = len(g["scored"]); ev["elim_played"] = g["elim"]
            teams.setdefault(n, {"name": t.get("name"), "id": t["id"], "events": []})["events"].append(ev)
    if os.path.exists(a.leaderboard):
        lb = json.load(open(a.leaderboard)); N = len(lb)
        for row in lb:
            if row["number"] in teams:
                teams[row["number"]]["season"] = {"rank": row["rank"], "of": N, "rating": row["rating"], "record": row["record"],
                                                  "matches": row["matches"], "skills": row.get("skills"), "region": row.get("region")}
    for t in teams.values():
        t["events"].sort(key=lambda x: x["date"])
    events = {}
    RN = {2: "Qual", 3: "QF", 4: "SF", 5: "Final", 6: "R16"}
    ours = {v: k for k, v in EVENTS.items()}
    for eid, e in E.items():
        num, agg = event_numbers(e)
        ms = []
        for m in sorted(e["matches"], key=lambda m: ({2: 0, 6: 1, 3: 2, 4: 3, 5: 4}.get(m["round"], 9), m["inst"], m["num"])):
            if m["round"] not in RN:
                continue
            nm = f"Qual {m['num']}" if m["round"] == 2 else f"{RN[m['round']]} {m['inst']}-{m['num']}"
            ms.append({"m": nm, "r": [num.get(t, str(t)) for t in m["red"]], "b": [num.get(t, str(t)) for t in m["blue"]],
                       "rs": m.get("rs"), "bs": m.get("bs"), "p": m.get("p")})
        tl = []
        for t in e["teams"]:
            g = agg.get(t["number"])
            tl.append({"n": t["number"], "name": t.get("name"), "rank": t.get("rank"), "record": t.get("record"), "rating": t.get("rating_now") or t.get("rating_pre"),
                       "skills": t.get("skills"), "avg": round(sum(g["scored"]) / len(g["scored"]), 1) if g and g["scored"] else None})
        events[eid] = {"name": e["name"], "short": ours.get(eid, e["name"]), "date": e["date"], "status": e.get("status"), "teams": tl, "matches": ms}
    # when the results were last pulled, so the site can say how fresh they are
    stamp = os.path.join(a.official, "fetched.txt")
    if os.path.exists(stamp):
        fetched = open(stamp).read().strip()
    else:
        src = glob.glob(os.path.join(a.official, "*.json"))
        fetched = datetime.datetime.fromtimestamp(max(os.path.getmtime(f) for f in src), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if src else None
    json.dump({"fetched": fetched, "matches": matches, "teams": teams, "events": events}, open(a.out, "w"), separators=(",", ":"))
    print(f"{len(matches)} of {len(idx)} tracked matches joined, {len(teams)} teams")

if __name__ == "__main__":
    main()
