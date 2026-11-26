# SPDX-License-Identifier: BSD-3-Clause
"""The switch between PyMOL+'s new GUI and PyMOL's classic GUI.

The PyMOL+ GUI features register here; the app's Qt GUI calls ``start``
before its main window is shown and ``ready`` once its plugins are loaded.
Both run the registered features only while the GUI style is ``new``; in
the classic style PyMOL starts exactly as it would without them. A
feature lives in a module listed in ``FEATURE_MODULES`` and registers when
``start`` imports it, in both styles, so the classic GUI too can offer the
switch to the new one::

    from pymol3 import app

    app.register(app.Feature(name="objects_panel", start=create_panel))

Importing a feature module must create no widget; that is ``start``'s and
``ready``'s work.

The style is fixed for a run at its first use. ``PYMOL_PLUS_GUI``, which
the app's ``--new-gui`` and ``--classic-gui`` set, wins over the choice
stored by Display → New GUI; without either, ``DEFAULT_STYLE`` applies.
Importing this module loads no Qt binding, so it imports in headless PyMOL
too.
"""

from __future__ import annotations

import dataclasses
import importlib
import os
import sys
import traceback
from collections.abc import Callable
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from pymol.Qt import QtCore
  from pymol.Qt import QtWidgets

NEW = "new"
"""The style that runs the registered PyMOL+ GUI features."""

CLASSIC = "classic"
"""The style that runs PyMOL's own GUI only."""

STYLES = (NEW, CLASSIC)
"""Every style name, in the order messages list them."""

DEFAULT_STYLE = CLASSIC
"""The style when neither the environment nor the store names one."""

ENVIRONMENT_VARIABLE = "PYMOL_PLUS_GUI"
"""The environment variable that names the style for one run.

The app's ``startup_wrapper.py`` sets it from ``--new-gui`` and
``--classic-gui`` under the same name, before this package can be imported.
"""

FEATURE_MODULES: tuple[str, ...] = ()
"""The modules of the PyMOL+ GUI features, imported by ``start``."""

SETTINGS_ORGANIZATION = "PyMOL-Open-Source"
"""The organization of the app's ``QSettings`` store."""

SETTINGS_APPLICATION = "PyMOL-Open-Source"
"""The application of the app's ``QSettings`` store."""

SETTINGS_KEY = "gui/style"
"""The key that holds the stored style."""

_MENU_TEXT = "New GUI"
"""The text of the Display menu's entry for the switch."""

_ACTION_NAME = "pymol3_app_new_gui"
"""The object name of that entry, which finds it again."""

Callback = Callable[["QtWidgets.QMainWindow"], None]
"""A feature's start or ready function; it receives PyMOL's main window."""

TickCallback = Callable[["QtWidgets.QMainWindow", Sequence[str]], None]
"""A feature's tick function; it receives the window and feedback lines."""


@dataclasses.dataclass(frozen=True)
class Feature:
  """A PyMOL+ GUI feature that runs only in the new style.

  Attributes:
    name: The feature's unique name, used in messages.
    start: Runs before the main window is shown, or None.
    ready: Runs once the plugins are loaded, or None.
    tick: Runs on PyMOL's feedback tick with feedback lines, or None.
  """

  name: str
  start: Callback | None = None
  ready: Callback | None = None
  tick: TickCallback | None = None


class _State:
  """What the module holds for the run."""

  def __init__(self) -> None:
    """Starts with no style decided and no feature registered."""
    self.style: str | None = None
    """The style of the run, once decided."""

    self.overridden = False
    """Whether the environment decided the style."""

    self.features: dict[str, Feature] = {}
    """The registered features by name, in registration order."""

    self.failed: set[str] = set()
    """The names of features that raised; they run no more."""

    self.message: QtWidgets.QMessageBox | None = None
    """The open restart message, kept from deletion while shown."""

    self.imported = False
    """Whether the feature modules were imported."""


_state = _State()
"""The module's state for the run."""


def _open_settings() -> QtCore.QSettings:
  """Opens the app's settings store.

  Returns:
    The store.

  Raises:
    ImportError: No Qt binding loads.
  """
  tmp_qt_core = importlib.import_module("pymol.Qt").QtCore
  return tmp_qt_core.QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)


def _valid_style(value: object, source: str) -> str | None:
  """Reads a style name, reporting one that is unknown.

  Args:
    value: The value found, or None when there is none.
    source: Where the value came from, for the report.

  Returns:
    The style, or None when the value is missing, empty or unknown.
  """
  if value is None or value == "":
    return None
  tmp_style = str(value).strip().lower()
  if tmp_style in STYLES:
    return tmp_style
  print(
      f" PyMOL+: ignoring the GUI style {value!r} from {source};"
      f" expected one of {', '.join(STYLES)}."
  )
  return None


def stored_style() -> str | None:
  """Reads the style stored by Display → New GUI.

  Returns:
    The stored style, or None when none is stored, the stored value is
    unknown or no Qt binding loads.
  """
  try:
    tmp_settings = _open_settings()
  except ImportError:
    return None
  return _valid_style(tmp_settings.value(SETTINGS_KEY), "the app's settings")


def store_style(style: str) -> None:
  """Stores the style for the next starts.

  Args:
    style: ``NEW`` or ``CLASSIC``.

  Raises:
    ValueError: The style is neither.
  """
  if style not in STYLES:
    raise ValueError(
        f"unknown GUI style {style!r}; expected one of {', '.join(STYLES)}"
    )
  tmp_settings = _open_settings()
  tmp_settings.setValue(SETTINGS_KEY, style)
  tmp_settings.sync()


def style() -> str:
  """Tells the style of this run.

  The first call decides it: ``PYMOL_PLUS_GUI`` if it names a style, else
  the stored choice, else ``DEFAULT_STYLE``. Later changes to either apply
  from the next start.

  Returns:
    ``NEW`` or ``CLASSIC``.
  """
  if _state.style is None:
    tmp_from_environment = _valid_style(
        os.environ.get(ENVIRONMENT_VARIABLE), ENVIRONMENT_VARIABLE
    )
    _state.overridden = tmp_from_environment is not None
    _state.style = tmp_from_environment or stored_style() or DEFAULT_STYLE
  return _state.style


def register(feature: Feature) -> None:
  """Registers a feature for the hooks to run in the new style.

  Args:
    feature: The feature; a feature that registers after ``start`` has run
      misses that phase.

  Raises:
    ValueError: A feature of the same name is registered already.
  """
  if feature.name in _state.features:
    raise ValueError(f"GUI feature {feature.name!r} is registered already")
  _state.features[feature.name] = feature


def start(window: QtWidgets.QMainWindow) -> None:
  """Imports the feature modules, then runs each start in the new style.

  The modules are imported in both styles, once, so their features are
  registered and ``ready`` can offer the switch in the classic GUI too.

  Args:
    window: PyMOL's main window, not shown yet.
  """
  _import_features()
  if style() == NEW:
    _run_all("start", window)


def _import_features() -> None:
  """Imports every module of ``FEATURE_MODULES`` once.

  A module that fails to import is reported and skipped; the others are
  still imported.
  """
  if _state.imported:
    return
  _state.imported = True
  for tmp_module_name in FEATURE_MODULES:
    try:
      importlib.import_module(tmp_module_name)
    # A broken feature module must leave PyMOL and the other features
    # starting, so every exception is caught and reported here.
    except Exception:
      traceback.print_exc(file=sys.stdout)
      print(
          f" PyMOL+: the GUI feature module {tmp_module_name!r} failed to"
          " import and is left out of this run."
      )


def ready(window: QtWidgets.QMainWindow) -> None:
  """Runs every feature's ready in the new style, then adds the menu entry.

  The Display menu's New GUI entry appears whenever a feature is
  registered, in both styles, so the classic GUI can switch to the new one.

  Args:
    window: PyMOL's main window, shown and with its plugins loaded.
  """
  _import_features()
  if style() == NEW:
    _run_all("ready", window)
  if _state.features:
    _add_menu_entry(window)


def tick(
    window: QtWidgets.QMainWindow,
    feedback: Sequence[str] = (),
) -> None:
  """Runs every feature's tick in the new style with one feedback batch.

  Args:
    window: PyMOL's main window.
    feedback: Feedback lines collected on this tick.
  """
  _import_features()
  if style() == NEW:
    _run_all("tick", window, (tuple(feedback),))


def _run_all(
    phase: str,
    window: QtWidgets.QMainWindow,
    extra: tuple[object, ...] = (),
) -> None:
  """Runs one phase of every feature that has not failed.

  A feature that raises is reported and runs no more in this run; the
  others still run.

  Args:
    phase: ``"start"``, ``"ready"`` or ``"tick"``.
    window: PyMOL's main window.
    extra: Extra positional arguments passed after ``window``.
  """
  for tmp_feature in list(_state.features.values()):
    tmp_callback = getattr(tmp_feature, phase)
    if tmp_callback is None or tmp_feature.name in _state.failed:
      continue
    try:
      tmp_callback(window, *extra)
    # Any error of one feature must leave PyMOL and the other features
    # starting, so every exception is caught and reported here.
    except Exception:
      _state.failed.add(tmp_feature.name)
      # PyMOL's output shows standard output; the app has no console for
      # standard error.
      traceback.print_exc(file=sys.stdout)
      print(
          f" PyMOL+: the GUI feature {tmp_feature.name!r} failed in"
          f" {phase} and is switched off for this run."
      )


def _add_menu_entry(window: QtWidgets.QMainWindow) -> None:
  """Adds the checkable New GUI entry to PyMOL's Display menu, once.

  Args:
    window: PyMOL's main window; without a Display menu in its
      ``menudict`` nothing is added.
  """
  tmp_menus = getattr(window, "menudict", None)
  if not isinstance(tmp_menus, dict) or "Display" not in tmp_menus:
    return
  tmp_display = tmp_menus["Display"]
  for tmp_action in tmp_display.actions():
    if tmp_action.objectName() == _ACTION_NAME:
      return
  tmp_action = tmp_display.addAction(_MENU_TEXT)
  tmp_action.setObjectName(_ACTION_NAME)
  tmp_action.setCheckable(True)
  tmp_action.setChecked(style() == NEW)
  tmp_action.toggled.connect(
      lambda checked: _choose(window, NEW if checked else CLASSIC)
  )


def _choose(window: QtWidgets.QMainWindow, chosen: str) -> None:
  """Stores the style chosen in the menu and says when it applies.

  Args:
    window: PyMOL's main window, the message's parent.
    chosen: The style chosen.
  """
  store_style(chosen)
  tmp_text = f"PyMOL starts with the {chosen} GUI after a restart."
  if _state.overridden:
    tmp_text += (
        f" This start was set by --new-gui, --classic-gui or"
        f" {ENVIRONMENT_VARIABLE}, which win over this choice."
    )
  tmp_widgets = importlib.import_module("pymol.Qt").QtWidgets
  if _state.message is not None:
    _state.message.close()
  tmp_message = tmp_widgets.QMessageBox(window)
  tmp_message.setIcon(tmp_widgets.QMessageBox.Icon.Information)
  tmp_message.setWindowTitle(_MENU_TEXT)
  tmp_message.setText(tmp_text)
  tmp_message.finished.connect(lambda result: _forget_message(tmp_message))
  _state.message = tmp_message
  tmp_message.open()


def _forget_message(message: QtWidgets.QMessageBox) -> None:
  """Lets a closed restart message be deleted.

  Args:
    message: The message that closed.
  """
  if _state.message is message:
    _state.message = None
  message.deleteLater()
