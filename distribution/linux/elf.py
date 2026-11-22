"""Reads ELF files: the libraries they need and the glibc versions they use.

The Linux app's tests use it to check that every library a binary needs is
bundled or declared by the packages, and that no binary needs a newer glibc
than the oldest supported distribution has. Only the standard library is
used, so the readers also run, on fixtures, away from Linux.
"""

import pathlib
import re
import struct


_MAGIC = b"\x7fELF"
"""The first four bytes of every ELF file."""

_PT_LOAD = 1
"""The program header type of a loaded segment."""

_PT_DYNAMIC = 2
"""The program header type of the dynamic section."""

_DT_NEEDED = 1
"""The dynamic entry naming a needed library."""

_DT_STRTAB = 5
"""The dynamic entry giving the string table's address."""

_GLIBC_VERSION = re.compile(rb"GLIBC_(\d+)\.(\d+)")
"""A glibc symbol version name, as the version tables hold it."""


def is_elf(path: pathlib.Path) -> bool:
  """Tells whether a file is an ELF file.

  Args:
    path: The file.

  Returns:
    Whether it starts with the ELF magic number.
  """
  with open(path, "rb") as tmp_handle:
    return tmp_handle.read(4) == _MAGIC


def _segments(data: bytes) -> list[tuple[int, int, int, int]]:
  """Lists a 64-bit little-endian ELF file's program headers.

  Args:
    data: The file's bytes.

  Returns:
    Each header's type, file offset, virtual address and file size.

  Raises:
    ValueError: The file is not a 64-bit little-endian ELF file.
  """
  if data[:4] != _MAGIC or data[4] != 2 or data[5] != 1:
    raise ValueError("not a 64-bit little-endian ELF file")
  tmp_offset = struct.unpack_from("<Q", data, 32)[0]
  tmp_size, tmp_count = struct.unpack_from("<HH", data, 54)
  tmp_segments = []
  for tmp_index in range(tmp_count):
    tmp_type, _, tmp_file_offset, tmp_address, _, tmp_file_size = (
      struct.unpack_from("<IIQQQQ", data, tmp_offset + tmp_index * tmp_size)
    )
    tmp_segments.append((tmp_type, tmp_file_offset, tmp_address, tmp_file_size))
  return tmp_segments


def _file_offset(segments: list[tuple[int, int, int, int]], address: int) -> int:
  """Maps a virtual address to a file offset through the loaded segments.

  Args:
    segments: The program headers, as _segments gives them.
    address: The address.

  Returns:
    The file offset.

  Raises:
    ValueError: No loaded segment holds the address.
  """
  for tmp_type, tmp_offset, tmp_address, tmp_size in segments:
    if tmp_type == _PT_LOAD and tmp_address <= address < tmp_address + tmp_size:
      return address - tmp_address + tmp_offset
  raise ValueError(f"address {address:#x} is in no loaded segment")


def needed_libraries(path: pathlib.Path) -> list[str]:
  """Lists the libraries an ELF file needs (its DT_NEEDED entries).

  Args:
    path: A shared library or executable.

  Returns:
    The library names, in the file's order; none for a static file.
  """
  tmp_data = path.read_bytes()
  tmp_segments = _segments(tmp_data)
  tmp_dynamic = [s for s in tmp_segments if s[0] == _PT_DYNAMIC]
  if not tmp_dynamic:
    return []
  _, tmp_offset, _, tmp_size = tmp_dynamic[0]
  tmp_needed = []
  tmp_strtab = None
  for tmp_entry in range(tmp_offset, tmp_offset + tmp_size, 16):
    tmp_tag, tmp_value = struct.unpack_from("<qQ", tmp_data, tmp_entry)
    if tmp_tag == 0:
      break
    if tmp_tag == _DT_NEEDED:
      tmp_needed.append(tmp_value)
    elif tmp_tag == _DT_STRTAB:
      tmp_strtab = _file_offset(tmp_segments, tmp_value)
  if tmp_strtab is None:
    return []
  return [
    tmp_data[tmp_strtab + tmp_name : tmp_data.index(b"\0", tmp_strtab + tmp_name)]
    .decode("ascii")
    for tmp_name in tmp_needed
  ]


def glibc_versions(path: pathlib.Path) -> set[tuple[int, int]]:
  """Reads the glibc versions an ELF file's symbols ask for.

  Args:
    path: A shared library or executable.

  Returns:
    Each (major, minor) GLIBC_ version the file names.
  """
  return {
    (int(tmp_major), int(tmp_minor))
    for tmp_major, tmp_minor in _GLIBC_VERSION.findall(path.read_bytes())
  }
