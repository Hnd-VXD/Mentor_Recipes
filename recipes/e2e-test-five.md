---
category: panel
summary: A test of the intake, enable-hot-corners.
submitted: 2026-10-13
status: auto
source: e2eburst1
---
# E2E test five

> A test of the intake, enable-hot-corners.

| | |
|---|---|
| Needs | nothing |
| Touches | one setting of the desktop |
| Risk | low |

## What you get
A test.

## Steps
```
gsettings set org.gnome.desktop.interface enable-hot-corners true
```

## Check that it works
```
gsettings get org.gnome.desktop.interface enable-hot-corners
```

## Take it away again
```
gsettings set org.gnome.desktop.interface enable-hot-corners false
```
