"""Reads the DLL names a Windows executable or DLL imports.

A small reader of the PE import directory with the standard library, so the
app's tests need no PE package. Delay-loaded imports are not listed; none of
the app's binaries uses them for the C++ runtime.
"""

import pathlib
import re
import struct


RUNTIME_DLL = re.compile(
  r"^(vcruntime140(_\d+)?|msvcp140(_\w+)?|concrt140|vcomp140|vccorlib140"
  r"|vcamp140)\.dll$",
  re.IGNORECASE,
)
"""The Microsoft C++ and OpenMP runtime DLLs an app must ship itself."""

_PE32_PLUS = 0x20B
"""The optional header magic of 64-bit images."""


class PeError(Exception):
  """The file is not a PE image this reader understands."""


def _file_offset(sections: list[tuple[int, int, int]], rva: int) -> int:
  """Maps a relative virtual address to a file offset.

  Args:
    sections: Each section's virtual address, virtual size and raw offset.
    rva: The address.

  Returns:
    The file offset.

  Raises:
    PeError: No section holds the address.
  """
  for tmp_address, tmp_size, tmp_raw in sections:
    if tmp_address <= rva < tmp_address + max(tmp_size, 1):
      return rva - tmp_address + tmp_raw
  raise PeError(f"address {rva:#x} is in no section")


def imported_dlls(path: pathlib.Path) -> list[str]:
  """Lists the DLLs a PE image imports.

  Args:
    path: An .exe, .dll or .pyd file.

  Returns:
    The imported DLL names, as the image spells them.

  Raises:
    PeError: The file is not a PE image.
  """
  tmp_data = path.read_bytes()
  if tmp_data[:2] != b"MZ":
    raise PeError(f"{path} is not a PE image")
  tmp_pe = struct.unpack_from("<I", tmp_data, 0x3C)[0]
  if tmp_data[tmp_pe : tmp_pe + 4] != b"PE\0\0":
    raise PeError(f"{path} has no PE header")
  tmp_section_count = struct.unpack_from("<H", tmp_data, tmp_pe + 6)[0]
  tmp_optional_size = struct.unpack_from("<H", tmp_data, tmp_pe + 20)[0]
  tmp_optional = tmp_pe + 24
  tmp_magic = struct.unpack_from("<H", tmp_data, tmp_optional)[0]
  tmp_directories = tmp_optional + (112 if tmp_magic == _PE32_PLUS else 96)
  tmp_import_rva = struct.unpack_from("<I", tmp_data, tmp_directories + 8)[0]
  if tmp_import_rva == 0:
    return []
  tmp_sections = []
  for tmp_index in range(tmp_section_count):
    tmp_header = tmp_optional + tmp_optional_size + 40 * tmp_index
    tmp_size, tmp_address = struct.unpack_from("<II", tmp_data, tmp_header + 8)
    tmp_raw = struct.unpack_from("<I", tmp_data, tmp_header + 20)[0]
    tmp_sections.append((tmp_address, tmp_size, tmp_raw))
  tmp_names = []
  tmp_entry = _file_offset(tmp_sections, tmp_import_rva)
  while True:
    tmp_name_rva = struct.unpack_from("<I", tmp_data, tmp_entry + 12)[0]
    if tmp_name_rva == 0:
      return tmp_names
    tmp_start = _file_offset(tmp_sections, tmp_name_rva)
    tmp_end = tmp_data.index(b"\0", tmp_start)
    tmp_names.append(tmp_data[tmp_start:tmp_end].decode("ascii"))
    tmp_entry += 20
