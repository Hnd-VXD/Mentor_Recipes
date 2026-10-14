#!/usr/bin/env python3
"""Takes the submissions in incoming/ and publishes the ones that pass, by themselves.

Run by GitHub (.github/workflows/accept.yml) on a submission; nobody has to look. A submission
is one JSON file, written by the site's submit function (netlify/functions/submit.js):

    {"recipe": "# Title ...", "category": "desktop", "new_category": {"id", "name", "description"},
     "source": "<salted hash of where it came from>", "time": "2026-10-13T20:00:00Z"}

Every gate has to pass, or the submission is dropped and the reason is written to the job log:
  1. the shape: size, a title, "## Steps", valid UTF-8
  2. the rules of inspector.py (the same Mentor uses): any serious finding stops it
  3. no secret, key, token or email address in it
  4. a category that exists, or a new one that is valid and not a copy of one that exists
  5. the limits: a number a day, a number from one source a day

What is published is the text as received, below a header of our own (never the sender's).
Nothing in a recipe is ever run here: it is read, as text.

    python3 tools/accept.py [incoming_dir] [--root REPO]
"""
import difflib
import glob
import json
import os
import re
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = [a for a in sys.argv[1:] if not a.startswith("--")]
if "--root" in sys.argv:
    ROOT = sys.argv[sys.argv.index("--root") + 1]
    args = [a for a in args if a != ROOT]
sys.path.insert(0, ROOT)
from inspector import inspect, scan_secrets, similarity, parse_setup  # noqa: E402

INCOMING = args[0] if args else os.path.join(ROOT, "incoming")
MAX_BYTES = 120000
PER_DAY = 40          # recipes published in one day
PER_SOURCE_DAY = 5    # from one key in one day
PER_NEW_KEY_DAY = 2   # a key that has nothing published yet
NEW_CATEGORIES_DAY = 3
SAME = 0.95      # as much alike as that: the same recipe again; it is counted, not published twice
VERSION = 0.5    # as much alike as that: a version of it, shown on the same page
CATEGORY_ID = re.compile(r"^[a-z][a-z0-9-]{2,29}$")
CATEGORY_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9 ,&'/-]{2,39}$")
RESERVED = {"index", "raw", "r", "c", "recipes", "assets", "404", "static", "api", "admin"}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60].strip("-")


def split_header(text):
    """The text without any header the sender put at its top: the header is ours alone."""
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end >= 0:
            return text[end + 4:].lstrip("\n")
    return text


def read_published():
    """[(id, header dict)] of what is on the site now."""
    out = []
    for path in glob.glob(os.path.join(ROOT, "recipes", "*.md")):
        head = {}
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read(4000)
        if text.startswith("---\n") and "\n---" in text[4:]:
            for line in text[4:text.find("\n---", 4)].splitlines():
                m = re.match(r"^([A-Za-z_]+)\s*:\s*(.*)$", line)
                if m:
                    head[m.group(1).lower()] = m.group(2).strip()
        out.append((os.path.basename(path)[:-3], head))
    return out


def similar(a, b):
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= 0.8 or a in b or b in a


def read_text(rid):
    with open(os.path.join(ROOT, "recipes", rid + ".md"), encoding="utf-8", errors="replace") as f:
        return split_header(f.read())


def closest(body, published):
    """(id, score) of the published recipe most like this one, or (None, 0). A version of a
    version belongs to the first of them (its header's `group`), so a family has one head."""
    best, score = None, 0.0
    for rid, _head in published:
        try:
            s = similarity(body, read_text(rid))
        except OSError:
            continue
        if s > score:
            best, score = rid, s
    if best:
        head = dict(published).get(best, {})
        best = head.get("group") or best
    return best, score


def decide(sub, categories, published, today, new_today):
    """(True, record) or (False, why)."""
    text = sub.get("recipe")
    if not isinstance(text, str) or not text.strip():
        return False, "no recipe text"
    if len(text.encode("utf-8", errors="replace")) > MAX_BYTES:
        return False, "too long"
    body = split_header(text.replace("\r\n", "\n")).strip("\n") + "\n"
    title = next((l[2:].strip() for l in body.splitlines() if l.startswith("# ")), "")
    if not title or len(title) > 100:
        return False, "no title, or one that is too long"
    if "## Steps" not in body or "## Check that it works" not in body:
        return False, "not in the form of a recipe (needs ## Steps and ## Check that it works)"

    # 2 and 3: the rules and the secrets
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(body)
        probe = f.name
    try:
        report, counts, _sha = inspect(probe)
    finally:
        os.unlink(probe)
    if counts["high"]:
        first = [l for l in report.splitlines() if l.startswith("- line")][:3]
        return False, f"{counts['high']} serious finding(s): " + " | ".join(first)
    leaks = scan_secrets(body)
    if leaks:
        return False, "holds " + ", ".join(sorted({what for what, _x in leaks}))

    # alike: the same again, or a version of one that is there
    group = ""
    near, score = closest(body, published)
    if near and score >= SAME:
        return False, "the same recipe is already published as " + near + " (counted as another Mentor that made it)"
    if near and score >= VERSION:
        group = near
    # A fork: the recipe says which one it was made from (its "Based on" row, which Mentor writes when the
    # user improves a recipe of the site). Shown with that one, as a version of it, however much it changed.
    based = re.search(r"(?mi)^\|\s*Based on\s*\|\s*([a-z0-9][a-z0-9-]{0,80})\s*\|\s*$", body)
    if based and based.group(1) in dict(published):
        group = dict(published)[based.group(1)].get("group") or based.group(1)

    # 5: the limits
    source = str(sub.get("source", ""))[:16]
    from_today = [h for _id, h in published if h.get("submitted") == today and h.get("status") == "auto"]
    if len(from_today) >= PER_DAY:
        return False, "the limit for today has been reached"
    if source:
        mine_today = sum(1 for h in from_today if h.get("source") == source)
        known = any(h.get("source") == source for _i, h in published)
        if mine_today >= (PER_SOURCE_DAY if known else PER_NEW_KEY_DAY):
            return False, "too many from this key today"

    # 4: the category
    wanted = str(sub.get("category") or "")
    new = sub.get("new_category") if isinstance(sub.get("new_category"), dict) else None
    added = None
    if wanted in categories:
        category = wanted
    elif new:
        nid, name, desc = str(new.get("id", "")), str(new.get("name", "")).strip(), str(new.get("description", "")).strip()
        # The main categories are the maintainer's; what is made on the fly is a sub-category,
        # under one of them (under "other" when none is named).
        parent = str(new.get("parent") or "other")
        if parent not in categories or categories[parent].get("parent"):
            parent = "other"
        if not (CATEGORY_ID.match(nid) and CATEGORY_NAME.match(name) and 10 <= len(desc) <= 140) or nid in RESERVED:
            category = "other"
        elif re.search(r"https?:|www\.|@", name + desc):
            category = "other"
        else:
            near = next((cid for cid, c in categories.items()
                         if similar(nid, cid) or similar(name.lower(), c["name"].lower())), None)
            if near:
                category = near  # it already exists, under that name
            elif new_today >= NEW_CATEGORIES_DAY:
                category = "other"
            else:
                category, added = nid, {"id": nid, "parent": parent, "name": name, "description": desc}
    else:
        category = "other"

    summary = next((l.lstrip("> ").strip() for l in body.splitlines() if l.startswith(">")), "")
    summary = re.sub(r"[`*_\[\]<>]", "", summary)[:200]
    rid = slug(title) or "recipe"
    if rid in RESERVED:
        rid += "-recipe"
    taken = {i for i, _h in published}
    base, n = rid, 2
    while rid in taken:
        rid, n = f"{base}-{n}", n + 1
    setup = parse_setup(body)
    stamped = ("gnome: " + setup["gnome"] + "\n" if setup.get("gnome") else "") + \
              ("or_later: yes\n" if setup.get("or_later") else "") + \
              ("kernel: " + setup["kernel"] + "\n" if setup.get("kernel") else "")
    header = ("---\ncategory: " + category + "\nsummary: " + summary.replace("\n", " ") + "\nsubmitted: " + today +
              "\nstatus: auto\nsource: " + source + ("\ngroup: " + group if group else "") + "\n" + stamped + "---\n")
    return True, {"id": rid, "text": header + body, "category": category, "new_category": added, "counts": counts,
                  "group": group}


def main():
    today = time.strftime("%Y-%m-%d", time.gmtime())
    cat_path = os.path.join(ROOT, "categories.json")
    with open(cat_path, encoding="utf-8") as f:
        data = json.load(f)
    categories = {c["id"]: c for c in data["categories"]}
    published = read_published()
    new_today = published_now = rejected = 0
    for path in sorted(glob.glob(os.path.join(INCOMING, "*.json"))):
        name = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as f:
                sub = json.load(f)
            ok, result = decide(sub, categories, published, today, new_today)
        except (OSError, ValueError, UnicodeError) as e:
            ok, result = False, "unreadable: " + str(e)
        if not ok:
            rejected += 1
            print("REJECTED " + name + ": " + str(result))
            continue
        with open(os.path.join(ROOT, "recipes", result["id"] + ".md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(result["text"])
        if result["new_category"]:
            data["categories"].insert(max(0, len(data["categories"]) - 1), result["new_category"])  # before "other"
            categories[result["new_category"]["id"]] = result["new_category"]
            new_today += 1
        published.append((result["id"], {"submitted": today, "status": "auto", "source": str(sub.get("source", ""))[:16],
                                         "group": result["group"]}))
        published_now += 1
        print("PUBLISHED " + result["id"] + " in " + result["category"] + (" (new category)" if result["new_category"] else "")
              + (" as a version of " + result["group"] if result["group"] else "")
              + " - " + str(result["counts"]["medium"]) + " to look at")
    if new_today:
        with open(cat_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
    print("done: " + str(published_now) + " published, " + str(rejected) + " dropped")


if __name__ == "__main__":
    main()
