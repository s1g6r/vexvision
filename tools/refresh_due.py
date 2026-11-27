"""Decides whether the scheduled results refresh should run now (used by .github/workflows/pages.yml).
The workflow wakes every 20 minutes. It refreshes every time around a tracked event (the day before it starts
through two days after), and otherwise only on the run just after 00:00, 06:00, 12:00 and 18:00 UTC.
Writes due=true|false to $GITHUB_OUTPUT (or prints it)."""
import datetime as dt, json, os

now = dt.datetime.now(dt.timezone.utc)
today = now.date()
ev = json.load(open("site2/data/official.json"))["events"].values()
busy = [e["short"] for e in ev if e.get("date") and dt.date.fromisoformat(e["date"]) - dt.timedelta(days=1) <= today <= dt.date.fromisoformat(e["date"]) + dt.timedelta(days=2)]
due = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" or bool(busy) or (now.hour % 6 == 0 and now.minute < 20)
line = f"due={'true' if due else 'false'}"
print(line, "| events on:", ", ".join(busy) or "none")
if os.environ.get("GITHUB_OUTPUT"):
    open(os.environ["GITHUB_OUTPUT"], "a").write(line + "\n")
