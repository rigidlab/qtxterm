"""AppearanceStore: load/save theme+font prefs via QSettings (tmp-backed)."""

from __future__ import annotations

from dataclasses import replace

from pathlib import Path

from PySide6.QtCore import QSettings

from qtxterm.appearance import (
    Appearance,
    AppearanceStore,
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    DEFAULT_SCROLLBACK,
    MAX_SCROLLBACK,
    MIN_SCROLLBACK,
)
from qtxterm.themes import THEMES, default_theme_name


def make_settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def test_defaults_to_qt_default_theme_when_nothing_saved(tmp_path: Path) -> None:
    store = AppearanceStore(make_settings(tmp_path))

    assert store.current.theme_name == default_theme_name()
    assert store.current.font_family == DEFAULT_FONT_FAMILY
    assert store.current.font_size == DEFAULT_FONT_SIZE


def test_save_persists_across_store_instances(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    store = AppearanceStore(settings)

    store.save(Appearance(theme_name="Solarized Dark", font_family="Cascadia Mono", font_size=16))

    reloaded = AppearanceStore(settings)
    assert reloaded.current.theme_name == "Solarized Dark"
    assert reloaded.current.font_family == "Cascadia Mono"
    assert reloaded.current.font_size == 16


def test_save_emits_changed(tmp_path: Path) -> None:
    store = AppearanceStore(make_settings(tmp_path))
    calls = []
    store.changed.connect(lambda: calls.append(True))

    store.save(Appearance(theme_name="VS Code Dark High Contrast"))

    assert calls == [True]


def test_unknown_saved_theme_name_falls_back_to_default(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    settings.setValue("appearance/theme", "Nonexistent Theme")

    store = AppearanceStore(settings)

    assert store.current.theme_name == default_theme_name()


def test_appearance_theme_property_resolves_to_theme_object(tmp_path: Path) -> None:
    appearance = Appearance(theme_name="Solarized Light")

    assert appearance.theme is THEMES["Solarized Light"]


def test_scrollback_defaults_to_xterms_own_default(tmp_path: Path) -> None:
    store = AppearanceStore(make_settings(tmp_path))

    assert store.current.scrollback == DEFAULT_SCROLLBACK == 1000


def test_scrollback_is_saved_and_reloaded(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    AppearanceStore(settings).save(Appearance(scrollback=25_000))

    assert AppearanceStore(make_settings(tmp_path)).current.scrollback == 25_000


def test_no_scrollback_at_all_survives_a_reload(tmp_path: Path) -> None:
    """0 is a real choice - keep nothing but the screen - and falsy, so it is
    exactly the value a sloppy default would swallow."""
    settings = make_settings(tmp_path)
    AppearanceStore(settings).save(Appearance(scrollback=0))

    assert AppearanceStore(make_settings(tmp_path)).current.scrollback == 0


def test_a_hand_edited_scrollback_is_clamped(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    settings.setValue("appearance/scrollback", -5)
    assert AppearanceStore(make_settings(tmp_path)).current.scrollback == MIN_SCROLLBACK

    settings.setValue("appearance/scrollback", 10**9)
    assert AppearanceStore(make_settings(tmp_path)).current.scrollback == MAX_SCROLLBACK


def test_background_image_and_opacity_round_trip(tmp_path) -> None:
    from qtxterm.appearance import DEFAULT_BACKGROUND_OPACITY

    settings = QSettings(str(tmp_path / "a.ini"), QSettings.Format.IniFormat)
    store = AppearanceStore(settings)
    assert store.current.background_image == ""
    assert store.current.background_opacity == DEFAULT_BACKGROUND_OPACITY

    store.save(replace(store.current, background_image="C:/wall.png", background_opacity=70))

    reloaded = AppearanceStore(QSettings(str(tmp_path / "a.ini"), QSettings.Format.IniFormat))
    assert reloaded.current.background_image == "C:/wall.png"
    assert reloaded.current.background_opacity == 70


def test_background_opacity_is_clamped_on_load(tmp_path) -> None:
    """The ini is hand-editable, and a nonsense percentage should not produce
    an invalid CSS alpha."""
    from qtxterm.appearance import MAX_BACKGROUND_OPACITY

    settings = QSettings(str(tmp_path / "a.ini"), QSettings.Format.IniFormat)
    settings.setValue("appearance/backgroundOpacity", 900)
    assert AppearanceStore(settings).current.background_opacity == MAX_BACKGROUND_OPACITY

    settings.setValue("appearance/backgroundOpacity", -5)
    assert AppearanceStore(settings).current.background_opacity == 0


def test_the_default_background_strength_keeps_text_readable() -> None:
    """A photograph at full strength behind text is unreadable, so trying the
    feature for the first time should still leave a working terminal."""
    from qtxterm.appearance import DEFAULT_BACKGROUND_OPACITY

    assert 0 < DEFAULT_BACKGROUND_OPACITY <= 50
