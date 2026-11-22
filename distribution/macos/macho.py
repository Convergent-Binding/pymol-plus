"""Reads Mach-O files: architectures, minimum macOS, and universal slices.

The macOS app's build and tests use it to cut PySide6's universal binaries
down to the DMG's architecture and to check that no binary needs a newer
macOS than the app's minimum. Only the standard library is used, so the
checks also run, on fixtures, where Apple's lipo and otool are missing.
"""

import pathlib
import struct


_MH_MAGIC_64 = 0xFEEDFACF
"""The magic number of a 64-bit Mach-O image, read little-endian."""

_MH_MAGIC = 0xFEEDFACE
"""The magic number of a 32-bit Mach-O image, read little-endian."""

_FAT_MAGIC = 0xCAFEBABE
"""The magic number of a universal file, read big-endian."""

_FAT_MAGIC_64 = 0xCAFEBABF
"""The magic number of a universal file with 64-bit offsets."""

_MAX_FAT_SLICES = 20
"""More slices than any universal file has; Java class files share the magic
number and carry their version (45 or more) where the slice count would be."""

_LC_BUILD_VERSION = 0x32
"""The load command that holds the minimum OS since macOS 10.14."""

_LC_VERSION_MIN_MACOSX = 0x24
"""The older load command that holds the minimum macOS."""

_ARCHITECTURES = {0x01000007: "x86_64", 0x0100000C: "arm64", 7: "i386"}
"""The CPU types of the architectures by name."""


def _fat_slices(data: bytes) -> list[tuple[str, int, int]] | None:
  """Lists a universal file's slices.

  Args:
    data: The file's bytes.

  Returns:
    Each slice's architecture, offset and size, or None for a file that is
    not universal.
  """
  if len(data) < 8:
    return None
  tmp_magic, tmp_count = struct.unpack_from(">II", data, 0)
  if tmp_magic not in (_FAT_MAGIC, _FAT_MAGIC_64):
    return None
  if not 0 < tmp_count <= _MAX_FAT_SLICES:
    return None
  tmp_slices = []
  tmp_entry = 8
  for _ in range(tmp_count):
    if tmp_magic == _FAT_MAGIC:
      tmp_cpu, _, tmp_offset, tmp_size, _ = struct.unpack_from(
        ">IIIII", data, tmp_entry
      )
      tmp_entry += 20
    else:
      tmp_cpu, _, tmp_offset, tmp_size, _, _ = struct.unpack_from(
        ">IIQQII", data, tmp_entry
      )
      tmp_entry += 32
    tmp_slices.append(
      (_ARCHITECTURES.get(tmp_cpu, hex(tmp_cpu)), tmp_offset, tmp_size)
    )
  return tmp_slices


def _is_thin(data: bytes) -> bool:
  """Tells whether bytes start a single-architecture Mach-O image.

  Args:
    data: The bytes.

  Returns:
    Whether they carry a Mach-O magic number.
  """
  return len(data) >= 32 and struct.unpack_from("<I", data, 0)[0] in (
    _MH_MAGIC_64,
    _MH_MAGIC,
  )


def is_macho(path: pathlib.Path) -> bool:
  """Tells whether a file is a Mach-O image or a universal file.

  Args:
    path: The file.

  Returns:
    Whether it is one.
  """
  with open(path, "rb") as tmp_handle:
    tmp_head = tmp_handle.read(4096)
  return _is_thin(tmp_head) or _fat_slices(tmp_head) is not None


def _thin_architecture(image: bytes) -> str:
  """Gives a single-architecture image's architecture.

  Args:
    image: The image's bytes.

  Returns:
    The architecture's name.
  """
  tmp_cpu = struct.unpack_from("<I", image, 4)[0]
  return _ARCHITECTURES.get(tmp_cpu, hex(tmp_cpu))


def _slices(data: bytes) -> list[tuple[str, bytes]]:
  """Splits a file into its single-architecture images.

  Args:
    data: A Mach-O image's or a universal file's bytes.

  Returns:
    Each image's architecture and bytes.
  """
  tmp_fat = _fat_slices(data)
  if tmp_fat is None:
    return [(_thin_architecture(data), data)]
  return [
    (tmp_name, data[tmp_offset : tmp_offset + tmp_size])
    for tmp_name, tmp_offset, tmp_size in tmp_fat
  ]


def architectures(path: pathlib.Path) -> list[str]:
  """Lists a Mach-O file's architectures.

  Args:
    path: A Mach-O image or universal file.

  Returns:
    The architectures, in the file's order.
  """
  return [tmp_name for tmp_name, _ in _slices(path.read_bytes())]


def _image_minimum(image: bytes) -> tuple[int, int] | None:
  """Reads a single-architecture image's minimum macOS.

  Args:
    image: The image's bytes.

  Returns:
    (major, minor), or None when the image names none.
  """
  tmp_magic = struct.unpack_from("<I", image, 0)[0]
  tmp_count = struct.unpack_from("<I", image, 16)[0]
  tmp_offset = 32 if tmp_magic == _MH_MAGIC_64 else 28
  for _ in range(tmp_count):
    tmp_command, tmp_size = struct.unpack_from("<II", image, tmp_offset)
    if tmp_command == _LC_BUILD_VERSION:
      tmp_version = struct.unpack_from("<I", image, tmp_offset + 12)[0]
      return tmp_version >> 16, (tmp_version >> 8) & 0xFF
    if tmp_command == _LC_VERSION_MIN_MACOSX:
      tmp_version = struct.unpack_from("<I", image, tmp_offset + 8)[0]
      return tmp_version >> 16, (tmp_version >> 8) & 0xFF
    tmp_offset += tmp_size
  return None


def minimum_macos(path: pathlib.Path) -> tuple[int, int] | None:
  """Reads the macOS version a Mach-O file needs at least.

  Args:
    path: A Mach-O image or universal file.

  Returns:
    (major, minor), the highest of the slices' minimums, or None when no
    slice names one.
  """
  tmp_minimums = [
    tmp_minimum
    for _, tmp_image in _slices(path.read_bytes())
    if (tmp_minimum := _image_minimum(tmp_image)) is not None
  ]
  return max(tmp_minimums) if tmp_minimums else None


def thin(path: pathlib.Path, architecture: str) -> bytes:
  """Cuts a Mach-O file down to one architecture.

  The slice is copied byte for byte, as `lipo -thin` and `ditto --arch` do,
  so its code signature stays valid.

  Args:
    path: A Mach-O image or universal file.
    architecture: Such as "arm64" or "x86_64".

  Returns:
    The image for the architecture.

  Raises:
    ValueError: The file has no slice for the architecture.
  """
  for tmp_name, tmp_image in _slices(path.read_bytes()):
    if tmp_name == architecture:
      return tmp_image
  raise ValueError(f"{path} has no {architecture} slice")
