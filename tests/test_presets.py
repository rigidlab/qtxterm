"""Preset dataclass defaults and PresetStore JSON persistence."""

from __future__ import annotations

from pathlib import Path

from mterm.presets import Preset, PresetStore


def test_target_defaults_to_active_for_single_line() -> None:
    preset = Preset(name="Status", lines=["git status"])
    assert preset.target == "active"


def test_target_defaults_to_new_tab_for_multiple_lines() -> None:
    preset = Preset(name="Deploy", lines=["cd app", "make deploy"])
    assert preset.target == "new_tab"


def test_explicit_target_is_not_overridden() -> None:
    preset = Preset(name="Status", lines=["git status"], target="new_tab")
    assert preset.target == "new_tab"


def test_store_seeds_defaults_when_no_file_exists(tmp_path: Path) -> None:
    store = PresetStore(path=tmp_path / "presets.json")

    assert store.presets  # non-empty seed data
    assert (tmp_path / "presets.json").exists()


def test_store_round_trips_through_disk(tmp_path: Path) -> None:
    path = tmp_path / "presets.json"
    store = PresetStore(path=path)
    store.presets = [Preset(name="Custom", lines=["echo hi"], group="Misc")]
    store.save()

    reloaded = PresetStore(path=path)

    assert len(reloaded.presets) == 1
    assert reloaded.presets[0].name == "Custom"
    assert reloaded.presets[0].group == "Misc"


def test_sidebar_presets_filters_by_flag(tmp_path: Path) -> None:
    store = PresetStore(path=tmp_path / "presets.json")
    store.presets = [
        Preset(name="Shown", lines=["echo shown"], show_in_sidebar=True),
        Preset(name="Hidden", lines=["echo hidden"], show_in_sidebar=False),
    ]

    assert [p.name for p in store.sidebar_presets()] == ["Shown"]


def test_sidebar_presets_excludes_new_tab_macros_even_if_flagged(tmp_path: Path) -> None:
    """Commands vs Macros is a strict split: a new_tab preset is a Macro and
    belongs in the Macros menu (Phase 4), never the sidebar."""
    store = PresetStore(path=tmp_path / "presets.json")
    store.presets = [
        Preset(name="Command", lines=["echo one"], show_in_sidebar=True),
        Preset(
            name="Macro",
            lines=["echo one", "echo two"],
            show_in_sidebar=True,
            target="new_tab",
        ),
    ]

    assert [p.name for p in store.sidebar_presets()] == ["Command"]


def test_save_emits_changed(qtbot, tmp_path: Path) -> None:
    store = PresetStore(path=tmp_path / "presets.json")

    with qtbot.waitSignal(store.changed, timeout=1000):
        store.add(Preset(name="New", lines=["echo new"]))


def test_add_update_delete_persist(tmp_path: Path) -> None:
    path = tmp_path / "presets.json"
    store = PresetStore(path=path)
    store.presets = []
    store.save()

    store.add(Preset(name="A", lines=["echo a"]))
    assert PresetStore(path=path).presets[0].name == "A"

    store.update(0, Preset(name="B", lines=["echo b"]))
    assert PresetStore(path=path).presets[0].name == "B"

    store.delete(0)
    assert PresetStore(path=path).presets == []
