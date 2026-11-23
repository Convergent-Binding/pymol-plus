# SPDX-License-Identifier: BSD-3-Clause
"""Tests of pymol3.gui's dock panels in a Qt main window."""

import threading

import pytest

import pymol

from pymol3 import gui

# Skips this module without a Qt binding; the fixtures make the window.
qt = pytest.importorskip("pymol.Qt", exc_type=ImportError)
"""The Qt binding PyMOL found."""

_AREA = qt.QtCore.Qt.DockWidgetArea
"""Qt's dock area enumeration."""


@pytest.mark.parametrize(
    ("area", "expected"),
    [
        ("left", _AREA.LeftDockWidgetArea),
        ("Right", _AREA.RightDockWidgetArea),
        ("top", _AREA.TopDockWidgetArea),
        ("bottom", _AREA.BottomDockWidgetArea),
        (_AREA.BottomDockWidgetArea, _AREA.BottomDockWidgetArea),
    ],
)
def test_docks_widget_in_requested_area(main_window, area, expected):
  """The panel holds the widget, titled, in the area asked for.

  Args:
    main_window: The window PyMOL returns.
    area: The area as a plugin passes it.
    expected: The Qt area the panel must end up in.
  """
  tmp_label = qt.QtWidgets.QLabel("sequence")
  tmp_panel = gui.add_dock_panel(tmp_label, "Sequences", area=area)
  assert main_window.dockWidgetArea(tmp_panel.dock_widget) == expected
  assert tmp_panel.dock_widget.widget() is tmp_label
  assert tmp_panel.dock_widget.windowTitle() == "Sequences"


def test_area_defaults_to_right(main_window):
  """Without an area the panel docks on the right.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = gui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  assert (
      main_window.dockWidgetArea(tmp_panel.dock_widget)
      == _AREA.RightDockWidgetArea
  )


def test_panel_id_defaults_to_title(main_window):
  """Without a panel id the title is the id.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = gui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  assert tmp_panel.panel_id == "Sequences"
  assert gui.get_dock_panel("Sequences") is tmp_panel


def test_object_name_carries_panel_id(main_window):
  """The dock widget is named after the panel id.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = gui.add_dock_panel(
      qt.QtWidgets.QLabel(), "Sequences", panel_id="seq"
  )
  assert tmp_panel.dock_widget.objectName() == "pymol3_panel_seq"


def test_get_dock_panel_returns_none_for_unknown_id(main_window):
  """An id no panel has gives None.

  Args:
    main_window: The window PyMOL returns.
  """
  assert gui.get_dock_panel("nothing") is None


def test_hide_and_show(main_window):
  """hide() and show() switch the panel off and on.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = gui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  tmp_panel.hide()
  assert not tmp_panel.is_visible()
  assert tmp_panel.dock_widget.isHidden()
  tmp_panel.show()
  assert tmp_panel.is_visible()
  assert not tmp_panel.dock_widget.isHidden()


def test_floating_panel_floats(main_window):
  """floating=True floats the panel.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = gui.add_dock_panel(
      qt.QtWidgets.QLabel(), "Sequences", floating=True
  )
  assert tmp_panel.dock_widget.isFloating()


def test_remove_frees_id(main_window):
  """After remove() the id is free for a new panel.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = gui.add_dock_panel(
      qt.QtWidgets.QLabel(), "Sequences", panel_id="seq"
  )
  tmp_panel.remove()
  assert gui.get_dock_panel("seq") is None
  tmp_again = gui.add_dock_panel(
      qt.QtWidgets.QLabel(), "Again", panel_id="seq"
  )
  assert gui.get_dock_panel("seq") is tmp_again


def test_remove_twice_is_harmless(main_window):
  """A second remove() does nothing.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = gui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  tmp_panel.remove()
  tmp_panel.remove()


def test_show_after_remove_raises(main_window):
  """show() on a removed panel raises instead of touching Qt.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = gui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  tmp_panel.remove()
  with pytest.raises(RuntimeError, match="removed"):
    tmp_panel.show()


def test_duplicate_panel_id_raises_value_error(main_window):
  """A second panel with a used id raises; the first stays.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_first = gui.add_dock_panel(
      qt.QtWidgets.QLabel(), "Sequences", panel_id="seq"
  )
  with pytest.raises(ValueError, match="seq"):
    gui.add_dock_panel(qt.QtWidgets.QLabel(), "Other", panel_id="seq")
  assert gui.get_dock_panel("seq") is tmp_first


@pytest.mark.parametrize("area", ["middle", _AREA.AllDockWidgetAreas])
def test_unknown_area_raises_value_error(main_window, area):
  """An area other than the four raises and adds no panel.

  Args:
    main_window: The window PyMOL returns.
    area: The area a plugin passes.
  """
  with pytest.raises(ValueError) as tmp_raised:
    gui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences", area=area)
  for tmp_name in ("left", "right", "top", "bottom"):
    assert tmp_name in str(tmp_raised.value)
  assert gui.get_dock_panel("Sequences") is None


def _plugin_panels_actions(window) -> list:
  """Lists the entries of Display's Plugin Panels submenu.

  Args:
    window: The window PyMOL returns.

  Returns:
    One list per Plugin Panels submenu, each with its actions.
  """
  return [
      tmp_action.menu().actions()
      for tmp_action in window.menudict["Display"].actions()
      if tmp_action.menu() is not None
      and tmp_action.text() == "Plugin Panels"
  ]


def test_panel_has_checkable_entry_under_plugin_panels(main_window):
  """Display > Plugin Panels gets a checked entry that hides the panel.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = gui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  [tmp_actions] = _plugin_panels_actions(main_window)
  [tmp_entry] = tmp_actions
  assert tmp_entry.text() == "Sequences"
  assert tmp_entry.isCheckable()
  assert tmp_entry.isChecked()
  tmp_entry.trigger()
  assert not tmp_panel.is_visible()


def test_close_button_hides_and_menu_unchecks(main_window):
  """Closing the dock hides the panel, unchecks it and keeps it.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = gui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  [[tmp_entry]] = _plugin_panels_actions(main_window)
  tmp_panel.dock_widget.close()
  assert not tmp_panel.is_visible()
  assert not tmp_entry.isChecked()
  assert gui.get_dock_panel("Sequences") is tmp_panel
  tmp_panel.show()
  assert tmp_entry.isChecked()


def test_one_submenu_for_many_panels(main_window):
  """Two panels share one Plugin Panels submenu.

  Args:
    main_window: The window PyMOL returns.
  """
  gui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  gui.add_dock_panel(qt.QtWidgets.QLabel(), "Contacts", area="left")
  [tmp_actions] = _plugin_panels_actions(main_window)
  assert [tmp_action.text() for tmp_action in tmp_actions] == [
      "Sequences",
      "Contacts",
  ]


def test_remove_takes_entry_away(main_window):
  """remove() takes the panel's entry out of the submenu.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = gui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  tmp_panel.remove()
  [tmp_actions] = _plugin_panels_actions(main_window)
  assert "Sequences" not in [tmp_action.text() for tmp_action in tmp_actions]


def test_window_without_menudict_still_docks(bare_main_window):
  """A window without PyMOL's menus still gets the panel.

  Args:
    bare_main_window: The window PyMOL returns, without menudict.
  """
  tmp_panel = gui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  assert (
      bare_main_window.dockWidgetArea(tmp_panel.dock_widget)
      == _AREA.RightDockWidgetArea
  )


def test_second_panel_in_same_area_is_tabbed(main_window):
  """A second panel in the same area joins the first as a tab.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_first = gui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  tmp_second = gui.add_dock_panel(qt.QtWidgets.QLabel(), "Contacts")
  assert tmp_second.dock_widget in main_window.tabifiedDockWidgets(
      tmp_first.dock_widget
  )


def test_panel_in_other_area_is_not_tabbed(main_window):
  """Panels in different areas stay apart.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_first = gui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  gui.add_dock_panel(qt.QtWidgets.QLabel(), "Contacts", area="left")
  assert main_window.tabifiedDockWidgets(tmp_first.dock_widget) == []


def test_floating_panel_is_not_tabbed(main_window):
  """A floating panel is not tabbed with a docked one.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_first = gui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  tmp_second = gui.add_dock_panel(
      qt.QtWidgets.QLabel(), "Contacts", floating=True
  )
  assert tmp_second.dock_widget.isFloating()
  assert main_window.tabifiedDockWidgets(tmp_first.dock_widget) == []


def test_call_from_worker_thread_raises_runtime_error(main_window):
  """A call from another thread than the GUI thread raises, adding nothing.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_label = qt.QtWidgets.QLabel()
  tmp_raised = []

  def tmp_call() -> None:
    """Adds a panel from the worker thread and keeps what it raises."""
    try:
      gui.add_dock_panel(tmp_label, "T")
    except RuntimeError as exception:
      tmp_raised.append(exception)

  tmp_thread = threading.Thread(target=tmp_call)
  tmp_thread.start()
  tmp_thread.join()
  [tmp_exception] = tmp_raised
  assert "GUI thread" in str(tmp_exception)
  assert gui.get_dock_panel("T") is None


def test_works_when_pymol_gui_name_is_replaced(main_window, monkeypatch):
  """A script's ``from pymol3 import gui`` in PyMOL's namespace breaks nothing.

  PyMOL runs scripts and typed Python in the ``pymol`` module's namespace,
  where that import replaces the attribute ``pymol.gui``.

  Args:
    main_window: The window PyMOL returns.
    monkeypatch: Replaces ``pymol.gui`` with ``pymol3.gui``.
  """
  monkeypatch.setattr(pymol, "gui", gui)
  tmp_panel = gui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  assert gui.get_dock_panel("Sequences") is tmp_panel
