#!/usr/bin/env python3
"""Counts the votes that Mentors sent (netlify/functions/rate.js), by itself.

Run by GitHub (.github/workflows/accept.yml). A vote says "up" or "down" about one published
recipe, signed by the key of a Mentor that used it. It is counted when:
  - the recipe is published now, and the checksum in the vote is the text published now;
  - that key has not already made 30 vote changes today;
  - the key is not one of more than 300 first seen today (a flood of new keys waits for tomorrow).
One key has one vote for each recipe: a later vote replaces its earlier one, and "up" and "down"
are what the site shows, with nothing else. The result is ratings.json.

    python3 tools/vote.py [votes_dir] [--root REPO]
"""
import glob
import hashlib
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = [a for a in sys.argv[1:] if not a.startswith("--")]
if "--root" in sys.argv:
    ROOT = sys.argv[sys.argv.index("--root") + 1]
    args = [a for a in args if a != ROOT]

VOTES = args[0] if args else os.path.join(ROOT, "votes")
STATE = os.path.join(ROOT, "ratings.json")
PER_KEY_DAY = 30
NEW_KEYS_DAY = 300
ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
KEY = re.compile(r"^[0-9a-f]{16}$")


def load():
    try:
        with open(STATE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def main():
    state = load()
    votes = state.setdefault("votes", {})   # id -> {key: [vote, time]}
    keys = state.setdefault("keys", {})     # key -> first time seen
    today = state.setdefault("today", {})   # key -> [times of the last day]
    t = time.time()
    for k in list(today):
        today[k] = [x for x in today[k] if t - x < 86400]
        if not today[k]:
            del today[k]
    log = []
    for path in sorted(glob.glob(os.path.join(VOTES, "*.json"))):
        name = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as f:
                v = json.load(f)
            rid, sha, vote, source = str(v["id"]), str(v["sha256"]).lower(), v["vote"], str(v["source"])
        except (OSError, ValueError, KeyError, TypeError):
            log.append("IGNORED " + name + ": unreadable")
            continue
        recipe = os.path.join(ROOT, "recipes", rid + ".md")
        if not ID.match(rid) or vote not in ("up", "down") or not KEY.match(source) or not os.path.isfile(recipe):
            log.append("IGNORED " + name + ": not a vote for a published recipe")
            continue
        with open(recipe, "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() != sha:
                log.append("IGNORED " + name + ": that was another version of " + rid)
                continue
        if source not in keys:
            if sum(1 for first in keys.values() if t - first < 86400) >= NEW_KEYS_DAY:
                log.append("IGNORED " + name + ": too many new keys today")
                continue
            keys[source] = t
        if len(today.get(source, [])) >= PER_KEY_DAY:
            log.append("IGNORED " + name + ": too many votes from this key today")
            continue
        today.setdefault(source, []).append(t)
        votes.setdefault(rid, {})[source] = [vote, t]
        log.append("COUNTED " + vote + " for " + rid)
    for rid in list(votes):  # a recipe that is gone has no votes to keep
        if not os.path.isfile(os.path.join(ROOT, "recipes", rid + ".md")):
            del votes[rid]
    with open(STATE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, indent=1, sort_keys=True)
        f.write("\n")
    print("\n".join(log) or "no votes")


if __name__ == "__main__":
    main()
