---
category: appearance
status: example
submitted: 2026-10-13
summary: Switch the whole desktop to the dark style, and back.
---
# Dark style for the desktop

> Windows, menus and the programs that follow the system's choice turn dark.

| | |
|---|---|
| Made on | Mentor, GNOME 50 or later |
| Needs | nothing |
| Touches | one setting of the desktop, for the current user only |
| Risk | low: nothing is installed and no file is changed |

## What you get
A dark look for the desktop and for programs that follow it. Some programs keep their own look.

## Before you start
Run `gsettings get org.gnome.desktop.interface color-scheme`. Note what it says: it is what you go back to.

## Steps
1. Choose the dark style.

```
gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'
```

## Check that it works
Run `gsettings get org.gnome.desktop.interface color-scheme`: it must print `'prefer-dark'`. Open Files or Settings: they are dark.

## Take it away again
```
gsettings set org.gnome.desktop.interface color-scheme 'default'
```

## What did not work
Nothing to report.

## Notes for the agent
This is a user setting; no root, no sandbox needed. If the first answer was `'prefer-light'`, go back to that.
