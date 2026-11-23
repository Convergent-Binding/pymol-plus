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
  tmp_names_before = set(vars(pymol))
  try:
    exec("from pymol3 import ui", vars(pymol))
    assert pymol.gui is sys.modules["pymol.gui"]
  finally:
    for tmp_name in set(vars(pymol)) - tmp_names_before:
      delattr(pymol, tmp_name)
