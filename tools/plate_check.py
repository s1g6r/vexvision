"""How plate reads alone would name each alliance, next to the names a match has now.

    python -m tools.plate_check RAW ID [ID ...]
"""
import json, os, sys
from vexvision import analyze as AN, teams as TM


def decide(raw, mid):
    R = json.load(open(os.path.join(raw, mid + ".json")))
    log = json.load(open(os.path.join(raw, mid + ".plates.json")))
    P = json.load(open(os.path.join(raw, mid + ".perc.json")))
    _, assigns = AN.run_tracker(P["det_log"])
    who = {}
    for t, a in assigns:
        for tid, j in a.items():
            if j is not None:
                who[(round(t, 2), j)] = tid
    plates = {}
    for t, j, reads in log:
        tid = who.get((round(t, 2), j))
        if tid is not None:
            plates.setdefault(tid, []).extend(tuple(r) for r in reads)
    out = []
    for al in ("red", "blue"):
        rb = [b for b in R["robots"] if b["alliance"] == al]
        if len(rb) != 2:
            continue
        tids = [b["track"] for b in rb]; teams = sorted(b["team"] for b in rb)
        nreads = sum(len(plates.get(t, [])) for t in tids)
        m, conf = TM.assign_alliance(tids, teams, plates)
        now = {b["track"]: b["team"] for b in rb}
        out.append({"id": mid, "alliance": al, "reads": nreads, "plate_conf": round(conf, 3),
                    "agree": all(m[t] == now[t] for t in tids), "now_conf": rb[0].get("confidence"),
                    "plate_map": m, "now": now})
    return out


if __name__ == "__main__":
    raw = sys.argv[1]
    for mid in sys.argv[2:]:
        for d in decide(raw, mid):
            print(json.dumps(d))
