from __future__ import annotations

import html
from dataclasses import replace

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QPainter, QPalette, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QInputDialog,
    QSplitter,
    QTabWidget,
    QToolButton,
    QWidget,
)

from qtxterm import shortcuts
from qtxterm.appearance import (
    DEFAULT_FONT_SIZE,
    MAX_FONT_SIZE,
    MIN_FONT_SIZE,
    Appearance,
    AppearanceStore,
)
from qtxterm.browser_widget import BrowserWidget
from qtxterm.exit_prefs import PaneExitStore, should_close
from qtxterm.pane import PaneWidget
from qtxterm.presets import STEP_RIGHT, STEP_TAB, macro_steps
from qtxterm.pty_backend import PtySession, default_shell
from qtxterm.shell_prefs import ShellPreferenceStore
from qtxterm.terminal_widget import TerminalWidget, shell_short_name


class TerminalTabWidget(QTabWidget):
    """Tab container for TerminalWidgets, labelled tmux-style "{index}:{shell}".

    Shortcuts deliberately avoid plain Ctrl+W/Ctrl+T: Ctrl+W is bash/readline's
    "delete previous word", so binding it to "close tab" would break normal
    shell line-editing whenever a terminal has focus.
    """

    all_tabs_closed = Signal()
    # Re-emitted from whichever tab was right-clicked, so listeners wire up
    # once here instead of per-tab.
    context_menu_requested = Signal(QPoint)

    def __init__(
        self,
        parent: QWidget | None = None,
        appearance_store: AppearanceStore | None = None,
        shell_store: ShellPreferenceStore | None = None,
        exit_store: PaneExitStore | None = None,
    ) -> None:
        super().__init__(parent)
        self._shell_store = shell_store
        self._exit_store = exit_store
        # Two layers: the automatic name (shell name, or a browser tab's
        # host) and an optional user-set one that overrides it. Kept apart so
        # a rename isn't silently overwritten the next time the automatic name
        # changes, and so clearing a rename can fall back to something current.
        self._auto_titles: dict[QWidget, str] = {}
        self._custom_titles: dict[QWidget, str] = {}
        # Which pane was last focused inside each tab - a terminal or a
        # browser. "The active pane" has to be the one you last used, not an
        # arbitrary one: getting it wrong sends a sidebar command to the wrong
        # terminal, silently.
        self._focused_panes: dict[QWidget, PaneWidget] = {}
        self._appearance_store = appearance_store
        if self._appearance_store is not None:
            self._appearance_store.changed.connect(self._apply_appearance_to_all_tabs)

        self.setTabsClosable(True)
        self.setMovable(True)
        self.tabCloseRequested.connect(self.close_tab_at)
        self.tabBar().tabMoved.connect(lambda *_args: self._renumber())
        self.tabBarDoubleClicked.connect(self._prompt_rename)

        add_button = QToolButton(self)
        add_button.setText("+")
        add_button.setToolTip("New Tab (Ctrl+Shift+T)")
        add_button.clicked.connect(lambda: self.new_tab())
        self.setCornerWidget(add_button, Qt.Corner.TopRightCorner)

        self._install_shortcuts()

        # focusChanged rather than an event filter per terminal: keyboard
        # focus inside a terminal lands on a Chromium child widget, not on the
        # TerminalWidget itself, so the owning terminal has to be found by
        # walking up from whatever actually took focus.
        app = QApplication.instance()
        if app is not None:
            app.focusChanged.connect(self._on_focus_changed)

    def paintEvent(self, event) -> None:
        """Tell an empty window how to get a terminal.

        With no tabs the widget is a blank rectangle, and the app now both
        starts and can end up in that state, so it needs to say what to do.
        """
        super().paintEvent(event)
        if self.count():
            return
        painter = QPainter(self)
        painter.setPen(self.palette().color(QPalette.ColorRole.PlaceholderText))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "No terminals open\n\n"
            "Ctrl+Shift+T for a new terminal, or the + button\n"
            "File → New Terminal for a specific shell",
        )

    def _install_shortcuts(self) -> None:
        """Bind every action, using the sequences chosen for this platform.

        Application context on purpose: a QShortcut is matched before the
        focused widget sees the key, which is what keeps the QTabBar from
        treating a bare arrow as "switch tab" while a pane has focus.
        """

        def bind(sequences: list[str], slot) -> list[QShortcut]:
            bound = []
            for sequence in sequences:
                shortcut = QShortcut(QKeySequence(sequence), self)
                shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
                shortcut.activated.connect(slot)
                bound.append(shortcut)
            return bound

        def seq(action: str) -> list[str]:
            return shortcuts.sequences_for(action)

        # Kept in one list so nothing is garbage-collected: PySide6 will
        # collect a QShortcut whose only reference was a local.
        self._shortcuts: list[QShortcut] = []

        def register(action: str, slot) -> None:
            self._shortcuts.extend(bind(seq(action), slot))

        register(shortcuts.NEW_TAB, lambda: self.new_tab())
        register(shortcuts.CLOSE_TAB, self._close_current_tab)
        register(shortcuts.NEXT_TAB, self._activate_next_tab)
        register(shortcuts.PREV_TAB, self._activate_prev_tab)
        register(
            shortcuts.SPLIT_RIGHT,
            lambda: self.split_active(Qt.Orientation.Horizontal),
        )
        register(
            shortcuts.SPLIT_DOWN,
            lambda: self.split_active(Qt.Orientation.Vertical),
        )
        register(shortcuts.CLOSE_PANE, self.close_active_pane)
        register(shortcuts.FIND, self.show_find_in_active)
        register(shortcuts.COPY, self.copy_in_active)
        register(shortcuts.PASTE, self.paste_in_active)
        register(shortcuts.ZOOM_IN, lambda: self.zoom_font(1))
        register(shortcuts.ZOOM_OUT, lambda: self.zoom_font(-1))
        register(shortcuts.ZOOM_RESET, self.reset_font_zoom)
        register(shortcuts.FOCUS_PANE_LEFT, lambda: self.focus_pane_in_direction(-1, 0))
        register(shortcuts.FOCUS_PANE_RIGHT, lambda: self.focus_pane_in_direction(1, 0))
        register(shortcuts.FOCUS_PANE_UP, lambda: self.focus_pane_in_direction(0, -1))
        register(shortcuts.FOCUS_PANE_DOWN, lambda: self.focus_pane_in_direction(0, 1))
        for slot in range(1, shortcuts.TAB_SLOTS + 1):
            register(
                shortcuts.tab_slot_action(slot),
                lambda checked=False, s=slot: self.activate_tab_slot(s),
            )

    def _make_terminal(
        self,
        shell: str | list[str] | None = None,
        pty_session: PtySession | None = None,
    ) -> TerminalWidget:
        appearance = (
            self._appearance_store.current if self._appearance_store else Appearance()
        )
        # Resolved here rather than by callers: every route into a new tab
        # (the + button, Ctrl+Shift+T, macros, selection actions) passes
        # shell=None for "the default", and all of them should honour the
        # preference.
        if shell is None:
            shell = self.preferred_shell()
        widget = TerminalWidget(
            shell=shell, pty_session=pty_session, appearance=appearance
        )
        # Deliberately not wired to the tab label. Shells set wildly
        # different OSC titles - Git Bash sends
        # "MINGW64:/c/Users/dev/git/qtxterm", cmd sends its own full exe
        # path - which made tabs unreadably wide. The label stays the shell's
        # name; the live title goes in the tooltip so the cwd is still there
        # when you want it.
        widget.title_changed.connect(
            lambda title, w=widget: self._update_tab_tooltip(w, title)
        )
        widget.context_menu_requested.connect(self.context_menu_requested)
        widget.process_exited.connect(
            lambda code, w=widget: self._on_process_exited(w, code)
        )
        return widget

    def new_tab(
        self,
        shell: str | list[str] | None = None,
        pty_session: PtySession | None = None,
    ) -> TerminalWidget:
        return self._add_tab(self._make_terminal(shell, pty_session))

    def new_browser_tab(self, url: str | None = None) -> BrowserWidget:
        """Open a web page in a tab alongside the terminals."""
        widget = BrowserWidget(url=url)
        # Unlike a terminal, a browser tab's live title is worth showing: the
        # host is short and is exactly what identifies the tab, where a
        # shell's OSC title was a full path. The page title goes in the
        # tooltip.
        widget.host_changed.connect(lambda host, w=widget: self._set_tab_title(w, host))
        widget.title_changed.connect(
            lambda title, w=widget: self._update_tab_tooltip(w, title)
        )
        return self._add_tab(widget)

    def _add_tab(self, widget):
        self._auto_titles[widget] = widget.default_title
        index = self.addTab(widget, "")
        self.setCurrentIndex(index)
        self._renumber()
        # addTab leaves Qt's focus on the tab bar, so a brand new terminal
        # needs a click before it accepts a keystroke - and until that click,
        # arrow keys switch tabs instead.
        widget.focus_pane()
        self._schedule_background_refresh()
        return widget

    @staticmethod
    def _panes_in(container: QWidget | None) -> list[PaneWidget]:
        """Every pane inside a tab, whether it is the tab or nested in it.

        findChildren walks the whole subtree, so a tab holding a tree of
        splits is handled the same as one holding a single pane.
        """
        if container is None:
            return []
        if isinstance(container, PaneWidget):
            return [container]
        return container.findChildren(PaneWidget)

    def _terminals_in(self, container: QWidget | None) -> list[TerminalWidget]:
        """Just the terminals - commands can only target those."""
        return [p for p in self._panes_in(container) if isinstance(p, TerminalWidget)]

    def _on_focus_changed(self, _old: QWidget | None, new: QWidget | None) -> None:
        terminal = self._owning_terminal(new)
        if terminal is None:
            return
        for i in range(self.count()):
            if terminal in self._terminals_in(self.widget(i)):
                self._focused_panes[self.widget(i)] = terminal
                self._refresh_pane_indicators()
                return

    @staticmethod
    def _owning_terminal(widget: QWidget | None) -> TerminalWidget | None:
        while widget is not None:
            if isinstance(widget, TerminalWidget):
                return widget
            widget = widget.parentWidget()
        return None

    def _apply_appearance_to_all_tabs(self) -> None:
        appearance = self._appearance_store.current
        for i in range(self.count()):
            for pane in self._panes_in(self.widget(i)):
                pane.apply_appearance(appearance)
        # A new image needs its slices recomputed; a new theme needs the veil
        # repainted over them.
        self._schedule_background_refresh()

    def close_tab_at(self, index: int) -> None:
        widget = self.widget(index)
        if widget is None:
            return
        # Every pane, not the tab's root widget: once a tab is split its root
        # is a QSplitter, which has no shutdown(). Calling it there raised
        # before removeTab() ever ran, so the tab stayed open and its shells
        # were left running.
        for pane in self._panes_in(widget):
            pane.shutdown()
        self.removeTab(index)
        self._auto_titles.pop(widget, None)
        self._custom_titles.pop(widget, None)
        self._focused_panes.pop(widget, None)
        widget.deleteLater()

        if self.count() == 0:
            self.all_tabs_closed.emit()
            # Repaint so the empty-state hint replaces the last tab's content.
            self.update()
        else:
            self._renumber()

    def close_all_tabs(self) -> None:
        """Shut every tab down (PTYs, loading pages) as the window closes."""
        for i in range(self.count()):
            for pane in self._panes_in(self.widget(i)):
                pane.shutdown()

    def tab_index_of(self, widget: QWidget) -> int:
        """Which tab a widget lives in, however deeply nested. -1 if none."""
        for i in range(self.count()):
            root = self.widget(i)
            if widget is root or widget in self._panes_in(root):
                return i
        return -1

    def _replace_tab_widget(
        self, index: int, new_root: QWidget, old_root: QWidget | None = None
    ) -> None:
        """Swap a tab's root widget, keeping its label, tooltip and position.

        QTabWidget has no setWidget, so the tab is removed and re-inserted.
        The title maps are keyed by root widget, so they move across too -
        otherwise a renamed tab would lose its name the moment you split it.

        `old_root` is passed explicitly when the caller has already reparented
        it: adding a widget to a QSplitter removes it from the tab first, so
        by then self.widget(index) no longer names the widget whose titles
        need carrying over.
        """
        if old_root is None:
            old_root = self.widget(index)
        was_current = self.currentIndex() == index
        tooltip = self.tabToolTip(index)

        self.removeTab(index)
        for store in (self._auto_titles, self._custom_titles):
            if old_root in store:
                store[new_root] = store.pop(old_root)
        self._focused_panes.pop(old_root, None)

        self.insertTab(index, new_root, "")
        self.setTabToolTip(index, tooltip)
        if was_current:
            self.setCurrentIndex(index)
        self._renumber()

    def _clone_kind_of(
        self,
        pane: PaneWidget,
        shell: str | list[str] | None = None,
        pty_session: PtySession | None = None,
    ) -> PaneWidget:
        """A fresh pane of the same kind as `pane`.

        Splitting means "another one of these": splitting a browser gives a
        browser, splitting a terminal gives a terminal. A browser pane is
        deliberately not wired to the tab title the way a browser *tab* is -
        only a tab's root widget names the tab, so a pane renaming it would
        be writing to a key nothing reads.
        """
        if isinstance(pane, BrowserWidget):
            return BrowserWidget()
        return self._make_terminal(shell, pty_session)

    def split_active(
        self,
        orientation: Qt.Orientation = Qt.Orientation.Horizontal,
        shell: str | list[str] | None = None,
        pty_session: PtySession | None = None,
    ) -> PaneWidget | None:
        """Split the focused pane in two, returning the new pane.

        Horizontal puts the panes side by side, vertical stacks them - the
        orientation names the divider's axis of arrangement, matching
        QSplitter.
        """
        terminal = self.active_pane()
        if terminal is None:
            return None

        index = self.tab_index_of(terminal)
        if index == -1:
            return None

        new_terminal = self._clone_kind_of(terminal, shell, pty_session)
        splitter = QSplitter(orientation)
        # Panes start even; without this the new one can open at zero width.
        splitter.setChildrenCollapsible(False)

        parent = terminal.parentWidget()
        if terminal is self.widget(index):
            # Detach the tab *before* reparenting: adding the terminal to the
            # splitter pulls it out of the tab widget's stack on its own, and
            # a removeTab() after that acts on an already-mangled tab, which
            # left the new pane hidden at zero width.
            was_current = self.currentIndex() == index
            tooltip = self.tabToolTip(index)
            self.removeTab(index)

            splitter.addWidget(terminal)
            splitter.addWidget(new_terminal)

            for store in (self._auto_titles, self._custom_titles):
                if terminal in store:
                    store[splitter] = store.pop(terminal)
            self._focused_panes.pop(terminal, None)

            self.insertTab(index, splitter, "")
            self.setTabToolTip(index, tooltip)
            if was_current:
                self.setCurrentIndex(index)
            self._renumber()
        else:
            at = parent.indexOf(terminal)
            sizes = parent.sizes()
            splitter.addWidget(terminal)
            splitter.addWidget(new_terminal)
            parent.insertWidget(at, splitter)
            parent.setSizes(sizes)

        # Both panes need showing, for two different reasons: a widget built
        # with no parent starts hidden, and removeTab() explicitly hides the
        # page it detaches. A hidden child of a splitter is laid out at zero
        # size, which is how a split ended up looking like it did nothing.
        splitter.show()
        for i in range(splitter.count()):
            splitter.widget(i).show()

        self._even_out(splitter)
        # A new pane changes every sibling's slice of the background.
        splitter.splitterMoved.connect(
            lambda *_args: self.refresh_background_geometry()
        )
        # Again once the layout has run: at this point the splitter has just
        # been inserted and has no geometry, so its extent is 0 and there is
        # nothing to divide yet.
        QTimer.singleShot(0, lambda s=splitter: self._even_out(s))
        self._focused_panes[self.widget(index)] = new_terminal
        self._refresh_pane_indicators()
        self._schedule_background_refresh()
        # Qt leaves focus on the tab bar after the tab surgery above, which
        # is worse than it sounds: the new pane looks active and swallows
        # nothing, while arrow keys reach the QTabBar and switch *tabs*. The
        # pane you just made is the one you want to type in, so focus it.
        new_terminal.focus_pane()
        return new_terminal

    @staticmethod
    def _even_out(splitter: QSplitter) -> None:
        """Give a splitter's panes equal space.

        Both halves are needed. setSizes() takes *pixels*, not ratios - the
        obvious setSizes([1, 1]) gives each pane one pixel and dumps the
        remainder into the last one, which is how the first pane ended up
        zero-width. And it can't be used alone either: right after a split the
        splitter may not be laid out yet, so its extent is still 0. Stretch
        factors cover that case, since they govern how space is shared
        whenever the layout does happen.
        """
        for i in range(splitter.count()):
            splitter.setStretchFactor(i, 1)
        extent = (
            splitter.width()
            if splitter.orientation() is Qt.Orientation.Horizontal
            else splitter.height()
        )
        if extent > 0 and splitter.count():
            share = extent // splitter.count()
            splitter.setSizes([share] * splitter.count())

    def active_pane_orientation(self) -> Qt.Orientation | None:
        """How the focused pane's splitter arranges it, or None if unsplit.

        Callers use it to label a move as left/right vs up/down.
        """
        pane = self.active_pane()
        parent = pane.parentWidget() if pane else None
        return parent.orientation() if isinstance(parent, QSplitter) else None

    def can_move_active_pane(self, forward: bool) -> bool:
        pane = self.active_pane()
        parent = pane.parentWidget() if pane else None
        if not isinstance(parent, QSplitter):
            return False
        target = parent.indexOf(pane) + (1 if forward else -1)
        return 0 <= target < parent.count()

    def move_active_pane(self, forward: bool) -> bool:
        """Swap the focused pane with its neighbour in the same splitter.

        The size list is left alone on purpose: positions keep their widths
        and the panes trade places, rather than each pane dragging its size
        along and shuffling the layout.
        """
        if not self.can_move_active_pane(forward):
            return False
        pane = self.active_pane()
        parent = pane.parentWidget()
        sizes = parent.sizes()
        parent.insertWidget(parent.indexOf(pane) + (1 if forward else -1), pane)
        pane.show()
        parent.setSizes(sizes)
        return True

    def move_active_pane_to_new_tab(self) -> TerminalWidget | None:
        """Pull the focused pane out into a tab of its own.

        The common "I put this in the wrong place" fix, and much cheaper than
        dragging panes around: the pane keeps its shell, scrollback and PTY,
        it just changes container.
        """
        pane = self.active_pane()
        if pane is None:
            return None
        index = self.tab_index_of(pane)
        if index == -1 or len(self._panes_in(self.widget(index))) <= 1:
            return None

        terminal = pane
        terminal.setParent(None)
        remaining = self._panes_in(self.widget(index))
        if remaining:
            self._focused_panes[self.widget(index)] = remaining[0]
        self._collapse_single_child_splitters(index)

        self._add_tab(terminal)
        terminal.show()
        self._refresh_pane_indicators()
        return terminal

    def close_active_pane(self) -> None:
        """Close the focused pane; the last pane closes the whole tab."""
        self.close_pane(self.active_pane())

    def close_pane(self, terminal: PaneWidget | None) -> None:
        """Close one pane; the last pane in a tab closes the tab.

        Takes the pane rather than assuming the focused one, because a shell
        that exits does so in whichever pane it was running - very often not
        the one you are looking at.
        """
        if terminal is None:
            return
        index = self.tab_index_of(terminal)
        if index == -1:
            return

        siblings = self._panes_in(self.widget(index))
        if len(siblings) <= 1:
            self.close_tab_at(index)
            return

        terminal.shutdown()
        terminal.setParent(None)
        terminal.deleteLater()

        remaining = self._panes_in(self.widget(index))
        self._focused_panes[self.widget(index)] = remaining[0]
        self._collapse_single_child_splitters(index)
        self._refresh_pane_indicators()
        # Closing the focused pane leaves the keyboard nowhere. Hand it to
        # the pane that inherited the space.
        remaining[0].focus_pane()
        self._schedule_background_refresh()

    def _collapse_single_child_splitters(self, index: int) -> None:
        """Unwrap splitters left holding one pane, so the tree doesn't grow
        a chain of pointless single-child splitters as panes are closed."""
        while True:
            root = self.widget(index)
            stale = [
                s
                for s in ([root] if isinstance(root, QSplitter) else [])
                + root.findChildren(QSplitter)
                if s.count() == 1
            ]
            if not stale:
                return
            splitter = stale[0]
            survivor = splitter.widget(0)
            if splitter is self.widget(index):
                survivor.setParent(None)
                self._replace_tab_widget(index, survivor)
            else:
                grandparent = splitter.parentWidget()
                at = grandparent.indexOf(splitter)
                grandparent.insertWidget(at, survivor)
            splitter.setParent(None)
            splitter.deleteLater()

    def _refresh_pane_indicators(self) -> None:
        """Frame the panes of a split, picking out the focused one.

        With one pane per tab there is nothing to disambiguate and the tab
        already outlines it; with several, every pane needs a boundary and
        "which one will this command go to?" needs an answer.
        """
        for i in range(self.count()):
            panes = self._panes_in(self.widget(i))
            active = self._focused_panes.get(self.widget(i))
            for pane in panes:
                pane.set_pane_state(len(panes) > 1, pane is active)

    def preferred_shell(self) -> str | list[str] | None:
        """The configured default shell, or None to let the OS decide."""
        return self._shell_store.resolve() if self._shell_store else None

    def default_shell_name(self) -> str:
        """Short name of the shell a new tab would open, e.g. 'bash'.

        Selection Actions targeting a new tab need it to know how to feed a
        file to stdin, which differs per shell.
        """
        preferred = self.preferred_shell()
        if preferred is None:
            return shell_short_name(default_shell())
        command = preferred if isinstance(preferred, str) else preferred[0]
        return shell_short_name(command)

    def run_in_active(self, lines: list[str]) -> None:
        """Send each line to the active terminal's PTY. No-op if there's no tab."""
        terminal = self.active_terminal()
        if terminal is None:
            return
        for line in lines:
            terminal.send_command(line)

    def run_in_new_tab(
        self,
        shell: str | list[str] | None,
        lines: list[str],
        pty_session: PtySession | None = None,
    ) -> TerminalWidget:
        """Open a new tab and feed it `lines` once its PTY has actually started."""
        widget = self.new_tab(shell=shell, pty_session=pty_session)
        self._feed_when_ready(widget, lines)
        return widget

    def feed_terminal(self, widget: TerminalWidget, lines: list[str]) -> None:
        """Send `lines` to one particular terminal, once its PTY is up.

        Public because a caller can hold on to a terminal and write to it
        repeatedly - the cron scheduler keeps a tab per job and feeds the
        same one on every run.
        """
        self._feed_when_ready(widget, lines)

    @staticmethod
    def _feed_when_ready(widget: TerminalWidget, lines: list[str]) -> None:
        def _feed() -> None:
            for line in lines:
                widget.send_command(line)

        widget.run_when_ready(_feed)

    def run_macro(
        self, lines: list[str], shell: str | list[str] | None = None
    ) -> list[TerminalWidget]:
        """Run a Macro, which may lay itself out across tabs and panes.

        The first step always opens a tab; each later step opens a tab of its
        own or splits the one before it, per the separator that introduced it
        (see presets.macro_steps). A Macro with no separators is one step, so
        it behaves exactly as it did before this existed.

        Splits chain off the pane just created rather than the tab's first
        one - "right then down" gives a column beside the original, which is
        what reading it top to bottom suggests.
        """
        opened: list[TerminalWidget] = []
        for step in macro_steps(lines):
            if step.placement == STEP_TAB or not opened:
                widget = self.run_in_new_tab(shell, step.lines)
            else:
                orientation = (
                    Qt.Orientation.Horizontal
                    if step.placement == STEP_RIGHT
                    else Qt.Orientation.Vertical
                )
                widget = self.split_active(orientation, shell=shell)
                if widget is None:
                    continue
                self._feed_when_ready(widget, step.lines)
            opened.append(widget)
        return opened

    def active_pane(self) -> PaneWidget | None:
        """The pane you last used in the current tab - terminal or browser."""
        current = self.currentWidget()
        if isinstance(current, PaneWidget):
            return current
        panes = self._panes_in(current)
        remembered = self._focused_panes.get(current)
        if remembered in panes:
            return remembered
        return panes[0] if panes else None

    def active_terminal(self) -> TerminalWidget | None:
        """The active pane, but only if it is a terminal.

        Callers that send commands (sidebar, Command submenu, Selection
        Actions) must not write into a web page, so a focused browser pane
        yields None rather than falling back to some other terminal in the
        tab - that would run your command somewhere you weren't looking.
        """
        pane = self.active_pane()
        return pane if isinstance(pane, TerminalWidget) else None

    def _pane_rect(self, pane: PaneWidget) -> QRect:
        """A pane's geometry in this widget's coordinates.

        Mapped rather than read directly so panes nested at different depths
        of the splitter tree are comparable with each other.
        """
        return QRect(pane.mapTo(self, pane.rect().topLeft()), pane.size())

    def focus_pane_in_direction(self, dx: int, dy: int) -> PaneWidget | None:
        """Move the keyboard to the neighbouring pane in a direction.

        Geometry, not tree order: `dx`/`dy` are a unit direction and panes are
        compared by where they sit on screen, so Alt+Right in a nested split
        lands on the pane genuinely to the right rather than on whatever comes
        next in the splitter tree.

        Candidates are ranked by how much of their edge lines up with the
        current pane, then by distance, then top-left first. Ranking by
        distance between centres looked equivalent and was not: with a tall
        pane on the left and two stacked on the right, the two candidates'
        centres sat 138 and 139 pixels off axis, so which one Alt+Right chose
        came down to a single pixel and would flip if the splitter moved.
        Overlap is stable under that, and the final top-left tie-break means
        an exact tie still resolves the same way every time.
        """
        current = self.active_pane()
        tab = self.currentWidget()
        panes = self._panes_in(tab)
        if current is None or len(panes) < 2:
            return None

        origin = self._pane_rect(current)
        best: PaneWidget | None = None
        best_score: tuple[int, int, int, int] | None = None
        for pane in panes:
            if pane is current:
                continue
            rect = self._pane_rect(pane)
            if dx:
                along = (rect.center().x() - origin.center().x()) * dx
                overlap = min(rect.bottom(), origin.bottom()) - max(
                    rect.top(), origin.top()
                )
            else:
                along = (rect.center().y() - origin.center().y()) * dy
                overlap = min(rect.right(), origin.right()) - max(
                    rect.left(), origin.left()
                )
            # Strictly beyond us in the direction asked for, and sharing at
            # least some edge - a pane diagonally opposite is not "to the
            # right", and stepping to it would be a jump nobody predicted.
            if along <= 0 or overlap <= 0:
                continue
            score = (-overlap, along, rect.top(), rect.left())
            if best_score is None or score < best_score:
                best, best_score = pane, score

        if best is None:
            return None
        self._focused_panes[tab] = best
        best.focus_pane()
        self._refresh_pane_indicators()
        return best

    def _on_process_exited(self, terminal: TerminalWidget, exit_code: int) -> None:
        """Close the pane whose shell just exited, if the preference says so.

        Deferred to the next turn of the event loop rather than closed here:
        this runs from the PTY's own `exited` signal, and deleting the widget
        that owns the object currently emitting is how you get a crash rather
        than a closed pane. The pane is also re-checked at that point, since
        a tab closed in the meantime would leave nothing to act on.
        """
        if self._exit_store is None:
            return
        if not should_close(self._exit_store.current, exit_code):
            return
        QTimer.singleShot(0, lambda: self._close_exited_pane(terminal))

    def _close_exited_pane(self, terminal: TerminalWidget) -> None:
        if self.tab_index_of(terminal) == -1:
            return
        self.close_pane(terminal)

    def refresh_background_geometry(self) -> None:
        """Push every terminal pane its rectangle within its own tab.

        Cheap enough to do for all tabs rather than only the visible one: a
        background tab that is resized while hidden would otherwise paint a
        stale slice the moment you switched to it.
        """
        for index in range(self.count()):
            page = self.widget(index)
            if page is None:
                continue
            for pane in self._panes_in(page):
                if not isinstance(pane, TerminalWidget):
                    continue
                # The view, not the pane: the pane's border margin is not part
                # of the page, so using it would shift every slice by two
                # pixels and leave visible seams between panes.
                origin = pane.view_origin_in(page)
                pane.set_background_geometry(
                    origin.x(), origin.y(), page.width(), page.height()
                )

    def _schedule_background_refresh(self) -> None:
        """Refresh now and again after the layout settles.

        A pane inserted into a splitter has no geometry yet, so the immediate
        pass would push zeros; the deferred one catches the real numbers. The
        same trick, and the same reason, as _even_out.
        """
        self.refresh_background_geometry()
        QTimer.singleShot(0, self.refresh_background_geometry)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._schedule_background_refresh()

    def copy_in_active(self) -> bool:
        """Copy the focused terminal's selection. False if there was none.

        Returning rather than always swallowing the key matters for the
        macOS binding: there Cmd+C is copy, and with nothing selected the
        sensible thing is to do nothing at all rather than clear the
        clipboard.
        """
        terminal = self.active_terminal()
        return bool(terminal and terminal.copy_selection())

    def paste_in_active(self) -> None:
        """Paste into the focused terminal, honouring bracketed paste.

        Routed through the terminal rather than written to the PTY directly
        so a multi-line clipboard arrives as a paste, not as a series of
        typed commands with their newlines acted on.
        """
        terminal = self.active_terminal()
        if terminal is not None:
            terminal.paste_from_clipboard()

    def zoom_font(self, steps: int) -> int | None:
        """Grow or shrink the terminal font, and remember it.

        Saved through the appearance store rather than pushed straight at the
        open terminals, so it survives a restart and reaches panes opened
        later - the same path the Preferences font size uses, which also
        means the shell is told its new grid size rather than left wrapping
        to the old width.
        """
        if self._appearance_store is None:
            return None
        current = self._appearance_store.current
        size = max(MIN_FONT_SIZE, min(current.font_size + steps, MAX_FONT_SIZE))
        if size == current.font_size:
            return size
        self._appearance_store.save(replace(current, font_size=size))
        return size

    def reset_font_zoom(self) -> int | None:
        """Back to the default font size, not to whatever Preferences last held.

        There is only one stored size, so zooming *is* editing the
        preference; without a fixed point to return to, Ctrl+0 would have
        nothing to mean.
        """
        if self._appearance_store is None:
            return None
        current = self._appearance_store.current
        if current.font_size != DEFAULT_FONT_SIZE:
            self._appearance_store.save(replace(current, font_size=DEFAULT_FONT_SIZE))
        return DEFAULT_FONT_SIZE

    def activate_tab_slot(self, slot: int) -> bool:
        """Switch to the tab in position `slot`, counting from 1.

        The last slot means the *last* tab rather than the ninth, following
        browsers and Windows Terminal, so it keeps working once there are
        more tabs than slots.
        """
        if self.count() == 0:
            return False
        index = self.count() - 1 if slot >= shortcuts.LAST_TAB_SLOT else slot - 1
        if not 0 <= index < self.count():
            return False
        self.setCurrentIndex(index)
        pane = self.active_pane()
        if pane is not None:
            pane.focus_pane()
        return True

    def show_find_in_active(self) -> None:
        """Open the find bar in the focused pane, if that pane is a terminal.

        No-op on a browser pane, for the same reason commands are: there is
        no scrollback to search, and silently searching some other terminal in
        the tab would put the bar somewhere you weren't looking.
        """
        terminal = self.active_terminal()
        if terminal is not None:
            terminal.show_find()

    def _set_tab_title(self, widget, title: str) -> None:
        """Update the automatic name. A user rename still wins over it."""
        self._auto_titles[widget] = title
        self._renumber()

    def tab_title(self, index: int) -> str:
        """The name shown for a tab, without the index prefix."""
        widget = self.widget(index)
        return self._custom_titles.get(widget) or self._auto_titles.get(widget, "")

    def rename_tab(self, index: int, name: str) -> None:
        """Give a tab a user-chosen name; blank restores the automatic one."""
        widget = self.widget(index)
        if widget is None:
            return
        stripped = name.strip()
        if stripped:
            self._custom_titles[widget] = stripped
        else:
            self._custom_titles.pop(widget, None)
        self._renumber()

    def _prompt_rename(self, index: int) -> None:
        # -1 is a double-click on empty tab bar space, not on a tab.
        if index < 0:
            return
        name, accepted = QInputDialog.getText(
            self,
            "Rename Tab",
            "Tab name (leave blank to restore the default):",
            text=self.tab_title(index),
        )
        if accepted:
            self.rename_tab(index, name)

    def _update_tab_tooltip(self, widget, title: str) -> None:
        """Show the shell's own title, as text rather than as markup.

        Anything running in the terminal can set this - including a remote
        host over SSH - and Qt renders a tooltip as rich text whenever the
        string looks like markup. An OSC title of "<b>bank.com</b>" would
        then be drawn as formatted text rather than shown for what it is, so
        it is escaped on the way in.
        """
        index = self.indexOf(widget)
        if index != -1:
            self.setTabToolTip(index, html.escape(title))

    def _renumber(self) -> None:
        for i in range(self.count()):
            self.setTabText(i, f"{i}:{self.tab_title(i)}")

    def _close_current_tab(self) -> None:
        index = self.currentIndex()
        if index != -1:
            self.close_tab_at(index)

    def _activate_next_tab(self) -> None:
        if self.count() > 0:
            self.setCurrentIndex((self.currentIndex() + 1) % self.count())

    def _activate_prev_tab(self) -> None:
        if self.count() > 0:
            self.setCurrentIndex((self.currentIndex() - 1) % self.count())
