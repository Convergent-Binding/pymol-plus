# SPDX-License-Identifier: BSD-3-Clause
"""Fixtures for testing the docked Scenes panel against a real PyMOL."""

import collections
import os

import pytest

import pymol.cmd
import pymol.gui
from pymol3 import app

from ..pymol3_ui import qt_binding


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_APPLICATION = []
"""The QApplication the fixtures made, kept alive for the whole session."""


@pytest.fixture(autouse=True)
def reset_pymol_and_switch(monkeypatch: pytest.MonkeyPatch, tmp_path):
  """Gives each test clean PyMOL state, isolated settings, and new GUI mode.

  Args:
    monkeypatch: Isolates ``pymol3.app`` state and settings store.
    tmp_path: Temporary folder holding the test settings INI file.

  Yields:
    None while the test runs, then reinitializes PyMOL.
  """
  tmp_qt = qt_binding.import_qt()
  tmp_store = str(tmp_path / "settings.ini")
  monkeypatch.setattr(app, "_state", app._State())
  monkeypatch.setattr(app, "FEATURE_MODULES", ())
  monkeypatch.setattr(
      app,
      "_open_settings",
      lambda: tmp_qt.QtCore.QSettings(
          tmp_store, tmp_qt.QtCore.QSettings.Format.IniFormat
      ),
  )
  monkeypatch.setenv(app.ENVIRONMENT_VARIABLE, app.NEW)
  pymol.cmd.reinitialize()
  yield
  pymol.cmd.reinitialize()


@pytest.fixture
def scene_window(monkeypatch: pytest.MonkeyPatch):
  """A shown QMainWindow wired to ``pymol.cmd`` and ``pymol.gui``.

  Args:
    monkeypatch: Makes ``pymol.gui.get_qtwindow`` return this window.

  Yields:
    The main window, closed and scheduled for deletion afterwards.
  """
  tmp_qt = qt_binding.import_qt()
  if tmp_qt.QtWidgets.QApplication.instance() is None:
    _APPLICATION.append(tmp_qt.QtWidgets.QApplication(["pymol3-tests"]))
  tmp_window = tmp_qt.QtWidgets.QMainWindow()
  tmp_window.setCentralWidget(tmp_qt.QtWidgets.QWidget())
  tmp_menubar = tmp_window.menuBar()
  tmp_window.menudict = {
      "": tmp_menubar,
      "Display": tmp_menubar.addMenu("Display"),
      "Scene": tmp_menubar.addMenu("Scene"),
  }
  tmp_window.cmd = pymol.cmd
  tmp_window.setting_callbacks = collections.defaultdict(list)
  tmp_window.resize(900, 600)
  tmp_window.show()
  monkeypatch.setattr(pymol.gui, "get_qtwindow", lambda: tmp_window)
  yield tmp_window
  tmp_window.close()
  tmp_window.deleteLater()
