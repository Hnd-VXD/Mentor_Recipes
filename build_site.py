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

from inspector import inspect

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
            "status": meta.get("status", ""), "submitted": meta.get("submitted", ""),
            "sha256": hashlib.sha256(raw).hexdigest(), "body": body, "raw": raw,
            "report": report, "counts": counts,
        })
    found.sort(key=lambda r: (r["submitted"], r["title"]), reverse=True)
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

def page(title, body, depth=0, description="Recipes for Mentor, an Arch Linux that you talk to."):
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
<a class="brand" href="{up}index.html"><img src="{up}mentor.png" alt="" width="36" height="36"><span>Mentor</span></a>
<nav><a href="{up}recipes/index.html">Recipes</a><a href="{SOURCE}">Source</a><a class="cta" href="{DOWNLOAD}">Download</a></nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer><div class="wrap">Mentor is an experiment, written with the help of AI and not audited by anyone independent.
Recipes are instructions from other people: Mentor reads each one with you first and tells you everything it would do.
<a href="{HUB}">The recipes repository</a> · <a href="{SOURCE}">Mentor on GitHub</a></div></footer>
</body></html>
"""


def badge(counts):
    if counts["high"]:
        return f'<span class="badge bad">{counts["high"]} serious</span>'
    if counts["medium"]:
        return f'<span class="badge care">{counts["medium"]} to look at</span>'
    return '<span class="badge ok">nothing found</span>'


def recipe_card(r, categories, up):
    cat = categories[r["category"]]
    example = '<span class="badge example">example</span>' if r["status"] == "example" else ""
    return (f'<a class="card" href="{up}r/{r["id"]}/index.html"><strong>{esc(r["title"])}</strong>'
            f'<span>{esc(r["summary"])}</span><span class="meta">{esc(cat["name"])} {example} {badge(r["counts"])}</span></a>')


def build_pages(recipes, categories):
    used = {}
    for r in recipes:
        used.setdefault(r["category"], []).append(r)

    # home
    cats = "".join(
        f'<a class="card" href="c/{c["id"]}/index.html"><strong>{esc(c["name"])}</strong><span>{esc(c["description"])}</span>'
        f'<span class="meta">{len(used.get(c["id"], []))} recipe(s)</span></a>'
        for c in categories.values() if used.get(c["id"]))
    latest = "".join(recipe_card(r, categories, "") for r in recipes[:6])
    home = f"""
<section class="hero">
<h1>Talk to your computer. It builds what you ask for.</h1>
<p>Mentor is Arch Linux with an assistant on the desktop that changes the system when you ask it to, in a window on Windows 11.
Nothing to learn first: you say what you want.</p>
<p><a class="button" href="{DOWNLOAD}">Download Mentor for Windows</a> <a class="button ghost" href="{RELEASES}">All downloads</a></p>
<p class="small">Run <code>MentorSetup.exe</code>; it does the rest. Windows 11, 8 GB of memory or more. Windows may warn about an unsigned program the first time:
<a href="{SOURCE}#install">the README explains how to check it</a>.</p>
</section>
<section>
<h2>Recipes</h2>
<p>When someone builds something with Mentor that works, their assistant writes down how, in enough detail that another Mentor can
build the same thing. Those files are here. Download one, give it to your Mentor, and it does the rest: after it has read it with you
and told you everything it would do.</p>
<div class="grid">{cats or '<p>No recipes yet.</p>'}</div>
<h3>Latest</h3>
<div class="grid">{latest}</div>
</section>
<section>
<h2>Is it safe to follow a recipe from a stranger?</h2>
<p>Not by default, and Mentor does not assume it is. Before anything is changed, Mentor checks the recipe with fixed rules
(a program run unseen, a change to the safety rules, private keys read, files sent away, hidden text, text aimed at the assistant),
gives you the whole report in plain words, and waits for your answer. The report on each recipe's page is the same one.</p>
</section>"""
    write("index.html", page("Mentor: talk to your computer", home, 0))

    # one page per category, and the list of all
    for c in categories.values():
        mine = used.get(c["id"], [])
        if not mine:
            continue
        body = f'<h1>{esc(c["name"])}</h1><p>{esc(c["description"])}</p><div class="grid">' + \
               "".join(recipe_card(r, categories, "../../") for r in mine) + "</div>"
        write(f"c/{c['id']}/index.html", page(f"{c['name']}: Mentor recipes", body, 2))
    sections = "".join(
        f'<h2><a href="../c/{c["id"]}/index.html">{esc(c["name"])}</a></h2><div class="grid">' +
        "".join(recipe_card(r, categories, "../") for r in used[c["id"]]) + "</div>"
        for c in categories.values() if used.get(c["id"]))
    write("recipes/index.html", page("All recipes: Mentor", f"<h1>All recipes</h1>{sections or '<p>No recipes yet.</p>'}", 1))

    # each recipe
    for r in recipes:
        cat = categories[r["category"]]
        notes = ""
        if r["status"] == "example":
            notes = '<p class="note">This is an example, written to show what a recipe looks like. It has not been tested on a real system.</p>'
        serious = ""
        if r["counts"]["high"]:
            serious = '<p class="note bad">The automatic check found serious things in this recipe. Read the report before you do anything with it.</p>'
        body = f"""
<p class="crumbs"><a href="../../recipes/index.html">Recipes</a> / <a href="../../c/{cat['id']}/index.html">{esc(cat['name'])}</a></p>
<h1>{esc(r['title'])}</h1>
<p class="lead">{esc(r['summary'])}</p>
{notes}{serious}
<div class="box">
<p><strong>Use it:</strong> download the file, put it in <code>Documents/Mentor recipes</code> on your Mentor, and tell the assistant
&ldquo;follow this recipe&rdquo;. It checks it, tells you everything it would do, and waits for your yes.</p>
<p><a class="button" href="../../raw/{r['id']}.md" download>Download the recipe (.md)</a></p>
<p class="small">SHA-256: <code>{r['sha256']}</code> {badge(r['counts'])}</p>
</div>
<h2>The automatic check</h2>
<p class="small">Made by fixed rules, not by a model. It is the same check Mentor does itself. It is not a promise that a recipe is safe.</p>
<pre class="report">{esc(r['report'])}</pre>
<h2>The recipe</h2>
<div class="recipe">{markdown(r['body'])}</div>"""
        write(f"r/{r['id']}/index.html", page(f"{r['title']}: Mentor recipe", body, 2, r["summary"] or "A Mentor recipe."))
        os.makedirs(os.path.join(DIST, "raw"), exist_ok=True)
        with open(os.path.join(DIST, "raw", r["id"] + ".md"), "wb") as f:
            f.write(r["raw"])

    write("404.html", page("Not found: Mentor", "<h1>Not found</h1><p><a href=\"/index.html\">Back to the start</a></p>", 0))


def write(rel, text):
    path = os.path.join(DIST, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)
    categories = load_categories()
    categories.setdefault("other", {"id": "other", "name": "Other", "description": "Recipes that fit no other category."})
    recipes = load_recipes(categories)
    build_pages(recipes, categories)
    for asset in ("style.css", "mentor.png"):
        shutil.copy(os.path.join(ROOT, "assets", asset), os.path.join(DIST, asset))
    index = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "categories": [{"id": c["id"], "name": c["name"], "description": c["description"]} for c in categories.values()],
        "recipes": [{"id": r["id"], "title": r["title"], "summary": r["summary"], "category": r["category"],
                     "status": r["status"], "submitted": r["submitted"], "sha256": r["sha256"],
                     "findings": r["counts"], "file": f"raw/{r['id']}.md"} for r in recipes],
    }
    write("index.json", json.dumps(index, indent=1, ensure_ascii=False))
    print(f"built {len(recipes)} recipe(s) in {len(set(r['category'] for r in recipes))} categor(ies) -> dist/")


if __name__ == "__main__":
    main()
