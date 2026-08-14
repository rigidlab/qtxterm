"""Soak test: is the app still healthy after a long session?

Everything here is about *drift* rather than correctness. The rest of the
suite asks "does this work?"; these ask "does it still work on day two?",
which is a different failure mode - nothing throws, the window just gets
slower, heavier, and eventually stops drawing.

Run it:

    uv run pytest -m soak                      # ~20 cycles, a couple of minutes
    uv run pytest -m soak --soak-minutes 60    # an hour
    uv run pytest -m soak --soak-minutes 1440  # the full 24 hours

Deselected from the default suite (see `addopts`) because it is measured in
minutes, not milliseconds.

One cycle is a compressed session: tabs opened and closed, panes split and
collapsed, a multi-step macro, a browser, output written to scrollback,
theme changes, preset edits that rebuild every menu. It ends back at the
one tab it started with, which is what makes the invariants below
meaningful - anything else still alive at that point is something the app
forgot to let go of.

That surviving tab is the point, not an accident. "Open for 24 hours"
usually means one terminal nobody has closed since Monday, quietly
accumulating scrollback while everything around it churns, so the cycle
keeps one and feeds it output every time round.

Real PTYs are deliberately *not* used by default (`--soak-real-shell` opts
in): spawning thousands of shells measures the OS more than it measures
this app, while the expensive, leak-prone half - a QWebEngineView per
terminal, with a real Chromium render process behind it - is exercised
either way.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from conftest import FakePtySession
from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt, QTimer
from PySide6.QtWidgets import QApplication, QMenu
from soak_metrics import (
    Sample,
    collect,
    growth_per_cycle,
    growth_per_hour,
    write_csv,
)

from qtxterm import terminal_widget as terminal_widget_module
from qtxterm.appearance import Appearance
from qtxterm.browser_widget import BrowserWidget
from qtxterm.main_window import MainWindow
from qtxterm.presets import Preset
from qtxterm.terminal_widget import TerminalWidget

pytestmark = pytest.mark.soak

# Cycles to run when no duration is given. Measured, not guessed: handles
# stop climbing around cycle 45 and memory around cycle 40-60, so a run has
# to get past that before its tail means anything. 60 leaves the last
# quarter comfortably inside the flat part, at about 90 seconds.
DEFAULT_CYCLES = 60

# Below this, warm-up dominates any window you could pick and the trend
# assertions are noise, so a deliberately short run checks the structural
# invariants only. The default run is above it, so the normal path always
# asserts on the trend.
MIN_CYCLES_FOR_TREND = 60

# Growth allowed per cycle, once settled. Measured against a healthy run:
# RSS drifts about 0.04 MB/cycle over eight minutes and the rest are flat,
# so these leave an order of magnitude of headroom while still catching the
# things that actually end a long session - a leaked terminal is tens of MB
# and a dozen handles per cycle, not fractions of one.
MAX_RSS_GROWTH_PER_CYCLE = 2e6
MAX_GDI_GROWTH_PER_CYCLE = 1.0
MAX_USER_GROWTH_PER_CYCLE = 1.0
MAX_HANDLE_GROWTH_PER_CYCLE = 2.0
MAX_PY_OBJECT_GROWTH_PER_CYCLE = 200.0
MAX_WIDGET_GROWTH_PER_CYCLE = 1.0

# Everything is judged on the *tail* of the run - its last quarter. A
# healthy process does not settle instantly: Chromium's render process, font
# caches, handle pools and the JS heap all grow and then plateau, and a line
# fitted through that curve reports a huge "leak" that is really start-up.
# What separates the two is whether a number is still climbing once it has
# had time to settle, which is what the tail measures. Observed on a healthy
# run: memory +2.1 MB/cycle over the first 20 cycles, +0.4 by cycle 40, and
# *negative* past 130 as the working set is handed back.
TAIL_FRACTION = 4
MIN_TAIL_SAMPLES = 8

# The window is idle-ish between cycles, so a round trip through the event
# loop should be immediate. This is the "app feels laggy after a day" check.
MAX_LATENCY_MS = 250.0
MAX_LATENCY_GROWTH = 4.0


def pump(app: QApplication, seconds: float = 0.05) -> None:
    """Let Qt run: deferred deletes, page loads, and the PTY's own signals."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def event_loop_latency_ms(app: QApplication) -> float:
    """How late a zero-delay timer actually fires.

    A proxy for what a user feels as lag: if the loop is clogged with timers,
    queued signals or paint work that accumulated over the session, this is
    where it shows up before anything else does.
    """
    fired: list[float] = []
    start = time.monotonic()
    QTimer.singleShot(0, lambda: fired.append(time.monotonic()))
    deadline = start + 2.0
    while not fired and time.monotonic() < deadline:
        app.processEvents()
    if not fired:
        return 2000.0
    return (fired[0] - start) * 1000


def live(widget_type) -> int:
    return sum(1 for w in QApplication.allWidgets() if isinstance(w, widget_type))


class SoakSession:
    """A MainWindow driven through repeated open/use/close cycles."""

    def __init__(self, window: MainWindow, app: QApplication, real_shell: bool) -> None:
        self.window = window
        self.app = app
        self.real_shell = real_shell
        self.tabs = window._tabs
        self.samples: list[Sample] = []
        self.started = time.monotonic()
        self.peak_terminals = 0
        # The tab nobody ever closes. Everything else in a cycle is opened
        # and closed around it.
        self.long_lived = self.tabs.new_tab()
        self.baseline_receivers: dict[str, int] = {}

    def run_cycle(self, index: int) -> Sample:
        self._open_tabs()
        self._split_panes()
        self._run_macro()
        self._write_output()
        self._churn_ui()
        self._move_things_around()
        self._close_everything()

        if not self.baseline_receivers:
            self.baseline_receivers = self.receiver_counts()

        latency = event_loop_latency_ms(self.app)
        sample = collect(
            cycle=index,
            started=self.started,
            widgets=len(QApplication.allWidgets()),
            terminals=live(TerminalWidget) + live(BrowserWidget),
            latency_ms=latency,
        )
        self.samples.append(sample)
        return sample

    def receiver_counts(self) -> dict[str, int]:
        """How many things are listening to each long-lived store.

        A store outlives every tab, so anything that connects to it per tab
        and never disconnects makes every save a little slower than the last
        - the kind of decay that only shows up after a day, and never in a
        test that opens one window.
        """
        return {
            "presets": self.window._preset_store.receivers("2changed()"),
            "appearance": self.window._appearance_store.receivers("2changed()"),
            "menu order": self.window._menu_order_store.receivers("2changed()"),
        }

    def _open_tabs(self) -> None:
        for _ in range(2):
            self.tabs.new_tab()
        self.tabs.new_browser_tab("about:blank")
        pump(self.app, 0.2)

    def _note_peak(self) -> None:
        self.peak_terminals = max(
            self.peak_terminals, live(TerminalWidget) + live(BrowserWidget)
        )

    def _split_panes(self) -> None:
        # Index 1 onwards: the long-lived tab sits at 0 and is left alone.
        self.tabs.setCurrentIndex(1)
        self.tabs.split_active(Qt.Orientation.Horizontal)
        self.tabs.split_active(Qt.Orientation.Vertical)
        pump(self.app, 0.2)
        self._note_peak()

    def _run_macro(self) -> None:
        self.tabs.run_macro(["echo one", "--- right", "echo two", "---", "echo three"])
        pump(self.app, 0.2)
        self._note_peak()

    def _write_output(self) -> None:
        """Push output through the bridge, the way a chatty shell would.

        xterm.js keeps a scrollback buffer per terminal; a session that never
        closes a tab is the case where that grows without bound.
        """
        for i in range(self.tabs.count()):
            for pane in self.tabs._panes_in(self.tabs.widget(i)):
                if isinstance(pane, TerminalWidget):
                    for _ in range(20):
                        pane._bridge.output.emit("soak output line\r\n")
        pump(self.app, 0.1)

    def _churn_ui(self) -> None:
        """The things that rebuild menus and restyle every open pane."""
        self.window._appearance_store.save(
            Appearance(theme_name="VS Code Dark High Contrast")
        )
        self.window._appearance_store.save(Appearance(theme_name="Solarized Dark"))

        store = self.window._preset_store
        store.add(Preset(name="Soak", lines=["echo soak"], target="active"))
        store.presets = [p for p in store.presets if p.name != "Soak"]
        store.save()

        order_store = self.window._menu_order_store
        order_store.save(list(reversed(order_store.order)))
        order_store.save(list(reversed(order_store.order)))

        if self.tabs.count() > 1:
            self.tabs.rename_tab(1, "renamed")
        pump(self.app, 0.1)

    def _move_things_around(self) -> None:
        self.tabs.setCurrentIndex(1)
        self.tabs.move_active_pane(forward=True)
        self.tabs.move_active_pane_to_new_tab()
        pump(self.app, 0.1)

    def _close_everything(self) -> None:
        """Close every tab this cycle opened, and only those."""
        for index in reversed(range(self.tabs.count())):
            if self.tabs.widget(index) is not self.long_lived:
                self.tabs.close_tab_at(index)
        pump(self.app, 0.4)
        assert self.tabs.count() == 1, "the long-lived tab was closed by a cycle"


@pytest.fixture
def soak_session(qtbot, request, tmp_path: Path, monkeypatch):
    if not request.config.getoption("--soak-real-shell"):
        # A fake PTY per terminal: the QWebEngineView, the bridge and every
        # widget are still real, which is where the leaks would be.
        monkeypatch.setattr(
            terminal_widget_module, "create_pty_session", FakePtySession
        )

    settings = QSettings(str(tmp_path / "soak.ini"), QSettings.Format.IniFormat)
    window = MainWindow(settings=settings)
    qtbot.addWidget(window)
    window.resize(900, 600)
    window.show()
    app = QApplication.instance()
    pump(app, 0.5)

    session = SoakSession(window, app, request.config.getoption("--soak-real-shell"))
    yield session

    window.close()
    pump(app, 0.3)


def tail_of(samples: list[Sample]) -> list[Sample]:
    """The part of the run that is allowed to be flat - see TAIL_FRACTION."""
    tail = samples[-max(len(samples) // TAIL_FRACTION, MIN_TAIL_SAMPLES) :]
    return tail or samples


def report(samples: list[Sample], measured: list[Sample]) -> str:
    def row(name: str, value, scale: float = 1.0, unit: str = "") -> str:
        per_cycle = growth_per_cycle(measured, value) / scale
        per_hour = growth_per_hour(measured, value) / scale
        return f"  {name:<11}{per_cycle:+9.3f}{unit}/cycle{per_hour:+12.1f}{unit}/h"

    lines = ["", "soak samples:"] + [s.line() for s in samples]
    lines += [
        "",
        (
            f"tail: {len(measured)} of {len(samples)} cycles "
            f"({measured[-1].seconds - measured[0].seconds:.0f}s). Per cycle "
            "is what is asserted on; per hour is this workload's pace, which "
            "is far heavier than a real session."
        ),
        row("rss", lambda s: s.rss, 1e6, "MB"),
        row("gdi", lambda s: s.gdi),
        row("user", lambda s: s.user),
        row("handles", lambda s: s.handles),
        row("py objects", lambda s: s.py_objects),
        row("widgets", lambda s: s.widgets),
    ]
    return "\n".join(lines)


def run_cycles(session: SoakSession, request) -> None:
    """Cycle until the clock (or the default cycle count) runs out."""
    minutes = request.config.getoption("--soak-minutes")
    deadline = time.monotonic() + minutes * 60 if minutes else None
    cycle = 0
    while True:
        cycle += 1
        session.run_cycle(cycle)
        if deadline is None:
            if cycle >= DEFAULT_CYCLES:
                break
        elif time.monotonic() >= deadline:
            break


def test_a_long_session_stays_flat_and_responsive(soak_session, request) -> None:
    """Run the cycle over and over and watch for drift.

    Every assertion is on a *slope*, not an absolute: what matters is
    whether a number keeps climbing, since anything that climbs per cycle
    eventually ends the session, and anything that plateaus never will.

    Memory and lag are checked together because they come from one workload
    - running the whole thing twice to assert on them separately would
    double the wall clock and tell us nothing new.
    """
    run_cycles(soak_session, request)

    samples = soak_session.samples
    measured = tail_of(samples)
    print(report(samples, measured))

    csv_path = request.config.getoption("--soak-csv")
    if csv_path:
        write_csv(csv_path, samples)
        print(f"samples written to {csv_path}")

    assert len(measured) >= 2, "not enough cycles to measure a trend"
    assert soak_session.peak_terminals >= 5, (
        f"the cycle only ever had {soak_session.peak_terminals} terminals open - "
        "it is not exercising anything, so its flat metrics prove nothing"
    )

    # Only the long-lived tab survives a cycle. Everything else was closed,
    # so another terminal alive here is one the app is holding on to for good.
    assert samples[-1].terminals == 1, (
        f"{samples[-1].terminals} terminals alive, expected only the "
        "long-lived one - a closed tab is still referenced somewhere"
    )

    tabs = soak_session.tabs
    assert tabs.count() == 1
    for name in ("_auto_titles", "_custom_titles", "_focused_panes"):
        held = getattr(tabs, name)
        assert len(held) <= 1, f"{name} still holds {len(held)} closed widgets"

    # Connections to a store that outlives every tab. If a menu or pane
    # connects per tab and never disconnects, this is where it shows.
    receivers = soak_session.receiver_counts()
    assert receivers == soak_session.baseline_receivers, (
        f"signal connections accumulated: {soak_session.baseline_receivers} "
        f"-> {receivers}"
    )

    # Menus rebuild on every preset/order change; clear_menu() exists so the
    # submenus go with them rather than piling up as hidden children.
    context_menu = soak_session.window._terminal_context_menu
    submenus = context_menu.findChildren(QMenu, options=Qt.FindDirectChildrenOnly)
    assert len(submenus) <= 4, f"context menu accumulated {len(submenus)} submenus"

    if len(samples) < MIN_CYCLES_FOR_TREND:
        print(
            f"\nonly {len(samples)} cycles: too few to tell warm-up from a "
            f"leak (needs {MIN_CYCLES_FOR_TREND}), so the trend assertions "
            "were skipped. The invariants above still ran."
        )
        return

    def assert_flat(name: str, value, limit: float, unit: str = "") -> None:
        growth = growth_per_cycle(measured, value)
        assert growth < limit, (
            f"{name} climbing at {growth:+.3f}{unit}/cycle "
            f"({growth_per_hour(measured, value):+.1f}{unit}/h at this pace), "
            f"limit {limit}{unit}/cycle"
        )

    assert_flat("memory", lambda s: s.rss / 1e6, MAX_RSS_GROWTH_PER_CYCLE / 1e6, "MB")
    assert_flat("GDI handles", lambda s: s.gdi, MAX_GDI_GROWTH_PER_CYCLE)
    assert_flat("USER handles", lambda s: s.user, MAX_USER_GROWTH_PER_CYCLE)
    assert_flat("kernel handles", lambda s: s.handles, MAX_HANDLE_GROWTH_PER_CYCLE)
    assert_flat(
        "Python objects", lambda s: s.py_objects, MAX_PY_OBJECT_GROWTH_PER_CYCLE
    )
    assert_flat("widgets", lambda s: s.widgets, MAX_WIDGET_GROWTH_PER_CYCLE)

    # Lag is its own failure: a session can be flat on memory and still
    # crawl, if timers or queued connections pile up.
    latencies = [s.latency_ms for s in measured]
    worst = max(latencies)
    assert worst < MAX_LATENCY_MS, f"event loop stalled for {worst:.0f}ms"

    half = max(len(latencies) // 2, 1)
    early_half = latencies[:half]
    late_half = latencies[half:] or latencies
    early = sorted(early_half)[len(early_half) // 2]
    late = sorted(late_half)[len(late_half) // 2]
    assert late <= early * MAX_LATENCY_GROWTH + 5.0, (
        f"event loop got slower over the session: {early:.1f}ms -> {late:.1f}ms"
    )
