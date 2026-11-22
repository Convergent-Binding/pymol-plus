"""The .tar.gz and .deb hold the app, the desktop files and the metadata.

They must match what build_packages.sh built with fpm, which the package
tests on eight distributions and the update over the latest release check:
the install folder, the command link, the desktop entry, icon, AppStream
metainfo and MIME types, the declared dependencies and the post-install
script. The .rpm is checked in CI with rpm -qpl and rpm -qpR.
"""

import io
import pathlib
import re
import stat
import sys
import tarfile
import unittest

import unpack_deb


_TARBALL, _DEB, _VERSION = sys.argv[1:4]
"""The tarball, the .deb and the app's version."""

_DEPENDS = sys.argv[4:]
"""The deb Depends list, in order."""

_INSTALL = f"opt/PyMOL-Open-Source-{_VERSION}"
"""The install folder, without the leading slash."""


def _tar_members(data: bytes) -> dict[str, tarfile.TarInfo]:
  """Lists a tar archive's members by normalized path.

  Args:
    data: The archive's bytes, compressed or not.

  Returns:
    Each member by its path without a leading "./" or "/".
  """
  with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tmp_tar:
    return {
      tmp_member.name.removeprefix("./").lstrip("/").rstrip("/"): tmp_member
      for tmp_member in tmp_tar.getmembers()
    }


def _tar_text(data: bytes, name: str) -> str:
  """Reads one text member of a tar archive.

  Args:
    data: The archive's bytes.
    name: The member's path without a leading "./".

  Returns:
    Its text.
  """
  with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tmp_tar:
    for tmp_member in tmp_tar.getmembers():
      if tmp_member.name.removeprefix("./").lstrip("/") == name:
        return tmp_tar.extractfile(tmp_member).read().decode("utf-8")
  raise KeyError(name)


class PackagesTest(unittest.TestCase):
  """Reads the built tarball and .deb."""

  @classmethod
  def setUpClass(cls) -> None:
    """Splits the .deb into its control and data archives."""
    tmp_members = unpack_deb._ar_members(pathlib.Path(_DEB).read_bytes())
    cls.control = next(
      tmp_data
      for tmp_name, tmp_data in tmp_members.items()
      if tmp_name.startswith("control.tar")
    )
    cls.data_name, cls.data = next(
      (tmp_name, tmp_data)
      for tmp_name, tmp_data in tmp_members.items()
      if tmp_name.startswith("data.tar")
    )

  def test_tarball_top_folder(self) -> None:
    """The tarball extracts into PyMOL-Open-Source-<version>/."""
    self.assertEqual(
      pathlib.Path(_TARBALL).name, f"PyMOL-Open-Source_v{_VERSION}.tar.gz"
    )
    tmp_members = _tar_members(pathlib.Path(_TARBALL).read_bytes())
    tmp_top = {tmp_name.split("/")[0] for tmp_name in tmp_members}
    self.assertEqual(tmp_top, {f"PyMOL-Open-Source-{_VERSION}"})
    tmp_launcher = tmp_members[
      f"PyMOL-Open-Source-{_VERSION}/PyMOL-Open-Source"
    ]
    self.assertTrue(tmp_launcher.mode & stat.S_IXUSR)

  def test_deb_control(self) -> None:
    """Name, version, architecture, dependencies and postinst as before."""
    self.assertEqual(
      pathlib.Path(_DEB).name, f"PyMOL-Open-Source_v{_VERSION}_amd64.deb"
    )
    tmp_control = _tar_text(self.control, "control")
    tmp_fields = dict(
      re.findall(r"^([A-Za-z-]+): (.*)$", tmp_control, re.MULTILINE)
    )
    self.assertEqual(tmp_fields["Package"], "pymol-open-source")
    self.assertEqual(tmp_fields["Version"], _VERSION)
    self.assertEqual(tmp_fields["Architecture"], "amd64")
    self.assertEqual(tmp_fields["Depends"], ", ".join(_DEPENDS))
    self.assertIn("rmdir", _tar_text(self.control, "postinst"))

  def test_deb_files(self) -> None:
    """The app, the command link and the desktop integration files."""
    tmp_members = _tar_members(self.data)
    for tmp_path in (
      f"{_INSTALL}/PyMOL-Open-Source",
      f"{_INSTALL}/manifest.json",
      "usr/share/applications/pymol-open-source.desktop",
      "usr/share/icons/hicolor/256x256/apps/pymol-open-source.png",
      "usr/share/metainfo/io.github.kullik01.pymol-open-source.metainfo.xml",
      "usr/share/mime/packages/pymol-open-source.xml",
    ):
      with self.subTest(path=tmp_path):
        self.assertIn(tmp_path, tmp_members)
    self.assertTrue(
      tmp_members[f"{_INSTALL}/PyMOL-Open-Source"].mode & stat.S_IXUSR
    )
    tmp_link = tmp_members["usr/bin/PyMOL-Open-Source"]
    self.assertTrue(tmp_link.issym())
    self.assertEqual(tmp_link.linkname, f"/{_INSTALL}/PyMOL-Open-Source")

  def test_deb_data_compressed(self) -> None:
    """The app goes into the .deb gzip-compressed, as fpm packed it."""
    self.assertEqual(self.data_name, "data.tar.gz")
    self.assertEqual(self.data[:2], b"\x1f\x8b")

  def test_desktop_entry_names_install_dir(self) -> None:
    """The desktop entry starts the installed app, not the template path."""
    tmp_entry = _tar_text(
      self.data, "usr/share/applications/pymol-open-source.desktop"
    )

    self.assertIn(f"/{_INSTALL}", tmp_entry)
    self.assertNotIn("/opt/pymol-open-source", tmp_entry)

  def test_metainfo_version_and_date(self) -> None:
    """The AppStream release names the version and a date, no placeholder."""
    tmp_metainfo = _tar_text(
      self.data,
      "usr/share/metainfo/io.github.kullik01.pymol-open-source.metainfo.xml",
    )

    self.assertIn(f'version="{_VERSION}"', tmp_metainfo)
    self.assertRegex(tmp_metainfo, r'date="\d{4}-\d{2}-\d{2}"')
    self.assertNotIn("@VERSION@", tmp_metainfo)
    self.assertNotIn("@DATE@", tmp_metainfo)


if __name__ == "__main__":
  unittest.main(argv=sys.argv[:1])
