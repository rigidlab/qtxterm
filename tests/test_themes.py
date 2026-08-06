"""Theme presets: registry consistency and xterm.js dict shape."""

from __future__ import annotations

import dataclasses

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
        "VS Code Dark High Contrast",
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


def test_qt_default_has_no_ui_palette() -> None:
    """None means "leave the native Qt look alone" - QT_DEFAULT is the only
    theme that shouldn't repaint the app chrome."""
    assert QT_DEFAULT.ui is None


def test_every_non_default_theme_carries_a_ui_palette() -> None:
    for theme in THEMES.values():
        if theme is QT_DEFAULT:
            continue
        assert theme.ui is not None, theme.name


def test_ui_palette_colors_are_hex_strings() -> None:
    for theme in THEMES.values():
        if theme.ui is None:
            continue
        for value in dataclasses.asdict(theme.ui).values():
            assert value.startswith("#"), (theme.name, value)
            assert len(value) in (4, 7)


def test_dark_high_contrast_is_pure_black_on_white() -> None:
    theme = THEMES["VS Code Dark High Contrast"]

    assert theme.background == "#000000"
    assert theme.foreground == "#ffffff"
    assert theme.ui.window == "#000000"
