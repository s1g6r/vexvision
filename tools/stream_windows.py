"""Turn title reads into match windows and a Mac job list.
Usage: python -m tools.stream_windows TITLES.json EVENT_ID STREAM_ID PREFIX OUT_DIR [--step 30]
Writes OUT_DIR/windows.txt (id start length), OUT_DIR/jobs.txt (for mac_perceive.py) and OUT_DIR/matches.json
(for finish_perc.py). PREFIX names the ids, e.g. e64359-1 gives e64359-1-qual12."""
import json, os, sys

def main():
    titles, eid, stream, prefix, out = sys.argv[1:6]
    step = 30
    res = json.load(open(titles))
    runs, cur = {}, None
    for t, name, _ in res:
        if name and cur and cur[0] == name and t - cur[2] <= 2 * step:
            cur[2] = t
        elif name:
            cur = [name, t, t]; runs.setdefault(name, []).append(cur)
        else:
            cur = None
    win = {}
    for name, R in runs.items():
        _, t0, t1 = max(R, key=lambda r: r[2] - r[1])          # the longest run is the match itself
        a0 = max(0, t0 - 60)
        win[name] = (a0, min(a0 + 420, t1 + 150) - a0)
    ev = json.load(open("site2/data/official.json"))["events"][eid]
    ms = {m["m"]: m for m in ev["matches"]}
    ok = {k: v for k, v in win.items() if k in ms}
    os.makedirs(out, exist_ok=True)
    def mid(k):
        kind, num = k.split(" ", 1)
        return f"{prefix}-{kind.lower()}{num.replace(' ', '')}"
    order = sorted(ok, key=lambda k: ok[k][0])
    with open(os.path.join(out, "windows.txt"), "w") as f:
        for k in order:
            f.write(f"{mid(k)} {int(ok[k][0])} {int(ok[k][1])}\n")
    with open(os.path.join(out, "jobs.txt"), "w") as f:
        for k in order:
            f.write(f"{mid(k)}\t~/vexvisionstuff/{prefix}/clips/{mid(k)}.mp4\t" + json.dumps({"red": ms[k]["r"], "blue": ms[k]["b"]}) + "\n")
    json.dump([{"id": mid(k), "event": ev["short"], "match": k, "red": ms[k]["r"], "blue": ms[k]["b"],
                "start": int(ok[k][0]), "length": int(ok[k][1]), "stream": stream} for k in order],
              open(os.path.join(out, "matches.json"), "w"), indent=0)
    print(len(win), "titles found,", len(ok), "match the official schedule; skipped:", sorted(set(win) - set(ok))[:10])

if __name__ == "__main__":
    main()
