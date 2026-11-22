"""make_dmg stages a writable copy of the signed app for create-dmg.

Bazel leaves its outputs read-only, and create-dmg copies its source folder
into the disk image it then writes to, so a read-only app fails there with
"Permission denied".
"""

import os
import pathlib
import stat
import sys
import tempfile
import unittest

import make_dmg


class StageAppTest(unittest.TestCase):
  """Stages a read-only fake app."""

  def setUp(self) -> None:
    """Writes a read-only app with an executable launcher."""
    self._dir = tempfile.TemporaryDirectory()
    self.root = pathlib.Path(self._dir.name)
    self.app = self.root / "signed" / "PyMOL-Open-Source.app"
    tmp_launcher = self.app / "Contents" / "MacOS" / "PyMOL-Open-Source"
    tmp_launcher.parent.mkdir(parents=True)
    tmp_launcher.write_bytes(b"launcher")
    tmp_launcher.chmod(0o555)
    (self.app / "Contents" / "Info.plist").write_text("<plist/>")
    for tmp_path in [*self.app.rglob("*"), self.app]:
      tmp_mode = tmp_path.stat().st_mode
      tmp_path.chmod(tmp_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))

  def tearDown(self) -> None:
    """Makes everything writable again and removes the temporary folder."""
    for tmp_path in self.root.rglob("*"):
      tmp_path.chmod(tmp_path.stat().st_mode | stat.S_IWUSR)
    self._dir.cleanup()

  def test_copy_is_writable_in_its_own_folder(self) -> None:
    """The copy sits alone in a staging folder and can be written to."""
    tmp_staged = make_dmg.stage_app(self.app, self.root / "staging")

    self.assertEqual(
      tmp_staged, self.root / "staging" / "PyMOL-Open-Source.app"
    )
    self.assertEqual(
      [tmp_path.name for tmp_path in (self.root / "staging").iterdir()],
      ["PyMOL-Open-Source.app"],
    )
    for tmp_path in [tmp_staged, *tmp_staged.rglob("*")]:
      with self.subTest(path=tmp_path.name):
        self.assertTrue(os.access(tmp_path, os.W_OK))

  @unittest.skipIf(sys.platform == "win32", "Windows has no executable bit")
  def test_executable_bits_kept(self) -> None:
    """The launcher stays executable."""
    tmp_staged = make_dmg.stage_app(self.app, self.root / "staging")

    tmp_launcher = tmp_staged / "Contents" / "MacOS" / "PyMOL-Open-Source"
    self.assertTrue(tmp_launcher.stat().st_mode & stat.S_IXUSR)


if __name__ == "__main__":
  unittest.main()
