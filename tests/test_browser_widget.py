"""BrowserWidget: address bar input handling and tab-facing contract."""

from __future__ import annotations

from PySide6.QtCore import QUrl

from qtxterm.browser_widget import SEARCH_URL, BrowserWidget, normalize_url


def test_full_urls_are_left_alone() -> None:
    for text in (
        "https://example.com/a?b=c",
        "http://example.com",
        "file:///C:/tmp/x.html",
        "about:blank",
    ):
        assert normalize_url(text) == text


def test_bare_hosts_get_https() -> None:
    assert normalize_url("example.com") == "https://example.com"
    assert normalize_url("example.com/path") == "https://example.com/path"
    assert normalize_url("  example.com  ") == "https://example.com"


def test_localhost_is_treated_as_a_host_despite_having_no_dot() -> None:
    assert normalize_url("localhost") == "https://localhost"
    assert normalize_url("localhost:8080") == "https://localhost:8080"


def test_words_become_a_search_rather_than_a_broken_url() -> None:
    """https://hello%20world is never what someone meant by typing words."""
    assert normalize_url("hello world") == SEARCH_URL.format(query="hello%20world")
    assert normalize_url("qtwebengine") == SEARCH_URL.format(query="qtwebengine")


def test_empty_input_navigates_nowhere() -> None:
    assert normalize_url("") == ""
    assert normalize_url("   ") == ""


def test_scheme_detection_is_case_insensitive() -> None:
    assert normalize_url("HTTPS://Example.com") == "HTTPS://Example.com"


def test_address_bar_follows_navigation(qtbot) -> None:
    """The bar has to track links clicked in the page and redirects, not
    only what was typed into it."""
    widget = BrowserWidget(url="about:blank")
    qtbot.addWidget(widget)

    with qtbot.waitSignal(widget.host_changed, timeout=2000) as blocker:
        widget._view.urlChanged.emit(QUrl("https://example.com/page"))

    assert widget._address.text() == "https://example.com/page"
    assert blocker.args == ["example.com"]


def test_typing_in_the_address_bar_loads_it(qtbot) -> None:
    widget = BrowserWidget(url="about:blank")
    qtbot.addWidget(widget)
    loaded = []
    widget._view.load = lambda url: loaded.append(url.toString())

    widget._address.setText("example.com")
    widget._address.returnPressed.emit()

    assert loaded == ["https://example.com"]


def test_widget_offers_the_contract_the_tab_widget_expects(qtbot) -> None:
    """close_tab_at()/_apply_appearance_to_all_tabs() call these on every tab."""
    widget = BrowserWidget(url="about:blank")
    qtbot.addWidget(widget)

    assert widget.default_title == "browser"
    widget.apply_appearance(None)
    widget.shutdown()
