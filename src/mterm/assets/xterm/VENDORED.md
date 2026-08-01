# Vendored files

| File | Source | Version |
|---|---|---|
| `xterm.js` | https://unpkg.com/@xterm/xterm@5.5.0/lib/xterm.js | 5.5.0 |
| `xterm.css` | https://unpkg.com/@xterm/xterm@5.5.0/css/xterm.css | 5.5.0 |
| `addon-fit.js` | https://unpkg.com/@xterm/addon-fit@0.10.0/lib/addon-fit.js | 0.10.0 |

`qwebchannel.js` is NOT vendored here — Qt auto-registers it as a resource
(`qrc:///qtwebchannel/qwebchannel.js`) whenever `QtWebChannel` is imported
alongside `QWebEngineView`, so it's loaded directly from that path in
`terminal.html`.

MIT licensed (xterm.js project). To upgrade, re-run the curl commands with a
new version number and update this table.
