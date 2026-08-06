"""AppearanceStore: load/save theme+font prefs via QSettings (tmp-backed)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from qtxterm.appearance import Appearance, AppearanceStore, DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE
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
