# One switch between the new PyMOL+ GUI and the classic GUI

**Goal:** One switch, read at start-up, decides whether the app runs the new PyMOL+ GUI or the classic one; the classic GUI is the default for now, and once the default flips, the same switch brings the classic GUI back.

**Architecture:** A new module `pymol3.app` holds the switch and the registry of PyMOL+ GUI features. Two marked segments in the app's edited `pymol_qt_gui.py` call `pymol3.app.start(window)` before `window.show()` and `pymol3.app.ready(window)` after the plugins load; with the classic style neither runs a feature, so PyMOL starts exactly as today. The app's `startup_wrapper.py` turns `--new-gui` and `--classic-gui` into an environment variable before PyMOL reads the arguments, so `modules/pymol/` stays untouched (ADR 0001).

**Tech Stack:** Python 3.13, PySide6 6.9 through `pymol.Qt`, `QSettings`, pytest under Bazel.

**Spec:** The design agreed in the session of 2026-11-25 (approach A: the switch decides at start-up), recorded under Design below.

## Design

- **Intent.** The PyMOL+ GUI features (objects panel, command palette, scenes panel, project library, MCP server; `.opp/plans/features/`) replace parts of PyMOL's interface. People must be able to try them while the classic GUI stays the default, and later get the classic GUI back once the new one is the default. One switch for all of them, so "the old GUI" always means the same thing.
- **Approaches considered.**
  - A. The switch decides at start-up: the hooks run registered features only in the new style; a change takes effect after a restart. Simple, nothing flashes at start, each feature only asks whether it is on. **Chosen** by the developer.
  - B. A live switch: every feature always builds, and the checkbox shows and hides them and brings the internal and External GUI back without a restart. Nicer, but every feature must tear itself down and rebuild cleanly, roughly doubling each feature's edge cases. Rejected.
  - C. A command-line option only. Least code, but the switch cannot be found in the app and cannot become the way back to the old GUI. Rejected.
  - A PyMOL setting (`set new_gui, 1`) was ruled out: it needs a C++ addition, and PyMOL saves settings in `.pse` sessions, so opening someone's session would change the user's GUI.
- **Decided by the developer.** One switch replaces the per-feature switches planned so far (Display → Internal GUI remembered by the objects panel, External GUI "Show at start" of the command palette). The switch decides at start-up.
- **Claude's calls, approved with the design.**
  - The choice is stored as a style, `gui/style` = `new` or `classic`, in the app's existing `QSettings('PyMOL-Open-Source', 'PyMOL-Open-Source')`; a missing key means the built-in default, `classic` for now. Flipping the default later is one constant, and an explicit choice survives it.
  - `--new-gui` or `--classic-gui` on the command line wins over the stored choice for that run, through the environment variable `PYMOL_PLUS_GUI`, which the user may also set.
  - `ready()` adds a checkable **Display → New GUI** action that saves the choice and says it takes effect after a restart. It appears only once at least one feature is registered, so no release ships a switch that does nothing.
  - The five feature plans drop their own switches and use this one.

## Global Constraints

- "`distribution/edited/` holds upstream PyMOL files with marked edits (`BEGIN EDITED CODE SEGMENT`)" (AGENTS.md): the two hooks are new marked segments; the upstream original and `upstream.sha256` do not change.
- ADR 0001: PyMOL API additions live in `pymol3`; `modules/pymol/` stays untouched.
- App decisions (AGENTS.md): PySide6 stays at 6.9; Python 3.13.
- Python follows `opp-workflow:python-style`; `python3 .opp/style/check.py` passes on every changed line.

## Review Focus

- **Classic start unchanged.** With the classic style, no feature's `start` or `ready` runs and no menu entry appears. Covered by `test_classic_style_runs_no_feature` and `test_menu_hidden_without_features`.
- **Precedence.** Command line over stored choice over default, and a bad value in the environment or the store falls back instead of failing the start. Covered by the `test_style_*` tests and the wrapper tests.
- **A failing feature.** An exception in one feature's `start` or `ready` must not stop PyMOL from starting or the other features from running. Covered by `test_failing_feature_does_not_stop_others`.
- **Unknown arguments.** PyMOL must never see `--new-gui` or `--classic-gui`. Covered by `startup_wrapper_test`.

## Scope

.opp/plans/new-gui-switch.md
.opp/plans/features/command-palette.md
.opp/plans/features/objects-panel.md
.opp/plans/features/scenes-panel.md
.opp/plans/features/project-library.md
.opp/plans/features/mcp-server.md
modules/pymol3/app.py
tests/pymol3_app/**
distribution/edited/pmg_qt/pymol_qt_gui.py
distribution/edited/pymol/startup_wrapper.py
distribution/edited/BUILD.bazel
distribution/edited/startup_wrapper_test.py

## Done

The app starts in the classic GUI by default, `--new-gui`, `PYMOL_PLUS_GUI` or the stored `gui/style` switch the registered PyMOL+ features on at start-up, and the five feature plans use this switch.

## Non-goals

- Any PyMOL+ GUI feature itself; with none registered the switch has no visible effect.
- Switching live without a restart (approach B).
- The `pymol3.app.tick` hook in `update_feedback()`; the first feature that needs it adds it, as its plan says.
- Flipping the default to the new GUI, and renaming the menu entry to "Classic GUI"; both come with that later decision.
- User documentation on the website; it follows with the first feature that makes the switch visible.

## Interfaces

- `pymol3.app.NEW`, `pymol3.app.CLASSIC`: the two style names, `"new"` and `"classic"`.
- `pymol3.app.DEFAULT_STYLE`: `CLASSIC`.
- `pymol3.app.ENVIRONMENT_VARIABLE`: `"PYMOL_PLUS_GUI"`.
- `pymol3.app.style() -> str`: the style in effect for this run: the environment variable if valid, else the stored choice if valid, else the default. Fixed at the first call of the run.
- `pymol3.app.stored_style() -> str | None` and `pymol3.app.store_style(style: str) -> None`: the stored choice.
- `pymol3.app.register(feature: Feature) -> None`: a feature registers once; a `Feature` has a `name` and optional `start(window)` and `ready(window)`.
- `pymol3.app.start(window)` and `pymol3.app.ready(window)`: called by the app's hooks; they run the registered features in the new style only, and `ready` adds the menu entry when any feature is registered.
- Command line of the app: `--new-gui`, `--classic-gui` (the last one wins); removed from `sys.argv` before `pymol.launch`.

## Edge cases

- `PYMOL_PLUS_GUI` or the stored value is neither `new` nor `classic`: ignored, with one line on PyMOL's output naming the value.
- A feature raises in `start` or `ready`: the traceback is printed, the feature is skipped for the rest of the run, the others still run.
- A feature registers twice under the same name: `ValueError`.
- The window has no `menudict` or no Display menu (a host without PyMOL's menus): no menu entry, no error, as `pymol3.ui` does.
- The checkbox is changed while a command-line override is in effect: the stored choice changes, the message says it applies from the next start without the option.

## Acceptance criteria

- With no option, no environment variable and no stored choice, `pymol3.app.style()` is `classic`, and the app starts exactly as before.
- `--new-gui` runs the registered features' `start` before the window is shown and `ready` after the plugins are loaded; `--classic-gui` runs neither, whatever is stored.
- With at least one registered feature, Display → New GUI is checked in the new style, unchecked in the classic style, and toggling it stores the choice and tells the user it applies after a restart.
- With no registered feature, the Display menu has no New GUI entry.
- PyMOL never receives `--new-gui` or `--classic-gui` among its arguments.
- The five feature plans name this switch instead of their own, and no longer plan a remembered Internal GUI choice or a "Show at start" setting.
- `//distribution/edited:edited_base_test` passes without a change to `upstream.sha256`.

## Tasks

1. **Plan** — this file, committed alone.
2. **`pymol3.app`** — `modules/pymol3/app.py` and `tests/pymol3_app/` (style precedence, stored choice, registry, failing feature, menu entry, classic runs nothing), test-first; the tests run in `//tests` with the existing offscreen Qt fixtures' pattern.
3. **Hooks and command line** — two marked segments in `distribution/edited/pmg_qt/pymol_qt_gui.py` (`start` before `window.show()`, `ready` after the plugin block); `startup_wrapper.py` turns the options into `PYMOL_PLUS_GUI`; `distribution/edited/startup_wrapper_test.py` and its `py_test`.
4. **Feature plans** — the five plans' shared-hooks bullet and the objects panel's and command palette's switch decisions rewritten to use this switch.

## Verification

- `bazel test //tests` passes, the new `tests/pymol3_app` tests among them.
- `bazel test //distribution/edited:all` passes: `edited_base_test` and `startup_wrapper_test`.
- `bazel test //distribution/...` passes on Windows, the bundle's headless smoke test included.
- `python3 .opp/style/check.py` reports no finding on the changed lines.
- By hand on Windows: the built app starts in the classic GUI; with `--new-gui` it starts the same (no feature registered yet) and the Display menu has no New GUI entry.
