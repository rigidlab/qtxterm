from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import platformdirs


@dataclasses.dataclass
class Preset:
    """A named, reusable shell command (or sequence of commands).

    `target` decides how the Macros menu will eventually run it: "active"
    types it into the current terminal, "new_tab" opens a fresh tab first
    (Phase 4). The sidebar (Phase 3) ignores `target` entirely and always
    sends to the active terminal, since sidebar buttons are meant for quick
    one-click actions in whatever terminal you're already looking at.
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


class PresetStore:
    """Loads/saves the preset list as JSON, seeding defaults on first run."""

    def __init__(self, path: Path | None = None) -> None:
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
