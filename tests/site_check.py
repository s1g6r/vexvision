"""Checks a built copy of the site before it goes live (run by .github/workflows/pages.yml, also works locally).
Usage: python tests/site_check.py <site url> [live url]
On a phone-sized and a laptop-sized screen it opens the home page, an event prep page, a team page and a report,
and fails if a page throws a script error, scrolls sideways or comes up empty. With a live url it also fails when
the new build has noticeably fewer replays or scouting reports than the live site, unless ALLOW_DROP=1."""
import asyncio, json, os, sys, urllib.request
from playwright.async_api import async_playwright

SITE = sys.argv[1].rstrip("/") + "/"
LIVE = sys.argv[2].rstrip("/") + "/" if len(sys.argv) > 2 else None
EV, TEAM = "64351", "2360A"
PAGES = [("home", "", "#prep-out", 2000), ("event prep", f"#event-{EV}-{TEAM}", "#prep-out", 2000),
         ("team page", f"#team-{TEAM}", "#result", 300), ("report", f"#report-{TEAM}", "#result", 300)]
SCREENS = [("phone", {"width": 390, "height": 844}, True), ("laptop", {"width": 1360, "height": 900}, False)]
problems = []


def count(base, path, f):
    with urllib.request.urlopen(base + path, timeout=60) as r:
        return f(json.load(r))


def compare_with_live():
    if not LIVE:
        return
    for what, path, f in [("replays", "data/replays/index.json", len), ("scouting reports", "data/reports.json", len)]:
        try:
            new, old = count(SITE, path, f), count(LIVE, path, f)
        except Exception as e:
            print(f"  couldn't compare {what} with the live site: {e}"); continue
        print(f"  {what}: {new} in this build, {old} live")
        if new < old * 0.98 and os.environ.get("ALLOW_DROP") != "1":
            problems.append(f"{what} dropped from {old} to {new} (put [allow-drop] in the commit message if that's intended)")


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get("CHROME") or None, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        for screen, vp, mobile in SCREENS:
            ctx = await b.new_context(viewport=vp, is_mobile=mobile, has_touch=mobile, service_workers="block")
            for name, h, sel, need in PAGES:
                pg = await ctx.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
                await pg.goto(SITE + h)
                try:
                    await pg.wait_for_function(f"(document.querySelector('{sel}')?.innerText || '').length > {need}", timeout=30000)
                except Exception:
                    problems.append(f"{screen} {name}: {sel} stayed (nearly) empty")
                try:
                    await pg.wait_for_function("window.__ready === true", timeout=60000)
                except Exception:
                    problems.append(f"{screen} {name}: the page never finished loading")
                await pg.wait_for_timeout(2500)
                st = await pg.evaluate("""({w: innerWidth, sw: document.documentElement.scrollWidth,
                    strip: document.querySelectorAll('#rp-list > button[data-id]').length, find: !!document.querySelector('#rpf-q')})""")
                if st["sw"] > st["w"] + 1:
                    problems.append(f"{screen} {name}: page is {st['sw']} px wide on a {st['w']} px screen")
                if name == "home" and not (st["find"] if mobile else st["strip"] > 10):
                    problems.append(f"{screen} home: the replay picker is missing")
                problems.extend(f"{screen} {name}: {e[:200]}" for e in errs)
                print(f"  {screen} {name}: {'ok' if not errs else f'{len(errs)} errors'}")
                await pg.close()
            await ctx.close()
        await b.close()

asyncio.run(main())
compare_with_live()
if problems:
    print("\nThe site check failed:"); [print(" -", x) for x in problems]; sys.exit(1)
print("Site check passed.")
