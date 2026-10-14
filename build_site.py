#!/usr/bin/env python3
"""Builds the Mentor recipes site into dist/ from recipes/*.md.

Plain Python, standard library only (3.8 or later), so that Netlify can run it with nothing to
install:  python3 build_site.py

What goes in:   recipes/<id>.md       a recipe, with a few header lines (see CONTRIBUTING.md)
                categories.json       the categories, and what each is for
What comes out: dist/                 static pages, no scripts; the recipes themselves as .md;
                dist/index.json       the list, for Mentor to read

Every recipe is looked at by the same rules Mentor uses before it follows one (inspector.py),
and the report is on the recipe's page. A recipe is text from a stranger: it is never shown
as HTML, only as escaped text, and no image or script from it is ever loaded.
"""
import hashlib
import html
import json
import os
import re
import shutil
import sys
import time

from inspector import inspect, features, parse_setup

ROOT = os.path.dirname(os.path.abspath(__file__))
RECIPES = os.path.join(ROOT, "recipes")
DIST = os.path.join(ROOT, "dist")
DOWNLOAD = "https://github.com/Hnd-VXD/Mentor_OS/releases/latest/download/MentorSetup.exe"
RELEASES = "https://github.com/Hnd-VXD/Mentor_OS/releases/latest"
SOURCE = "https://github.com/Hnd-VXD/Mentor_OS"
HUB = "https://github.com/Hnd-VXD/Mentor_Recipes"


def esc(text):
    return html.escape(str(text), quote=True)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "other"


# --- reading the files ----------------------------------------------------------------------

def split_front_matter(text):
    """({"key": "value"}, the rest). The header is between two lines of three dashes."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    meta = {}
    for line in text[4:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m:
            meta[m.group(1).lower()] = m.group(2).strip().strip("\"'")
    return meta, text[end + 4:].lstrip("\n")


def load_categories():
    with open(os.path.join(ROOT, "categories.json"), encoding="utf-8") as f:
        data = json.load(f)
    return {c["id"]: c for c in data["categories"]}


def based_on(body):
    """The id of the recipe this one was made from (its "Based on" row), or ""."""
    found = re.search(r"(?mi)^\|\s*Based on\s*\|\s*([a-z0-9][a-z0-9-]{0,80})\s*\|\s*$", body)
    return found.group(1) if found else ""


def written_by(body):
    """The model a recipe says wrote it (its "Written by" row, which Mentor fills in itself), or ""."""
    found = re.search(r"(?mi)^\|\s*Written by\s*\|\s*(.+?)\s*\|\s*$", body)
    return re.sub(r"[^A-Za-z0-9 .()/+-]", "", found.group(1)).strip()[:80] if found else ""


def load_recipes(categories):
    found = []
    for name in sorted(os.listdir(RECIPES)):
        if not name.endswith(".md") or name.startswith("."):
            continue
        path = os.path.join(RECIPES, name)
        with open(path, "rb") as f:
            raw = f.read()
        text = raw.decode("utf-8", errors="replace")
        meta, body = split_front_matter(text)
        title = next((l[2:].strip() for l in body.splitlines() if l.startswith("# ")), name[:-3])
        summary = meta.get("summary") or next(
            (l.lstrip("> ").strip() for l in body.splitlines() if l.startswith(">")), "")
        category = meta.get("category", "other")
        if category not in categories:
            print(f"warning: {name}: category '{category}' is not in categories.json; shown under Other", file=sys.stderr)
            category = "other"
        report, counts, _sha = inspect(path)
        report = report.replace(path, "recipes/" + name)  # the page must not say where this was built
        found.append({
            "id": name[:-3], "title": title, "summary": summary, "category": category,
            "status": meta.get("status", ""), "submitted": meta.get("submitted", ""), "group": meta.get("group", ""),
            "author": meta.get("source", ""), "updated": meta.get("updated", ""),
            "model": written_by(body), "based_on": based_on(body),
            # from the header the intake wrote; for one added by hand, from its own "Made on" row
            "setup": {k: v for k, v in (("gnome", meta.get("gnome") or parse_setup(body).get("gnome", "")),
                                        ("kernel", meta.get("kernel") or parse_setup(body).get("kernel", "")),
                                        ("or_later", meta.get("or_later") or ("yes" if parse_setup(body).get("or_later") else ""))) if v},
            "sha256": hashlib.sha256(raw).hexdigest(), "body": body, "raw": raw,
            "report": report, "counts": counts,
        })
    found.sort(key=lambda r: (r["submitted"], r["title"]), reverse=True)
    by_id = {r["id"]: r for r in found}
    for r in found:  # a version belongs to the head of its group, which is not itself a version
        head = by_id.get(r["group"])
        r["head"] = head["id"] if head and not head["group"] else ""
    for r in found:
        r["versions"] = [v for v in found if v["head"] == r["id"]]
    return found


# --- Markdown, the small part of it that recipes use, with nothing passed through ---------------

INLINE_CODE = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)")
IMAGE = re.compile(r"!\[([^\]\n]*)\]\([^)\n]*\)")
BOLD = re.compile(r"\*\*([^*\n]+)\*\*")


def inline(text):
    """Escaped text with `code`, **bold** and links to http(s) only. Images become their words."""
    out = esc(IMAGE.sub(lambda m: m.group(1), text))
    out = INLINE_CODE.sub(lambda m: f"<code>{m.group(1)}</code>", out)
    out = BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", out)
    return LINK.sub(lambda m: f'<a href="{m.group(2)}" rel="noopener noreferrer nofollow">{m.group(1)}</a>', out)


def markdown(text):
    lines = text.splitlines()
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            out.append(f"<pre><code>{esc(chr(10).join(block))}</code></pre>")
        elif re.match(r"^#{1,6}\s", line):
            level = min(len(line.split(" ")[0]) + 1, 6)  # the page has its own h1
            out.append(f"<h{level}>{inline(line.lstrip('#').strip())}</h{level}>")
            i += 1
        elif line.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i].lstrip("> ").rstrip())
                i += 1
            out.append(f"<blockquote>{inline(' '.join(quote))}</blockquote>")
        elif line.strip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            body = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
            cells = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
            out.append(f"<table>{cells}</table>")
        elif re.match(r"^\s*([-*]|\d+\.)\s+", line):
            ordered = bool(re.match(r"^\s*\d+\.", line))
            items = []
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                items.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i]))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(t)}</li>" for t in items) + f"</{tag}>")
        elif line.strip() in ("---", "***"):
            out.append("<hr>")
            i += 1
        elif not line.strip():
            i += 1
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,6}\s|>|\||```|\s*([-*]|\d+\.)\s)", lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(out)


# --- the pages ------------------------------------------------------------------------------

SIDE = {"mains": [], "children": {}}  # filled by build_pages: the main categories, and what is in each


def sidebar(depth, current):
    """The left panel: the library, the main categories and under each its sub-categories, with counts."""
    up = "../" * depth
    total = sum(t for _c, t, _subs in SIDE["mains"])
    out = [f'<div class="lib"><span>Recipe library</span><b>{total} .md</b></div>',
           f'<a class="side-all" href="{up}recipes/index.html"><i class="ico">\u25a4</i> All recipes <span>{total}</span></a>']
    for c, count_, subs in SIDE["mains"]:
        here = ' aria-current="page"' if c["id"] == current else ""
        out.append(f'<a class="main"{here} href="{up}c/{c["id"]}/index.html">{esc(c["name"])} <span>{count_}</span></a>')
        for sc, k in subs:
            there = ' aria-current="page"' if sc["id"] == current else ""
            out.append(f'<a class="subl"{there} href="{up}c/{sc["id"]}/index.html"><i>\u21b3</i> {esc(sc["name"])} <span>{k}</span></a>')
    return "".join(out)


def page(title, body, depth=0, description="Recipes for Mentor, an Arch Linux that you talk to.", current=None):
    up = "../" * depth
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="stylesheet" href="{up}style.css">
<link rel="icon" href="{up}mentor.png">
</head><body>
<header class="top"><div class="wrap">
<a class="brand" href="{up}index.html"><img src="{up}mentor.png" alt="" width="34" height="34"><span><b>Mentor</b><i>recipes</i></span></a>
<form class="search" role="search" hidden><input type="search" placeholder="Search recipes   ( / )" aria-label="Search recipes" autocomplete="off" spellcheck="false"><div class="results" hidden></div></form>{SORT if '<article class="card"' in body else ''}
<nav class="links"><a href="{SOURCE}">Source</a><a class="cta" href="{DOWNLOAD}">Get Mentor</a></nav>
</div></header>
<div class="wrap layout">
<aside class="side" aria-label="Categories">{sidebar(depth, current)}</aside>
<main>
{body}
</main>
</div>
<footer><div class="wrap">Mentor is an experiment, written with the help of AI and not audited by anyone independent.
Recipes are instructions from other people: Mentor reads each one with you first and tells you everything it would do.
<a href="{HUB}">The recipes repository</a> · <a href="{SOURCE}">Mentor on GitHub</a></div></footer>
<script src="{up}search.js" data-root="{up}" defer></script>
</body></html>
"""


def badge(counts):
    if counts["high"]:
        return f'<span class="badge bad">{counts["high"]} serious</span>'
    if counts["medium"]:
        return f'<span class="badge care">{counts["medium"]} to look at</span>'
    return '<span class="badge ok">nothing found</span>'


# The thumbs Mentor itself draws (mentor-thumb-up-symbolic.svg in Mentor): one outline in the colour
# of the text around it, rather than emoji, which every system draws differently.
THUMB_PATH = ('<path d="M1 7h3v8H1z"/><path d="M5.25 7.2 8.6 1.3c.95-.25 2.3.55 2 2.15L10.1 6.5h3.4c1 0 1.75.9 '
              '1.55 1.9l-1 5.2c-.15.8-.85 1.4-1.65 1.4h-7.15z"/>')


def thumb(which):
    turn = ' transform="rotate(180 8 8)"' if which == "down" else ""
    return (f'<svg class="thumb" viewBox="0 0 16 16" width="13" height="13" fill="currentColor" aria-hidden="true">'
            f'<g{turn}>{THUMB_PATH}</g></svg>')


def votes(r):
    """What Mentors that used it said: up and down counts, or nothing while nobody has."""
    if not (r.get("up") or r.get("down")):
        return ""
    return f'<span class="badge votes" title="Mentors that used it said so">{thumb("up")} {r["up"]} {thumb("down")} {r["down"]}</span>'


def recipe_card(r, categories, up):
    """One recipe in a list: its category, what Mentors said, the title, one line, and what to do with it."""
    cat = categories[r["category"]]
    example = '<span class="badge example">example</span>' if r["status"] == "example" else ""
    more = f'<span class="badge">{len(r["versions"]) + 1} versions</span>' if r.get("versions") else ""
    if r["setup"].get("gnome"):
        more += f' <span class="badge">GNOME {esc(r["setup"]["gnome"])}{"+" if r["setup"].get("or_later") else ""}</span>'
    rated = (f'<span class="vote" title="Mentors that used it: it worked, it did not"><b class="yes">{thumb("up")} {r["up"]}</b>'
             f'<i></i><b class="no">{thumb("down")} {r["down"]}</b></span>'
             if (r.get("up") or r.get("down")) else '<span class="vote none">not rated yet</span>')
    text = esc((r["title"] + " " + r["summary"] + " " + cat["name"]).lower())
    link = f'{up}r/{r["id"]}/index.html'
    return (f'<article class="card" data-title="{esc(r["title"].lower())}" data-score="{r.get("up", 0) - r.get("down", 0)}" '
            f'data-time="{esc(r["submitted"])}" data-text="{text}">'
            f'<div class="top"><span class="chip">{esc(cat["name"])}</span>{rated}</div>'
            f'<a class="t" href="{link}">{esc(r["title"])}</a><p>{esc(r["summary"])}</p>'
            f'<div class="meta">{example} {more} {badge(r["counts"])}</div>'
            f'<div class="actions"><a class="btn ghost" href="{up}raw/{r["id"]}.md" download>Download .md</a>'
            f'<a class="btn" href="{link}">View</a></div></article>')


def stats(recipes):
    heads = [r for r in recipes if not r["head"]]
    liked = sum(1 for r in heads if r.get("up", 0) > r.get("down", 0))
    clean = sum(1 for r in heads if not r["counts"]["high"])
    voted = sum(r.get("up", 0) + r.get("down", 0) for r in heads)
    cells = (("Recipes", len(heads), "published"), ("Liked", liked, "more up than down"),
             ("Checked", clean, "nothing serious found"), ("Votes", voted, "from Mentor users"))
    return '<div class="stats">' + "".join(
        f'<div><span>{esc(k)}</span><b>{v}</b><i>{esc(sub)}</i></div>' for k, v, sub in cells) + "</div>"


TOOLBAR = ""  # the sort is in the bar at the top (SORT), on pages that list recipes
SORT = ('<label class="sort" id="toolbar" hidden>Sort <select id="sort" aria-label="Sort the recipes">'
        '<option value="score">Highest rated</option><option value="time">Newest</option>'
        '<option value="title">A to Z</option></select></label>')


def parent_link(cat, categories):
    parent = categories.get(cat.get("parent"))
    return f'<a href="../../c/{parent["id"]}/index.html">{esc(parent["name"])}</a> / ' if parent else ""


def versions_box(r, recipes):
    """Other versions that do nearly the same, and how each differs: what it adds, what it leaves out."""
    head = r if not r["head"] else next(x for x in recipes if x["id"] == r["head"])
    family = [head] + head["versions"]
    others = [x for x in family if x["id"] != r["id"]]
    if not others:
        return ""
    mine = features(r["body"])
    rows = ""
    for x in others:
        theirs = features(x["body"])
        added = sorted(f[2:] for f in theirs - mine if f.startswith("c:"))[:3]
        left = sorted(f[2:] for f in mine - theirs if f.startswith("c:"))[:3]
        diff = ""
        if added:
            diff += "<br>adds: " + ", ".join(f"<code>{esc(c)}</code>" for c in added)
        if left:
            diff += "<br>leaves out: " + ", ".join(f"<code>{esc(c)}</code>" for c in left)
        rows += (f'<li><a href="../{x["id"]}/index.html">{esc(x["title"])}</a>{" (the first)" if x["id"] == head["id"] else ""}'
                 f' {badge(x["counts"])}{diff}</li>')
    return f'<h2>Other versions of this</h2><ul class="versions">{rows}</ul>'


def build_pages(recipes, categories):
    used = {}
    for r in recipes:
        if not r["head"]:
            used.setdefault(r["category"], []).append(r)
    children = {}
    for c in categories.values():
        if c.get("parent") in categories and c.get("parent") != c["id"]:
            children.setdefault(c["parent"], []).append(c)

    def count(cid):
        return len(used.get(cid, []))
    mains = []
    for c in categories.values():
        if c.get("parent") in categories:
            continue
        subs = [(sc, count(sc["id"])) for sc in children.get(c["id"], []) if count(sc["id"])]
        total = count(c["id"]) + sum(k for _sc, k in subs)
        if total:
            mains.append((c, total, subs))
    SIDE["mains"], SIDE["children"] = mains, children

    # home: the recipes are the page; Mentor itself is one line and a button in the header
    chips = "".join(
        f'<a class="chip" href="c/{c["id"]}/index.html">{esc(c["name"])} <span>{len(used.get(c["id"], []))}</span></a>'
        for c in categories.values() if used.get(c["id"]))
    browse = ""
    for c, _total, subs in mains:
        if subs:
            browse += (f'<h2><a href="c/{c["id"]}/index.html">{esc(c["name"])}</a></h2><div class="subs">' +
                       "".join(f'<a class="sub" href="c/{sc["id"]}/index.html"><strong>{esc(sc["name"])}</strong>'
                               f'<span>{esc(sc["description"])}</span><em>{k} recipe(s)</em></a>' for sc, k in subs) + "</div>")
    heads = [r for r in recipes if not r["head"]]
    listing = "".join(recipe_card(r, categories, "") for r in heads)
    home = f"""
{stats(recipes)}
{TOOLBAR}
<div class="grid">{listing or '<p>No recipes yet.</p>'}</div>
<details class="safe"><summary>Is it safe to follow a recipe from a stranger?</summary>
<p>Not by default, and Mentor does not assume it is. Before anything is changed, Mentor checks the recipe with fixed rules
(a program run unseen, a change to the safety rules, private keys read, files sent away, hidden text, text aimed at the assistant),
gives you the whole report in plain words, and waits for your answer. The report on each recipe's page is the same one.
Recipes are published here automatically after that check and are not read by a person; one that a Mentor finds harmful is taken down.</p>
</details>"""
    write("index.html", page("Mentor recipes", home, 0))

    # one page per category: its own recipes, and the sub-categories' under it
    def cards(rs, up):
        return "".join(recipe_card(r, categories, up) for r in rs)

    for c in categories.values():
        own = used.get(c["id"], [])
        sections = ""
        for sc in children.get(c["id"], []):
            if used.get(sc["id"]):
                sections += (f'<h2><a href="../{sc["id"]}/index.html">{esc(sc["name"])}</a></h2>'
                             f'<p class="small">{esc(sc["description"])}</p><div class="grid">{cards(used[sc["id"]], "../../")}</div>')
        if not own and not sections:
            continue
        parent = categories.get(c.get("parent"))
        crumbs = ('<p class="crumbs"><a href="../../recipes/index.html">Recipes</a> / ' +
                  (f'<a href="../{parent["id"]}/index.html">{esc(parent["name"])}</a> / ' if parent else "") +
                  f'{esc(c["name"])}</p>')
        subcards = "".join(
            f'<a class="sub" href="../{sc["id"]}/index.html"><strong>{esc(sc["name"])}</strong><span>{esc(sc["description"])}</span>'
            f'<em>{len(used[sc["id"]])} recipe(s)</em></a>' for sc in children.get(c["id"], []) if used.get(sc["id"]))
        body = (f'{crumbs}<h1>{esc(c["name"])}</h1><p class="lead">{esc(c["description"])}</p>' +
                TOOLBAR + (f'<div class="subs">{subcards}</div>' if subcards else "") +
                (f'<h2>Recipes</h2><div class="grid">{cards(own, "../../")}</div>' if own else "") + sections)
        write(f"c/{c['id']}/index.html", page(f"{c['name']}: Mentor recipes", body, 2, current=c["id"]))
    everything = ""
    for c, _total, subs in mains:
        everything += f'<h2><a href="../c/{c["id"]}/index.html">{esc(c["name"])}</a></h2>'
        if used.get(c["id"]):
            everything += f'<div class="grid">{cards(used[c["id"]], "../")}</div>'
        for sc, _k in subs:
            everything += f'<h3><a href="../c/{sc["id"]}/index.html">{esc(sc["name"])}</a></h3><div class="grid">{cards(used[sc["id"]], "../")}</div>'
    write("recipes/index.html", page("All recipes: Mentor", f"<h1>All recipes</h1>{stats(recipes)}{TOOLBAR}{everything or '<p>No recipes yet.</p>'}", 1))

    # each recipe
    for r in recipes:
        cat = categories[r["category"]]
        notes = ""
        if r["status"] == "example":
            notes = '<p class="note">This is an example, written to show what a recipe looks like. It has not been tested on a real system.</p>'
        if r["setup"]:
            what = ", ".join(x for x in (
                f'GNOME {esc(r["setup"]["gnome"])}{" or later" if r["setup"].get("or_later") else ""}' if r["setup"].get("gnome") else "",
                f'kernel {esc(r["setup"]["kernel"])}' if r["setup"].get("kernel") else "") if x)
            notes += (f'<p class="note">Written for {what}. Your Mentor compares that with your computer and tells you if it is '
                      f'different; a recipe made for another setup may not work the same.</p>')
        else:
            notes += '<p class="note">This recipe does not say which GNOME and kernel it was written for.</p>'
        if r["model"]:
            notes += (f'<p class="note">Written by {esc(r["model"])}, the model Mentor ran on when it wrote this recipe down. '
                      f'Another model may follow it differently.</p>')
        if r["based_on"] and any(x["id"] == r["based_on"] for x in recipes):
            notes += (f'<p class="note">Made from <a href="../{r["based_on"]}/index.html">another recipe</a>, improved by '
                      f'someone who used it.</p>')
        elif r["head"]:
            notes += f'<p class="note">This is a version of <a href="../{r["head"]}/index.html">another recipe</a> that does nearly the same.</p>'
        serious = ""
        if r["counts"]["high"]:
            serious = '<p class="note bad">The automatic check found serious things in this recipe. Read the report before you do anything with it.</p>'
        body = f"""
<p class="crumbs"><a href="../../recipes/index.html">Recipes</a> / {parent_link(cat, categories)}<a href="../../c/{cat['id']}/index.html">{esc(cat['name'])}</a></p>
<h1>{esc(r['title'])}</h1>
<p class="lead">{esc(r['summary'])}</p>
{serious}
<div class="box">
<p><a class="button" href="../../raw/{r['id']}.md" download>Download the recipe</a></p>
<p class="small">Download it on your Mentor. It checks the recipe, tells you what it would do, and asks before it changes anything. {badge(r['counts'])}</p>
</div>
{versions_box(r, recipes)}
<details class="inside">
<summary>Show what is inside</summary>
{notes}
<h2>The automatic check</h2>
<p class="small">Made by fixed rules, not by a model. It is the same check Mentor does itself. It is not a promise that a recipe is safe.</p>
<pre class="report">{esc(r['report'])}</pre>
<h2>The recipe</h2>
<div class="recipe">{markdown(r['body'])}</div>
<p class="small">SHA-256: <code>{r['sha256']}</code> &middot; <a href="{HUB}/issues/new?title=Report+{esc(r['id'])}">Report a problem</a></p>
</details>"""
        write(f"r/{r['id']}/index.html", page(f"{r['title']}: Mentor recipe", body, 2, r["summary"] or "A Mentor recipe.", current=r["category"]))
        os.makedirs(os.path.join(DIST, "raw"), exist_ok=True)
        with open(os.path.join(DIST, "raw", r["id"] + ".md"), "wb") as f:
            f.write(r["raw"])

    write("404.html", page("Not found: Mentor", "<h1>Not found</h1><p><a href=\"/index.html\">Back to the start</a></p>", 0))


def write(rel, text):
    path = os.path.join(DIST, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def load_ratings():
    """{recipe id: (up, down)} from ratings.json (tools/vote.py)."""
    try:
        with open(os.path.join(ROOT, "ratings.json"), encoding="utf-8") as f:
            votes = json.load(f).get("votes", {})
    except (OSError, ValueError, AttributeError):
        return {}
    return {rid: (sum(1 for v in who.values() if v and v[0] == "up"), sum(1 for v in who.values() if v and v[0] == "down"))
            for rid, who in votes.items() if isinstance(who, dict)}


def main():
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)
    categories = load_categories()
    categories.setdefault("other", {"id": "other", "name": "Other", "description": "Recipes that fit no other category."})
    recipes = load_recipes(categories)
    ratings = load_ratings()
    for r in recipes:
        r["up"], r["down"] = ratings.get(r["id"], (0, 0))
    build_pages(recipes, categories)
    for asset in ("style.css", "mentor.png", "search.js"):
        shutil.copy(os.path.join(ROOT, "assets", asset), os.path.join(DIST, asset))
    index = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "categories": [{"id": c["id"], "parent": c.get("parent", ""), "name": c["name"], "description": c["description"]}
                       for c in categories.values()],
        "recipes": [{"id": r["id"], "title": r["title"], "summary": r["summary"], "category": r["category"],
                     "status": r["status"], "submitted": r["submitted"], "group": r["head"], "setup": r["setup"], "sha256": r["sha256"],
                     "findings": r["counts"], "up": r["up"], "down": r["down"], "author": r["author"], "updated": r["updated"], "model": r["model"], "based_on": r["based_on"], "file": f"raw/{r['id']}.md"} for r in recipes],
    }
    write("index.json", json.dumps(index, indent=1, ensure_ascii=False))
    print(f"built {len(recipes)} recipe(s) in {len(set(r['category'] for r in recipes))} categor(ies) -> dist/")


if __name__ == "__main__":
    main()
