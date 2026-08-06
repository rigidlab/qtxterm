# qtxterm — Usage

A tabbed terminal with one-click command buttons and reusable command presets.

## Terminals and tabs

| Action | How |
|---|---|
| New tab (default shell) | `Ctrl+Shift+T`, or the `+` button at the right of the tab bar |
| New tab (specific shell) | **File → New Terminal →** PowerShell / Command Prompt / Git Bash / WSL |
| Close tab | `Ctrl+Shift+W`, or the `x` on the tab |
| Next / previous tab | `Ctrl+Tab` / `Ctrl+Shift+Tab` |

Only shells actually installed on your machine appear under **New Terminal**.

Tabs are labelled tmux-style as `index:title`, and the title tracks whatever the
shell reports — usually the current directory or running command.

`Ctrl+Shift+T` and `Ctrl+Shift+W` are used instead of plain `Ctrl+T`/`Ctrl+W`
on purpose: bash and readline bind `Ctrl+W` to "delete previous word", so
reusing it for "close tab" would break normal shell line-editing.

Closing the last tab closes the window.

## Commands vs. Macros

Both are the same underlying thing — a named list of shell lines — but they
serve different jobs, and each preset is one or the other:

- **Command** — runs in the terminal tab you're *already working in*, and you
  stay in it. For quick, short interactions: `git status`, `clear`.
- **Macro** — always opens a *fresh tab* and runs there. For anything
  long-running or disruptive that shouldn't hijack your current session:
  a dev server, a build, a deploy.

## Running them

- **Sidebar buttons** — one click sends that Command to the active terminal.
  This is the only place Commands run from; the Commands menu itself is
  management-only (New Command..., Manage Presets..., Show Sidebar) — it
  doesn't list them.
- **Macros menu** — every Macro. Picking one opens a new tab and runs it.

Show or hide the sidebar with **Commands → Show Sidebar**. Closing it from
its own title-bar button works too — either way it just hides, and the menu
item flips back to unchecked so you can bring it back.

## Creating and editing presets

Open **Manage Presets...** under the Commands menu to manage Commands, or
under the Macros menu to manage Macros — each opens scoped to its own
category, so there's no way to create a Command from the Macros dialog
or vice versa.

| Field | What it does |
|---|---|
| Name | Label shown in menus and on sidebar buttons |
| Group | Optional. Groups presets into sidebar sections and menu submenus |
| Commands | One shell line per row |
| Show in sidebar | Commands only — pins it as a sidebar button. Macros never appear there |

Changes save immediately, and the sidebar and both menus refresh straight away.

Presets are stored as JSON, so you can hand-edit or back them up:

- Windows — `%LOCALAPPDATA%\qtxterm\presets.json`
- Linux — `~/.config/qtxterm/presets.json`

## Appearance

**File → Preferences...** sets the color theme, font, and font size.

| Theme | Look |
|---|---|
| Qt Default | The original terminal colors, with your platform's native window chrome left untouched |
| VS Code Dark High Contrast | Pure black ground, saturated ANSI colors — VS Code's `hc-black` |
| VS Code Light+ | VS Code's default light theme |
| Solarized Dark | The classic low-contrast dark palette |
| Solarized Light | Solarized on its cream ground |

Everything except **Qt Default** themes the whole window — menus, tabs,
sidebar, and dialogs — not only the terminal grid. **Qt Default** deliberately
leaves the native look alone.

Changes apply immediately to every open tab, and are remembered for next time.

## What else is remembered

The window's size and position, and whether the Commands sidebar is showing,
are restored the next time you open qtxterm — alongside the appearance
settings above. They live next to your presets:

- Windows — `%LOCALAPPDATA%\qtxterm\window_state.ini`
- Linux — `~/.config/qtxterm/window_state.ini`

## How multiline presets run

Each line is typed into the terminal followed by Enter. Lines run strictly in
order, each finishing before the next begins — a preset starting with a
3-second sleep won't run its second line until that sleep is done.

Two differences from a real `.sh` or `.bat` script are worth knowing:

- **A failing line does not stop the rest.** There's no `set -e` equivalent;
  every line runs regardless of what came before.
- **Interactive prompts swallow the queued lines.** If a line triggers a
  password prompt, a `y/n` confirmation, or opens a full-screen app like
  `vim`, the lines waiting behind it get read as *answers to that prompt*
  rather than as commands. Keep prompting commands out of multiline presets,
  or run them by hand.
