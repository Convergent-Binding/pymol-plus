"""macho reads Mach-O architectures and minimum macOS, and thins universal files.

The fixtures are built here: minimal 64-bit Mach-O images with one load
command each, and universal (fat) files holding two of them.
"""

import pathlib
import struct
import tempfile
import unittest

import macho


_ARM64 = 0x0100000C
"""CPU_TYPE_ARM64."""

_X86_64 = 0x01000007
"""CPU_TYPE_X86_64."""


def _thin(cpu: int, minimum: tuple[int, int], legacy: bool = False) -> bytes:
  """Builds a 64-bit Mach-O image with one minimum-version load command.

  Args:
    cpu: The CPU type.
    minimum: The minimum macOS, (major, minor).
    legacy: Whether to use LC_VERSION_MIN_MACOSX instead of LC_BUILD_VERSION.

  Returns:
    The image's bytes.
  """
  tmp_version = (minimum[0] << 16) | (minimum[1] << 8)
  if legacy:
    tmp_command = struct.pack("<IIII", 0x24, 16, tmp_version, tmp_version)
  else:
    tmp_command = struct.pack("<IIIIII", 0x32, 24, 1, tmp_version, 0, 0)
  tmp_header = struct.pack(
    "<IIIIIIII", 0xFEEDFACF, cpu, 0, 2, 1, len(tmp_command), 0, 0
  )
  return tmp_header + tmp_command


def _fat(*images: tuple[int, bytes]) -> bytes:
  """Builds a universal file from (CPU type, image) pairs.

  Args:
    *images: The slices.

  Returns:
    The file's bytes, each slice aligned to 4096 bytes.
  """
  tmp_header = struct.pack(">II", 0xCAFEBABE, len(images))
  tmp_offset = 4096
  tmp_body = b""
  for tmp_cpu, tmp_image in images:
    tmp_header += struct.pack(
      ">IIIII", tmp_cpu, 0, tmp_offset, len(tmp_image), 12
    )
    tmp_body += tmp_image + b"\0" * (-len(tmp_image) % 4096)
    tmp_offset += len(tmp_image) + (-len(tmp_image) % 4096)
  return tmp_header + b"\0" * (4096 - len(tmp_header)) + tmp_body


class MachoTest(unittest.TestCase):
  """Runs macho's readers on fixture files in a temporary folder."""

  def setUp(self) -> None:
    """Creates the temporary folder."""
    self._dir = tempfile.TemporaryDirectory()
    self.root = pathlib.Path(self._dir.name)

  def tearDown(self) -> None:
    """Removes the temporary folder."""
    self._dir.cleanup()

  def _file(self, name: str, data: bytes) -> pathlib.Path:
    """Writes a fixture file.

    Args:
      name: Its name.
      data: Its bytes.

    Returns:
      Its path.
    """
    tmp_path = self.root / name
    tmp_path.write_bytes(data)
    return tmp_path

  def test_thin_extracts_slice(self) -> None:
    """The arm64 slice of a universal file comes out byte for byte."""
    tmp_arm = _thin(_ARM64, (11, 0))
    tmp_path = self._file(
      "QtCore", _fat((_X86_64, _thin(_X86_64, (10, 15))), (_ARM64, tmp_arm))
    )

    self.assertEqual(macho.thin(tmp_path, "arm64"), tmp_arm)

  def test_thin_keeps_thin_file(self) -> None:
    """A single-architecture file stays as it is."""
    tmp_data = _thin(_X86_64, (10, 15))
    tmp_path = self._file("python3.13", tmp_data)

    self.assertEqual(macho.thin(tmp_path, "x86_64"), tmp_data)

  def test_thin_missing_architecture_fails(self) -> None:
    """Thinning to an architecture the file lacks raises ValueError."""
    tmp_path = self._file("lib.so", _thin(_X86_64, (10, 15)))

    with self.assertRaises(ValueError):
      macho.thin(tmp_path, "arm64")

  def test_minimum_from_build_version(self) -> None:
    """LC_BUILD_VERSION gives the minimum macOS."""
    tmp_path = self._file("a.so", _thin(_ARM64, (14, 0)))

    self.assertEqual(macho.minimum_macos(tmp_path), (14, 0))

  def test_minimum_from_version_min(self) -> None:
    """LC_VERSION_MIN_MACOSX gives it for older binaries."""
    tmp_path = self._file("b.so", _thin(_X86_64, (10, 9), legacy=True))

    self.assertEqual(macho.minimum_macos(tmp_path), (10, 9))

  def test_minimum_of_fat_file_is_the_highest(self) -> None:
    """A universal file needs what its most demanding slice needs."""
    tmp_path = self._file(
      "c.so",
      _fat(
        (_X86_64, _thin(_X86_64, (10, 15))), (_ARM64, _thin(_ARM64, (12, 0)))
      ),
    )

    self.assertEqual(macho.minimum_macos(tmp_path), (12, 0))

  def test_architectures_of_fat_file(self) -> None:
    """A universal file lists each slice's architecture."""
    tmp_path = self._file(
      "d.so",
      _fat(
        (_X86_64, _thin(_X86_64, (10, 15))), (_ARM64, _thin(_ARM64, (11, 0)))
      ),
    )

    self.assertEqual(macho.architectures(tmp_path), ["x86_64", "arm64"])

  def test_other_files_are_not_macho(self) -> None:
    """Text and a Java class file (also 0xCAFEBABE) are no Mach-O."""
    tmp_text = self._file("x.py", b"print()\n")
    tmp_class = self._file("X.class", struct.pack(">IHH", 0xCAFEBABE, 0, 65))

    self.assertFalse(macho.is_macho(tmp_text))
    self.assertFalse(macho.is_macho(tmp_class))


if __name__ == "__main__":
  unittest.main()
