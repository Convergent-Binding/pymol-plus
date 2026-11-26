# SPDX-License-Identifier: BSD-3-Clause
"""Tests of pymol3.ui's dock panels in a Qt main window."""

import threading

import pytest

import pymol

from pymol3 import ui

from . import qt_binding

# Skips this module without a Qt binding, unless the setup requires one;
# the fixtures make the window.
qt = qt_binding.import_qt()
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
  tmp_panel = ui.add_dock_panel(tmp_label, "Sequences", area=area)
  assert main_window.dockWidgetArea(tmp_panel.dock_widget) == expected
  assert tmp_panel.dock_widget.widget() is tmp_label
  assert tmp_panel.dock_widget.windowTitle() == "Sequences"


def test_area_defaults_to_right(main_window):
  """Without an area the panel docks on the right.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  assert (
      main_window.dockWidgetArea(tmp_panel.dock_widget)
      == _AREA.RightDockWidgetArea
  )


def test_panel_id_defaults_to_title(main_window):
  """Without a panel id the title is the id.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  assert tmp_panel.panel_id == "Sequences"
  assert ui.get_dock_panel("Sequences") is tmp_panel


def test_object_name_carries_panel_id(main_window):
  """The dock widget is named after the panel id.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = ui.add_dock_panel(
      qt.QtWidgets.QLabel(), "Sequences", panel_id="seq"
  )
  assert tmp_panel.dock_widget.objectName() == "pymol3_panel_seq"


def test_get_dock_panel_returns_none_for_unknown_id(main_window):
  """An id no panel has gives None.

  Args:
    main_window: The window PyMOL returns.
  """
  assert ui.get_dock_panel("nothing") is None


def test_hide_and_show(main_window):
  """hide() and show() switch the panel off and on.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
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
  tmp_panel = ui.add_dock_panel(
      qt.QtWidgets.QLabel(), "Sequences", floating=True
  )
  assert tmp_panel.dock_widget.isFloating()


def test_remove_frees_id(main_window):
  """After remove() the id is free for a new panel.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = ui.add_dock_panel(
      qt.QtWidgets.QLabel(), "Sequences", panel_id="seq"
  )
  tmp_panel.remove()
  assert ui.get_dock_panel("seq") is None
  tmp_again = ui.add_dock_panel(
      qt.QtWidgets.QLabel(), "Again", panel_id="seq"
  )
  assert ui.get_dock_panel("seq") is tmp_again


def test_remove_twice_is_harmless(main_window):
  """A second remove() does nothing.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  tmp_panel.remove()
  tmp_panel.remove()


def test_show_after_remove_raises(main_window):
  """show() on a removed panel raises instead of touching Qt.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  tmp_panel.remove()
  with pytest.raises(RuntimeError, match="removed"):
    tmp_panel.show()


def test_duplicate_panel_id_raises_value_error(main_window):
  """A second panel with a used id raises; the first stays.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_first = ui.add_dock_panel(
      qt.QtWidgets.QLabel(), "Sequences", panel_id="seq"
  )
  with pytest.raises(ValueError, match="seq"):
    ui.add_dock_panel(qt.QtWidgets.QLabel(), "Other", panel_id="seq")
  assert ui.get_dock_panel("seq") is tmp_first


@pytest.mark.parametrize("area", ["middle", _AREA.AllDockWidgetAreas])
def test_unknown_area_raises_value_error(main_window, area):
  """An area other than the four raises and adds no panel.

  Args:
    main_window: The window PyMOL returns.
    area: The area a plugin passes.
  """
  with pytest.raises(ValueError) as tmp_raised:
    ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences", area=area)
  for tmp_name in ("left", "right", "top", "bottom"):
    assert tmp_name in str(tmp_raised.value)
  assert ui.get_dock_panel("Sequences") is None


def _plugin_panels_actions(window) -> list:
  """Lists the entries of Display's Plugin Panels submenu.

  Args:
    window: The window PyMOL returns.

  Returns:
    One list per Plugin Panels submenu, each with its actions.
  """
  tmp_display = window.menudict["Display"]
  return [
      tmp_menu.actions()
      for tmp_menu in tmp_display.findChildren(qt.QtWidgets.QMenu)
      if tmp_menu.parent() is tmp_display
      and tmp_menu.title() == "Plugin Panels"
  ]


def test_panel_has_checkable_entry_under_plugin_panels(main_window):
  """Display > Plugin Panels gets a checked entry that hides the panel.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
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
  tmp_panel = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  [[tmp_entry]] = _plugin_panels_actions(main_window)
  tmp_panel.dock_widget.close()
  assert not tmp_panel.is_visible()
  assert not tmp_entry.isChecked()
  assert ui.get_dock_panel("Sequences") is tmp_panel
  tmp_panel.show()
  assert tmp_entry.isChecked()


def test_one_submenu_for_many_panels(main_window):
  """Two panels share one Plugin Panels submenu.

  Args:
    main_window: The window PyMOL returns.
  """
  ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  ui.add_dock_panel(qt.QtWidgets.QLabel(), "Contacts", area="left")
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
  tmp_panel = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  tmp_panel.remove()
  [tmp_actions] = _plugin_panels_actions(main_window)
  assert "Sequences" not in [tmp_action.text() for tmp_action in tmp_actions]


def test_window_without_menudict_still_docks(bare_main_window):
  """A window without PyMOL's menus still gets the panel.

  Args:
    bare_main_window: The window PyMOL returns, without menudict.
  """
  tmp_panel = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  assert (
      bare_main_window.dockWidgetArea(tmp_panel.dock_widget)
      == _AREA.RightDockWidgetArea
  )


def test_second_panel_in_same_area_is_tabbed(main_window):
  """A second panel in the same area joins the first as a tab.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_first = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  tmp_second = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Contacts")
  assert tmp_second.dock_widget in main_window.tabifiedDockWidgets(
      tmp_first.dock_widget
  )


def test_panel_in_other_area_is_not_tabbed(main_window):
  """Panels in different areas stay apart.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_first = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  ui.add_dock_panel(qt.QtWidgets.QLabel(), "Contacts", area="left")
  assert main_window.tabifiedDockWidgets(tmp_first.dock_widget) == []


def test_floating_panel_is_not_tabbed(main_window):
  """A floating panel is not tabbed with a docked one.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_first = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  tmp_second = ui.add_dock_panel(
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
      ui.add_dock_panel(tmp_label, "T")
    except RuntimeError as exception:
      tmp_raised.append(exception)

  tmp_thread = threading.Thread(target=tmp_call)
  tmp_thread.start()
  tmp_thread.join()
  [tmp_exception] = tmp_raised
  assert "GUI thread" in str(tmp_exception)
  assert ui.get_dock_panel("T") is None


def test_works_when_pymol_gui_name_is_replaced(main_window, monkeypatch):
  """Panels still dock when a script has replaced the name ``pymol.gui``.

  PyMOL runs scripts and typed Python in the ``pymol`` module's namespace,
  where an import such as ``from x import gui`` replaces that attribute.

  Args:
    main_window: The window PyMOL returns.
    monkeypatch: Replaces ``pymol.gui`` with another module.
  """
  monkeypatch.setattr(pymol, "gui", ui)
  tmp_panel = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  assert ui.get_dock_panel("Sequences") is tmp_panel


@pytest.mark.parametrize("method", ["show", "hide", "remove"])
def test_panel_methods_from_worker_thread_raise_runtime_error(
    main_window, method
):
  """show(), hide() and remove() from another thread raise, changing nothing.

  Args:
    main_window: The window PyMOL returns.
    method: The panel method a worker thread calls.
  """
  tmp_panel = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  tmp_raised = []

  def tmp_call() -> None:
    """Calls the panel method from the worker thread, keeping its error."""
    try:
      getattr(tmp_panel, method)()
    except RuntimeError as exception:
      tmp_raised.append(exception)

  tmp_thread = threading.Thread(target=tmp_call)
  tmp_thread.start()
  tmp_thread.join()
  [tmp_exception] = tmp_raised
  assert "GUI thread" in str(tmp_exception)
  assert tmp_panel.is_visible()
  assert ui.get_dock_panel("Sequences") is tmp_panel


def _tab_titles_and_current(window) -> list:
  """Lists the tab bars of the window's docked tabs.

  Args:
    window: The window PyMOL returns.

  Returns:
    One pair per tab bar: its tab titles and the current tab's title.
  """
  qt.QtWidgets.QApplication.processEvents()
  return [
      (
          [tmp_bar.tabText(tmp_index) for tmp_index in range(tmp_bar.count())],
          tmp_bar.tabText(tmp_bar.currentIndex()),
      )
      for tmp_bar in window.findChildren(qt.QtWidgets.QTabBar)
      if tmp_bar.count() > 0
  ]


def test_show_raises_panel_tabbed_behind(main_window):
  """show() brings a panel tabbed behind another to the front.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_first = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  tmp_second = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Contacts")
  tmp_second.show()
  assert ([["Sequences", "Contacts"], "Contacts"]
          in [list(tmp_pair) for tmp_pair in _tab_titles_and_current(
              main_window)])
  tmp_first.show()
  assert ([["Sequences", "Contacts"], "Sequences"]
          in [list(tmp_pair) for tmp_pair in _tab_titles_and_current(
              main_window)])


def test_panel_tabbed_behind_counts_as_visible(main_window):
  """A panel behind another tab still counts as shown.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_first = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Sequences")
  tmp_second = ui.add_dock_panel(qt.QtWidgets.QLabel(), "Contacts")
  tmp_second.show()
  assert ([["Sequences", "Contacts"], "Contacts"]
          in [list(tmp_pair) for tmp_pair in _tab_titles_and_current(
              main_window)])
  assert tmp_first.is_visible()


def test_floating_panel_docks_back_into_its_area(main_window):
  """A panel that starts floating docks back into the area asked for.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = ui.add_dock_panel(
      qt.QtWidgets.QLabel(), "Sequences", area="bottom", floating=True
  )
  assert tmp_panel.dock_widget.isFloating()
  tmp_panel.dock_widget.setFloating(False)
  qt.QtWidgets.QApplication.processEvents()
  assert not tmp_panel.dock_widget.isFloating()
  assert not tmp_panel.dock_widget.isWindow()
  assert (
      main_window.dockWidgetArea(tmp_panel.dock_widget)
      == _AREA.BottomDockWidgetArea
  )


def test_remove_deletes_the_plugin_widget(main_window):
  """remove() deletes the dock widget and the plugin's widget with it.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_label = qt.QtWidgets.QLabel()
  tmp_destroyed = []
  tmp_label.destroyed.connect(lambda *_: tmp_destroyed.append(True))
  tmp_panel = ui.add_dock_panel(tmp_label, "Sequences")
  tmp_panel.remove()
  qt.QtCore.QCoreApplication.sendPostedEvents(
      None, qt.QtCore.QEvent.Type.DeferredDelete
  )
  assert tmp_destroyed == [True]


def test_widget_that_is_no_widget_leaves_no_dock(main_window):
  """A non-widget raises TypeError and leaves no dock widget behind.

  Args:
    main_window: The window PyMOL returns.
  """
  with pytest.raises(TypeError):
    ui.add_dock_panel(object(), "Sequences")
  qt.QtCore.QCoreApplication.sendPostedEvents(
      None, qt.QtCore.QEvent.Type.DeferredDelete
  )
  assert main_window.findChildren(qt.QtWidgets.QDockWidget) == []
  assert ui.get_dock_panel("Sequences") is None


def test_none_widget_raises_type_error(main_window):
  """None as the widget raises TypeError instead of making an empty panel.

  Args:
    main_window: The window PyMOL returns.
  """
  with pytest.raises(TypeError):
    ui.add_dock_panel(None, "Sequences")
  assert main_window.findChildren(qt.QtWidgets.QDockWidget) == []


def test_visible_false_starts_hidden_and_unchecked(main_window):
  """visible=False keeps the dock hidden and its menu entry unchecked.

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_panel = ui.add_dock_panel(
      qt.QtWidgets.QLabel(), "Scenes", visible=False
  )
  [[tmp_entry]] = _plugin_panels_actions(main_window)
  assert not tmp_panel.is_visible()
  assert tmp_panel.dock_widget.isHidden()
  assert ui.get_dock_panel("Scenes") is tmp_panel
  assert not tmp_entry.isChecked()
  tmp_panel.show()
  assert tmp_panel.is_visible()
  assert tmp_entry.isChecked()


def test_hidden_panel_tabs_cleanly_when_shown_beside_second_panel(main_window):
  """A hidden panel in the same area joins tabs and raises on show().

  Args:
    main_window: The window PyMOL returns.
  """
  tmp_first = ui.add_dock_panel(
      qt.QtWidgets.QLabel(), "Scenes", area="right", visible=False
  )
  tmp_second = ui.add_dock_panel(
      qt.QtWidgets.QLabel(), "Objects", area="right", visible=True
  )
  assert not tmp_first.is_visible()
  assert tmp_second.is_visible()
  tmp_first.show()
  assert tmp_first.is_visible()
  assert tmp_second.dock_widget in main_window.tabifiedDockWidgets(
      tmp_first.dock_widget
  )
  assert ([["Scenes", "Objects"], "Scenes"]
          in [list(tmp_pair) for tmp_pair in _tab_titles_and_current(
              main_window)])
