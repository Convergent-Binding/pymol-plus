"""The launcher starts the bundled Python on PyMOL with its own arguments.

Each test lays out a bundle root with the launcher and fake_python in the
place of the runtime's interpreter; fake_python reports the arguments and
PYMOL_APP_ROOT it received as JSON.
"""

import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest


_LAUNCHER = pathlib.Path(sys.argv[1])
"""The launcher under test."""

_FAKE_PYTHON = pathlib.Path(sys.argv[2])
"""fake_python, which stands in for the runtime's interpreter."""

_WINDOWS = sys.platform == "win32"
"""Whether the test runs on Windows."""

_LAUNCHER_NAME = "PyMOL-Open-Source.exe" if _WINDOWS else "PyMOL-Open-Source"
"""The launcher's name in an app folder."""

_RUNTIME_PYTHON = (
  pathlib.Path("runtime", "pythonw.exe")
  if _WINDOWS
  else pathlib.Path("runtime", "bin", "python3")
)
"""Where the launcher looks for the interpreter, relative to its folder."""


def _copy_executable(source: pathlib.Path, destination: pathlib.Path) -> None:
  """Copies a program and makes the copy executable.

  Args:
    source: The program.
    destination: The copy; missing folders are created.
  """
  destination.parent.mkdir(parents=True, exist_ok=True)
  shutil.copyfile(source, destination)
  destination.chmod(
    destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
  )


class LauncherTest(unittest.TestCase):
  """Runs the launcher from a temporary app folder with a space in its name."""

  def setUp(self) -> None:
    """Copies the launcher into the app folder."""
    self._dir = tempfile.TemporaryDirectory()
    self.root = pathlib.Path(self._dir.name, "My App")
    self.launcher = self.root / _LAUNCHER_NAME
    _copy_executable(_LAUNCHER, self.launcher)

  def tearDown(self) -> None:
    """Removes the app folder."""
    self._dir.cleanup()

  def _run(self, *args: str, exit_code: int = 0) -> subprocess.CompletedProcess:
    """Runs the launcher.

    Args:
      *args: Its arguments.
      exit_code: The exit code fake_python is to return.

    Returns:
      The finished process, with its output.
    """
    tmp_env = dict(os.environ, FAKE_EXIT_CODE=str(exit_code))
    tmp_env.pop("PYMOL_APP_ROOT", None)
    return subprocess.run(
      [str(self.launcher), *args],
      capture_output=True,
      env=tmp_env,
      check=False,
      timeout=60,
    )

  def _with_runtime(self) -> None:
    """Puts fake_python where the launcher expects the runtime."""
    _copy_executable(_FAKE_PYTHON, self.root / _RUNTIME_PYTHON)

  def test_arguments_pass_through(self) -> None:
    """Arguments reach Python unchanged, after the startup module."""
    self._with_runtime()
    tmp_argument = "C:/Users/Jörg/My Files/x.pdb"

    tmp_result = self._run("-cq", tmp_argument)

    self.assertEqual(tmp_result.returncode, 0, tmp_result.stderr)
    self.assertEqual(
      json.loads(tmp_result.stdout.decode("utf-8"))["args"],
      ["-I", "-m", "pymol.startup_wrapper", "-cq", tmp_argument],
    )

  def test_app_root_set(self) -> None:
    """PYMOL_APP_ROOT names the launcher's folder."""
    self._with_runtime()

    tmp_result = self._run()

    tmp_app_root = json.loads(tmp_result.stdout.decode("utf-8"))["app_root"]
    self.assertTrue(os.path.samefile(tmp_app_root, self.root), tmp_app_root)

  def test_exit_code_forwarded(self) -> None:
    """The launcher exits with Python's exit code."""
    self._with_runtime()

    self.assertEqual(self._run(exit_code=3).returncode, 3)

  def test_missing_runtime(self) -> None:
    """Without the runtime the launcher says so and exits 127."""
    tmp_result = self._run()

    self.assertEqual(tmp_result.returncode, 127)
    self.assertIn(
      "PyMOL-Open-Source: runtime not found:", tmp_result.stderr.decode("utf-8")
    )


if __name__ == "__main__":
  unittest.main(argv=sys.argv[:1])
