from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QTabWidget, QToolButton, QWidget

from mterm.pty_backend import PtySession
from mterm.terminal_widget import TerminalWidget


class TerminalTabWidget(QTabWidget):
    """Tab container for TerminalWidgets, with tmux-style "{index}:{title}" labels.

    Shortcuts deliberately avoid plain Ctrl+W/Ctrl+T: Ctrl+W is bash/readline's
    "delete previous word", so binding it to "close tab" would break normal
    shell line-editing whenever a terminal has focus.
    """

    all_tabs_closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._titles: dict[TerminalWidget, str] = {}

        self.setTabsClosable(True)
        self.setMovable(True)
        self.tabCloseRequested.connect(self.close_tab_at)
        self.tabBar().tabMoved.connect(lambda *_args: self._renumber())

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
        self, shell: str | list[str] | None = None, pty_session: PtySession | None = None
    ) -> TerminalWidget:
        widget = TerminalWidget(shell=shell, pty_session=pty_session)
        widget.title_changed.connect(
            lambda title, w=widget: self._update_tab_title(w, title)
        )
        self._titles[widget] = widget.default_title

        index = self.addTab(widget, "")
        self.setCurrentIndex(index)
        self._renumber()
        return widget

    def close_tab_at(self, index: int) -> None:
        widget = self.widget(index)
        if widget is None:
            return
        widget.shutdown()
        self.removeTab(index)
        self._titles.pop(widget, None)
        widget.deleteLater()

        if self.count() == 0:
            self.all_tabs_closed.emit()
        else:
            self._renumber()

    def close_all_tabs(self) -> None:
        """Shut down every tab's PTY, e.g. when the whole window is closing."""
        for i in range(self.count()):
            self.widget(i).shutdown()

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
        return self.currentWidget()

    def _update_tab_title(self, widget: TerminalWidget, title: str) -> None:
        self._titles[widget] = title
        self._renumber()

    def _renumber(self) -> None:
        for i in range(self.count()):
            title = self._titles.get(self.widget(i), "")
            self.setTabText(i, f"{i}:{title}")

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
