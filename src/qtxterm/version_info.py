"""Where the running code came from, for the About dialog.

The packaged version alone cannot answer "which build am I looking at?" -
`pyproject.toml` carries a static version that only moves on a release, so
every commit between two releases reports the same string. An editable
install makes that worse: the code is read live from a checkout, so the
version is fixed while the code underneath it changes with every branch
switch.

Git knows the answer and is right there in a checkout, so ask it, and fall
back to the packaged metadata when it is not - an installed wheel has no
`.git`, and a user machine may have no `git` at all.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent

# src/qtxterm -> src -> repo root. Absent from an installed wheel, which is
# exactly the signal that this is not a development build.
REPO_ROOT = PACKAGE_DIR.parent.parent

# Git is normally instant, but it takes locks and can block on a busy repo.
# The About dialog is not worth hanging the UI for, so cap the wait and
# degrade to the packaged version instead.
GIT_TIMEOUT_SECONDS = 2.0

UNKNOWN_VERSION = "unknown"


@dataclass(frozen=True)
class BuildInfo:
    """Identity of the running build, however much of it could be determined."""

    version: str
    describe: str | None = None
    commit_datetime: datetime | None = None
    source: Path | None = None
    installed_datetime: datetime | None = None

    @property
    def is_development(self) -> bool:
        """Whether this is running from a checkout rather than an installed copy."""
        return self.describe is not None


def _run_git(*args: str) -> str | None:
    """Run a git command in the repo, or return None if git cannot answer.

    Covers the three ways this fails in the wild: no git on PATH
    (FileNotFoundError), no repository to read (non-zero exit), and a repo
    that does not answer promptly (TimeoutExpired).
    """
    if not (REPO_ROOT / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def packaged_version() -> str:
    """The version recorded at install time, or a placeholder if unreadable."""
    try:
        return version("qtxterm")
    except PackageNotFoundError:
        return UNKNOWN_VERSION


def _commit_datetime() -> datetime | None:
    raw = _run_git("log", "-1", "--format=%cI")
    if raw is None:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _installed_datetime() -> datetime | None:
    """When the package landed on disk.

    The package directory's mtime is written when the wheel is unpacked, so
    for an installed copy it dates the install. It is meaningless for an
    editable install, where the directory is the checkout - hence only used
    when git found nothing.
    """
    try:
        stamp = PACKAGE_DIR.stat().st_mtime
    except OSError:
        return None
    # Read as UTC then converted to local, so the result is timezone-aware
    # and prints an offset like the git commit date does.
    return datetime.fromtimestamp(stamp, tz=UTC).astimezone()


@cache
def build_info() -> BuildInfo:
    """Identify the running build. Cached - the answer cannot change mid-run."""
    describe = _run_git("describe", "--always", "--dirty", "--tags")
    if describe is None:
        return BuildInfo(
            version=packaged_version(),
            installed_datetime=_installed_datetime(),
        )
    return BuildInfo(
        version=packaged_version(),
        describe=describe,
        commit_datetime=_commit_datetime(),
        source=REPO_ROOT,
    )


def _format(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S %z").strip()


def version_lines(info: BuildInfo | None = None) -> list[str]:
    """The About dialog's text, one line per fact that could be determined."""
    info = info if info is not None else build_info()
    lines = [f"qtxterm {info.version}"]
    if info.describe:
        lines.append(info.describe)
    if info.commit_datetime:
        lines.append(f"commit    {_format(info.commit_datetime)}")
    if info.installed_datetime:
        lines.append(f"installed {_format(info.installed_datetime)}")
    if info.source:
        lines.append(f"source    {info.source}")
    return lines


def version_string(info: BuildInfo | None = None) -> str:
    """The About dialog's text as one block, also what Copy puts on the clipboard."""
    return "\n".join(version_lines(info))
