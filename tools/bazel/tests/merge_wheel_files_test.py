"""merge_wheel_files copies wheels' files into one tree and refuses collisions.

Two wheels that both ship the same path would otherwise overwrite each other
silently, and which copy wins would depend on the order of the inputs.
"""

import contextlib
import io
import pathlib
import tempfile
import unittest

import merge_wheel_files


def _write(path: pathlib.Path, text: str) -> pathlib.Path:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(text, encoding="utf-8")
  return path


class MergeWheelFilesTest(unittest.TestCase):

  def setUp(self) -> None:
    self._dir = tempfile.TemporaryDirectory()
    self.root = pathlib.Path(self._dir.name)
    self.out = self.root / "out"

  def tearDown(self) -> None:
    self._dir.cleanup()

  def test_trees_merge(self) -> None:
    first = _write(self.root / "a" / "PySide6" / "QtCore.py", "qt")
    second = _write(self.root / "b" / "shiboken6" / "__init__.py", "sb")

    status = merge_wheel_files.main([
        "--out", str(self.out),
        str(first), "PySide6/QtCore.py",
        str(second), "shiboken6/__init__.py",
    ])

    self.assertEqual(status, 0)
    self.assertEqual((self.out / "PySide6" / "QtCore.py").read_text(), "qt")
    self.assertEqual((self.out / "shiboken6" / "__init__.py").read_text(), "sb")

  def test_overlapping_paths_fail(self) -> None:
    first = _write(self.root / "a" / "common.py", "one")
    second = _write(self.root / "b" / "common.py", "two")

    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
      status = merge_wheel_files.main([
          "--out", str(self.out),
          str(first), "common.py",
          str(second), "common.py",
      ])

    self.assertNotEqual(status, 0)
    self.assertIn("common.py", stderr.getvalue())


if __name__ == "__main__":
  unittest.main()
