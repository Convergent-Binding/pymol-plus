# pymol3: an API for plugins to dock their own panels

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Any PyMOL plugin can put its own panel into one of the main window's four dock areas with one public call, `pymol3.gui.add_dock_panel(...)`, while every existing PyMOL API stays exactly as it is.

**Architecture:** A new top-level package `modules/pymol3/`, shipped in the wheel (and through it in the app), holds this repository's own additions to PyMOL. Its module `pymol3.gui` finds the Qt main window through the existing `pymol.gui.get_qtwindow()`, wraps the plugin's widget in a `QDockWidget`, and returns a `DockPanel` handle. No upstream file under `modules/pymol`, `modules/pmg_qt` or `distribution/edited/` changes.

**Tech Stack:** Python, `pymol.Qt` (whichever Qt binding PyMOL found), Bazel (`rules_python`), pytest with Qt's `offscreen` platform, PySide6-Essentials 6.9.3 for the tests.

**Spec:** the design approved in the session of 2026-11-23, recorded in `## Design` below.

## Design

**Why.** PyMOL plugin developers have only `pymol.plugins.addmenuitemqt()`; a plugin that wants a docked panel reaches into `QMainWindow` itself, and nothing manages that panel afterwards. `pymol3` gives them one public, supported call. It only adds: no existing function, class or signature changes or disappears.

**Approaches considered.**
- **A. A function plus a handle (chosen).** `add_dock_panel()` returns a `DockPanel`; no upstream file is touched, so `//distribution/edited:edited_base_test` stays green; small and testable against a plain `QMainWindow`.
- B. `DockPanel` subclasses with a registry, lazy creation and saved layout: about three times the code and a persistence format to specify. Can be built on A later without breaking it.
- C. A new method on `PyMOLQtGUI`: edits upstream `pymol_qt_gui.py` and its marked copy, against keeping this repository's code in `pymol3`. Rejected.

**API (`pymol3.gui`).**
- `add_dock_panel(widget, title, area="right", panel_id=None, floating=False) -> DockPanel`
  - `area`: `"left"`, `"right"`, `"top"`, `"bottom"` (case-insensitive) or a `Qt.DockWidgetArea` member.
  - `panel_id` defaults to `title`.
  - A panel added to an area that already holds a docked `pymol3` panel is tabbed with it.
  - Each panel gets a checkable show/hide entry, labelled with its title, in a submenu **Display → Plugin Panels**, reached through the window's existing `menudict`. A window without `menudict` or without a `"Display"` entry gets the panel without a menu entry.
- `get_dock_panel(panel_id) -> DockPanel | None`
- `DockPanel`: `.panel_id`, `.dock_widget` (the `QDockWidget`, for anything beyond the basics), `.show()` (shows and raises), `.hide()`, `.is_visible()` (true unless hidden, also when tabbed behind another panel), `.remove()` (takes the panel and its menu entry out, frees the id, deletes the dock widget and the plugin's widget with it; a second call does nothing).

**Errors.**
- No Qt main window (`pymol -c`, the Tk GUI, `pymol2` embedded in another program, or no Qt binding): `pymol.plugins.QtNotAvailableError`, as `addmenuitemqt()` raises.
- A `panel_id` already in use, or an unknown `area`: `ValueError`.
- A call from any thread but the GUI thread: `RuntimeError`.

**Calls made in the design, approved with it.**
- Plugins load after the window exists (`execapp()` calls `window.initializePlugins()` after `window.show()`), so `__init_plugin__` may call `add_dock_panel()` directly; no deferral.
- A reused `panel_id` raises rather than replacing; a plugin that loads twice looks its panel up with `get_dock_panel()` first.
- The menu entries go under **Display**, where the External GUI's show/hide entry already is.
- The tests run offscreen against a real `QMainWindow` with a `menudict`, returned by a patched `pymol.gui.get_qtwindow`; only PySide6-Essentials 6.9.3 (the app's pin) joins `tools/bazel/requirements.in`, no `pytest-qt`.

**Calls made while planning.**
- The panel registry is a dict stored on the window object (attribute `_pymol3_dock_panels`), not a module global: one window, one registry, and each test's fresh window starts empty.
- `pymol3.gui` imports no Qt binding at import time; `import pymol3.gui` works headless and without Qt, and `add_dock_panel()` turns the binding's `ImportError` into `QtNotAvailableError`.
- Each dock widget's `objectName` is `pymol3_panel_<panel_id>`, so a later layout-saving feature can address it.
- New files carry this repository's own licence for its code, `SPDX-License-Identifier: BSD-3-Clause`, and the indentation of the repository's own Python (2 spaces, `distribution/pyproject.toml`'s ruff settings).

## Global Constraints

- Never remove or change anything in PyMOL's existing API; only add.
- No file under `modules/pymol/`, `modules/pmg_qt/`, `modules/pmg_tk/`, `modules/chempy/`, `modules/pymol2/` or `distribution/edited/` changes.
- "App: PySide6 stays at 6.9"; the test dependency is `PySide6-Essentials==6.9.3`, the pin in `distribution/requirements_lock.txt`.
- "New dependency versions only when they are at least 14 days old."
- Python follows `opp-workflow:python-style`; `python3 .opp/style/check.py --committed` passes on the last push.
- Pull requests get the Bazel check only; the branch `pymol3-dock-panels` starts from `origin/production` and ends in a pull request into `production`.

## Review Focus

1. **The wheel test job without a display or without Qt.** `scripts/test_wheel.py` runs `tests/` against each installed release wheel; there the Qt tests must skip when no binding is installed and must not try to open a real display when one is. Covered by `pytest.importorskip("pymol.Qt")` and `QT_QPA_PLATFORM=offscreen` set before the import in `tests/pymol3/conftest.py` (Task 2), and by `test_import_needs_no_qt_binding` (Task 2).
2. **A plugin loaded twice** (the plugin manager's reload) reusing its `panel_id`: `ValueError`, and `get_dock_panel()` finds the first panel. `test_duplicate_panel_id_raises_value_error` (Task 2).
3. **`remove()` called twice, or `show()` after `remove()`:** the second `remove()` does nothing; `show()` after `remove()` raises `RuntimeError("panel was removed")` rather than touching a deleted Qt object. `test_remove_twice_is_harmless`, `test_show_after_remove_raises` (Task 2).
4. **A call from a command typed at `PyMOL>` or a `run` script**, which must run in the GUI thread for the API to be usable from scripts. Pinned by the manual check in Task 4; if it raises the thread error there, stop and bring it back to the developer.
5. **A panel the user closed with the dock's own close button:** it is hidden, not removed; its menu entry unchecks and `show()` brings it back. `test_close_button_hides_and_menu_unchecks` (Task 3).

## Scope

modules/pymol3/**
tests/pymol3/**
tests/BUILD.bazel
tools/bazel/wheel/BUILD.bazel
tools/bazel/tests/wheel_layout_test.py
tools/bazel/requirements.in
tools/bazel/requirements_lock.txt
MODULE.bazel.lock
README.md
.opp/plans/pymol3-dock-panels.md

## Done

`pymol3.gui.add_dock_panel()` docks a plugin's widget in the requested area of the running PyMOL window, the wheel ships `pymol3`, every test named below passes, and nothing outside `## Scope` changed.

## Non-goals

- Saving and restoring where panels were and whether they were open across restarts.
- Approach B's `DockPanel` subclasses, registry and lazy creation.
- The Tk GUI (`pmg_tk`) and the `pymol2` embedding: both get `QtNotAvailableError`.
- Restricting which areas a panel may be dragged to (`.dock_widget.setAllowedAreas()` remains available to the plugin).
- Marshalling calls from other threads into the GUI thread.

## Interfaces

```python
# modules/pymol3/gui.py
def add_dock_panel(
    widget: QtWidgets.QWidget,
    title: str,
    area: str | QtCore.Qt.DockWidgetArea = "right",
    panel_id: str | None = None,
    floating: bool = False,
) -> DockPanel: ...

def get_dock_panel(panel_id: str) -> DockPanel | None: ...

class DockPanel:
  panel_id: str                          # read-only property
  dock_widget: QtWidgets.QDockWidget     # read-only property
  def show(self) -> None: ...
  def hide(self) -> None: ...
  def is_visible(self) -> bool: ...
  def remove(self) -> None: ...
```

`DockPanel` is created only by `add_dock_panel()`; its constructor is private API. Annotations naming Qt types sit under `TYPE_CHECKING` or as strings, so the module imports no binding at import time.

## Edge cases

- `area` given in any letter case (`"Left"`) is accepted; anything else, including `Qt.DockWidgetArea.AllDockWidgetAreas` and `NoDockWidgetArea`, raises `ValueError` naming the four accepted names.
- `floating=True`: the panel is placed in `area` first, then floated, so docking it back puts it in `area`; it is not tabbed with other panels.
- Tabbing considers only panels in the registry that are docked (not floating, not removed) in the same area; the new panel joins the most recently added one.
- `remove()` of the last panel leaves the empty **Plugin Panels** submenu in place.

## Acceptance criteria

- `from pymol3 import gui` works in an installed wheel, also without any Qt binding.
- `gui.add_dock_panel(widget, "Title", area=...)` docks `widget` in each of the four areas, by name or by `Qt.DockWidgetArea`; the default is the right area.
- A second panel in the same area is tabbed with the first; a panel in another area is not.
- Each panel has a checkable entry under **Display → Plugin Panels** that shows and hides it and follows its visibility; `remove()` takes the entry away.
- `get_dock_panel()` returns the handle for a live id and `None` otherwise; a freed id can be used again.
- Without a Qt main window the call raises `pymol.plugins.QtNotAvailableError`; a reused id or an unknown area raises `ValueError`; a call off the GUI thread raises `RuntimeError`.
- `git diff origin/production --stat` lists only paths in `## Scope`.
- README.md documents the API with a short plugin example.

## Reach

- `pymol.gui.get_qtwindow()` (`modules/pymol/gui.py:28`) is read, not changed; it imports `pmg_qt.pymol_qt_gui.window`, which `execapp()` sets before `initializePlugins()` (`modules/pmg_qt/pymol_qt_gui.py:1224-1300`).
- `PyMOLQtGUI.menudict['Display']` (`modules/pmg_qt/pymol_qt_gui.py:362-394`) is read to add a submenu; the window already enables tabbed and nested docks (`:102`).
- `pymol.plugins.QtNotAvailableError` (`modules/pymol/plugins/__init__.py:34`) is reused, not changed.
- `_PACKAGES` in `tools/bazel/wheel/BUILD.bazel` gains `//modules/pymol3`; the app bundle takes the wheel, so the app ships `pymol3` without a change under `distribution/`.

## Tasks

### Task 1: The `pymol3` package in the wheel

**Files:**
- Create: `modules/pymol3/__init__.py`, `modules/pymol3/BUILD.bazel`
- Modify: `tools/bazel/wheel/BUILD.bazel` (`_PACKAGES`), `tools/bazel/tests/wheel_layout_test.py` (`test_packages_and_data_are_at_installed_paths`)

**Interfaces:**
- Produces: the Bazel target `//modules/pymol3` (a `py_library` like `//modules/pymol2`: `srcs = glob(["**/*.py"])`, `imports = [".."]`, public visibility) and the import name `pymol3`.

- [ ] **Step 1: Write the failing test.** Add `"pymol3/__init__.py"` to the member tuple of `test_packages_and_data_are_at_installed_paths`.
- [ ] **Step 2: Run it to see it fail.** `bazel test //tools/bazel/tests:wheel_layout_test` → FAIL, `'pymol3/__init__.py' not found`.
- [ ] **Step 3: Add the package.** `modules/pymol3/__init__.py` holds only the SPDX line and a module docstring saying that `pymol3` holds this repository's additions to PyMOL's API, never changes to it. `modules/pymol3/BUILD.bazel` as in Interfaces. Append `"//modules/pymol3"` to `_PACKAGES`.
- [ ] **Step 4: Run it to see it pass.** `bazel test //tools/bazel/tests:wheel_layout_test` → PASS.
- [ ] **Step 5: Commit.** `git add modules/pymol3 tools/bazel/wheel/BUILD.bazel tools/bazel/tests/wheel_layout_test.py` → `feat: ship a pymol3 package for additions to PyMOL's API`

### Task 2: `add_dock_panel`, `get_dock_panel` and `DockPanel`

**Files:**
- Create: `modules/pymol3/gui.py`, `tests/pymol3/__init__.py`, `tests/pymol3/conftest.py`, `tests/pymol3/test_gui.py`, `tests/pymol3/test_gui_headless.py`
- Modify: `tools/bazel/requirements.in`, `tools/bazel/requirements_lock.txt`, `MODULE.bazel.lock`, `tests/BUILD.bazel`

**Interfaces:**
- Consumes: `//modules/pymol3` (Task 1).
- Produces: `add_dock_panel`, `get_dock_panel`, `DockPanel` as in `## Interfaces`; the fixture `main_window` in `tests/pymol3/conftest.py` (a `QMainWindow` with a central widget and `menudict = {"": menubar, "Display": <QMenu>}`, returned by a monkeypatched `pymol.gui.get_qtwindow`, shown, and closed after the test).

- [ ] **Step 1: Add the test dependency.** Append `PySide6-Essentials==6.9.3` to `tools/bazel/requirements.in` with a comment line saying the `pymol3` GUI tests need a Qt binding, pinned as the app's; run `bazel run //tools/bazel:requirements.update`. In `tests/BUILD.bazel` add `"//modules/pymol3"` and `"@pymol_pip//pyside6_essentials"` to `deps` and `env = {"QT_QPA_PLATFORM": "offscreen"}`.
- [ ] **Step 2: Write the fixture.** `tests/pymol3/conftest.py` sets `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` at import; fixture `main_window` as in Interfaces calls `pytest.importorskip("pymol.Qt")` first (inside the fixture, so the headless tests still run without Qt), then reuses `QApplication.instance()` or creates one.
- [ ] **Step 3: Write the failing tests** in `tests/pymol3/test_gui.py`, each with a one-line docstring:
  - `test_docks_widget_in_requested_area` (parametrized over `"left"`, `"Right"`, `"top"`, `"bottom"` and `Qt.DockWidgetArea.BottomDockWidgetArea`): `main_window.dockWidgetArea(panel.dock_widget)` is the matching area; `panel.dock_widget.widget() is tmp_label`; `panel.dock_widget.windowTitle() == "Sequences"`.
  - `test_area_defaults_to_right`: area is `RightDockWidgetArea`.
  - `test_panel_id_defaults_to_title`: `panel.panel_id == "Sequences"` and `gui.get_dock_panel("Sequences") is panel`.
  - `test_object_name_carries_panel_id`: `panel.dock_widget.objectName() == "pymol3_panel_seq"`.
  - `test_get_dock_panel_returns_none_for_unknown_id`.
  - `test_hide_and_show`: after `hide()`, `is_visible()` is `False` and `dock_widget.isHidden()`; after `show()`, both flip.
  - `test_floating_panel_floats`: `floating=True` → `dock_widget.isFloating()`.
  - `test_remove_frees_id`: after `remove()`, `get_dock_panel("seq") is None` and `add_dock_panel(QLabel(), "Again", panel_id="seq")` succeeds.
  - `test_remove_twice_is_harmless`: second `remove()` raises nothing.
  - `test_show_after_remove_raises`: `pytest.raises(RuntimeError, match="removed")`.
  - `test_duplicate_panel_id_raises_value_error`: second `add_dock_panel(..., panel_id="seq")` raises `ValueError`; `get_dock_panel("seq")` is still the first panel.
  - `test_unknown_area_raises_value_error` (parametrized over `"middle"` and `Qt.DockWidgetArea.AllDockWidgetAreas`): `ValueError` whose message names `left`, `right`, `top`, `bottom`; no panel is registered.

  And in `tests/pymol3/test_gui_headless.py`, which imports no Qt binding:
  - `test_import_needs_no_qt_binding`: in a fresh interpreter (`subprocess.run([sys.executable, "-c", ...])` with `PYTHONPATH` set to the test's `sys.path`, since other tests in the session import `pymol.Qt`), `import pymol3.gui` leaves `"pymol.Qt"` out of `sys.modules`; return code 0.
  - `test_without_qt_window_raises_qt_not_available`: with `pymol.gui.get_qtwindow` patched to return `None`, `add_dock_panel(object(), "T")` raises `pymol.plugins.QtNotAvailableError`.
- [ ] **Step 4: Run them to see them fail.** `bazel test //tests --test_output=errors` → FAIL, `module 'pymol3' has no attribute 'gui'` or `No module named 'pymol3.gui'`.
- [ ] **Step 5: Implement `modules/pymol3/gui.py`** with the signatures in `## Interfaces`. The area table maps the four lower-cased names to `Qt.DockWidgetArea` members; the registry is `window._pymol3_dock_panels`, created on first use; `DockPanel` keeps a `_removed` flag that `show()`/`hide()` check. Module docstring carries a short plugin example (`__init_plugin__` calling `add_dock_panel`).
- [ ] **Step 6: Run them to see them pass.** `bazel test //tests --test_output=errors` → PASS; `--test_output=all` shows the `tests/pymol3` tests as passed, none skipped.
- [ ] **Step 7: Commit.** `git add modules/pymol3/gui.py tests/pymol3 tests/BUILD.bazel tools/bazel/requirements.in tools/bazel/requirements_lock.txt MODULE.bazel.lock` → `feat: let plugins dock their own panels with pymol3.gui`

### Task 3: Menu entries and tabbing

**Files:**
- Modify: `modules/pymol3/gui.py`, `tests/pymol3/test_gui.py`, `tests/pymol3/conftest.py` (a second fixture)

**Interfaces:**
- Consumes: `add_dock_panel`, `DockPanel`, fixture `main_window` (Task 2).
- Produces: fixture `bare_main_window` (a `QMainWindow` without `menudict`, patched in the same way).

- [ ] **Step 1: Write the failing tests:**
  - `test_panel_has_checkable_entry_under_plugin_panels`: `main_window.menudict["Display"]` holds a submenu titled `"Plugin Panels"` with one checkable, checked action titled `"Sequences"`; triggering it hides the panel.
  - `test_close_button_hides_and_menu_unchecks`: `panel.dock_widget.close()` → `is_visible()` is `False`, the action is unchecked, `get_dock_panel` still returns the panel; `show()` checks it again.
  - `test_one_submenu_for_many_panels`: two panels → one `"Plugin Panels"` submenu with two actions.
  - `test_remove_takes_entry_away`: after `remove()` the submenu has no action titled `"Sequences"`.
  - `test_window_without_menudict_still_docks` (fixture `bare_main_window`): the panel docks and nothing raises.
  - `test_second_panel_in_same_area_is_tabbed`: `second.dock_widget in main_window.tabifiedDockWidgets(first.dock_widget)`.
  - `test_panel_in_other_area_is_not_tabbed`: `main_window.tabifiedDockWidgets(first.dock_widget) == []`.
  - `test_floating_panel_is_not_tabbed`.
- [ ] **Step 2: Run them to see them fail.** `bazel test //tests --test_output=errors --test_arg=-k --test_arg="menu or entry or tabbed or menudict"` → FAIL.
- [ ] **Step 3: Implement.** The entry is the dock widget's own `toggleViewAction()`, so its check state follows the dock widget; the submenu is found by title in `menudict["Display"]` or added after a separator; `remove()` removes the action from it. Tabbing as in `## Edge cases`, with `window.tabifyDockWidget()`.
- [ ] **Step 4: Run them to see them pass.** `bazel test //tests --test_output=errors` → PASS.
- [ ] **Step 5: Commit.** `git add modules/pymol3/gui.py tests/pymol3` → `feat: list plugin panels under Display and tab panels sharing an area`

### Task 4: The GUI-thread rule, the README and the check in the real app

**Files:**
- Modify: `modules/pymol3/gui.py`, `tests/pymol3/test_gui.py`, `README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Write the failing test.** `test_call_from_worker_thread_raises_runtime_error`: the widget is made in the test's thread; a `threading.Thread` calls `add_dock_panel(tmp_label, "T")` and stores the exception; after `join()`, it is a `RuntimeError` mentioning the GUI thread, and `get_dock_panel("T") is None`.
- [ ] **Step 2: Run it to see it fail.** `bazel test //tests --test_output=errors --test_arg=-k --test_arg=worker_thread` → FAIL.
- [ ] **Step 3: Implement.** `add_dock_panel()`, after finding the window, compares `QtCore.QThread.currentThread()` with `QtWidgets.QApplication.instance().thread()` and raises before touching any widget.
- [ ] **Step 4: Run all tests.** `bazel test //tests --test_output=errors` → PASS.
- [ ] **Step 5: Document.** README.md gets a section `## Plugin API: dock panels` after `## Install` (and a line in `## Contents of this document`): what `pymol3` is (additions only, never changes to PyMOL's API), a ten-line `__init_plugin__` example, the four areas, the errors.
- [ ] **Step 6: Check in the real app.** Build `bazel build //distribution/bundle`, start the app from it, and at `PyMOL>` run `/from pymol3 import gui; from pymol.Qt import QtWidgets; gui.add_dock_panel(QtWidgets.QLabel("hello"), "Test", area="left")`. Expected: a "Test" panel on the left, an entry **Display → Plugin Panels → Test** that hides and shows it. Then run the same line from a script with `run`. If either raises the thread `RuntimeError`, stop and bring it to the developer.
- [ ] **Step 7: Commit.** `git add modules/pymol3/gui.py tests/pymol3/test_gui.py README.md` → `feat: refuse dock panel calls off the GUI thread; document pymol3.gui`

## Verification

- `bazel test //tests --test_output=all`: passes; the `tests/pymol3` tests are listed as passed, none skipped.
- `bazel test //tools/bazel/tests:wheel_layout_test`: passes, `pymol3/__init__.py` is in the wheel.
- `bazel test //distribution/...` on Windows: passes, `edited_base_test` included (no upstream file changed).
- `bazel run //distribution:checks`: ruff, shellcheck and actionlint pass.
- `python3 .opp/style/check.py --committed`: no findings.
- `git diff origin/production --stat`: only paths in `## Scope`.
- Task 4 Step 6 in the running app: the panel docks on the left, its menu entry hides and shows it, and the call works from `PyMOL>` and from a `run` script.
