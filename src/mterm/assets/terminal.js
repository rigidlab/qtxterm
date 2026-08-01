(function () {
  const term = new Terminal({
    cursorBlink: true,
    fontFamily: "Consolas, 'Cascadia Mono', monospace",
    fontSize: 14,
    theme: { background: "#1e1e1e", foreground: "#d4d4d4" },
  });
  const fitAddon = new FitAddon.FitAddon();
  term.loadAddon(fitAddon);
  term.open(document.getElementById("terminal"));
  fitAddon.fit();

  new QWebChannel(qt.webChannelTransport, function (channel) {
    const bridge = channel.objects.bridge;

    term.onData((data) => bridge.sendInput(data));

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
