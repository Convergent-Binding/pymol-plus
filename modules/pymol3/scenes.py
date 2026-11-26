# SPDX-License-Identifier: BSD-3-Clause
"""PyMOL+ docked Scenes panel feature.

Importing this module registers the feature with ``pymol3.app`` without
importing any Qt binding, so headless PyMOL and CLI tools remain unaffected.
"""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from typing import TYPE_CHECKING

from pymol3 import app


if TYPE_CHECKING:
  from pymol.Qt import QtWidgets


FEATURE_NAME = "scenes_panel"
"""Unique feature name registered with ``pymol3.app``."""

PANEL_ID = "scenes"
"""Dock panel identifier used with ``pymol3.ui``."""

PANEL_TITLE = "Scenes"
"""Dock panel title shown in the UI."""

RESERVED_SCENE_NAMES = frozenset({"*", "new", "auto"})
"""Scene keys handled specially by PyMOL's ``scene`` command."""

MAX_THUMBNAIL_RETRIES = 5
"""Maximum idle ticks to retry an empty or unrendered scene thumbnail."""

_CONTROLLER_ATTRIBUTE = "_pymol3_scenes_controller"
"""Main window attribute storing the active scenes controller."""


def validate_scene_name(
    old_name: str,
    proposed_name: str,
    existing_names: Sequence[str],
) -> tuple[str | None, str | None]:
  """Validates a scene rename target against PyMOL's scene constraints.

  Leading and trailing whitespace is stripped while internal spaces are kept.
  An unchanged name returns ``(None, None)`` so callers can cancel silently.

  Args:
    old_name: Current name of the scene being renamed.
    proposed_name: Raw text entered by the user.
    existing_names: All scene names currently defined in PyMOL.

  Returns:
    ``(cleaned_name, None)`` when valid, ``(None, None)`` when unchanged, or
    ``(None, reason)`` when refused.
  """
  tmp_cleaned = proposed_name.strip()
  if tmp_cleaned == old_name:
    return None, None
  if not tmp_cleaned:
    return None, "Scene name cannot be empty."
  if "\n" in tmp_cleaned or "\r" in tmp_cleaned:
    return None, "Scene name cannot contain line breaks."
  if tmp_cleaned in RESERVED_SCENE_NAMES:
    return None, f"{tmp_cleaned!r} is a reserved PyMOL scene key."
  if tmp_cleaned in existing_names:
    return None, f"A scene named {tmp_cleaned!r} already exists."
  return tmp_cleaned, None


def _controller(window: QtWidgets.QMainWindow):
  """Returns the scenes controller attached to ``window``, if any.

  Args:
    window: PyMOL's main window.

  Returns:
    The controller instance, or None when not installed.
  """
  return getattr(window, _CONTROLLER_ATTRIBUTE, None)


def start(window: QtWidgets.QMainWindow) -> None:
  """Creates and docks the Scenes panel hidden before the window is shown.

  Args:
    window: PyMOL's main window.
  """
  tmp_panel_module = importlib.import_module("pymol3._scenes_panel")
  tmp_controller = tmp_panel_module.install(window)
  setattr(window, _CONTROLLER_ATTRIBUTE, tmp_controller)


def ready(window: QtWidgets.QMainWindow) -> None:
  """Performs initial scene synchronization once plugins have loaded.

  Args:
    window: PyMOL's main window.
  """
  tmp_controller = _controller(window)
  if tmp_controller is not None:
    tmp_controller.sync(auto_open=True)


def tick(
    window: QtWidgets.QMainWindow,
    _feedback: Sequence[str] = (),
) -> None:
  """Polls for scene changes on PyMOL's feedback tick.

  Args:
    window: PyMOL's main window.
    _feedback: Feedback batch from PyMOL (unused).
  """
  tmp_controller = _controller(window)
  if tmp_controller is not None:
    tmp_controller.on_tick()


def open_panel(window: QtWidgets.QMainWindow | None = None) -> bool:
  """Opens and raises the docked Scenes panel when the new GUI is active.

  Args:
    window: PyMOL's main window, or None to look it up via ``pymol.gui``.

  Returns:
    True when the docked panel was shown in the new GUI, or False so the
    caller can fall back to PyMOL's classic Scenes window.
  """
  if app.style() != app.NEW:
    return False
  tmp_window = window
  if tmp_window is None:
    tmp_window = importlib.import_module("pymol.gui").get_qtwindow()
  if tmp_window is None:
    return False
  tmp_controller = _controller(tmp_window)
  if tmp_controller is None:
    return False
  tmp_controller.open_panel()
  return True


FEATURE = app.Feature(
    name=FEATURE_NAME,
    start=start,
    ready=ready,
    tick=tick,
)
"""Feature definition registered with ``pymol3.app``."""

app.register(FEATURE)
