"""Every library the Linux app loads is bundled or declared, on glibc 2.28.

The package tests install on minimal distributions, where only declared
dependencies exist, so a library the app loads but neither ships nor
declares stops it there. RHEL and AlmaLinux 8 have glibc 2.28.

The library check follows what the app loads: the runtime, _cmd and the
other Python extensions, the PySide6 modules PyMOL imports and the Qt
plugins that show its window, and every bundled library these need. The
rest of PySide6 (QML modules, the Wayland compositor, Designer, build tools,
Qt's optional plugins) is never loaded, so the libraries it would need are
not required.
"""

import os
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

_APP_QT_MODULES = frozenset(
  {"QtCore", "QtGui", "QtWidgets", "QtOpenGL", "QtOpenGLWidgets", "QtUiTools"}
)
"""The PySide6 modules PyMOL imports (pymol.Qt, and QtUiTools for forms)."""

_REQUIRED_PLUGINS = {
  "platforms": ("libqxcb", "libqwayland", "libqoffscreen"),
  "xcbglintegrations": ("",),
  "wayland-decoration-client": ("",),
  "wayland-graphics-integration-client": ("",),
  "wayland-shell-integration": ("",),
}
"""The Qt plugins that show the window, by folder and name prefix: X11,
Wayland, and the offscreen platform the smoke tests use."""


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


def _loaded_directly(path: pathlib.Path) -> bool:
  """Tells whether the app loads a binary itself, not only as a dependency.

  Args:
    path: A binary in the app.

  Returns:
    Whether it lies outside PySide6, or is a PySide6 module PyMOL imports or
    a Qt plugin the window needs.
  """
  tmp_parts = path.relative_to(_BUNDLE).parts
  if "PySide6" not in tmp_parts:
    return True
  tmp_inner = tmp_parts[tmp_parts.index("PySide6") + 1 :]
  if len(tmp_inner) == 1:
    return tmp_inner[0].split(".")[0] in _APP_QT_MODULES
  if "plugins" not in tmp_inner:
    return False
  tmp_folder = tmp_inner[tmp_inner.index("plugins") + 1]
  return any(
    tmp_inner[-1].startswith(tmp_prefix)
    for tmp_prefix in _REQUIRED_PLUGINS.get(tmp_folder, ())
  )


def _bundled(
  path: pathlib.Path, name: str, files: dict[str, list[pathlib.Path]]
) -> list[pathlib.Path]:
  """Finds the app's files a binary's needed library can resolve to.

  Args:
    path: The binary.
    name: Its DT_NEEDED entry, a soname or a path from $ORIGIN.
    files: The app's files by name.

  Returns:
    The matching files in the app; none if it ships no such library.
  """
  if name.startswith("$ORIGIN/"):
    tmp_path = pathlib.Path(
      os.path.normpath(path.parent / name.removeprefix("$ORIGIN/"))
    )
    return [tmp_path] if tmp_path.is_file() else []
  return files.get(name, [])


def _missing_libraries() -> list[str]:
  """Follows what the app loads and lists the libraries it cannot find.

  Returns:
    One "binary: library" line per library a loaded binary needs that the
    app does not ship and the system may lack, sorted.
  """
  tmp_files = {}
  for tmp_path in _BUNDLE.rglob("*"):
    if tmp_path.is_file():
      tmp_files.setdefault(tmp_path.name, []).append(tmp_path)
  tmp_pending = [
    tmp_path
    for tmp_path in _binaries()
    if _loaded_directly(tmp_path)
  ]
  tmp_seen = set(tmp_pending)
  tmp_missing = []
  while tmp_pending:
    tmp_path = tmp_pending.pop()
    for tmp_name in elf.needed_libraries(tmp_path):
      tmp_libraries = _bundled(tmp_path, tmp_name, tmp_files)
      if not tmp_libraries and tmp_name not in _SYSTEM:
        tmp_missing.append(f"{tmp_path.relative_to(_BUNDLE)}: {tmp_name}")
      for tmp_library in tmp_libraries:
        if tmp_library not in tmp_seen:
          tmp_seen.add(tmp_library)
          tmp_pending.append(tmp_library)
  return sorted(tmp_missing)


class LinuxLibrariesTest(unittest.TestCase):
  """Reads every ELF file of the app."""

  maxDiff = None
  """Shows every missing library, not only the first."""

  def test_the_app_has_its_libraries(self) -> None:
    """libgomp and libxcb-cursor are bundled."""
    tmp_names = {tmp_path.name for tmp_path in _binaries()}

    self.assertIn("libgomp.so.1", tmp_names)
    self.assertIn("libxcb-cursor.so.0", tmp_names)

  def test_every_loaded_library_is_bundled_or_declared(self) -> None:
    """Nothing the app loads needs a library the system may lack."""
    self.assertEqual(_missing_libraries(), [])

  def test_bundled_libgomp_has_every_version_used(self) -> None:
    """The bundled libgomp defines each GOMP_ version the binaries use.

    It comes from the build machine's GCC, which may be older than the
    compiler _cmd was linked with.
    """
    tmp_binaries = _binaries()
    tmp_gomp = next(
      tmp_path for tmp_path in tmp_binaries if tmp_path.name == "libgomp.so.1"
    )
    tmp_defined = elf.version_names(tmp_gomp, "GOMP_")
    tmp_users = [
      tmp_path
      for tmp_path in tmp_binaries
      if "libgomp.so.1" in elf.needed_libraries(tmp_path)
    ]
    tmp_missing = sorted(
      f"{tmp_path.relative_to(_BUNDLE)}: {tmp_name}"
      for tmp_path in tmp_users
      for tmp_name in elf.version_names(tmp_path, "GOMP_") - tmp_defined
    )

    self.assertTrue(tmp_users)
    self.assertEqual(tmp_missing, [])

  def test_glibc_at_most_2_28(self) -> None:
    """No binary, unloaded ones included, needs a newer glibc."""
    tmp_newer = sorted(
      f"{tmp_path.relative_to(_BUNDLE)}: {max(tmp_versions)}"
      for tmp_path in _binaries()
      if (tmp_versions := elf.glibc_versions(tmp_path))
      and max(tmp_versions) > _MAXIMUM_GLIBC
    )

    self.assertEqual(tmp_newer, [])


if __name__ == "__main__":
  unittest.main(argv=sys.argv[:1])
