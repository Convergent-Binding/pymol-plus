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


_BUNDLE, _SMOKE_TEST = (pathlib.Path(arg).resolve() for arg in sys.argv[1:3])
_WINDOWS = sys.platform == "win32"
# Like the CI's timeout-minutes for the smoke test.
_TIMEOUT_SECONDS = 300


def _clean_environment(home: pathlib.Path) -> dict[str, str]:
  """Returns an environment with only what a desktop session always has."""
  if _WINDOWS:
    system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
    return {
        "PATH": rf"{system_root}\System32;{system_root}",
        "SYSTEMROOT": system_root,
        "USERPROFILE": str(home),
        "APPDATA": str(home / "AppData" / "Roaming"),
        "LOCALAPPDATA": str(home / "AppData" / "Local"),
        "TEMP": str(home),
        "TMP": str(home),
    }
  return {"PATH": "/usr/bin:/bin", "HOME": str(home), "TMPDIR": str(home)}


class BundleSmokeTest(unittest.TestCase):

  def test_moved_bundle_runs_headless(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      app = pathlib.Path(tmp, "moved", "PyMOL-Open-Source")
      shutil.copytree(_BUNDLE, app, symlinks=False)
      home = pathlib.Path(tmp, "home")
      home.mkdir()
      launcher = app / ("PyMOL-Open-Source.exe" if _WINDOWS else "PyMOL-Open-Source")

      result = subprocess.run(
          [str(launcher), "-cq", str(_SMOKE_TEST)],
          stdout=subprocess.PIPE,
          stderr=subprocess.STDOUT,
          env=_clean_environment(home),
          check=False,
          timeout=_TIMEOUT_SECONDS,
      )

    output = result.stdout.decode("utf-8", errors="replace")
    self.assertEqual(result.returncode, 0, output)
    self.assertIn("SMOKE TEST OK", output, output)
    print(output)


if __name__ == "__main__":
  unittest.main(argv=sys.argv[:1])
