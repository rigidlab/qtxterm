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
  - `PosixPtySession` using `ptyprocess` (implemented, not yet verified on Linux)
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

## Open Questions / Deferred

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
