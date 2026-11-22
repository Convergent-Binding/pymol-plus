# SPDX-License-Identifier: BSD-3-Clause
"""Tests of pymol3.gui's dock panels in a Qt main window."""

import pytest

from pymol3 import gui

# Skips this module without a Qt binding; the fixtures make the window.
qt = pytest.importorskip("pymol.Qt")
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
