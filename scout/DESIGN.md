# vexvision scout: design notes

## Brief

- **Who:** V5RC high school drivers, scouts and coaches. They usually use it on a phone at an event, or on a laptop the night before.
- **Job:** before a match or alliance selection, find every Override video of a team: their matches, who they partnered with and played against, and what their robot looks like.
- **Primary action:** type a team number.
- **Success:** from the home page, someone gets to a team's match list in one search, and every row opens the original video.
- **What it's built on:** `data/catalog.json` from `tools/catalog.py`, which holds 266 Override videos from YouTube with event, round and alliances parsed out of each title. Older seasons are filtered out because Robot Stats High Stakes titles don't name the game; this was checked against the frames. A team appears once a video title names it.
- **Pinned by the owner:**
  - Override only.
  - No methodology on the page.
  - No dark background with a neon accent like the first site.
  - Text-only buttons.
  - Rounded forms.
  - No headings made of two short statements.
  - Plain wording.

## Direction

The page works like the printed match schedule a scout carries around an event, with the team they're watching run over in highlighter.

- **Picture:** a real elimination bracket with one team's run highlighted. On a phone it opens on just that team's path, with a button to show the whole bracket.
- **Highlighter:** the same yellow mark sits behind the followed team's number on every page. It is the only motion on the site (a 450 ms swipe, turned off under reduced motion).
- **Colour:** taken from the field.
  - White ground, ink text, and a light tile grey for bands.
  - Alliance red and blue are used only to show alliances: team numbers and the partner/opponent bars.
  - Highlighter yellow `#ffe14a` marks the team you follow, with dark text on it in both themes.
  - Dark theme: the same roles on `#111315`.
- **Type:** Archivo only, on purpose. The width axis carries the hierarchy:
  - wdth 62–70 at weight 800–900 for team numbers and titles;
  - wdth 75–80 for team numbers in lists;
  - wdth 100 for reading text.
- **Geometry:** 16 px rounded search field, pill buttons and chips, 12 px match cells. Hairline rules separate rows instead of cards.

## Pages

| Page | What it shows |
|---|---|
| Home | Search and recent teams; the most-filmed teams; the bracket for the event with the most elimination video; events; robot videos |
| `#team-471B` | The team number, its facts and its robot video, then matches grouped by event, then robot/skills videos, then partner and opponent tallies. An unknown team gets an empty state with teams from the same club |
| `#event-<slug>` | The bracket (bold alliances appear in a later round; no final winner is claimed because titles don't say), other videos, and the teams named |
| `#events`, `#teams` | Every event (plus Final Four recaps), and every team with its video count |

## Scanner disposition (Impeccable detect.mjs)

- `single-font`: kept on purpose. Archivo's width axis (62 to 100) and weights 400 to 900 carry the display/body contrast, and that was checked in the renders.

## Verification

- **Renders:** Playwright at 1440×900 (light and dark) and 390×844 for home, team (471B, 2360A), unknown team (9999Z), event (Speedway), the events page and the teams page. No horizontal overflow and no script errors.
- **Function test:**
  - typing "19" suggests 197E and 1965B;
  - arrow down plus Enter opens 1965B;
  - the phone bracket shows 4 cells and expands to 15;
  - recent teams are remembered.
- **Not done:** no independent reviewer was used.
