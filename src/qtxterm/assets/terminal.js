(function () {
  const params = new URLSearchParams(location.search);
  const themeParam = params.get("theme");
  const theme = themeParam
    ? JSON.parse(themeParam)
    : { background: "#1e1e1e", foreground: "#d4d4d4" };
  const fontFamily =
    params.get("fontFamily") || "Consolas, 'Cascadia Mono', monospace";
  const fontSize = parseInt(params.get("fontSize"), 10) || 14;

  // Paint the page ground too, not just xterm's canvas - otherwise the
  // margin around the grid stays default-white on dark themes.
  const applyPageBackground = (background) => {
    document.body.style.background = background;
  };

  // xterm.js scrolls a plain div, so the bar is Chromium's own. Restyled
  // here rather than in terminal.html's stylesheet because Chromium does not
  // resolve CSS custom properties inside ::-webkit-scrollbar-* pseudo
  // elements - a var() rule silently uses its fallback, so the colour never
  // followed the theme. Concrete values are written into a <style> element
  // instead, and rewritten whenever the theme changes.
  //
  // The tint is the theme's own foreground: a fixed light thumb vanishes on
  // light themes and vice versa. 0x66 is ~40% alpha, matching VS Code's
  // terminal - quiet enough to ignore, strong enough to find.
  const scrollbarStyle = document.createElement("style");
  document.head.appendChild(scrollbarStyle);

  const applyScrollbarTint = (foreground) => {
    const fg = /^#[0-9a-f]{6}$/i.test(foreground || "") ? foreground : "#808080";
    scrollbarStyle.textContent = `
      .xterm-viewport::-webkit-scrollbar { width: 8px; }
      .xterm-viewport::-webkit-scrollbar-track { background: transparent; }
      .xterm-viewport::-webkit-scrollbar-thumb {
        background: ${fg}66; border-radius: 4px;
      }
      .xterm-viewport::-webkit-scrollbar-thumb:hover { background: ${fg}b3; }
    `;
  };

  applyPageBackground(theme.background);
  applyScrollbarTint(theme.foreground);

  const term = new Terminal({
    cursorBlink: true,
    fontFamily,
    fontSize,
    theme,
  });
  const fitAddon = new FitAddon.FitAddon();
  term.loadAddon(fitAddon);
  term.open(document.getElementById("terminal"));
  fitAddon.fit();

  // Called from Python (TerminalWidget.paste). Routed through term.paste()
  // rather than written straight to the PTY so bracketed paste mode is
  // honored - editors and shells that enable it need the text wrapped, or a
  // multi-line paste is read as a series of typed commands.
  window.pasteText = function (text) {
    term.paste(text);
  };

  // Called from Python (TerminalWidget.apply_appearance) to live-update an
  // already-open tab without reloading the page.
  window.applyAppearance = function (options) {
    term.options.theme = options.theme;
    term.options.fontFamily = options.fontFamily;
    term.options.fontSize = options.fontSize;
    applyPageBackground(options.theme.background);
    applyScrollbarTint(options.theme.foreground);
    fitAddon.fit();
    // A different font size means a different number of cells in the same
    // pixels, and the shell has to be told or it wraps to the old width.
    if (window.reportResize) window.reportResize();
  };

  new QWebChannel(qt.webChannelTransport, function (channel) {
    const bridge = channel.objects.bridge;

    term.onData((data) => bridge.sendInput(data));
    term.onTitleChange((title) => bridge.setTitle(title));
    term.onSelectionChange(() => bridge.setSelection(term.getSelection()));

    bridge.output.connect((data) => term.write(data));
    bridge.exited.connect((code) => {
      term.write(`\r\n[process exited with code ${code}]\r\n`);
    });

    // Sizing is driven from Qt, not from the page. Chromium skips layout for
    // a view in a background tab, so a terminal that asks the document how
    // big it is can get a stale answer - one row for a pane split into a tab
    // you aren't looking at - and the shell would start at that size. Qt
    // knows the real geometry, so it pushes it here (see
    // TerminalWidget._apply_size) and the container is sized explicitly.
    let started = false;
    window.reportResize = function () {
      if (started) bridge.resize(term.cols, term.rows);
    };
    window.applySize = function (width, height) {
      if (width <= 0 || height <= 0) return;
      const el = document.getElementById("terminal");
      el.style.width = width + "px";
      el.style.height = height + "px";
      fitAddon.fit();
      if (started) {
        bridge.resize(term.cols, term.rows);
      } else {
        started = true;
        bridge.ready(term.cols, term.rows);
      }
    };

    bridge.loaded();
  });
})();
