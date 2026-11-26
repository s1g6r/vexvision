# Design notes

The site follows the Bloody Coconut Design + Impeccable skill: rounded forms, text-only buttons, plain words, no
headings made of two short statements.

## Scanner disposition (22 Nov 2026, `detect.mjs` on `site2/index.html`)

| Finding | Decision |
| --- | --- |
| Border accent on rounded element (`.tc`, 3px top border) | Kept. The red or blue top edge is how a card says which alliance a team is on, and the prep page is read at a glance between matches. Checked in screenshots at 16px radius: it follows the corner cleanly. |
| Overused font (Geist) | Kept. Body text is Geist for legibility at small sizes; the character comes from Big Shoulders Display in headings and numbers. |
| Broken image (`#h-photo`, `#s-photo`) | False positive: both get their `src` from script once a frame is picked. |
| Auto-scrolling marquee (`.ticker`) | Kept for the home page's results ticker. It stops for anyone with reduced motion turned on. |

## Phone layouts chosen (26 Nov)

The owner picked one option per area for phones; laptops keep the original layout (A) until those are decided.
`PHONE_PICK` in main.js holds the picks, and they apply at 640 px wide and below:

- Event prep matches: C (one match at a time, opening on the next one)
- Pick list: C (short rows that open; the table already stays on wider screens)
- Team page and report: C (one page, fold-out sections; the report link opens them all)
- Replay picker: B (team search and event list)
- Frame reader: C (folded behind one button)
- Event list: B (grouped into played and coming up)

options.js now always loads, since phones need it. The switcher button shows only with `?try=1` or an explicit choice,
and `?prep=a` (and so on) forces the original on a phone. Crossing the 640 px line re-renders event prep, the pick list
and the team page in place. The replay picker and frame reader are set when the page loads.
Checked at 390 px and 1360 px: phones get every pick, laptops get none, no script errors and no sideways scrolling.
Narrowing a laptop window swaps the team page to C and back.

## Layout options under trial (26 Nov)

Brief: show every area two or three ways so the owner can choose, cutting repeats and length, mostly on phones.
The current site is always option A. The others live in `site2/js/options.js`, which only loads when the address
has `?prep=b`, `?pick=c`, `?team=c`, `?rp=b`, `?read=c`, `?evpick=b` or `?try=1`. Nobody else sees them. A yellow
"Layout options" button switches between them, and `site2/options.html` shows them side by side with phone pictures.

- **main.js changes made for this:** the event page is split into `evHeader`, `evMatches`, `evPick` and `matchView`, the
  report into `reportParts` (one set of sections that every team-page layout uses), and the CSV export reads team
  order from `data-pick-n` so any pick-list layout can be exported. With no switch the output is byte-for-byte the
  same text as before (checked on 2360A's event, team and report pages).
- **Once options are chosen:** move the chosen code into main.js and its CSS into index.html, then delete
  options.js, options.html and `site2/options/`.
- **Scanner:** index.html shows the same findings as before, and options.html has only "Overused font (Geist)", kept for
  the same reason. The CSS injected by options.js isn't seen by the scanner. Its only accent border is the alliance
  colour on the left of `.who` rows in event prep B, used on purpose the same way as `.tc`.
- **Checks:** every option at 390 px and 1360 px: no script errors and no sideways scrolling. Prep C prints every match,
  not just the one on screen. No independent reviewer was used.

## Team page and report on phones (25 Nov)

Brief, from a friend testing on his phone: the deeper pages repeated the same things, some matches seemed to go
missing, and it wasn't clear which matches a report used.

- **Team page is the overview, the report is the detail.** The team page keeps official results, notes, a short
  scouting card (tags, up to three "watch for" lines, one button to the report) and one list of matches. The maps, tiles
  and summary sentences moved to the report, which no longer repeats the official results or the notes box.
- **One match list.** The 3D replay buttons and the YouTube rows were two lists of the same matches. Now each match is one
  row under its event heading, with side, partner, opponents, "3D replay" and "YouTube". It shows six and folds the rest
  behind "Show all N matches". Rows we couldn't use say why ("Couldn't tell which robot was…", "Too unclear to use").
- **Where the numbers come from.** Both pages show the same three counts (played this season, on video, used for
  scouting) and one sentence that accounts for every match left out: not filmed, on YouTube but not read yet, robot not
  identified, or too unclear. On the report this sits right under the team name, with the used matches folded into a
  `<details>` list grouped by event. Each report section says how many matches it is from.
- **Each sentence said once.** The summary list is gone; each sentence now opens the section it describes (Autonomous,
  Which Goals, What it carries, Driver control, The robot). The autonomous lead says how often Route A runs rather than
  restating the route, and the "keeps going back to" caption under the Goals was dropped because the sentence says it.
- **One number per stat.** Distance and time on the other side come from the report's own averages everywhere. The
  quals vs elims table was dropped; the summary already says whether the team plays differently in eliminations.
- **Mobile layout.** Official results rows stack into a four-figure grid. Match-by-match is a list of cards instead of a
  seven-column table. Route chips name the event when a team has more than one.
- **Sideways scrolling.** Tables in `.scroll` had no overflow rule, and a screen-reader label inside the event pick list
  escaped its box, which widened the whole page to about 860 px on a phone. `.scroll` now scrolls on its own and is
  positioned, and the page width stays at the screen width (checked at 390 px: scroll width 390).
- **Checks:** 390 px and 1360 px screenshots of 2360A, 1862A (two events), 2145Y (30 matches) and 4189R (no robot
  identified yet); the event prep page still renders; no script errors. Scanner rerun: the same four findings as the
  table above, nothing new. No independent reviewer was used.

## Added 22 Nov

- **Match plan picture** on each prep-page match: the four most-run autons on one field, your side bottom left. Colours are
  per team (gold you, green partner, pink and violet opponents) because two red or two blue lines would be hard to tell apart.
- **Pick list sort** as a row of text toggle buttons (pill shaped, pressed state filled), and a "With you" column with a
  small green or pink pill.
- **Your notes**: a rounded text box on reports and team pages, saved on the device only; a note shows as a soft gold strip
  on that team's prep-page card.
- **"From N matches on video"** under each card, so a read from one match isn't mistaken for a habit.
- **Match strip**: your matches as pill buttons in one horizontally scrolling row that sticks under the menu while the match
  cards are on screen and lets go after the last one. Results are a small green W or pink L; the next unplayed match is
  filled gold, the one place gold fills a control on this page. Jumps respect reduced motion.
- **Your mix** panel: a rounded panel of six sliders in a responsive grid, label left and its current word ("Off", "A
  little", "Some", "A lot") right, slider full width under them; gold accent to match the rest of the page. Words rather
  than numbers, because the weights only matter relative to each other.
- **Download the pick list** and **Copy my notes**: ghost buttons, text only, placed under the thing they act on.
- Scanner rerun on the rendered event page with the mix panel open: the same three findings as above, nothing new.
- **Mark picked**: a small text pill at the end of each pick-list row. A picked row dims, its number is struck through and
  it drops to the bottom, so the best teams left are always at the top during alliance selection. "Clear picks" is a
  plain underlined text button next to the one-line help, shown only when something is marked. Your own team has no
  button.
- **Print**: event pages and reports switch to a light sheet (white, dark text, light borders), with the menu, forms,
  sliders, strip and buttons hidden. The field drawings keep their dark background so the coloured routes stay visible.
