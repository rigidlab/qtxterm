# Vendored files

| File | Source | Version |
|---|---|---|
| `xterm.js` | https://unpkg.com/@xterm/xterm@5.5.0/lib/xterm.js | 5.5.0 |
| `xterm.css` | https://unpkg.com/@xterm/xterm@5.5.0/css/xterm.css | 5.5.0 |
| `addon-fit.js` | https://unpkg.com/@xterm/addon-fit@0.10.0/lib/addon-fit.js | 0.10.0 |
| `addon-search.js` | https://unpkg.com/@xterm/addon-search@0.15.0/lib/addon-search.js | 0.15.0 |
| `addon-web-links.js` | https://unpkg.com/@xterm/addon-web-links@0.11.0/lib/addon-web-links.js | 0.11.0 |

`qwebchannel.js` is NOT vendored here — Qt auto-registers it as a resource
(`qrc:///qtwebchannel/qwebchannel.js`) whenever `QtWebChannel` is imported
alongside `QWebEngineView`, so it's loaded directly from that path in
`terminal.html`.

MIT licensed (xterm.js project). Its licence travels with the code it covers,
in [`LICENSE`](LICENSE) beside these files - MIT requires the notice to ship
with any copy, and these are copies. qtxterm's own licence is at the repo
root and does not replace it.

To upgrade, re-run the curl commands with a new version number, update this
table, and refresh `LICENSE` from
`https://unpkg.com/@xterm/xterm@<version>/LICENSE`.
