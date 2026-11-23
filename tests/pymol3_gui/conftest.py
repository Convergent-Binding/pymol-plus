# SPDX-License-Identifier: BSD-3-Clause
"""Fixtures that stand a plain Qt main window in for PyMOL's.

Qt runs on its ``offscreen`` platform, so the tests never open a window on
a real display, also in the wheel test job of CI. Without a Qt binding the
fixtures skip their tests.
"""

import os

import pytest

import pymol.gui

from . import qt_binding

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _make_window(monkeypatch: pytest.MonkeyPatch, with_menus: bool):
  """Makes a shown main window and makes PyMOL return it as its window.

  Args:
    monkeypatch: Replaces ``pymol.gui.get_qtwindow`` for one test.
    with_menus: Whether the window gets PyMOL's ``menudict`` with a
      Display menu, as PyMOL's own window has.

  Returns:
    The main window.
  """
  tmp_qt = qt_binding.import_qt()
  if tmp_qt.QtWidgets.QApplication.instance() is None:
    tmp_qt.QtWidgets.QApplication(["pymol3-tests"])
  tmp_window = tmp_qt.QtWidgets.QMainWindow()
  tmp_window.setCentralWidget(tmp_qt.QtWidgets.QWidget())
  if with_menus:
    tmp_menubar = tmp_window.menuBar()
    tmp_window.menudict = {
        "": tmp_menubar,
        "Display": tmp_menubar.addMenu("Display"),
    }
  tmp_window.show()
  monkeypatch.setattr(pymol.gui, "get_qtwindow", lambda: tmp_window)
  return tmp_window


@pytest.fixture
def main_window(monkeypatch: pytest.MonkeyPatch):
  """A main window with PyMOL's Display menu, returned as PyMOL's window.

  Args:
    monkeypatch: Replaces ``pymol.gui.get_qtwindow`` for one test.

  Yields:
    The main window; it is closed and deleted after the test.
  """
  tmp_window = _make_window(monkeypatch, with_menus=True)
  yield tmp_window
  tmp_window.close()
  tmp_window.deleteLater()


@pytest.fixture
def bare_main_window(monkeypatch: pytest.MonkeyPatch):
  """A main window without ``menudict``, returned as PyMOL's window.

  Args:
    monkeypatch: Replaces ``pymol.gui.get_qtwindow`` for one test.

  Yields:
    The main window; it is closed and deleted after the test.
  """
  tmp_window = _make_window(monkeypatch, with_menus=False)
  yield tmp_window
  tmp_window.close()
  tmp_window.deleteLater()
