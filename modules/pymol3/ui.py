# SPDX-License-Identifier: BSD-3-Clause
"""Panels that plugins dock into PyMOL's main window.

A plugin hands over its own widget and names one of the window's four dock
areas; PyMOL wraps the widget in a dock widget and returns a ``DockPanel``
to show, hide or remove it later::

    from pymol.Qt import QtWidgets
    from pymol3 import ui

    def __init_plugin__(app=None):
      ui.add_dock_panel(
          QtWidgets.QLabel("Hello"), "My Plugin", area="left",
          panel_id="my_plugin")

Every function runs in PyMOL's Qt GUI only, from the GUI thread. Importing
this module loads no Qt binding, so it imports in headless PyMOL too.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from pymol.Qt import QtCore
  from pymol.Qt import QtWidgets

_AREA_NAMES = ("left", "right", "top", "bottom")
"""The dock areas by name, in the order error messages list them."""

_REGISTRY_ATTRIBUTE = "_pymol3_dock_panels"
"""The main window's attribute that maps panel ids to their panels."""

_MENU_TITLE = "Plugin Panels"
"""The submenu of PyMOL's Display menu that lists the panels."""


class DockPanel:
  """A plugin's panel, docked in PyMOL's main window.

  Only ``add_dock_panel`` makes one. Once removed, the panel cannot be
  shown or hidden again; its id is free for a new panel.
  """

  def __init__(
      self,
      panel_id: str,
      dock_widget: QtWidgets.QDockWidget,
      window: QtWidgets.QMainWindow,
  ) -> None:
    """Keeps the panel's id, dock widget and window.

    Args:
      panel_id: The id the panel is registered under.
      dock_widget: The dock widget that holds the plugin's widget.
      window: PyMOL's main window the panel is docked in.
    """
    self._panel_id = panel_id
    """The id the panel is registered under."""
    self._dock_widget = dock_widget
    """The dock widget that holds the plugin's widget."""
    self._window = window
    """PyMOL's main window the panel is docked in."""
    self._removed = False
    """Whether ``remove`` took the panel out of the window."""

  @property
  def panel_id(self) -> str:
    """The id the panel is registered under."""
    return self._panel_id

  @property
  def dock_widget(self) -> QtWidgets.QDockWidget:
    """The dock widget that holds the plugin's widget."""
    return self._dock_widget

  def show(self) -> None:
    """Shows the panel and raises it above panels it is tabbed with.

    Raises:
      RuntimeError: The panel was removed, or the call came from another
        thread than the GUI thread.
    """
    _check_gui_thread("show")
    self._check_not_removed()
    self._dock_widget.show()
    self._dock_widget.raise_()

  def hide(self) -> None:
    """Hides the panel; ``show`` brings it back.

    Raises:
      RuntimeError: The panel was removed, or the call came from another
        thread than the GUI thread.
    """
    _check_gui_thread("hide")
    self._check_not_removed()
    self._dock_widget.hide()

  def is_visible(self) -> bool:
    """Tells whether the panel is shown.

    A panel tabbed behind another one counts as shown.

    Returns:
      False once the panel is hidden or removed, True otherwise.
    """
    return not self._removed and not self._dock_widget.isHidden()

  def remove(self) -> None:
    """Takes the panel out of the window and frees its id.

    The dock widget and the plugin's widget in it are deleted. A second
    call does nothing.

    Raises:
      RuntimeError: The call came from another thread than the GUI thread.
    """
    _check_gui_thread("remove")
    if self._removed:
      return
    self._removed = True
    _registry(self._window).pop(self._panel_id, None)
    tmp_menu = _plugin_panels_menu(self._window, create=False)
    if tmp_menu is not None:
      tmp_menu.removeAction(self._dock_widget.toggleViewAction())
    self._window.removeDockWidget(self._dock_widget)
    self._dock_widget.deleteLater()

  def _check_not_removed(self) -> None:
    """Refuses to touch a removed panel's deleted dock widget.

    Raises:
      RuntimeError: The panel was removed.
    """
    if self._removed:
      raise RuntimeError(f"dock panel {self._panel_id!r} was removed")


def add_dock_panel(
    widget: QtWidgets.QWidget,
    title: str,
    area: str | QtCore.Qt.DockWidgetArea = "right",
    panel_id: str | None = None,
    floating: bool = False,
) -> DockPanel:
  """Docks a plugin's widget as a panel in PyMOL's main window.

  Args:
    widget: The plugin's widget; the panel takes ownership of it.
    title: The panel's title.
    area: ``"left"``, ``"right"``, ``"top"`` or ``"bottom"``, in any
      letter case, or the matching ``Qt.DockWidgetArea`` member.
    panel_id: The id to find the panel by; the title when left out.
    floating: Whether the panel starts floating instead of docked; it
      docks back into ``area``.

  Returns:
    The panel.

  Raises:
    pymol.plugins.QtNotAvailableError: PyMOL runs without its Qt window.
    ValueError: The area is none of the four, or the id is in use.
    RuntimeError: The call came from another thread than the GUI thread.
  """
  tmp_window = _qt_window()
  if tmp_window is None:
    raise _qt_not_available()
  tmp_qt = _import_qt()
  _check_gui_thread("add_dock_panel")
  tmp_area = _dock_area(tmp_qt, area)
  tmp_panel_id = title if panel_id is None else panel_id
  tmp_panels = _registry(tmp_window)
  if tmp_panel_id in tmp_panels:
    raise ValueError(f"a dock panel with id {tmp_panel_id!r} exists already")
  tmp_dock_widget = tmp_qt.QtWidgets.QDockWidget(title, tmp_window)
  tmp_dock_widget.setObjectName(f"pymol3_panel_{tmp_panel_id}")
  tmp_dock_widget.setWidget(widget)
  tmp_window.addDockWidget(tmp_area, tmp_dock_widget)
  if floating:
    tmp_dock_widget.setFloating(True)
  else:
    tmp_neighbour = _last_docked_panel(tmp_window, tmp_area)
    if tmp_neighbour is not None:
      tmp_window.tabifyDockWidget(tmp_neighbour.dock_widget, tmp_dock_widget)
  tmp_menu = _plugin_panels_menu(tmp_window, create=True)
  if tmp_menu is not None:
    tmp_menu.addAction(tmp_dock_widget.toggleViewAction())
  # Shown at once rather than at the window's next layout pass, so the menu
  # entry is checked and the panel counts as visible from the start.
  tmp_dock_widget.show()
  tmp_panel = DockPanel(tmp_panel_id, tmp_dock_widget, tmp_window)
  tmp_panels[tmp_panel_id] = tmp_panel
  return tmp_panel


def get_dock_panel(panel_id: str) -> DockPanel | None:
  """Finds a panel that ``add_dock_panel`` added and that is not removed.

  Args:
    panel_id: The panel's id.

  Returns:
    The panel, or None when no panel has the id or PyMOL has no Qt window.
  """
  tmp_window = _qt_window()
  if tmp_window is None:
    return None
  return _registry(tmp_window).get(panel_id)


def _check_gui_thread(caller: str) -> None:
  """Refuses calls that would touch Qt widgets from another thread.

  Args:
    caller: The function or method name the error message names.

  Raises:
    RuntimeError: The call came from another thread than the GUI thread.
  """
  tmp_qt = _import_qt()
  tmp_gui_thread = tmp_qt.QtWidgets.QApplication.instance().thread()
  if tmp_qt.QtCore.QThread.currentThread() != tmp_gui_thread:
    raise RuntimeError(f"{caller} must be called from PyMOL's GUI thread")


def _qt_window() -> QtWidgets.QMainWindow | None:
  """Asks PyMOL for its Qt main window.

  ``pymol.gui`` is taken from ``sys.modules``, never as an attribute of
  ``pymol``: scripts and Python typed at ``PyMOL>`` run in the ``pymol``
  module's namespace, where an import such as ``from x import gui`` can
  replace that attribute.

  Returns:
    The window, or None when PyMOL runs without its Qt GUI.
  """
  return importlib.import_module("pymol.gui").get_qtwindow()


def _registry(window: QtWidgets.QMainWindow) -> dict[str, DockPanel]:
  """Returns the window's map of panel ids to panels, made on first use.

  Args:
    window: PyMOL's main window.

  Returns:
    The map, kept on the window so that each window has its own.
  """
  tmp_panels = getattr(window, _REGISTRY_ATTRIBUTE, None)
  if tmp_panels is None:
    tmp_panels = {}
    setattr(window, _REGISTRY_ATTRIBUTE, tmp_panels)
  return tmp_panels


def _last_docked_panel(
    window: QtWidgets.QMainWindow,
    area: QtCore.Qt.DockWidgetArea,
) -> DockPanel | None:
  """Finds the panel a new panel in the area is tabbed with.

  Args:
    window: PyMOL's main window.
    area: The area the new panel docks in.

  Returns:
    The most recently added panel docked in the area, or None.
  """
  for tmp_panel in reversed(list(_registry(window).values())):
    tmp_dock_widget = tmp_panel.dock_widget
    if (
        not tmp_dock_widget.isFloating()
        and window.dockWidgetArea(tmp_dock_widget) == area
    ):
      return tmp_panel
  return None


def _plugin_panels_menu(
    window: QtWidgets.QMainWindow, create: bool
) -> QtWidgets.QMenu | None:
  """Finds the Plugin Panels submenu of PyMOL's Display menu.

  Args:
    window: PyMOL's main window, whose ``menudict`` holds its menus.
    create: Whether to add the submenu, after a separator, when missing.

  Returns:
    The submenu, or None when the window has no Display menu or the
    submenu is missing and not to be made.
  """
  tmp_menus = getattr(window, "menudict", None)
  if not isinstance(tmp_menus, dict) or "Display" not in tmp_menus:
    return None
  tmp_display = tmp_menus["Display"]
  # Found among the Display menu's child menus rather than through
  # QAction.menu(), which Qt 6 dropped and not every binding brings back.
  tmp_qt = _import_qt()
  for tmp_child in tmp_display.findChildren(tmp_qt.QtWidgets.QMenu):
    if tmp_child.parent() is tmp_display and tmp_child.title() == _MENU_TITLE:
      return tmp_child
  if not create:
    return None
  # The Display menu is the submenu's Qt parent and owner; a submenu that
  # addMenu(title) makes would be deleted with its Python wrapper.
  tmp_menu = tmp_qt.QtWidgets.QMenu(_MENU_TITLE, tmp_display)
  tmp_display.addSeparator()
  tmp_display.addMenu(tmp_menu)
  return tmp_menu


def _dock_area(qt, area) -> QtCore.Qt.DockWidgetArea:
  """Turns an area name or Qt member into one of the four dock areas.

  Args:
    qt: The ``pymol.Qt`` module.
    area: The area as the plugin passed it.

  Returns:
    The ``Qt.DockWidgetArea`` member.

  Raises:
    ValueError: The area is none of the four.
  """
  tmp_enum = qt.QtCore.Qt.DockWidgetArea
  tmp_areas = {
      "left": tmp_enum.LeftDockWidgetArea,
      "right": tmp_enum.RightDockWidgetArea,
      "top": tmp_enum.TopDockWidgetArea,
      "bottom": tmp_enum.BottomDockWidgetArea,
  }
  if isinstance(area, str):
    tmp_area = tmp_areas.get(area.lower())
  else:
    tmp_area = next(
        (tmp_member for tmp_member in tmp_areas.values() if tmp_member == area),
        None,
    )
  if tmp_area is None:
    tmp_names = ", ".join(repr(tmp_name) for tmp_name in _AREA_NAMES)
    raise ValueError(f"unknown dock area {area!r}; use one of {tmp_names}")
  return tmp_area


def _import_qt():
  """Imports the Qt binding PyMOL uses.

  Returns:
    The ``pymol.Qt`` module.

  Raises:
    pymol.plugins.QtNotAvailableError: No Qt binding is installed.
  """
  try:
    return importlib.import_module("pymol.Qt")
  except ImportError as exception:
    raise _qt_not_available() from exception


def _qt_not_available() -> Exception:
  """Makes the error PyMOL raises when its Qt GUI is missing.

  ``pymol.plugins`` is imported only here, since it loads the plugin
  system, which this module needs only to report the error.

  Returns:
    A ``pymol.plugins.QtNotAvailableError``.
  """
  tmp_plugins = importlib.import_module("pymol.plugins")
  return tmp_plugins.QtNotAvailableError(
      "dock panels need PyMOL's Qt window, which this PyMOL does not have"
  )
