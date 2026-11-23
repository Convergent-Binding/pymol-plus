# 0001. PyMOL API additions live in pymol3; dock panels in pymol3.ui

## Context

Plugin developers needed a supported way to dock their own panel into PyMOL's
Qt main window. PyMOL offered only `pymol.plugins.addmenuitemqt()`, so a plugin
had to reach into `QMainWindow` itself. The hard constraint: nothing in
PyMOL's existing API may change or disappear, so every plugin and script
written for PyMOL keeps working.

PyMOL's own packages (`pymol`, `pmg_qt`, `pymol2`) are upstream code. Editing
them diverges from Schrödinger's sources, and `pmg_qt/pymol_qt_gui.py` also has
a marked copy in `distribution/edited/` that must be kept in step. PyMOL runs
`run` scripts and Python typed at `PyMOL>` in the `pymol` module's own
namespace, so a module that shares a name with something PyMOL reads there
can replace it.

## Decision

This repository's additions to PyMOL's API go into a new top-level package,
`pymol3`, shipped in the wheel and through it in the app. It only adds and
changes or replaces nothing in `pymol`, `pmg_qt` or `pymol2`; it calls
`pymol.gui.get_qtwindow()` and reads the window's `menudict` attribute
without editing either.

The dock panel API is the module `pymol3.ui`: `add_dock_panel()` returns a
`DockPanel` handle, `get_dock_panel()` finds one by id, and each panel gets an
entry under Display > Plugin Panels.

## Consequences

Plugins get one public call per panel. Upstream PyMOL files stay untouched, so
syncing with Schrödinger and the edited-copy check are unaffected, and later
additions have a home that keeps them apart from upstream code.

Every addition must work through PyMOL's public surface. Where PyMOL offers
none, pymol3 reads attributes such as `menudict` and has to follow upstream
changes to them.

Rejected alternatives:

- A method on `PyMOLQtGUI`. It would edit upstream `pymol_qt_gui.py` and its
  marked copy, against keeping this repository's code apart.
- Panel classes with a registry and saved layouts. That meant about three
  times the code and a persistence format to specify. It can still be built
  on `pymol3.ui` later without breaking it.
- The module name `pymol3.gui`. A script's `from pymol3 import gui` replaced
  `pymol.gui` in PyMOL's namespace and broke PyMOL's own callers (the volume
  panel, legacy plugins). `ui` collides with nothing PyMOL reads there.
