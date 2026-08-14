from __future__ import annotations

import dataclasses

from PySide6.QtCore import QObject, QSettings, Signal

from qtxterm.themes import THEMES, Theme, default_theme_name

_THEME_KEY = "appearance/theme"
_FONT_FAMILY_KEY = "appearance/fontFamily"
_FONT_SIZE_KEY = "appearance/fontSize"
_SCROLLBACK_KEY = "appearance/scrollback"

DEFAULT_FONT_FAMILY = "Consolas"
DEFAULT_FONT_SIZE = 14

# xterm.js's own default, kept as ours so the setting starts where the
# terminal already was. Every line held is memory that a terminal left open
# for days never gives back, which is why this is worth exposing at all.
DEFAULT_SCROLLBACK = 1000
# 0 means "keep nothing but the screen". The ceiling is xterm.js's
# MAX_BUFFER_SIZE, past which it silently clamps - better to stop at a
# number the user chose than one they didn't.
MIN_SCROLLBACK = 0
MAX_SCROLLBACK = 100_000


@dataclasses.dataclass
class Appearance:
    theme_name: str = default_theme_name()
    font_family: str = DEFAULT_FONT_FAMILY
    font_size: int = DEFAULT_FONT_SIZE
    scrollback: int = DEFAULT_SCROLLBACK

    @property
    def theme(self) -> Theme:
        return THEMES.get(self.theme_name, THEMES[default_theme_name()])


class AppearanceStore(QObject):
    """Loads/saves terminal appearance prefs (theme, font) via QSettings.

    Emits `changed` after every save() so every open TerminalWidget can
    re-apply live, the same pattern PresetStore uses for presets.
    """

    changed = Signal()

    def __init__(self, settings: QSettings) -> None:
        super().__init__()
        self._settings = settings
        self.current = self._load()

    def _load(self) -> Appearance:
        theme_name = self._settings.value(_THEME_KEY, default_theme_name())
        if theme_name not in THEMES:
            theme_name = default_theme_name()
        font_family = self._settings.value(_FONT_FAMILY_KEY, DEFAULT_FONT_FAMILY)
        font_size = int(self._settings.value(_FONT_SIZE_KEY, DEFAULT_FONT_SIZE))
        scrollback = int(self._settings.value(_SCROLLBACK_KEY, DEFAULT_SCROLLBACK))
        return Appearance(
            theme_name=theme_name,
            font_family=font_family,
            font_size=font_size,
            # Clamped on the way in: a hand-edited ini shouldn't be able to
            # ask xterm.js for a negative buffer.
            scrollback=max(MIN_SCROLLBACK, min(scrollback, MAX_SCROLLBACK)),
        )

    def save(self, appearance: Appearance) -> None:
        self.current = appearance
        self._settings.setValue(_THEME_KEY, appearance.theme_name)
        self._settings.setValue(_FONT_FAMILY_KEY, appearance.font_family)
        self._settings.setValue(_FONT_SIZE_KEY, appearance.font_size)
        self._settings.setValue(_SCROLLBACK_KEY, appearance.scrollback)
        self.changed.emit()
