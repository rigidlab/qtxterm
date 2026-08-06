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
  The sidebar is a curated shortcut list; only Commands you've ticked
  "Show in sidebar" appear there.
- **Commands menu** — every Command, including ones not pinned to the sidebar.
- **Macros menu** — every Macro. Picking one opens a new tab and runs it.

Show or hide the sidebar with **Commands → Show Sidebar**. It has no close
button, so it can't be dismissed with no way back.

## Creating and editing presets

Open **Commands → Manage Presets...** (or the same item under Macros).

| Field | What it does |
|---|---|
| Name | Label shown in menus and on sidebar buttons |
| Group | Optional. Groups presets into sidebar sections and menu submenus |
| Type | **Command** (active terminal) or **Macro** (new tab) |
| Commands | One shell line per row |
| Show in sidebar | Pin as a sidebar button. Commands only — Macros never appear there |

Changes save immediately, and the sidebar and both menus refresh straight away.

Presets are stored as JSON, so you can hand-edit or back them up:

- Windows — `%LOCALAPPDATA%\qtxterm\presets.json`
- Linux — `~/.config/qtxterm/presets.json`

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
