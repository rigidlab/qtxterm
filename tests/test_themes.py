"""Theme presets: registry consistency and xterm.js dict shape."""

from __future__ import annotations

from qtxterm.themes import QT_DEFAULT, THEMES, default_theme_name

_EXPECTED_XTERM_KEYS = {
    "background",
    "foreground",
    "cursor",
    "selectionBackground",
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "white",
    "brightBlack",
    "brightRed",
    "brightGreen",
    "brightYellow",
    "brightBlue",
    "brightMagenta",
    "brightCyan",
    "brightWhite",
}


def test_default_theme_name_is_qt_default() -> None:
    assert default_theme_name() == "Qt Default"
    assert THEMES[default_theme_name()] is QT_DEFAULT


def test_registry_includes_expected_presets() -> None:
    assert set(THEMES) == {
        "Qt Default",
        "VS Code Dark+",
        "VS Code Light+",
        "Solarized Dark",
        "Solarized Light",
    }


def test_every_theme_serializes_to_full_xterm_dict() -> None:
    for theme in THEMES.values():
        assert set(theme.to_xterm_dict()) == _EXPECTED_XTERM_KEYS


def test_theme_colors_are_hex_strings() -> None:
    for theme in THEMES.values():
        for value in theme.to_xterm_dict().values():
            assert value.startswith("#")
            assert len(value) in (4, 7)
