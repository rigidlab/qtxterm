from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import platformdirs
from PySide6.QtCore import QObject, Signal


@dataclasses.dataclass
class Preset:
    """A named, reusable shell command (or sequence of commands).

    `target` is a strict category, not just an execution detail (see
    SPEC.md "Data Model"): "active" is a Command, shown in the sidebar and
    sent to whichever terminal you're already working in. "new_tab" is a
    Macro, shown in the Macros menu and run in a fresh tab, for anything
    long-running or disruptive (a dev server, a build). A preset is one or
    the other, never both.
    """

    name: str
    lines: list[str]
    group: str | None = None
    target: str = ""
    show_in_sidebar: bool = False

    def __post_init__(self) -> None:
        if not self.target:
            self.target = "active" if len(self.lines) == 1 else "new_tab"


def default_presets() -> list[Preset]:
    return [
        Preset(name="Git Status", lines=["git status"], group="Git", show_in_sidebar=True),
        Preset(name="Git Pull", lines=["git pull"], group="Git", show_in_sidebar=True),
        Preset(name="Clear", lines=["clear"], show_in_sidebar=True),
    ]


def default_presets_path() -> Path:
    # appauthor=False: no vendor subfolder (Windows would otherwise nest
    # under "mterm/mterm" since appauthor defaults to the app name).
    return Path(platformdirs.user_config_dir("mterm", appauthor=False)) / "presets.json"


class PresetStore(QObject):
    """Loads/saves the preset list as JSON, seeding defaults on first run.

    Emits `changed` after every save() so any number of UI surfaces
    (sidebar, Macros menu) can stay in sync regardless of which one
    triggered the edit, without reaching into each other.
    """

    changed = Signal()

    def __init__(self, path: Path | None = None) -> None:
        super().__init__()
        self.path = path or default_presets_path()
        self.presets: list[Preset] = []
        self.load()

    def load(self) -> None:
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.presets = [Preset(**item) for item in raw]
        else:
            self.presets = default_presets()
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [dataclasses.asdict(p) for p in self.presets]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.changed.emit()

    def sidebar_presets(self) -> list[Preset]:
        """Command-category presets opted into the sidebar.

        target == "active" is required, not just show_in_sidebar: Commands
        and Macros are a strict split (see SPEC.md) - a new_tab preset is a
        Macro and belongs in the Macros menu (Phase 4), never the sidebar,
        even if show_in_sidebar was left set from before it became a Macro.
        """
        return [p for p in self.presets if p.show_in_sidebar and p.target == "active"]

    def add(self, preset: Preset) -> None:
        self.presets.append(preset)
        self.save()

    def update(self, index: int, preset: Preset) -> None:
        self.presets[index] = preset
        self.save()

    def delete(self, index: int) -> None:
        del self.presets[index]
        self.save()
