# A command palette as PyMOL+'s central command input

**Goal:** A VS Code-style command palette (Ctrl+Shift+P) becomes PyMOL+'s main way to give commands: newcomers find commands without knowing their names, experienced users work faster than in the old command line; command output moves to an optional bottom panel, the External GUI's quick buttons to a slim toolbar, and the External GUI becomes legacy, off by default behind a remembered setting.

**Architecture:** New modules in the `pymol3` package (introduced by `pymol3-dock-panels`) hold the palette, the bottom output panel, the toolbar, the layout toggles and the go-to mode; they build on `pymol3.ui` and `pymol.Qt`. The app's marked copy `distribution/edited/pmg_qt/pymol_qt_gui.py` gets only short `BEGIN EDITED CODE SEGMENT` hooks that start the new interface, pass feedback and progress on, and honour the External GUI setting at start.

**Tech Stack:** Python, `pymol.Qt` (PySide6 6.9 in the app), `pymol3.ui`, Bazel (`rules_python`), pytest with Qt's `offscreen` platform as in `tests/pymol3_ui/`.

**Spec:** The design approved in the brainstorming session of 2026-11-23, recorded in `## Design` below. Backlog source: the Notion list's "Adding a VS Code style command palette", "Adding command specific placeholder text to the CLI in PyMOL's external GUI" and "Go to … selection jump from Ctrl + G", merged into this feature.

## Design

**Why.** Today people do not know which commands exist: the External GUI's command line offers only Tab completion over command names and a static tooltip. The palette should make PyMOL's commands discoverable for newcomers and make experienced users clearly faster than the old command line.

**What the user sees.**

- **Palette.** Ctrl+Shift+P, or the search button in the toolbar, opens a popup above the viewer with a text field and a result list.
  - Search matches command names *and* their descriptions (from PyMOL's help texts), so "surface", "measure" or "distance" find the right command without its exact name. Recently run commands rank first.
  - Each result line shows the command, its argument hint and a one-line description, for example `color   color, selection — set the colour of atoms`. This replaces the backlog item "command-specific placeholder text".
  - Arguments get suggestions: names of loaded objects and selections, colour names, representations and other fixed value sets.
  - **Hybrid input (developer's choice, option C).** Typing works like a command line: a complete line such as `color red, chain A` runs on Enter. Picking a command from the list asks for **every positional argument in turn** (colour → which atoms), each pre-filled with its default and offered with suggestions; Tab or Enter accepts the shown value and moves on, so an optional argument costs one key. A value the search matched is filled in already: searching "surface" and picking `show` gives `show surface,` and asks only for the atoms.
  - Esc closes the palette without running anything.
- **Go to (Ctrl+G).** Opens the palette in go-to mode: the list starts with all loaded objects and named selections; the field also accepts addresses (`A/45`, `HEM`) and any selection string (`resn HEM within 5 of chain B`). Enter zooms the view to the target and makes it the current selection `sele`, as a click would, so the next command applies to it.
- **Bottom panel (output).** Ctrl+J or the bottom-panel toggle opens and closes it; closed by default. It shows PyMOL's output, read-only, selectable and copyable, with Clear and Search. Python tracebacks and `Error:` lines are shown in red. PyMOL catches command errors and only prints them, so the panel watches the output: on **any** traceback or `Error:` line, whether from the palette, a script, a plugin or a mouse action, it opens by itself and shows it. A "Don't open on errors" option in the panel turns this off for noisy plugins. Commands are entered only through the palette: the panel has no command line.
- **Toolbar.** A slim, standard Qt toolbar below the menu bar, which the user can hide or move:
  - on the left, a search button with a magnifying glass, styled as a field ("Search commands… Ctrl+Shift+P"), which opens the palette;
  - the External GUI's quick buttons with icons and text: Reset, Zoom, Orient, Draw/Ray, Unpick, Deselect, Rock, Get View, the movie controls (`|<`, `<`, Stop, Play, `>`, `>|`, MClear), Builder, Properties, Rebuild; every one also exists as a palette entry;
  - on the right, VS Code's three layout toggles: left side, bottom panel, right side. Left and right show or hide every `pymol3` panel docked in that area; bottom shows or hides the output panel.
- **Status bar.** The progress bar and the red Abort button move from the External GUI into the window's status bar, always visible, so a long ray trace or calculation can always be stopped.
- **External GUI as legacy.** A remembered setting, **Display → External GUI → Show at start**, decides whether the External GUI appears. It defaults to off for **every** installation, updated ones included: the app cannot tell an update from a fresh install without installer changes. At the first start of the version that turns it off, a one-time notice says "The External GUI is now off. Commands: Ctrl+Shift+P, output: Ctrl+J" with a button that switches it back on; the notice's having been shown is remembered in the same `QSettings` store. Everything it offered stays reachable: commands through the palette, output in the bottom panel, buttons in the toolbar, progress in the status bar.

**Approaches considered.**

- **A. Own code in `pymol3`, small hooks in the upstream GUI (chosen).** The new interface lives in `pymol3` modules and is tested on its own; `pymol_qt_gui.py`'s marked copy gets a few short hooks. Upstream changes stay easy to port and `//distribution/edited:edited_base_test` rarely fails.
- B. Everything in the upstream GUI file. Fastest at first, but hundreds of marked lines; every upstream change to `pymol_qt_gui.py` becomes a laborious port. Rejected.
- C. A plugin with no upstream edits. Plugins load after the window is shown, so the External GUI would flash at start, and a user who disables the plugin loses the central input. Rejected.

**Decisions made with the developer.**

- Option C for the input: typing like a command line, step-by-step arguments when a command is picked from the list.
- The palette takes Ctrl+Shift+P from PyMOL's editing shortcut (replace the picked atom with phosphorus, `modules/pymol/shortcut_dict.py`'s `CTSH-P`); that replacement stays reachable through the palette (`replace P,4,1`) and the Builder.
- A slim toolbar with a magnifying-glass search button and the quick buttons; layout toggles copied from VS Code.
- Tracebacks in red.
- Go-to mode accepts the loaded objects and selections and any selection string.
- Built with approach A.
- Every positional argument is asked in turn, pre-filled with its default; a value the search matched is filled in (reviewer question, accepted 2026-11-23).
- The External GUI is off for every installation, with a one-time notice and a button to bring it back; no installer changes (reviewer question, accepted 2026-11-23).
- The bottom panel opens on any traceback or `Error:` line, with a "Don't open on errors" option (reviewer question, accepted 2026-11-23).

**Calls made in the design (Claude's, open to correction).**

- The External GUI defaults to off in new installations; the setting is stored in the app's existing `QSettings('PyMOL-Open-Source', 'PyMOL-Open-Source')` (already used by `offer_to_remove_older_apps`).
- Ctrl+J toggles the bottom panel, as in VS Code.
- The bottom panel opens by itself on a failed command.
- After a go-to jump the target becomes `sele`.
- Progress and Abort live in the status bar, whatever the External GUI setting.
- Recent commands rank first in the palette. They are kept across restarts in the same `QSettings` store (the last 100 distinct command lines); the External GUI's in-memory history (`_setup_history`, at most 255 entries, not saved) stays as it is and is not merged with them.
- "Show at start" lives only in the menu (Display → External GUI → Show at start): the Qt GUI has no preferences dialog, and building one is not part of this feature.

**Facts from the code that bind the design.**

- The External GUI's `update_feedback()` (`distribution/edited/pmg_qt/pymol_qt_gui.py`, around line 974) is the only reader of `cmd._get_feedback()`, which hands each line out once, and the same timer runs the setting callbacks (the window title among them). The hook must pass each feedback batch on to `pymol3` listeners rather than add a second reader, and the timer must keep running when the External GUI is off.
- `update_progress()` drives the External GUI's progress bar and Abort button from `cmd.get_progress()`; the status bar uses the same source through a hook.
- `options.external_gui` (`modules/pymol/invocation.py`) already hides the External GUI on `-x`-style starts; the new setting must not override an explicit command-line choice.
- The edited copy applies to the app only; `modules/pmg_qt/pymol_qt_gui.py` is the upstream original checked by `distribution/edited/upstream.sha256`.

## Global Constraints

Quoted from AGENTS.md and the `pymol3-dock-panels` plan; every step holds them:

- "App: PySide6 stays at 6.9 (6.10+ drops macOS 12 and RHEL/AlmaLinux 8); Python 3.13."
- "`distribution/edited/` holds upstream PyMOL files with marked edits (`BEGIN EDITED CODE SEGMENT`)"; no file under `modules/pymol/`, `modules/pmg_qt/`, `modules/pmg_tk/`, `modules/chempy/` or `modules/pymol2/` changes.
- Never remove or change anything in PyMOL's existing command or Python API; only add. The palette runs commands through the same path as the command line.
- "New dependency versions only when they are at least 14 days old"; no new runtime dependency is planned.
- Python follows `opp-workflow:python-style`; `python3 .opp/style/check.py --committed` passes on each step's last push.
- "Pull requests get the Bazel check only."
- New files carry `SPDX-License-Identifier: BSD-3-Clause`.

## Scope

modules/pymol3/**
tests/pymol3_*/**
distribution/edited/pmg_qt/pymol_qt_gui.py
distribution/edited/BUILD.bazel
distribution/docs/website/**
tools/bazel/requirements.in
tools/bazel/requirements_lock*.txt

## Done

All four steps below are merged into `production`, and a fresh app install starts with the toolbar and palette, without the External GUI.

## Non-goals

- Changing the wheel's own GUI (`modules/pmg_qt/`): the hooks are in the app's edited copy only; wheel users get the `pymol3` modules but not the new default interface.
- Removing the External GUI or the in-viewport command line; both stay as legacy.
- Searching menus, settings or plugin actions in the palette (commands, quick buttons and go-to only, for now).
- User-defined key bindings or a keyboard-shortcut editor.
- Theming beyond what PyMOL's current Qt style gives (no new light/dark themes).
- The Tk GUI and `pymol -c`.

## Steps

Each step is one branch from `production` and one pull request into `production`; each step's own Superpowers plan goes to `.opp/plans/<branch>.md` when it starts. Every step leaves the app usable: the External GUI stays on by default until step 3, so nobody is left without a command input.

0. **Prerequisite (met):** `pymol3-dock-panels` merged into `production` (Convergent-Binding/pymol-plus#15), with the `pymol3` package and `pymol3.ui`.
1. **Palette** (`command-palette`): the popup, the command index (names, argument signatures, help descriptions), ranking with recent commands first, argument suggestions, the hybrid input, Ctrl+Shift+P, and the hook in the edited GUI that installs it. Done when the palette runs commands in the app beside the unchanged External GUI.
2. **Bottom panel and layout toggles** (`command-output-panel`): the output panel docked at the bottom through `pymol3.ui`, fed by the feedback hook; red tracebacks and `Error:` lines; Clear and Search; Ctrl+J; opening by itself on a failed command; the three layout toggles as actions (placed in the toolbar in step 3, reachable from the menu until then).
3. **Toolbar, status bar and the legacy setting** (`command-toolbar`): the toolbar with the search button, quick buttons and layout toggles; progress and Abort in the status bar; the "Show at start" setting, default off, honouring an explicit command-line choice.
4. **Go to** (`command-goto`): Ctrl+G and the go-to mode with objects, selections, addresses and selection strings; jump and `sele`.

## Review Focus

- **Feedback lost or shown twice.** With two consumers of PyMOL's output, a line may disappear from one view or the setting callbacks may stop when the External GUI is off. Each step 2 test feeds a batch through the hook and checks both views and a setting callback.
- **Ctrl+Shift+P swallowed by the viewer.** The OpenGL widget handles keys itself; the shortcut must win while the viewer has focus and while the palette is closed. A test sends the key to the viewer widget offscreen.
- **A step-by-step argument run that never ends.** Commands with arguments PyMOL cannot describe (no signature, `*args`) must fall back to free typing; a command without positional arguments runs at once.
- **Startup with the External GUI off.** No flash of the External GUI, `-x`-style command-line options still win, and the one-time notice shows exactly once.
- **The panel opening too often.** A burst of error lines opens the panel once, and "Don't open on errors" holds across restarts.

## Acceptance criteria

- Ctrl+Shift+P and the toolbar's search button open the palette from anywhere in the main window, the viewer included.
- Typing "surface" lists `show`/`hide` with surface among the top results; typing a full command line and Enter runs it.
- Picking `color` from the list asks for the colour, then for the atoms, each with suggestions, and runs the command.
- Ctrl+G lists loaded objects and selections; entering `A/45` or a selection string zooms to it and sets `sele`.
- Searching "surface" and picking `show` fills in `show surface,` and asks only for the atoms; Tab or Enter on a pre-filled default moves on.
- Ctrl+J opens and closes the bottom panel; any traceback or `Error:` line opens it and shows in red, unless "Don't open on errors" is set.
- The toolbar holds the search button, every former quick button and the three layout toggles; progress and Abort show in the status bar during a ray trace.
- A fresh install and an updated one both start without the External GUI; the one-time notice shows once and its button brings the External GUI back; switching "Show at start" on brings it back after a restart.
- No upstream file changes (`modules/` outside `modules/pymol3/`); `bazel test //...` and `bazel test //distribution/...` pass.

## Verification

- `bazel test //tests/...` runs each step's offscreen Qt tests for `pymol3` (palette ranking, argument flow, feedback fan-out, toggles, go-to parsing).
- `bazel test //distribution/...` passes, `//distribution/edited:edited_base_test` included, and the app's headless smoke test still starts.
- `python3 .opp/style/check.py --committed` reports no findings.
- By hand on Windows (and macOS for the shortcut's Cmd mapping): the acceptance criteria above, in a freshly installed app.
