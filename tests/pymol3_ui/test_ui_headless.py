# SPDX-License-Identifier: BSD-3-Clause
"""Tests of pymol3.ui that need neither a Qt binding nor a window."""

import os
import subprocess
import sys

import pytest

import pymol
import pymol.gui
from pymol import plugins
from pymol3 import ui

from . import qt_binding


def test_import_needs_no_qt_binding():
  """Importing pymol3.ui loads no Qt binding.

  Runs in a fresh interpreter, since other tests of the session load one.
  """
  tmp_environment = dict(os.environ)
  tmp_environment["PYTHONPATH"] = os.pathsep.join(sys.path)
  tmp_result = subprocess.run(
      [
          sys.executable,
          "-c",
          "import sys, pymol3.ui; "
          "sys.exit('pymol.Qt' in sys.modules)",
      ],
      env=tmp_environment,
      capture_output=True,
      text=True,
      check=False,
  )
  assert tmp_result.returncode == 0, tmp_result.stderr


def test_without_qt_window_raises_qt_not_available(
    monkeypatch: pytest.MonkeyPatch,
):
  """Without PyMOL's Qt window the call raises QtNotAvailableError.

  Args:
    monkeypatch: Makes PyMOL report no Qt window.
  """
  monkeypatch.setattr(pymol.gui, "get_qtwindow", lambda: None)
  with pytest.raises(plugins.QtNotAvailableError):
    ui.add_dock_panel(object(), "T")


def test_import_in_pymol_namespace_keeps_pymol_gui():
  """``from pymol3 import ui`` in PyMOL's script namespace keeps pymol.gui.

  PyMOL runs scripts and Python typed at ``PyMOL>`` in the ``pymol``
  module's namespace, so the import must not replace a name PyMOL's own
  code reads there.
  """
  tmp_namespace = vars(pymol)
  tmp_before = dict(tmp_namespace)
  try:
    exec("from pymol3 import ui", tmp_namespace)
    tmp_replaced = [
        tmp_name
        for tmp_name, tmp_value in tmp_before.items()
        if tmp_namespace.get(tmp_name) is not tmp_value
    ]
    assert tmp_replaced == []
    assert pymol.gui is sys.modules["pymol.gui"]
  finally:
    tmp_namespace.clear()
    tmp_namespace.update(tmp_before)


def test_get_dock_panel_without_qt_window_returns_none(
    monkeypatch: pytest.MonkeyPatch,
):
  """Without PyMOL's Qt window there is no panel to find.

  Args:
    monkeypatch: Makes PyMOL report no Qt window.
  """
  monkeypatch.setattr(pymol.gui, "get_qtwindow", lambda: None)
  assert ui.get_dock_panel("anything") is None


@pytest.mark.parametrize(
    ("value", "required"), [("1", True), ("0", False), ("", False)]
)
def test_require_qt_variable_counts_only_one(monkeypatch, value, required):
  """Only PYMOL3_TESTS_REQUIRE_QT=1 turns a missing binding into a failure.

  Args:
    monkeypatch: Sets the variable.
    value: The variable's value.
    required: Whether the value requires Qt.
  """
  monkeypatch.setenv(qt_binding.REQUIRE_QT_VARIABLE, value)
  assert qt_binding.qt_required() is required
