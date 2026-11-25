# An Objects panel that replaces the internal GUI, ASHLC kept

**Goal:** A Qt panel docked on the right takes over everything PyMOL's internal GUI does (the object list with its A S H L C buttons and their menus, the movie controls, the mouse mode and bindings, and wizard panels) in a modern look with smooth fonts and light and dark themes, so the new GUI can run without the internal GUI.

**Architecture:** New modules in the `pymol3` package build the panel on `pymol3.ui.add_dock_panel(..., area="right")`. The panel reads PyMOL's state through `cmd` (names, groups, enabled objects, frames, states, mouse mode, the active wizard), builds its menus from the same `pymol.menu` functions the internal GUI calls, and runs the same commands. A few new, read-only C++ entry points (object tree with group membership and open state, current mouse bindings, measured frame rate) are added to `_cmd` and reached through `pymol3`, since `cmd` cannot provide them; no existing function changes. One marked hook in the app's copy of `pymol_qt_gui.py` creates the panel at start.

**Tech Stack:** Python, `pymol.Qt` (PySide6 6.9 in the app), `pymol3.ui`, `pymol.menu`, Bazel (`rules_python`), pytest with Qt's `offscreen` platform as in `tests/pymol3_ui/`.

**Spec:** The design approved in the brainstorming session of 2026-11-23, recorded in `## Design` below, and its design board "PyMOL+ Objects panel (ASHLC) design board" (https://claude.ai/artifact/59LAigu97Z4jZ13MQyZPL4): boards Main (dark, interactive), Light, MenuOpen, Wizard, Bindings and Context. Backlog source: an idea raised in that session.

## Design

**Why.** The internal GUI on the right of the viewer is drawn by PyMOL in OpenGL with a pixel font and looks decades old. The developer wants it modern and from the 2020s, but wants to keep the familiar, "nostalgic" A S H L C buttons, and every feature the internal GUI has must be kept.

**What the user sees** (board Main and Context).

- A panel titled **Objects**, in the right dock area, tabbed with the Scenes panel (`features/scenes-panel.md`) when both are open.
- **Header:** title, a count ("7 objects · 2 selections"), collapse-all and a more-options button, and a **filter field** that narrows the list by name.
- **Rows**, one per object and selection, in PyMOL's order, groups nested and foldable; names starting with `_` hidden as `hide_underscore_names` says. Each row: a visibility **eye**, a fold chevron on groups, a type icon (all, group, molecule, map, selection), the name (selections in parentheses and in their own colour, hidden objects dimmed and italic), a **state badge** on multi-state objects ("120 states"), and the **A S H L C** chips: A S H L as rounded chips in PyMOL's lavender, **C** as a rainbow swatch. In the mouse mode "3-Button Motions" (`button_mode_name`, as `get_op_cnt()` decides), a sixth chip **M** (camera or object motion) appears.
- **Menus:** each chip opens a Qt popup menu built from the same `pymol.menu` function the internal GUI uses for that object type, so the entries and their commands are identical (board MenuOpen).
- **Movie row** (in the panel, the developer's choice): rewind, back, stop, play (Ctrl: from the start), forward, end (Ctrl: middle); toggles **S** (sequence viewer), rock, **F** (full screen); a readout "Frame 1/120 · 30.0 Hz", or "State n" without a movie.
- **Mouse section:** the mouse mode as a pill (click: next mode, Shift-click: previous, right-click: the mouse configuration menu), the selection mode as a pill (click: next, Shift-click: previous), and a fold-out **binding table** (Buttons L M R Wheel against keys, single and double click) from the current mouse mode (board Bindings).
- **Wizard section**, above the movie row while a wizard is active: its title, menu buttons and buttons, built from the wizard's `get_panel()` (board Wizard).
- **Themes:** dark and light, following the operating system's colour scheme.

**Every internal GUI feature and its new place** (from `layer3/Executive.cpp` `CExecutive::click/release/drag`, `layer1/ButMode.cpp`, `layer1/Control.cpp`).

| Internal GUI | Objects panel |
|---|---|
| Left-click name: toggle enabled; Shift: immediate; Ctrl: solo while hovering; Ctrl+Shift: hover activate | Eye or name click, the same modifiers |
| Drag down the names: paint visibility | Drag across the eyes |
| Middle-click: center and activate; Ctrl: zoom; Ctrl+Shift: zoom and show only this | Middle-click with the same modifiers |
| Right-drag: reorder; dropping into an open group or out of one groups or ungroups | Drag and drop rows (`cmd.order`, `cmd.group`, `cmd.ungroup`) |
| Group +/− | Fold chevron |
| A S H L C per object type (all, selection, group, molecule, map, mesh, surface, CGO, measurement, alignment, volume, slice, gadget) | Same chips, menus from the same `pymol.menu` functions |
| M (`camera_motion`, `obj_motion`) in "3-Button Motions" | M chip, only then |
| Movie buttons, S, rock, F | Movie row |
| Frame n/N, rate in Hz, state | Movie row readout |
| Mouse mode name and cycling, `mouse_config` menu | Mouse pill |
| Selection mode and cycling | Selection pill |
| Binding table | Fold-out table |
| Wizard panel | Wizard section |
| Scroll wheel and scroll bar | Native scrolling |
| Cloaked rows: an enabled object inside a disabled group in its own shade | Same shade |
| `internal_gui_name_color_mode`: names in object colours | Same setting honoured |
| `group_full_member_names`: group prefix shown as `^.name` | Same setting honoured |
| `mouse_grid` off hides the binding table | Same |
| Editing modes: "Picking Atoms (and Joints)" replaces the selection mode, no cycling | Same in the selection pill |
| Right-click or wheel on the selection line cycles backwards | Same on the selection pill |
| Stop also ends sculpting and rocking | Stop runs the same commands as `Control.cpp` |
| Colour codes in menu labels (`\RGB`) | Rendered as coloured text in the Qt menus |
| Drag the edge to resize, double-click to collapse | Dock width, right layout toggle |

**Approaches considered.**

- **B. A new Qt panel in `pymol3` (chosen).** Python only, no upstream change; real widgets, smooth fonts and themes; fits the layout of the command palette and scenes panel features.
- A. Restyle the OpenGL drawing in C++. Keeps one implementation for every GUI, but means deep edits in upstream C++ files, and smooth fonts in the OpenGL overlay are a project of their own. Rejected.
- C. Settings only (`internal_gui_mode`, `internal_gui_control_size`, colours). Small, but the look stays. Rejected.

**Decisions made with the developer.**

- Keep the A S H L C buttons and their look; every internal GUI feature moves over.
- The movie controls live in the panel, not in the toolbar; `features/command-palette.md`'s toolbar drops them in step 3 of this feature.
- Built as approach B.
- Small, purely additive read-only C++ functions are allowed where `cmd` cannot provide what the panel needs (reviewer question, accepted 2026-11-23).
- The one new-GUI switch decides whether the panel exists: in the classic GUI it is not created and nothing changes. In the new GUI, `internal_gui` decides within the run: the panel shows exactly while the internal GUI is off, never both. The new GUI starts with it off; the existing Display → Internal GUI checkbox toggles it for the run and is not remembered; `pymol -i` or a `.pymolrc` still set it (one switch for all PyMOL+ GUI features, decided 2026-11-25).

**Calls made in the design (Claude's, open to correction).**

- **Shared GUI hooks** (all PyMOL+ GUI features: `command-palette.md`, `scenes-panel.md`, `objects-panel.md`, `project-library.md`, `mcp-server.md`): the app's edited `pymol_qt_gui.py` gets two shared marked segment areas that every feature registers through: at start-up in `execapp()`, `pymol3.app.start(window)` before `window.show()` and `pymol3.app.ready(window)` after `initializePlugins()` (which clears the Plugin menu); and in `update_feedback()`, `pymol3.app.tick(window, feedback)` with every tick and feedback batch. `pymol3.app` and the `start` and `ready` areas exist (branch `new-gui-switch`): a feature registers with `pymol3.app.register(pymol3.app.Feature(...))`, and the hooks run it only while the GUI style is `new`, chosen by the one switch (Display → New GUI, remembered; `--new-gui` or `--classic-gui`, or `PYMOL_PLUS_GUI`, for one start). In the classic style the feature does not run at all, so no feature adds a switch of its own. Whichever feature lands first adds the `tick` area and `pymol3.ui.add_dock_panel(..., visible=True)` if it is not there yet. A feature adds a marked segment of its own only where it must change an existing method or class-level code, and names it here. This feature: `start` (switch `internal_gui` off before the window shows, create the panel), `tick` (sync).
- The panel follows `internal_gui` through the GUI's existing setting callbacks, so `reinitialize`, `.psw` files and scripts that change it are followed too.
- The new C++ functions are reached from Python only through `pymol3` (for example `pymol3.query.object_tree()`, `mouse_bindings()`, `frame_rate()`); `modules/pymol/` stays untouched. Each C++ addition sits in its own clearly marked block so porting upstream changes stays simple.
- The panel follows PyMOL's state by polling on the GUI's existing 500 ms tick and on the setting updates it already receives, as the scenes panel does; it does not call `get_setting_updates()` itself.
- The mouse mode and selection mode stay in the panel, not the status bar.
- **Themes** follow the operating system's colour scheme (`QStyleHints.colorScheme()`, Qt 6.5+, so PySide6 6.9 has it), light when the OS reports none; no theme setting of its own. The theme module built in step 2 applies to this panel; other `pymol3` panels may adopt it later.
- Dragging a row into an open group or out of one groups or ungroups it, as the internal GUI does.
- Every behaviour in the table above is in scope, cloaked rows and the label colour codes included.
- Things drawn in the viewer stay there: the wizard prompt, the sequence viewer, scene buttons and the in-viewer command line are not part of this panel.

**Facts from the code that bind the design.**

- `pymol.menu` functions return lists of `[kind, label, action]`: kind 2 a title, 1 an item whose action is a command string or a nested list (a submenu), 0 a separator (`modules/pymol/menu.py`, e.g. `mol_show`). The panel turns these into `QMenu`s and runs the actions as the internal GUI does.
- The internal GUI picks the menu by row kind and object type in `CExecutive::click()`. Its `%` prefix code is disabled (`#if 0`), so plain names are passed; the panel passes the same plain names, so its commands are identical (a `%` would also break `obj_motion`'s `cmd.mview(object=...)`).
- The menus run their actions through `PLog` plus `PParse`, so they are logged as typed commands; the panel does the same.
- With `internal_gui` off, the wizard block, `ButMode` and `Control` all go inactive, so the panel is the only place left for them. The wizard prompt and the movie timeline stay drawn in the viewer.
- There is already a **Display → Internal GUI** checkbox (`modules/pymol/_gui.py`); `pymol -i`, a `.pymolrc`, `.psw` files and `reinitialize` also set `internal_gui`.
- A wizard's `get_panel()` returns `[kind, label, action]` rows: 1 a title, 2 a button running a command, 3 a menu named by the wizard (e.g. `modules/pymol/wizard/mutagenesis.py`).
- The movie buttons log and run `cmd.rewind()`, `cmd.back()`, `cmd.mstop()`, `cmd.mplay()`, `cmd.forward()`, `cmd.middle()`/`cmd.ending()`, `seq_view`, `cmd.rock()` and `cmd.full_screen()` (`layer1/Control.cpp`); mouse cycling runs `mouse forward/backward` and `mouse select_forward/select_backward` (`layer1/ButMode.cpp`).

## Global Constraints

Quoted from AGENTS.md and the `pymol3-dock-panels` plan:

- "App: PySide6 stays at 6.9 (6.10+ drops macOS 12 and RHEL/AlmaLinux 8); Python 3.13."
- "`distribution/edited/` holds upstream PyMOL files with marked edits (`BEGIN EDITED CODE SEGMENT`)"; nothing under `modules/pymol/`, `modules/pmg_qt/`, `modules/pmg_tk/`, `modules/chempy/` or `modules/pymol2/` changes.
- Upstream C++ only gains new, read-only functions in blocks marked `BEGIN PYMOL+ ADDITION` / `END PYMOL+ ADDITION` (`layer4/Cmd.cpp` and the layer files that hold the data); no existing C++ function's behaviour changes. ADR `docs/decisions/0002-additive-cpp-entry-points.md` records this exception to ADR 0001.
- C++ follows `opp-workflow:cpp-style` for the added code.
- Never remove or change anything in PyMOL's existing command or Python API; only add.
- Python follows `opp-workflow:python-style`; `python3 .opp/style/check.py --committed` passes on each step's last push.
- "Pull requests get the Bazel check only."
- New files carry `SPDX-License-Identifier: BSD-3-Clause`.

## Scope

modules/pymol3/**
tests/pymol3_*/**
distribution/edited/pmg_qt/pymol_qt_gui.py
layer4/Cmd.cpp
layer3/Executive.cpp
layer3/Executive.h
layer1/ButMode.cpp
layer1/ButMode.h

## Done

All four steps below are merged into `production`, and the app in the new GUI starts with the Objects panel and without the internal GUI; in the classic GUI it starts as before.

## Non-goals

- Changing the internal GUI's C++ drawing or any existing C++ behaviour, or removing the internal GUI: it stays available through Display → Internal GUI.
- Moving what is drawn in the viewer (wizard prompt, sequence viewer, scene buttons, in-viewer command line).
- New entries in the A S H L C menus beyond what `pymol.menu` gives.
- Wheel users' GUI: the hook is in the app's edited copy only.

## Steps

Each step is one branch from `production` and one pull request into `production`; each step's own Superpowers plan goes to `.opp/plans/<branch>.md` when it starts. The internal GUI stays on, in the new GUI too, until step 4, so nothing is lost on the way.

1. **Read-only C++ getters** (`objects-panel-getters`): the object tree (every object's and selection's name, type, enabled and cloaked state, group membership, group open state, state count, in panel order), the current mouse bindings with their code names, and the measured frame rate, added to `_cmd` in marked blocks and wrapped in `pymol3.query`. Tested from Python against a real PyMOL; the wheel builds on every platform.
2. **Object list and menus** (`objects-panel-list`): the panel, rows, eye and name clicks with their modifiers, paint visibility, middle-click, drag reorder with group and ungroup, groups through `cmd.group(..., action=open/close)`, filter, state badges, cloaked rows, name colours, A S H L C (and M) menus from `pymol.menu` for every object type with coloured labels, sync with PyMOL, the shared light and dark theme.
3. **Movie and mouse** (`objects-panel-movie-mouse`): the movie row with its readout, the mouse and selection pills with their cycling, editing-mode and configuration behaviour, the binding table from `pymol3.query.mouse_bindings()`, and removing the movie buttons and Rock from the command palette's toolbar if it exists.
4. **Wizards and the switch** (`objects-panel-wizards`): the wizard section from `get_panel()`, the registration through the shared GUI hooks (adding `visible=` if this lands first; the panel starts hidden while `internal_gui` is on), the panel following `internal_gui`, and `internal_gui` switched off at start in the new GUI unless `pymol -i` or a `.pymolrc` set it.

## Review Focus

- **A menu that runs on the wrong target.** The panel must hand each menu the same name the internal GUI hands it, for objects, groups, selections and `all`. Covered by a test that opens each chip on a molecule, a group, a selection and `all`, and checks the command each menu entry runs against the internal GUI's.
- **Menus that differ by object type.** Each of the thirteen row kinds must open the menu the internal GUI opens. Covered by a table test against the mapping in `CExecutive::click()`.
- **Sync cost and flicker.** Polling a session with hundreds of objects must not rebuild the whole list every tick. Covered by a test that counts row rebuilds over idle ticks.
- **Wizards that change their panel.** Wizards rebuild `get_panel()` as their state changes (e.g. Mutagenesis' "Mutate to …"); the section must follow without reopening. Covered by a test with a wizard whose panel changes.

## Acceptance criteria

- The panel lists every object and selection as the internal GUI does, groups nested and foldable, `hide_underscore_names` respected.
- Clicking an eye or a name, with and without Shift, Ctrl and Ctrl+Shift, and middle-clicking, does what the same click does in the internal GUI.
- Dragging across the eyes paints visibility; dragging a row reorders the objects in PyMOL.
- A S H L C open the same menus as the internal GUI for every object type, and their entries run the same commands; M appears in the mouse mode "3-Button Motions", and only then.
- The movie row's buttons and toggles do what the internal GUI's do; the readout shows frame, rate and state.
- The mouse and selection pills cycle as the internal GUI does; right-click opens the mouse configuration menu; the binding table matches the current mode.
- A running wizard (Mutagenesis, Measurement, Sculpting) can be driven completely from the wizard section.
- In the new GUI the app starts with the panel and without the internal GUI; Display → Internal GUI brings the internal GUI back for the run (and hides the panel); `pymol -i` or a `.pymolrc` setting wins at start. In the classic GUI there is no panel and the internal GUI is as before.
- The new C++ functions only add; every existing `cmd` function behaves as before.
- No upstream Python file changes (`modules/` outside `modules/pymol3/`); upstream C++ changes only by the marked, additive blocks in `## Scope`, each marked `BEGIN PYMOL+ ADDITION` / `END PYMOL+ ADDITION`; `bazel test //...` and `bazel test //distribution/...` pass.

## Verification

- `bazel test //tests/...` runs the panel's offscreen Qt tests against a real PyMOL: rows and order, click modifiers, reorder, menu mapping per object type with plain names (no `%` prefix), menu commands, movie and mouse actions, wizard sections, sync without full rebuilds.
- `bazel test //distribution/...` passes, `//distribution/edited:edited_base_test` included.
- `python3 .opp/style/check.py --committed` reports no findings.
- By hand in the app on Windows: the acceptance criteria above, side by side with the classic internal GUI.
