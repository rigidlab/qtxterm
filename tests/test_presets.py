"""Preset dataclass defaults and PresetStore JSON persistence."""

from __future__ import annotations

from pathlib import Path

from qtxterm.presets import macro_steps, Preset, PresetStore


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


def test_macro_without_a_separator_is_one_step() -> None:
    """Every Macro written before steps existed must keep opening one tab."""
    steps = macro_steps(["echo one", "echo two"])

    assert [(s.placement, s.lines) for s in steps] == [("tab", ["echo one", "echo two"])]


def test_a_separator_starts_another_tab() -> None:
    steps = macro_steps(["npm run dev", "---", "git status"])

    assert [(s.placement, s.lines) for s in steps] == [
        ("tab", ["npm run dev"]),
        ("tab", ["git status"]),
    ]


def test_separators_carry_where_the_step_opens() -> None:
    steps = macro_steps(["a", "--- right", "b", "--- down", "c"])

    assert [(s.placement, s.lines) for s in steps] == [
        ("tab", ["a"]),
        ("right", ["b"]),
        ("down", ["c"]),
    ]


def test_the_first_step_always_opens_a_tab() -> None:
    """It has nothing to be placed relative to."""
    steps = macro_steps(["--- right", "a", "--- down", "b"])

    assert steps[0].placement == "tab"
    assert steps[1].placement == "down"


def test_an_unknown_placement_falls_back_to_a_tab() -> None:
    """A typo should cost a pane arrangement, not the whole macro."""
    steps = macro_steps(["a", "--- sideways", "b"])

    assert [s.placement for s in steps] == ["tab", "tab"]


def test_empty_groups_are_dropped() -> None:
    steps = macro_steps(["---", "a", "---", "---", "b", "---"])

    assert [s.lines for s in steps] == [["a"], ["b"]]


def test_a_separator_needs_to_be_the_whole_line() -> None:
    """`echo ---` is a command, not a separator."""
    steps = macro_steps(["echo ---", "git log --- graph"])

    assert len(steps) == 1
    assert steps[0].lines == ["echo ---", "git log --- graph"]
