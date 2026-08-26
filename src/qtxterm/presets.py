from __future__ import annotations

import dataclasses
from pathlib import Path

import platformdirs

from qtxterm.config_store import ConfigStore

INPUT_NONE = "none"
INPUT_SELECTION = "selection"

KIND_SHELL = "shell"
KIND_URL = "url"
KIND_STDIN = "stdin"

CATEGORY_COMMANDS = "commands"
CATEGORY_MACROS = "macros"
CATEGORY_SELECTION = "selection"

# The placeholder a url-kind template must contain to receive the selection.
SELECTION_PLACEHOLDER = "{selection}"

# A Macro's lines can be split into steps, each opening its own terminal.
# The separator carries where that terminal goes, so the layout is authored
# inline and needs no extra fields or editor controls:
#
#     uv run python -m app.server
#     --- right
#     uv run pytest -q
#     --- down
#     git status
#
MACRO_STEP_SEPARATOR = "---"
STEP_TAB = "tab"
STEP_RIGHT = "right"
STEP_DOWN = "down"
_STEP_PLACEMENTS = {STEP_TAB, STEP_RIGHT, STEP_DOWN}


@dataclasses.dataclass(frozen=True)
class MacroStep:
    """One terminal's worth of a Macro, and where it opens."""

    lines: list[str]
    placement: str = STEP_TAB


def macro_steps(lines: list[str]) -> list[MacroStep]:
    """Split a Macro's lines into the terminals it should open.

    No separator means one step, which is what every Macro written before
    this existed contains - so they keep opening a single tab.

    The placement on a separator applies to the step *after* it; the first
    step has nowhere to be relative to, so it always opens a tab. An
    unrecognised word falls back to a tab rather than refusing to run: a
    typo should cost you a pane arrangement, not the whole macro.
    """
    steps: list[MacroStep] = []
    current: list[str] = []
    placement = STEP_TAB

    def flush() -> None:
        if current:
            steps.append(MacroStep(list(current), placement))
        current.clear()

    for line in lines:
        stripped = line.strip()
        if stripped == MACRO_STEP_SEPARATOR or stripped.startswith(
            MACRO_STEP_SEPARATOR + " "
        ):
            flush()
            word = stripped[len(MACRO_STEP_SEPARATOR) :].strip().lower()
            placement = word if word in _STEP_PLACEMENTS else STEP_TAB
        else:
            current.append(line)
    flush()

    if steps:
        steps[0] = MacroStep(steps[0].lines, STEP_TAB)
    return steps


@dataclasses.dataclass
class Preset:
    """A named, reusable shell command (or sequence of commands).

    Every preset belongs to exactly one category (see SPEC.md "Data Model"),
    decided by `input` and then `target`:

    - Command (input none, target "active") - sent to whichever terminal
      you're already working in, and shown in the sidebar.
    - Macro (input none, target "new_tab") - run in a fresh tab, for
      anything long-running or disruptive (a dev server, a build).
    - Selection Action (input "selection") - takes the terminal's selected
      text as its input. `kind` decides how that text travels, because each
      route needs different escaping: "url" percent-encodes it into a
      template and opens a browser (never touching a shell), "stdin" hands
      it to a command on standard input via a temp file. Interpolating it
      into a command line is deliberately not offered - see SPEC.md.
    """

    name: str
    lines: list[str]
    group: str | None = None
    target: str = ""
    show_in_sidebar: bool = False
    input: str = INPUT_NONE
    kind: str = KIND_SHELL

    def __post_init__(self) -> None:
        if not self.target:
            self.target = "active" if len(self.lines) == 1 else "new_tab"
        # A url action opens a browser, so "which terminal" is meaningless -
        # and it must never be pinned to the sidebar as if it were a Command.
        if self.input == INPUT_SELECTION:
            self.show_in_sidebar = False


def category_of(preset: Preset) -> str:
    """The single category `preset` belongs to."""
    if preset.input == INPUT_SELECTION:
        return CATEGORY_SELECTION
    return CATEGORY_COMMANDS if preset.target == "active" else CATEGORY_MACROS


def in_category(presets: list[Preset], category: str) -> list[Preset]:
    return [p for p in presets if category_of(p) == category]


def default_selection_actions() -> list[Preset]:
    """Worked examples of both kinds, one per route the selection can take.

    Separate from default_presets() because defaults are only seeded on
    first run: an install that predates Selection Actions would otherwise
    have no way to discover them, so the editor offers these for restore.
    """
    return [
        Preset(
            name="Search Google",
            lines=["https://www.google.com/search?q={selection}"],
            input=INPUT_SELECTION,
            kind=KIND_URL,
        ),
        Preset(
            name="Explain with Claude",
            lines=["claude -p 'Explain this terminal output, briefly.'"],
            input=INPUT_SELECTION,
            kind=KIND_STDIN,
            target="new_tab",
        ),
    ]


def default_presets() -> list[Preset]:
    return [
        Preset(
            name="Git Status", lines=["git status"], group="Git", show_in_sidebar=True
        ),
        Preset(name="Git Pull", lines=["git pull"], group="Git", show_in_sidebar=True),
        Preset(name="Clear", lines=["clear"], show_in_sidebar=True),
        *default_selection_actions(),
    ]


def default_presets_path() -> Path:
    # appauthor=False: no vendor subfolder (Windows would otherwise nest
    # under "qtxterm/qtxterm" since appauthor defaults to the app name).
    return (
        Path(platformdirs.user_config_dir("qtxterm", appauthor=False)) / "presets.json"
    )


class PresetStore(ConfigStore):
    """Loads/saves the preset list as JSON, seeding defaults on first run.

    Emits `changed` after every save() so any number of UI surfaces
    (sidebar, Macros menu) can stay in sync regardless of which one
    triggered the edit, without reaching into each other - and, since
    `ConfigStore` polls, regardless of which *instance* made the edit.
    """

    def __init__(self, path: Path | None = None) -> None:
        super().__init__(path or default_presets_path())
        self.presets: list[Preset] = []
        self.load()

    def _apply_missing(self) -> None:
        self.presets = default_presets()
        self.save()

    def _apply_payload(self, raw: list) -> None:
        self.presets = [Preset(**item) for item in raw]

    def _build_payload(self) -> list:
        return [dataclasses.asdict(p) for p in self.presets]

    def sidebar_presets(self) -> list[Preset]:
        """Command-category presets opted into the sidebar.

        target == "active" is required, not just show_in_sidebar: Commands
        and Macros are a strict split (see SPEC.md) - a new_tab preset is a
        Macro and belongs in the Macros menu (Phase 4), never the sidebar,
        even if show_in_sidebar was left set from before it became a Macro.
        """
        return [
            p for p in in_category(self.presets, CATEGORY_COMMANDS) if p.show_in_sidebar
        ]

    def add(self, preset: Preset) -> None:
        self.presets.append(preset)
        self.save()

    def update(self, index: int, preset: Preset) -> None:
        self.presets[index] = preset
        self.save()

    def delete(self, index: int) -> None:
        del self.presets[index]
        self.save()

    def swap(self, first: int, second: int) -> None:
        """Exchange two presets, which is how reordering is expressed.

        A swap rather than a move: one list holds all three categories
        interleaved, and the two entries being exchanged are neighbours
        within their own category but rarely adjacent in the file. Swapping
        their positions leaves every other preset exactly where it was.
        """
        self.presets[first], self.presets[second] = (
            self.presets[second],
            self.presets[first],
        )
        self.save()
