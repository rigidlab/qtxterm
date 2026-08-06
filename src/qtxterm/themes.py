from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class UiPalette:
    """Chrome colors for the Qt widgets around the terminal (menus, tabs,
    sidebar, dialogs) - the QPalette counterpart to `Theme`'s xterm colors.

    Kept separate from the ANSI 16 because the two answer different
    questions: ANSI colors are what a shell asks for by index, these are
    what the app's own surfaces are painted with.
    """

    window: str
    window_text: str
    base: str
    alternate_base: str
    text: str
    button: str
    button_text: str
    highlight: str
    highlighted_text: str
    tooltip_base: str
    tooltip_text: str
    disabled_text: str
    link: str


@dataclasses.dataclass(frozen=True)
class Theme:
    """A terminal color scheme - maps directly onto xterm.js's `theme` option.

    `ui` optionally carries matching chrome colors for the surrounding Qt
    widgets. None means "leave the platform's native look alone" (see
    QT_DEFAULT).
    """

    name: str
    background: str
    foreground: str
    cursor: str
    selection_background: str
    black: str
    red: str
    green: str
    yellow: str
    blue: str
    magenta: str
    cyan: str
    white: str
    bright_black: str
    bright_red: str
    bright_green: str
    bright_yellow: str
    bright_blue: str
    bright_magenta: str
    bright_cyan: str
    bright_white: str
    ui: UiPalette | None = None

    def to_xterm_dict(self) -> dict[str, str]:
        return {
            "background": self.background,
            "foreground": self.foreground,
            "cursor": self.cursor,
            "selectionBackground": self.selection_background,
            "black": self.black,
            "red": self.red,
            "green": self.green,
            "yellow": self.yellow,
            "blue": self.blue,
            "magenta": self.magenta,
            "cyan": self.cyan,
            "white": self.white,
            "brightBlack": self.bright_black,
            "brightRed": self.bright_red,
            "brightGreen": self.bright_green,
            "brightYellow": self.bright_yellow,
            "brightBlue": self.bright_blue,
            "brightMagenta": self.bright_magenta,
            "brightCyan": self.bright_cyan,
            "brightWhite": self.bright_white,
        }


# "Qt Default" is qtxterm's original hardcoded look, kept as the default
# selection so existing users see no change unless they pick something else.
QT_DEFAULT = Theme(
    name="Qt Default",
    background="#1e1e1e",
    foreground="#d4d4d4",
    cursor="#d4d4d4",
    selection_background="#264f78",
    black="#000000",
    red="#cd3131",
    green="#0dbc79",
    yellow="#e5e510",
    blue="#2472c8",
    magenta="#bc3fbc",
    cyan="#11a8cd",
    white="#e5e5e5",
    bright_black="#666666",
    bright_red="#f14c4c",
    bright_green="#23d18b",
    bright_yellow="#f5f543",
    bright_blue="#3b8eea",
    bright_magenta="#d670d6",
    bright_cyan="#29b8db",
    bright_white="#e5e5e5",
)

# VS Code's "Dark High Contrast" (hc-black): pure-black ground with the
# saturated, unmuted ANSI set, for maximum legibility.
VSCODE_DARK_HIGH_CONTRAST = Theme(
    name="VS Code Dark High Contrast",
    background="#000000",
    foreground="#ffffff",
    cursor="#ffffff",
    selection_background="#ffffff",
    black="#000000",
    red="#cd0000",
    green="#00cd00",
    yellow="#cdcd00",
    blue="#0000ee",
    magenta="#cd00cd",
    cyan="#00cdcd",
    white="#e5e5e5",
    bright_black="#7f7f7f",
    bright_red="#ff0000",
    bright_green="#00ff00",
    bright_yellow="#ffff00",
    bright_blue="#5c5cff",
    bright_magenta="#ff00ff",
    bright_cyan="#00ffff",
    bright_white="#ffffff",
    ui=UiPalette(
        window="#000000",
        window_text="#ffffff",
        base="#000000",
        alternate_base="#0d0d0d",
        text="#ffffff",
        button="#000000",
        button_text="#ffffff",
        highlight="#0f4a85",
        highlighted_text="#ffffff",
        tooltip_base="#000000",
        tooltip_text="#ffffff",
        disabled_text="#8a8a8a",
        link="#3794ff",
    ),
)

VSCODE_LIGHT = Theme(
    name="VS Code Light+",
    background="#ffffff",
    foreground="#333333",
    cursor="#000000",
    selection_background="#add6ff",
    black="#000000",
    red="#cd3131",
    green="#00bc00",
    yellow="#949800",
    blue="#0451a5",
    magenta="#bc05bc",
    cyan="#0598bc",
    white="#555555",
    bright_black="#666666",
    bright_red="#cd3131",
    bright_green="#14ce14",
    bright_yellow="#b5ba00",
    bright_blue="#0451a5",
    bright_magenta="#bc05bc",
    bright_cyan="#0598bc",
    bright_white="#a5a5a5",
    ui=UiPalette(
        window="#f3f3f3",
        window_text="#333333",
        base="#ffffff",
        alternate_base="#f8f8f8",
        text="#333333",
        button="#f3f3f3",
        button_text="#333333",
        highlight="#0060c0",
        highlighted_text="#ffffff",
        tooltip_base="#f3f3f3",
        tooltip_text="#333333",
        disabled_text="#a0a0a0",
        link="#0451a5",
    ),
)

SOLARIZED_DARK = Theme(
    name="Solarized Dark",
    background="#002b36",
    foreground="#839496",
    cursor="#839496",
    selection_background="#073642",
    black="#073642",
    red="#dc322f",
    green="#859900",
    yellow="#b58900",
    blue="#268bd2",
    magenta="#d33682",
    cyan="#2aa198",
    white="#eee8d5",
    bright_black="#002b36",
    bright_red="#cb4b16",
    bright_green="#586e75",
    bright_yellow="#657b83",
    bright_blue="#839496",
    bright_magenta="#6c71c4",
    bright_cyan="#93a1a1",
    bright_white="#fdf6e3",
    ui=UiPalette(
        window="#002b36",
        window_text="#93a1a1",
        base="#073642",
        alternate_base="#002b36",
        text="#93a1a1",
        button="#073642",
        button_text="#93a1a1",
        highlight="#268bd2",
        highlighted_text="#fdf6e3",
        tooltip_base="#073642",
        tooltip_text="#93a1a1",
        disabled_text="#586e75",
        link="#268bd2",
    ),
)

SOLARIZED_LIGHT = Theme(
    name="Solarized Light",
    background="#fdf6e3",
    foreground="#657b83",
    cursor="#657b83",
    selection_background="#eee8d5",
    black="#073642",
    red="#dc322f",
    green="#859900",
    yellow="#b58900",
    blue="#268bd2",
    magenta="#d33682",
    cyan="#2aa198",
    white="#eee8d5",
    bright_black="#002b36",
    bright_red="#cb4b16",
    bright_green="#586e75",
    bright_yellow="#657b83",
    bright_blue="#839496",
    bright_magenta="#6c71c4",
    bright_cyan="#93a1a1",
    bright_white="#fdf6e3",
    ui=UiPalette(
        window="#eee8d5",
        window_text="#586e75",
        base="#fdf6e3",
        alternate_base="#eee8d5",
        text="#586e75",
        button="#eee8d5",
        button_text="#586e75",
        highlight="#268bd2",
        highlighted_text="#fdf6e3",
        tooltip_base="#eee8d5",
        tooltip_text="#586e75",
        disabled_text="#93a1a1",
        link="#268bd2",
    ),
)

THEMES: dict[str, Theme] = {
    theme.name: theme
    for theme in [
        QT_DEFAULT,
        VSCODE_DARK_HIGH_CONTRAST,
        VSCODE_LIGHT,
        SOLARIZED_DARK,
        SOLARIZED_LIGHT,
    ]
}


def default_theme_name() -> str:
    return QT_DEFAULT.name
