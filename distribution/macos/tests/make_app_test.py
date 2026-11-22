"""make_app wraps the app folder into PyMOL-Open-Source.app.

The app folder is a small fake with the launcher at its top, a runtime and
one universal binary; the test checks the bundle's layout, its Info.plist
and that universal binaries are cut down to the target's architecture.
"""

import pathlib
import plistlib
import struct
import sys
import tempfile
import unittest

import macho
import make_app


def _image(cpu: int) -> bytes:
  """Builds a minimal 64-bit Mach-O image without load commands.

  Args:
    cpu: The CPU type.

  Returns:
    The image's bytes.
  """
  return struct.pack("<IIIIIIII", 0xFEEDFACF, cpu, 0, 6, 0, 0, 0, 0)


def _universal(*images: bytes) -> bytes:
  """Builds a universal file from Mach-O images.

  Args:
    *images: The slices, arm64 or x86_64.

  Returns:
    The file's bytes.
  """
  tmp_header = struct.pack(">II", 0xCAFEBABE, len(images))
  tmp_body = b""
  tmp_offset = 4096
  for tmp_image in images:
    tmp_cpu = struct.unpack_from("<I", tmp_image, 4)[0]
    tmp_header += struct.pack(">IIIII", tmp_cpu, 0, tmp_offset, len(tmp_image), 12)
    tmp_body += tmp_image.ljust(4096, b"\0")
    tmp_offset += 4096
  return tmp_header.ljust(4096, b"\0") + tmp_body


class MakeAppTest(unittest.TestCase):
  """Runs make_app.main on a fake app folder."""

  def setUp(self) -> None:
    """Writes the fake app folder, Info.plist and icon."""
    self._dir = tempfile.TemporaryDirectory()
    self.root = pathlib.Path(self._dir.name)
    self.app = self.root / "PyMOL-Open-Source"
    (self.app / "runtime" / "lib").mkdir(parents=True)
    (self.app / "PyMOL-Open-Source").write_bytes(_image(0x0100000C))
    (self.app / "runtime" / "lib" / "QtCore.so").write_bytes(
      _universal(_image(0x01000007), _image(0x0100000C))
    )
    (self.app / "manifest.json").write_text("{}", encoding="utf-8")
    self.plist = self.root / "Info.plist"
    with open(self.plist, "wb") as tmp_handle:
      plistlib.dump(
        {
          "CFBundleExecutable": "PyMOL-Open-Source",
          "CFBundleIdentifier": "io.github.kullik01.pymol-open-source",
          "LSMinimumSystemVersion": "12.0",
        },
        tmp_handle,
      )
    self.icon = self.root / "icon.icns"
    self.icon.write_bytes(b"icns")
    self.out = self.root / "out" / "PyMOL-Open-Source.app"

  def tearDown(self) -> None:
    """Removes the temporary folder."""
    self._dir.cleanup()

  def _make(self) -> pathlib.Path:
    """Builds the .app for arm64.

    Returns:
      Its Contents folder.
    """
    tmp_status = make_app.main([
      "--app",
      str(self.app),
      "--info-plist",
      str(self.plist),
      "--icon",
      str(self.icon),
      "--version",
      "3.2.0.3+1",
      "--arch",
      "arm64",
      "--out",
      str(self.out),
    ])
    self.assertEqual(tmp_status, 0)
    return self.out / "Contents"

  def test_layout(self) -> None:
    """Launcher in MacOS/, app folder and icon in Resources/, Info.plist."""
    tmp_contents = self._make()

    for tmp_path in (
      tmp_contents / "MacOS" / "PyMOL-Open-Source",
      tmp_contents / "Resources" / "runtime" / "lib" / "QtCore.so",
      tmp_contents / "Resources" / "manifest.json",
      tmp_contents / "Resources" / "icon.icns",
      tmp_contents / "Info.plist",
      tmp_contents / "PkgInfo",
    ):
      self.assertTrue(tmp_path.is_file(), tmp_path)
    self.assertFalse((tmp_contents / "Resources" / "PyMOL-Open-Source").exists())

  def test_plist_version_stamped_and_keys_kept(self) -> None:
    """The version is set; every other key stays as Info.plist has it."""
    with open(self._make() / "Info.plist", "rb") as tmp_handle:
      tmp_plist = plistlib.load(tmp_handle)

    self.assertEqual(tmp_plist["CFBundleShortVersionString"], "3.2.0.3+1")
    self.assertEqual(tmp_plist["CFBundleVersion"], "3.2.0.3+1")
    self.assertEqual(
      tmp_plist["CFBundleIdentifier"], "io.github.kullik01.pymol-open-source"
    )
    self.assertEqual(tmp_plist["LSMinimumSystemVersion"], "12.0")

  def test_universal_files_thinned(self) -> None:
    """Universal binaries keep only the target's architecture."""
    tmp_qt = self._make() / "Resources" / "runtime" / "lib" / "QtCore.so"

    self.assertEqual(macho.architectures(tmp_qt), ["arm64"])

  @unittest.skipIf(sys.platform == "win32", "Windows has no executable bit")
  def test_launcher_is_executable(self) -> None:
    """The bundle's executable keeps its executable mode."""
    tmp_launcher = self._make() / "MacOS" / "PyMOL-Open-Source"

    self.assertTrue(tmp_launcher.stat().st_mode & 0o100)


if __name__ == "__main__":
  unittest.main()
