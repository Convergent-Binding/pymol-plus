# A docked scenes panel

**Goal:** A panel docked on the right lists every PyMOL scene with its thumbnail and name, scrolls when the list is long, and lets the user create, recall, update, rename, reorder (by dragging) and remove scenes; it replaces the floating Scenes window as the place to manage scenes.

**Architecture:** A new module in the `pymol3` package docks a Qt list view through `pymol3.ui.add_dock_panel(..., area="right")` and talks to PyMOL only through its scene commands (`scene`, `scene_order`, `get_scene_list`, `get_scene_thumbnail`). Two marked hooks in the app's copy of `pymol_qt_gui.py`: the panel registers through the shared start-up hook, and `scene_panel_menu_dialog()` makes **Scene → Scenes…** open the panel instead of the old window.

**Tech Stack:** Python, `pymol.Qt` (PySide6 6.9 in the app), `pymol3.ui`, Bazel (`rules_python`), pytest with Qt's `offscreen` platform as in `tests/pymol3_ui/`.

**Spec:** The design approved in the brainstorming session of 2026-11-23, recorded in `## Design` below. Backlog source: the Notion list's "PyMOL scenes panel".

## Design

**Why.** Scenes are central to building figures and talks, but PyMOL's Scenes window (Scene → Scenes…, `modules/pmg_qt/scene_bin_gui.py`) floats apart from the main window, is hard to find, and is unfinished: every row shows the placeholders "This is a base message" and "Rock, zoom, something". The developer wants scenes visible at a glance beside the structure and easy to create, remove and recall.

**What the user sees.**

- A panel titled **Scenes**, docked in the right dock area, holding a vertical list: one entry per scene with its **thumbnail** (from `cmd.get_scene_thumbnail(name)`) and **name**, in PyMOL's scene order. A vertical scroll bar appears when the entries no longer fit.
- A **+** button at the top saves the current view as a new scene with an automatically numbered name (`cmd.scene("new", "store")`, which names scenes `001`, `002`, …).
- **Recall:** a plain click on an entry, or Enter on the selected entry, recalls the scene, with PyMOL's usual scene animation. Moving the selection with the arrow keys, right-clicking, starting a drag, or selecting an entry before F2 or Delete does **not** recall it.
- **Update:** an Update button and the entry's right-click menu store everything on screen into the selected scene, as PyMOL's own update does (camera, colours, representations, enabled objects, movie frame), keep the scene's message, and refresh its thumbnail. No key shortcut: Ctrl+S already saves the session (`pymol_qt_gui.py`, line 405).
- **Rename:** double-click on the name or F2 edits it in place; the scene is renamed in PyMOL (`scene <old>, rename, new_key=<new>`). A name already in use is refused and the old name stays.
- **Reorder:** drag and drop; the new order goes to PyMOL with `scene_order`, so PgUp/PgDn play the scenes in that order.
- **Remove:** a delete button on each entry, the right-click menu and the Delete key remove the scene (`scene <name>, clear`).
- The entry of the current scene is highlighted. The scene's message, if it has one, shows as the entry's tooltip; it is not edited here.

**Approaches considered.**

- **A. A new panel in `pymol3` on `pymol3.ui` (chosen).** Own code, tested on its own, docked like every other `pymol3` panel and shown or hidden by the right layout toggle of the command palette feature (`features/command-palette.md`).
- B. Dock and finish the existing `ScenePanel`. It is an upstream file (`modules/pmg_qt/scene_bin_gui.py`) with placeholder content; finishing it means large marked edits in a copy under `distribution/edited/`. Rejected.
- C. A plugin. It would sit outside the central interface and could be switched off. Rejected.

**Decisions made with the developer.**

- Docked on the right, thumbnails and names, vertical scrolling.
- Create, recall, remove, and also update, rename and reorder by dragging, so the old window is no longer needed.
- Built as approach A.
- Update stores everything on screen, keeping the message (reviewer question, accepted 2026-11-23).
- Only a plain click or Enter recalls; selection, arrow keys, right-click and drags do not (reviewer question, accepted 2026-11-23).
- The panel opens by itself once per app run, on the first new scene or a session with scenes (reviewer question, accepted 2026-11-23).

**Calls made in the design (Claude's, open to correction).**

- **Shared GUI hooks** (all PyMOL+ GUI features: `command-palette.md`, `scenes-panel.md`, `objects-panel.md`, `project-library.md`, `mcp-server.md`): the app's edited `pymol_qt_gui.py` gets two shared marked segment areas that every feature registers through: at start-up in `execapp()`, `pymol3.app.start(window)` before `window.show()` and `pymol3.app.ready(window)` after `initializePlugins()` (which clears the Plugin menu); and in `update_feedback()`, `pymol3.app.tick(window, feedback)` with every tick and feedback batch. `pymol3.app` and the `start` and `ready` areas exist (branch `new-gui-switch`): a feature registers with `pymol3.app.register(pymol3.app.Feature(...))`, and the hooks run it only while the GUI style is `new`, chosen by the one switch (Display → New GUI, remembered; `--new-gui` or `--classic-gui`, or `PYMOL_PLUS_GUI`, for one start). In the classic style the feature does not run at all, so no feature adds a switch of its own. Whichever feature lands first adds the `tick` area and `pymol3.ui.add_dock_panel(..., visible=True)` if it is not there yet. A feature adds a marked segment of its own only where it must change an existing method or class-level code, and names it here. This feature: `start` (create the panel hidden), `tick` (scene sync); its own segment in `scene_panel_menu_dialog()`.
- The panel stays in sync with scene changes made anywhere (palette, scripts, PgUp/PgDn, the scene buttons) and highlights the current scene.
- **Scene → Scenes…** opens the new panel; the old window is no longer reachable from the menu, but its upstream file stays unchanged.
- The panel is closed at start and opens by itself, once per app run, on the first scene created (in the panel, the palette, a script or Ctrl+F1) or on opening a session (.pse) that holds scenes. With the project library (`project-library.md`), which reopens the last chat at start, that means the panel opens at start whenever that chat holds scenes. Once the user closes it, it stays closed until the next start unless opened by hand.
- The scene message is a read-only tooltip.
- Update has no key shortcut, because Ctrl+S saves the session.
- The panel is created at start through the shared start-up hook (see Shared GUI hooks) and registers its `setting_callbacks`. It starts hidden: `pymol3.ui.add_dock_panel()` gains an optional keyword `visible=True`, an addition that changes no existing call.

**Facts from the code that bind the design.**

- The menu entry Scene → Scenes… is built in `modules/pymol/_gui.py` (upstream) and calls `scene_panel_menu_dialog()`, which the app's edited copy `distribution/edited/pmg_qt/pymol_qt_gui.py` defines (around line 924). The hook goes into that method, so `_gui.py` stays untouched.
- Every `scene` call sets the setting `scenes_changed` (index 254, `layer3/MovieScene.cpp`), and `scene_current_name` (index 396) changes with the current scene. The Qt GUI already polls `get_setting_updates()` every 500 ms and hands changes to `self.setting_callbacks` (`update_feedback()` in the edited `pymol_qt_gui.py`). The panel registers there; it never calls `get_setting_updates()` itself, which clears the flags and would take them from the GUI. `scene_order` and session restore do not set `scenes_changed`, so a cheap comparison of `get_scene_list()` on the same tick covers them.
- PyMOL never refuses a rename: `MovieSceneRename` silently overwrites a scene that already has the new name and drops it from the order, and an empty `new_key` deletes the scene. The panel's own check is the only protection.
- `scene <name>, update` keeps only the message of the scene now on screen (`_scene_get_current_message` in `modules/pymol/viewing.py`), so updating another scene would erase or copy messages; the panel passes `message=cmd.get_scene_message(name)` explicitly. Update also makes that scene the current one.
- A thumbnail is taken on the next redraw (`SceneDeferImage`), so `get_scene_thumbnail()` right after a store can be empty; it is also empty for scenes from old sessions. The panel shows a placeholder and fetches again on a later tick until a thumbnail arrives.
- `CTRL-F1`…`CTRL-F12` are PyMOL shortcuts that store scenes `F1`…`F12` (`modules/pymol/shortcut_dict.py`); these scenes appear in the panel like any other.

## Global Constraints

Quoted from AGENTS.md and the `pymol3-dock-panels` plan:

- "App: PySide6 stays at 6.9 (6.10+ drops macOS 12 and RHEL/AlmaLinux 8); Python 3.13."
- "`distribution/edited/` holds upstream PyMOL files with marked edits (`BEGIN EDITED CODE SEGMENT`)"; no file under `modules/pymol/`, `modules/pmg_qt/`, `modules/pmg_tk/`, `modules/chempy/` or `modules/pymol2/` changes.
- Never remove or change anything in PyMOL's existing command or Python API; only add.
- Python follows `opp-workflow:python-style`; `python3 .opp/style/check.py --committed` passes on the last push.
- "Pull requests get the Bazel check only."
- New files carry `SPDX-License-Identifier: BSD-3-Clause`.

## Scope

modules/pymol3/**
tests/pymol3_*/**
distribution/edited/pmg_qt/pymol_qt_gui.py

## Done

The scenes panel is merged into `production`, and Scene → Scenes… opens it in the app.

## Non-goals

- Editing scene messages, or the scene "actions" the old window's placeholders hinted at.
- Changing what a scene stores (`scene` command options) or PyMOL's scene playback.
- Changing or deleting the old `ScenePanel` (`modules/pmg_qt/scene_bin_gui.py`) or `_gui.py`.
- Scene export, import or a gallery view.
- Wheel users' GUI: the hook is in the app's edited copy only.

## Steps

One step, one branch `scenes-panel` from `production`, one pull request into `production`; its Superpowers plan goes to `.opp/plans/scenes-panel.md` when it starts.

1. **Scenes panel** (`scenes-panel`): the panel module, the list with thumbnails and scrolling, the six operations, sync with outside changes, opening on the first new scene, the start-up registration through the shared GUI hooks (adding `visible=` if this lands first), and the hook in `scene_panel_menu_dialog()`. It does not depend on the command palette's steps; once the palette's layout toggles exist, the right toggle covers this panel without further work.

## Review Focus

- **Rename to a name in use, or to an empty name.** PyMOL would silently overwrite the other scene or delete this one; the panel must keep the old name and say why. Covered by a rename test with a duplicate and an empty name.
- **Sync loops.** A reorder sent with `scene_order` comes back as a changed list; the panel must not rebuild the list under the user's drag or re-send the order. Covered by a test that reorders and checks one `scene_order` call.
- **Thumbnail cost.** Fetching every thumbnail on every timer tick would stall the GUI with many scenes; thumbnails are fetched on change, and again only while still empty. Covered by a test that counts `get_scene_thumbnail` calls across idle ticks once every thumbnail has arrived.
- **Messages lost on Update.** Updating a scene that is not on screen must keep its own message. Covered by a test with two scenes and two messages.

## Acceptance criteria

- Scene → Scenes… opens the panel on the right; the old window no longer opens from the menu.
- The panel lists every scene with thumbnail and name in PyMOL's order, and scrolls vertically with more scenes than fit.
- **+** creates a new numbered scene from the current view; the panel opens by itself once per app run on the first new scene or on opening a .pse with scenes, and stays closed after the user closes it.
- A click or Enter recalls a scene; arrow keys, right-click and drags do not. Update stores everything on screen into the selected scene, keeps its message and refreshes its thumbnail.
- Double-click or F2 renames; a duplicate or empty name is refused and the old name stays.
- Dragging reorders, and PgUp/PgDn then follow the new order.
- The delete button, the right-click menu and Delete remove a scene.
- A scene stored with `scene new, store` in the command line or with Ctrl+F1 appears in the panel without any action in it; the current scene is highlighted.
- No upstream file changes (`modules/` outside `modules/pymol3/`); `bazel test //...` and `bazel test //distribution/...` pass.

## Verification

- `bazel test //tests/...` runs the panel's offscreen Qt tests against a real PyMOL instance: list contents and order, each operation's PyMOL command, sync without loops, thumbnail fetches on change only, opening on the first scene.
- `bazel test //distribution/...` passes, `//distribution/edited:edited_base_test` included.
- `python3 .opp/style/check.py --committed` reports no findings.
- By hand in the app on Windows: the acceptance criteria above with a loaded structure and at least 15 scenes.
