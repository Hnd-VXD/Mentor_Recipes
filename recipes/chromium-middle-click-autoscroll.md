---
category: mouse
summary: Enables Windows-style middle-click autoscrolling in Chromium so holding or clicking the middle mouse button scrolls the page.
submitted: 2026-10-13
status: auto
source: 8e06c0160a2e1d6d
gnome: 51
kernel: 7.2
---
# Chromium Middle-Click Autoscroll

> Enables Windows-style middle-click autoscrolling in Chromium so holding or clicking the middle mouse button scrolls the page.

| | |
|---|---|
| Made on | Mentor, GNOME 51.0, kernel 7.2.9, 2026-10-13 |
| Needs | chromium |
| Touches | ~/.config/chromium-flags.conf (no restart or logout needed) |
| Risk | low (adds a user-level browser flag; no system files or root permissions touched) |

## What you get
Clicking or holding the middle mouse button on any scrollable page in Chromium displays the autoscroll anchor (compass circle icon), allowing smooth scrolling by moving the mouse up or down, exactly like Chrome on Windows.

## Before you start
Verify that Chromium is installed:
`which chromium` → `/usr/bin/chromium`

Tell the user: "I will configure Chromium to enable Windows-style middle-click autoscroll navigation."

## Steps
1. Append the middle-click autoscroll flag to the user's Chromium flags configuration file.
Write `~/.config/chromium-flags.conf`:
```
--enable-blink-features=MiddleClickAutoscroll
```
If the file already exists, append `--enable-blink-features=MiddleClickAutoscroll` on its own line.

## Check that it works
1. Verify that the Chromium launcher recognizes the flag:
Run `chromium --help` and verify that the output under "Currently detected flags:" includes:
```
--enable-blink-features=MiddleClickAutoscroll
```
2. Open Chromium and visit any long webpage. Click or hold the middle mouse button on empty space on the page; the directional scroll anchor should appear, and moving the mouse should scroll the page.

## Take it away again
Remove `--enable-blink-features=MiddleClickAutoscroll` from `~/.config/chromium-flags.conf`. If that was the only flag in the file, delete `~/.config/chromium-flags.conf`.

## Notes for the agent
On Arch Linux and Mentor, `/usr/bin/chromium` automatically reads custom flags from `~/.config/chromium-flags.conf` on startup. If applying this on another distribution that does not read flags files, add the flag `--enable-blink-features=MiddleClickAutoscroll` to the browser's desktop launcher `Exec=` line instead.
