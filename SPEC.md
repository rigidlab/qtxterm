# mterm — Cross-Platform GUI Terminal (PySide6 + xterm.js)

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
| PTY backend | `pywinpty` (ConPTY) on Windows, `ptyprocess` (openpty) on Linux, behind a common `PtySession` wrapper interface |
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
- [x] Tab labels: tmux-style `"{index}:{title}"`, live-updated from the shell's OSC title sequence (`xterm.js onTitleChange` -> bridge), renumbered on add/close/reorder
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

### Phase 5 — Packaging & polish
- Sidebar "Edit Layout" mode (drag reorder, section management) - deferred here
  from Phase 3/4 twice now; revisit once real usage shows it's actually needed
- PyInstaller specs (Windows `.exe`, Linux binary/AppImage)
- App icon, settings persistence (last window size, default shell), themes (xterm.js theme presets)

## Open Questions / Deferred
- Multi-step macro *scripting* (delays, wait-for-pattern) — deferred past v1 per earlier decision; current model only supports "send lines in sequence" with no conditional waiting.
- Session persistence across app restarts (reopen tabs) — not yet decided.
- Config file format: JSON assumed above; can switch to YAML/TOML if preferred.
