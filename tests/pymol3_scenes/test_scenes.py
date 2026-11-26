# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the docked Scenes panel."""

import os
import subprocess
import sys

import pytest

import pymol.cmd
from pymol3 import _scenes_panel
from pymol3 import scenes
from pymol3 import ui

from ..pymol3_ui import qt_binding


qt = qt_binding.import_qt()
"""The Qt binding PyMOL found."""


def _valid_png_bytes(color_name: str = "#336699") -> bytes:
  """Builds valid PNG bytes using Qt's offscreen QImage encoder.

  Args:
    color_name: Fill color name or hex code.

  Returns:
    Encoded PNG bytes.
  """
  tmp_image = qt.QtGui.QImage(
      220, 124, qt.QtGui.QImage.Format.Format_RGBA8888
  )
  tmp_image.fill(qt.QtGui.QColor(color_name))
  tmp_buffer = qt.QtCore.QBuffer()
  tmp_buffer.open(qt.QtCore.QIODevice.OpenModeFlag.WriteOnly)
  tmp_image.save(tmp_buffer, "PNG")
  return bytes(tmp_buffer.data())


def _simulate_key_press(widget, key) -> None:
  """Sends a key press and release event to ``widget``.

  Args:
    widget: Target Qt widget.
    key: ``Qt.Key`` member to press.
  """
  tmp_modifiers = qt.QtCore.Qt.KeyboardModifier.NoModifier
  tmp_press = qt.QtGui.QKeyEvent(
      qt.QtCore.QEvent.Type.KeyPress, int(key), tmp_modifiers
  )
  tmp_release = qt.QtGui.QKeyEvent(
      qt.QtCore.QEvent.Type.KeyRelease, int(key), tmp_modifiers
  )
  qt.QtWidgets.QApplication.sendEvent(widget, tmp_press)
  qt.QtWidgets.QApplication.sendEvent(widget, tmp_release)


def _simulate_row_click(view, row: int) -> None:
  """Simulates a plain left-click in the middle of a list row.

  Args:
    view: The scenes list view.
    row: Zero-based row index to click.
  """
  tmp_index = view.model().index(row, 0)
  tmp_rectangle = view.visualRect(tmp_index)
  tmp_center = tmp_rectangle.center()
  tmp_mouse_button = qt.QtCore.Qt.MouseButton.LeftButton
  tmp_modifiers = qt.QtCore.Qt.KeyboardModifier.NoModifier
  tmp_press = qt.QtGui.QMouseEvent(
      qt.QtCore.QEvent.Type.MouseButtonPress,
      qt.QtCore.QPointF(tmp_center),
      qt.QtCore.QPointF(view.viewport().mapToGlobal(tmp_center)),
      tmp_mouse_button,
      tmp_mouse_button,
      tmp_modifiers,
  )
  tmp_release = qt.QtGui.QMouseEvent(
      qt.QtCore.QEvent.Type.MouseButtonRelease,
      qt.QtCore.QPointF(tmp_center),
      qt.QtCore.QPointF(view.viewport().mapToGlobal(tmp_center)),
      tmp_mouse_button,
      qt.QtCore.Qt.MouseButton.NoButton,
      tmp_modifiers,
  )
  view.mousePressEvent(tmp_press)
  view.mouseReleaseEvent(tmp_release)


def _simulate_delete_button_click(view, row: int) -> None:
  """Simulates a left-click on a row's inline delete button.

  Args:
    view: The scenes list view.
    row: Zero-based row index whose delete button to click.
  """
  tmp_index = view.model().index(row, 0)
  tmp_rectangle = view.visualRect(tmp_index)
  tmp_button_rectangle = view.itemDelegate().delete_button_rect(tmp_rectangle)
  tmp_center = tmp_button_rectangle.center()
  tmp_mouse_button = qt.QtCore.Qt.MouseButton.LeftButton
  tmp_modifiers = qt.QtCore.Qt.KeyboardModifier.NoModifier
  tmp_press = qt.QtGui.QMouseEvent(
      qt.QtCore.QEvent.Type.MouseButtonPress,
      qt.QtCore.QPointF(tmp_center),
      qt.QtCore.QPointF(view.viewport().mapToGlobal(tmp_center)),
      tmp_mouse_button,
      tmp_mouse_button,
      tmp_modifiers,
  )
  tmp_release = qt.QtGui.QMouseEvent(
      qt.QtCore.QEvent.Type.MouseButtonRelease,
      qt.QtCore.QPointF(tmp_center),
      qt.QtCore.QPointF(view.viewport().mapToGlobal(tmp_center)),
      tmp_mouse_button,
      qt.QtCore.Qt.MouseButton.NoButton,
      tmp_modifiers,
  )
  view.mousePressEvent(tmp_press)
  view.mouseReleaseEvent(tmp_release)


def test_import_needs_no_qt_binding():
  """Importing pymol3.scenes loads no Qt binding in a fresh interpreter."""
  tmp_environment = dict(os.environ)
  tmp_environment["PYTHONPATH"] = os.pathsep.join(sys.path)
  tmp_result = subprocess.run(
      [
          sys.executable,
          "-c",
          "import sys, pymol3.scenes; "
          "sys.exit(any(name == 'pymol.Qt' or name.split('.')[0] in "
          "('PySide6', 'PyQt5', 'PyQt6', 'shiboken6') "
          "for name in sys.modules))",
      ],
      env=tmp_environment,
      capture_output=True,
      text=True,
      check=False,
  )
  assert tmp_result.returncode == 0, tmp_result.stderr


def test_empty_state_and_plus_creates_numbered_scenes(scene_window):
  """Empty state starts visible, and + creates numbered scenes in order.

  Args:
    scene_window: Main window fixture wired to PyMOL.
  """
  scenes.start(scene_window)
  tmp_panel = ui.get_dock_panel(scenes.PANEL_ID)
  assert tmp_panel is not None
  tmp_widget = tmp_panel.dock_widget.widget()
  assert not tmp_widget.empty_label.isHidden()
  assert tmp_widget.list_view.isHidden()
  assert not tmp_widget.update_button.isEnabled()

  tmp_widget.add_button.click()
  tmp_widget.add_button.click()
  tmp_model = tmp_widget.list_view.model()
  assert pymol.cmd.get_scene_list() == ["001", "002"]
  assert [
      tmp_model.index(tmp_row, 0).data()
      for tmp_row in range(tmp_model.rowCount())
  ] == ["001", "002"]
  assert tmp_widget.empty_label.isHidden()
  assert not tmp_widget.list_view.isHidden()
  assert tmp_model.index(1, 0).data(_scenes_panel.IS_CURRENT_ROLE) is True
  assert tmp_model.index(0, 0).data(_scenes_panel.IS_CURRENT_ROLE) is False


def test_click_and_enter_recall_while_arrows_and_right_click_do_not(
    scene_window,
):
  """Click and Enter recall scenes; arrows and right-click only select.

  Args:
    scene_window: Main window fixture wired to PyMOL.
  """
  pymol.cmd.pseudoatom("mol", pos=[0.0, 0.0, 0.0])
  pymol.cmd.scene("001", "store", message="First message")
  tmp_view_one = pymol.cmd.get_view()
  pymol.cmd.turn("y", 45)
  pymol.cmd.scene("002", "store", message="Second message")
  tmp_view_two = pymol.cmd.get_view()
  assert tmp_view_one != tmp_view_two

  scenes.start(scene_window)
  scenes.ready(scene_window)
  tmp_widget = ui.get_dock_panel(scenes.PANEL_ID).dock_widget.widget()
  tmp_view = tmp_widget.list_view
  tmp_model = tmp_view.model()
  tmp_view.resize(260, 300)
  qt.QtWidgets.QApplication.processEvents()

  assert (
      tmp_model.index(0, 0).data(qt.QtCore.Qt.ItemDataRole.ToolTipRole)
      == "First message"
  )
  assert pymol.cmd.get("scene_current_name") == "002"

  tmp_view.setCurrentIndex(tmp_model.index(1, 0))
  _simulate_key_press(tmp_view, qt.QtCore.Qt.Key.Key_Up)
  assert tmp_view.currentIndex().row() == 0
  assert pymol.cmd.get("scene_current_name") == "002"
  assert pymol.cmd.get_view() == pytest.approx(tmp_view_two)

  tmp_row_two_center = tmp_view.visualRect(tmp_model.index(1, 0)).center()
  tmp_right_press = qt.QtGui.QMouseEvent(
      qt.QtCore.QEvent.Type.MouseButtonPress,
      qt.QtCore.QPointF(tmp_row_two_center),
      qt.QtCore.QPointF(tmp_view.viewport().mapToGlobal(tmp_row_two_center)),
      qt.QtCore.Qt.MouseButton.RightButton,
      qt.QtCore.Qt.MouseButton.RightButton,
      qt.QtCore.Qt.KeyboardModifier.NoModifier,
  )
  tmp_view.mousePressEvent(tmp_right_press)
  assert tmp_view.currentIndex().row() == 1
  assert pymol.cmd.get("scene_current_name") == "002"

  _simulate_row_click(tmp_view, 0)
  assert pymol.cmd.get("scene_current_name") == "001"
  assert pymol.cmd.get_view() == pytest.approx(tmp_view_one)

  tmp_view.setCurrentIndex(tmp_model.index(1, 0))
  assert pymol.cmd.get("scene_current_name") == "001"
  _simulate_key_press(tmp_view, qt.QtCore.Qt.Key.Key_Return)
  assert pymol.cmd.get("scene_current_name") == "002"
  assert pymol.cmd.get_view() == pytest.approx(tmp_view_two)


def test_update_stores_current_screen_and_keeps_target_message(scene_window):
  """Updating a selected non-current scene keeps its own message.

  Args:
    scene_window: Main window fixture wired to PyMOL.
  """
  pymol.cmd.pseudoatom("mol", pos=[0.0, 0.0, 0.0])
  pymol.cmd.scene("001", "store", message="Keep alpha message")
  pymol.cmd.turn("x", 60)
  pymol.cmd.scene("002", "store", message="Beta message")
  tmp_screen_view = pymol.cmd.get_view()

  scenes.start(scene_window)
  scenes.ready(scene_window)
  tmp_widget = ui.get_dock_panel(scenes.PANEL_ID).dock_widget.widget()
  tmp_view = tmp_widget.list_view
  tmp_view.setCurrentIndex(tmp_view.model().index(0, 0))
  assert pymol.cmd.get("scene_current_name") == "002"
  assert tmp_widget.update_button.isEnabled()

  tmp_widget.update_button.click()
  assert pymol.cmd.get_scene_message("001") == "Keep alpha message"
  assert pymol.cmd.get_scene_message("002") == "Beta message"
  assert pymol.cmd.get("scene_current_name") == "001"

  pymol.cmd.scene("002", "recall", animate=0)
  pymol.cmd.scene("001", "recall", animate=0)
  assert pymol.cmd.get_view() == pytest.approx(tmp_screen_view)


def test_delete_via_row_button_key_and_context_menu(scene_window):
  """Row delete button, Delete key, and context menu delete without recall.

  Args:
    scene_window: Main window fixture wired to PyMOL.
  """
  pymol.cmd.pseudoatom("mol", pos=[0.0, 0.0, 0.0])
  pymol.cmd.scene("001", "store")
  pymol.cmd.scene("002", "store")
  pymol.cmd.scene("003", "store")

  scenes.start(scene_window)
  scenes.ready(scene_window)
  tmp_widget = ui.get_dock_panel(scenes.PANEL_ID).dock_widget.widget()
  tmp_view = tmp_widget.list_view
  tmp_model = tmp_view.model()
  tmp_view.resize(260, 300)
  qt.QtWidgets.QApplication.processEvents()

  assert pymol.cmd.get("scene_current_name") == "003"
  _simulate_delete_button_click(tmp_view, 0)
  assert pymol.cmd.get_scene_list() == ["002", "003"]
  assert pymol.cmd.get("scene_current_name") == "003"

  tmp_view.setCurrentIndex(tmp_model.index(0, 0))
  _simulate_key_press(tmp_view, qt.QtCore.Qt.Key.Key_Delete)
  assert pymol.cmd.get_scene_list() == ["003"]

  tmp_menu = tmp_view.build_context_menu(tmp_model.index(0, 0))
  tmp_delete_action = next(
      tmp_action
      for tmp_action in tmp_menu.actions()
      if tmp_action.text() == "Delete"
  )
  tmp_delete_action.trigger()
  assert pymol.cmd.get_scene_list() == []
  assert not tmp_widget.empty_label.isHidden()


def test_thumbnail_loads_valid_png_and_rejects_zero_buffer_and_scrolls(
    scene_window, monkeypatch
):
  """Zeroed RGBA buffers show placeholder; valid PNG loads; 15 scenes scroll.

  Args:
    scene_window: Main window fixture wired to PyMOL.
    monkeypatch: Supplies synthetic PNG and zeroed thumbnail buffers.
  """
  tmp_valid_png = _valid_png_bytes()
  tmp_zero_buffer = b"\x00" * (220 * 124 * 4)
  for tmp_number in range(1, 16):
    pymol.cmd.scene(f"{tmp_number:03d}", "store")

  def tmp_fake_thumbnail(name: str, _self=pymol.cmd) -> bytes:
    """Returns a valid PNG for 001 and a zeroed RGBA buffer for others.

    Args:
      name: Scene name.
      _self: Unused cmd binding.

    Returns:
      PNG bytes or zeroed RGBA bytes.
    """
    return tmp_valid_png if name == "001" else tmp_zero_buffer

  monkeypatch.setattr(pymol.cmd, "get_scene_thumbnail", tmp_fake_thumbnail)
  scenes.start(scene_window)
  scenes.ready(scene_window)
  tmp_widget = ui.get_dock_panel(scenes.PANEL_ID).dock_widget.widget()
  tmp_view = tmp_widget.list_view
  tmp_model = tmp_view.model()
  tmp_widget.resize(260, 250)
  tmp_view.resize(260, 200)
  qt.QtWidgets.QApplication.processEvents()

  tmp_first_pixmap = tmp_model.index(0, 0).data(_scenes_panel.PIXMAP_ROLE)
  tmp_second_pixmap = tmp_model.index(1, 0).data(_scenes_panel.PIXMAP_ROLE)
  assert isinstance(tmp_first_pixmap, qt.QtGui.QPixmap)
  assert not tmp_first_pixmap.isNull()
  assert tmp_second_pixmap is None
  assert tmp_view.verticalScrollBar().maximum() > 0
