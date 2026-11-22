"""The portable ZIP holds the app folder's contents under the release name.

Users extract it anywhere and start PyMOL-Open-Source.exe at its top level,
as with the cx_Freeze app's ZIP; the website links the name the release job
checks (tests/check_release_assets.sh).
"""

import pathlib
import re
import sys
import unittest
import zipfile


_ZIP = pathlib.Path(sys.argv[1])
"""The portable ZIP under test."""

_VERSION = sys.argv[2]
"""The app's version from distribution/pyproject.toml."""


class PortableZipTest(unittest.TestCase):
  """Reads the ZIP's name and members."""

  def test_release_name(self) -> None:
    """The file carries the release name for the app's version."""
    self.assertEqual(
      _ZIP.name, f"PyMOL-Open-Source_v{_VERSION}_x64_portable.zip"
    )

  def test_app_at_the_root(self) -> None:
    """The launcher, the runtime and the manifest are top-level members."""
    with zipfile.ZipFile(_ZIP) as tmp_zip:
      tmp_names = set(tmp_zip.namelist())
    for tmp_name in (
      "PyMOL-Open-Source.exe",
      "runtime/pythonw.exe",
      "runtime/msvcp140.dll",
      "manifest.json",
      "licenses/README.txt",
    ):
      with self.subTest(member=tmp_name):
        self.assertIn(tmp_name, tmp_names)

  def test_no_bytecode_or_absolute_paths(self) -> None:
    """No .pyc, and no member path that is absolute or climbs out."""
    with zipfile.ZipFile(_ZIP) as tmp_zip:
      tmp_names = tmp_zip.namelist()
    self.assertEqual(
      [tmp_name for tmp_name in tmp_names if tmp_name.endswith(".pyc")], []
    )
    tmp_unsafe = re.compile(r"^(/|[A-Za-z]:)|(^|/)\.\.(/|$)")
    self.assertEqual(
      [tmp_name for tmp_name in tmp_names if tmp_unsafe.search(tmp_name)], []
    )


if __name__ == "__main__":
  unittest.main(argv=sys.argv[:1])
