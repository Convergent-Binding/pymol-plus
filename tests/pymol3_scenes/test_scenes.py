# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the docked Scenes panel."""

import os
import subprocess
import sys

import pytest

import pymol.cmd
from pymol3 import _scenes_panel
from pymol3 import app
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


def test_rename_via_f2_and_double_click_updates_pymol_preserving_spaces(
    scene_window, monkeypatch
):
  """F2 and double-click rename in place, trimming ends and keeping spaces.

  Args:
    scene_window: Main window fixture wired to PyMOL.
    monkeypatch: Spies on ``pymol.cmd.scene`` for unchanged names.
  """
  pymol.cmd.scene("001", "store")
  pymol.cmd.scene("002", "store")
  scenes.start(scene_window)
  scenes.ready(scene_window)
  tmp_widget = ui.get_dock_panel(scenes.PANEL_ID).dock_widget.widget()
  tmp_view = tmp_widget.list_view
  tmp_model = tmp_view.model()
  tmp_view.resize(260, 300)
  qt.QtWidgets.QApplication.processEvents()

  tmp_view.setCurrentIndex(tmp_model.index(0, 0))
  _simulate_key_press(tmp_view, qt.QtCore.Qt.Key.Key_F2)
  assert tmp_view.state() == qt.QtWidgets.QAbstractItemView.State.EditingState
  assert pymol.cmd.get("scene_current_name") == "002"
  tmp_editor = tmp_view.findChild(qt.QtWidgets.QLineEdit)
  assert tmp_editor is not None
  tmp_editor.setText("  Active site  ")
  _simulate_key_press(tmp_editor, qt.QtCore.Qt.Key.Key_Return)
  qt.QtWidgets.QApplication.processEvents()
  qt.QtCore.QCoreApplication.sendPostedEvents(
      None, qt.QtCore.QEvent.Type.DeferredDelete
  )

  assert pymol.cmd.get_scene_list() == ["Active site", "002"]
  assert pymol.cmd.get("scene_current_name") == "002"
  assert tmp_widget.notice_label.isHidden()

  tmp_row_two_center = tmp_view.visualRect(tmp_model.index(1, 0)).center()
  tmp_double_click = qt.QtGui.QMouseEvent(
      qt.QtCore.QEvent.Type.MouseButtonDblClick,
      qt.QtCore.QPointF(tmp_row_two_center),
      qt.QtCore.QPointF(tmp_view.viewport().mapToGlobal(tmp_row_two_center)),
      qt.QtCore.Qt.MouseButton.LeftButton,
      qt.QtCore.Qt.MouseButton.LeftButton,
      qt.QtCore.Qt.KeyboardModifier.NoModifier,
  )
  tmp_view.mouseDoubleClickEvent(tmp_double_click)
  assert tmp_view.state() == qt.QtWidgets.QAbstractItemView.State.EditingState
  tmp_editor_two = tmp_view.findChild(qt.QtWidgets.QLineEdit)
  assert tmp_editor_two is not None
  tmp_editor_two.setText("Final view")
  _simulate_key_press(tmp_editor_two, qt.QtCore.Qt.Key.Key_Return)
  qt.QtWidgets.QApplication.processEvents()
  assert pymol.cmd.get_scene_list() == ["Active site", "Final view"]
  assert pymol.cmd.get("scene_current_name") == "Final view"

  tmp_scene_calls = []
  tmp_real_scene = pymol.cmd.scene

  def tmp_spy_scene(*args, **kwargs):
    """Records ``cmd.scene`` calls while forwarding to PyMOL.

    Args:
      *args: Positional arguments for ``cmd.scene``.
      **kwargs: Keyword arguments for ``cmd.scene``.

    Returns:
      Result of ``pymol.cmd.scene``.
    """
    tmp_scene_calls.append((args, kwargs))
    return tmp_real_scene(*args, **kwargs)

  monkeypatch.setattr(pymol.cmd, "scene", tmp_spy_scene)
  tmp_unchanged = tmp_model.setData(
      tmp_model.index(1, 0),
      "Final view",
      qt.QtCore.Qt.ItemDataRole.EditRole,
  )
  assert tmp_unchanged is False
  assert tmp_scene_calls == []


@pytest.mark.parametrize(
    "bad_name",
    ["001", "", "   ", "*", "new", "auto", "line\nbreak"],
)
def test_rename_refuses_duplicate_empty_and_reserved_names(
    scene_window, capsys, bad_name
):
  """Duplicate, empty, multi-line, and reserved names are refused with reason.

  Args:
    scene_window: Main window fixture wired to PyMOL.
    capsys: Captures PyMOL stdout notice.
    bad_name: Invalid rename target under test.
  """
  pymol.cmd.scene("001", "store")
  pymol.cmd.scene("002", "store")
  scenes.start(scene_window)
  scenes.ready(scene_window)
  tmp_widget = ui.get_dock_panel(scenes.PANEL_ID).dock_widget.widget()
  tmp_model = tmp_widget.list_view.model()

  tmp_accepted = tmp_model.setData(
      tmp_model.index(1, 0),
      bad_name,
      qt.QtCore.Qt.ItemDataRole.EditRole,
  )
  assert tmp_accepted is False
  assert pymol.cmd.get_scene_list() == ["001", "002"]
  assert tmp_model.index(1, 0).data() == "002"
  assert not tmp_widget.notice_label.isHidden()
  assert tmp_widget.notice_label.text()
  assert capsys.readouterr().out.strip()


def test_drag_reorder_updates_pymol_playback_order_once_without_recall(
    scene_window, monkeypatch
):
  """Dragging a row reorders PyMOL playback once and never recalls or loops.

  Args:
    scene_window: Main window fixture wired to PyMOL.
    monkeypatch: Spies on ``cmd.scene_order`` and ``cmd.scene``.
  """
  pymol.cmd.scene("001", "store")
  pymol.cmd.scene("binding pocket", "store")
  pymol.cmd.scene("003", "store")
  scenes.start(scene_window)
  scenes.ready(scene_window)
  tmp_widget = ui.get_dock_panel(scenes.PANEL_ID).dock_widget.widget()
  tmp_view = tmp_widget.list_view
  tmp_model = tmp_view.model()
  tmp_view.resize(260, 300)
  qt.QtWidgets.QApplication.processEvents()

  tmp_order_calls = []
  tmp_real_order = pymol.cmd.scene_order

  def tmp_spy_order(names, *args, **kwargs):
    """Records ``cmd.scene_order`` calls while forwarding to PyMOL.

    Args:
      names: Ordered scene names passed to ``scene_order``.
      *args: Extra positional arguments.
      **kwargs: Extra keyword arguments.

    Returns:
      Result of ``pymol.cmd.scene_order``.
    """
    tmp_order_calls.append((list(names), kwargs.get("location")))
    return tmp_real_order(names, *args, **kwargs)

  tmp_scene_calls = []
  tmp_real_scene = pymol.cmd.scene

  def tmp_spy_scene(*args, **kwargs):
    """Records ``cmd.scene`` calls while forwarding to PyMOL.

    Args:
      *args: Positional arguments for ``cmd.scene``.
      **kwargs: Keyword arguments for ``cmd.scene``.

    Returns:
      Result of ``pymol.cmd.scene``.
    """
    tmp_scene_calls.append(args)
    return tmp_real_scene(*args, **kwargs)

  monkeypatch.setattr(pymol.cmd, "scene_order", tmp_spy_order)
  monkeypatch.setattr(pymol.cmd, "scene", tmp_spy_scene)

  tmp_mime = tmp_model.mimeData([tmp_model.index(2, 0)])
  tmp_top_point = tmp_view.visualRect(tmp_model.index(0, 0)).topLeft()
  tmp_drop_position = qt.QtCore.QPointF(
      tmp_top_point.x() + 10, tmp_top_point.y() + 2
  )
  tmp_drop = qt.QtGui.QDropEvent(
      tmp_drop_position,
      qt.QtCore.Qt.DropAction.MoveAction,
      tmp_mime,
      qt.QtCore.Qt.MouseButton.LeftButton,
      qt.QtCore.Qt.KeyboardModifier.NoModifier,
  )
  monkeypatch.setattr(tmp_drop, "source", lambda: tmp_view)
  tmp_view.dropEvent(tmp_drop)

  assert pymol.cmd.get_scene_list() == ["003", "001", "binding pocket"]
  assert tmp_order_calls == [(["003", "001", "binding pocket"], "top")]
  assert tmp_scene_calls == []

  scenes.tick(scene_window)
  scenes.tick(scene_window)
  assert len(tmp_order_calls) == 1

  pymol.cmd.scene("", "next")
  assert pymol.cmd.get("scene_current_name") == "001"


def test_starts_hidden_auto_opens_once_and_stays_closed_after_close(
    scene_window,
):
  """Panel starts hidden, auto-opens on first scene, and stays closed.

  Args:
    scene_window: Main window fixture wired to PyMOL.
  """
  app.start(scene_window)
  app.ready(scene_window)
  tmp_panel = ui.get_dock_panel(scenes.PANEL_ID)
  assert tmp_panel is not None
  assert (
      scene_window.dockWidgetArea(tmp_panel.dock_widget)
      == qt.QtCore.Qt.DockWidgetArea.RightDockWidgetArea
  )
  assert not tmp_panel.is_visible()

  pymol.cmd.scene("F1", "store")
  for tmp_callback in scene_window.setting_callbacks[
      _scenes_panel.SETTING_SCENES_CHANGED
  ]:
    tmp_callback(True)
  app.tick(scene_window)
  assert tmp_panel.is_visible()
  tmp_model = tmp_panel.dock_widget.widget().list_view.model()
  assert [
      tmp_model.index(tmp_row, 0).data()
      for tmp_row in range(tmp_model.rowCount())
  ] == ["F1"]
  assert tmp_model.index(0, 0).data(_scenes_panel.IS_CURRENT_ROLE) is True

  tmp_panel.dock_widget.close()
  assert not tmp_panel.is_visible()

  pymol.cmd.scene("F2", "store")
  app.tick(scene_window)
  assert [
      tmp_model.index(tmp_row, 0).data()
      for tmp_row in range(tmp_model.rowCount())
  ] == ["F1", "F2"]
  assert not tmp_panel.is_visible()

  assert scenes.open_panel(scene_window) is True
  assert tmp_panel.is_visible()


def test_auto_opens_on_session_with_scenes_and_respects_manual_close(
    scene_window, monkeypatch, tmp_path
):
  """Loading a .pse with scenes auto-opens; manual close prevents auto-open.

  Args:
    scene_window: Main window fixture wired to PyMOL.
    monkeypatch: Redirects ``pymol.gui.get_qtwindow`` for the second window.
    tmp_path: Temporary folder for saving the test session file.
  """
  pymol.cmd.pseudoatom("mol")
  pymol.cmd.scene("S1", "store")
  tmp_session = tmp_path / "with_scenes.pse"
  pymol.cmd.save(str(tmp_session))
  pymol.cmd.reinitialize()

  app.start(scene_window)
  app.ready(scene_window)
  tmp_panel = ui.get_dock_panel(scenes.PANEL_ID)
  assert not tmp_panel.is_visible()

  pymol.cmd.load(str(tmp_session))
  app.tick(scene_window)
  assert tmp_panel.is_visible()
  assert tmp_panel.dock_widget.widget().list_view.model().names() == ["S1"]

  pymol.cmd.reinitialize()
  tmp_second_window = qt.QtWidgets.QMainWindow()
  tmp_second_window.setCentralWidget(qt.QtWidgets.QWidget())
  tmp_second_window.cmd = pymol.cmd
  tmp_second_window.show()
  monkeypatch.setattr(
      "pymol.gui.get_qtwindow", lambda: tmp_second_window
  )
  try:
    scenes.start(tmp_second_window)
    scenes.ready(tmp_second_window)
    tmp_second_controller = scenes._controller(tmp_second_window)
    tmp_second_panel = tmp_second_controller._dock_panel
    assert not tmp_second_panel.is_visible()
    assert scenes.open_panel(tmp_second_window) is True
    assert tmp_second_panel.is_visible()
    tmp_second_panel.dock_widget.close()
    assert not tmp_second_panel.is_visible()

    pymol.cmd.scene("new", "store")
    app.tick(tmp_second_window)
    assert tmp_second_controller._model.names() == ["001"]
    assert not tmp_second_panel.is_visible()
  finally:
    tmp_second_window.close()
    tmp_second_window.deleteLater()


def test_external_scene_order_current_scene_and_reinitialize_sync(
    scene_window,
):
  """External order, PgDn, editing guard, and reinitialize stay in sync.

  Args:
    scene_window: Main window fixture wired to PyMOL.
  """
  pymol.cmd.scene("001", "store")
  pymol.cmd.scene("002", "store")
  pymol.cmd.scene("003", "store")
  app.start(scene_window)
  app.ready(scene_window)
  tmp_widget = ui.get_dock_panel(scenes.PANEL_ID).dock_widget.widget()
  tmp_view = tmp_widget.list_view
  tmp_model = tmp_view.model()
  tmp_view.resize(260, 300)
  qt.QtWidgets.QApplication.processEvents()

  pymol.cmd.scene_order(["003", "001", "002"])
  app.tick(scene_window)
  assert tmp_model.names() == ["003", "001", "002"]

  pymol.cmd.scene("", "next")
  app.tick(scene_window)
  assert tmp_model.index(0, 0).data(_scenes_panel.IS_CURRENT_ROLE) is False
  assert tmp_model.index(1, 0).data(_scenes_panel.IS_CURRENT_ROLE) is True

  tmp_view.setCurrentIndex(tmp_model.index(0, 0))
  _simulate_key_press(tmp_view, qt.QtCore.Qt.Key.Key_F2)
  assert tmp_view.state() == qt.QtWidgets.QAbstractItemView.State.EditingState
  pymol.cmd.scene("004", "store")
  app.tick(scene_window)
  assert tmp_view.state() == qt.QtWidgets.QAbstractItemView.State.EditingState
  assert tmp_model.names() == ["003", "001", "002"]

  tmp_editor = tmp_view.findChild(qt.QtWidgets.QLineEdit)
  _simulate_key_press(tmp_editor, qt.QtCore.Qt.Key.Key_Escape)
  qt.QtWidgets.QApplication.processEvents()
  app.tick(scene_window)
  assert tmp_model.names() == ["003", "001", "002", "004"]

  pymol.cmd.reinitialize()
  app.tick(scene_window)
  assert tmp_model.rowCount() == 0
  assert not tmp_widget.empty_label.isHidden()


def test_thumbnail_fetches_on_change_and_caps_retries_when_empty(
    scene_window, monkeypatch
):
  """Thumbnails fetch on change and stop polling after arrival or retry cap.

  Args:
    scene_window: Main window fixture wired to PyMOL.
    monkeypatch: Supplies controlled thumbnail bytes and counts queries.
  """
  tmp_valid_png = _valid_png_bytes()
  tmp_payloads = {"001": b"", "002": b""}
  tmp_calls = []

  def tmp_fake_thumbnail(name: str, _self=pymol.cmd) -> bytes:
    """Records each thumbnail query and returns the configured buffer.

    Args:
      name: Scene name requested.
      _self: Unused cmd binding.

    Returns:
      Configured PNG or empty bytes.
    """
    tmp_calls.append(name)
    return tmp_payloads.get(name, b"")

  monkeypatch.setattr(pymol.cmd, "get_scene_thumbnail", tmp_fake_thumbnail)
  pymol.cmd.scene("001", "store")
  pymol.cmd.scene("002", "store")
  app.start(scene_window)
  app.ready(scene_window)
  tmp_calls.clear()

  tmp_payloads["001"] = tmp_valid_png
  tmp_payloads["002"] = tmp_valid_png
  app.tick(scene_window)
  assert sorted(tmp_calls) == ["001", "002"]

  tmp_calls.clear()
  for _ in range(10):
    app.tick(scene_window)
  assert tmp_calls == []

  pymol.cmd.scene("003", "store")
  tmp_payloads["003"] = b""
  app.tick(scene_window)
  tmp_calls.clear()
  for _ in range(scenes.MAX_THUMBNAIL_RETRIES + 10):
    app.tick(scene_window)
  assert len(tmp_calls) == scenes.MAX_THUMBNAIL_RETRIES
  assert all(tmp_name == "003" for tmp_name in tmp_calls)


def test_scene_menu_hook_opens_panel_in_new_gui_and_falls_back_in_classic(
    scene_window, monkeypatch
):
  """Scene menu hook opens the docked panel only when the new GUI is active.

  Args:
    scene_window: Main window fixture wired to PyMOL.
    monkeypatch: Switches between new and classic GUI styles.
  """
  app.start(scene_window)
  app.ready(scene_window)
  tmp_panel = ui.get_dock_panel(scenes.PANEL_ID)
  assert not tmp_panel.is_visible()
  assert scenes.open_panel(scene_window) is True
  assert tmp_panel.is_visible()

  monkeypatch.setattr(app, "_state", app._State())
  monkeypatch.setenv(app.ENVIRONMENT_VARIABLE, app.CLASSIC)
  app.register(scenes.FEATURE)
  assert app.style() == app.CLASSIC
  assert scenes.open_panel(scene_window) is False


def _fire_update_feedback(window) -> None:
  """Simulates PyMOLQtGUI.update_feedback() callbacks followed by app.tick().

  Args:
    window: Main window fixture with ``cmd`` and ``setting_callbacks``.
  """
  for tmp_setting in window.cmd.get_setting_updates() or ():
    if tmp_setting in window.setting_callbacks:
      tmp_value = window.cmd.get_setting_tuple(tmp_setting)[1][0]
      for tmp_callback in window.setting_callbacks[tmp_setting]:
        tmp_callback(tmp_value)
  app.tick(window)


def test_scenes_changed_callback_preserves_inline_editor_and_drag_state(
    scene_window,
):
  """setting_callbacks[254] does not clobber inline rename or active drag.

  Args:
    scene_window: Main window fixture wired to PyMOL.
  """
  pymol.cmd.scene("001", "store")
  pymol.cmd.scene("002", "store")
  app.start(scene_window)
  app.ready(scene_window)
  tmp_widget = ui.get_dock_panel(scenes.PANEL_ID).dock_widget.widget()
  tmp_view = tmp_widget.list_view
  tmp_model = tmp_view.model()
  tmp_view.resize(260, 300)
  qt.QtWidgets.QApplication.processEvents()

  _simulate_row_click(tmp_view, 0)
  tmp_row_zero_center = tmp_view.visualRect(tmp_model.index(0, 0)).center()
  tmp_double_click = qt.QtGui.QMouseEvent(
      qt.QtCore.QEvent.Type.MouseButtonDblClick,
      qt.QtCore.QPointF(tmp_row_zero_center),
      qt.QtCore.QPointF(tmp_view.viewport().mapToGlobal(tmp_row_zero_center)),
      qt.QtCore.Qt.MouseButton.LeftButton,
      qt.QtCore.Qt.MouseButton.LeftButton,
      qt.QtCore.Qt.KeyboardModifier.NoModifier,
  )
  tmp_view.mouseDoubleClickEvent(tmp_double_click)
  assert tmp_view.state() == qt.QtWidgets.QAbstractItemView.State.EditingState
  tmp_editor = tmp_view.findChild(qt.QtWidgets.QLineEdit)
  assert tmp_editor is not None
  tmp_editor.setText("Draft name")

  _fire_update_feedback(scene_window)
  assert tmp_view.state() == qt.QtWidgets.QAbstractItemView.State.EditingState
  assert tmp_editor.text() == "Draft name"

  pymol.cmd.scene("003", "store")
  _fire_update_feedback(scene_window)
  assert tmp_view.state() == qt.QtWidgets.QAbstractItemView.State.EditingState
  assert tmp_editor.text() == "Draft name"
  assert tmp_model.names() == ["001", "002"]

  _simulate_key_press(tmp_editor, qt.QtCore.Qt.Key.Key_Return)
  qt.QtWidgets.QApplication.processEvents()
  _fire_update_feedback(scene_window)
  assert tmp_model.names() == ["Draft name", "002", "003"]

  tmp_view.setState(qt.QtWidgets.QAbstractItemView.State.DraggingState)
  pymol.cmd.scene("004", "store")
  _fire_update_feedback(scene_window)
  assert tmp_model.names() == ["Draft name", "002", "003"]

  tmp_view.setState(qt.QtWidgets.QAbstractItemView.State.NoState)
  _fire_update_feedback(scene_window)
  assert tmp_model.names() == ["Draft name", "002", "003", "004"]
