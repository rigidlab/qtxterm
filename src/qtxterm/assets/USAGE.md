# qtxterm - Usage

A tabbed terminal with one-click command buttons and reusable command presets.

## Terminals and tabs

Shortcuts below are the Windows and Linux ones. macOS uses Command in
place of Ctrl and drops the Shift - `Cmd+T`, `Cmd+W`, `Cmd+F`. The full
side-by-side list is under [Keyboard shortcuts](#keyboard-shortcuts).

| Action | How |
|---|---|
| New tab (default shell) | `Ctrl+Shift+T`, or the `+` button at the right of the tab bar |
| New tab (specific shell) | **File → New Terminal →** PowerShell / Command Prompt / Git Bash / WSL: *distro* |
| New browser tab | **File → New Browser** |
| Close tab | `Ctrl+Shift+W`, or the `x` on the tab |
| Next / previous tab | `Ctrl+Tab` / `Ctrl+Shift+Tab` |
| Go to tab 1-8, or the last | `Alt+1` ... `Alt+9`, or `Ctrl+Alt+1` ... |
| Rename a tab | Double-click the tab |
| Find in the scrollback | `Ctrl+Shift+F` |
| Copy / paste | `Ctrl+Shift+C` / `Ctrl+Shift+V` |
| Bigger / smaller / default text | `Ctrl+=` / `Ctrl+-` / `Ctrl+0` |
| Split the pane | Right-click → **Pane → Split**, or see [Split panes](#split-panes) |
| Close a pane | `Alt+Shift+W`, or right-click → **Pane → Close** |
| Move the keyboard between panes | `Alt+←` `Alt+→` `Alt+↑` `Alt+↓` |
| Move a pane | Right-click → **Pane → Move Left/Right** (or Up/Down) |
| Pull a pane into its own tab | Right-click → **Pane → Move to New Tab** |

Only shells actually installed on your machine appear under **New Terminal**,
and every installed WSL distro gets its own entry (`WSL: Ubuntu-22.04`).
Docker Desktop's `docker-desktop` and `docker-desktop-data` are left out -
they're data-only and give no usable shell.

Tabs are labelled tmux-style as `index:shell` - `0:powershell`, `1:bash`,
`2:cmd`. Hover a tab to see what the shell is reporting (usually the current
directory or running command); that goes in the tooltip rather than the
label, since some shells report a full path and would stretch the tab bar.

Double-click a tab to rename it - useful once several tabs run the same
shell and `0:powershell` / `1:powershell` stop telling them apart. The index
prefix stays, and renumbering keeps your name attached to the right tab.
Leave the box blank to go back to the automatic name. A rename sticks: a
browser tab that keeps renaming itself from the page host won't overwrite
it.

`Ctrl+Shift+T` and `Ctrl+Shift+W` are used instead of plain `Ctrl+T`/`Ctrl+W`
on purpose: bash and readline bind `Ctrl+W` to "delete previous word", so
reusing it for "close tab" would break normal shell line-editing.

qtxterm opens with no terminal - you choose what to start, and closing the
last tab leaves the window open rather than quitting. An empty window tells
you how to open one: `Ctrl+Shift+T` or **File → New Terminal**. The `+`
button isn't available there - Qt only draws it alongside existing tabs.

## Split panes

A tab can hold several panes side by side. Right-click a terminal and pick
**Pane → Split Right** or **Split Down**, or use a keyboard chord -
there are two pairs and either works:

- `Ctrl+Shift+|` splits **right** - a vertical bar for a vertical divider
- `Ctrl+Shift+_` splits **down** - an underscore for a horizontal one
- `Alt+Shift++` splits right, `Alt+Shift+-` splits down, matching Windows
  Terminal

Everything that rearranges panes lives under that one **Pane** group.
Splits nest, so you can build columns of rows. Drag the divider to resize.

Browser panes split too, and a split gives you **another pane of the same
kind** - splitting a browser gives a browser, splitting a terminal gives a
terminal. In a browser pane the shortcuts are the only route: right-clicking
a web page shows Chromium's own menu, which you want for links and images.

`Alt+←` `Alt+→` `Alt+↑` `Alt+↓` move the keyboard between panes. They go by
where panes actually sit on screen, not by the order they were created, so
`Alt+→` lands on the pane genuinely to the right even in a nested split. There
is no wraparound - from the rightmost pane, `Alt+→` stays put.

A new pane takes the keyboard as soon as it opens, whether it came from a
split or a new tab, so you can type into it straight away without clicking
first.

The pane you last clicked or typed in is the **active** one, outlined in the
highlight colour whenever a tab has more than one. That outline matters:
sidebar buttons, the Command menu and Selection Actions all go to the active
pane, so it answers "where will this land?".

**Pane → Move Left/Right** (labelled Up/Down in a stacked split) swaps the
active pane with its neighbour. **Move to New Tab** pulls it out into a tab
of its own - the usual fix for "I split the wrong one". Either way the
pane keeps its shell, scrollback and running processes; only its container
changes.

Panes can't be dragged with the mouse. Neither can Windows Terminal's,
iTerm2's or tmux's - it needs a custom drag-and-drop layer, and the menu
commands cover the cases that actually come up.

**Pane → Close** (`Alt+Shift+W`) closes just that terminal; closing the last
pane closes the tab. `Ctrl+Shift+W` still closes the whole tab, panes and
all. `Alt+Shift+W` rather than a `Ctrl` chord, because closing a pane
sits next to the `Alt+Shift` splits above it.

## Keyboard shortcuts

Every shortcut, on each platform. The two columns differ more than a
find-and-replace would suggest, and the reason is worth a sentence:

- **On Windows and Linux the shell owns `Ctrl`+letter.** `Ctrl+C` interrupts,
  `Ctrl+W` deletes a word, `Ctrl+F` moves forward a character. So qtxterm's
  own actions take `Ctrl+Shift`, exactly as Windows Terminal, GNOME Terminal
  and VS Code's terminal do.
- **On macOS the opposite holds.** The shell uses Control and Command is
  free, so the binding is plain `Cmd`+letter, like every other Mac app. In
  particular `Cmd+C` is copy while Control+C still interrupts, because they
  are different keys.

| Action | Windows / Linux | macOS |
|---|---|---|
| New tab | `Ctrl+Shift+T` | `Cmd+T` |
| Close tab | `Ctrl+Shift+W` | `Cmd+W` |
| Next tab | `Ctrl+Tab` | `Ctrl+Tab` or `Cmd+Shift+]` |
| Previous tab | `Ctrl+Shift+Tab` | `Ctrl+Shift+Tab` or `Cmd+Shift+[` |
| Go to tab 1-8, or the last with 9 | `Alt+1`..`Alt+9` or `Ctrl+Alt+1`..`9` | `Cmd+1`..`Cmd+9` |

Where two chords are listed they both work on purpose. `Alt+1` is GNOME
Terminal's and `Ctrl+Alt+1` is Windows Terminal's, and people arrive with
one or the other already in their fingers.
| Find | `Ctrl+Shift+F` | `Cmd+F` |
| Copy | `Ctrl+Shift+C` or `Ctrl+Insert` | `Cmd+C` |
| Paste | `Ctrl+Shift+V` or `Shift+Insert` | `Cmd+V` |
| Bigger text | `Ctrl+=` or `Ctrl+Shift+=` | `Cmd+=` or `Cmd+Shift+=` |
| Smaller text | `Ctrl+-` | `Cmd+-` |
| Default text size | `Ctrl+0` | `Cmd+0` |
| Split right | `Alt+Shift++` | `Cmd+D` |
| Split down | `Alt+Shift+-` | `Cmd+Shift+D` |
| Close pane | `Alt+Shift+W` | `Cmd+Shift+W` |
| Move between panes | `Alt+←` `Alt+→` `Alt+↑` `Alt+↓` | `Cmd+Opt+←` and friends |
| Follow a link | `Ctrl+click` | `Cmd+click` |

On Windows and Linux the splits have a second pair, `Ctrl+Shift+|` for right
and `Ctrl+Shift+_` for down, which read as what they do - a vertical bar for
a vertical divider, an underscore for a horizontal one.

Two macOS choices are worth calling out. Next tab is a physical `Ctrl+Tab`
there, not `Cmd+Tab`, which belongs to the OS application switcher. And
`Cmd+D` / `Cmd+Shift+D` for splitting come from iTerm2 rather than from the
Windows chords, since that is what Mac terminal users already have in their
fingers.

## Browser tabs

**File → New Browser** opens a web page in a tab beside your terminals. Type
in the address bar and press Enter: a full URL loads as-is, a bare host like
`example.com` or `localhost:8080` gets `https://`, and anything else - words
with spaces, say - becomes a search rather than a broken URL. The `←` `→` `⟳`
buttons are back, forward, and reload.

Browser tabs are labelled by host (`1:example.com`), with the page title in
the tooltip. Commands and Selection Actions do nothing while a browser is the
active pane - there's no shell to send them to. They don't quietly pick some
other terminal in the tab either, which would run your command somewhere you
weren't looking; click the terminal pane you meant first.

## Commands vs. Macros

Both are the same underlying thing - a named list of shell lines - but they
serve different jobs, and each preset is one or the other:

- **Command** - runs in the terminal tab you're *already working in*, and you
  stay in it. For quick, short interactions: `git status`, `clear`.
- **Macro** - always opens a *fresh tab* and runs there. For anything
  long-running or disruptive that shouldn't hijack your current session:
  a dev server, a build, a deploy.

## Running them

- **Sidebar buttons** - one click sends that Command to the active terminal.
  The sidebar is the curated view: only Commands you've pinned with *Show in
  sidebar* appear there.
- **Right-click in a terminal → Command** - every Command, grouped the
  same way as the sidebar, without leaving the terminal you're typing in.
  Unlike the sidebar this lists *all* of them, pinned or not. Picking one
  sends it to that terminal. The same menu has **Copy** and **Paste** (see
  below).
- **Macros menu** - every Macro. Picking one opens a new tab and runs it.

The Commands menu in the menu bar is management-only (New Command...,
Manage Commands..., Show Sidebar) - it doesn't list individual Commands.

Show or hide the sidebar with **Commands → Show Sidebar**. Closing it from
its own title-bar button works too - either way it just hides, and the menu
item flips back to unchecked so you can bring it back.

## Copy and paste

`Ctrl+Shift+C` and `Ctrl+Shift+V`, or right-click for **Copy** and **Paste**.
`Ctrl+Insert` and `Shift+Insert` work too. On macOS it is plain `Cmd+C` and
`Cmd+V`.

`Ctrl+C` is deliberately left alone on Windows and Linux: it is the
interrupt, and a terminal that stole it to mean copy would be unable to stop
a running command. macOS has no such clash, because copy is `Cmd+C` there
while the interrupt is Control+C - two different keys.

Copying with nothing selected does nothing at all rather than emptying the
clipboard, which matters most on macOS where the binding is a bare `Cmd+C`.

- **Copy** takes the text you've selected with the mouse. It's greyed out
  when nothing is selected.
- **Paste** inserts the clipboard at the cursor without pressing Enter for
  you, so you can check a pasted command before running it. Multi-line
  clipboard text is handed to the terminal as a paste, not as typing, so
  shells and editors that use bracketed paste treat it correctly.

## Find in the scrollback

`Ctrl+Shift+F` opens a find bar in the top-right corner of the active
terminal. It searches the whole scrollback, not just the lines on screen, so
it will find something that scrolled past a thousand lines ago - as far back
as your scrollback setting keeps.

| Key | What |
|---|---|
| `Ctrl+Shift+F` | Open the find bar (again to re-focus it) |
| `Enter` | Next match |
| `Shift+Enter` | Previous match |
| `Esc` | Close, clear the highlights, and put the cursor back in the terminal |

`Aa` makes the search case-sensitive, `.*` treats what you typed as a regular
expression. The counter reads `3 of 17`, or `No results` with the box outlined
in red.

Every match is tinted, and the one you are on is brighter with an outline
around it. Both are drawn in the theme's own colors, so the bar and the
highlights follow whatever theme you have set - including a theme change while
the bar is open.

Typing extends the current match rather than jumping ahead on every keystroke,
so searching for `error` doesn't walk you through three matches on the way to
finishing the word.

`Ctrl+Shift+F` rather than `Ctrl+F` because `Ctrl+F` is forward-char in
bash and readline, and is bound to something in most full-screen apps. Find
does nothing in a browser pane - there is no scrollback to search, and it
won't quietly search a terminal you aren't looking at.

## Clickable links

A URL in the output is a link. Hover it and it underlines, with a tip showing
where it goes; **Ctrl+click** (Cmd+click on macOS) opens it in your normal
browser.

Ctrl rather than a plain click, matching VS Code's terminal, Windows Terminal
and iTerm2: an ordinary click already places the cursor and starts a
selection, and terminal output is full of URLs you did not mean to visit.

Only `http://` and `https://` are linkified, and only those are ever opened.
A bare `example.com` stays plain text. That is deliberate rather than
fussiness - what the terminal prints is not necessarily yours: over SSH it is
whatever the remote host chose to print. Restricting the schemes keeps a
printed line from launching a local handler.

The tip shows the whole target, which is worth reading before you click: a
link can wrap across two rows or run off the edge of the terminal, so the
text under your cursor is not always the whole URL.

Links open in your system browser rather than a qtxterm browser tab. That is
where your extensions, blocklists and logged-in sessions already live, and
it is the safer home for a URL that arrived as untrusted output.

## Selection Actions

Select text in a terminal, right-click, and pick **Selection** to run
something against it. The submenu shows what you selected at the top, so you
can see the payload before sending it. Two built-in examples ship:

- **Search Google** - opens your browser on a search for the selected text.
- **Explain with Claude** - opens a new tab running `claude -p`, with the
  selection as its input.

Each action is one of two kinds, chosen in **Manage Selection Actions...**:

| Kind | What it does | Where the selection goes |
|---|---|---|
| Open a URL | Substitutes into a URL template and opens the browser | Percent-encoded into `{selection}` |
| Send to a command's input | Runs a shell command in a tab | Standard input, via a temp file |

The selection is never pasted into a command line. That keeps text
containing quotes, `;`, `&&` or backticks from being executed as part of the
command, and means multi-line and very long selections work - both of which
break if text is spliced into a command. URL actions cap the selection at
1500 characters, since browsers and search engines reject longer URLs.

If the right-click **Selection** submenu is empty - an install created before
this feature existed keeps its own presets - open **Manage Selection
Actions...** and press **Add Examples**.

## Cron: running something on a schedule

The **Cron** menu runs a Macro you already have, on a schedule, for as long
as qtxterm is open.

Macros only, not Commands: a Command means "send this to the terminal I'm
working in", and a job firing at 2am has no terminal to mean. A Macro is
already defined as something that runs somewhere of its own.

A job is a name, a schedule, and the Macro to run. **New Cron Job...**
creates one; the schedule uses ordinary cron syntax:

    minute  hour  day-of-month  month  day-of-week

    */15 * * * *     every quarter of an hour
    0 9 * * 1-5      09:00 on weekdays
    0 2 1 * *        02:00 on the 1st of the month
    30 6 * * 0       06:30 on Sundays (0 and 7 both mean Sunday)

Each field takes `*`, a number, a range (`9-17`), a list (`0,30`), or a step
(`*/15`, `0-30/10`). The dialog previews the next run as you type, and
refuses to save a schedule it cannot read.

**Each job gets one tab, reused on every run**, named after the job. A job
firing every five minutes doesn't bury the tab bar, and the tab's scrollback
becomes that job's history. Close the tab and the next run opens a fresh one.

Jobs are listed in the Cron menu with a checkbox each, so you can turn one
off without opening a dialog. Give jobs a **Group** and they nest under it in
that menu, the same way Macros do - useful once you have a job per feed per
session. Ungrouped jobs stay at the top level. **Run Now** in the editor runs a job
immediately, which beats waiting until 2am to find out whether it works.

Two things to know:

- **Jobs only run while qtxterm is open**, and nothing missed while it was
  closed is caught up on. Launching after a weekend does not fire a burst of
  overdue jobs. For work that must happen whether or not you're at the
  machine, use the system's own scheduler.
- **A job names its Macro.** Rename or delete that Macro and the job says so
  in the status bar rather than running something else.

## Ordering

Each Manage dialog has **Move Up** and **Move Down** under its list. The
order there is the order they appear in - the Macros menu, the right-click
Command submenu, and the sidebar buttons.

One thing to know: entries with a **Group** are shown nested under that group
in the menu, so moving one only reorders it *within* its group. Moving a
grouped entry past an ungrouped one changes the stored order without visibly
changing the menu.

## Creating and editing

Each menu manages its own category: **Manage Commands...** under Commands,
**Manage Macros...** under Macros, **Manage Selection Actions...** under
Selection. Each dialog opens scoped to that category, so there's no way to
create a Command from the Macros dialog or vice versa.

| Field | What it does |
|---|---|
| Name | Label shown in menus and on sidebar buttons |
| Group | Optional. Groups presets into sidebar sections and menu submenus |
| Commands | One shell line per row |
| Show in sidebar | Commands only - pins it as a sidebar button. Macros never appear there |

Changes save immediately, and the sidebar and both menus refresh straight away.

Presets are stored as JSON, so you can hand-edit or back them up:

- Windows - `%LOCALAPPDATA%\qtxterm\presets.json`
- macOS - `~/Library/Application Support/qtxterm/presets.json`
- Linux - `~/.config/qtxterm/presets.json`

## Background image

**File -> Preferences... -> Background image** puts a picture behind the
terminal. **Image strength** controls how much of it shows through.

The theme colour is laid over the image as a veil rather than replaced by it,
so lowering the strength dims the picture toward your theme's normal
background. The default is 30%, because a photograph at full strength behind
text is unreadable - start there and raise it until it stops being
comfortable.

**The image spans the tab, not each pane.** Split a tab three ways and you
get one continuous picture with the dividers cutting across it, rather than
the same image repeated in every pane. Each tab shows the whole image again.

The path is stored, not a copy of the file, so replacing the image on disk
changes the background without touching the setting. Point it at a file that
no longer exists and you simply get a normal terminal rather than a broken
one. **Clear** removes it.

## Preferences

**File → Preferences...** sets the default shell, what happens when a shell
exits, the color theme, font, font size, scrollback, and the order of the
right-click menu.

### Default shell

Which shell new tabs open with - the startup tab, the `+` button,
`Ctrl+Shift+T`, and Macros. **System default** follows the OS
(`powershell.exe` on Windows, `$SHELL` elsewhere); otherwise pick any
detected shell, including a specific WSL distro. Existing tabs keep the
shell they started with, and **File → New Terminal** still opens whichever
shell you pick there regardless of this setting.

If the chosen shell later disappears - a WSL distro you removed - new tabs
quietly fall back to the system default rather than failing to open.

### When a shell exits

What happens to a pane once its shell finishes:

| Setting | What it does |
|---|---|
| Close it, unless the shell failed | The default. A shell you exited on purpose takes its pane with it; one that died leaves the pane open |
| Always close it | Even when the shell failed |
| Leave it open | What qtxterm did before this setting existed |

The default is the middle ground on purpose. Exiting a shell yourself means
you are finished with that pane, so keeping it costs a second keystroke. But
a shell that *died* has usually printed why, and closing its pane throws that
away exactly when you wanted to read it.

Only the pane closes, not the tab around it - unless it was the last pane, in
which case the tab goes too. The window still outlives its terminals either
way.

### Appearance

| Theme | Look |
|---|---|
| Qt Default | The original terminal colors, with your platform's native window chrome left untouched |
| VS Code Dark High Contrast | Pure black ground, saturated ANSI colors - VS Code's `hc-black` |
| VS Code Light+ | VS Code's default light theme |
| Solarized Dark | The classic low-contrast dark palette |
| Solarized Light | Solarized on its cream ground |

Everything except **Qt Default** themes the whole window - menus, tabs,
sidebar, and dialogs - not only the terminal grid. **Qt Default** deliberately
leaves the native look alone.

Changes apply immediately to every open tab, and are remembered for next time.

`Ctrl+=` and `Ctrl+-` resize the text without opening this dialog, and
`Ctrl+0` puts it back to the default. `Ctrl+Shift+=` zooms in too - it is
the same key with Shift held, which is how most people press "plus", and
every browser accepts both. There is only one stored size, so
zooming *is* editing the preference - which is why `Ctrl+0` returns to the
default rather than to whatever the dialog last held, since otherwise it
would have nothing to mean.

## What else is remembered

The window's size and position, and whether the Commands sidebar is showing,
are restored the next time you open qtxterm - alongside the appearance
settings above. They live next to your presets:

- Windows - `%LOCALAPPDATA%\qtxterm\window_state.ini`
- macOS - `~/Library/Application Support/qtxterm/window_state.ini`
- Linux - `~/.config/qtxterm/window_state.ini`

## How multiline presets run

Each line is typed into the terminal followed by Enter. Lines run strictly in
order, each finishing before the next begins - a preset starting with a
3-second sleep won't run its second line until that sleep is done.

Two differences from a real `.sh` or `.bat` script are worth knowing:

- **A failing line does not stop the rest.** There's no `set -e` equivalent;
  every line runs regardless of what came before.
- **Interactive prompts swallow the queued lines.** If a line triggers a
  password prompt, a `y/n` confirmation, or opens a full-screen app like
  `vim`, the lines waiting behind it get read as *answers to that prompt*
  rather than as commands. Keep prompting commands out of multiline presets,
  or run them by hand.
