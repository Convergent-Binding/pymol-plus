# SPDX-License-Identifier: BSD-3-Clause
"""Fixtures that give each test a fresh switch, store and main window.

The stored choice goes to an INI file in the test's temporary folder, so
the tests never read or change the app's real settings. Qt runs on its
``offscreen`` platform, so no window opens on a real display.
"""

import os

import pytest

from pymol3 import app

from ..pymol3_ui import qt_binding

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_APPLICATION = []
"""The QApplication the fixtures made, kept alive for the whole session."""


@pytest.fixture(autouse=True)
def fresh_switch(monkeypatch: pytest.MonkeyPatch, tmp_path):
  """Gives the test a switch with no style, features or stored choice.

  Args:
    monkeypatch: Replaces the module's state and settings store.
    tmp_path: The test's temporary folder, which holds the store.
  """
  tmp_qt = qt_binding.import_qt()
  tmp_path_to_store = str(tmp_path / "settings.ini")
  monkeypatch.setattr(app, "_state", app._State())
  monkeypatch.setattr(
      app,
      "_open_settings",
      lambda: tmp_qt.QtCore.QSettings(
          tmp_path_to_store, tmp_qt.QtCore.QSettings.Format.IniFormat
      ),
  )
  monkeypatch.delenv(app.ENVIRONMENT_VARIABLE, raising=False)


def _make_window(with_menus: bool):
  """Makes a shown main window, with PyMOL's Display menu if asked.

  Args:
    with_menus: Whether the window gets PyMOL's ``menudict`` with a
      Display menu, as PyMOL's own window has.

  Returns:
    The main window.
  """
  tmp_qt = qt_binding.import_qt()
  if tmp_qt.QtWidgets.QApplication.instance() is None:
    # PyQt deletes an application nothing refers to; keep it for the session.
    _APPLICATION.append(tmp_qt.QtWidgets.QApplication(["pymol3-tests"]))
  tmp_window = tmp_qt.QtWidgets.QMainWindow()
  tmp_window.setCentralWidget(tmp_qt.QtWidgets.QWidget())
  if with_menus:
    tmp_menubar = tmp_window.menuBar()
    tmp_window.menudict = {
        "": tmp_menubar,
        "Display": tmp_menubar.addMenu("Display"),
    }
  tmp_window.show()
  return tmp_window


@pytest.fixture
def main_window():
  """A main window with PyMOL's Display menu.

  Yields:
    The main window; it is closed and deleted after the test.
  """
  tmp_window = _make_window(with_menus=True)
  yield tmp_window
  tmp_window.close()
  tmp_window.deleteLater()


@pytest.fixture
def bare_main_window():
  """A main window without ``menudict``.

  Yields:
    The main window; it is closed and deleted after the test.
  """
  tmp_window = _make_window(with_menus=False)
  yield tmp_window
  tmp_window.close()
  tmp_window.deleteLater()
