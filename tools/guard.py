#!/usr/bin/env python3
"""Looks at what is about to be committed, and refuses it unless it is small and of the right kind.

Run by the workflows between `git add` and `git commit`. Whatever went wrong before this point
(a submission that talks the intake into something, a bug, a change to a script), the commit that
reaches main can only be:

  - new recipe files (recipes/<name>.md), not more than a day's limit,
  - a few recipes moved to quarantine/ (recipes/<name>.md -> quarantine/<name>.md), and its log,
  - categories.json and reports.json changed.

Nothing else: no file deleted, no published recipe edited, no workflow, script, function or setting
touched. More than the limits in one run is refused whole, not cut down.

    python3 tools/guard.py        # exit 0: fine; exit 1: nothing is to be committed
"""
import re
import subprocess
import sys

MAX_ADDED = 40   # the day's limit for publishing (tools/accept.py): a run may not do more than a day may
MAX_MOVED = 10   # the day's limit for taking down (tools/takedown.py)
NAME = r"[a-z0-9][a-z0-9-]{0,80}"
ALWAYS = {"categories.json", "reports.json", "quarantine/LOG.txt"}


def main():
    out = subprocess.run(["git", "diff", "--cached", "--name-status", "-M50%"], capture_output=True, text=True, check=True).stdout
    added = moved = 0
    problems = []
    for line in out.splitlines():
        parts = line.split("\t")
        status, paths = parts[0], parts[1:]
        if status[0] == "A" and re.fullmatch(r"recipes/" + NAME + r"\.md", paths[0]):
            added += 1
        elif status[0] == "A" and re.fullmatch(r"quarantine/" + NAME + r"\.md", paths[0]):
            moved += 1  # a new file in quarantine: the move seen as add and delete is below
        elif status[0] == "R" and re.fullmatch(r"recipes/" + NAME + r"\.md", paths[0]) \
                and re.fullmatch(r"quarantine/" + NAME + r"\.md", paths[1]):
            moved += 1
        elif status[0] == "D" and re.fullmatch(r"recipes/" + NAME + r"\.md", paths[0]):
            pass  # the other half of a move; counted with the file that appeared in quarantine/
        elif status[0] in "AM" and paths[0] in ALWAYS:
            pass
        else:
            problems.append(line)
    if problems:
        print("REFUSED: this change touches more than it may:\n  " + "\n  ".join(problems[:20]))
        return 1
    if added > MAX_ADDED or moved > MAX_MOVED:
        print("REFUSED: too much for one run: " + str(added) + " added, " + str(moved) + " moved")
        return 1
    # nothing may have been deleted that was not moved
    deleted = sum(1 for l in out.splitlines() if l.startswith("D"))
    if deleted > moved:
        print("REFUSED: " + str(deleted) + " deleted, " + str(moved) + " moved")
        return 1
    print("fine: " + str(added) + " added, " + str(moved) + " moved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
