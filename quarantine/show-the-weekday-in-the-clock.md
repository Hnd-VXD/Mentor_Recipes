---
category: panel
summary: The clock in the panel shows the day of the week.
submitted: 2026-10-13
status: auto
source: e2etest1
---
# Show the weekday in the clock

> The clock in the panel shows the day of the week.

| | |
|---|---|
| Needs | nothing |
| Touches | one setting of the desktop |
| Risk | low |

## What you get
The clock reads "Tue 14:02".

## Steps
```
gsettings set org.gnome.desktop.interface clock-show-weekday true
```

## Check that it works
```
gsettings get org.gnome.desktop.interface clock-show-weekday
```

## Take it away again
```
gsettings set org.gnome.desktop.interface clock-show-weekday false
```
