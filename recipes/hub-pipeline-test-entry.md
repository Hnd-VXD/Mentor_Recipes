---
category: panel
summary: A harmless test of the recipes site, safe to ignore.
submitted: 2026-10-13
status: auto
source: e89de8a2cc41bbd5
gnome: 51
kernel: 6.12
---
# Hub pipeline test entry

> A harmless test of the recipes site, safe to ignore.

| | |
|---|---|
| Made on | Mentor, GNOME 51.0, kernel 6.12.5, 2026-10-13 |
| Needs | nothing |
| Risk | low |

## What you get
Nothing changes. This only tests that the site accepts a post.

## Steps
```
gsettings set org.gnome.desktop.interface show-battery-percentage true
```

## Check that it works
Look at the battery icon.
