# A clean, documented PyMOL viewer widget for other Qt apps

**Goal:** Other Python applications put a PyMOL viewer into their own PyQt or PySide window with one documented class, `pymol3.widget.PyMOLWidget`, that has no hidden dependency on PyMOL's main window, takes commands like Jmol's viewer and reports back through Qt signals.

**Architecture:** A small additive C hook queues atom picks for Python. `PyMOLWidget` subclasses the existing `pmg_qt.pymol_gl_widget.PyMOLGLWidget` to inherit its tested mouse, gesture, HiDPI and drawing code, and replaces only its `__init__` so that it reads no command-line options, needs no PyMOL main window and redirects no process-wide output. It adds keyboard handling (through the existing `pmg_qt.keymapping`) and Jmol-style signals. It ships in the wheel through the `pymol3` package; the website gets a page with a complete example app.

**Tech Stack:** Python, `pymol.Qt` (PyQt5, PyQt6, PySide2, PySide6), `pymol2.SingletonPyMOL`, Bazel (`rules_python`), pytest with Qt's `offscreen` platform, Material for MkDocs for the website page.

**Spec:** The design approved in the brainstorming session of 2026-11-23, recorded in `## Design` below. Backlog source: the Notion list's "Easier embedding in PyQt-based applications".

## Design

**Why.** Developers who want PyMOL inside their own Qt application today copy and adapt `PyMOLGLWidget`, which expects PyMOL's main window as its parent, reads PyMOL's command-line options, redirects all Python output of the process and leaves keyboard handling to the main window. The developer's own tools (PySSA, JBioMOL) did the same by hand. PyMOL+ should offer one clean, documented widget, like Jmol's viewer.

**What a host developer writes.**

```python
from pymol3.widget import PyMOLWidget

viewer = PyMOLWidget(parent)                 # an ordinary QWidget
layout.addWidget(viewer)
viewer.cmd.fetch("1hpv")                     # PyMOL's usual cmd
viewer.do("show sticks, organic")            # a script line, like Jmol's script()
viewer.picked.connect(on_pick)               # an atom was clicked
viewer.feedback.connect(log)                 # PyMOL's output
```

**The widget.**

- `PyMOLWidget(parent=None, *, internal_gui=False, stereo=None, multisample=None)`: a `QWidget` subclass in the host's own Qt binding. `pymol.Qt` ignores what is already imported and tries PyQt5, PySide2, PyQt6, PySide6 in that order, so `pymol3.widget` detects the binding the host has imported (`sys.modules`) and sets `QT_API` before `pymol.Qt` is first imported; if `pymol.Qt` already chose another binding, it raises `RuntimeError` naming both.
- `.cmd`: PyMOL's global `cmd`; `from pymol import cmd` in the host is the same object, so existing PyMOL scripts and plugins work.
- `.do(script)`: runs PyMOL command-language lines.
- **Signals:** `picked(dict)` (object, segment, chain, residue name and number, atom name, index, state), `objects_changed()` (objects or selections created, deleted or renamed), `feedback(str)` (PyMOL's C feedback, always; Python output of commands run through `do()` too), `error(str)` (error lines, and tracebacks of commands run through `do()`). Output of `cmd` calls the host makes directly stays on the host's own `sys.stdout`/`sys.stderr`, which the widget never replaces; `do()` captures only for its own duration.
- **Input:** PyMOL's mouse modes, wheel, pinch gestures, and its keyboard shortcuts (arrows, Ctrl+…, F1–F12) while the viewer has focus.
- **Viewer only (developer's choice):** no menus, panels or palette; the classic internal GUI only when `internal_gui=True`.
- **One viewer per process, once:** a second `PyMOLWidget` raises `RuntimeError` naming the reason (the global PyMOL). PyMOL cannot be restarted reliably in one process (`SingletonPyMOL.stop()` leaves the C globals until garbage collection, and restarting after `PyMOL_Stop` is untested upstream), so closing the widget does not free the slot. If the host has already used `cmd` before creating the widget, PyMOL has started headless (`parse_args(['pymol','-cqk'])` in `layer4/Cmd.cpp`), and the widget raises `RuntimeError` telling the host to create the widget first.
- **Lifecycle:** PyMOL starts with the widget and stops when the host application quits. While the widget lives it installs the process-wide hooks the PyMOL app's `execapp()` installs (`cmd._call_with_opengl_context`, `_call_in_gui_thread`, `_copy_image`, the `viewport` and `full_screen` overloads), so `cmd.png`, `draw` and `refresh` use its GL context; it sets `pymol.invocation.options` from its own arguments before `SingletonPyMOL.start()` reads them. The host's own `sys.stdout` stays untouched.
- **Wayland:** the subclass carries the app's fractional-scaling fix in `resizeGL` (the only difference of `distribution/edited/pmg_qt/pymol_gl_widget.py` from upstream), so wheel users get it too.
- **Documentation:** a website page "Embedding PyMOL+" with installation (`pip install pymol-open-source-whl`), the API above, a complete small example app, and the limits (one viewer per process, viewer only).

**Approaches considered.**

- **A. A subclass of the existing `PyMOLGLWidget` (chosen).** Inherits the tested input and drawing code, replaces only `__init__`, adds keys and signals; fixes in the upstream class carry over; an upstream change that breaks the subclass is caught by the tests.
- B. A separate class written from scratch. Independent of upstream internals, but copies about 280 lines of input code and maintains them alone. Rejected.
- C. The existing class unchanged with a stand-in main window. Keeps the process-wide output redirect and the command-line options. Rejected.

**Decisions made with the developer.**

- One clean, documented widget for other Python apps' PyQt GUIs.
- Viewer only, like Jmol; Jmol-style commands and callbacks as Qt signals.
- Built as approach A.
- Picks are reported by a small, purely additive C hook: every atom pick, in every mouse mode and alongside any wizard, is queued in C and read by the widget on its next GUI tick through a new `_cmd` entry reached via `pymol3` (reviewer question, accepted 2026-11-23). It sits in marked blocks, like the read-only getters of `features/objects-panel.md`; no existing C behaviour changes.

**Calls made in the design (Claude's, open to correction).**

- The widget lives in `pymol3` and therefore in the wheel, where other apps get PyMOL; the app bundle carries it too.
- It uses the global PyMOL (`SingletonPyMOL`), so one viewer per process for the process's lifetime; several viewers and restarts are non-goals.
- `picked` never takes over PyMOL's wizard slot, so a host's or user's wizard keeps working and still receives its picks.
- Drag and drop of files onto the viewer loads them with `cmd.load` (no main window to ask), and can be turned off with `accept_drops=False`.

**Facts from the code that bind the design.**

- `PyMOLGLWidget.__init__` (`modules/pmg_qt/pymol_gl_widget.py`) stores `self.gui = parent`, reads `pymol.invocation.options` (multisample, stereo), starts `SingletonPyMOL` and calls `pcatch._install()`; `dropEvent` calls `self.gui.load_dialog()`.
- The widget has no `keyPressEvent`; the main window's (`pymol_qt_gui.py`) turns keys into PyMOL calls through `pmg_qt.keymapping.keyPressEventToPyMOLButtonArgs()`.
- `pymol.Qt` supports PyQt5, PySide2, PyQt6 and PySide6, chosen by `QT_API` or by what is available.

## Global Constraints

Quoted from AGENTS.md and the `pymol3-dock-panels` plan:

- No file under `modules/pymol/`, `modules/pmg_qt/`, `modules/pmg_tk/`, `modules/chempy/` or `modules/pymol2/` changes; the subclass lives in `pymol3`.
- Upstream C++ only gains the pick queue and its `_cmd` reader, in blocks marked `BEGIN PYMOL+ ADDITION` / `END PYMOL+ ADDITION`, as ADR `docs/decisions/0002-additive-cpp-entry-points.md` allows; no existing C++ function's behaviour changes. C++ follows `opp-workflow:cpp-style`.
- Never remove or change anything in PyMOL's existing API; only add.
- "New dependency versions only when they are at least 14 days old"; PyQt5 and PyQt6 join only as test dependencies in `tools/bazel/requirements.in` (PySide6-Essentials is there already), never as runtime dependencies of the wheel.
- Python follows `opp-workflow:python-style`; `python3 .opp/style/check.py --committed` passes on each step's last push.
- "Pull requests get the Bazel check only."
- "Website: Material for MkDocs until the stable Zensical release (switch planned for March 2027); no Zensical code before that." The website is built by `mkdocs` in `docs.yaml`, not by Bazel.
- New files carry `SPDX-License-Identifier: BSD-3-Clause`.

## Scope

modules/pymol3/**
tests/pymol3_*/**
layer1/SceneMouse.cpp
layer1/Scene.h
layer4/Cmd.cpp
layer5/PyMOL.cpp
layer5/PyMOL.h
tools/bazel/requirements.in
tools/bazel/requirements_lock*.txt
distribution/docs/website/**

## Done

All three steps below are merged into `production`, and the example app runs with the wheel built from `production` under PyQt6 and PySide6. Releasing the wheel and publishing the website follow the usual release flow and are not part of this feature.

## Non-goals

- Several independent viewers in one process.
- Menus, panels, the command palette or other PyMOL+ interface in the widget.
- Jupyter or web embedding.
- Changing the PyMOL+ app's own viewer, which keeps using `PyMOLGLWidget`.
- PySide2 tests on Python 3.13, which PySide2 does not support; it stays supported through `pymol.Qt` as today.
- Restarting PyMOL in the same process after the widget is closed.
- Making a wheel or website release.

## Steps

Each step is one branch from `production` and one pull request into `production`; each step's own Superpowers plan goes to `.opp/plans/<branch>.md` when it starts.

1. **The pick hook** (`embeddable-widget-picks`): the additive C pick queue (object, segment, chain, residue, atom, index, state per pick, in every mouse mode), its `_cmd` reader and `pymol3.query.picks()`; tested from Python by simulating picks in a headless PyMOL with and without an active wizard; the wheel builds on every platform.
2. **The widget** (`embeddable-widget`): `pymol3.widget.PyMOLWidget` with its `__init__`, binding detection, keys, `do()`, the four signals, drag and drop, the one-viewer rule, the process-wide hooks and the Wayland fix. Tests run in their own processes, one Bazel target per binding (PySide6, PyQt6, PyQt5), apart from `//tests`, whose undo tests already start a headless PyMOL and whose `pymol3_ui` tests must stay on PySide6. Offscreen tests cover what needs no OpenGL (construction, binding detection, `do()`, signals from commands, keys reaching PyMOL, the host's `sys.stdout`, the one-viewer rule); rendering, rotation and real picks are checked by a test tagged `manual` that needs a display, and by hand.
3. **Documentation and example** (`embeddable-widget-docs`): the website page "Embedding PyMOL+" and the example app as a file in the repository, run by a test so the page's code never goes stale.

## Review Focus

- **The host's output hijacked.** `pcatch._install()` replaces `sys.stdout` for the whole process. Covered by a test that prints from the host after creating the widget and finds the text on the host's own stream.
- **Keys swallowed or doubled.** With the viewer focused, PyMOL's shortcuts must work, and the host's own shortcuts (menus, QShortcuts) must still win. Covered by a test with a host QShortcut on Ctrl+O and a PyMOL arrow-key binding.
- **The upstream base class changing.** A change to `PyMOLGLWidget.__init__` or its attributes can break the subclass silently. Covered by the step 2 tests running against the in-repo `pmg_qt` on every build.
- **A user's wizard blocked.** `picked` must keep working while a wizard such as Measurement is active, and the wizard must keep receiving its picks. Covered by a test with an active wizard.

## Acceptance criteria

- A plain PyQt6 or PySide6 `QMainWindow` with `PyMOLWidget` shows a fetched structure, rotates and zooms with the mouse, and reacts to PyMOL's keyboard shortcuts while focused.
- `viewer.cmd` is `pymol.cmd`; `viewer.do()` runs command-language lines.
- `picked`, `objects_changed`, `feedback` and `error` fire as described, and a wizard keeps working alongside `picked`.
- Creating a second widget raises `RuntimeError`, also after the first is destroyed.
- The host's `sys.stdout` is unchanged after the widget starts.
- The website page's example app runs as written.
- No upstream Python file changes (`modules/` outside `modules/pymol3/`); upstream C++ changes only by the marked, additive blocks in `## Scope` (`BEGIN PYMOL+ ADDITION` / `END PYMOL+ ADDITION`); `bazel test //...` passes.

## Verification

- `bazel test //tests/...` runs the widget tests offscreen in one target per binding (PySide6, PyQt6, PyQt5), and the example-app test.
- The `manual` display test, run on a desktop, renders, rotates and picks.
- `mkdocs build --strict` (as `docs.yaml` runs it) builds the new page without warnings.
- `python3 .opp/style/check.py --committed` reports no findings.
- By hand on Windows, macOS and Linux: the example app with the wheel built by `bazel build //tools/bazel/wheel:wheel`.
