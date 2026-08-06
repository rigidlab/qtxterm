# qtxterm

A cross-platform tabbed terminal (Windows + Linux) built with PySide6, rendering
terminals via embedded xterm.js and backed by real PTYs.

- Multiple terminal tabs with tmux-style labels that track the shell's title
- On Windows, open PowerShell, Command Prompt, Git Bash, or WSL from **File → New Terminal**
- **Commands** — reusable one-liners, sent to the terminal you're working in,
  as one-click sidebar buttons
- **Macros** — multi-step scripts that open and run in a fresh tab

## Install and run

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run qtxterm
```

## Usage

The full usage guide is in the app under **Help → Usage**, or read
[`src/qtxterm/assets/USAGE.md`](src/qtxterm/assets/USAGE.md).

## Development

```bash
uv run pytest
```

Design decisions and the phased build plan are in [`SPEC.md`](SPEC.md).
