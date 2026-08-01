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

Commands and macros are the same underlying object, viewed two ways:

```yaml
Preset:
  name: str
  group: str                       # optional, for menu/sidebar section organization
  lines: list[str]                 # one or more shell lines
  target: active | new_tab         # default: active if len(lines)==1 else new_tab
  show_in_sidebar: bool            # opt-in to sidebar button
```

Stored as a single JSON/YAML file (e.g. `~/.config/mterm/presets.json` on Linux,
`%APPDATA%/mterm/presets.json` on Windows).

- **Commands sidebar**: shows presets with `show_in_sidebar: true`. One-click
  sends `lines` to the currently active terminal tab. Fast, always visible.
- **Macros menu** (dropdown, grouped by `group`): full preset list, with
  Run / Edit / New / Delete. Presets with `target: new_tab` open a fresh tab,
  spawn a PTY, and feed `lines` into it in sequence.

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

### Phase 1 — Single-tab terminal (current target)
Goal: prove the core rendering + I/O loop works cross-platform before any
tabs/macros/sidebar complexity.

- [ ] `uv init` project, add deps: `PySide6`, `PySide6-Addons` (WebEngine), `pywinpty` (win only), `ptyprocess` (posix only)
- [ ] Vendor xterm.js + addon-fit into `assets/xterm/`
- [ ] `PtySession` abstract wrapper: `start(shell, cols, rows)`, `write(data)`, `resize(cols, rows)`, `on_output` callback, `close()`
  - `WinPtySession` using `pywinpty`
  - `PosixPtySession` using `ptyprocess`
- [ ] `TerminalWidget(QWidget)`: hosts `QWebEngineView` loading local `terminal.html`, wires `QWebChannel` object (`TerminalBridge`) exposing `write_to_pty(str)` (JS->Py) and a Py->JS signal for PTY output
- [ ] `terminal.html`/`terminal.js`: init xterm.js + fit addon, pipe keystrokes to bridge, render incoming PTY output, handle resize -> notify bridge
- [ ] `MainWindow(QMainWindow)`: single `TerminalWidget` as central widget, spawns default shell (`$SHELL` on Linux, `powershell.exe` on Windows) on startup
- [ ] Verify: shell prompt renders, keyboard I/O works, resizing the window resizes the PTY, full-screen apps (`vim`, `htop`/`btop`) render correctly, process exit closes cleanly

**Definition of done for Phase 1**: one window, one working real terminal, on both Windows and Linux, no crashes on resize/exit.

### Phase 2 — Tabs
- `QTabWidget` central widget, each tab = one `TerminalWidget` + `PtySession`
- New tab (button/shortcut), close tab (button/Ctrl+W, kill PTY on close), rename tab, switch tabs
- Track "active terminal" reference for later command/macro targeting

### Phase 3 — Command Presets + Sidebar
- `Preset` model + JSON persistence (`presets.json`)
- Sidebar dock widget rendering buttons per `SidebarLayout`
- Click -> write `lines` to active terminal's PTY
- Basic preset editor dialog (add/edit/delete, set `show_in_sidebar`)

### Phase 4 — Macros menu + new-tab execution
- Macros menu (grouped dropdown) listing all presets
- `target: new_tab` execution: open tab, spawn PTY, feed lines sequentially
- Sidebar "Edit Layout" mode (drag reorder, section management)

### Phase 5 — Packaging & polish
- PyInstaller specs (Windows `.exe`, Linux binary/AppImage)
- App icon, settings persistence (last window size, default shell), themes (xterm.js theme presets)

## Open Questions / Deferred
- Multi-step macro *scripting* (delays, wait-for-pattern) — deferred past v1 per earlier decision; current model only supports "send lines in sequence" with no conditional waiting.
- Session persistence across app restarts (reopen tabs) — not yet decided.
- Config file format: JSON assumed above; can switch to YAML/TOML if preferred.
