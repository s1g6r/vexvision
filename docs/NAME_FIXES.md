# Fixing a robot's name

Every replay has a "Wrong team on a robot? Tell us" link. It opens a GitHub issue that already says which match it is
and which team the replay put on each robot. The person writes what's wrong.

## Applying a fix

1. Open the match's reading: `/home/claude/work/raw/<match id>.json` (the match id is in the issue, in brackets).
   Its `robots` list has each robot's `track`, `alliance` and the `team` it was given.
2. Watch the replay to check the claim. The broadcast in the corner shows the same four robots marked.
3. Add the match to `data/name_fixes.json`: the track id and the team that robot really is. One robot per alliance is
   enough, since the other one must be its partner.

   ```json
   { "gl-qual64": { "0": "355Y" } }
   ```

4. Rebuild (`/home/claude/work/rebuild.sh`) and publish (`post.sh`).

A fix is treated as certain. It also helps the rest of the event: the robot's look is now known for sure, so other
matches with that team get named more often.

Tested on 22 Nov by forcing Great Lakes Qual 64's red alliance the other way round: that alliance flipped with
confidence 1.0 and the other 346 named alliances stayed the same.
