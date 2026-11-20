# vexvision site: design notes

## Brief
- **Audience:** VEX V5RC High School teams and scouts (students and coaches), starting with 2360A Arachnid.
- **Jobs:** *operate* (analyse a broadcast screenshot, replay an analysed match, work out Override scores) and *read* (how the system works, how accurate it is).
- **Primary action:** drop a screenshot of any Override broadcast and get the field map with robot positions.
- **Known:** the models, calibration and accuracy numbers come from vexvision; the gallery is real frames from YouTube match videos (credited and linked). **Assumed:** most visits are on a laptop at home or a phone in the stands. **Needed later:** real full-match outputs from the Mac pipeline.

## Direction
For scouts mid-event, put a real broadcast frame next to its top-down field diagram, with the white tape traced on both, and set everything in the condensed lettering of the match overlay on field-tile grey and tape white, so the page says *your stream, measured* while the screenshot tool stays one click away.

- **Type:** Barlow Condensed (overlay-style headings and figures), Barlow (body).
- **Colour:** tile grey and tape white carry the page; alliance red `#e5484d` and blue `#2d7ff9` only mean alliances; pin yellow `#f5c400` is the single sharp accent (the primary button, the live marker).
- **Geometry:** rounded panels (16 px), pill chips, octagons only where the field has octagons (goals).
- **Motion:** one purposeful move: the tape traces onto the frame, then robot dots settle onto the map. Off under reduced motion.
- **Buttons:** text only, no arrows. **Headings:** single descriptive thoughts, no two-short-statement cadence.

## Anti-references
- Generic dark "AI dashboard" with neon accents and fake charts.
- A stock hero with a slogan and three feature cards.
- Scout's own landing look: we show our own frames and numbers.

## Verification record
- The Bloody Coconut repo's Impeccable scanner could not be run here (running the repo's setup scripts was blocked in this environment), so no scanner disposition is recorded. Checks done instead: manual review against the skill's anti-slop prompts and owner preferences, rendered screenshots at desktop and phone widths, and the JS calibration test (`site/test/calib.test.mjs`).
