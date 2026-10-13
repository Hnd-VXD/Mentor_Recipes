---
category: panel
summary: A test of the intake, clock-show-date.
submitted: 2026-10-13
status: auto
source: e2eburst0
---
# E2E test one

> A test of the intake, clock-show-date.

| | |
|---|---|
| Needs | nothing |
| Touches | one setting of the desktop |
| Risk | low |

## What you get
A test.

## Steps
```
gsettings set org.gnome.desktop.interface clock-show-date true
```

## Check that it works
```
gsettings get org.gnome.desktop.interface clock-show-date
```

## Take it away again
```
gsettings set org.gnome.desktop.interface clock-show-date false
```
