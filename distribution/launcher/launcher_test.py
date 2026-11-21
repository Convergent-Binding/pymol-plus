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


_LAUNCHER, _FAKE_PYTHON = (pathlib.Path(arg) for arg in sys.argv[1:3])
_WINDOWS = sys.platform == "win32"
_LAUNCHER_NAME = "PyMOL-Open-Source.exe" if _WINDOWS else "PyMOL-Open-Source"
_RUNTIME_PYTHON = (
    pathlib.Path("runtime", "pythonw.exe")
    if _WINDOWS
    else pathlib.Path("runtime", "bin", "python3")
)


def _copy_executable(source: pathlib.Path, destination: pathlib.Path) -> None:
  destination.parent.mkdir(parents=True, exist_ok=True)
  shutil.copyfile(source, destination)
  destination.chmod(destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class LauncherTest(unittest.TestCase):

  def setUp(self) -> None:
    self._dir = tempfile.TemporaryDirectory()
    self.root = pathlib.Path(self._dir.name, "My App")
    self.launcher = self.root / _LAUNCHER_NAME
    _copy_executable(_LAUNCHER, self.launcher)

  def tearDown(self) -> None:
    self._dir.cleanup()

  def _run(self, *args: str, exit_code: int = 0) -> subprocess.CompletedProcess:
    env = dict(os.environ, FAKE_EXIT_CODE=str(exit_code))
    env.pop("PYMOL_APP_ROOT", None)
    return subprocess.run(
        [str(self.launcher), *args],
        capture_output=True,
        env=env,
        check=False,
        timeout=60,
    )

  def _with_runtime(self) -> None:
    _copy_executable(_FAKE_PYTHON, self.root / _RUNTIME_PYTHON)

  def test_arguments_pass_through(self) -> None:
    self._with_runtime()
    argument = "C:/Users/Jörg/My Files/x.pdb"

    result = self._run("-cq", argument)

    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual(
        json.loads(result.stdout.decode("utf-8"))["args"],
        ["-I", "-m", "pymol.startup_wrapper", "-cq", argument],
    )

  def test_app_root_set(self) -> None:
    self._with_runtime()

    result = self._run()

    app_root = json.loads(result.stdout.decode("utf-8"))["app_root"]
    self.assertTrue(os.path.samefile(app_root, self.root), app_root)

  def test_exit_code_forwarded(self) -> None:
    self._with_runtime()

    self.assertEqual(self._run(exit_code=3).returncode, 3)

  def test_missing_runtime(self) -> None:
    result = self._run()

    self.assertEqual(result.returncode, 127)
    self.assertIn("PyMOL-Open-Source: runtime not found:", result.stderr.decode("utf-8"))


if __name__ == "__main__":
  unittest.main(argv=sys.argv[:1])
