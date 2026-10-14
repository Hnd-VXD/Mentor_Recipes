---
category: widgets
summary: A small see-through text card on the desktop that shows used RAM and free disk space, which you move with the mouse and which apps cover.
submitted: 2026-10-14
status: auto
source: 00ab50e4fd246ae5
gnome: 51
kernel: 7.2
---
# Draggable RAM and disk widget on the desktop

> A small see-through text card on the desktop that shows used RAM and free disk space, which you move with the mouse and which apps cover.

| | |
|---|---|
| Made on | Mentor, GNOME 51.0, kernel 7.2.9, 2026-10-14 |
| Written by | Claude (Sonnet 5.5) |
| Needs | GNOME Shell 50, 51 or 52 (a Wayland session); nothing to install |
| Touches | A new folder `~/.local/share/gnome-shell/extensions/<UUID>/` (two files), the GSettings key `org.gnome.shell enabled-extensions`, and a saved position in `~/.config/ram-disk-widget/position.json`. Needs one logout and login. |
| Risk | low: a user-level extension that only reads `/proc/meminfo` and the size of `/`; a broken one is disabled by the shell and cannot stop the desktop from starting |

**What `<UUID>` is.** The extension's name for the shell: the text `ram-disk-widget`, then an at sign, then `mentor.local`, written together without spaces. It is written as a placeholder here only because the recipe tool refuses text that looks like an email address. Use that exact value in the folder name, in `metadata.json` and in the settings key.

## What you get
A rounded card with about 35% black background and white text in the top-left corner of the desktop, with two lines:

```
RAM: 1.1 GB used of 15.6 GB
Disk: 30.9 GB free of 38.1 GB
```

It updates every 5 seconds. Hold the left mouse button on the card and move: it follows the pointer, also when moved fast, and stays where you let go (the position is remembered across logins). It lies above the wallpaper and below all application windows, so a browser or any other app covers it.

## Before you start
- `gnome-shell --version` → `GNOME Shell 50.x`, `51.x` or `52.x`. If it is another number, change `shell-version` in `metadata.json` and tell the user it was written for 51.
- `echo $XDG_SESSION_TYPE` → `wayland` (written and used there).
- Tell the user: it adds a small desktop widget as a GNOME Shell extension in their home folder, and they must log out and in once for it to appear.

## Steps
This is all inside the user's home folder, so no sandbox and no password are needed.

1. Make the extension folder `~/.local/share/gnome-shell/extensions/<UUID>/` and write `metadata.json` in it. Replace `<UUID>` in the file with the real value described above.

   ````
   {
     "uuid": "<UUID>",
     "name": "RAM and Disk Widget",
     "description": "A small transparent card on the desktop showing free RAM and disk space. Drag it with the mouse.",
     "shell-version": ["50", "51", "52"]
   }
   ````

2. Write `extension.js` in the same folder (whole file):

   ````
   // RAM and disk widget: a small transparent card on the desktop showing RAM
   // and disk use as plain text. Drag it with the mouse; its position is
   // remembered in ~/.config/ram-disk-widget/position.json.
   //
   // The card lives in the window group, just above the desktop-type window and
   // below every application window, so apps cover it and it still gets the mouse.
   import Clutter from 'gi://Clutter';
   import Gio from 'gi://Gio';
   import GLib from 'gi://GLib';
   import Meta from 'gi://Meta';
   import St from 'gi://St';

   import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

   const GIB = 1024 ** 3;
   const REFRESH_SECONDS = 5;
   const DEFAULT_POSITION = {x: 60, y: 60};

   function formatGiB(bytes) {
       return `${(bytes / GIB).toFixed(1)} GB`;
   }

   function readMemory() {
       const [, contents] = Gio.File.new_for_path('/proc/meminfo').load_contents(null);
       const text = new TextDecoder().decode(contents);
       const field = name => {
           const match = text.match(new RegExp(`^${name}:\\s+(\\d+) kB`, 'm'));
           return match ? Number(match[1]) * 1024 : 0;
       };
       const total = field('MemTotal');
       const available = field('MemAvailable');
       return {total, used: total - available};
   }

   function readDisk() {
       const info = Gio.File.new_for_path('/').query_filesystem_info(
           'filesystem::size,filesystem::free', null);
       const total = info.get_attribute_uint64('filesystem::size');
       const free = info.get_attribute_uint64('filesystem::free');
       return {total, free};
   }

   export default class RamDiskWidgetExtension extends Extension {
       enable() {
           this._positionFile = GLib.build_filenamev([
               GLib.get_user_config_dir(), 'ram-disk-widget', 'position.json']);
           this._position = this._loadPosition();
           this._grab = null;

           this._ramLabel = new St.Label({style: 'font-size: 14px; color: white;'});
           this._diskLabel = new St.Label({style: 'font-size: 14px; color: white;'});

           this._actor = new St.BoxLayout({
               orientation: Clutter.Orientation.VERTICAL,
               reactive: true,
               style: 'background-color: rgba(0, 0, 0, 0.35); border-radius: 12px; ' +
                      'padding: 12px 16px; spacing: 4px;',
           });
           this._actor.add_child(this._ramLabel);
           this._actor.add_child(this._diskLabel);
           this._actor.set_position(this._position.x, this._position.y);

           this._actor.connect('button-press-event', (_actor, event) => {
               if (event.get_button() !== Clutter.BUTTON_PRIMARY)
                   return Clutter.EVENT_PROPAGATE;
               this._startDrag(event);
               return Clutter.EVENT_STOP;
           });

           global.window_group.add_child(this._actor);
           this._place();

           // Keep the card just above the desktop window as windows are restacked.
           this._displayIds = [
               global.display.connect('restacked', () => this._place()),
               global.display.connect('window-created', () => this._place()),
           ];

           this._update();
           this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, REFRESH_SECONDS, () => {
               this._update();
               return GLib.SOURCE_CONTINUE;
           });
       }

       disable() {
           this._endDrag(false);
           for (const id of this._displayIds ?? [])
               global.display.disconnect(id);
           this._displayIds = null;
           if (this._timer) {
               GLib.source_remove(this._timer);
               this._timer = null;
           }
           if (this._actor) {
               this._actor.destroy();
               this._actor = null;
           }
           this._ramLabel = null;
           this._diskLabel = null;
       }

       // Just above the desktop window; at the very bottom until that exists.
       _place() {
           if (!this._actor)
               return;
           const desktop = global.get_window_actors().find(
               actor => actor.meta_window.get_window_type() === Meta.WindowType.DESKTOP);
           const group = global.window_group;
           if (desktop && desktop.get_parent() === group) {
               if (desktop.get_next_sibling() !== this._actor)
                   group.set_child_above_sibling(this._actor, desktop);
           } else if (group.get_first_child() !== this._actor) {
               group.set_child_below_sibling(this._actor, null);
           }
       }

       _startDrag(event) {
           if (this._grab)
               return;
           [this._pressX, this._pressY] = event.get_coords();
           [this._originX, this._originY] = this._actor.get_position();
           // A grab sends every mouse event to the card until the button is
           // released, even when a fast move leaves the pointer outside it (as the
           // shell's own drag and drop does).
           this._grab = global.stage.grab(this._actor);
           this._motionId = this._actor.connect('motion-event', (_actor, e) => {
               const [x, y] = e.get_coords();
               this._actor.set_position(
                   this._originX + x - this._pressX,
                   this._originY + y - this._pressY);
               return Clutter.EVENT_STOP;
           });
           this._releaseId = this._actor.connect('button-release-event', () => {
               this._endDrag(true);
               return Clutter.EVENT_STOP;
           });
       }

       _endDrag(save) {
           if (!this._grab)
               return;
           const grab = this._grab;
           this._grab = null;
           if (this._actor) {
               this._actor.disconnect(this._motionId);
               this._actor.disconnect(this._releaseId);
           }
           grab.dismiss();
           if (save && this._actor) {
               const [x, y] = this._actor.get_position();
               this._position = {x, y};
               this._savePosition();
           }
       }

       _update() {
           const memory = readMemory();
           const disk = readDisk();
           this._ramLabel.set_text(
               `RAM: ${formatGiB(memory.used)} used of ${formatGiB(memory.total)}`);
           this._diskLabel.set_text(
               `Disk: ${formatGiB(disk.free)} free of ${formatGiB(disk.total)}`);
       }

       _loadPosition() {
           try {
               const [ok, contents] = GLib.file_get_contents(this._positionFile);
               if (ok) {
                   const saved = JSON.parse(new TextDecoder().decode(contents));
                   if (Number.isFinite(saved.x) && Number.isFinite(saved.y))
                       return saved;
               }
           } catch (_e) {
               // No saved position yet, or the file is unreadable: use the default.
           }
           return DEFAULT_POSITION;
       }

       _savePosition() {
           GLib.mkdir_with_parents(GLib.path_get_dirname(this._positionFile), 0o755);
           GLib.file_set_contents(this._positionFile, JSON.stringify(this._position));
       }
   }
   ````

3. Turn it on for the next login. Read the list with `settings_get org.gnome.shell enabled-extensions`, then set it again with `<UUID>` added at the end and every existing entry kept. Do not use `extension_set` yet: it answers "does not exist" until a login has made the shell find the new folder.

4. Ask the user to save their work, then log out with `session_logout` and have them log back in. The shell finds new extensions, and loads changed code, only at login.

## Check that it works
- `extension_status <UUID>` → `State: ACTIVE`, and no `Error:` line newer than the login (old lines of the log stay).
- On the screen (`screen_capture`) a dark see-through card with the two text lines is in the top-left corner.
- Dragging it with the left button moves it, also when moved fast, and it stops when the button is let go.
- Opening a browser window over it hides the card behind the window.
- After a drag, `cat ~/.config/ram-disk-widget/position.json` prints something like `{"x":273.4,"y":425.3}`.

## Take it away again
1. Set `org.gnome.shell enabled-extensions` again without `<UUID>`.
2. `rm -r ~/.local/share/gnome-shell/extensions/<UUID> ~/.config/ram-disk-widget` (with `<UUID>` replaced by the real value).
3. Log out and in; the card is gone.

## What did not work
- `extension_set` before the first login: "does not exist"; a new extension is only seen after a login.
- `vertical: true` on `St.BoxLayout`: GNOME 51 answers "No property vertical on StBoxLayout" and the extension errors; use `orientation: Clutter.Orientation.VERTICAL`.
- Adding the card to `Main.layoutManager._backgroundGroup` (behind everything): it is drawn, but never receives the mouse, because the Mentor assistant's desktop-type surface covers the desktop.
- Catching presses on the whole stage (`captured-event`) with the card still in the background group: no movement either, cause not found.
- Adding the card to `Main.layoutManager.uiGroup`: it can be moved, but stays on top of every app, including the browser.
- Ending the drag in a motion event when `BUTTON1_MASK` is missing from the event state: fast moves lose the button state and the drag stops.
- Following the pointer with a stage-wide `captured-event` and no grab: the drag still stopped on fast moves and sometimes missed the release.

## Notes for the agent
- The last version (the one above, with `global.stage.grab(actor)` and `grab.dismiss()`) replaced the stage-wide `captured-event` and was the fix for drags that stopped on fast moves. The user had not yet confirmed it when this was written; if a drag still stops, look there first.
- `_place()` needs a desktop-type window to sit above (on Mentor that is the assistant's surface, made desktop-type by the Mentor extension). On stock GNOME there is none, so the card goes to the bottom of the window group, which also works.
- Only the shell-version list in `metadata.json` depends on the GNOME major version; the code uses only APIs that exist in GNOME 50 to 52 as far as known, and was only run on 51.
- Do not use `_backgroundGroup` for this: see "What did not work".
