(function () {
  const params = new URLSearchParams(location.search);
  const themeParam = params.get("theme");
  const theme = themeParam
    ? JSON.parse(themeParam)
    : { background: "#1e1e1e", foreground: "#d4d4d4" };
  const fontFamily =
    params.get("fontFamily") || "Consolas, 'Cascadia Mono', monospace";
  const fontSize = parseInt(params.get("fontSize"), 10) || 14;
  // Not `|| 1000`: 0 is a real choice here - keep nothing but what's on
  // screen - and falsy, so it would silently become the default.
  const requestedScrollback = parseInt(params.get("scrollback"), 10);
  const scrollback = Number.isFinite(requestedScrollback)
    ? requestedScrollback
    : 1000;

  const backgroundImage = params.get("backgroundImage") || "";
  const rawOpacity = parseInt(params.get("backgroundOpacity"), 10);
  const backgroundOpacity = Number.isFinite(rawOpacity) ? rawOpacity : 30;

  // "#rrggbb" -> "rgba(r, g, b, a)", so the theme colour can be laid over an
  // image at partial strength. Anything unparseable falls back to opaque
  // black rather than producing invalid CSS, which would drop the whole
  // declaration and show the image at full strength behind the text.
  const withAlpha = (hex, alpha) => {
    const match = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || "");
    if (!match) return `rgba(0, 0, 0, ${alpha})`;
    const [r, g, b] = match.slice(1).map((part) => parseInt(part, 16));
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
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

  // Colors for the find bar and for the highlight xterm paints on each match.
  // Both are derived from the terminal theme rather than fixed, so a find bar
  // is never a light rectangle on a black terminal.
  //
  // *On*, not behind: xterm draws search decorations over the glyphs, so an
  // opaque highlight erases the text it is pointing at. Measured - reusing
  // the theme's `selectionBackground` looked like the safe choice and turned
  // every match into a solid white block on VS Code Dark High Contrast, whose
  // selection colour is #ffffff. The tint has to be translucent, and the
  // alpha is the whole design:
  //
  //   - yellow is the one hue every theme here keeps clear of its background
  //     and its foreground, so it marks a match without being mistaken for
  //     either
  //   - 0x40 (25%) for the crowd, 0x80 (50%) for the current match - enough
  //     separation to find the active one at a glance, still transparent
  //     enough to read the text through
  //   - the active match's border is the theme's *foreground*, which is
  //     contrasty against the background by definition, so the outline holds
  //     up in a theme nobody has tried yet
  let findDecorations = {};

  const applyFindTheme = (t) => {
    const root = document.documentElement.style;
    root.setProperty("--find-bg", t.background);
    root.setProperty("--find-fg", t.foreground);
    root.setProperty("--find-accent", t.blue);
    root.setProperty("--find-error", t.red);
    findDecorations = {
      matchBackground: `${t.yellow}40`,
      matchBorder: t.yellow,
      activeMatchBackground: `${t.yellow}80`,
      activeMatchBorder: t.foreground,
      // Not optional, despite reading like it. The addon passes these
      // straight to registerDecoration as overviewRulerOptions.color, and an
      // undefined color throws from inside the search - which surfaced as
      // "No results" on a query with three matches, because the throw
      // happened while selecting the match it had already found. They are
      // inert until the terminal is given an overviewRulerWidth, so this
      // costs nothing but keeps the search from breaking.
      matchOverviewRuler: t.yellow,
      activeMatchColorOverviewRuler: t.foreground,
    };
  };

  // Paint the page ground too, not just xterm's canvas - otherwise the
  // margin around the grid stays default-white on dark themes.
  //
  // With a background image the theme colour becomes a *veil* over it rather
  // than the ground itself: the image is the bottom layer and a flat wash of
  // the theme background sits on top at (100 - strength), which is what keeps
  // text readable over a photograph. Done as a gradient layer rather than an
  // extra element so it stays one CSS property and cannot fall out of sync
  // with the terminal's own geometry.
  //
  // The image spans the whole *tab*, not each pane. Every pane is a separate
  // page, so left alone each one paints the entire picture and a tab split
  // three ways shows it three times. Instead Qt pushes each pane its own
  // rectangle within the tab (applyBackgroundGeometry) and the page draws
  // only its slice, so the panes reassemble into one continuous image.
  let pageBackground = theme.background;
  // Starts null rather than at the query-param value, so the first
  // applyPageBackground call below counts as a change and measures the
  // image. Seeding it with the real value made that call a no-op, the
  // measurement never ran, and every pane silently fell back to painting the
  // whole picture itself - the exact bug this spanning code exists to fix.
  let pageImage = null;
  let pageOpacity = backgroundOpacity;
  // {x, y, width, height} of this pane inside its tab, in CSS pixels.
  let paneRect = null;
  // The image's intrinsic size, needed to reproduce `cover` by hand across
  // the tab rather than per pane. Measured once per image.
  let imageSize = null;

  const measureImage = (url, done) => {
    if (!url) {
      imageSize = null;
      done();
      return;
    }
    const probe = new Image();
    probe.onload = () => {
      imageSize = { width: probe.naturalWidth, height: probe.naturalHeight };
      done();
    };
    // A missing or unreadable file falls back to per-pane `cover` rather
    // than leaving the background half-applied.
    probe.onerror = () => {
      imageSize = null;
      done();
    };
    probe.src = url;
  };

  const paintBackground = () => {
    const body = document.body.style;
    body.backgroundColor = pageBackground;
    if (!pageImage) {
      body.backgroundImage = "none";
      return;
    }
    const veil = withAlpha(pageBackground, (100 - pageOpacity) / 100);
    body.backgroundImage = `linear-gradient(${veil}, ${veil}), url("${pageImage}")`;
    body.backgroundRepeat = "no-repeat";

    const canSpan =
      paneRect && imageSize && paneRect.width > 0 && paneRect.height > 0;
    if (!canSpan) {
      // Before the first geometry arrives, or without a measurable image.
      body.backgroundSize = "auto, cover";
      body.backgroundPosition = "0 0, center";
      return;
    }
    // `cover` computed against the tab, then shifted by where this pane sits
    // in it. Doing it by hand is the only way: CSS `cover` always resolves
    // against the element's own box, which is exactly the per-pane repeat
    // being avoided here.
    const scale = Math.max(
      paneRect.tabWidth / imageSize.width,
      paneRect.tabHeight / imageSize.height,
    );
    const drawWidth = imageSize.width * scale;
    const drawHeight = imageSize.height * scale;
    const left = (paneRect.tabWidth - drawWidth) / 2 - paneRect.x;
    const top = (paneRect.tabHeight - drawHeight) / 2 - paneRect.y;
    // Two layers: the veil covers this pane, the image is positioned across
    // the tab. Their sizes and positions are per-layer and comma separated.
    body.backgroundSize = `auto, ${drawWidth}px ${drawHeight}px`;
    body.backgroundPosition = `0 0, ${left}px ${top}px`;
  };

  const applyPageBackground = (background, image, opacity) => {
    const imageChanged = image !== pageImage;
    pageBackground = background;
    pageImage = image;
    pageOpacity = opacity;
    if (imageChanged) {
      measureImage(image, paintBackground);
    } else {
      paintBackground();
    }
  };

  // Called from Python (TerminalWidget.set_background_geometry) whenever this
  // pane's place in its tab changes - a split, a resize, a divider drag, a
  // pane moved or closed.
  window.applyBackgroundGeometry = function (x, y, tabWidth, tabHeight) {
    paneRect = { x, y, tabWidth, tabHeight, width: tabWidth, height: tabHeight };
    paintBackground();
  };

  applyPageBackground(theme.background, backgroundImage, backgroundOpacity);
  applyScrollbarTint(theme.foreground);
  applyFindTheme(theme);

  // xterm gets a transparent background when an image is set, so the image
  // and its veil show through; without an image it keeps the solid colour,
  // so the no-image case renders exactly as it did before this existed.
  const termTheme = (t, image) =>
    image ? { ...t, background: "#00000000" } : t;

  const term = new Terminal({
    cursorBlink: true,
    // Required by the search addon: the match highlights are drawn with
    // registerMarker/registerDecoration, which xterm 5.5 still classes as
    // proposed API and refuses to run without this. Without it every search
    // throws *after* finding its matches, which reads as "No results" on a
    // query that plainly matches. Safe here because xterm is vendored at a
    // pinned version, so the proposed API cannot change underneath us - see
    // xterm/VENDORED.md.
    allowProposedApi: true,
    // Lets the grid sit on the page's background instead of painting an
    // opaque one of its own, which is what makes a background image
    // visible at all. Set at construction because xterm reads it once.
    allowTransparency: true,
    fontFamily,
    fontSize,
    scrollback,
    theme: termTheme(theme, backgroundImage),
  });
  const fitAddon = new FitAddon.FitAddon();
  term.loadAddon(fitAddon);
  const searchAddon = new SearchAddon.SearchAddon();
  term.loadAddon(searchAddon);
  term.open(document.getElementById("terminal"));
  fitAddon.fit();

  const findBar = document.getElementById("find-bar");
  const findInput = document.getElementById("find-input");
  const findCount = document.getElementById("find-count");
  const findCase = document.getElementById("find-case");
  const findRegex = document.getElementById("find-regex");

  const setResultCount = (count, index) => {
    if (!findInput.value) {
      findCount.textContent = "";
    } else if (count > 0) {
      findCount.textContent = `${index + 1} of ${count}`;
    } else {
      findCount.textContent = "No results";
    }
    findBar.classList.toggle(
      "no-results",
      Boolean(findInput.value) && count === 0,
    );
  };

  searchAddon.onDidChangeResults((results) => {
    setResultCount(results ? results.resultCount : 0, results ? results.resultIndex : -1);
  });

  const findOptions = (incremental) => ({
    caseSensitive: findCase.classList.contains("active"),
    regex: findRegex.classList.contains("active"),
    decorations: findDecorations,
    incremental,
  });

  // `incremental` keeps the current match anchored while the query grows, so
  // typing "err" doesn't walk three matches on the way to the word you meant.
  // It only applies to typing - the next/previous buttons must actually move.
  const runFind = (backwards, incremental) => {
    if (!findInput.value) {
      searchAddon.clearDecorations();
      setResultCount(0, -1);
      return;
    }
    const options = findOptions(incremental);
    try {
      if (backwards) {
        searchAddon.findPrevious(findInput.value, options);
      } else {
        searchAddon.findNext(findInput.value, options);
      }
    } catch (e) {
      console.error("find failed", e);
      // A half-typed regex ("[a" ) throws rather than simply not matching.
      // Reported as no results, which is what it is, instead of leaving the
      // count stale on a query that found nothing.
      setResultCount(0, -1);
    }
  };

  findInput.addEventListener("input", () => runFind(false, true));
  findInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      runFind(event.shiftKey, false);
    } else if (event.key === "Escape") {
      event.preventDefault();
      window.hideFind();
    }
  });

  const bindToggle = (button) => {
    button.addEventListener("click", () => {
      button.classList.toggle("active");
      button.setAttribute(
        "aria-pressed",
        String(button.classList.contains("active")),
      );
      // Re-run from where we are rather than from the top of the buffer.
      // The active match can still step forward by one - the addon resumes
      // from the current selection - but you stay in the same region of the
      // scrollback instead of being thrown back to the first match.
      runFind(false, true);
      findInput.focus();
    });
  };
  bindToggle(findCase);
  bindToggle(findRegex);

  const bindStep = (button, backwards) => {
    button.addEventListener("click", () => {
      runFind(backwards, false);
      findInput.focus();
    });
  };
  bindStep(document.getElementById("find-prev"), true);
  bindStep(document.getElementById("find-next"), false);
  document.getElementById("find-close").addEventListener("click", () => {
    window.hideFind();
  });

  // Called from Python (TerminalWidget.show_find / hide_find).
  window.showFind = function () {
    findBar.hidden = false;
    findInput.focus();
    // Selected rather than cleared, so the previous query is still there to
    // step through with Enter but is replaced by whatever you type next.
    findInput.select();
    if (findInput.value) runFind(false, true);
  };

  window.hideFind = function () {
    findBar.hidden = true;
    searchAddon.clearDecorations();
    // Focus has to go back explicitly: it is sitting in the find input, so
    // without this the terminal is visible but not typeable.
    term.focus();
  };

  window.isFindOpen = function () {
    return !findBar.hidden;
  };

  const linkTip = document.getElementById("link-tip");
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform || "");

  const showLinkTip = (event, uri) => {
    linkTip.textContent = uri;
    const hint = document.createElement("div");
    hint.className = "link-hint";
    hint.textContent = `${isMac ? "Cmd" : "Ctrl"}+click to open`;
    linkTip.appendChild(hint);
    linkTip.hidden = false;

    // Placed after unhiding, because a hidden element measures 0x0 and the
    // tip would be flipped by the edge checks below on every first hover.
    const pad = 12;
    const box = linkTip.getBoundingClientRect();
    let left = event.clientX + pad;
    let top = event.clientY + pad;
    // Kept inside the viewport: a link near the right edge is exactly the
    // one whose full URL you wanted to read.
    if (left + box.width > window.innerWidth) {
      left = Math.max(0, event.clientX - box.width - pad);
    }
    if (top + box.height > window.innerHeight) {
      top = Math.max(0, event.clientY - box.height - pad);
    }
    linkTip.style.left = `${left}px`;
    linkTip.style.top = `${top}px`;
  };

  const hideLinkTip = () => {
    linkTip.hidden = true;
  };

  // Called from Python (TerminalWidget.focus_pane). Focusing the
  // QWebEngineView alone leaves the keyboard on the page rather than in the
  // terminal - xterm reads keystrokes from a hidden textarea, and only this
  // puts the caret there.
  window.focusTerminal = function () {
    term.focus();
  };

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
    const image = options.backgroundImage || "";
    term.options.theme = termTheme(options.theme, image);
    term.options.fontFamily = options.fontFamily;
    term.options.fontSize = options.fontSize;
    // Lowering this drops the oldest lines immediately, which is the point:
    // a terminal left open for days is holding every one of them.
    term.options.scrollback = options.scrollback;
    applyPageBackground(
      options.theme.background,
      image,
      options.backgroundOpacity,
    );
    applyScrollbarTint(options.theme.foreground);
    applyFindTheme(options.theme);
    // Decorations already on screen were painted in the old theme's colors,
    // so an open find has to be re-run to pick the new ones up.
    if (!findBar.hidden) runFind(false, true);
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

    // Clickable URLs. Loaded here rather than beside the other addons
    // because opening one means calling Python, and the bridge only exists
    // inside this callback.
    //
    // Ctrl+click (Cmd on macOS), not a plain click, following VS Code's
    // terminal, Windows Terminal and iTerm2. A bare click has a job already -
    // placing the cursor and starting a selection - and terminal output is
    // full of URLs you did not mean to visit. The handler is still called on
    // an unmodified click, and returning without acting leaves the click to
    // do its normal thing.
    const openLink = (event, uri) => {
      if (!event.ctrlKey && !event.metaKey) return;
      hideLinkTip();
      bridge.openLink(uri);
    };

    term.loadAddon(
      new WebLinksAddon.WebLinksAddon(openLink, {
        hover: (event, uri) => showLinkTip(event, uri),
        leave: () => hideLinkTip(),
      }),
    );

    bridge.loaded();
  });
})();
