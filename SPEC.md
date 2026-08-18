# qtxterm — Cross-Platform GUI Terminal (PySide6 + xterm.js)

## Overview
A desktop terminal application (Windows + Linux) built with PySide6, rendering
terminals via embedded xterm.js (in `QWebEngineView`), backed by real PTYs.
Supports multiple tabs, a customizable sidebar of one-click command buttons,
and a Macros menu for multi-step/multi-tab command sequences.

## Core Architecture Decisions

| Concern | Decision |
|---|---|
| Terminal rendering | xterm.js + addon-fit + addon-webgl, vendored locally in `assets/xterm/` (no CDN, offline-capable) |
| Python <-> JS bridge | `QWebChannel` (no extra port/server) |
| PTY backend | `pywinpty` (ConPTY) on Windows, `ptyprocess` (openpty) on Linux, behind a common `PtySession` wrapper interface. `start()` takes a real argv `list[str]`, not a bare command string - needed for e.g. `["wsl.exe", "-d", "Ubuntu"]` |
| Project tooling | `uv` (installed via `pipx install uv`), `pyproject.toml` + `uv.lock` |
| Packaging (later) | PyInstaller, one spec per OS |

## Data Model — unified "Command Preset"

Commands and macros share one storage format and one `Preset` shape, but
`target` is a strict, mutually-exclusive category, not just an execution
detail — every preset is *either* a Command *or* a Macro, never both:

- **Command** (`target: active`): a short interaction with a terminal you're
  actively working in and staying in — `git status`, `clear`, etc. Sent to
  whichever tab is currently active; you keep using that tab afterwards.
- **Macro** (`target: new_tab`): a script for something long-running or
  disruptive to run alongside your current work — starting a dev server,
  a build, a deploy — so it gets its own fresh tab rather than hijacking
  the terminal you're in.

```yaml
Preset:
  name: str
  group: str                       # optional, for menu/sidebar section organization
  lines: list[str]                 # one or more shell lines
  target: active | new_tab         # category: Command vs Macro. Default:
                                    # active if len(lines)==1 else new_tab
  show_in_sidebar: bool            # opt-in to sidebar button; only meaningful
                                    # (and only offered in the editor) for
                                    # target: active presets — Macros don't
                                    # appear in the sidebar, only the Macros menu
```

Stored as a single JSON file under the platformdirs user config dir
(`presets.py::PresetStore`, built in Phase 3).

- **Commands sidebar**: shows only `target: active` presets with
  `show_in_sidebar: true`. One-click sends `lines` to the currently active
  terminal tab. Fast, always visible. (Built in Phase 3.)
- **Macros menu** (dropdown, grouped by `group`): shows only `target: new_tab`
  presets, with Run / Edit / New / Delete. Clicking one always opens a fresh
  tab, spawns a PTY, and feeds `lines` into it in sequence. (Phase 4.)

### Why the split survives — settled

**Decision: keep the Commands/Macros separation, and only Commands appear as
sidebar buttons.** Considered and rejected: collapsing both into one type
with a `run in: active | new tab` field, and a separate Button/layout entity
on top of presets. What is in the code today is the intended design, not an
interim state.

The obvious objection is that Commands and Macros do the same thing: feed
lines to a shell. The only mechanical difference is which tab receives them.
That reading makes the categories look like an execution detail promoted to a
taxonomy, and it argues for one "Command" with a `run in: active | new tab`
field.

The split holds because the real distinction is **the interaction pattern,
not the execution target** — where it runs falls out of that, not the other
way round:

- **Command — contextual and frequent.** You're looking at a terminal and you
  reach for it. That is a button beside the terminal. `Command` and `sidebar
  button` are close to synonymous; running in the active tab is a consequence
  of being a thing you click *while working in that tab*.
- **Macro — occasional, and it launches something that goes elsewhere.** You
  are not mid-flow in a terminal when you start a dev server. That is a menu
  item, and a fresh tab is a consequence of it being disruptive.

Two things follow, and both are deliberate:

- **A Command need not be a sidebar button.** `show_in_sidebar` keeps the
  sidebar a curated subset; the right-click `Command` submenu lists all of
  them. "Button" is a property of a Command, not a synonym for it.
- **Commands stay out of the menu bar.** The menu bar is the surface furthest
  from the terminal, which contradicts the contextual argument above, and it
  would be a third surface to keep in sync (sidebar, right-click, menu bar).
  Individual Command listings were removed from the Commands menu in `4ce011c`
  for exactly this reason. If the underlying need turns out to be *keyboard*
  access, the answer is per-preset keyboard shortcuts, not menu items — that
  serves the contextual model instead of fighting it.

Known costs, accepted deliberately — these are consequences of the decision,
not oversights to be "fixed":

- A Macro cannot be pinned to the sidebar, even if it is your most-used
  action. Buttons are for Commands; a Macro that you reach for constantly is
  a sign it wanted to be a Command.
- Macros are absent from the terminal right-click menu, where Commands appear.
- The Commands menu bar entry lists nothing while the Macros one lists
  everything, so two menus for one concept behave differently.

If it is ever reopened, note that unification needs **no storage change**:
`target` and `show_in_sidebar` already exist, so it is a presentation change,
cheap to reverse in either direction. The plausible trigger would be a
concrete case the split cannot serve — most likely wanting a one-click "start
dev server" button.

Selection Actions are a genuinely different category and are unaffected by
any of this: they consume the terminal's selection, and a `url` one never
touches a shell at all. The durable line is *takes input* vs *doesn't*.

### Sidebar Layout (separate from preset content)

Layout is a distinct, user-editable arrangement on top of the preset list —
editing *placement/appearance*, not the command itself:

```yaml
SidebarLayout:
  sections:
    - title: str
      columns: int                 # buttons per row
      button_size: small|medium|large
      preset_refs: list[str]       # ordered preset names in this section
```

Edited via an "Edit Layout" mode on the sidebar (drag to reorder/add/remove),
stored separately from `presets.json` (e.g. `sidebar_layout.json`) so layout
and content can evolve independently.

## Phased Build Plan

### Phase 1 — Single-tab terminal ✅ done
Goal: prove the core rendering + I/O loop works cross-platform before any
tabs/macros/sidebar complexity.

- [x] `uv init` project, add deps: `PySide6`, `PySide6-Addons` (WebEngine), `pywinpty` (win only), `ptyprocess` (posix only)
- [x] Vendor xterm.js + addon-fit into `assets/xterm/`
- [x] `PtySession` abstract wrapper: `start(shell, cols, rows)`, `write(data)`, `resize(cols, rows)`, `on_output` callback, `close()`, `is_alive`
  - `WinPtySession` using `pywinpty`
  - `PosixPtySession` using `ptyprocess` (verified on Ubuntu 24.04 under WSL - see Phase 4r)
- [x] `TerminalWidget(QWidget)`: hosts `QWebEngineView` loading local `terminal.html`, wires `QWebChannel` object (`TerminalBridge`) exposing `sendInput`/`resize`/`ready`/`setTitle` (JS->Py) and `output`/`exited`/`title_changed` (Py->JS)
- [x] `terminal.html`/`terminal.js`: init xterm.js + fit addon, pipe keystrokes to bridge, render incoming PTY output, handle resize -> notify bridge
- [x] `MainWindow(QMainWindow)`: hosts terminal(s), spawns default shell (`$SHELL` on Linux, `powershell.exe` on Windows) on startup
- [x] Verify: shell prompt renders, keyboard I/O works, resizing the window resizes the PTY, full-screen apps (vim) render correctly, process exit closes cleanly (caught + fixed a PTY-leak-on-close bug: child widgets never get `closeEvent` from a closing `QMainWindow`)
- [x] pytest + pytest-qt suite: PTY backend (real spawn/write/read/resize), bridge signal re-emission, widget wiring against a fake PtySession

**Definition of done for Phase 1**: one window, one working real terminal, on both Windows and Linux, no crashes on resize/exit. *(Windows verified end-to-end; Linux backend implemented but untested — no Linux machine available yet.)*

### Phase 2 — Tabs ✅ done
- [x] `TerminalTabWidget(QTabWidget)` central widget, each tab = one `TerminalWidget` + `PtySession`
- [x] New tab (`+` corner button, Ctrl+Shift+T), close tab (per-tab "x", Ctrl+Shift+W), Ctrl+Tab/Ctrl+Shift+Tab to switch — deliberately not plain Ctrl+T/W, which would fight bash/readline's Ctrl+W word-delete
- [x] Tab labels: tmux-style `"{index}:{shell}"` (`bash`, `cmd`, `powershell`), renumbered on add/close/reorder. Deliberately *not* the shell's OSC title: Git Bash sends `MINGW64:/c/Users/dev/git/qtxterm` and cmd its own full exe path, which made tabs unreadably wide. The live OSC title (`xterm.js onTitleChange` -> bridge) becomes the tab's tooltip instead, so the cwd is still reachable
- [x] `active_terminal()` tracks the current tab's `TerminalWidget` for later command/macro targeting
- [x] Closing the last tab closes the window; closing the window (titlebar X) shuts down every tab's PTY, not just the active one
- [x] pytest-qt suite: tab creation/labeling/renumbering, active-terminal tracking, all-tabs-closed vs close-all-tabs semantics, next/prev wraparound

### Phase 3 — Command Presets + Sidebar ✅ done
- [x] `Preset` dataclass + `PresetStore` JSON persistence (`presets.json` under the
      platformdirs user config dir), seeded with example presets on first run
- [x] `CommandSidebar` dock widget: buttons grouped by `group` (ungrouped flat at
      top), single column — full drag-and-drop `SidebarLayout` arrangement deferred
      to Phase 4, per-scope decision (not enough presets/macros yet to need it)
- [x] Click -> `run_in_active()` sends `lines` + Enter to the active terminal's PTY.
      Only ever shows `target: active` presets (Commands) - see the Commands vs
      Macros split below, finalized during Phase 4
- [x] `PresetEditorDialog` (add/edit/delete, set group + show_in_sidebar)
- [x] pytest suite: PresetStore CRUD/persistence, sidebar grouping/click emission,
      editor dialog New/Save/Delete flows

### Phase 4 — Macros menu + new-tab execution ✅ done
- [x] Commands vs Macros finalized as a strict split on `target` (see "Data Model"
      above): every preset is a Command (`active`) or a Macro (`new_tab`), never
      both. `PresetEditorDialog` gained an explicit Type dropdown - target is no
      longer inferred purely from line count, and picking Macro live-disables
      "Show in sidebar"
- [x] `MacrosMenu(QMenu)`: lists only `target: new_tab` presets, grouped by
      `group` into submenus (ungrouped ones flat), plus New Macro.../Manage
      Presets... actions
- [x] Running a macro -> `TerminalTabWidget.run_in_new_tab()`: opens a tab, feeds
      `lines` once the PTY has actually started (`TerminalWidget.pty_started` /
      `run_when_ready()`) - fixes a real race where writing immediately after
      `new_tab()` returns silently drops input, since the PTY only starts after
      an async QWebEngineView load -> xterm.js boot -> JS-calls-Python round trip
- [x] `PresetStore` is now reactive (`changed` signal after every `save()`), so
      the sidebar and Macros menu both auto-refresh regardless of which surface
      (or dialog) made the edit
- [x] pytest suite: MacrosMenu grouping/actions/auto-reload, run_when_ready
      (immediate vs deferred), run_in_new_tab against a fake PTY
- [x] Verified end-to-end: menu renders grouped/ungrouped macros correctly;
      triggering one opens a new tab and runs every script line in sequence

### Phase 4b — File menu & multi-shell support ✅ done
- [x] `File` menu (before `Macros` in the menu bar): `New Terminal` submenu +
      `Exit`. `New Terminal` always has "Default Shell" (Ctrl+Shift+T shown as
      a hint, not a duplicate binding) plus one entry per shell `known_shells()`
      (`src/qtxterm/shells.py`) actually finds installed
- [x] Windows-only for now (PowerShell/CMD/Git Bash/WSL are Windows concepts);
      `known_shells()` returns `[]` on other platforms
- [x] Git Bash resolved via its standard install dirs, not `shutil.which` (which
      can resolve to the unrelated legacy WSL `bash.exe` shim in System32)
- [x] WSL resolved by listing real distros (`wsl.exe -l -q`, UTF-16LE decoded)
      and picking one explicitly (`wsl.exe -d <name>`), skipping Docker
      Desktop's non-interactive `docker-desktop`/`docker-desktop-data` -
      bare `wsl.exe` launches whatever's marked "default", which can be one of
      those and fail outright with no usable shell
- [x] `PtySession.start()` changed from a bare shell string to a real argv
      `list[str]` throughout (`TerminalWidget`, `TerminalTabWidget`), needed
      for `wsl.exe -d <name>`-style multi-arg commands
- [x] Fixed along the way: `WinPtySession` passed a bare string to
      `PtyProcess.spawn()`, which shlex-splits on whitespace and silently
      broke any shell path containing a space (e.g. Git Bash's default
      `C:\Program Files\Git\bin\bash.exe`)
- [x] Fixed along the way: a PySide6/shiboken lifetime issue where
      `QMenu.addMenu()`'s returned submenu can be garbage-collected without a
      retained Python reference, despite being C++-parented to a live menu -
      affected both the new File menu and `MacrosMenu`'s group submenus
- [x] pytest suite for `known_shells()`; verified end-to-end that all four
      shells spawn correctly in a new tab

### Phase 4c — Commands menu ✅ done
- [x] `Commands` menu item (menu bar order: File, Commands, Macros), alongside
      the existing sidebar rather than replacing it
- [x] `MacrosMenu` refactored into a shared `_PresetCategoryMenu` base
      (`src/qtxterm/preset_menu.py`, replaces `macros_menu.py`); `CommandsMenu`
      only supplies its target (`active`), run behavior (`run_in_active`), and
      labels - grouping/reload/New/Manage logic is shared
- [x] Lists every `target: active` preset, not just sidebar-pinned ones - the
      sidebar stays the curated quick-access view, this menu is the full list
- [x] pytest suite (renamed to `test_preset_menu.py`, covers both menus);
      verified end-to-end

### Phase 4d — Terminal right-click menu ✅ done
- [x] Right-clicking a terminal opens a context menu with a `Command`
      submenu of every `target: active` preset, grouped by `group`; picking
      one sends it to that terminal. Lists all Commands, not just
      sidebar-pinned ones - the sidebar stays the curated view.
- [x] Copy/Paste in the same menu. Copy reads a cached selection that
      xterm.js pushes over the bridge on every `onSelectionChange`, rather
      than fetching it on demand: `runJavaScript` is async, so an on-demand
      read would resolve too late to enable or disable a menu item that is
      already being shown. Paste calls `term.paste()` in JS instead of
      writing to the PTY directly, so bracketed paste mode is honored and a
      multi-line clipboard isn't read as a series of typed commands.
      Availability is refreshed on `aboutToShow` - selection and clipboard
      both change without the preset store changing.
- [x] `QWebEngineView` needs `CustomContextMenu` policy or it shows
      Chromium's own Back/Reload/View Source menu. The request is re-emitted
      as `TerminalWidget.context_menu_requested` (global pos) and forwarded
      by `TerminalTabWidget`, so `MainWindow` wires one shared menu instead
      of one per tab.
- [x] Fixed along the way: `QMenu.addMenu(str)` gives PySide6 ownership of
      the new submenu, and `QAction.menu()` then ties its lifetime to the
      returned wrapper - so a discarded `action.menu()` lookup destroys the
      submenu for *every* holder, including a parent that deliberately kept a
      reference. Submenus are now built with an explicit C++ parent
      (`add_submenu`), which also made the old reference-retention lists
      unnecessary; `clear_menu` disposes of them on reload so rebuilding
      doesn't orphan a QMenu per change.

### Phase 4e — Selection Actions ✅ done
- [x] Third preset category alongside Commands and Macros, keyed off a new
      `input` field (`none` | `selection`); `category_of()` is now the single
      place the split is decided, replacing scattered `target ==` checks.
      Reachable from the terminal right-click menu under `Selection`,
      which is disabled without a live selection and shows a truncated
      preview of what will be sent.
- [x] `kind` (`url` | `stdin`) decides how the selection travels, because
      each route needs different escaping. The selection is **never**
      interpolated into a command line: that route (`arg`) is deliberately
      not offered, since it would mean owning a per-shell quoting matrix
      across PowerShell/cmd/bash/WSL, and would still break on multi-line
      selections and on Windows' ~8191-char command-line cap.
  - `url` - percent-encoded with `safe=""` into a `{selection}` placeholder
    and opened via QDesktopServices; never touches a shell. Capped at 1500
    chars, below the ~2083 practical URL ceiling.
  - `stdin` - written to a temp file the command reads on standard input.
- [x] Fixed along the way: `<` is **not** portable, contrary to the original
      design. Windows PowerShell reserves it ("The '<' operator is reserved
      for future use"), so `feed_from_file()` is per-shell: `Get-Content -Raw
      | cmd` for powershell/pwsh, `type | cmd` for cmd, `< path` for
      POSIX shells, and `< /mnt/c/...` for WSL, whose Linux side can't see a
      Windows path. Only the generated path is interpolated, never the
      selection, so the safety property is unchanged. Caught by running it
      against a real PowerShell tab - unit tests all passed with the broken
      form.
- [x] Temp files are swept at startup (24h old), not on tab close: the
      command reading one may outlive the tab.
- [x] Menu bar order is now File, Macros, Commands, Selection, Help - one
      menu per preset category. `SelectionMenu` is management-only, the same
      shape as `CommandsMenu` and for the same reason: running an action
      needs a live selection, which a menu bar item can't offer, so that half
      lives in the terminal's right-click `Selection` submenu instead.
- [x] Defaults are only seeded on first run, so pre-existing installs get an
      empty right-click `Selection`; `Selection -> Manage Selection
      Actions... -> Add Examples`
      adds the built-in examples by name without duplicating.

### Phase 4f — Default shell preference + per-distro WSL ✅ done
- [x] `File -> Preferences...` gains a Default shell combo: System default,
      or any detected shell. Resolved in `TerminalTabWidget.new_tab()` rather
      than by callers, so every route to a new tab (+ button, Ctrl+Shift+T,
      Macros, Selection Actions) honours it; an explicit `shell=` argument
      (File -> New Terminal) still wins.
- [x] `ShellPreferenceStore` persists the shell's *label*, not its resolved
      argv: readable in the ini, portable between machines, and it degrades
      to the system default if that shell is uninstalled later - a stored
      argv would simply fail to spawn.
- [x] `known_shells()` now lists every installed WSL distro separately
      (`WSL: Ubuntu-22.04`) instead of silently picking the first one;
      data-only Docker distros stay filtered out.
- [x] `selection_actions.default_shell_name()` removed - `shell_name_for()`
      asks `tabs.default_shell_name()` instead, so a stdin action opening a
      new tab picks the redirection form for the shell that tab will
      actually run.

### Phase 4g — Browser tabs ✅ done
- [x] `File -> New Browser` opens a `BrowserWidget` (address bar +
      QWebEngineView + back/forward/reload) as a tab beside the terminals.
- [x] `normalize_url()` guesses between "go here" and "look this up": a
      scheme loads verbatim, a dotted host (or localhost[:port]) gets
      https://, anything else becomes a search - `https://hello%20world` is
      never what was meant.
- [x] Address bar follows `urlChanged`, not only typed input, so it tracks
      links clicked in the page and redirects.
- [x] Tab label is the host, live-updated - unlike a shell's OSC title, a
      host is short and is exactly what identifies the tab. Page title goes
      in the tooltip.
- [x] `active_terminal()` is now type-checked instead of returning
      `currentWidget()`: with browser tabs in the mix, the sidebar, Command
      submenu and Selection Actions would otherwise try to write to a web
      page. They no-op while a browser tab is active.
- [x] No `QWebChannel` is registered on a browsed page, unlike terminal.html
      - a web page must never reach `TerminalBridge` and be able to write to
      a PTY.

### Phase 5 — Packaging & polish
- Sidebar "Edit Layout" mode (drag reorder, section management) - deferred here
  from Phase 3/4 twice now; revisit once real usage shows it's actually needed
- PyInstaller specs (Windows `.exe`, Linux binary/AppImage)
- [x] App icon (`src/qtxterm/branding.py`): an SVG terminal-window mark, plus a
      simplified chevron+cursor variant used at 32px and below where the frame
      and title dots blur. Both are registered as per-size pixmaps on one
      `QIcon` - Qt's SVG icon engine keeps one entry per mode/state, so
      `QIcon.addFile()` overwrites instead of keying by size and the
      last-added file would win everywhere. Windows also needs an explicit
      AppUserModelID, or the taskbar groups the app under python.exe and shows
      the interpreter's icon regardless of `setWindowIcon()`.
- Settings persistence (last window size, default shell), themes (xterm.js theme presets)

## Execution semantics: multiline presets vs. a real script

Both Commands and Macros execute the same way — each line is written to the
PTY followed by Enter. They differ only in *where* they run (`target`), not in
how. Verified empirically:

- **Sequencing works.** Lines run strictly one after another, each completing
  before the next starts, because the terminal's input buffer queues them and
  the shell reads one line at a time. A macro whose first line is
  `Start-Sleep -Seconds 3` does not run line 2 until the sleep finishes, and
  nothing is garbled or lost. This matches script behavior.
- **No stop-on-error.** Unlike `set -e` or `&&` chaining, a failing line does
  not halt the rest. Deliberately left as-is - matches "paste these commands
  into my terminal" semantics. If revisited, note that Windows PowerShell 5.1
  (the default shell here) has no `&&`, so a fix needs per-shell handling.
- **Interactive prompts consume queued lines.** If a line triggers a `sudo`
  password, a `y/n` confirm, or a full-screen app, the buffered keystrokes are
  read as input to *that* prompt rather than as commands. Inherent to feeding a
  live terminal's keyboard buffer; the tradeoff for running in a session you
  can keep interacting with.

### Phase 4h — Tab rename ✅ done
- [x] Double-click a tab to rename it (`QInputDialog`, prefilled with the
      current name); blank restores the automatic name.
- [x] Titles are two layers rather than one: `_auto_titles` (shell name, or a
      browser tab's host) and `_custom_titles` (user-set, wins when present).
      Kept apart so a rename isn't silently overwritten the next time the
      automatic name changes - a browser tab renames itself on every
      navigation - and so clearing a rename falls back to the *current*
      automatic name, not the one the tab was born with.
- [x] `tabBarDoubleClicked` fires with -1 for a double-click on empty tab bar
      space; that is ignored rather than prompting for a nonexistent tab.

### Phase 4i — Split panes, step 1: focus tracking ✅ done
Groundwork only - no visible change. A tab still holds exactly one terminal.

- [x] `active_terminal()` now means *the focused pane of the current tab*
      rather than "the current tab". It walks the tab's subtree, prefers the
      terminal last focused there, and falls back to the first one found.
- [x] Focus is tracked via `QApplication.focusChanged` plus
      `_owning_terminal()`, which walks up the parent chain. An event filter
      per terminal would not do: keyboard focus inside a terminal lands on a
      Chromium child widget, not on the `TerminalWidget`.
- [x] `_terminals_in()` / `_panes_in()` make the appearance and shutdown loops
      subtree-aware, so they already reach panes nested in a splitter.

Why this landed first, on its own: it is the only part of splitting that can
fail *silently*. If the active pane is wrong, a sidebar click sends `git
status` to the wrong terminal with no error. Everything else about splitting
(the splitter tree, close semantics, the active-pane border) fails visibly.

### Phase 4i — Split panes, step 2 ✅ done
- [x] `split_active()` builds a nested `QSplitter` tree; `close_active_pane()`
      closes one pane and unwraps any splitter left holding a single child, so
      the tree doesn't accumulate pointless single-child splitters.
- [x] Active-pane outline, painted in `TerminalWidget.paintEvent` rather than
      styled - a `QWebEngineView`'s native surface ignores a stylesheet border
      on its parent. Shown only when a tab has more than one pane.
- [x] Right-click Split Right / Split Down / Close Pane, plus `Alt+Shift+=`,
      `Alt+Shift+-`, `Alt+Shift+W`. Alt+Shift follows Windows Terminal:
      shells and TUIs rarely bind those, unlike Ctrl+Shift.
- [x] Three Qt traps found by measuring geometry, each of which silently
      produced a zero-width pane rather than an error:
  - `setSizes([1, 1])` takes **pixels**, not ratios - it gives each pane one
    pixel and dumps the rest into the last one. `_even_out()` uses stretch
    factors plus real halves, and runs again on the next event-loop turn
    because a freshly inserted splitter has no geometry yet.
  - Adding a widget to a `QSplitter` pulls it out of the tab widget's stack,
    so the tab surgery has to happen *before* reparenting, not after.
  - `removeTab()` explicitly hides the page it detaches, and a parentless
    widget starts hidden; a hidden splitter child is laid out at zero size.
    Both panes are shown explicitly.

### Phase 4i — Split panes, step 3: moving panes ✅ done
- [x] `move_active_pane(forward)` swaps the focused pane with its neighbour;
      the size list is deliberately left alone, so positions keep their widths
      and the panes trade places rather than shuffling the layout.
- [x] `move_active_pane_to_new_tab()` pulls a pane out into its own tab,
      reusing `_collapse_single_child_splitters()` to tidy the source. The
      pane keeps its shell, scrollback and PTY - only its container changes.
- [x] Menu labels follow the splitter's orientation: "Move Pane Left/Right"
      would be a lie in a stacked split, so it reads Up/Down there.

Mouse drag-and-drop of panes was considered and rejected for now: `QSplitter`
has no notion of dragging children to reorder, so it means hand-rolling a
drag source, drop targets and the tree surgery per drop - a custom docking
layer. Windows Terminal, iTerm2 and tmux don't offer it either. If it ever
becomes a hard requirement, nesting a `QMainWindow` per tab with panes as
`QDockWidget`s would get it from Qt for free, at the cost of a title bar on
every pane.

### Phase 4l — Browsers as panes ✅ done
- [x] `PaneWidget` base class, inherited by `TerminalWidget` and
      `BrowserWidget`, carrying the shared contract (`default_title`,
      `shutdown()`, `apply_appearance()`) and the active-pane outline.
- [x] Splitting works on any pane and yields *the same kind*: a browser
      splits into a browser, a terminal into a terminal. "Split" reads as
      "another one of these", and it keeps the shortcut unambiguous.
- [x] `active_pane()` (either kind) drives splitting, moving and closing;
      `active_terminal()` stays terminal-only and returns None when a browser
      pane is focused. It deliberately does *not* fall back to another
      terminal in the tab - that would run a sidebar command somewhere you
      weren't looking.
- [x] A shared base type is what makes `_panes_in()` correct by
      construction. Matching on `TerminalWidget` alone made it fall back to
      the tab's root widget, so a split tab handed a `QSplitter` to
      `shutdown()` - the AttributeError fixed in 2ae5958. A splitter holding
      only browsers would have reproduced it; now it can't.
- [x] Browser panes are keyboard-only for split/close: a web page keeps
      Chromium's context menu, which is what you want for links and images.

Remaining, not started:
- Focus-navigation shortcuts between panes (currently click to focus).
- Tab labels still name one shell when a tab holds several panes.
- Per-pane close on shell exit.

`QDockWidget` was considered and rejected for panes: docks are built for
peripheral tool windows around a central widget, carry title bars you would
not want on every pane, and bring float/drag-out behaviour that a splitter
does not need. The sidebar stays a dock; terminals do not.

### Phase 4j — The window outlives its terminals ✅ done
- [x] Startup no longer opens a terminal, and closing the last one no longer
      closes the window (`all_tabs_closed` is still emitted, just not wired to
      `close()`). Opening the app doesn't decide what you wanted to open, and
      closing a tab doesn't quit the app out from under you.
- [x] An empty tab widget is a blank rectangle, so `paintEvent` draws a hint
      naming the two ways to open a terminal. The `+` corner button is
      deliberately *not* named: with zero tabs Qt doesn't lay out the tab bar
      row, so the corner widget is never drawn - even though
      `cornerWidget().isVisible()` still returns True, which is how the first
      version of the hint came to advertise a button that wasn't on screen.

### Phase 4k — First-terminal latency ✅ done
Opening the app empty (Phase 4j) exposed a cost that used to hide inside
start-up: the first terminal flashed while Chromium started.

- [x] Measured before fixing: first terminal 0.64s to `pty_started`,
      second 0.17s. QtWebEngine spawns its render process lazily, on the
      first page load, so the first terminal paid all of it.
- [x] The bigger half was not speed at all: adding the **first**
      QWebEngineView to a top-level window makes Qt rebuild the native
      window. The HWND genuinely changes (measured 5179268 -> 5244804 on the
      first terminal, stable after), which on screen reads as the window
      closing and reopening. A `QWebEnginePage` does not trigger it - only a
      view, because only a view is in the widget hierarchy.
- [x] `webengine.prepare_window()` creates a 1x1 `WA_DontShowOnScreen`
      QWebEngineView inside the window at the end of `MainWindow.__init__`,
      before the window is shown, and discards it once loaded. That pays both
      costs off screen: the HWND then never changes, and the first terminal
      drops from 0.64s to ~0.26s. The view is disposable - verified the
      native window keeps its new form without it.
- [x] `page().setBackgroundColor(theme.background)` on every terminal view.
      A `QWebEngineView` paints white until terminal.js applies the theme,
      which flashed on *every* new terminal, not just the first - worst on a
      dark theme. Re-applied on theme change.
- [x] Warm-up lives in `app.main()`, not `MainWindow.__init__`: tests build
      windows constantly and shouldn't each spawn a render process.

### Phase 4m — Visible chrome borders ✅ done
Menus, tabs and the content frame all had borders too faint to see on dark
themes.

- [x] Cause: Fusion derives a menu's frame from
      `palette.window().darker(140)` - *darker* than the menu it outlines.
      Measured contrast: **1.00:1** on VS Code Dark High Contrast (black on
      black), 1.14:1 on Solarized Dark, ~2:1 on the light themes.
- [x] Same cause for the tab strip and the frame around the terminal:
      measured **1.3:1** (`#1e1e1e` on `#000000`) on VS Code Dark High
      Contrast.
- [x] `chrome_border_color()` mixes the window *text* colour into the window
      instead, stepping up only until the frame clears 3:1 - WCAG's bar for
      non-text UI, which is the right one for something you only have to see,
      not read. One rule works in both directions: lighter on dark themes,
      darker on light ones. Now 3.66 / 3.20 / 3.15 / 3.10:1.
- [x] Applied as an app style sheet (`chrome_stylesheet()`) covering
      `QMenu`, `QTabWidget::pane` and `QTabBar::tab`. Menus keep their
      palette-driven item painting - only the frame is restyled - but tabs
      have to be spelled out, because styling any part of `QTabBar::tab`
      makes the style sheet take over painting it.
- [x] Which tab is selected therefore needed restating, and **not** with
      `alternate_base`: that is `#0d0d0d` against a `#000000` window, so the
      first attempt left the selected tab indistinguishable from its
      neighbour. The cue is an accent line in the theme's highlight colour
      plus full-strength text, with unselected tabs dimmed - the signal VS
      Code's own tab strip uses, and one that survives any palette.
- [x] The active-pane outline had the same problem from a different source:
      it paints `QPalette::Highlight` raw, which is 2.34:1 against black on
      VS Code Dark High Contrast - dimmer than the 3.66:1 frames beside it.
      `ensure_contrast()` lifts it in HSL rather than blending toward white,
      so the hue survives; an accent washed to grey is no longer an accent.
- [x] Its bar (`ACTIVE_PANE_CONTRAST`, 4.0) is deliberately above the frames'
      3.0: it marks *state* and has to out-shout the static chrome next to
      it. 4.0 clears them everywhere without recolouring accents that already
      passed - 4.5 starts dragging Solarized Dark's blue lighter for no gain.
      Measured on screen afterwards: #166ec6, 4.08:1.
- [x] Inactive panes previously drew no frame at all, so on a dark theme only
      the splitter gap separated them. Every pane in a split now gets one,
      from the same `frame_color()` the tab strip and content edge use - so
      the three can't drift apart - while the focused pane keeps the accent.
      A pane alone in its tab still draws nothing: the tab already outlines
      it, and a second box inside the first is noise. `set_pane_state(in_split,
      active)` carries both facts, replacing a single flag that conflated
      them.
- [x] Side effect worth knowing: an app style sheet makes Qt wrap the style,
      and the wrapper reports an empty `objectName()`. A test asserting
      `app.style().objectName() == "fusion"` had to change - restoring the
      native style is still covered separately.

## Process cleanup on close — verified, no leak

"If a terminal starts a long-running process, does closing the tab kill it?"
Measured on Windows against real PTYs (`ping -n 600` to a unique address, so
the process could be identified by command line):

| Spawned how | Closing the tab / window |
|---|---|
| Direct child (`ping ...`) | killed |
| Grandchild (`cmd /c ping ...`) | killed |
| The shell itself | killed |
| App hard-killed, no `closeEvent` (crash, Task Manager) | killed |
| Detached (`Start-Process`, `start`) | **survives** |

The mechanism is **not** `terminate(force=True)` in `WinPtySession.close()`.
That kills the shell only, and on Windows killing a process orphans its
children. What actually cleans up is **ConPTY teardown**: closing the
pseudoconsole tears down the console and every process attached to it. That
is also why the crash case is safe - process death closes the handles, so the
pseudoconsole dies even though no cleanup code ran.

The survivor is correct, not a bug: `Start-Process` explicitly creates a
process *not* attached to the console, and killing it would break the
documented contract of that command. Windows Terminal, cmd and PowerShell all
behave the same way.

Not verified on Linux. `PosixPtySession.close()` is the same
`terminate(force=True)`, but the mechanism differs - closing the pty master
sends `SIGHUP` to the foreground process group, which normally reaps
children, while `setsid`/`nohup` processes survive. Same boundary, different
plumbing; the POSIX backend has still never been run (see Phase 1).

Worth re-checking if the PTY backend, the shutdown path, or the tab-close
path is ever reworked.

### Terminal sizing is pushed from Qt, never measured by the page ✅ done
Found while testing multi-step Macros: a macro that split a pane and then
opened a second tab left a PowerShell stack trace across the new pane —
`PSConsoleReadLine.SelfInsert` → `SetCursorPosition` →
`ArgumentOutOfRangeException: Actual value was -1`.

- [x] Not a race on typing, as it first looked. Measured: the pane's PTY
      **started at 54x1**. PSReadLine renders its prompt into a one-row
      console, computes a cursor row of -1, and throws.
- [x] Cause: Chromium skips layout for a view whose tab is in the
      background. Measured with the panes left in a background tab — Qt
      geometry 429x248, page viewport 30px; switching to that tab made it
      248px immediately. `fitAddon.fit()` had faithfully fitted the stale
      viewport. `page().setVisible(True)`, hide/show and a ±1px resize poke
      all failed to force the layout.
- [x] Fix: the page no longer measures itself. `terminal.js` exposes
      `window.applySize(w, h)`, which sizes `#terminal` in explicit pixels,
      fits, and reports `ready` (first call) or `resize` (later ones).
      `TerminalWidget._apply_size()` pushes the view's size on `resizeEvent`
      and on the new `bridge.loaded()` handshake — Qt logical pixels map 1:1
      to CSS pixels, verified (view 425x505 → document 505px).
- [x] The old `window.addEventListener("resize")` path is gone; one source
      of truth. Verified afterwards: 3/3 crash-free runs (was 3/3 crashing),
      every pane starting at a real size, and resize still reaching the shell
      on window resize, split, splitter drag and font-size change.
- [x] Font-size changes now report the new grid too. `applyAppearance()`
      refitted without telling the PTY, so the shell kept wrapping to the old
      width — a pre-existing bug this path exposed.

### Phase 4n — Right-click menu order preference ✅ done
Where each group sits in the terminal right-click menu is a matter of
which one you reach for, so it is a preference rather than a fixed opinion.

- [x] `menu_prefs.ContextMenuOrderStore` persists the order of the four
      sections (`menu/context_order` in the ini) and emits `changed`, so the
      one shared `TerminalContextMenu` rebuilds itself the moment it's saved —
      same pattern as `PresetStore.changed`.
- [x] Copy/Paste is a movable section too, not a pinned header. It still
      *leads by default* - it's the one thing here people hit by muscle
      memory, and every other terminal puts it first - but a preference that
      exempts the entry you most want at the bottom isn't much of one.
- [x] It's the only section that isn't a submenu, so it carries its own
      separators wherever it lands: two bare actions butting straight against
      a run of submenus read as part of the list above them.
- [x] `normalise_order()` drops unknown sections and appends missing ones, so
      a stale or hand-edited setting can never make a section disappear —
      a silently vanishing menu item would be a miserable thing to debug.
- [x] Up/Down buttons, not drag-and-drop: four rows are too few and too
      short a target for dragging to be worth its discoverability cost. The
      moved row keeps the selection, so Move Up twice moves one entry two
      places.
- [x] `QListWidget` picked up a themed border in `chrome_stylesheet()` for
      the same reason menus and tabs did — Fusion's frame is invisible on a
      dark theme, which left the rows reading as loose text in the form. Also
      improves the Manage dialogs' lists.

### Phase 4o — Soak test: does it survive being left open? ✅ done
A terminal is an app you open on Monday and close on Friday, so the failure
that matters is not a crash but decay: it gets heavier, then slower, then
stops drawing. `tests/test_soak.py` runs one compressed session over and
over and asserts that nothing keeps climbing.

- [x] Deselected from the default run (`addopts = "-m 'not soak'"`).
      `pytest -m soak` is ~90s; `--soak-minutes 1440` is the full day.
      `--soak-csv` dumps every sample, because on a long run the shape of
      the curve says far more than pass/fail does.
- [x] Watched: RSS, GDI/USER handles (Windows caps these per process, and a
      GUI that leaks one per window dies of that long before it runs out of
      memory), kernel handles, Python objects, live widgets, and event-loop
      latency. Read through `ctypes`, not psutil - a soak test that needs an
      extra package installed is one nobody runs.
- [x] One tab is never closed and is fed output every cycle. "Open for 24
      hours" usually means one terminal nobody has touched since Monday, and
      a test that closes everything each round would miss it entirely.
- [x] **Thresholds are per *cycle*, not per hour.** Per-hour looked obvious
      and was wrong: fitted over a decelerating curve it shrinks the longer
      you measure - the same healthy process reported +4241 MB/h over 30s,
      +620 MB/h over 4min and +95 MB/h over 8min. Per-cycle growth doesn't
      depend on how long the run happened to be, so one threshold covers the
      smoke run and the 24-hour one.
- [x] Judged on the last quarter of the run, and `DEFAULT_CYCLES = 60`
      because that is where the measurements say things settle: handles stop
      climbing around cycle 45 (+6.2/cycle over the first 20, +2.1 by 40,
      +0.16 after), memory around 40-60 (+2.1 MB/cycle early, +0.4 by 40,
      *negative* past 130 as the working set is handed back). A run shorter
      than that checks the structural invariants and says why it skipped the
      trend, rather than reporting warm-up as a leak.
- [x] Structural invariants, which need no trend at all: only the long-lived
      terminal is alive at the end, the per-widget bookkeeping dicts don't
      hold closed widgets, the context menu doesn't accumulate submenus, and
      the count of receivers on each long-lived store is unchanged — a menu
      that connects per tab and never disconnects makes every save slower
      than the last.
- [x] Results, 199 cycles: memory settles ~350MB and stops, handles ~1780
      and stop, GDI/USER/widgets dead flat, event-loop latency max 16ms with
      a median of 0 throughout. Nothing found to fix.
- [x] Fake PTYs by default; `--soak-real-shell` opts into real ones.
      Spawning thousands of shells measures the OS more than it measures
      this app, and the leak-prone half - a QWebEngineView and a Chromium
      render process per terminal - runs either way.

### Phase 4p — Scrollback preference ✅ done
xterm.js defaults to **1000 lines** of scrollback (`scrollback: 1e3` in the
vendored bundle) and `terminal.js` never overrode it, so that was qtxterm's
default by accident rather than by choice. It is now a preference, sitting
next to font size in Preferences.

- [x] Lives on `Appearance`, which is already the object pushed to every
      open terminal on change. Not strictly *appearance* - it is a buffer
      size - but it travels the same two paths as font size (query param on
      load, `applyAppearance()` live) and inventing a second store to carry
      one integer along the identical wires would be worse.
- [x] Passed as a query param, not pushed after load: xterm.js allocates the
      buffer when the Terminal is constructed.
- [x] `0` is a real setting - keep nothing but the screen - and falsy, so
      both the JS default (`|| 1000` would swallow it) and the spin box
      (which shows "None (screen only)") handle it explicitly.
- [x] Clamped to 0..100,000 on load, so a hand-edited ini can't ask xterm.js
      for a negative buffer. Above its MAX_BUFFER_SIZE xterm silently
      clamps, and stopping at a number the user chose beats stopping at one
      they didn't.
- [x] Verified against real xterm.js by writing 2000 lines and measuring the
      viewport's scrollHeight: 0 -> 391px (the screen alone), 100 -> 2091px,
      1000 -> 17391px, 5000 -> 34017px (capped by the 2000 lines written,
      not by the setting). Each is exactly 17px per retained line.

### Phase 4q — Macro step syntax, discoverable ✅ done
Multi-step Macros were only documented in SPEC.md, which is no help to
someone staring at an empty command box.

- [x] "Add step: New Tab | Split Right | Split Down" buttons under the
      command box in Manage Macros, each inserting its separator on a line
      of its own. Inserting mid-line breaks the line first - a separator
      only counts alone on its line, so otherwise the button would look like
      it did nothing.
- [x] The button labels are built from `presets.MACRO_STEP_SEPARATOR` and
      the placement tokens, and a test runs what they insert back through
      `macro_steps()`. The two can't drift into a state where a button emits
      something the parser quietly treats as a plain tab.
- [x] A hint line under them says what `---` does and that a macro without
      one runs in a single tab - the buttons cover the common case, the
      sentence covers the person editing an existing macro by hand.
- [x] Text inputs gained the themed border that lists got in 4n: on a dark
      theme Fusion's frame is invisible, and the macro editor's Name, Group
      and command box read as labels rather than fields. QSpinBox is
      deliberately excluded - styling any part of it hands its painting to
      the style sheet and its arrows come back as one squashed glyph.

### Phase 4r — First real Linux run ✅ done
The README claimed Windows + Linux while `PosixPtySession` had never been
run on Linux. Tested under WSL (Ubuntu 24.04, Python 3.12.3, PySide6 6.11.1,
`QT_QPA_PLATFORM=offscreen`) before wiring up CI. First run: 284 passed, 5
failed. All five are now fixed, and none were bugs in the app's behaviour.

- [x] **The argv contract was only enforced on Linux.** Two tests called
      `start(default_shell(), ...)` with a bare string. `pywinpty` quietly
      shlex-splits that and gets away with it; `ptyprocess` raises. The app
      always passed a list, so only the tests were wrong - but the same
      laxness is why `win.py` carries a comment about paths with spaces.
- [x] `wsl_path` was tested with `Path(r"C:\...")`, which is a *PosixPath*
      on Linux and keeps the backslashes. Now `PureWindowsPath`, so the
      translation is exercised on either OS.
- [x] The offscreen platform ignores resize ("does not support
      propagateSizeHints"), so the window-geometry test cannot observe a
      restore. Skipped when `QT_QPA_PLATFORM=offscreen`, which means CI
      should use xvfb if that test is to count. Note the skip has to read the
      env var: `QGuiApplication.platformName()` at import time reports the
      default it *would* pick ("xcb"), so a skipif on that never fires.
- [x] A ~30% flake on `test_the_warm_up_view_is_discarded_once_loaded`,
      which passed alone and always passed on Windows. It was the victim,
      not the cause: it is the test that sits waiting on the event loop, so
      pytest-qt reported against it the "Signal source has been deleted"
      exceptions that *earlier* tests' teardown left queued. Marked
      `qt_no_exception_capture`; 0 failures in 22 subsequent full-suite runs.
- [x] Tightened the real cause where it was cheap: the reader thread no
      longer emits once `close()` has been called, and `close()` waits
      briefly (0.5s, bounded because it runs on the GUI thread) for the
      thread to finish. Honest note - this did **not** move the flake rate;
      the remaining noise is Qt teardown with async work still in flight,
      and the proper fix is for a widget to stop its page the way
      `BrowserWidget.shutdown()` already does.

### Phase 4s — Cron ✅ done
Run a Macro on a schedule, for as long as the app is open.

Four decisions, each taken over a plausible alternative:

- [x] **A job names a Macro; it does not carry its own commands.** Macros
      already have an editor, and one command living in two places is how the
      two copies drift apart. The cost is a job whose Macro is renamed or
      deleted - handled by reporting it (status bar, and "(missing)" in the
      editor) rather than silently repointing the job at whatever is first in
      the list.
- [x] **Macros only - not Commands, not Selection Actions.** A Command means
      "send this to the terminal I am working in", which a job firing at 2am
      cannot honour: there may be no terminal, or the wrong one. A Selection
      Action needs a live selection a schedule can never provide. Enforced in
      the scheduler as well as the editor, so a hand-edited `cron.json` is
      refused with a reason rather than quietly typing into whatever tab you
      were using.
- [x] **Real cron expressions**, not "every N minutes". Five fields with
      ranges, lists and steps, because it is syntax people already know.
      That includes cron's day rule: with *both* day-of-month and day-of-week
      restricted, a day matching *either* fires. Kept deliberately, since
      schedules copied in from a crontab depend on it.
- [x] **One tab per job, reused.** A five-minute job would otherwise bury the
      tab bar, and the tab's scrollback is exactly that job's history. The tab
      takes the job's name. Close it and the next run opens another.
- [x] **Saved, but the clock restarts at launch.** No catch-up: the minute in
      progress when the app opens never fires, and nothing missed while it
      was closed is replayed. Otherwise launching after a weekend opens a
      burst of terminals before you have touched anything. `cron.json` sits
      next to `presets.json`.

- [x] Jobs carry an optional `group`, nested in the menu exactly as a
      preset's group is - ungrouped first, groups after in name order. A
      trading setup reaches a job per feed per session quickly, which is more
      than a flat list holds. The menu reuses `add_submenu`/`clear_menu` from
      the preset menus rather than growing its own copy of the ownership
      handling those exist for.

Implementation notes:

- `cron.py` is schedules and storage and knows nothing about terminals;
  `cron_scheduler.py` owns the tab-per-job and the firing. Splitting them is
  what let the whole expression layer be tested without a Qt widget.
- The scheduler ticks every second and acts only when the *minute* changes.
  A 60s timer drifts against the wall clock and skips a minute whenever the
  machine sleeps.
- `next_run()` walks minute by minute but skips whole days that cannot match,
  and gives up after four years - "0 0 31 2 *" parses fine and can never
  happen, and the alternative to a bound is a UI that hangs.
- Failures go to the status bar, not a dialog: a job fires on a schedule,
  possibly while you are away, and a modal appearing once a minute over your
  work is the worst available option.
- Verified end to end against a real shell: two firings, one tab named after
  the job, both runs landing in the same terminal.

## Open Questions / Deferred

### Start-up latency — measured, not yet decided
The window takes **~950ms** to appear. Investigated and parked: what remains
is a UX choice, not a missing measurement.

Where it goes, on this machine (Windows, Qt 6.11):

| Phase | Cost |
|---|---|
| Python boot | 41ms |
| Imports (Qt + the app) | ~255ms |
| `QApplication` + icon | ~25ms |
| `MainWindow()` minus the warm-up | ~89ms |
| **`prepare_window()` → Chromium** | **~455ms** |
| `show()` → first paint | ~100ms |

The 455ms is **`view.load("about:blank")`**, not constructing the view
(0.1ms): loading is where QtWebEngine spawns its render process. Chromium
flags (`--disable-gpu`, `--in-process-gpu`, …) make no difference, because
they do not change that the process has to start.

Phase 4k put that load before `show()` so the native-window rebuild happens
off screen. Re-verified on Qt 6.11 and the constraint still holds — and it is
tighter than it looks:

- The rebuild fires on **`load()`**, not on view creation (HWND 6817848 →
  6883384). Cost and rebuild are the same event; neither can be moved alone.
- It is **per window, not per application**. With Chromium fully initialised
  in a separate throwaway top-level window, the main window still rebuilt when
  its own first view arrived (31263386 → 31328922). So deferring the warm-up
  only decides *when* the flash happens, never whether.
- A 1x1 `QOpenGLWidget` added before `show()` does **not** pre-empt it - the
  rebuild still happened, and `QOpenGLWidget` itself pushed the window's
  appearance out to 966ms.

Options, all measured:

| Approach | Window appears | Flash |
|---|---|---|
| Warm up before `show()` (today) | ~950ms | none |
| Warm up right after `show()` | ~180ms | brief, just after start-up |
| Warm up in a throwaway window | ~200ms | moves to the **first terminal** |

The second is the one to take if start-up speed wins: the flicker lands
before the user has done anything, and every later terminal is fast *and*
clean. The third is worse - it defers the flicker to the moment attention is
on the window.

Orthogonal and free of visual cost: the ~255ms of imports, and the ~89ms of
`MainWindow` construction, neither of which has been attacked.

### Stopping a cron job — designed, parked
Cron starts things today and never stops them. The use case that raised it:
stream market data 06:30-13:30 Mon-Fri (equities) and 15:00-14:00 the next
day Sun-Thu (futures). Parked in favour of having the streamer exit on its
own schedule, which is cheaper and cleaner - a process that knows its own
stop time can flush and close properly, and nothing has to reach into a
terminal. Start-only cron already serves that: `30 6 * * 1-5` and
`0 15 * * 0-4`, both verified against the parser.

Recorded because the design work is done and the blocking discovery is real.

**A stop cannot be a separate job.** Each job owns its own tab, so a
"stop equities" job would open a *second* terminal and type into it, leaving
the stream untouched. Stopping has to belong to the job that started it, or
name it explicitly.

**The better model is a window, not two events.** Give one job an optional
stop schedule and the tick stops being edge-triggered and becomes a
reconciliation:

    desired = inside_window(now)
    actual  = this job's tab is open and was started by it
    desired and not actual -> start;  actual and not desired -> stop

Three problems then dissolve without special cases: a missed start (open the
app at 07:05 and it starts, because it is inside the window), a double start
(cannot happen - `actual` is already true), and a missed stop edge while the
machine slept (the next tick reconciles). Note this only makes sense for
windowed jobs; a point-in-time job still cannot sensibly fire late.

**The weak joint is liveness.** We can see that the tab is open; we cannot
see whether the process inside it is alive, so a feed that dies at 09:00
leaves a tab at a prompt and reconciliation believes all is well. The fix is
a fork in the design: run a windowed job's command *as the terminal process*
rather than typing it into a shell. Process exit then is PTY exit, which is
already observable - liveness becomes real, stop becomes killing the PTY
(which works), and restart-on-crash becomes possible. The cost is losing the
shell around it: no profile, no aliases, and the Macro model stops being
"lines typed into a shell".

Shape, if built: `stop_expression`, `stop_action` (interrupt | close),
`stop_grace_seconds` (escalate to close, mirroring `docker stop -t`), and an
opt-in `start_if_inside_window`. Start stays required, stop optional; a job
with no stop is exactly today's behaviour. No visible "advanced" tier - one
job type with optional fields, because two tiers is two things to learn and a
migration when a simple job later needs a window.

### Ctrl-C does not reach child processes on Windows — bug, not yet fixed
Found while designing the above, and **independent of cron**: pressing Ctrl-C
in any qtxterm terminal does not stop a running command on Windows.

`pywinpty`'s `sendintr()` is literally `write("")`, which is what typing
Ctrl-C already does. Measured, spawning `ping -t` and counting replies:

| Backend | child started | after `` | after closing |
|---|---|---|---|
| **ConPTY** (what we use) | running | **still running** | killed |
| WinPTY (legacy) | running | killed | killed |

At an idle prompt the shell echoes `^C`, which makes it look like it worked;
a running child never sees it. Closing the terminal kills the process under
both backends, so that is the only stop that currently works.

Three ways out:

1. `GenerateConsoleCtrlEvent` - attach to the child console, raise
   CTRL_C_EVENT, detach. The correct mechanism, and it fixes interactive
   Ctrl-C too. Our own process must ignore the event first or it takes the
   app down with it.
2. Switch to the WinPTY backend - works immediately, but it is the
   deprecated emulation layer with an extra agent process and worse
   fidelity. Bad trade for the terminal's quality.
3. Leave it, and stop things by closing the tab.

Preferred: 1. Linux is unaffected - a real SIGINT to the foreground process
group is straightforward there, and untested only because the bug is
Windows-specific.

### Stable `Preset.id` — proposed, low priority, not implemented
Give every preset an `id: str` (uuid4 hex), assigned in `__post_init__` when
absent, and key `PresetStore.update()`/`delete()` off it instead of list
position. One namespace across all three categories, since they share one
dataclass and one `presets.json`.

**This is future-proofing, not a bug fix.** Nothing here is reproducible
through normal use today:

- **Index is not identity — latent, not live.** `update(index, preset)` /
  `delete(index)` key off list position, and `PresetEditorDialog` holds a
  store index (`_current_index`) across reloads. That is safe only because
  the editor is modal (`dialog.exec()`) and there is one window per process,
  so nothing can reorder the list underneath it. The invariant holds by
  circumstance rather than by construction, which is the actual objection.
  The one case that breaks now is **two app instances**: both hold the whole
  list in memory and rewrite the entire file on save, so the later save
  clobbers the earlier. An id alone would not fix that — it needs
  merge-on-write — but it turns "lost an edit" into "edited the right
  preset".
- **Value equality is not identity — already worked around.** `Preset` is a
  plain dataclass, so two presets with identical fields compare equal. This
  bit `_indexed_presets()`, where `preset in filtered_list` matched the wrong
  entry; it was rewritten to compare by category. Fixed instance, same class
  of problem.
- **Name is not identity — only matters if references appear.** Names aren't
  unique, and the `SidebarLayout` sketch above refers to presets by name
  (`preset_refs: list[str]`), so a rename would orphan its button. This is
  the real trigger, and it only fires once something *outside* `presets.json`
  points at a preset.

**Current status: no such references exist.** Buttons are `show_in_sidebar`,
a field on the preset itself (see the split rationale above), so nothing
stores a handle to a preset. That removes the main argument for doing this
now. Even the lighter version of sidebar arrangement — an `order` field on
the preset — needs no ids.

Do it **before**, not after, if any of these land: a separate
`sidebar_layout.json`, per-preset keyboard bindings, recently-used tracking,
or anything else referencing a preset from elsewhere. Retrofitting then means
migrating the references as well as the presets. Otherwise it can wait
indefinitely.

Migration is additive whenever it happens: entries without an `id` get one on
load and the file is saved once. Existing `presets.json` files keep working
and stay hand-editable.

- Multi-step macro *scripting* (wait-for-pattern, conditional branching) —
  deferred; would mean either running presets as a real temp script file (true
  script semantics, but a subshell, so `cd` wouldn't persist) or Expect-style
  prompt detection.
- Session persistence across app restarts (reopen tabs) — not yet decided.
- Config file format: JSON assumed above; can switch to YAML/TOML if preferred.
