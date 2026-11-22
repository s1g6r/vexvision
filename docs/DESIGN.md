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
