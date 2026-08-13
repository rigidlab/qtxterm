# qtxterm — Usage

A tabbed terminal with one-click command buttons and reusable command presets.

## Terminals and tabs

| Action | How |
|---|---|
| New tab (default shell) | `Ctrl+Shift+T`, or the `+` button at the right of the tab bar |
| New tab (specific shell) | **File → New Terminal →** PowerShell / Command Prompt / Git Bash / WSL: *distro* |
| New browser tab | **File → New Browser** |
| Close tab | `Ctrl+Shift+W`, or the `x` on the tab |
| Next / previous tab | `Ctrl+Tab` / `Ctrl+Shift+Tab` |
| Rename a tab | Double-click the tab |
| Split the pane | `Alt+Shift+=` (right) / `Alt+Shift+-` (down), or right-click → Split |
| Close a pane | `Alt+Shift+W`, or right-click → Close Pane |

Only shells actually installed on your machine appear under **New Terminal**,
and every installed WSL distro gets its own entry (`WSL: Ubuntu-22.04`).
Docker Desktop's `docker-desktop` and `docker-desktop-data` are left out —
they're data-only and give no usable shell.

Tabs are labelled tmux-style as `index:shell` — `0:powershell`, `1:bash`,
`2:cmd`. Hover a tab to see what the shell is reporting (usually the current
directory or running command); that goes in the tooltip rather than the
label, since some shells report a full path and would stretch the tab bar.

Double-click a tab to rename it — useful once several tabs run the same
shell and `0:powershell` / `1:powershell` stop telling them apart. The index
prefix stays, and renumbering keeps your name attached to the right tab.
Leave the box blank to go back to the automatic name. A rename sticks: a
browser tab that keeps renaming itself from the page host won't overwrite
it.

`Ctrl+Shift+T` and `Ctrl+Shift+W` are used instead of plain `Ctrl+T`/`Ctrl+W`
on purpose: bash and readline bind `Ctrl+W` to "delete previous word", so
reusing it for "close tab" would break normal shell line-editing.

Closing the last tab closes the window.

## Split panes

A tab can hold several terminals side by side. Right-click a terminal and
pick **Split Right** or **Split Down**, or use `Alt+Shift+=` / `Alt+Shift+-`.
Splits nest, so you can build columns of rows. Drag the divider to resize.

The pane you last clicked or typed in is the **active** one, outlined in the
highlight colour whenever a tab has more than one. That outline matters:
sidebar buttons, the Command menu and Selection Actions all go to the active
pane, so it answers "where will this land?".

**Close Pane** (`Alt+Shift+W`) closes just that terminal; closing the last
pane closes the tab. `Ctrl+Shift+W` still closes the whole tab, panes and
all. `Alt+Shift` chords are used rather than `Ctrl+Shift` because shells and
full-screen apps rarely bind them.

## Browser tabs

**File → New Browser** opens a web page in a tab beside your terminals. Type
in the address bar and press Enter: a full URL loads as-is, a bare host like
`example.com` or `localhost:8080` gets `https://`, and anything else — words
with spaces, say — becomes a search rather than a broken URL. The `←` `→` `⟳`
buttons are back, forward, and reload.

Browser tabs are labelled by host (`1:example.com`), with the page title in
the tooltip. Commands and Selection Actions do nothing while a browser tab is
active — there's no shell to send them to; switch to a terminal tab first.

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
  The sidebar is the curated view: only Commands you've pinned with *Show in
  sidebar* appear there.
- **Right-click in a terminal → Command** — every Command, grouped the
  same way as the sidebar, without leaving the terminal you're typing in.
  Unlike the sidebar this lists *all* of them, pinned or not. Picking one
  sends it to that terminal. The same menu has **Copy** and **Paste** (see
  below).
- **Macros menu** — every Macro. Picking one opens a new tab and runs it.

The Commands menu in the menu bar is management-only (New Command...,
Manage Commands..., Show Sidebar) — it doesn't list individual Commands.

Show or hide the sidebar with **Commands → Show Sidebar**. Closing it from
its own title-bar button works too — either way it just hides, and the menu
item flips back to unchecked so you can bring it back.

## Copy and paste

Right-click in a terminal for **Copy** and **Paste**.

- **Copy** takes the text you've selected with the mouse. It's greyed out
  when nothing is selected.
- **Paste** inserts the clipboard at the cursor without pressing Enter for
  you, so you can check a pasted command before running it. Multi-line
  clipboard text is handed to the terminal as a paste, not as typing, so
  shells and editors that use bracketed paste treat it correctly.

## Selection Actions

Select text in a terminal, right-click, and pick **Selection** to run
something against it. The submenu shows what you selected at the top, so you
can see the payload before sending it. Two built-in examples ship:

- **Search Google** — opens your browser on a search for the selected text.
- **Explain with Claude** — opens a new tab running `claude -p`, with the
  selection as its input.

Each action is one of two kinds, chosen in **Manage Selection Actions...**:

| Kind | What it does | Where the selection goes |
|---|---|---|
| Open a URL | Substitutes into a URL template and opens the browser | Percent-encoded into `{selection}` |
| Send to a command's input | Runs a shell command in a tab | Standard input, via a temp file |

The selection is never pasted into a command line. That keeps text
containing quotes, `;`, `&&` or backticks from being executed as part of the
command, and means multi-line and very long selections work — both of which
break if text is spliced into a command. URL actions cap the selection at
1500 characters, since browsers and search engines reject longer URLs.

If the right-click **Selection** submenu is empty — an install created before
this feature existed keeps its own presets — open **Manage Selection
Actions...** and press **Add Examples**.

## Creating and editing

Each menu manages its own category: **Manage Commands...** under Commands,
**Manage Macros...** under Macros, **Manage Selection Actions...** under
Selection. Each dialog opens scoped to that category, so there's no way to
create a Command from the Macros dialog or vice versa.

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

## Preferences

**File → Preferences...** sets the default shell, color theme, font, and
font size.

### Default shell

Which shell new tabs open with — the startup tab, the `+` button,
`Ctrl+Shift+T`, and Macros. **System default** follows the OS
(`powershell.exe` on Windows, `$SHELL` elsewhere); otherwise pick any
detected shell, including a specific WSL distro. Existing tabs keep the
shell they started with, and **File → New Terminal** still opens whichever
shell you pick there regardless of this setting.

If the chosen shell later disappears — a WSL distro you removed — new tabs
quietly fall back to the system default rather than failing to open.

### Appearance

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
