"""The usage guide, checked against the app rather than proofread.

Two kinds of rot this catches. Documented shortcuts drifting from the ones
actually bound is the obvious one. The subtler one is markdown that looks
right in the file and renders wrong in Help -> Usage: the guide is shown
through QTextBrowser.setMarkdown, whose escaping rules are not GitHub's, so
the file being correct is not evidence that the dialog is.
"""

from __future__ import annotations

import pathlib

import pytest

from qtxterm import shortcuts
from qtxterm.help_dialog import USAGE_PATH, HelpDialog

# Shortcuts a user would reasonably expect to find in the guide. Pane focus
# and the tab-number slots are covered by prose rather than every literal
# chord, so they are not listed here.
DOCUMENTED_ACTIONS = [
    shortcuts.NEW_TAB,
    shortcuts.CLOSE_TAB,
    shortcuts.NEXT_TAB,
    shortcuts.FIND,
    shortcuts.COPY,
    shortcuts.PASTE,
    shortcuts.ZOOM_IN,
    shortcuts.ZOOM_OUT,
    shortcuts.ZOOM_RESET,
    shortcuts.SPLIT_RIGHT,
    shortcuts.SPLIT_DOWN,
    shortcuts.CLOSE_PANE,
]


@pytest.fixture(scope="module")
def source() -> str:
    return USAGE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def rendered(qtbot) -> str:
    """What the Help -> Usage dialog actually puts on screen."""
    dialog = HelpDialog()
    qtbot.addWidget(dialog)
    return dialog.browser.toPlainText()


@pytest.mark.parametrize("action", DOCUMENTED_ACTIONS)
def test_every_documented_action_is_in_the_guide(action, source) -> None:
    """Catches a shortcut changed in the code and left stale in the docs -
    which is exactly how the guide came to advertise chords that could not
    fire from a keyboard.

    Matched against the *displayed* names, not Qt's. On macOS the two differ:
    Qt calls the binding "Ctrl+T" and the guide correctly calls it "Cmd+T",
    so comparing Qt's spelling failed this test on macOS CI while both the
    code and the guide were right.
    """
    shown = shortcuts.display_sequences_for(action)

    assert any(sequence in source for sequence in shown), (action, shown)


def test_the_guide_renders_without_escaping_artefacts(rendered) -> None:
    r"""A literal pipe ends a markdown table cell, and every way of escaping
    it that Qt accepts leaves something on screen: `\|` keeps its backslash
    and `&#124;` renders as the raw entity. The pipe shortcuts therefore live
    in a list, where no escaping is needed at all.
    """
    assert r"\|" not in rendered
    assert "&#" not in rendered


def test_the_guide_uses_plain_dashes(source) -> None:
    """Matching SPEC.md and README.md, which carry none."""
    assert "\u2014" not in source


def test_the_split_chords_survive_rendering(rendered) -> None:
    """The pipe is the one character this document cannot put in a table."""
    assert "Ctrl+Shift+|" in rendered
    assert "Ctrl+Shift+_" in rendered


def test_the_guide_lists_a_config_path_for_every_supported_platform(source) -> None:
    """The app runs on all three and stores its files via platformdirs, so
    naming only two leaves Mac users with nothing to look for."""
    for marker in (
        "%LOCALAPPDATA%",
        "~/Library/Application Support/qtxterm",
        "~/.config/qtxterm",
    ):
        assert marker in source, marker


def test_the_guide_covers_macos_shortcuts(source) -> None:
    """The two platforms differ by more than a find-and-replace, so the
    guide has to say so rather than quoting only the Windows chords."""
    assert "macOS" in source
    assert "Cmd+T" in source
    assert "Cmd+C" in source


def test_usage_ships_beside_the_package(source) -> None:
    assert USAGE_PATH.is_file()
    assert USAGE_PATH.parent.name == "assets"
    assert pathlib.Path(USAGE_PATH).suffix == ".md"
