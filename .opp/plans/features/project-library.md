# A project library with chat-style sessions

**Goal:** PyMOL+ keeps all work in a project library: a sidebar on the left lists projects and their sessions ("chats") like the Claude app's sidebar, every imported structure is copied into its project, every session saves itself, sessions can be forked, and projects can be exported and imported as ZIP files; no more loose session and structure files on the scientist's laptop.

**Architecture:** A Qt-free module `pymol3.projects` owns the library on disk (project folders, a manifest per project, auto-saving, forking, ZIP export and import) and switches sessions in the one global PyMOL by saving the current session and loading the next. A `pymol3` panel docked on the left through `pymol3.ui.add_dock_panel(..., area="left")` shows it. Short marked hooks in the app's copy of `pymol_qt_gui.py` capture imports at `load_dialog()`, point `fetch_path` at the current project, and save on close.

**Tech Stack:** Python (`zipfile`, `json`, `pathlib`), `pymol.Qt` (PySide6 6.9 in the app; `QStandardPaths`, `QFile.moveToTrash`), `pymol3.ui`, Bazel (`rules_python`), pytest, with Qt's `offscreen` platform for the panel.

**Spec:** The design approved in the brainstorming session of 2026-11-23, recorded in `## Design` below. Backlog source: an idea raised in that session; it absorbs the Notion list's "PyMOL session auto-saving".

## Design

**Why.** Scientists end up with loose `.pse` files and downloaded structures scattered across Downloads and Desktop, and no record of which belongs to what. PyMOL+ should give their work a clear structure: every session and every structure belongs to a project in one library, and nothing needs saving by hand. Instant switching between sessions is not needed for now.

**What the user sees.**

- **Sidebar (left).** Projects as expandable entries; under each, its chats, newest change first. A **New chat** button at the top creates a chat in the current project; a **New project** entry creates a project. Right-click on a chat: **Fork**, **Rename**, **Delete**, **Export session…**; on a project: **Rename**, **Delete**, **Export project…**. Clicking a chat switches the viewer to it. The current chat is highlighted, and the window title shows "<project> / <chat>". The left layout toggle of the command palette feature (`features/command-palette.md`) shows and hides the sidebar.
- **Always inside a project.** On first start PyMOL+ creates the project **Unsorted** with one chat and opens it, so a quick look needs no decision; a chat can be moved to another project later (right-click → **Move to…**). At every later start, the last opened chat comes back.
- **Imports are copied in.** A structure opened with **File → Open** or dropped onto the window is copied into the current project's `assets/` folder and loaded from there; `fetch` saves its downloads there too. Opening an existing `.pse` asks, as PyMOL does today, but with two answers: **Open as new chat** (the default), which copies it into the current project as a new chat, and **Merge into this chat**; PyMOL's "new window" and "replace" choices go. `load x.pse` typed in the command line or run from a script keeps PyMOL's behaviour and replaces the current chat's content, which the next save writes into that chat. `cmd.load` calls inside scripts and plugins are not copied, but their data still ends up in the session, which holds the molecule data itself.
- **Saving is automatic.** The current chat is saved when switching chats, when PyMOL+ closes, and every five minutes while it has unsaved changes. PyMOL keeps no reliable change flag (see Facts), so `pymol3.projects` keeps its own: a cheap fingerprint taken on each GUI tick (object names and state counts, the view, the scene list, and any setting change reported through `setting_callbacks`). **Ctrl+S** saves at once. **Save Session As…** becomes **export of a single session**: it copies a `.pse` out of the library to a place the user picks.
- **Fork** copies the chat's session into a new chat, "<name> (fork)", in the same project and opens it; assets are shared within the project, not copied.
- **Delete** moves a chat's session file, or a whole project folder, to the operating system's trash, so it can be undone.
- **Library location.** The library defaults to a folder **PyMOL Projects** in the user's Documents folder; **File → Library location…** changes it (for example to a synced folder), and PyMOL+ then lists the projects found there.
- **Export and import.** **Export project…** writes one ZIP with `assets/` and `sessions/`; its sessions open in plain PyMOL. **File → Import project…** brings such a ZIP into the library as a new project (a name in use gets a number appended).

**On disk.**

```
<library>/                         (default: Documents/PyMOL Projects)
  Unsorted/
    project.json                   manifest: chats (id, title, file, created, modified, forked_from), last opened
    assets/   4HHB.cif  ligand.sdf
    sessions/ Overview.pse  Overview (fork).pse
  Kinase study/ …
```

**Approaches considered.**

- **A. One PyMOL, imports captured at the GUI's entry points (chosen).** Switching saves and loads in the single global PyMOL, so menus, plugins, scripts and `from pymol import cmd` keep working. Imports are captured where users bring files in: `fetch_path`, and `load_dialog()`, through which both File → Open and drag and drop run.
- B. Wrap `cmd.load` so every load copies its file. Complete, but changes a core command that scripts and plugins rely on (paths, mass loads, temporary files), against never changing PyMOL's API. Rejected.
- C. Several live `pymol2.PyMOL` instances switched behind the viewer. Instant switching, which is not needed now; and the app's viewer uses `pymol2.SingletonPyMOL` (`distribution/edited/pmg_qt/pymol_gl_widget.py`), so menus and plugins would keep talking to the global instance. Rejected for now; A does not block it later.

**Decisions made with the developer.**

- Order is the goal; instant switching is not needed for now.
- One library folder, its location configurable; projects can be exported (and imported).
- Everything inside a project, with **Unsorted** as the start; File → Open copies into the current project.
- Save Session As… becomes the export of a single session.
- Built as approach A.
- A chat open in one PyMOL+ window is locked: other windows show it greyed ("open in another window") and cannot open it. A second PyMOL+ process (a double-clicked file, File → New Window) starts in a new chat in Unsorted, and files from its launch arguments go into that chat (reviewer question, accepted 2026-11-23).
- Opening a `.pse` asks: Open as new chat (default) or Merge into this chat (reviewer question, accepted 2026-11-23).
- `load x.pse` from the command line or a script replaces the current chat's content, as in PyMOL (reviewer question, accepted 2026-11-23).

**Calls made in the design (Claude's, open to correction).**

- Imports are copied, not linked; sessions never depend on `assets/`, which keeps the originals for order and traceability.
- Fork shares assets; it copies only the session.
- Auto-save every five minutes while changed, plus on switch and close; Ctrl+S saves at once.
- Delete goes to the system trash (`QFile.moveToTrash`), not a permanent delete.
- The default library is `Documents/PyMOL Projects` (`QStandardPaths.DocumentsLocation`); its location is stored in the app's `QSettings('PyMOL-Open-Source', 'PyMOL-Open-Source')`.
- Session files are named after the chat's title and renamed with it, so an exported project reads well; the manifest's id keeps the link.
- The ZIP is a plain folder copy; import gives a project whose name is in use a number ("Kinase study 2").
- This feature replaces the backlog item "PyMOL session auto-saving".
- Auto-save uses its own change fingerprint; a save of a large session may pause the GUI briefly, accepted for now (saves happen at most every five minutes and only after changes).
- Copied into `assets/`: structure, map, sequence and alignment files. Scripts (`.pml`, `.py`) are run in place and never copied, since they rely on paths relative to their own folder. A file over 200 MB (trajectories) is copied only after asking, with its size shown.
- Exported sessions target current open-source PyMOL 3.x; no older `pse_export_version` is pinned.
- The sidebar does not wait for the palette's layout toggles: until they exist, `pymol3.ui`'s Display → Plugin Panels entry shows and hides it.

**Facts from the code that bind the design.**

- File → Open, drag and drop on the viewer (`PyMOLGLWidget.dropEvent()`), Recent Files and the macOS FileOpen event all end in `load_dialog(fname)`. It is defined in the upstream `modules/pmg_qt/file_dialogs.py` and bound as a class attribute in the edited `pymol_qt_gui.py` (around line 50); the hook replaces that binding in the edited class with a `pymol3` wrapper, so `file_dialogs.py` stays untouched.
- `fetch_path` (setting 507, default `"."`) is where `fetch` stores downloads; it is not stored in sessions (`Setting.cpp`, `is_session_blacklisted`), so the app sets it on every switch. `download_chem_comp` (`internal.py`) also caches ligand CIFs there, which is wanted (they belong to the project); the plugin repository (`plugins/repository.py`) saves downloads there too, so the hook points the plugin manager at its own folder. A `fetch_path` set in `.pymolrc` is overridden while a project is open.
- `session_file` (setting 440) holds the current session's path, and `session_save()` (Ctrl+S, line 405) saves to it. `cmd.save(*.pse)` (`exporting.py`) and a non-partial `cmd.load(*.pse)` (`importing.py`) both overwrite it, so the library tracks the current chat itself and resets `session_file` to the chat's file after any such save or load; Ctrl+S is bound to the library's save. The window title is set from it in a marked segment (`setting_callbacks[440]`), which this feature extends to "<project> / <chat>".
- `session_changed` (setting 521) is dead: nothing in the C or Python code sets it; only the unused Tk skin reads it. Change detection is this feature's own.
- `closeEvent()` calls `cmd.quit()`, File → Quit calls `QApplication.quit()` (`confirm_quit`), and the `quit` command goes through `cmd._quit` without either. The window's close and File → Quit save first and stop on a failed save; the `quit` command cannot be stopped without changing PyMOL's API, so it relies on a save attempt registered for shutdown and on the last auto-save.

## Global Constraints

Quoted from AGENTS.md and the `pymol3-dock-panels` plan:

- "App: PySide6 stays at 6.9 (6.10+ drops macOS 12 and RHEL/AlmaLinux 8); Python 3.13."
- "`distribution/edited/` holds upstream PyMOL files with marked edits (`BEGIN EDITED CODE SEGMENT`)"; no file under `modules/pymol/`, `modules/pmg_qt/`, `modules/pmg_tk/`, `modules/chempy/` or `modules/pymol2/` changes.
- Never remove or change anything in PyMOL's existing command or Python API; only add.
- "New dependency versions only when they are at least 14 days old"; no new runtime dependency is planned (the trash and the Documents folder come from Qt).
- Python follows `opp-workflow:python-style`; `python3 .opp/style/check.py --committed` passes on each step's last push.
- "Pull requests get the Bazel check only."
- New files carry `SPDX-License-Identifier: BSD-3-Clause`.

## Scope

modules/pymol3/**
tests/pymol3_*/**
distribution/edited/pmg_qt/pymol_qt_gui.py
distribution/edited/pmg_qt/pymol_gl_widget.py

## Done

All three steps below are merged into `production`, and a fresh app start opens a chat in the project Unsorted inside the library.

## Non-goals

- Instant switching or several sessions computing at once (approach C).
- Copying files that scripts or plugins load with `cmd.load`.
- Sharing or syncing projects between people beyond ZIP export and import; no conflict handling for libraries in synced folders beyond what the file system gives.
- Version history of a session beyond forks.
- Wheel users' GUI: the hooks are in the app's edited copy only; `pymol3.projects` is usable from Python by anyone.
- Migrating loose files already on the laptop automatically; they come in as the user opens them.

## Steps

Each step is one branch from `production` and one pull request into `production`; each step's own Superpowers plan goes to `.opp/plans/<branch>.md` when it starts. Until step 2, nothing changes for the user.

1. **Library core** (`project-library-core`): `pymol3.projects` without Qt beyond `QStandardPaths`/`QFile.moveToTrash` behind a small seam: library location, project folders and manifest, Unsorted, chats (create, rename, move, fork, delete to trash), switching by save and load, auto-save rules, export of a session, ZIP export and import of a project. Tested headless against a real PyMOL and a temporary library.
2. **Sidebar and start-up** (`project-library-sidebar`): the left panel, the start-up hook that opens the last chat (or creates Unsorted), `session_file` and the window title, saving on close, the five-minute auto-save, Ctrl+S, and Save Session As… as export.
3. **Imports, library location and project ZIPs in the GUI** (`project-library-imports`): the `load_dialog()` hook that copies structures into `assets/` and turns opened `.pse` files into chats, `fetch_path` following the current project, File → Library location…, File → Import project…, and Export project… / Export session… in the sidebar.

## Review Focus

- **Losing work on switch or close.** A failed save (disk full, file locked by a sync client) must stop the switch or the close and say so, never discard the session. Covered by tests that make the save fail and check that the current session is still loaded and the user is told.
- **A second PyMOL+ on the same library.** Two windows auto-saving the same chat overwrite each other. A lock per open chat (a lock file in the project, cleared when stale after a crash) keeps other windows out; a second process starts in a new chat in Unsorted. Covered by a test with two library objects on one folder.
- **Names from users.** Chat and project titles become file and folder names: characters invalid on Windows, names differing only in case on macOS and Windows, and very long names. Covered by a test of the name mapping.
- **Switching inherits state.** Loading the next session must not keep settings, wizards or the `fetch_path` of the previous one. Covered by a test that switches between two chats with different state.

## Acceptance criteria

- On first start the library holds the project Unsorted with one open chat; on later starts the last chat comes back. A second PyMOL+ process starts in a new chat in Unsorted, with any double-clicked file in it, and shows the first window's chat as locked.
- Opening a `.pse` offers Open as new chat (default) and Merge into this chat.
- The sidebar lists projects and chats; clicking a chat switches to it, and the previous chat is saved first.
- File → Open and drag and drop copy the structure into the current project's `assets/`; `fetch` downloads there; opening a `.pse` creates a chat with a copy of it.
- Closing PyMOL+, switching, Ctrl+S and five minutes of unsaved changes each save the current chat.
- Fork creates "<name> (fork)" with a copy of the session; Delete moves to the trash.
- Save Session As… writes a copy outside the library and leaves the chat where it is.
- File → Library location… switches to another folder and lists its projects.
- Export project… writes a ZIP whose sessions open in plain PyMOL; Import project… brings it back as a new project.
- No upstream file changes (`modules/` outside `modules/pymol3/`); `bazel test //...` and `bazel test //distribution/...` pass.

## Verification

- `bazel test //tests/...` runs `pymol3.projects`' headless tests against a real PyMOL and a temporary library (folders, manifest, switching, fork, trash seam, ZIP round trip, name mapping, locks, failed saves) and the sidebar's offscreen Qt tests.
- `bazel test //distribution/...` passes, `//distribution/edited:edited_base_test` included, and the app's headless smoke test still starts.
- `python3 .opp/style/check.py --committed` reports no findings.
- By hand in the app on Windows and macOS: the acceptance criteria above, and an exported project opened in plain PyMOL.
