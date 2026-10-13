---
category: panel
summary: A test of the intake, enable-animations.
submitted: 2026-10-13
status: auto
source: e2eburst2
---
# E2E test three

> A test of the intake, enable-animations.

| | |
|---|---|
| Needs | nothing |
| Touches | one setting of the desktop |
| Risk | low |

## What you get
A test.

## Steps
```
gsettings set org.gnome.desktop.interface enable-animations true
```

## Check that it works
```
gsettings get org.gnome.desktop.interface enable-animations
```

## Take it away again
```
gsettings set org.gnome.desktop.interface enable-animations false
```
