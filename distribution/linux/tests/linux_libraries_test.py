"""Every library the Linux app needs is bundled or declared, on glibc 2.28.

The package tests install on minimal distributions, where only declared
dependencies exist, so a library the app needs but neither ships nor
declares stops it there. RHEL and AlmaLinux 8 have glibc 2.28.

Qt's optional plugins (print support, SQL drivers and the like) are left out
of the library check: Qt skips a plugin whose libraries are missing. The
platform plugins, which draw the window, are checked.
"""

import pathlib
import sys
import unittest

import elf


_BUNDLE = pathlib.Path(sys.argv[1]).resolve()
"""The built app folder."""

_SYSTEM = set(sys.argv[2:])
"""The declared sonames and the base system's libraries."""

_MAXIMUM_GLIBC = (2, 28)
"""RHEL and AlmaLinux 8's glibc."""

_REQUIRED_PLUGIN_FOLDERS = ("platforms", "xcbglintegrations")
"""The Qt plugin folders whose plugins the app needs to show its window."""


def _binaries() -> list[pathlib.Path]:
  """Lists the app's ELF files.

  Returns:
    Their paths, sorted.
  """
  return sorted(
    tmp_path
    for tmp_path in _BUNDLE.rglob("*")
    if tmp_path.is_file() and elf.is_elf(tmp_path)
  )


def _optional(path: pathlib.Path) -> bool:
  """Tells whether a binary is a Qt plugin the app can do without.

  Args:
    path: A binary in the app.

  Returns:
    Whether it lies below Qt's plugins folder, outside the required ones.
  """
  tmp_parts = path.relative_to(_BUNDLE).parts
  if "plugins" not in tmp_parts:
    return False
  tmp_folder = tmp_parts[tmp_parts.index("plugins") + 1]
  return tmp_folder not in _REQUIRED_PLUGIN_FOLDERS


class LinuxLibrariesTest(unittest.TestCase):
  """Reads every ELF file of the app."""

  def test_the_app_has_its_libraries(self) -> None:
    """libgomp and libxcb-cursor are bundled."""
    tmp_names = {tmp_path.name for tmp_path in _binaries()}

    self.assertIn("libgomp.so.1", tmp_names)
    self.assertIn("libxcb-cursor.so.0", tmp_names)

  def test_every_needed_library_is_bundled_or_declared(self) -> None:
    """No required binary needs a library the system may lack."""
    tmp_bundled = {tmp_path.name for tmp_path in _BUNDLE.rglob("*")}
    tmp_missing = sorted(
      f"{tmp_path.relative_to(_BUNDLE)}: {tmp_name}"
      for tmp_path in _binaries()
      if not _optional(tmp_path)
      for tmp_name in elf.needed_libraries(tmp_path)
      if tmp_name not in tmp_bundled and tmp_name not in _SYSTEM
    )

    self.assertEqual(tmp_missing, [])

  def test_glibc_at_most_2_28(self) -> None:
    """No binary, optional plugins included, needs a newer glibc."""
    tmp_newer = sorted(
      f"{tmp_path.relative_to(_BUNDLE)}: {max(tmp_versions)}"
      for tmp_path in _binaries()
      if (tmp_versions := elf.glibc_versions(tmp_path))
      and max(tmp_versions) > _MAXIMUM_GLIBC
    )

    self.assertEqual(tmp_newer, [])


if __name__ == "__main__":
  unittest.main(argv=sys.argv[:1])
