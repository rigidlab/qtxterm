# qtxterm

[![CI](https://github.com/rigidlab/qtxterm/actions/workflows/ci.yml/badge.svg)](https://github.com/rigidlab/qtxterm/actions/workflows/ci.yml)

A cross-platform tabbed terminal (Windows, Linux, macOS) built with PySide6,
rendering terminals via embedded [xterm.js](https://xtermjs.org/) in a
`QWebEngineView`, backed by real PTYs - ConPTY on Windows, `openpty` elsewhere.

![qtxterm](docs/screenshot.png)

*One macro produced that layout: a tab split three ways, each pane running its
own command. Shown in the default theme - several dark themes ship with it.*

## Features

- **Tabs and split panes** - split any pane right or down, move panes between
  tabs or out into their own.
- **Any shell on the box** - PowerShell, Command Prompt, Git Bash or a specific
  WSL distro, discovered at runtime.
- **Commands and Macros** - saved one-liners sent to the terminal you're in;
  macros that open their own tabs *and* panes.
- **Cron** - run a macro on a schedule for as long as the app is open.
- **Selection Actions** - search or pipe selected text, without interpolating it
  into a shell line.
- **Browser tabs and panes** - a page beside a terminal.
- **Themes and typography** - applied to the terminal *and* the window chrome,
  plus font, size and scrollback.

Each is covered in [Usage](src/qtxterm/assets/USAGE.md).

## Install
Needs [uv](https://docs.astral.sh/uv/) and Python 3.12+ (uv fetches it). No
clone needed - uv builds and installs straight from here:

```bash
uv tool install git+https://github.com/rigidlab/qtxterm.git
qtxterm
```

That installs two commands: **`qtxterm`** (console, so it prints where you ran it from) and **`qtxtermw`** (no console window - what a desktop shortcut should point at). On Windows, `scripts/install-shortcut.ps1` creates Desktop and Start Menu shortcuts with the app icon.

## Usage
The full guide is in the app under **Help → Usage**, or read [`src/qtxterm/assets/USAGE.md`](src/qtxterm/assets/USAGE.md).

## Development
### Run from source

```bash
git clone https://github.com/rigidlab/qtxterm.git
cd qtxterm
uv sync
uv run qtxterm
```

To build (if needed):
```bash
uv build
uv tool install dist/qtxterm-1.0.0-py3-none-any.whl  # replace version
```

### Making a change
```bash
git checkout main && git pull
git checkout -b feat/change-123   # feat|fix|docs|chore|refactor|test|perf
```

One logical change per commit, and add or update tests as you go.

### Test locally
```bash
uv run pytest            # ~340 tests, about 15 seconds
uv run ruff check src/
uv run ruff format src/  # CI runs --check; both cover src/ only
```

The soak test is excluded from that run and from CI because it takes minutes.
Run `uv run pytest -m soak` (~90s) if you touched anything owning a widget, a
timer or a PTY.

### Open a PR
```bash
git add <files>          # not `git add .`
git commit -m "feat: implement change 123"
git push -u origin feat/change-123
```

Open the PR on GitHub and say what changed and why - a screenshot saves a round
trip for anything visual. CI then runs the checks above on Windows, Linux and
macOS, and builds the wheel.

### After CI passes
Green and approved, the PR is merged from the GitHub UI - merge, squash or
rebase, whichever suits the change. Then delete the branch and `git checkout
main && git pull` before starting the next one.

Merging is itself a push to `main`, so CI runs once more on the result. That
run is the one that catches a PR which was green against a stale base and
broke against what landed in the meantime - worth a glance before you move on.

Releases are cut by tag, and only by a maintainer:

```bash
# bump `version` in pyproject.toml first, on main
git tag v1.1.0 && git push origin v1.1.0
```

That builds the wheel, checks the tag and the package version agree, installs
it into a clean venv on Linux and Windows and runs the app from it, and only
then publishes a GitHub Release with the artifacts attached. A failing smoke
test leaves the tag in git but publishes nothing.

### Where things live

| Path (under `src/qtxterm/`) | What |
|---|---|
| `terminal_widget.py` | one terminal: xterm.js in a web view, wired to a PTY |
| `terminal_tabs.py` | tabs, split panes, what runs where |
| `pty_backend/` | ConPTY on Windows, `openpty` elsewhere |
| `presets.py`, `cron*.py` | Commands/Macros/Selection Actions, and schedules |
| `assets/` | `terminal.html`/`terminal.js`, vendored xterm.js |

## License

MIT - see [`LICENSE`](LICENSE). Vendored xterm.js is MIT as well, with its notice
alongside the code it covers in
[`src/qtxterm/assets/xterm/LICENSE`](src/qtxterm/assets/xterm/LICENSE).
