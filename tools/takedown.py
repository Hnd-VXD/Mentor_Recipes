#!/usr/bin/env python3
"""Takes a recipe down when it deserves it, by itself.

Run by GitHub (.github/workflows/accept.yml) for a report that a Mentor sent
(netlify/functions/report.js), and after the rules have changed (--rescan).

A report is never taken on its word. It names a recipe and the checksum of the text the Mentor
looked at, and:
  - if that is not the text published now, it is ignored (it was another version);
  - the recipe is looked at again here with the rules of inspector.py: a serious finding takes it
    down at once, whoever reported it, or even if nobody did;
  - a suspicion that rules cannot show (a Mentor's reading of what it asks for) takes it down only
    when several different sources have said so within a week.

Taking down is moving the file to quarantine/. Nothing is deleted: putting it back is a move
back, and the recipe's page is gone from the site at the next build.

    python3 tools/takedown.py [reports_dir] [--rescan] [--root REPO]
"""
import glob
import json
import os
import re
import shutil
import sys
import time
import hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = [a for a in sys.argv[1:] if not a.startswith("--")]
if "--root" in sys.argv:
    ROOT = sys.argv[sys.argv.index("--root") + 1]
    args = [a for a in args if a != ROOT]
sys.path.insert(0, ROOT)
from inspector import inspect  # noqa: E402

REPORTS = args[0] if args else os.path.join(ROOT, "reports")
SOURCES_NEEDED = 3        # different sources that must have said it
WINDOW = 7 * 24 * 3600
PER_SOURCE_DAY = 10       # reports taken from one key in a day
MAX_PER_DAY = 10          # recipes taken down in a day, by anything; past that it stops and waits
STATE = os.path.join(ROOT, "reports.json")
ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def now():
    return time.time()


def sha_of(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def taken_today():
    try:
        with open(os.path.join(ROOT, "quarantine", "LOG.txt"), encoding="utf-8") as f:
            return sum(1 for line in f if line.startswith(time.strftime("%Y-%m-%d", time.gmtime())))
    except OSError:
        return 0


def quarantine(rid, why, log):
    if taken_today() >= MAX_PER_DAY:  # a flood of reports, or rules gone wrong: nothing more by itself today
        log.append("CIRCUIT OPEN: not taking " + rid + " down; the limit for today is " + str(MAX_PER_DAY))
        return
    src = os.path.join(ROOT, "recipes", rid + ".md")
    os.makedirs(os.path.join(ROOT, "quarantine"), exist_ok=True)
    shutil.move(src, os.path.join(ROOT, "quarantine", rid + ".md"))
    with open(os.path.join(ROOT, "quarantine", "LOG.txt"), "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M ", time.gmtime()) + rid + ": " + why + "\n")
    log.append("QUARANTINED " + rid + ": " + why)


def serious(path):
    _report, counts, _sha = inspect(path)
    return counts["high"]


def main():
    state = load_state()
    tally = state.setdefault("recipes", {})     # id -> {"sources": {source: time}}
    per_source = state.setdefault("sources", {})  # source -> [times]
    log = []
    t = now()

    if "--rescan" in sys.argv:  # the rules changed: everything published is looked at again
        for path in sorted(glob.glob(os.path.join(ROOT, "recipes", "*.md"))):
            rid = os.path.basename(path)[:-3]
            n = serious(path)
            if n:
                quarantine(rid, str(n) + " serious finding(s) under the present rules", log)
        print("\n".join(log) or "rescan: nothing to take down")
        return

    for path in sorted(glob.glob(os.path.join(REPORTS, "*.json"))):
        name = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as f:
                rep = json.load(f)
            rid, sha, kind = str(rep.get("id", "")), str(rep.get("sha256", "")).lower(), rep.get("kind")
            source = str(rep.get("source", ""))[:16] or "unknown"
        except (OSError, ValueError):
            log.append("IGNORED " + name + ": unreadable")
            continue
        recipe = os.path.join(ROOT, "recipes", rid + ".md")
        if not ID.match(rid) or not os.path.isfile(recipe):
            log.append("IGNORED " + name + ": no such recipe published")
            continue
        if sha_of(recipe) != sha:
            log.append("IGNORED " + name + ": that was another version of " + rid)
            continue
        # one source cannot take things down by volume
        recent = [x for x in per_source.get(source, []) if t - x < 24 * 3600]
        if len(recent) >= PER_SOURCE_DAY:
            log.append("IGNORED " + name + ": too many reports from this source today")
            continue
        per_source[source] = recent + [t]

        n = serious(recipe)
        if n:  # the rules say so themselves: whoever sent the report, it goes
            quarantine(rid, "verified: " + str(n) + " serious finding(s) when looked at again", log)
            tally.pop(rid, None)
            continue
        if kind != "reading":
            log.append("NOTED " + name + ": the rules find nothing serious in " + rid)
            continue
        sources = {s: x for s, x in tally.setdefault(rid, {}).get("sources", {}).items() if t - x < WINDOW}
        sources[source] = t
        tally[rid] = {"sources": sources}
        if len(sources) >= SOURCES_NEEDED:
            quarantine(rid, "reported as suspicious by " + str(len(sources)) + " different sources", log)
            tally.pop(rid, None)
        else:
            log.append("COUNTED " + name + ": " + str(len(sources)) + " of " + str(SOURCES_NEEDED) + " sources for " + rid)

    with open(STATE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, indent=1)
        f.write("\n")
    print("\n".join(log) or "nothing to do")


if __name__ == "__main__":
    main()
