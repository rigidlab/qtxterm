from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class Theme:
    """A terminal color scheme - maps directly onto xterm.js's `theme` option."""

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

VSCODE_DARK = Theme(
    name="VS Code Dark+",
    background="#1e1e1e",
    foreground="#cccccc",
    cursor="#ffffff",
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
)

THEMES: dict[str, Theme] = {
    theme.name: theme
    for theme in [QT_DEFAULT, VSCODE_DARK, VSCODE_LIGHT, SOLARIZED_DARK, SOLARIZED_LIGHT]
}


def default_theme_name() -> str:
    return QT_DEFAULT.name
