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

import pe_imports


_LAUNCHER = pathlib.Path(sys.argv[1])
"""The launcher under test."""

_FAKE_PYTHON = pathlib.Path(sys.argv[2])
"""fake_python, which stands in for the runtime's interpreter."""

_WINDOWS = sys.platform == "win32"
"""Whether the test runs on Windows."""

_MACOS = sys.platform == "darwin"
"""Whether the test runs on macOS, where the launcher runs Python in-process."""

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

  @unittest.skipIf(_MACOS, "macOS runs Python in the launcher's process")
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

  @unittest.skipIf(_MACOS, "macOS runs Python in the launcher's process")
  def test_app_root_set(self) -> None:
    """PYMOL_APP_ROOT names the launcher's folder."""
    self._with_runtime()

    tmp_result = self._run()

    tmp_app_root = json.loads(tmp_result.stdout.decode("utf-8"))["app_root"]
    self.assertTrue(os.path.samefile(tmp_app_root, self.root), tmp_app_root)

  @unittest.skipIf(_MACOS, "macOS runs Python in the launcher's process")
  def test_exit_code_forwarded(self) -> None:
    """The launcher exits with Python's exit code."""
    self._with_runtime()

    self.assertEqual(self._run(exit_code=3).returncode, 3)

  @unittest.skipUnless(_WINDOWS, "a Windows import table")
  def test_no_cpp_runtime_import(self) -> None:
    """The launcher sits outside runtime/, so it links its C runtime in."""
    tmp_runtime_imports = [
      tmp_name
      for tmp_name in pe_imports.imported_dlls(_LAUNCHER)
      if pe_imports.RUNTIME_DLL.match(tmp_name)
    ]

    self.assertEqual(tmp_runtime_imports, [])

  def test_missing_runtime(self) -> None:
    """Without the runtime the launcher says so and exits 127."""
    tmp_result = self._run()

    self.assertEqual(tmp_result.returncode, 127)
    self.assertIn(
      "PyMOL-Open-Source: runtime not found:", tmp_result.stderr.decode("utf-8")
    )

  def _run_unloadable(self, launcher: pathlib.Path, runtime: pathlib.Path) -> str:
    """Runs a launcher beside a runtime whose libpython does not load.

    Args:
      launcher: Where the launcher is copied to.
      runtime: The runtime folder the launcher is to find.

    Returns:
      What the launcher wrote to stderr; it must have exited 127.
    """
    _copy_executable(_LAUNCHER, launcher)
    tmp_library = runtime / "lib" / "libpython3.13.dylib"
    tmp_library.parent.mkdir(parents=True)
    tmp_library.write_bytes(b"not a library")
    tmp_result = subprocess.run(
      [str(launcher)], capture_output=True, check=False, timeout=60
    )
    self.assertEqual(tmp_result.returncode, 127, tmp_result.stderr)
    return tmp_result.stderr.decode("utf-8")

  @unittest.skipUnless(_MACOS, "the macOS app layout")
  def test_app_layout_root(self) -> None:
    """Inside an .app the launcher looks in Contents/Resources/runtime."""
    tmp_contents = self.root / "PyMOL-Open-Source.app" / "Contents"
    tmp_stderr = self._run_unloadable(
      tmp_contents / "MacOS" / "PyMOL-Open-Source",
      tmp_contents / "Resources" / "runtime",
    )

    self.assertIn("runtime not found:", tmp_stderr)
    self.assertIn("Contents/Resources/runtime/lib/libpython", tmp_stderr)

  @unittest.skipUnless(_MACOS, "the macOS app layout")
  def test_flat_layout_root(self) -> None:
    """Outside an .app the launcher looks in runtime/ beside itself."""
    tmp_folder = self.root / "flat"
    tmp_stderr = self._run_unloadable(
      tmp_folder / "PyMOL-Open-Source", tmp_folder / "runtime"
    )

    self.assertIn(f"{tmp_folder.name}/runtime/lib/libpython", tmp_stderr)


if __name__ == "__main__":
  unittest.main(argv=sys.argv[:1])
