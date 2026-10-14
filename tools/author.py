#!/usr/bin/env python3
"""Applies what the author of a recipe asked for: a new text for it, or taking it off the site.

Run by GitHub (.github/workflows/accept.yml) for a change that a Mentor sent
(netlify/functions/manage.js). Only the key that published a recipe may change it: the `source`
in the recipe's header (written by tools/accept.py when it was published) has to be the key that
signed the change. Nobody else can update or remove a recipe that is not theirs.

  - "withdraw": the recipe is moved to withdrawn/ (nothing is deleted; putting it back is a move back).
  - "update": the new text goes through the same gates as a new recipe (its form, the rules, no
    secret) and replaces the old one under the same id, category and header; `updated` says when.
    Votes stay with the recipe, but only votes for the new text count from now on (tools/vote.py
    checks the checksum).

Limits: 10 changes from one key a day, 40 in all.

    python3 tools/author.py [changes_dir] [--root REPO]
"""
import glob
import json
import os
import re
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = [a for a in sys.argv[1:] if not a.startswith("--")]
if "--root" in sys.argv:
    ROOT = sys.argv[sys.argv.index("--root") + 1]
    args = [a for a in args if a != ROOT]
sys.path.insert(0, ROOT)
from inspector import inspect, scan_secrets, parse_setup  # noqa: E402

CHANGES = args[0] if args else os.path.join(ROOT, "changes")
STATE = os.path.join(ROOT, "authors.json")
MAX_BYTES = 120000
PER_KEY_DAY = 10
PER_DAY = 40
ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
KEY = re.compile(r"^[0-9a-f]{16}$")


def header_of(text):
    """(dict of the header, body) of a published recipe."""
    head = {}
    if text.startswith("---\n") and "\n---" in text[4:]:
        end = text.find("\n---", 4)
        for line in text[4:end].splitlines():
            m = re.match(r"^([A-Za-z_]+)\s*:\s*(.*)$", line)
            if m:
                head[m.group(1).lower()] = m.group(2).strip()
        return head, text[end + 4:].lstrip("\n")
    return head, text


def strip_header(text):
    return header_of(text)[1] if text.startswith("---\n") else text


def checked_body(text):
    """(True, body) when the new text passes the gates of a new recipe, else (False, why)."""
    if not isinstance(text, str) or not text.strip():
        return False, "no recipe text"
    if len(text.encode("utf-8", errors="replace")) > MAX_BYTES:
        return False, "too long"
    body = strip_header(text.replace("\r\n", "\n")).strip("\n") + "\n"
    title = next((l[2:].strip() for l in body.splitlines() if l.startswith("# ")), "")
    if not title or len(title) > 100:
        return False, "no title, or one that is too long"
    if "## Steps" not in body or "## Check that it works" not in body:
        return False, "not in the form of a recipe"
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(body)
        probe = f.name
    try:
        report, counts, _sha = inspect(probe)
    finally:
        os.unlink(probe)
    if counts["high"]:
        return False, f"{counts['high']} serious finding(s)"
    leaks = scan_secrets(body)
    if leaks:
        return False, "holds " + ", ".join(sorted({what for what, _x in leaks}))
    return True, body


def new_header(head, body, today):
    summary = next((l.lstrip("> ").strip() for l in body.splitlines() if l.startswith(">")), "")
    summary = re.sub(r"[`*_\[\]<>]", "", summary)[:200].replace("\n", " ")
    setup = parse_setup(body)
    lines = ["category: " + head.get("category", "other"), "summary: " + summary, "submitted: " + head.get("submitted", today),
             "updated: " + today, "status: " + (head.get("status") or "auto"), "source: " + head.get("source", "")]
    if head.get("group"):
        lines.append("group: " + head["group"])
    if setup.get("gnome"):
        lines.append("gnome: " + setup["gnome"])
    if setup.get("or_later"):
        lines.append("or_later: yes")
    if setup.get("kernel"):
        lines.append("kernel: " + setup["kernel"])
    return "---\n" + "\n".join(lines) + "\n---\n"


def main():
    try:
        with open(STATE, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    t = time.time()
    today = time.strftime("%Y-%m-%d", time.gmtime())
    recent = {k: [x for x in v if t - x < 86400] for k, v in state.get("changes", {}).items()}
    recent = {k: v for k, v in recent.items() if v}
    log = []
    for path in sorted(glob.glob(os.path.join(CHANGES, "*.json"))):
        name = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as f:
                ch = json.load(f)
            action, rid, source = ch["action"], str(ch["id"]), str(ch["source"])
        except (OSError, ValueError, KeyError, TypeError):
            log.append("IGNORED " + name + ": unreadable")
            continue
        recipe = os.path.join(ROOT, "recipes", rid + ".md")
        if action not in ("update", "withdraw") or not ID.match(rid) or not KEY.match(source) or not os.path.isfile(recipe):
            log.append("IGNORED " + name + ": not a change to a published recipe")
            continue
        with open(recipe, encoding="utf-8", errors="replace") as f:
            head, _old = header_of(f.read())
        if head.get("source") != source:
            log.append("REFUSED " + name + ": " + rid + " was not published by this key")
            continue
        if len(recent.get(source, [])) >= PER_KEY_DAY or sum(len(v) for v in recent.values()) >= PER_DAY:
            log.append("IGNORED " + name + ": the limit of changes for today has been reached")
            continue
        if action == "withdraw":
            os.makedirs(os.path.join(ROOT, "withdrawn"), exist_ok=True)
            shutil.move(recipe, os.path.join(ROOT, "withdrawn", rid + ".md"))
            with open(os.path.join(ROOT, "withdrawn", "LOG.txt"), "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M ", time.gmtime()) + rid + ": withdrawn by its author\n")
            log.append("WITHDRAWN " + rid + " at its author's request")
        else:
            ok, body = checked_body(ch.get("recipe"))
            if not ok:
                log.append("REFUSED " + name + ": the new text of " + rid + " did not pass: " + body)
                continue
            with open(recipe, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_header(head, body, today) + body)
            log.append("UPDATED " + rid + " with its author's new text")
        recent.setdefault(source, []).append(t)
    state["changes"] = recent
    with open(STATE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, indent=1, sort_keys=True)
        f.write("\n")
    print("\n".join(log) or "no changes")


if __name__ == "__main__":
    main()
