#!/usr/bin/env python3
"""The check a submission has to pass: run by GitHub on every pull request.

Looks at every recipe in recipes/ with the rules in inspector.py. A recipe with a serious
finding fails; one with things to look at passes and is listed, for the person who reads it.
Also checks the header: a summary, and a category that exists.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from inspector import inspect  # noqa: E402

categories = {c["id"] for c in json.load(open(os.path.join(ROOT, "categories.json"), encoding="utf-8"))["categories"]}
failed, lines = 0, ["# Recipe check", ""]
for name in sorted(os.listdir(os.path.join(ROOT, "recipes"))):
    if not name.endswith(".md"):
        continue
    path = os.path.join(ROOT, "recipes", name)
    text = open(path, encoding="utf-8", errors="replace").read()
    problems = []
    head = re.match(r"^---\n(.*?)\n---", text, re.S)
    meta = dict(re.findall(r"^([A-Za-z_]+)\s*:\s*(.+)$", head.group(1), re.M)) if head else {}
    if not meta.get("summary"):
        problems.append("the header has no `summary`")
    if meta.get("category") not in categories:
        problems.append(f"`category` is not one of: {', '.join(sorted(categories))}")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*\.md", name):
        problems.append("the file name is not lower case words with dashes")
    report, counts, _sha = inspect(path)
    report = report.replace(path, "recipes/" + name)
    lines.append(f"## {name}: {counts['high']} serious, {counts['medium']} to look at")
    for p in problems:
        lines.append(f"- header: {p}")
    if counts["high"] or problems:
        failed += 1
        lines += ["", "```", report, "```"]
    elif counts["medium"]:
        lines += ["", "```", report, "```"]
    lines.append("")
out = "\n".join(lines)
print(out)
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    open(summary, "a", encoding="utf-8").write(out + "\n")
sys.exit(1 if failed else 0)
