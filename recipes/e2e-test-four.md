---
category: panel
summary: A test of the intake, locate-pointer.
submitted: 2026-10-13
status: auto
source: e2eburst0
---
# E2E test four

> A test of the intake, locate-pointer.

| | |
|---|---|
| Needs | nothing |
| Touches | one setting of the desktop |
| Risk | low |

## What you get
A test.

## Steps
```
gsettings set org.gnome.desktop.interface locate-pointer true
```

## Check that it works
```
gsettings get org.gnome.desktop.interface locate-pointer
```

## Take it away again
```
gsettings set org.gnome.desktop.interface locate-pointer false
```
