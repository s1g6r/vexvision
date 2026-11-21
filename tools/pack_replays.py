"""Bundle the per-match replay files into a few packs (the artifact host allows 512 files).
Usage: python -m tools.pack_replays REPLAY_DIR
Writes REPLAY_DIR/pack/p<n>.json ({match id: replay}) and sets "pack" on each index entry.
Matches from one event share packs, at most PER per pack, so opening a replay loads its neighbours too."""
import json, os, sys
from collections import defaultdict

PER = 12

def main():
    rep = sys.argv[1]
    idx_p = os.path.join(rep, "index.json")
    idx = json.load(open(idx_p))
    by_ev = defaultdict(list)
    for e in idx:
        e.pop("pack", None)
        if os.path.exists(os.path.join(rep, e["id"] + ".json")):
            by_ev[e.get("event", "")].append(e)
    os.makedirs(os.path.join(rep, "pack"), exist_ok=True)
    old = {f for f in os.listdir(os.path.join(rep, "pack")) if f.endswith(".json")}
    n = 0
    for ev in sorted(by_ev):
        L = sorted(by_ev[ev], key=lambda e: e["id"])
        for i in range(0, len(L), PER):
            name = f"p{n}"; n += 1
            pack = {}
            for e in L[i:i + PER]:
                pack[e["id"]] = json.load(open(os.path.join(rep, e["id"] + ".json")))
                e["pack"] = name
            json.dump(pack, open(os.path.join(rep, "pack", name + ".json"), "w"), separators=(",", ":"))
            old.discard(name + ".json")
    for f in old:                     # packs left over from a bigger earlier run
        os.remove(os.path.join(rep, "pack", f))
    json.dump(idx, open(idx_p, "w"), indent=0)
    print(sum(1 for e in idx if e.get("pack")), "replays in", n, "packs")

if __name__ == "__main__":
    main()
