from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QUrl, QUrlQuery, Signal
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from qtxterm.appearance import Appearance
from qtxterm.pane import PANE_BORDER_WIDTH, PaneWidget
from qtxterm.pty_backend import PtySession, create_pty_session, default_shell
from qtxterm.shell_integration import decorate, path_from_osc7
from qtxterm.terminal_bridge import TerminalBridge

ASSETS_DIR = Path(__file__).parent / "assets"

# What a Ctrl+click in the terminal is allowed to hand to the OS. The link
# addon's own regex already matches only http/https, but that regex is not a
# security boundary: the text it ran against came out of the terminal, which
# on an SSH session means it came from the remote host. QDesktopServices.
# openUrl will happily launch a registered handler for any scheme, so the
# check is repeated here, where it decides whether anything is launched.
OPENABLE_URL_SCHEMES = frozenset({"http", "https"})


class _TerminalView(QWebEngineView):
    """A web view with Chromium's own zoom gestures taken out.

    Ctrl+wheel (and a trackpad pinch) zoom the *page* - every pixel of it,
    the grid included - which is not what a terminal wants: the shell keeps
    its old size while the glyphs change, and one stray scroll over a
    scrollback buffer leaves the pane a size nothing in the app agrees on.
    Font size is a preference, changed by the zoom shortcuts, which resize
    the grid properly.

    Chromium receives input through a child widget the view creates after
    construction, so the filter is installed on children as they appear
    rather than on the view itself.
    """

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ChildAdded:
            child = event.child()
            if child.isWidgetType():
                child.installEventFilter(self)
        return super().event(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.Wheel
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            return True
        if (
            event.type() == QEvent.Type.NativeGesture
            and event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture
        ):
            return True
        return super().eventFilter(watched, event)


def shell_short_name(shell: str) -> str:
    """Best-effort short label for a shell path, e.g. 'powershell.exe' -> 'powershell'."""
    name = Path(shell).name
    if name.lower().endswith(".exe"):
        name = name[: -len(".exe")]
    return name


class TerminalWidget(PaneWidget):
    """A single terminal: xterm.js view (QWebEngineView) wired to a PtySession."""

    title_changed = Signal(str)
    pty_started = Signal()
    # The shell finished, with its exit code. Separate from the bridge's
    # `exited`, which only tells the page to print a line: this one is
    # what decides whether the pane closes itself.
    process_exited = Signal(int)
    # Global position, so a listener can pop a menu up without knowing where
    # this widget sits.
    context_menu_requested = Signal(QPoint)

    def __init__(
        self,
        shell: str | list[str] | None = None,
        parent: QWidget | None = None,
        pty_session: PtySession | None = None,
        appearance: Appearance | None = None,
        cwd: str | None = None,
    ) -> None:
        super().__init__(parent)
        if shell is None:
            self._command = [default_shell()]
        elif isinstance(shell, str):
            self._command = [shell]
        else:
            self._command = list(shell)
        self._pty = pty_session or create_pty_session()
        self.is_pty_started = False
        self._selection = ""
        # Where the shell says it is, kept fresh by OSC 7, and where it was
        # asked to start. The second is the answer until the first arrives,
        # so a pane split off a brand new pane - before its shell has drawn
        # a single prompt - still lands in the right place.
        self._reported_cwd: str | None = None
        self._start_cwd = cwd

        self._view = _TerminalView(self)
        # Without this the view shows Chromium's own menu (Back, Reload, View
        # Source), which is meaningless for a terminal.
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._on_context_menu_requested)
        # Without this the view is white until terminal.js paints the theme
        # background, which flashes on every new terminal - worst on a dark
        # theme, and most visible on the first one while Chromium starts.
        self._view.page().setBackgroundColor(
            QColor((appearance or Appearance()).theme.background)
        )
        self._bridge = TerminalBridge(self)
        self._channel = QWebChannel(self)
        self._channel.registerObject("bridge", self._bridge)
        self._view.page().setWebChannel(self._channel)

        # A margin the indicator can paint into. Zero would leave nowhere to
        # draw a border without resizing the terminal grid when focus moves,
        # which would reflow the shell's output on every click.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            PANE_BORDER_WIDTH, PANE_BORDER_WIDTH, PANE_BORDER_WIDTH, PANE_BORDER_WIDTH
        )
        layout.addWidget(self._view)

        self._script_loaded = False
        self._focus_when_loaded = False
        self._pending_background_geometry: tuple[int, int, int, int] | None = None
        self._bridge.script_loaded.connect(self._on_script_loaded)
        self._bridge.terminal_ready.connect(self._on_terminal_ready)
        self._bridge.input_received.connect(self._pty.write)
        self._bridge.resize_requested.connect(self._pty.resize)
        self._bridge.title_changed.connect(self.title_changed.emit)
        self._bridge.selection_changed.connect(self._on_selection_changed)
        self._bridge.link_activated.connect(self.open_link)
        self._bridge.cwd_changed.connect(self._on_cwd_changed)
        self._pty.output_ready.connect(self._bridge.output.emit)
        self._pty.exited.connect(self._bridge.exited.emit)
        self._pty.exited.connect(self.process_exited.emit)

        self._view.load(self._terminal_url(appearance or Appearance()))

    @staticmethod
    def _background_image_url(appearance: Appearance) -> str:
        """The background image as a URL the page can load, or "".

        A plain filesystem path will not do: the page is served from file://
        and resolves a bare path relative to the assets directory. Missing
        files resolve to "" rather than a broken url(), so deleting the image
        leaves a normal terminal instead of a half-painted one.
        """
        path = (appearance.background_image or "").strip()
        if not path or not Path(path).is_file():
            return ""
        return QUrl.fromLocalFile(str(Path(path).resolve())).toString()

    @staticmethod
    def _terminal_url(appearance: Appearance) -> QUrl:
        # Passed as query params (rather than a post-load bridge call) so
        # the terminal renders in the right theme/font from its very first
        # frame - no flash of the default look before JS catches up.
        url = QUrl.fromLocalFile(str(ASSETS_DIR / "terminal.html"))
        query = QUrlQuery()
        query.addQueryItem("theme", json.dumps(appearance.theme.to_xterm_dict()))
        query.addQueryItem("fontFamily", appearance.font_family)
        query.addQueryItem("fontSize", str(appearance.font_size))
        query.addQueryItem("scrollback", str(appearance.scrollback))
        query.addQueryItem(
            "backgroundImage", TerminalWidget._background_image_url(appearance)
        )
        query.addQueryItem("backgroundOpacity", str(appearance.background_opacity))
        url.setQuery(query)
        return url

    def apply_appearance(self, appearance: Appearance) -> None:
        """Live-update an already-open tab's theme/font without reloading it."""
        self._view.page().setBackgroundColor(QColor(appearance.theme.background))
        payload = json.dumps(
            {
                "theme": appearance.theme.to_xterm_dict(),
                "fontFamily": appearance.font_family,
                "fontSize": appearance.font_size,
                "scrollback": appearance.scrollback,
                "backgroundImage": self._background_image_url(appearance),
                "backgroundOpacity": appearance.background_opacity,
            }
        )
        self._view.page().runJavaScript(
            f"window.applyAppearance && window.applyAppearance({payload});"
        )

    @property
    def shell_name(self) -> str:
        """Short name of the shell this tab is running, e.g. 'powershell'.

        Selection Actions need it: how to feed a file to a command's stdin
        differs per shell (see selection_actions.feed_from_file).
        """
        return shell_short_name(self._command[0])

    @property
    def default_title(self) -> str:
        """Short label derived from the shell, used until the shell sets its own title."""
        return shell_short_name(self._command[0])

    def _on_script_loaded(self) -> None:
        """terminal.js is wired up, so it can be told how big it is.

        Nothing is pushed before this: runJavaScript against a page whose
        script hasn't run yet is silently dropped, and the resize that comes
        with being added to a splitter usually happens first.
        """
        self._script_loaded = True
        self._apply_size()
        # Geometry pushed before the page was ready was dropped, and nothing
        # would push it again until the next split or resize - which left the
        # first pane of a tab painting the whole background while its
        # neighbours painted their slices.
        if self._pending_background_geometry is not None:
            pending = self._pending_background_geometry
            self._pending_background_geometry = None
            self.set_background_geometry(*pending)
        if self._focus_when_loaded:
            self._focus_when_loaded = False
            self.focus_pane()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_size()

    def _apply_size(self) -> None:
        """Tell the page its pixel size, which starts or re-fits the terminal.

        Qt logical pixels map 1:1 to CSS pixels in QtWebEngine, so the view's
        own size is what the document should be.
        """
        if not self._script_loaded:
            return
        width, height = self._view.width(), self._view.height()
        if width <= 0 or height <= 0:
            return
        self._view.page().runJavaScript(
            f"window.applySize && window.applySize({width}, {height});"
        )

    def _on_terminal_ready(self, cols: int, rows: int) -> None:
        command, env = decorate(self._command)
        self._pty.start(command, cols, rows, cwd=self._start_cwd, env=env)
        self.is_pty_started = True
        self.pty_started.emit()

    def _on_cwd_changed(self, uri: str) -> None:
        path = path_from_osc7(uri)
        # Checked against the filesystem, not taken on trust: the payload
        # came out of the terminal, which on an SSH session means it came
        # from the remote host, and a path that is not a directory here would
        # only make the next split fail to start.
        if path and Path(path).is_dir():
            self._reported_cwd = path

    @property
    def current_directory(self) -> str | None:
        """The directory a pane split off this one should start in.

        None when the shell has never reported one and this pane was not
        given a starting directory either - a shell qtxterm has no hook for,
        or one running something that has taken the prompt over.
        """
        return self._reported_cwd or self._start_cwd

    def _on_context_menu_requested(self, pos: QPoint) -> None:
        self.context_menu_requested.emit(self._view.mapToGlobal(pos))

    def _on_selection_changed(self, text: str) -> None:
        self._selection = text

    @property
    def selection(self) -> str:
        """The terminal's current selection, as last pushed by xterm.js."""
        return self._selection

    def copy_selection(self) -> bool:
        """Put the selection on the clipboard. False if nothing is selected."""
        if not self._selection:
            return False
        QGuiApplication.clipboard().setText(self._selection)
        return True

    def paste(self, text: str) -> None:
        """Feed `text` to the terminal as if pasted with the mouse or keyboard."""
        if not text:
            return
        self._view.page().runJavaScript(
            f"window.pasteText && window.pasteText({json.dumps(text)});"
        )

    def paste_from_clipboard(self) -> None:
        self.paste(QGuiApplication.clipboard().text())

    def open_link(self, uri: str) -> bool:
        """Open a URL Ctrl+clicked in the output, in the system browser.

        The system browser rather than a qtxterm browser tab, even though the
        app has them. Two reasons, and the second is the one that settles it:
        it is what every other terminal does, and the URL is untrusted output,
        so the sandboxed browser the user already keeps their extensions and
        blocklists in is the better place for it than this app's embedded
        engine.

        Returns whether it was opened, so a caller can tell a refused scheme
        from a successful launch.
        """
        url = QUrl(uri.strip())
        if not url.isValid() or url.scheme().lower() not in OPENABLE_URL_SCHEMES:
            return False
        QDesktopServices.openUrl(url)
        return True

    def view_origin_in(self, ancestor: QWidget) -> QPoint:
        """Where this pane's *page* starts, in `ancestor` coordinates."""
        return self._view.mapTo(ancestor, QPoint(0, 0))

    def set_background_geometry(
        self, x: int, y: int, tab_width: int, tab_height: int
    ) -> None:
        """Tell the page where this pane sits inside its tab.

        A background image spans the whole tab, but every pane is a separate
        page, so none of them can work this out alone - left to itself each
        would paint the entire picture and a split tab would show it once per
        pane. Only the tab widget knows the layout, so it pushes the numbers
        here.

        Measured from the web view rather than the pane, because the pane
        carries a border margin the page never sees.
        """
        if not self._script_loaded:
            self._pending_background_geometry = (x, y, tab_width, tab_height)
            return
        self._view.page().runJavaScript(
            "window.applyBackgroundGeometry && window.applyBackgroundGeometry("
            f"{x}, {y}, {tab_width}, {tab_height});"
        )

    def focus_pane(self) -> None:
        """Put the keyboard in this terminal.

        Two steps, because there are two layers between the pane and the
        keys. `setFocus()` on the view moves Qt's focus off whatever had it -
        the tab bar, after a split - and `term.focus()` moves it again inside
        the page, to the hidden textarea xterm actually reads from. Without
        the second, the pane looks focused and types nowhere.

        A pane split off a moment ago has no page yet, and runJavaScript
        against it is silently dropped, so the request is remembered and
        replayed from _on_script_loaded.
        """
        self._view.setFocus()
        if self._script_loaded:
            self._view.page().runJavaScript(
                "window.focusTerminal && window.focusTerminal();"
            )
        else:
            self._focus_when_loaded = True

    def show_find(self) -> None:
        """Open the find bar over this terminal and focus its input.

        The bar is part of the page, not a Qt widget stacked above the view:
        a Qt bar would take rows off the grid every time it appeared, and
        reflowing the shell's output is a high price for opening a search.
        """
        self._view.page().runJavaScript("window.showFind && window.showFind();")

    def hide_find(self) -> None:
        """Close the find bar, clear its highlights, and refocus the terminal."""
        self._view.page().runJavaScript("window.hideFind && window.hideFind();")

    def send_command(self, text: str) -> None:
        """Write a line to the PTY and submit it, as if the user typed it + Enter.

        Terminated with a bare CR, which is what the Enter key actually
        sends. CRLF submits *twice* - the shell accepts on the CR and again
        on the LF - so every command left an empty line behind it: a stray
        prompt in bash, a `>>` continuation prompt in PowerShell.
        """
        self._pty.write(f"{text}\r")

    def run_when_ready(self, callback) -> None:
        """Call `callback` once the PTY has started (immediately if it already has).

        The PTY only starts after an async round trip (QWebEngineView loads
        terminal.html -> xterm.js boots -> JS calls back into Python), so
        code that spawns a tab and immediately wants to feed it input (e.g.
        macros) can't just call send_command() right after new_tab() returns.
        """
        if self.is_pty_started:
            callback()
        else:
            self.pty_started.connect(callback)

    def shutdown(self) -> None:
        """Terminate the backing PTY process.

        Not done via closeEvent: a child widget embedded in a layout never
        receives closeEvent when its parent QMainWindow closes, only
        top-level windows do. Callers must invoke this explicitly.
        """
        self._pty.close()
