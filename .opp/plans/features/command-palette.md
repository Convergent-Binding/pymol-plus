# A command palette as PyMOL+'s central command input

> **For agentic workers:** this is a feature plan. Each step below gets its own plan, written with superpowers:writing-plans when the step starts, and is built with superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** In PyMOL+'s new GUI, a command palette (Ctrl+Shift+P) is the main way to give commands, so newcomers find commands without knowing their names and experienced users work faster than in the old command line, inside a calm, accessible window whose design the other panels share.

**Architecture:** GUI-free command logic, a shared design foundation (tokens, themes, icons) and the GUI (views and controllers) are separate parts of `pymol3`. The panes stay Qt dock widgets, because `pymol3.ui` hands them to plugins. The app's marked copy of `pymol_qt_gui.py` gets only short hooks. The branch `command-palette` is a prototype: a source of lessons, not a specification and not a base.

**Tech Stack:** Python 3.13, `pymol.Qt` (PySide6 6.9 in the app), Bazel (`rules_python`), pytest with Qt's `offscreen` platform (pytest-qt if step 1 adds it).

**Spec:** issue #16, `## Design` below, and the [GUI vision board](https://claude.ai/artifact/59LAigu97Z4jZ13MQyZPL4), version `1795900721-3b67`, which shows every state. Where they differ, this plan wins on behaviour and the board on look. This plan replaces the one of 2026-11-23, revised on 2026-11-25.

## Design

### Decided when the plan was approved (2026-11-28)

- **Recent must not rerun a command by accident.** While Recent shows, nothing is highlighted until the user moves with the arrow keys; until then, Enter and Tab do nothing. On a first start, the first common task is highlighted.
- **A single word is a search.** Typing `reinitialize` and pressing Enter starts its steps and its confirmation. A typed command line has a space or a comma, or matches no command; it runs on Enter without asking.
- **No trial for the rounded viewer corners.** Step 3 builds them directly, and they are checked like the rest of the step. If they do not work well on a platform, the owner decides whether the viewer gets square corners, and the board changes to match.

### Why

Today the External GUI's command line offers only Tab completion over command names and a static tooltip, so people do not know which commands exist. Success means that a newcomer gets from "surface" to a shown surface without knowing `show`, and that an experienced user runs or repeats a command in fewer keys than before.

**It has failed if** a stray key can discard work, a state can only be told by its colour, an existing plugin breaks, or the classic GUI changes.

### The palette

- **Opening.** Ctrl+Shift+P or the toolbar's search field opens it near the top of the viewer, 640 px wide, also while the viewer has the focus. Ctrl+Shift+P no longer runs PyMOL's `replace P,4,1`, which stays reachable as a command and through the Builder. Esc or a click outside closes it and runs nothing.
- **Before typing.** *Recent* lists the last five command lines and is hidden while there are none. *Common tasks* lists, in plain words with the command beside each: Load (`fetch`), Show (`show surface`), Color (`color`), Measure (`distance`), Export (`png`). Results replace both lists while the user types. While Recent shows, nothing is highlighted until the user moves with the arrow keys, and until then Enter and Tab do nothing. Picking a recent line puts it in the field; Enter then treats it like typed text, so a one-word line such as `zoom` starts its steps. Without Recent, the first task is highlighted.
- **Search.** It covers command names, help descriptions and fixed first values (`surface` finds `show surface`). Recently used commands rank higher and carry a clock. Matches are bold and underlined in the command name only. Enter picks the highlighted command. A typed command line, one with a space or a comma or one no command matches, runs on Enter as it stands.
- **Help strip.** Below the results, 89 px high: the highlighted command's description (two lines at most), usage and one example, all from PyMOL's help. F1 shows the full help in Output. A missing part leaves its line blank. The strip is not shown for recent lines, argument steps, confirmation or Go to.
- **Arguments.** Picking a command asks for each user-facing positional argument. The field starts with the default, selected. Filled arguments are chips; one left out says "default". Clicking a chip changes it and keeps the later values. Backspace in an empty field goes back one step, from the first argument to the search, and also keeps the later values. A chip shortens at 160 px; if the chips do not fit, the oldest collapse into "…". Arguments PyMOL cannot describe (`*args`) are typed freely.
- **Suggestions.** Arrow keys and a click put a suggestion in the field; a double click accepts it. Every colour argument offers colours, special names such as `atomic` included. Each colour has a 14 px swatch of its real colour, read from the running PyMOL; a name without one fixed colour has an empty square with a dashed outline. The name always stays.
- **After Enter.** The palette closes before the command runs, and the focus returns to the viewer. The line becomes the first under Recent, even if it fails. Recent keeps 100 distinct lines across restarts.

### Nothing runs by accident

1. **Text in the field wins.** Enter and Tab accept typed text, or a default in the field, exactly as shown.
2. **Empty field, more steps follow:** Enter or Tab picks the highlighted suggestion. Enter leaves out an optional value instead.
3. **Empty field, this step runs the command:** nothing is highlighted until the user chooses with the arrow keys or a click. Enter leaves out an optional value. Otherwise, the palette stays open and says "Choose a value or type one.", or "A value is missing. Type one and press Enter." when there is nothing to suggest. Tab says the same for an optional value that has suggestions.
4. **Ctrl+Enter and Shift+Enter** run the command with the remaining defaults, so rule 3 holds for them on every step.
5. **Confirmation.** A picked command that can discard work asks first when the user chose or typed no value. An untouched default, a left-out value and an automatic pick are not choices. The palette says what will happen and offers *Go back* (highlighted) and *Run <command>*. Only a click on Run, or Enter after moving to it, runs the command. Tab does nothing, Backspace goes back, Esc closes, and no shortcut skips the step.
6. **The list for rule 5** starts with `reinitialize` and `remove_picked`; `mdelete` is a candidate. Step 2 goes through every public command, also those without arguments, and the owner approves the list. It adds to rules 1–4 and replaces none of them.
7. **A searched value** for a command with one argument goes into the field and does not run the command.
8. **A typed command line** never asks; a single word that finds a command is a search.
9. **Opening the palette** and pressing any number of Enters or Tabs never runs a recent line.

### Go to, Output and the status bar

- **Go to (Ctrl+G)** lists the loaded objects and selections, then reads, in this order: an exact name; a `/` macro; a short address (`A/45`, `obj/A/45`, `A/45/CA`); residue numbers (`45`, `100-120`); a bare word that is no selection keyword, as a residue name (`HEM`); any other selection. `A/45` is translated first, because PyMOL reads a macro without a leading slash from the right (`layer3/Selector.cpp`). It zooms and sets `sele`. An object without atoms is zoomed to and `sele` stays. A target that is not found keeps `sele` and keeps the palette open with a message. A jump is not added to Recent.
- **Output (Ctrl+J)** starts closed. It is read-only and can be selected and copied, with Search and Clear. It uses the console style and marks warnings and errors with an icon in the margin; errors and tracebacks are also in the danger colour. One batch of errors, from any source, opens it once, unless "Don't open on errors" is set; that choice is remembered.
- **Status bar.** A command without an error shows "Ran <command>" for about four seconds. It does not say "Done", because PyMOL does not reliably report success. An error shows "Error. See Output." instead. While PyMOL reports progress, the bar shows it with an Abort button.

### The window

- **Islands.** Panes and the viewer are islands: 10 px corners, 6 px apart, no borders or shadows. The menu bar, toolbar and status bar sit on the frame. The viewer keeps the session's colours and is not themed. Only menus, dialogs and the palette cast a shadow.
- **Panes** have three fixed slots: left, right and bottom. Each is shown or hidden from the toolbar or the palette (the bottom one also with Ctrl+J), remembers its size and may hold tabs. Hiding a slot remembers its visible panes and showing it restores exactly those. A pane the user closed stays closed, and a pane may refuse to show. Nothing is dragged out.
- **Plugin panels** keep the whole `pymol3.ui` API and Display ▸ Plugin Panels. `left`, `right` and `bottom` open as tabs in that slot, and `top` as a tab in the bottom slot. `floating=True` opens a themed window of its own, which can be moved and closed but not docked by dragging. `panel.dock_widget` stays the panel's `QDockWidget`, so a plugin can still change it.
- **Toolbar.** One fixed row: the left pane toggle; the search field; Reset, Zoom, Orient, Draw/Ray | Unpick, Deselect, Get View, MClear | Builder, Properties, Rebuild (all also in the palette); the bottom and right pane toggles; the gear.
- **PyMOL+ Options** opens from the gear or the palette. *Appearance:* theme Light (default), Dark, or Follow the system, which uses Light if the system reports none. *Accessibility:* Color vision (Standard, Red-green adjusted, Blue-yellow adjusted) and Animate the interface (on by default). Changes apply at once and are remembered.
- **Menus.** PyMOL's menus keep their names, order, items and wording. The new GUI leaves out only Display ▸ External GUI, together with the External GUI. Display ▸ New GUI and Display ▸ Plugin Panels exist already and stay.
- **Design language.** One look on every platform. The boards *Islands*, *Colours*, *TypeShape*, *Icons* and *Components* hold the values. No state is shown by colour alone. The colour-vision modes change only the success, danger and warning tokens. Text reaches at least 4.5:1, and field outlines and focus rings at least 3:1.
- **Words.** New text is plain and calm. Buttons and window titles use title case, other labels sentence case. An error says what happened, why, and what to do next.

### What becomes of the External GUI

The new GUI starts without the External GUI and its menu, and shows no notice about it. Everything it offered is in the palette, Output, toolbar and status bar. The classic GUI, still the default, does not change. `ext_window`, `lineedit`, `browser`, `progressbar` and `abortbutton` stay on the window, so plugins that read them do not fail. `options.external_gui` is never changed, because PyMOL also reads it elsewhere at start.

### Approaches

- **A. Rebuild in steps (chosen by the owner):** one feature plan; each step has its own branch, plan and pull request. Every step is small enough to review, and the Objects, Scenes and Library panels can reuse the foundation. The full result takes longer. This replaces the one-branch decision of 2026-11-25.
- **B. Rebuild on one branch:** everything arrives together, but in a pull request at least as large as the prototype (about 11,000 added lines, tests included), and the other panels wait for all of it.
- **C. Rework the prototype:** something to see soonest, but nearly all its GUI code would be replaced and its choices would keep shaping the result. Ruled out.
- Where the code lives is unchanged since 2026-11-23: in `pymol3` with short hooks, not in the upstream GUI file (laborious to port) and not in a plugin (the External GUI would flash at start).

### What the prototype is for

Nothing is merged, cherry-picked or copied as a whole from the prototype. A step first writes tests from this plan and may then rewrite what passes them. A prototype test is evidence of a case worth covering, never proof that its expected value is right. The prototype's tests were not run for this plan.

| Prototype | In the rebuild |
|---|---|
| Arguments from `USAGE`, with signature fallback; `quiet`, `flags` and `_self` hidden | Keep the cases, rewrite |
| Command lines: unused defaults left out, names after a gap | Keep the cases, rewrite |
| Go to addresses, `sele` kept on a miss; history of 100 lines | Keep the cases, rewrite |
| Error detection across batches, with and without a traceback header | Keep the cases, rewrite |
| Shortcuts caught while the viewer has the focus; the palette as a child of the window | Keep the idea, rewrite |
| External GUI left out without changing `options.external_gui` | Keep the idea, rewrite |
| `app.tick`, `add_dock_panel(visible=)` | Use PR #27's versions |
| `popup.py` (1,512 lines of look and logic), Output, panes, toolbar, status bar | Rebuild as views and controllers |
| Going back drops later values; a single-argument search match runs at once; Tab picks a suggestion on the last step | Change: the rules above |
| Fixed colours, drawn icons, movable toolbar, red Abort, pane toggles in the Display menu, helpers repeated in up to four files | Drop |

### Facts that bind the design

- `update_feedback()` in the edited `pymol_qt_gui.py` is the only reader of `cmd._get_feedback()`, which hands out each line once. Its timer also runs the setting callbacks, so it must keep running without the External GUI.
- PR #27 (Scenes panel, open on 2026-11-28) adds `pymol3.app.tick(window, feedback)`, called after the setting callbacks, and `add_dock_panel(visible=True)`. It has fixed colours of its own.
- `pymol3.app.start` imports the modules in `FEATURE_MODULES` in both styles, but runs their features only in the new one. Importing such a module loads no Qt.
- `panel.dock_widget` is public and documented in README.md as the `QDockWidget`, so a slot has to be built from Qt docks.
- `PyMOLQtGUI` sets `pymol.sty` as the main window's style sheet. A marked segment then replaces it with the app's `base.css`. Nothing reloads either file.
- `cmd.get_progress()` reports a number and no job name.
- The viewer is a `QOpenGLWidget` (or `QGLWidget`), so rounding its corners is the least proven part of the design.
- `replace P,4,1` is PyMOL's `CTSH-P` shortcut. PyMOL's shortcut table has no default for Ctrl+G, Ctrl+J or F1. PyMOL has no View menu.
- A rough count found 318 registered commands and help for 291 of them, with usage for 199 and an example for 114.

### Calls made in this plan (Claude's, open to correction)

- **No notice.** The plan on `production` has a one-time notice with a button back to the classic GUI. The prototype's later plan dropped it and the owner chose to follow that; Display ▸ New GUI is the way back.
- **No entries for the pane toggles in PyMOL's menus.** The board named a View menu, which PyMOL does not have, and its menus do not change.
- **The job's name.** The status bar shows the command when the palette or toolbar started it, and "Working…" otherwise.
- **No jobs flyout yet.** The board has one, but PyMOL reports only one job at a time. It waits until a feature adds a second source, such as `mp4-export.md`. "Saved" and "Claude connected" come with the features that own them.
- **No movie controls in the toolbar.** The earlier plan put them there until the Objects panel exists, but the approved board does not. The internal GUI has them and stays on until then.
- **"Ran" or "Error".** The message follows the first feedback tick after the command. A later error replaces "Ran". "Error. See Output." goes away once Output has been visible for about four seconds, also when it opened by itself.
- **The help example** is the first one with a comma, else the first one, without its trailing comment.
- **A Go to jump** shows "Went to <target>" in the status bar.
- **The toolbar** cannot be moved, as on the board.
- **What the theme covers:** the main window, its menus and panes, PyMOL+ dialogs and floating plugin windows. PyMOL's own dialogs keep their look for now.
- **Ctrl+Enter and Shift+Enter in the search** act like Enter; they run a command early only in its argument steps.
- **The bottom line** says "Enter runs the command" on the step that runs it.
- **Approved boards win over `opp-gui:qt-themes` defaults:** semibold and monospace text, shadows on popups, and a third theme choice. Icons, the Color vision setting and the Animate switch follow the boards too.
- **Two-space indentation**, as in the rest of `pymol3`; everything else follows `opp-workflow:python-style` and `opp-gui:qt-style`.

### Left to the builder

Module names inside the parts above, ranking weights, the painting technique, and the exact timing within the limits given.

## Global Constraints

Every step holds these:

- "App: PySide6 stays at 6.9 (6.10+ drops macOS 12 and RHEL/AlmaLinux 8); Python 3.13; biopython 1.86."
- "New dependency versions only when they are at least 14 days old (Dependabot cooldown)." No new runtime dependency. pytest-qt is a test dependency if step 1 adds it.
- "Changes reach `production` only through pull requests"; Hannah or Martin approves and merges by hand.
- "`distribution/edited/` holds upstream PyMOL files with marked edits (`BEGIN EDITED CODE SEGMENT`)". No file under `modules/pymol/`, `modules/pmg_qt/`, `modules/pmg_tk/`, `modules/chempy/` or `modules/pymol2/` changes.
- Nothing in PyMOL's or `pymol3`'s public API is removed or changed. Commands run through the same path as the command line.
- "App package and AppStream license: `BSD-3-Clause AND LGPL-3.0-only AND HPND`." Material Symbols are Apache-2.0, so Hannah decides before any of them is added. If the answer is no, step 1 draws its own icons (BSD-3-Clause) for the same concepts.
- Public `pymol3` modules import without Qt. Only the GUI part's one binding module names `pymol.Qt`.
- No colour or size is written outside the tokens. Only PyMOL+'s own windows are styled, never `QApplication`, and only in the new GUI.
- Every GUI test runs offscreen, isolated and, where it checks the look, in both themes. It names its board and takes its expected values from the tokens or this plan.
- Python follows `opp-workflow:python-style`. New files carry `SPDX-License-Identifier: BSD-3-Clause`. No attribution in commits or on GitHub.

## Scope

.opp/plans/features/command-palette.md
.opp/plans/features/objects-panel.md
.opp/plans/gui-foundation.md
.opp/plans/command-logic.md
.opp/plans/gui-window.md
.opp/plans/command-palette-view.md
.opp/plans/gui-toolbar.md
.opp/gui/**
modules/pymol3/**
tests/BUILD.bazel
tests/pymol3_*/**
distribution/edited/pmg_qt/pymol_qt_gui.py
distribution/edited/BUILD.bazel
distribution/linux/BUILD.bazel
distribution/os_specific/**
distribution/licenses/**
tools/bazel/requirements.in
tools/bazel/requirements_lock*.txt
README.md
docs/decisions/**

## Done

All five steps are merged into `production`. In the new GUI, every acceptance criterion below holds on Windows, macOS and Linux; the classic GUI is unchanged and still the default.

## Non-goals

- Making the new GUI the default, and the website's documentation, which comes with that change.
- Changing the wheel's own GUI (`modules/pmg_qt/`). Wheel users get the `pymol3` modules but not the new window.
- Removing the External GUI from the classic GUI, or the command line in the viewer.
- Searching menus or PyMOL settings, editing shortcuts, and confirmation for typed command lines.
- Undoing commands, and judging whether a chosen or typed value is harmful.
- Restyling PyMOL's own dialogs, recolouring the viewer, and the colour-blind-safe palettes in the C menu, which belong to `objects-panel.md`.
- Moving the Scenes panel to the new design. That follows step 1, in agreement with Hannah.
- Objects, Scenes, Library, MP4 export and MCP features.
- Windows high-contrast mode, the PyMOL+ app icon, the Tk GUI and `pymol -c`.

## Steps

Each step is one branch from `production` and one pull request. Its Superpowers plan, `.opp/plans/<branch>.md`, is approved before any code. Steps 1 and 2 can run side by side. Step 3 needs step 1, step 4 needs steps 1 to 3, and step 5 needs step 4. The External GUI stays on in both styles until step 5, so nobody is without a command line.

**Before step 1:** this plan is merged, and Hannah has decided on Material Symbols. **Before step 3:** PR #27 is merged. If it is closed instead, step 3 adds `tick` and `visible=` with the same signatures. Before steps 1 and 3, agree with Hannah on files that both branches change.

1. **Design foundation** (`gui-foundation`).
   - Tokens for both themes and three colour-vision modes; style sheet, palette and fonts for each of our own windows; a theme manager with Light, Dark and Follow the system; the Animate switch; the icons; the Options window; GUI tests tied to their boards, with the ledger in `.opp/gui/`. Until steps 4 and 5 add its entries, only tests open the Options window.
   - Update the theme and colour parts of `objects-panel.md`: the theme and its choices come from here.
   - *Boards:* Colours, TypeShape, Icons, Components, Options, OptionsAccessibility.
   - *Done when* a theme or colour-vision change restyles open test windows at once and survives a restart, contrast is tested in every mode, and nothing changes in the classic GUI or outside our own windows.
2. **Command logic** (`command-logic`), without Qt.
   - The command index with search, ranking, help text and example; arguments, their suggestions and real colours; building the command line; the argument steps as a state machine that holds rules 1 to 9; history; Go to; sorting feedback into normal, warning and error lines.
   - Go through every public command for rule 6 and give the owner the list, with the reason for each entry and for each close call left out.
   - *Done when* all of it is tested without a window, against a real PyMOL where the result depends on it, and the owner has approved the list.
3. **Window and Output** (`gui-window`), in the new GUI only.
   - The frame, islands (the viewer's rounded corners included) and three slots, built from `QDockWidget`s that cannot be moved or floated; plugin panels as described above; hiding and restoring slots; Output with Ctrl+J; full screen. In the new GUI, the theme takes the place of `pymol.sty` and the app's `base.css` on the main window.
   - Update README.md for plugin panels in the new GUI, and record the slots in a new ADR that amends ADR 0001.
   - *Boards:* Islands, Output.
   - *Done when* the README's example and a floating, a `top` and an unmodified existing panel work in both styles, and Output shows every feedback line exactly once.
4. **Palette** (`command-palette-view`).
   - Every palette state on the boards, Go to included, as views over the logic of step 2. It also has the quick buttons, pane toggles, Options and F1. The shortcuts win while the viewer has the focus. The prototype's branch keeps its name, so this branch needs another.
   - *Boards:* Palette, PaletteEmpty, PaletteFirstStart, PaletteArgs, PaletteColorChip, PaletteChips, PaletteChangeChip, PaletteLongChips, PaletteChoose, PaletteConfirm, PaletteMissing, PaletteRan (the closed palette), GoTo.
   - *Done when* the palette criteria below hold in the new GUI beside the External GUI. The status bar messages come in step 5.
5. **Toolbar and status bar** (`gui-toolbar`).
   - The toolbar with the search field, quick buttons, pane toggles and gear; "Ran", "Went to", "Error", progress and Abort in the status bar. After that, the new GUI starts without the External GUI and its menu.
   - *Boards:* Toolbar, PaletteRan (its status message), Vision (its toolbar, status bar, Output and palette; the Library and Objects panes belong to their own plans).
   - *Done when* everything the External GUI offered has its new place, the new GUI starts without it and without a flash, `-x`-style starts still hide it in the classic GUI, and every acceptance criterion holds.

## Review Focus

Each line gets its test in the step named.

- **A command runs without a choice (2, 4).** Twenty presses each of Enter, Tab, Ctrl+Enter and Shift+Enter, from search and from every step, never run `delete`, `remove`, `reinitialize` or any other command on the approved list. The same presses on a freshly opened palette never run a recent line such as `delete all`. A held key does not pass a confirmation.
- **Feedback is lost, doubled or blamed on the wrong command (3, 5).** Without the External GUI, setting callbacks still run and each line arrives once. A traceback split across batches opens Output once. An older error does not hide "Ran", and a later one replaces it.
- **The viewer takes a shortcut (4).** Ctrl+Shift+P opens the palette and never runs `replace P,4,1`. Ctrl+G and Ctrl+J work while the viewer or the palette has the focus, also with ⌘ on macOS.
- **A plugin breaks or takes on the wrong look (1, 3).** Existing calls, `dock_widget` and `ext_window` keep working. A theme change reaches a panel added later and leaves PyMOL's own dialogs alone.
- **The viewer's rounded corners (3).** They stay right while the view rotates and the window is resized, at 100 % and 200 % scaling, without flicker or a slower picture.
- **Unusual commands and names (2, 4).** Commands with `*args`, keyword-only arguments, no help or a very long usage line work, as do names with spaces or non-English characters, hundreds of objects, changed colours and commands a plugin adds while the app runs. No `None` ends up in a command line.

## Acceptance criteria

- Ctrl+Shift+P and the toolbar's search field open the palette, also while the viewer has the focus; Esc and a click outside run nothing.
- A first start shows only the five common tasks. After a command ran, also a failed one, it is the first under Recent, also after a restart. Opening the palette and pressing only Enter or Tab never runs a recent line. Moving to it with the arrow keys and pressing Enter fills the field and does not run it.
- Typing "surf" ranks `show surface` first, marks the match without relying on colour, and shows PyMOL's help for `show`; picking it asks only for the atoms. Typing `color red, chain A` and Enter runs that line; typing `reinitialize` and Enter starts its steps.
- `color` offers PyMOL's colours with their real swatches, also after `set_color`. The chosen colour keeps its swatch in its chip. Clicking a chip, or Backspace in an empty field, changes it and keeps the later values.
- Rules 1 to 9 hold with the keyboard and the mouse, and the owner has approved the confirmation list.
- Ctrl+G reads `A/45` as chain A, residue 45, and `HEM` as a residue name, zooms and sets `sele`. A target that is not found leaves `sele` alone and the palette open.
- Each batch of errors opens Output once, unless "Don't open on errors" is set, also after a restart. Every line appears once. Errors are marked by more than their colour.
- "Ran", "Went to" and "Error. See Output." appear and go away as described. During a ray trace the status bar shows progress, and Abort stops it.
- Each slot keeps its size and panes when hidden, shown and after a restart. PyMOL+'s panes cannot be dragged out. Every plugin panel case in `### The window` works, and the classic GUI handles panels as before.
- The gear and the palette open Options. Each choice applies at once and after a restart, and Light is the default. Contrast holds in both themes and all three colour-vision modes. With Animate the interface off, nothing moves.
- Every control on this feature's boards can be reached and used with the keyboard, shows its focus and has an accessible name.
- Every board a step names has a test that names it. The owner has looked at its renders in both themes.
- The new GUI starts without the External GUI, its menu or a notice. In the classic GUI, tests show the same window, menus, panels and command line as before this feature.
- Upstream files are unchanged, and the package licence is unchanged unless Hannah decided otherwise.

## Verification

Before each step's pull request:

- `bazel test //tests` passes, with the step's tests in both themes where they check the look; `bazel test //distribution/...` passes, `//distribution/edited:edited_base_test` and the app's smoke test included.
- `bazel run //distribution:checks` and `python3 .opp/style/check.py --committed` report nothing. From step 1 on, `python3 .opp/gui/ledger.py check` passes.
- Each GUI state is rendered in both themes, and the colours also in each colour-vision mode, and looked at beside its board. Each step gets a fresh review of its exact commits; GUI steps also get the `opp-gui:gui-reviewer`.
- A classic start is compared with `production`: window, menus, panels and command line.
- By hand in the built app on Windows, macOS (with ⌘) and Linux: the step's criteria, at 100 % and 200 % scaling, with `--new-gui` and `--classic-gui`. A platform nobody could check is named in the pull request, and the feature is not done until it has been checked.
