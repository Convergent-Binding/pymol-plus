# SPDX-License-Identifier: BSD-3-Clause
"""Tests of pymol3.gui that need neither a Qt binding nor a window."""

import os
import subprocess
import sys

import pytest

import pymol.gui
from pymol import plugins
from pymol3 import gui


def test_import_needs_no_qt_binding():
  """Importing pymol3.gui loads no Qt binding.

  Runs in a fresh interpreter, since other tests of the session load one.
  """
  tmp_environment = dict(os.environ)
  tmp_environment["PYTHONPATH"] = os.pathsep.join(sys.path)
  tmp_result = subprocess.run(
      [
          sys.executable,
          "-c",
          "import sys, pymol3.gui; "
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
    gui.add_dock_panel(object(), "T")
