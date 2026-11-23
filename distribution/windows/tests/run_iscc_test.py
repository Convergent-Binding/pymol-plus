"""run_iscc copies the app to a short folder that ISCC can read.

Inside Bazel's output tree the app's deepest files (PySide6's QML images)
pass Windows' classic 260-character path limit, which ISCC may not handle.
"""

import pathlib
import sys
import tempfile
import unittest

import run_iscc


class ShortCopyTest(unittest.TestCase):
  """Copies a folder whose files lie deeper than 260 characters."""

  def test_deep_files_copied_to_a_short_path(self) -> None:
    """Every file arrives, at a path well below the limit."""
    with tempfile.TemporaryDirectory() as tmp_folder:
      tmp_app = pathlib.Path(tmp_folder, "a" * 60, "b" * 60, "c" * 60, "app")
      tmp_relative = pathlib.Path("d" * 60, "e" * 60, "file.png")
      tmp_source = run_iscc.long_path(tmp_app / tmp_relative)
      tmp_source.parent.mkdir(parents=True)
      tmp_source.write_bytes(b"png")
      self.assertGreater(len(str(tmp_app / tmp_relative)), 260)

      with run_iscc.short_copy(tmp_app) as tmp_copy:
        tmp_copied = tmp_copy / tmp_relative
        self.assertEqual(run_iscc.long_path(tmp_copied).read_bytes(), b"png")
        self.assertLess(len(str(tmp_copy)), 80)

      self.assertFalse(run_iscc.long_path(tmp_copy).exists())

  def test_long_path_prefix_on_windows(self) -> None:
    """Windows paths get the \\\\?\\ prefix; others stay as they are."""
    tmp_path = run_iscc.long_path(pathlib.Path("C:/x/y"))
    if sys.platform == "win32":
      self.assertTrue(str(tmp_path).startswith("\\\\?\\"))
    else:
      self.assertEqual(tmp_path, pathlib.Path("C:/x/y"))


if __name__ == "__main__":
  unittest.main()
