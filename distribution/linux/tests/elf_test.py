"""elf reads the libraries an ELF file needs and the glibc versions it uses.

The fixture is a minimal 64-bit ELF file built here: one PT_LOAD segment
covering the file at address 0, and one PT_DYNAMIC segment whose entries
name a string table holding the needed libraries.
"""

import pathlib
import struct
import tempfile
import unittest

import elf


def _elf(needed: tuple[str, ...], extra: bytes = b"") -> bytes:
  """Builds a minimal 64-bit little-endian ELF file.

  Args:
    needed: The DT_NEEDED library names.
    extra: Bytes appended to the file, such as version strings.

  Returns:
    The file's bytes.
  """
  tmp_strings = b"\0"
  tmp_offsets = []
  for tmp_name in needed:
    tmp_offsets.append(len(tmp_strings))
    tmp_strings += tmp_name.encode() + b"\0"
  tmp_headers = 64 + 2 * 56
  tmp_strtab = tmp_headers
  tmp_dynamic = tmp_strtab + len(tmp_strings) + (-len(tmp_strings) % 8)
  tmp_entries = [(1, tmp_offset) for tmp_offset in tmp_offsets]
  tmp_entries += [(5, tmp_strtab), (0, 0)]
  tmp_dynamic_bytes = b"".join(
    struct.pack("<qQ", *tmp_entry) for tmp_entry in tmp_entries
  )
  tmp_size = tmp_dynamic + len(tmp_dynamic_bytes) + len(extra)
  tmp_header = (
    b"\x7fELF"
    + bytes([2, 1, 1, 0])
    + bytes(8)
    + struct.pack("<HHIQQQIHHHHHH", 3, 62, 1, 0, 64, 0, 0, 64, 56, 2, 64, 0, 0)
  )
  tmp_load = struct.pack("<IIQQQQQQ", 1, 5, 0, 0, 0, tmp_size, tmp_size, 4096)
  tmp_dyn = struct.pack(
    "<IIQQQQQQ",
    2,
    6,
    tmp_dynamic,
    tmp_dynamic,
    tmp_dynamic,
    len(tmp_dynamic_bytes),
    len(tmp_dynamic_bytes),
    8,
  )
  tmp_padding = bytes(tmp_dynamic - tmp_strtab - len(tmp_strings))
  return (
    tmp_header
    + tmp_load
    + tmp_dyn
    + tmp_strings
    + tmp_padding
    + tmp_dynamic_bytes
    + extra
  )


class ElfTest(unittest.TestCase):
  """Runs elf's readers on fixture files in a temporary folder."""

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

  def test_needed_libraries(self) -> None:
    """DT_NEEDED entries come back in order."""
    tmp_path = self._file("_cmd.so", _elf(("libgomp.so.1", "libGL.so.1")))

    self.assertEqual(
      elf.needed_libraries(tmp_path), ["libgomp.so.1", "libGL.so.1"]
    )

  def test_glibc_versions(self) -> None:
    """The GLIBC_x.y version names the file uses."""
    tmp_path = self._file(
      "lib.so", _elf((), b"GLIBC_2.17\0GLIBC_2.28\0GLIBC_PRIVATE\0")
    )

    self.assertEqual(elf.glibc_versions(tmp_path), {(2, 17), (2, 28)})

  def test_version_names(self) -> None:
    """Full names with the prefix, not symbols or other libraries' versions."""
    tmp_path = self._file(
      "_cmd.so",
      _elf(
        (),
        b"GOMP_4.0\0GOMP_5.0.1\0GOMP_parallel\0GOMP_PLUGIN_1.0\0OMP_1.0\0",
      ),
    )

    self.assertEqual(
      elf.version_names(tmp_path, "GOMP_"), {"GOMP_4.0", "GOMP_5.0.1"}
    )

  def test_not_elf(self) -> None:
    """Text and Mach-O files are no ELF files."""
    tmp_text = self._file("x.py", b"print()\n")
    tmp_macho = self._file("y.so", struct.pack("<I", 0xFEEDFACF) + bytes(60))

    self.assertFalse(elf.is_elf(tmp_text))
    self.assertFalse(elf.is_elf(tmp_macho))
    self.assertTrue(elf.is_elf(self._file("z.so", _elf(()))))


if __name__ == "__main__":
  unittest.main()
