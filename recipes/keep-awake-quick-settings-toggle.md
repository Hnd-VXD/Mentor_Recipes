---
category: panel
summary: A switch in the Quick Settings menu to keep the computer awake and prevent automatic sleep or screen dimming.
submitted: 2026-10-14
status: auto
source: 00ab50e4fd246ae5
gnome: 51
kernel: 7.2
---
# Keep Awake Quick Settings toggle

> A switch in the Quick Settings menu to keep the computer awake and prevent automatic sleep or screen dimming.

| | |
|---|---|
| Made on | Mentor, GNOME 51.0, kernel 7.2.9, 2026-10-14 |
| Written by | Gemini |
| Needs | gnome-shell |
| Touches | ~/.local/share/gnome-shell/extensions/keep-awake@example.com/, org.gnome.shell enabled-extensions, needs a logout |
| Risk | low, runs as a user extension and uses standard session sleep inhibition |

## What you get
A new "Keep Awake" switch in the Quick Settings menu (system menu). When switched on, it prevents the system from going to sleep or dimming/turning off the display, and displays a coffee cup icon in the top panel/status bar. When turned off, normal power saving and sleep behavior resume.

## Before you start
Check that GNOME Shell is running version 50, 51, or 52:
`gnome-shell --version` -> GNOME Shell 50, 51, or 52.

Tell the user that this adds a Keep Awake switch to Quick Settings, which will require logging out and back in once to take effect.

## Steps
1. Create the extension directory and icons directory:
```bash
mkdir -p ~/.local/share/gnome-shell/extensions/keep-awake@example.com/icons
```

2. Write the extension metadata file `~/.local/share/gnome-shell/extensions/keep-awake@example.com/metadata.json`:
```json
{
  "uuid": "keep-awake@example.com",
  "name": "Keep Awake",
  "description": "Keep the computer awake and prevent automatic sleep or screen turning off.",
  "shell-version": ["50", "51", "52"]
}
```

3. Extract or write the coffee cup symbolic icon `~/.local/share/gnome-shell/extensions/keep-awake@example.com/icons/keep-awake-symbolic.svg`.

4. Write the extension code `~/.local/share/gnome-shell/extensions/keep-awake@example.com/extension.js`:
```javascript
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {QuickToggle, SystemIndicator} from 'resource:///org/gnome/shell/ui/quickSettings.js';

// Flags for org.gnome.SessionManager.Inhibit:
// 4 = Inhibit suspend / sleep
// 8 = Inhibit idle / screen blanking
const GSM_INHIBIT_SUSPEND = 4;
const GSM_INHIBIT_IDLE = 8;
const GSM_INHIBIT_FLAGS = GSM_INHIBIT_SUSPEND | GSM_INHIBIT_IDLE;

const KeepAwakeToggle = GObject.registerClass(
class KeepAwakeToggle extends QuickToggle {
    constructor(icon) {
        super({
            title: 'Keep Awake',
            gicon: icon,
            toggleMode: true,
        });

        this._cookie = null;

        this.connect('notify::checked', () => {
            if (this.checked) {
                this._inhibit();
            } else {
                this._uninhibit();
            }
        });
    }

    _inhibit() {
        if (this._cookie !== null)
            return;

        Gio.DBus.session.call(
            'org.gnome.SessionManager',
            '/org/gnome/SessionManager',
            'org.gnome.SessionManager',
            'Inhibit',
            new GLib.Variant('(susu)', ['keep-awake', 0, 'Keep Awake is active', GSM_INHIBIT_FLAGS]),
            null,
            Gio.DBusCallFlags.NONE,
            -1,
            null,
            (conn, res) => {
                try {
                    const ret = conn.call_finish(res);
                    const [cookie] = ret.deep_unpack();
                    this._cookie = cookie;
                    if (!this.checked)
                        this._uninhibit();
                } catch (e) {
                    console.error(`keep-awake: failed to inhibit sleep: ${e.message}`);
                    this.checked = false;
                }
            }
        );
    }

    _uninhibit() {
        if (this._cookie === null)
            return;

        const cookie = this._cookie;
        this._cookie = null;

        Gio.DBus.session.call(
            'org.gnome.SessionManager',
            '/org/gnome/SessionManager',
            'org.gnome.SessionManager',
            'Uninhibit',
            new GLib.Variant('(u)', [cookie]),
            null,
            Gio.DBusCallFlags.NONE,
            -1,
            null,
            (conn, res) => {
                try {
                    conn.call_finish(res);
                } catch (e) {
                    console.error(`keep-awake: failed to uninhibit sleep: ${e.message}`);
                }
            }
        );
    }

    destroy() {
        this._uninhibit();
        super.destroy();
    }
});

const KeepAwakeIndicator = GObject.registerClass(
class KeepAwakeIndicator extends SystemIndicator {
    constructor(icon) {
        super();
        this._indicator = this._addIndicator();
        this._indicator.gicon = icon;

        this._toggle = new KeepAwakeToggle(icon);
        this._toggle.bind_property(
            'checked',
            this._indicator,
            'visible',
            GObject.BindingFlags.SYNC_CREATE
        );

        this.quickSettingsItems.push(this._toggle);
    }

    destroy() {
        this.quickSettingsItems.forEach(item => item.destroy());
        super.destroy();
    }
});

export default class KeepAwakeExtension extends Extension {
    enable() {
        const iconPath = `${this.path}/icons/keep-awake-symbolic.svg`;
        const icon = Gio.icon_new_for_string(iconPath);

        this._indicator = new KeepAwakeIndicator(icon);
        Main.panel.statusArea.quickSettings.addExternalIndicator(this._indicator);
    }

    disable() {
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }
}
```

5. Add `keep-awake@example.com` to GNOME Shell enabled extensions in GSettings:
```bash
gsettings set org.gnome.shell enabled-extensions "$(gsettings get org.gnome.shell enabled-extensions | sed "s/]$/, 'keep-awake@example.com']/")"
```

6. Ask the user to log out and back in so GNOME Shell discovers and loads the new extension.

## Check that it works
1. Verify the extension is active:
```bash
gnome-extensions show keep-awake@example.com
```
Expect: `State: ACTIVE`.

2. Open the Quick Settings menu. Verify the "Keep Awake" toggle appears.
3. Click "Keep Awake" to turn it on:
- The toggle button turns active (blue).
- A coffee cup icon appears in the system status panel.
- Run `gnome-session-inhibit --list` to verify:
```bash
gnome-session-inhibit --list
```
Expect: `keep-awake: Keep Awake is active (suspend, idle)`.
4. Click "Keep Awake" again to turn it off:
- The toggle turns off.
- The coffee cup icon disappears from the status panel.
- Run `gnome-session-inhibit --list` to verify no inhibitors remain.

## Take it away again
1. Remove `keep-awake@example.com` from enabled extensions:
```bash
gsettings set org.gnome.shell enabled-extensions "$(gsettings get org.gnome.shell enabled-extensions | sed "s/, 'keep-awake@example.com'//")"
```
2. Delete the extension folder:
```bash
rm -rf ~/.local/share/gnome-shell/extensions/keep-awake@example.com
```
3. Log out and back in to remove it from the running session.

## What did not work
- `extension_set` fails to enable an extension immediately before logging out because GNOME Shell only scans for new extension directories on startup/login. The extension must be added to `org.gnome.shell enabled-extensions` and loaded via session login.

## Notes for the agent
- The extension communicates with `org.gnome.SessionManager` over D-Bus using flags `12` (`GSM_INHIBITOR_FLAG_SUSPEND = 4` | `GSM_INHIBITOR_FLAG_IDLE = 8`), which natively inhibits both system sleep and idle display blanking in GNOME.
- GNOME Shell 45+ uses standard ES modules for extensions (`export default class ... extends Extension`).
