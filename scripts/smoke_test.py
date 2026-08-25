"""Smoke-test an *installed* qtxterm, not the source tree.

The test suite runs against `src/`, so it cannot see anything that goes wrong
between the source and the wheel: an asset excluded by the build backend, a
missing entry point, a package that imports but cannot start. Those only
surface once someone installs it - which is the last moment you want to find
out.

Run it inside an environment where the wheel is installed:

    uv venv .smoke
    uv pip install --python .smoke --find-links dist qtxterm
    uv run --no-project --python .smoke python scripts/smoke_test.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Loaded at runtime from the installed package, so their absence is a broken
# install rather than a failing test.
REQUIRED_ASSETS = [
    "assets/terminal.html",
    "assets/terminal.js",
    "assets/xterm/xterm.js",
    "assets/xterm/xterm.css",
    "assets/xterm/addon-fit.js",
    "assets/xterm/addon-search.js",
    "assets/xterm/addon-web-links.js",
    "assets/USAGE.md",
    "assets/logo.ico",
]

# Long enough that a crash on start-up has happened by the time we look -
# Chromium's first launch is the slow part - and short enough to keep a
# release quick.
ALIVE_SECONDS = 12


def fail(message: str) -> None:
    print(f"SMOKE FAIL: {message}", file=sys.stderr)
    sys.exit(1)


def check_assets() -> Path:
    try:
        import qtxterm
    except ImportError as exc:  # pragma: no cover - the point of the check
        fail(f"the installed package does not import: {exc}")

    package = Path(qtxterm.__file__).parent
    missing = [name for name in REQUIRED_ASSETS if not (package / name).is_file()]
    if missing:
        fail(f"installed package is missing {missing} (built from {package})")
    print(f"assets present in {package}")
    return package


def check_entry_points() -> str:
    console = shutil.which("qtxterm")
    if console is None:
        fail("the 'qtxterm' entry point is not on PATH in this environment")
    if shutil.which("qtxtermw") is None:
        fail("the 'qtxtermw' entry point is not on PATH in this environment")
    print(f"entry points resolve: {console}")
    return console


def check_it_starts(console: str) -> None:
    """Launch the real command and require it to still be running.

    Not "exits 0": a terminal that exits on its own has crashed. Staying up
    is the pass condition, so this asserts the process is alive after a
    grace period and then stops it.
    """
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")

    process = subprocess.Popen(
        [console],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(ALIVE_SECONDS)

    if process.poll() is not None:
        output = process.stdout.read() if process.stdout else ""
        fail(
            f"the app exited on its own with code {process.returncode} "
            f"within {ALIVE_SECONDS}s:\n{output}"
        )

    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        fail("the app ignored terminate() and had to be killed")

    print(f"started and stayed up for {ALIVE_SECONDS}s, then stopped on request")


def main() -> None:
    check_assets()
    console = check_entry_points()
    check_it_starts(console)
    print("SMOKE OK")


if __name__ == "__main__":
    main()
