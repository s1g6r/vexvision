r"""Read only the matches an Illinois team played in a stream, instead of all of them.

Why this exists. Two of the six events on the Illinois list are big out-of-state Signature
events, and they are nearly all footage we don't need:

  Speedway (64359)  236 matches, 1 Illinois team  (355T, 9 matches)
  UND (64244)       273 matches, 4 Illinois teams (355B 355T 355V 355Z, 35 matches)

`watch.py` reads every match in a stream it accepts. For Speedway Day 1 -- 7.7 hours of video --
that is somewhere around ten nights of this PC running flat out to reach nine matches that
mention an Illinois team. This reads the same stream and skips the rest.

It is a wrapper, not a copy: it replaces `stream_job.official` with a version that hides matches
with nobody from the region in them, and then runs `stream_job` exactly as normal. Hidden matches
take the path `stream_job` already has for a match it has no teams for -- "not in the official
results, skipped" -- so nothing else changes, and the match ids and output files are identical to
what `watch.py` would have written.

  python pc_results\read_region.py --video zhGs-5gah_Y --event 64359 --prefix e64359-0- [--region Illinois]

Use the prefix `watch.py` would have used (`e<event>-<n>-`, n counting streams from 0) so that a
later `watch.py` run skips these matches instead of reading them again under a second name.
"""
import json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "pc"))
sys.path.insert(0, ROOT)
import stream_job as S

LEADERBOARD = "https://stats.2360arachnid.com/data/override/leaderboard.json"

def region_teams(region):
    board = json.load(urllib.request.urlopen(LEADERBOARD, timeout=30))
    return {t["number"] for t in board if t.get("region") == region}

def patch(region):
    """stream_job.official -> the same thing with other teams' matches left out."""
    want = region_teams(region)
    plain = S.official

    def official(event):
        name, off = plain(event)
        keep = {m: s for m, s in off.items() if set(s["red"] + s["blue"]) & want}
        print(f"{region}: {len(want)} teams; keeping {len(keep)} of {len(off)} matches at this event")
        for m in sorted(keep):
            print(f"  {m}: red {keep[m]['red']} blue {keep[m]['blue']}")
        return name, keep

    S.official = official

def main():
    argv = sys.argv[1:]
    region = "Illinois"
    if "--region" in argv:
        i = argv.index("--region")
        region = argv[i + 1]; del argv[i:i + 2]
    patch(region)
    sys.argv = [sys.argv[0]] + argv
    S.main()

if __name__ == "__main__":
    main()
