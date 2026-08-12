from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QInputDialog, QTabWidget, QToolButton, QWidget

from qtxterm.appearance import Appearance, AppearanceStore
from qtxterm.browser_widget import BrowserWidget
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
    ) -> None:
        super().__init__(parent)
        self._shell_store = shell_store
        # Two layers: the automatic name (shell name, or a browser tab's
        # host) and an optional user-set one that overrides it. Kept apart so
        # a rename isn't silently overwritten the next time the automatic name
        # changes, and so clearing a rename can fall back to something current.
        self._auto_titles: dict[QWidget, str] = {}
        self._custom_titles: dict[QWidget, str] = {}
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

    def _install_shortcuts(self) -> None:
        def bind(sequence: str, slot) -> QShortcut:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(slot)
            return shortcut

        self._new_tab_shortcut = bind("Ctrl+Shift+T", lambda: self.new_tab())
        self._close_tab_shortcut = bind("Ctrl+Shift+W", self._close_current_tab)
        self._next_tab_shortcut = bind("Ctrl+Tab", self._activate_next_tab)
        self._prev_tab_shortcut = bind("Ctrl+Shift+Tab", self._activate_prev_tab)

    def new_tab(
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

        return self._add_tab(widget)

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
        return widget

    def _apply_appearance_to_all_tabs(self) -> None:
        appearance = self._appearance_store.current
        for i in range(self.count()):
            self.widget(i).apply_appearance(appearance)

    def close_tab_at(self, index: int) -> None:
        widget = self.widget(index)
        if widget is None:
            return
        widget.shutdown()
        self.removeTab(index)
        self._auto_titles.pop(widget, None)
        self._custom_titles.pop(widget, None)
        widget.deleteLater()

        if self.count() == 0:
            self.all_tabs_closed.emit()
        else:
            self._renumber()

    def close_all_tabs(self) -> None:
        """Shut every tab down (PTYs, loading pages) as the window closes."""
        for i in range(self.count()):
            self.widget(i).shutdown()

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

        def _feed() -> None:
            for line in lines:
                widget.send_command(line)

        widget.run_when_ready(_feed)
        return widget

    def active_terminal(self) -> TerminalWidget | None:
        """The current tab if it's a terminal, else None.

        Type-checked rather than just returning currentWidget(): with
        browser tabs in the mix, callers that send commands (sidebar,
        Command submenu, Selection Actions) would otherwise try to write to
        a web page.
        """
        widget = self.currentWidget()
        return widget if isinstance(widget, TerminalWidget) else None

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
        index = self.indexOf(widget)
        if index != -1:
            self.setTabToolTip(index, title)

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
