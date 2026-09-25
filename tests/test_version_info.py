"""Build identification, including the paths where git cannot answer."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime

import pytest

from qtxterm import version_info
from qtxterm.version_info import BuildInfo, version_lines, version_string


@pytest.fixture(autouse=True)
def _clear_cache():
    """build_info() is cached for the process; tests need it recomputed."""
    version_info.build_info.cache_clear()
    yield
    version_info.build_info.cache_clear()


def test_development_build_reports_git_description() -> None:
    """The repo under test is a checkout, so git should answer."""
    info = version_info.build_info()

    assert info.is_development
    assert info.describe
    assert info.source == version_info.REPO_ROOT
    assert info.commit_datetime is not None


def test_missing_git_falls_back_to_packaged_metadata(monkeypatch) -> None:
    """An installed wheel has no .git, and a user machine may have no git."""
    monkeypatch.setattr(version_info, "_run_git", lambda *args: None)

    info = version_info.build_info()

    assert not info.is_development
    assert info.describe is None
    assert info.version == version_info.packaged_version()
    assert info.installed_datetime is not None


def test_git_timeout_is_not_fatal(monkeypatch) -> None:
    """A slow repo must degrade, not hang the About dialog."""

    def _hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=2.0)

    monkeypatch.setattr(subprocess, "run", _hang)

    assert version_info._run_git("describe") is None


def test_missing_git_binary_is_not_fatal(monkeypatch) -> None:
    def _absent(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", _absent)

    assert version_info._run_git("describe") is None


def test_non_zero_exit_returns_none(monkeypatch) -> None:
    """Outside a repository git exits non-zero rather than raising."""

    def _fail(*args, **kwargs):
        return subprocess.CompletedProcess(args=["git"], returncode=128, stdout="")

    monkeypatch.setattr(subprocess, "run", _fail)

    assert version_info._run_git("describe") is None


def test_version_lines_for_a_development_build() -> None:
    info = BuildInfo(
        version="1.0.0",
        describe="v1.0.0-21-gd4bd495",
        commit_datetime=datetime(2026, 9, 20, 21, 41, 22, tzinfo=UTC),
        source=version_info.REPO_ROOT,
    )

    lines = version_lines(info)

    assert lines[0] == "qtxterm 1.0.0"
    assert lines[1] == "v1.0.0-21-gd4bd495"
    assert any(line.startswith("commit") for line in lines)
    assert any(line.startswith("source") for line in lines)
    assert not any(line.startswith("installed") for line in lines)


def test_version_lines_for_an_installed_build() -> None:
    """No commit or source line when there is no checkout to report."""
    info = BuildInfo(
        version="1.0.0",
        installed_datetime=datetime(2026, 9, 20, 15, 5, tzinfo=UTC),
    )

    lines = version_lines(info)

    assert lines[0] == "qtxterm 1.0.0"
    assert any(line.startswith("installed") for line in lines)
    assert not any(line.startswith("commit") for line in lines)


def test_version_string_joins_the_lines() -> None:
    info = BuildInfo(version="1.0.0", describe="abc1234")

    assert version_string(info) == "qtxterm 1.0.0\nabc1234"
