"""Command-line options for the soak test.

At the repo root, not in tests/, because pytest parses the command line
before it loads conftest files under testpaths - an option declared down
there is "unrecognized" depending on what else is on the line.
"""

from __future__ import annotations


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--soak-minutes",
        type=float,
        default=0.0,
        help="Run the soak test for this many minutes instead of a fixed "
        "number of cycles (e.g. 1440 for 24 hours).",
    )
    parser.addoption(
        "--soak-csv",
        default="",
        help="Write the soak test's per-cycle samples to this CSV. Worth "
        "doing on a long run: the shape of the curve says far more than the "
        "pass/fail does.",
    )
    parser.addoption(
        "--soak-real-shell",
        action="store_true",
        help="Soak with real PTYs instead of fakes. Slower, and measures the "
        "OS as much as the app, but covers shell process cleanup.",
    )
