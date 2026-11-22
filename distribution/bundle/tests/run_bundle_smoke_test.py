"""The app runs distribution/tests/smoke_test.py headless from a moved copy.

The bundle is copied to a new directory, so a reference into Bazel's output
tree (a symlink, an absolute path) fails here rather than after
installation, and runs with only the system folders on PATH, so it cannot
lean on a host Python.
"""

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest


_BUNDLE = pathlib.Path(sys.argv[1]).resolve()
"""The built app folder, as Bazel staged it."""

_SMOKE_TEST = pathlib.Path(sys.argv[2]).resolve()
"""distribution/tests/smoke_test.py."""

_WINDOWS = sys.platform == "win32"
"""Whether the test runs on Windows."""

_TIMEOUT_SECONDS = 240
"""Below Bazel's 300 seconds for a medium test, which include copying the
bundle, so a hang reports PyMOL's output instead of being killed silently."""


def _clean_environment(home: pathlib.Path) -> dict[str, str]:
  """Builds an environment with only what a desktop session always has.

  Args:
    home: The user's home and temporary folder.

  Returns:
    The environment variables.
  """
  if _WINDOWS:
    tmp_system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
    return {
      "PATH": rf"{tmp_system_root}\System32;{tmp_system_root}",
      "SYSTEMROOT": tmp_system_root,
      "USERPROFILE": str(home),
      "APPDATA": str(home / "AppData" / "Roaming"),
      "LOCALAPPDATA": str(home / "AppData" / "Local"),
      "TEMP": str(home),
      "TMP": str(home),
    }
  return {"PATH": "/usr/bin:/bin", "HOME": str(home), "TMPDIR": str(home)}


_TEXT_SUFFIXES = {".cfg", ".json", ".pth", ".py", ".txt"}
"""Text files that could tie the app to the folder it was built in."""


def _output_base(bundle: pathlib.Path) -> str:
  """Finds the Bazel output base a bundle was built in.

  Args:
    bundle: The bundle's path in the runfiles, resolved.

  Returns:
    The part of the path above Bazel's execroot.
  """
  tmp_parts = bundle.parts
  return (
    str(pathlib.Path(*tmp_parts[: tmp_parts.index("execroot")]))
    if "execroot" in tmp_parts
    else str(bundle)
  )


class BundleSmokeTest(unittest.TestCase):
  """Checks the built bundle, then runs a moved copy."""

  def test_bundle_holds_no_build_paths(self) -> None:
    """No bytecode, and no text file naming Bazel's output base.

    The compiled extensions are not searched: _cmd holds source paths of
    the wheel build in assert messages.
    """
    self.assertEqual(sorted(_BUNDLE.rglob("*.pyc")), [])
    tmp_output_base = _output_base(_BUNDLE).lower().encode("utf-8")
    for tmp_path in _BUNDLE.rglob("*"):
      if tmp_path.suffix in _TEXT_SUFFIXES and tmp_path.is_file():
        with self.subTest(path=tmp_path.relative_to(_BUNDLE).as_posix()):
          self.assertNotIn(tmp_output_base, tmp_path.read_bytes().lower())

  def test_moved_bundle_runs_headless(self) -> None:
    """The copy prints SMOKE TEST OK and exits 0."""
    with tempfile.TemporaryDirectory() as tmp_folder:
      tmp_app = pathlib.Path(tmp_folder, "moved", "PyMOL-Open-Source")
      shutil.copytree(_BUNDLE, tmp_app, symlinks=False)
      tmp_home = pathlib.Path(tmp_folder, "home")
      tmp_home.mkdir()
      tmp_launcher = tmp_app / (
        "PyMOL-Open-Source.exe" if _WINDOWS else "PyMOL-Open-Source"
      )

      tmp_result = subprocess.run(
        [str(tmp_launcher), "-cq", str(_SMOKE_TEST)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=_clean_environment(tmp_home),
        check=False,
        timeout=_TIMEOUT_SECONDS,
      )

    tmp_output = tmp_result.stdout.decode("utf-8", errors="replace")
    self.assertEqual(tmp_result.returncode, 0, tmp_output)
    self.assertIn("SMOKE TEST OK", tmp_output, tmp_output)
    print(tmp_output)


if __name__ == "__main__":
  unittest.main(argv=sys.argv[:1])
