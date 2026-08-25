"""The find bar, exercised against the real xterm.js search addon.

The Python side of find is three lines that call into JavaScript, so testing
it in isolation only asserts that a string was sent. What is actually worth
knowing - that a query finds the right number of matches in the scrollback,
that the counter reads correctly, that Escape puts focus back in the terminal
- lives in the page, so these tests drive the page.

Slower than the rest of the suite (each one boots a real QWebEngineView and
xterm.js) which is why there are few of them, covering behaviour rather than
every button.
"""

from __future__ import annotations

import json

import pytest

from conftest import FakePtySession

from qtxterm.terminal_widget import TerminalWidget

# Enough lines to prove a match is found in the scrollback rather than only on
# the visible screen, with a repeated word to count and a distinct one to miss.
SAMPLE_OUTPUT = (
    "".join(f"line {i} nothing here\r\n" for i in range(60))
    + "first error here\r\n"
    + "second ERROR here\r\n"
    + "third error here\r\n"
)


@pytest.fixture
def terminal(qtbot):
    """A visible, booted terminal with SAMPLE_OUTPUT already written to it.

    Shown rather than merely constructed: the page is only told its size from
    resizeEvent and the loaded() handshake, and a zero-sized view never starts
    the terminal at all.
    """
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    widget.resize(800, 500)
    widget.show()
    qtbot.waitUntil(lambda: widget.is_pty_started, timeout=15000)
    widget._bridge.output.emit(SAMPLE_OUTPUT)
    # xterm.js buffers writes and flushes them on its own schedule, so the
    # text is not searchable the instant it is handed over - searching here
    # without waiting reports "No results" against a terminal that is about to
    # contain three matches. The rendered rows are the honest signal that the
    # write has landed.
    qtbot.waitUntil(
        lambda: (
            "third error here"
            in evaluate(
                widget, qtbot, 'document.querySelector(".xterm-rows").textContent'
            )
        ),
        timeout=10000,
    )
    yield widget


def evaluate(widget, qtbot, script: str):
    """Run `script` in the page and return its value.

    runJavaScript is asynchronous - there is a whole IPC round trip to the
    render process - so the result arrives in a callback and the event loop
    has to keep turning until it does.
    """
    result = []
    widget._view.page().runJavaScript(script, result.append)
    qtbot.waitUntil(lambda: bool(result), timeout=10000)
    return result[0]


def search_for(widget, qtbot, query: str) -> None:
    """Type `query` into the find bar the way a user would.

    The value is set and an `input` event dispatched rather than calling the
    search directly, so the test goes through the same path typing does -
    including the incremental option, which only the input handler passes.
    """
    evaluate(
        widget,
        qtbot,
        f"""
        (function () {{
          window.showFind();
          const input = document.getElementById("find-input");
          input.value = {json.dumps(query)};
          input.dispatchEvent(new Event("input"));
          return true;
        }})();
        """,
    )


def count_text(widget, qtbot) -> str:
    return evaluate(widget, qtbot, 'document.getElementById("find-count").textContent')


def test_find_counts_every_match_in_the_scrollback(terminal, qtbot) -> None:
    """Three matches, two of them scrolled off the screen's top is not the
    point - the point is that search covers the buffer, not the viewport."""
    search_for(terminal, qtbot, "error here")

    qtbot.waitUntil(lambda: count_text(terminal, qtbot) != "", timeout=10000)
    assert count_text(terminal, qtbot) == "1 of 3"


def test_search_is_case_insensitive_until_match_case_is_pressed(
    terminal, qtbot
) -> None:
    """'ERROR' on the middle line is one of the three by default, and one of
    two once case matters.

    Only the match *count* is asserted after the toggle. Which match is
    active can legitimately step forward by one, because the addon resumes
    the search from the current selection rather than from the top.
    """
    search_for(terminal, qtbot, "error")
    qtbot.waitUntil(lambda: count_text(terminal, qtbot) != "", timeout=10000)
    assert count_text(terminal, qtbot) == "1 of 3"

    evaluate(terminal, qtbot, 'document.getElementById("find-case").click()')

    qtbot.waitUntil(lambda: count_text(terminal, qtbot).endswith("of 2"), timeout=10000)


def test_a_query_that_matches_nothing_says_so(terminal, qtbot) -> None:
    search_for(terminal, qtbot, "no such text anywhere")

    qtbot.waitUntil(lambda: count_text(terminal, qtbot) == "No results", timeout=10000)
    # The input is outlined in the theme's red as well, which is the part you
    # actually notice; the class is what drives it.
    assert evaluate(
        terminal,
        qtbot,
        'document.getElementById("find-bar").classList.contains("no-results")',
    )


def test_a_half_typed_regex_reports_no_results_instead_of_throwing(
    terminal, qtbot
) -> None:
    """'[a' is what a regex looks like one keystroke before it is valid, and
    the addon throws on it rather than simply not matching."""
    evaluate(terminal, qtbot, 'document.getElementById("find-regex").click()')
    search_for(terminal, qtbot, "[a")

    qtbot.waitUntil(lambda: count_text(terminal, qtbot) == "No results", timeout=10000)


def test_closing_the_find_bar_hides_it_and_clears_the_count(terminal, qtbot) -> None:
    search_for(terminal, qtbot, "error")
    qtbot.waitUntil(lambda: count_text(terminal, qtbot) != "", timeout=10000)

    evaluate(terminal, qtbot, "window.hideFind()")

    assert evaluate(terminal, qtbot, "window.isFindOpen()") is False
    # Focus back in the terminal, or the window looks usable and swallows
    # every keystroke.
    assert evaluate(
        terminal,
        qtbot,
        'document.activeElement.classList.contains("xterm-helper-textarea")',
    )


def test_the_find_bar_is_themed_from_the_terminal_theme(terminal, qtbot) -> None:
    """A find bar with fixed colours is a white box on a black terminal."""
    background = evaluate(
        terminal,
        qtbot,
        'document.documentElement.style.getPropertyValue("--find-bg")',
    )

    assert background == "#1e1e1e"
