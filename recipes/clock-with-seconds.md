---
category: panel
status: example
submitted: 2026-10-13
summary: Show the seconds in the clock at the top of the screen.
---
# Clock with seconds

> The clock in the panel shows the seconds, so it reads 14:02:11 instead of 14:02.

| | |
|---|---|
| Made on | Mentor, GNOME 50 or later |
| Needs | nothing |
| Touches | one setting of the desktop, for the current user only |
| Risk | low: nothing is installed and no file is changed |

## What you get
The clock shows hours, minutes and seconds.

## Before you start
Run `gsettings get org.gnome.desktop.interface clock-show-seconds`. It should answer `false`. If it answers `true` there is nothing to do.

## Steps
1. Switch the setting on. This changes the desktop for you only.

```
gsettings set org.gnome.desktop.interface clock-show-seconds true
```

## Check that it works
Run `gsettings get org.gnome.desktop.interface clock-show-seconds`: it must print `true`. Look at the clock: the seconds are moving.

## Take it away again
```
gsettings set org.gnome.desktop.interface clock-show-seconds false
```

## What did not work
Nothing to report.

## Notes for the agent
This is a user setting; no root, no sandbox needed. Say to the user what the clock will look like before you change it.
