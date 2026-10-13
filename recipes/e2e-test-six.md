---
category: panel
summary: A test of the intake, toolkit-accessibility.
submitted: 2026-10-13
status: auto
source: e2eburst2
---
# E2E test six

> A test of the intake, toolkit-accessibility.

| | |
|---|---|
| Needs | nothing |
| Touches | one setting of the desktop |
| Risk | low |

## What you get
A test.

## Steps
```
gsettings set org.gnome.desktop.interface toolkit-accessibility true
```

## Check that it works
```
gsettings get org.gnome.desktop.interface toolkit-accessibility
```

## Take it away again
```
gsettings set org.gnome.desktop.interface toolkit-accessibility false
```
