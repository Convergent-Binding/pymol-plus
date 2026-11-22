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
  """Writes a text file, with its folders.

  Args:
    path: The file.
    text: Its contents.

  Returns:
    The path.
  """
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(text, encoding="utf-8")
  return path


class MergeWheelFilesTest(unittest.TestCase):
  """Runs merge_wheel_files.main on files in a temporary folder."""

  def setUp(self) -> None:
    """Creates the temporary folder."""
    self._dir = tempfile.TemporaryDirectory()
    self.root = pathlib.Path(self._dir.name)
    self.out = self.root / "out"

  def tearDown(self) -> None:
    """Removes the temporary folder."""
    self._dir.cleanup()

  def test_trees_merge(self) -> None:
    """Files of two wheels end up side by side in one tree."""
    tmp_first = _write(self.root / "a" / "PySide6" / "QtCore.py", "qt")
    tmp_second = _write(self.root / "b" / "shiboken6" / "__init__.py", "sb")

    tmp_status = merge_wheel_files.main(
      [
        "--out",
        str(self.out),
        str(tmp_first),
        "PySide6/QtCore.py",
        str(tmp_second),
        "shiboken6/__init__.py",
      ]
    )

    self.assertEqual(tmp_status, 0)
    self.assertEqual((self.out / "PySide6" / "QtCore.py").read_text(), "qt")
    self.assertEqual((self.out / "shiboken6" / "__init__.py").read_text(), "sb")

  def test_bytecode_skipped(self) -> None:
    """Bytecode a test wrote into a wheel extraction is left out."""
    tmp_source = _write(self.root / "a" / "pkg" / "__init__.py", "pkg")
    tmp_bytecode = _write(
      self.root / "a" / "pkg" / "__pycache__" / "__init__.cpython-313.pyc",
      "pyc",
    )

    tmp_status = merge_wheel_files.main(
      [
        "--out",
        str(self.out),
        str(tmp_source),
        "pkg/__init__.py",
        str(tmp_bytecode),
        "pkg/__pycache__/__init__.cpython-313.pyc",
      ]
    )

    self.assertEqual(tmp_status, 0)
    self.assertTrue((self.out / "pkg" / "__init__.py").is_file())
    self.assertFalse((self.out / "pkg" / "__pycache__").exists())

  def test_overlapping_paths_fail(self) -> None:
    """Two wheels shipping one path fail, naming the path."""
    tmp_first = _write(self.root / "a" / "common.py", "one")
    tmp_second = _write(self.root / "b" / "common.py", "two")

    tmp_stderr = io.StringIO()
    with contextlib.redirect_stderr(tmp_stderr):
      tmp_status = merge_wheel_files.main(
        [
          "--out",
          str(self.out),
          str(tmp_first),
          "common.py",
          str(tmp_second),
          "common.py",
        ]
      )

    self.assertNotEqual(tmp_status, 0)
    self.assertIn("common.py", tmp_stderr.getvalue())


if __name__ == "__main__":
  unittest.main()
