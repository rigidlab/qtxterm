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
  applyPageBackground(theme.background);

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

  // Called from Python (TerminalWidget.apply_appearance) to live-update an
  // already-open tab without reloading the page.
  window.applyAppearance = function (options) {
    term.options.theme = options.theme;
    term.options.fontFamily = options.fontFamily;
    term.options.fontSize = options.fontSize;
    applyPageBackground(options.theme.background);
    fitAddon.fit();
  };

  new QWebChannel(qt.webChannelTransport, function (channel) {
    const bridge = channel.objects.bridge;

    term.onData((data) => bridge.sendInput(data));
    term.onTitleChange((title) => bridge.setTitle(title));

    bridge.output.connect((data) => term.write(data));
    bridge.exited.connect((code) => {
      term.write(`\r\n[process exited with code ${code}]\r\n`);
    });

    const reportResize = () => {
      fitAddon.fit();
      bridge.resize(term.cols, term.rows);
    };
    window.addEventListener("resize", reportResize);

    bridge.ready(term.cols, term.rows);
  });
})();
