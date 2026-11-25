# SPDX-License-Identifier: BSD-3-Clause
"""startup_wrapper turns --new-gui and --classic-gui into PYMOL_PLUS_GUI.

PyMOL itself must never receive the two options: it would take them for
files to open.
"""

import importlib.util
import os
import pathlib
import sys
import unittest
from unittest import mock


def _load_wrapper():
  """Loads startup_wrapper.py from its place beside this test.

  Returns:
    The module; loading it runs no start-up, which only ``__main__`` does.
  """
  tmp_path = pathlib.Path(__file__).with_name("pymol") / "startup_wrapper.py"
  tmp_spec = importlib.util.spec_from_file_location(
      "startup_wrapper", tmp_path
  )
  tmp_module = importlib.util.module_from_spec(tmp_spec)
  tmp_spec.loader.exec_module(tmp_module)
  return tmp_module


_WRAPPER = _load_wrapper()
"""The module under test."""

_VARIABLE = "PYMOL_PLUS_GUI"
"""The environment variable pymol3.app reads."""


class TakeGuiOptionTest(unittest.TestCase):
  """The GUI options leave the arguments and set the variable."""

  def setUp(self) -> None:
    """Runs each test with no PYMOL_PLUS_GUI in the environment."""
    tmp_patch = mock.patch.dict(os.environ)
    tmp_patch.start()
    self.addCleanup(tmp_patch.stop)
    os.environ.pop(_VARIABLE, None)

  def test_new_gui(self) -> None:
    """--new-gui sets the new style and is removed."""
    tmp_arguments = _WRAPPER._take_gui_option(
        ["pymol", "--new-gui", "1abc.pdb"]
    )
    self.assertEqual(tmp_arguments, ["pymol", "1abc.pdb"])
    self.assertEqual(os.environ[_VARIABLE], "new")

  def test_classic_gui(self) -> None:
    """--classic-gui sets the classic style and is removed."""
    tmp_arguments = _WRAPPER._take_gui_option(["pymol", "--classic-gui"])
    self.assertEqual(tmp_arguments, ["pymol"])
    self.assertEqual(os.environ[_VARIABLE], "classic")

  def test_last_option_wins(self) -> None:
    """With both options, the last one decides; neither reaches PyMOL."""
    tmp_arguments = _WRAPPER._take_gui_option(
        ["pymol", "--new-gui", "-q", "--classic-gui"]
    )
    self.assertEqual(tmp_arguments, ["pymol", "-q"])
    self.assertEqual(os.environ[_VARIABLE], "classic")

  def test_option_overrides_environment(self) -> None:
    """The command line wins over a variable the user set."""
    os.environ[_VARIABLE] = "classic"
    _WRAPPER._take_gui_option(["pymol", "--new-gui"])
    self.assertEqual(os.environ[_VARIABLE], "new")

  def test_without_option(self) -> None:
    """Without an option the arguments and the environment stay as they are."""
    os.environ[_VARIABLE] = "new"
    tmp_arguments = _WRAPPER._take_gui_option(["pymol", "-q", "1abc.pdb"])
    self.assertEqual(tmp_arguments, ["pymol", "-q", "1abc.pdb"])
    self.assertEqual(os.environ[_VARIABLE], "new")

  def test_after_python_script_arguments(self) -> None:
    """Options after ``--`` belong to a script and stay untouched."""
    tmp_arguments = _WRAPPER._take_gui_option(
        ["pymol", "script.py", "--", "--new-gui"]
    )
    self.assertEqual(tmp_arguments, ["pymol", "script.py", "--", "--new-gui"])
    self.assertNotIn(_VARIABLE, os.environ)


if __name__ == "__main__":
  sys.exit(unittest.main())
