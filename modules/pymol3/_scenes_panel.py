# SPDX-License-Identifier: BSD-3-Clause
"""Qt model, view, delegate, widget, and controller for the Scenes panel."""

from __future__ import annotations

import dataclasses
import importlib
from collections.abc import Callable

import pymol.Qt
from pymol3 import scenes
from pymol3 import ui


QtCore = pymol.Qt.QtCore
"""QtCore module from PyMOL's active Qt binding."""

QtGui = pymol.Qt.QtGui
"""QtGui module from PyMOL's active Qt binding."""

QtWidgets = pymol.Qt.QtWidgets
"""QtWidgets module from PyMOL's active Qt binding."""

SETTING_SCENES_CHANGED = 254
"""PyMOL setting index flagged whenever ``cmd.scene`` mutates scenes."""

SETTING_SCENE_CURRENT_NAME = 396
"""PyMOL setting index holding the currently recalled scene key."""

THUMBNAIL_WIDTH = 88
"""Width in pixels of rendered scene thumbnails (16:9 ratio)."""

THUMBNAIL_HEIGHT = 50
"""Height in pixels of rendered scene thumbnails (16:9 ratio)."""

ROW_HEIGHT = 64
"""Height in pixels of each scene row in the panel list."""

DELETE_BUTTON_SIZE = 24
"""Square size in pixels of the per-row delete hit target."""

PIXMAP_ROLE = int(QtCore.Qt.ItemDataRole.UserRole) + 1
"""Model role returning the ``QPixmap`` thumbnail, or None for placeholder."""

IS_CURRENT_ROLE = int(QtCore.Qt.ItemDataRole.UserRole) + 2
"""Model role returning True when the row represents the current scene."""

SCENE_ROW_MIME = "application/x-pymol3-scene-row"
"""MIME type carrying the dragged scene row index during reordering."""


@dataclasses.dataclass
class _SceneEntry:
  """Cached presentation state for a single PyMOL scene.

  Attributes:
    name: Scene key in PyMOL.
    pixmap: Decoded thumbnail pixmap, or None when unavailable.
    message: Scene text message shown in the row tooltip.
    retries_left: Remaining ticks to retry fetching an unrendered thumbnail.
  """

  name: str
  pixmap: QtGui.QPixmap | None = None
  message: str = ""
  retries_left: int = 0


def pixmap_from_png(png_bytes: object) -> QtGui.QPixmap | None:
  """Decodes raw PNG bytes into a ``QPixmap``, rejecting empty or raw buffers.

  ``MovieSceneStore`` pre-allocates zeroed RGBA bytes before OpenGL redraw,
  and ``.pse`` files leave thumbnails empty. Both fail ``loadFromData(...,
  "PNG")`` and return None so the delegate draws a placeholder instead.

  Args:
    png_bytes: Raw bytes returned by ``cmd.get_scene_thumbnail``.

  Returns:
    A non-null ``QPixmap`` when valid PNG bytes were decoded, else None.
  """
  if not png_bytes:
    return None
  tmp_pixmap = QtGui.QPixmap()
  if (
      tmp_pixmap.loadFromData(bytes(png_bytes), "PNG")
      and not tmp_pixmap.isNull()
  ):
    return tmp_pixmap
  return None


class _ScenesListModel(QtCore.QAbstractListModel):
  """List model backing the docked Scenes panel."""

  def __init__(self, parent: QtCore.QObject | None = None) -> None:
    """Initializes an empty scenes model.

    Args:
      parent: Optional Qt parent object.
    """
    super().__init__(parent)
    self._entries: list[_SceneEntry] = []
    """Ordered scene entries matching PyMOL's ``get_scene_list()``."""
    self._current_name: str = ""
    """Name of the scene currently active in PyMOL, or empty string."""
    self._rename_handler: Callable[[int, str], bool] | None = None
    """Optional callback validating and applying inline scene renames."""

  def set_rename_handler(
      self, handler: Callable[[int, str], bool] | None
  ) -> None:
    """Registers the callback invoked when an inline edit commits.

    Args:
      handler: Callable taking ``(row, proposed_name)`` and returning True if
        the rename succeeded.
    """
    self._rename_handler = handler

  def rowCount(
      self, parent: QtCore.QModelIndex = QtCore.QModelIndex()
  ) -> int:
    """Returns the number of scenes at the root level.

    Args:
      parent: Parent model index.

    Returns:
      Number of scenes when ``parent`` is invalid, else 0.
    """
    if parent.isValid():
      return 0
    return len(self._entries)

  def data(
      self,
      index: QtCore.QModelIndex,
      role: int = int(QtCore.Qt.ItemDataRole.DisplayRole),
  ):
    """Returns scene data for the requested model role.

    Args:
      index: Model index of the row.
      role: Qt item data role.

    Returns:
      The requested role value, or None when unavailable.
    """
    if not index.isValid() or not (0 <= index.row() < len(self._entries)):
      return None
    tmp_entry = self._entries[index.row()]
    if role in (
        int(QtCore.Qt.ItemDataRole.DisplayRole),
        int(QtCore.Qt.ItemDataRole.EditRole),
    ):
      return tmp_entry.name
    if role == int(QtCore.Qt.ItemDataRole.ToolTipRole):
      return tmp_entry.message or None
    if role == PIXMAP_ROLE:
      return tmp_entry.pixmap
    if role == IS_CURRENT_ROLE:
      return tmp_entry.name == self._current_name
    return None

  def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
    """Returns item interaction flags for rows and root drop targets.

    Args:
      index: Target model index.

    Returns:
      Flags enabling selection, editing, and drag without dropping onto items.
    """
    if not index.isValid():
      return QtCore.Qt.ItemFlag.ItemIsDropEnabled
    return (
        QtCore.Qt.ItemFlag.ItemIsEnabled
        | QtCore.Qt.ItemFlag.ItemIsSelectable
        | QtCore.Qt.ItemFlag.ItemIsEditable
        | QtCore.Qt.ItemFlag.ItemIsDragEnabled
    )

  def entry_at(self, row: int) -> _SceneEntry | None:
    """Returns the entry at ``row`` when in bounds.

    Args:
      row: Zero-based row index.

    Returns:
      The ``_SceneEntry`` or None.
    """
    if 0 <= row < len(self._entries):
      return self._entries[row]
    return None

  def row_for_name(self, name: str) -> int:
    """Finds the row index for a scene name.

    Args:
      name: Scene name to locate.

    Returns:
      Zero-based row index, or -1 when absent.
    """
    for tmp_row, tmp_entry in enumerate(self._entries):
      if tmp_entry.name == name:
        return tmp_row
    return -1

  def names(self) -> list[str]:
    """Returns the ordered list of scene names in the model.

    Returns:
      List of scene names.
    """
    return [tmp_entry.name for tmp_entry in self._entries]

  def set_entries(
      self, entries: list[_SceneEntry], current_name: str
  ) -> bool:
    """Replaces the model's entries, resetting only when scene names change.

    Args:
      entries: New ordered entries.
      current_name: Currently active PyMOL scene name.

    Returns:
      True if the row list structure changed (reset performed), else False.
    """
    tmp_old_names = [tmp_entry.name for tmp_entry in self._entries]
    tmp_new_names = [tmp_entry.name for tmp_entry in entries]
    if tmp_old_names != tmp_new_names:
      self.beginResetModel()
      self._entries = list(entries)
      self._current_name = current_name
      self.endResetModel()
      return True
    self._entries = list(entries)
    self._current_name = current_name
    if self._entries:
      self.dataChanged.emit(
          self.index(0, 0),
          self.index(len(self._entries) - 1, 0),
      )
    return False

  def update_current(self, current_name: str) -> None:
    """Updates the highlighted current scene without resetting the model.

    Args:
      current_name: Currently active PyMOL scene name.
    """
    if self._current_name == current_name:
      return
    self._current_name = current_name
    if self._entries:
      self.dataChanged.emit(
          self.index(0, 0),
          self.index(len(self._entries) - 1, 0),
          [IS_CURRENT_ROLE],
      )

  def setData(
      self,
      index: QtCore.QModelIndex,
      value: object,
      role: int = int(QtCore.Qt.ItemDataRole.EditRole),
  ) -> bool:
    """Delegates committed inline edits to the registered rename handler.

    Args:
      index: Model index being edited.
      value: Committed editor text.
      role: Qt item data role.

    Returns:
      True when the rename succeeded, else False.
    """
    if (
        not index.isValid()
        or role != int(QtCore.Qt.ItemDataRole.EditRole)
        or self._rename_handler is None
    ):
      return False
    return self._rename_handler(index.row(), str(value))

  def rename_at(self, row: int, new_name: str, current_name: str) -> None:
    """Updates the cached scene name in place after a PyMOL rename.

    Args:
      row: Zero-based row index to rename.
      new_name: Accepted new scene name.
      current_name: Updated ``scene_current_name`` in PyMOL.
    """
    if not (0 <= row < len(self._entries)):
      return
    self._entries[row].name = new_name
    self._current_name = current_name
    tmp_index = self.index(row, 0)
    self.dataChanged.emit(tmp_index, tmp_index)

  def supportedDropActions(self) -> QtCore.Qt.DropAction:
    """Restricts drag-and-drop reordering to move operations.

    Returns:
      ``Qt.DropAction.MoveAction``.
    """
    return QtCore.Qt.DropAction.MoveAction

  def mimeTypes(self) -> list[str]:
    """Lists MIME formats produced for dragging scene rows.

    Returns:
      Single-element list containing :data:`SCENE_ROW_MIME`.
    """
    return [SCENE_ROW_MIME]

  def mimeData(self, indexes: list[QtCore.QModelIndex]) -> QtCore.QMimeData:
    """Encodes the dragged row index into ``QMimeData``.

    Args:
      indexes: Selected model indexes being dragged.

    Returns:
      ``QMimeData`` carrying the source row index.
    """
    tmp_mime = QtCore.QMimeData()
    if indexes and indexes[0].isValid():
      tmp_payload = str(indexes[0].row()).encode("ascii")
      tmp_mime.setData(SCENE_ROW_MIME, tmp_payload)
    return tmp_mime

  def move_row(self, source_row: int, destination_row: int) -> bool:
    """Moves one entry from ``source_row`` to ``destination_row``.

    Args:
      source_row: Current zero-based row index.
      destination_row: Final zero-based row index after the move.

    Returns:
      True when a move occurred, False when indices are invalid or equal.
    """
    tmp_count = len(self._entries)
    if (
        not (0 <= source_row < tmp_count)
        or not (0 <= destination_row < tmp_count)
        or source_row == destination_row
    ):
      return False
    tmp_qt_target = (
        destination_row + 1
        if destination_row > source_row
        else destination_row
    )
    self.beginMoveRows(
        QtCore.QModelIndex(),
        source_row,
        source_row,
        QtCore.QModelIndex(),
        tmp_qt_target,
    )
    tmp_entry = self._entries.pop(source_row)
    self._entries.insert(destination_row, tmp_entry)
    self.endMoveRows()
    return True


class _SceneItemDelegate(QtWidgets.QStyledItemDelegate):
  """Paints scene thumbnails, current-scene highlights, names, and delete."""

  def sizeHint(
      self,
      _option: QtWidgets.QStyleOptionViewItem,
      _index: QtCore.QModelIndex,
  ) -> QtCore.QSize:
    """Returns a fixed row height suitable for 16:9 thumbnails.

    Args:
      _option: Style option (unused).
      _index: Model index (unused).

    Returns:
      Size hint with ``ROW_HEIGHT`` height.
    """
    return QtCore.QSize(220, ROW_HEIGHT)

  def delete_button_rect(self, row_rect: QtCore.QRect) -> QtCore.QRect:
    """Computes the hit target rectangle for the row's inline delete button.

    Args:
      row_rect: Bounding rectangle of the row.

    Returns:
      Square rectangle aligned to the right edge of the row.
    """
    tmp_top = row_rect.top() + (row_rect.height() - DELETE_BUTTON_SIZE) // 2
    tmp_left = row_rect.right() - DELETE_BUTTON_SIZE - 8
    return QtCore.QRect(
        tmp_left, tmp_top, DELETE_BUTTON_SIZE, DELETE_BUTTON_SIZE
    )

  def text_rect(self, row_rect: QtCore.QRect) -> QtCore.QRect:
    """Computes the text and inline-editor rectangle for a row.

    Args:
      row_rect: Bounding rectangle of the row.

    Returns:
      Rectangle between the thumbnail and the delete button.
    """
    tmp_left = row_rect.left() + 12 + THUMBNAIL_WIDTH + 10
    tmp_right = self.delete_button_rect(row_rect).left() - 6
    return QtCore.QRect(
        tmp_left,
        row_rect.top() + 6,
        max(40, tmp_right - tmp_left),
        row_rect.height() - 12,
    )

  def _thumbnail_rect(self, row_rect: QtCore.QRect) -> QtCore.QRect:
    """Computes the thumbnail bounding rectangle on the left of a row.

    Args:
      row_rect: Bounding rectangle of the row.

    Returns:
      ``THUMBNAIL_WIDTH`` by ``THUMBNAIL_HEIGHT`` rectangle.
    """
    tmp_top = row_rect.top() + (row_rect.height() - THUMBNAIL_HEIGHT) // 2
    return QtCore.QRect(
        row_rect.left() + 12, tmp_top, THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT
    )

  def paint(
      self,
      painter: QtGui.QPainter,
      option: QtWidgets.QStyleOptionViewItem,
      index: QtCore.QModelIndex,
  ) -> None:
    """Paints a single scene row.

    Args:
      painter: Active Qt painter.
      option: Style options for the row.
      index: Model index of the scene row.
    """
    painter.save()
    tmp_palette = option.palette
    tmp_selected = bool(
        option.state & QtWidgets.QStyle.StateFlag.State_Selected
    )
    tmp_current = bool(index.data(IS_CURRENT_ROLE))
    if tmp_selected:
      painter.fillRect(option.rect, tmp_palette.highlight())
    elif tmp_current:
      tmp_tint = QtGui.QColor(tmp_palette.highlight().color())
      tmp_tint.setAlpha(36)
      painter.fillRect(option.rect, tmp_tint)
    if tmp_current:
      tmp_bar = QtCore.QRect(
          option.rect.left(),
          option.rect.top() + 2,
          3,
          option.rect.height() - 4,
      )
      painter.fillRect(tmp_bar, tmp_palette.highlight())

    tmp_thumb_rect = self._thumbnail_rect(option.rect)
    tmp_pixmap = index.data(PIXMAP_ROLE)
    if isinstance(tmp_pixmap, QtGui.QPixmap) and not tmp_pixmap.isNull():
      tmp_scaled = tmp_pixmap.scaled(
          tmp_thumb_rect.size(),
          QtCore.Qt.AspectRatioMode.KeepAspectRatio,
          QtCore.Qt.TransformationMode.SmoothTransformation,
      )
      tmp_draw_x = (
          tmp_thumb_rect.left()
          + (tmp_thumb_rect.width() - tmp_scaled.width()) // 2
      )
      tmp_draw_y = (
          tmp_thumb_rect.top()
          + (tmp_thumb_rect.height() - tmp_scaled.height()) // 2
      )
      painter.drawPixmap(tmp_draw_x, tmp_draw_y, tmp_scaled)
    else:
      painter.setPen(tmp_palette.mid().color())
      painter.setBrush(tmp_palette.base())
      painter.drawRoundedRect(tmp_thumb_rect, 4, 4)
      painter.drawText(
          tmp_thumb_rect,
          QtCore.Qt.AlignmentFlag.AlignCenter,
          "No preview",
      )

    tmp_text_rect = self.text_rect(option.rect)
    tmp_font = QtGui.QFont(option.font)
    tmp_font.setBold(tmp_current)
    painter.setFont(tmp_font)
    tmp_text_color = (
        tmp_palette.highlightedText().color()
        if tmp_selected
        else tmp_palette.text().color()
    )
    painter.setPen(tmp_text_color)
    tmp_metrics = QtGui.QFontMetrics(tmp_font)
    tmp_elided = tmp_metrics.elidedText(
        str(index.data() or ""),
        QtCore.Qt.TextElideMode.ElideRight,
        tmp_text_rect.width(),
    )
    painter.drawText(
        tmp_text_rect,
        (
            QtCore.Qt.AlignmentFlag.AlignVCenter
            | QtCore.Qt.AlignmentFlag.AlignLeft
        ),
        tmp_elided,
    )

    tmp_delete_rect = self.delete_button_rect(option.rect)
    tmp_delete_color = (
        tmp_palette.highlightedText().color()
        if tmp_selected
        else tmp_palette.placeholderText().color()
    )
    painter.setPen(tmp_delete_color)
    painter.drawText(
        tmp_delete_rect, QtCore.Qt.AlignmentFlag.AlignCenter, "\u00d7"
    )
    painter.restore()

  def updateEditorGeometry(
      self,
      editor: QtWidgets.QWidget,
      option: QtWidgets.QStyleOptionViewItem,
      _index: QtCore.QModelIndex,
  ) -> None:
    """Constrains the inline rename editor to the row's text area.

    Args:
      editor: Line edit widget created by Qt.
      option: Style options for the row.
      _index: Model index (unused).
    """
    editor.setGeometry(self.text_rect(option.rect))


class _ScenesListView(QtWidgets.QListView):
  """List view enforcing recall, selection, context menu, and delete rules."""

  recall_requested = QtCore.Signal(str)
  """Signal emitted with a scene name when clicked or activated via Enter."""

  update_requested = QtCore.Signal(str)
  """Signal emitted with a scene name from the context menu's Update."""

  delete_requested = QtCore.Signal(str)
  """Signal emitted with a scene name from the row button, Delete, or menu."""

  reorder_requested = QtCore.Signal(int, int)
  """Signal emitted with ``(source_row, destination_row)`` on row drop."""

  def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
    """Configures scrolling, single selection, and custom edit triggers.

    Args:
      parent: Optional parent widget.
    """
    super().__init__(parent)
    self.setEditTriggers(
        QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
    )
    self.setSelectionMode(
        QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
    )
    self.setVerticalScrollMode(
        QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
    )
    self.setVerticalScrollBarPolicy(
        QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )
    self.setHorizontalScrollBarPolicy(
        QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    self.setUniformItemSizes(True)
    self.setDragEnabled(True)
    self.setAcceptDrops(True)
    self.setDropIndicatorShown(True)
    self.setDragDropMode(
        QtWidgets.QAbstractItemView.DragDropMode.InternalMove
    )
    self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
    self._press_position: QtCore.QPoint | None = None
    """Viewport position of the active left mouse press, if any."""
    self._pressed_index = QtCore.QModelIndex()
    """Model index hit on the active left mouse press."""
    self._pressed_delete = False
    """Whether the active left mouse press landed on the row delete rect."""

  def _is_delete_hit(
      self, index: QtCore.QModelIndex, position: QtCore.QPoint
  ) -> bool:
    """Returns True when ``position`` lies inside ``index``'s delete button.

    Args:
      index: Row index under the pointer.
      position: Viewport coordinate.

    Returns:
      True when inside the delete target rectangle.
    """
    if not index.isValid():
      return False
    tmp_delegate = self.itemDelegate()
    if not isinstance(tmp_delegate, _SceneItemDelegate):
      return False
    tmp_rectangle = tmp_delegate.delete_button_rect(self.visualRect(index))
    return tmp_rectangle.contains(position)

  def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
    """Selects on press without recalling; tracks click vs. drag/delete.

    Args:
      event: Qt mouse press event.
    """
    tmp_position = event.position().toPoint()
    tmp_index = self.indexAt(tmp_position)
    if event.button() == QtCore.Qt.MouseButton.RightButton:
      if tmp_index.isValid():
        self.setCurrentIndex(tmp_index)
      event.accept()
      return
    if event.button() == QtCore.Qt.MouseButton.LeftButton:
      self._press_position = tmp_position
      self._pressed_index = tmp_index
      self._pressed_delete = self._is_delete_hit(tmp_index, tmp_position)
    super().mousePressEvent(event)

  def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
    """Triggers recall or delete on a plain left-click release.

    Args:
      event: Qt mouse release event.
    """
    tmp_press_position = self._press_position
    tmp_pressed_index = self._pressed_index
    tmp_pressed_delete = self._pressed_delete
    self._press_position = None
    self._pressed_index = QtCore.QModelIndex()
    self._pressed_delete = False

    if (
        event.button() == QtCore.Qt.MouseButton.LeftButton
        and tmp_press_position is not None
        and self.state() != QtWidgets.QAbstractItemView.State.DraggingState
    ):
      tmp_position = event.position().toPoint()
      tmp_distance = (tmp_position - tmp_press_position).manhattanLength()
      tmp_drag_threshold = QtWidgets.QApplication.startDragDistance()
      tmp_index = self.indexAt(tmp_position)
      if (
          tmp_distance < tmp_drag_threshold
          and tmp_index.isValid()
          and tmp_index == tmp_pressed_index
      ):
        tmp_name = str(tmp_index.data() or "")
        if tmp_pressed_delete and self._is_delete_hit(tmp_index, tmp_position):
          self.delete_requested.emit(tmp_name)
        elif not tmp_pressed_delete:
          self.recall_requested.emit(tmp_name)
    super().mouseReleaseEvent(event)

  def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
    """Starts inline rename on double-click outside the delete button.

    Args:
      event: Qt mouse double-click event.
    """
    if event.button() == QtCore.Qt.MouseButton.LeftButton:
      tmp_position = event.position().toPoint()
      tmp_index = self.indexAt(tmp_position)
      if tmp_index.isValid() and not self._is_delete_hit(
          tmp_index, tmp_position
      ):
        self.edit(tmp_index)
        event.accept()
        return
    super().mouseDoubleClickEvent(event)

  def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
    """Handles Enter recall, Delete removal, and F2 inline rename.

    Args:
      event: Qt key press event.
    """
    if self.state() != QtWidgets.QAbstractItemView.State.EditingState:
      tmp_index = self.currentIndex()
      tmp_key = event.key()
      if tmp_index.isValid():
        tmp_name = str(tmp_index.data() or "")
        if tmp_key in (
            int(QtCore.Qt.Key.Key_Return),
            int(QtCore.Qt.Key.Key_Enter),
        ):
          self.recall_requested.emit(tmp_name)
          event.accept()
          return
        if tmp_key == int(QtCore.Qt.Key.Key_Delete):
          self.delete_requested.emit(tmp_name)
          event.accept()
          return
        if tmp_key == int(QtCore.Qt.Key.Key_F2):
          self.edit(tmp_index)
          event.accept()
          return
    super().keyPressEvent(event)

  def build_context_menu(
      self, index: QtCore.QModelIndex
  ) -> QtWidgets.QMenu:
    """Builds the context menu for the given scene row.

    Args:
      index: Model index for the targeted row.

    Returns:
      Populated ``QMenu`` with Recall, Update, Rename, and Delete actions.
    """
    tmp_name = str(index.data() or "")
    tmp_menu = QtWidgets.QMenu(self)
    tmp_recall = tmp_menu.addAction("Recall")
    tmp_recall.triggered.connect(
        lambda _checked=False, scene_name=tmp_name: self.recall_requested.emit(
            scene_name
        )
    )
    tmp_update = tmp_menu.addAction("Update")
    tmp_update.triggered.connect(
        lambda _checked=False, scene_name=tmp_name: self.update_requested.emit(
            scene_name
        )
    )
    tmp_rename = tmp_menu.addAction("Rename")
    tmp_rename.triggered.connect(
        lambda _checked=False, row_index=index: self.edit(row_index)
    )
    tmp_menu.addSeparator()
    tmp_delete = tmp_menu.addAction("Delete")
    tmp_delete.triggered.connect(
        lambda _checked=False, scene_name=tmp_name: self.delete_requested.emit(
            scene_name
        )
    )
    return tmp_menu

  def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
    """Selects the clicked row without recalling and opens its context menu.

    Args:
      event: Qt context menu event.
    """
    tmp_index = self.indexAt(event.pos())
    if not tmp_index.isValid():
      return
    self.setCurrentIndex(tmp_index)
    tmp_menu = self.build_context_menu(tmp_index)
    tmp_menu.exec(event.globalPos())

  def dropEvent(self, event: QtGui.QDropEvent) -> None:
    """Commits an internal row drag as an atomic reorder without recall.

    Args:
      event: Qt drop event.
    """
    tmp_mime = event.mimeData()
    tmp_model = self.model()
    if (
        event.source() not in (self, None)
        or tmp_mime is None
        or not tmp_mime.hasFormat(SCENE_ROW_MIME)
        or tmp_model is None
        or tmp_model.rowCount() == 0
    ):
      event.ignore()
      return
    try:
      tmp_source_row = int(bytes(tmp_mime.data(SCENE_ROW_MIME)).decode("ascii"))
    except ValueError:
      event.ignore()
      return
    tmp_position = event.position().toPoint()
    tmp_target_index = self.indexAt(tmp_position)
    if not tmp_target_index.isValid():
      tmp_slot = tmp_model.rowCount()
    elif tmp_position.y() > self.visualRect(tmp_target_index).center().y():
      tmp_slot = tmp_target_index.row() + 1
    else:
      tmp_slot = tmp_target_index.row()
    tmp_destination = (
        tmp_slot - 1 if tmp_slot > tmp_source_row else tmp_slot
    )
    tmp_destination = max(0, min(tmp_model.rowCount() - 1, tmp_destination))
    self._press_position = None
    self._pressed_index = QtCore.QModelIndex()
    self._pressed_delete = False
    self.reorder_requested.emit(tmp_source_row, tmp_destination)
    event.acceptProposedAction()


class ScenesPanelWidget(QtWidgets.QWidget):
  """Top-level widget docked inside the Scenes panel."""

  def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
    """Builds the panel toolbar, inline notice, empty hint, and list view.

    Args:
      parent: Optional parent widget.
    """
    super().__init__(parent)
    tmp_layout = QtWidgets.QVBoxLayout(self)
    tmp_layout.setContentsMargins(8, 8, 8, 8)
    tmp_layout.setSpacing(6)

    tmp_toolbar = QtWidgets.QHBoxLayout()
    tmp_toolbar.setSpacing(6)
    self.add_button = QtWidgets.QPushButton("+", self)
    """Button creating a new numbered scene from the current view."""
    self.add_button.setObjectName("scenes_add_button")
    self.add_button.setFixedWidth(32)
    self.add_button.setToolTip("Save current view as a new scene")
    tmp_toolbar.addWidget(self.add_button)

    self.update_button = QtWidgets.QPushButton("Update", self)
    """Button storing the current screen into the selected scene."""
    self.update_button.setObjectName("scenes_update_button")
    self.update_button.setEnabled(False)
    self.update_button.setToolTip("Update selected scene with current view")
    tmp_toolbar.addWidget(self.update_button)
    tmp_toolbar.addStretch()
    tmp_layout.addLayout(tmp_toolbar)

    self.notice_label = QtWidgets.QLabel(self)
    """Inline warning banner shown when a rename is refused."""
    self.notice_label.setObjectName("scenes_notice_label")
    self.notice_label.setWordWrap(True)
    self.notice_label.setStyleSheet("color: #c62828;")
    self.notice_label.hide()
    tmp_layout.addWidget(self.notice_label)

    self.empty_label = QtWidgets.QLabel(
        "No scenes yet.\nClick + to save the current view.", self
    )
    """Placeholder hint shown while no scenes exist."""
    self.empty_label.setObjectName("scenes_empty_label")
    self.empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    self.empty_label.setWordWrap(True)
    self.empty_label.setStyleSheet("color: gray;")
    tmp_layout.addWidget(self.empty_label, 1)

    self.list_view = _ScenesListView(self)
    """List view displaying scenes with thumbnails and names."""
    self.list_view.setObjectName("scenes_list_view")
    self.list_view.hide()
    tmp_layout.addWidget(self.list_view, 1)

  def show_notice(self, message: str) -> None:
    """Displays an inline validation notice below the panel toolbar.

    Args:
      message: Explanation shown to the user.
    """
    self.notice_label.setText(message)
    self.notice_label.show()

  def clear_notice(self) -> None:
    """Hides any previously displayed validation notice."""
    self.notice_label.clear()
    self.notice_label.hide()

  def set_empty(self, is_empty: bool) -> None:
    """Toggles between the empty-state hint and the scenes list view.

    Args:
      is_empty: True when PyMOL currently defines zero scenes.
    """
    self.empty_label.setVisible(is_empty)
    self.list_view.setVisible(not is_empty)


class ScenesController:
  """Coordinates PyMOL scene commands, the Qt model, and dock visibility."""

  def __init__(
      self,
      window: QtWidgets.QMainWindow,
      cmd,
      widget: ScenesPanelWidget,
      dock_panel: ui.DockPanel,
  ) -> None:
    """Wires UI interactions and PyMOL setting callbacks.

    Args:
      window: PyMOL's main window.
      cmd: PyMOL command module for scene operations.
      widget: The Scenes panel widget.
      dock_panel: ``pymol3.ui.DockPanel`` wrapping ``widget``.
    """
    self._window = window
    """PyMOL's main window."""
    self._cmd = cmd
    """PyMOL command API object."""
    self._widget = widget
    """Top-level Scenes panel widget."""
    self._dock_panel = dock_panel
    """Dock handle controlling visibility and tab raising."""
    self._model = _ScenesListModel(widget.list_view)
    """List model backing the panel's list view."""
    self._delegate = _SceneItemDelegate(widget.list_view)
    """Custom item delegate rendering thumbnails and delete targets."""
    self._entries_by_name: dict[str, _SceneEntry] = {}
    """Cached scene entries keyed by scene name."""
    self._current_name = ""
    """Last observed ``scene_current_name`` value."""
    self._auto_opened = False
    """Whether automatic one-time opening has occurred or been consumed."""
    self._was_shown = False
    """Whether the panel has ever been visible during this run."""
    self._dirty_scenes = False
    """Whether ``scenes_changed`` fired since the last sync."""

    self._widget.list_view.setModel(self._model)
    self._model.set_rename_handler(self.rename_scene)
    self._widget.list_view.setItemDelegate(self._delegate)
    self._widget.add_button.clicked.connect(self.create_scene)
    self._widget.update_button.clicked.connect(self.update_selected_scene)
    self._widget.list_view.recall_requested.connect(self.recall_scene)
    self._widget.list_view.update_requested.connect(self.update_scene)
    self._widget.list_view.delete_requested.connect(self.delete_scene)
    self._widget.list_view.reorder_requested.connect(self.reorder_scene)
    self._widget.list_view.selectionModel().selectionChanged.connect(
        self._update_buttons
    )
    self._dock_panel.dock_widget.visibilityChanged.connect(
        self._on_visibility_changed
    )
    self._register_setting_callbacks()

  def _register_setting_callbacks(self) -> None:
    """Subscribes to PyMOL's scene setting callbacks on the main window."""
    tmp_callbacks = getattr(self._window, "setting_callbacks", None)
    if not isinstance(tmp_callbacks, dict):
      return
    tmp_callbacks[SETTING_SCENES_CHANGED].append(self._on_scenes_changed)
    tmp_callbacks[SETTING_SCENE_CURRENT_NAME].append(
        self._on_current_scene_changed
    )

  def _on_scenes_changed(self, _value: object) -> None:
    """Marks scene metadata dirty when PyMOL's ``scenes_changed`` fires.

    Args:
      _value: Setting value passed by ``PyMOLQtGUI`` (unused).
    """
    self._dirty_scenes = True
    self.sync(refresh_thumbnails=True, auto_open=True)

  def _on_current_scene_changed(self, value: object) -> None:
    """Updates current-scene highlighting when ``scene_current_name`` changes.

    Args:
      value: New ``scene_current_name`` string.
    """
    self._current_name = str(value or "")
    self._model.update_current(self._current_name)

  def _on_visibility_changed(self, visible: bool) -> None:
    """Tracks manual show/close so auto-open never overrides user dismissal.

    Args:
      visible: New Qt visibility state of the dock widget.
    """
    if visible:
      self._was_shown = True
    elif self._was_shown:
      self._auto_opened = True

  def _update_buttons(self, *_args: object) -> None:
    """Enables Update only when a valid scene row is selected."""
    tmp_selection = self._widget.list_view.selectionModel().selectedIndexes()
    self._widget.update_button.setEnabled(bool(tmp_selection))

  def _selected_scene_name(self) -> str | None:
    """Returns the currently selected scene name, if any.

    Returns:
      Selected scene name, or None when nothing is selected.
    """
    tmp_index = self._widget.list_view.currentIndex()
    if not tmp_index.isValid():
      return None
    tmp_entry = self._model.entry_at(tmp_index.row())
    return tmp_entry.name if tmp_entry is not None else None

  def _select_scene(self, name: str) -> None:
    """Selects ``name`` in the list view if present without recalling.

    Args:
      name: Scene name to select.
    """
    tmp_row = self._model.row_for_name(name)
    if tmp_row < 0:
      return
    tmp_index = self._model.index(tmp_row, 0)
    self._widget.list_view.setCurrentIndex(tmp_index)

  def _fetch_entry(
      self, name: str, force_thumbnail: bool
  ) -> _SceneEntry:
    """Builds or refreshes the cached ``_SceneEntry`` for ``name``.

    Args:
      name: Scene name in PyMOL.
      force_thumbnail: True to re-query ``get_scene_thumbnail`` even if cached.

    Returns:
      Updated ``_SceneEntry`` for ``name``.
    """
    tmp_previous = self._entries_by_name.get(name)
    tmp_message = str(self._cmd.get_scene_message(name) or "")
    if tmp_previous is not None and not force_thumbnail:
      tmp_pixmap = tmp_previous.pixmap
      tmp_retries = tmp_previous.retries_left
      if tmp_pixmap is None and tmp_retries > 0:
        tmp_png = self._cmd.get_scene_thumbnail(name)
        tmp_pixmap = pixmap_from_png(tmp_png)
        tmp_retries = 0 if tmp_pixmap is not None else tmp_retries - 1
    else:
      tmp_png = self._cmd.get_scene_thumbnail(name)
      tmp_pixmap = pixmap_from_png(tmp_png)
      tmp_retries = (
          0 if tmp_pixmap is not None else scenes.MAX_THUMBNAIL_RETRIES
      )
    return _SceneEntry(
        name=name,
        pixmap=tmp_pixmap,
        message=tmp_message,
        retries_left=tmp_retries,
    )

  def sync(
      self,
      refresh_thumbnails: bool = False,
      auto_open: bool = False,
  ) -> None:
    """Synchronizes the panel list, highlights, and thumbnails with PyMOL.

    Args:
      refresh_thumbnails: True to fetch thumbnails for all scenes again.
      auto_open: True to auto-open the panel once if scenes are non-empty.
    """
    tmp_names = list(self._cmd.get_scene_list() or ())
    tmp_current = str(self._cmd.get("scene_current_name") or "")
    tmp_selected = self._selected_scene_name()

    tmp_entries: list[_SceneEntry] = []
    tmp_new_cache: dict[str, _SceneEntry] = {}
    for tmp_name in tmp_names:
      tmp_is_new = tmp_name not in self._entries_by_name
      tmp_entry = self._fetch_entry(
          tmp_name, force_thumbnail=refresh_thumbnails or tmp_is_new
      )
      tmp_entries.append(tmp_entry)
      tmp_new_cache[tmp_name] = tmp_entry

    self._entries_by_name = tmp_new_cache
    self._current_name = tmp_current
    self._dirty_scenes = False
    tmp_reset = self._model.set_entries(tmp_entries, tmp_current)
    self._widget.set_empty(not tmp_names)
    if tmp_reset and tmp_selected is not None:
      self._select_scene(tmp_selected)
    self._update_buttons()

    if auto_open and tmp_names and not self._auto_opened:
      self._auto_opened = True
      self._dock_panel.show()

  def on_tick(self) -> None:
    """Runs on PyMOL's 500 ms timer to catch unnotified scene changes."""
    if self._widget.list_view.state() in (
        QtWidgets.QAbstractItemView.State.EditingState,
        QtWidgets.QAbstractItemView.State.DraggingState,
    ):
      return
    tmp_names = list(self._cmd.get_scene_list() or ())
    tmp_current = str(self._cmd.get("scene_current_name") or "")
    tmp_needs_retry = any(
        tmp_entry.pixmap is None and tmp_entry.retries_left > 0
        for tmp_entry in self._entries_by_name.values()
    )
    if (
        self._dirty_scenes
        or tmp_names != self._model.names()
        or tmp_current != self._current_name
        or tmp_needs_retry
    ):
      self.sync(refresh_thumbnails=self._dirty_scenes, auto_open=True)

  def open_panel(self) -> None:
    """Shows and raises the docked Scenes panel, marking auto-open done."""
    self._auto_opened = True
    self._dock_panel.show()

  def create_scene(self) -> None:
    """Saves the current view as a new auto-numbered scene."""
    self._widget.clear_notice()
    self._cmd.scene("new", "store")
    self.sync(refresh_thumbnails=False, auto_open=True)
    if self._current_name:
      self._select_scene(self._current_name)

  def recall_scene(self, name: str) -> None:
    """Recalls the named scene with PyMOL's default animation.

    Args:
      name: Scene name to recall.
    """
    self._widget.clear_notice()
    self._cmd.scene(name, "recall")
    self._current_name = str(self._cmd.get("scene_current_name") or name)
    self._model.update_current(self._current_name)

  def update_scene(self, name: str) -> None:
    """Updates ``name`` with the current screen while keeping its own message.

    Args:
      name: Scene name to update.
    """
    self._widget.clear_notice()
    tmp_message = str(self._cmd.get_scene_message(name) or "")
    self._cmd.scene(name, "update", message=tmp_message)
    self._entries_by_name.pop(name, None)
    self.sync(refresh_thumbnails=False)
    self._select_scene(name)

  def update_selected_scene(self) -> None:
    """Updates whichever scene row is currently selected."""
    tmp_name = self._selected_scene_name()
    if tmp_name is not None:
      self.update_scene(tmp_name)

  def delete_scene(self, name: str) -> None:
    """Removes ``name`` from PyMOL without recalling it.

    Args:
      name: Scene name to delete.
    """
    self._widget.clear_notice()
    self._cmd.scene(name, "clear")
    self._entries_by_name.pop(name, None)
    self.sync(refresh_thumbnails=False)

  def rename_scene(self, row: int, proposed_name: str) -> bool:
    """Validates and applies an in-place scene rename in PyMOL.

    Args:
      row: Zero-based row index being renamed.
      proposed_name: Raw text entered by the user.

    Returns:
      True when PyMOL renamed the scene, else False.
    """
    tmp_entry = self._model.entry_at(row)
    if tmp_entry is None:
      return False
    tmp_old_name = tmp_entry.name
    tmp_cleaned, tmp_reason = scenes.validate_scene_name(
        tmp_old_name, proposed_name, self._model.names()
    )
    if tmp_reason is not None:
      self._widget.show_notice(tmp_reason)
      tmp_rectangle = self._widget.list_view.visualRect(
          self._model.index(row, 0)
      )
      tmp_global = self._widget.list_view.viewport().mapToGlobal(
          tmp_rectangle.center()
      )
      QtWidgets.QToolTip.showText(
          tmp_global,
          tmp_reason,
          self._widget.list_view,
          tmp_rectangle,
      )
      print(f" PyMOL+: cannot rename scene {tmp_old_name!r}: {tmp_reason}")
      return False
    if tmp_cleaned is None:
      self._widget.clear_notice()
      return False
    self._widget.clear_notice()
    self._cmd.scene(tmp_old_name, "rename", new_key=tmp_cleaned)
    self._entries_by_name.pop(tmp_old_name, None)
    tmp_entry.name = tmp_cleaned
    self._entries_by_name[tmp_cleaned] = tmp_entry
    self._current_name = str(self._cmd.get("scene_current_name") or "")
    self._model.rename_at(row, tmp_cleaned, self._current_name)
    return True

  def reorder_scene(self, source_row: int, destination_row: int) -> None:
    """Reorders scenes in the model and sends the new order to PyMOL.

    Args:
      source_row: Zero-based index of the dragged scene.
      destination_row: Zero-based index where the scene landed.
    """
    self._widget.clear_notice()
    if not self._model.move_row(source_row, destination_row):
      return
    tmp_ordered = self._model.names()
    self._cmd.scene_order(tmp_ordered, location="top")
    self._widget.list_view.setCurrentIndex(
        self._model.index(destination_row, 0)
    )


def install(window: QtWidgets.QMainWindow) -> ScenesController:
  """Builds, docks (hidden), and returns the Scenes panel controller.

  Args:
    window: PyMOL's main window.

  Returns:
    The installed ``ScenesController``.
  """
  tmp_cmd = getattr(window, "cmd", None)
  if tmp_cmd is None:
    tmp_cmd = importlib.import_module("pymol.cmd")
  tmp_widget = ScenesPanelWidget()
  tmp_dock_panel = ui.add_dock_panel(
      tmp_widget,
      scenes.PANEL_TITLE,
      area="right",
      panel_id=scenes.PANEL_ID,
      visible=False,
  )
  return ScenesController(window, tmp_cmd, tmp_widget, tmp_dock_panel)
