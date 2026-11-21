"""List every Override event that Illinois High School teams have played, most Illinois teams first.
Standard library only.  python tools/pc/il_events.py > pc_results/il_events.json"""
import json, sys, time, urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

BASE = "https://stats.2360arachnid.com/data/override"
get = lambda p: json.load(urllib.request.urlopen(f"{BASE}/{p}", timeout=30))

def main(region="Illinois"):
    teams = [t for t in get("leaderboard.json") if t.get("region") == region]
    def events(t):
        try:
            return t["number"], get(f"teams/{t['id']}.json").get("events", [])
        except Exception:
            return t["number"], []
    with ThreadPoolExecutor(8) as pool:
        per = dict(pool.map(events, teams))
    c = Counter(e for ev in per.values() for e in ev)
    meta = {e["id"]: e for e in get("meta.json")["events"]}
    out = []
    for eid, n in c.most_common():
        e = meta.get(eid, {})
        out.append({"event_id": eid, "name": e.get("name"), "date": e.get("date"), "status": e.get("status"),
                    "illinois_teams": n, "teams": e.get("teams"), "matches": e.get("matches")})
    json.dump({"region": region, "teams": len(teams), "events": out}, sys.stdout, indent=1)

if __name__ == "__main__":
    main(*(sys.argv[1:2]))
