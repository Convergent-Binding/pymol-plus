"""Writes the Windows launcher's resources, the app icon and its version.

The output is a compiled resource file (.res), which the MSVC linker links
into the executable, so the launcher needs no resource compiler from the
Windows SDK. The format is a sequence of entries, each a header naming the
resource's type and id, then its data, every entry aligned to 4 bytes.
"""

import argparse
import pathlib
import re
import struct
import sys
import tomllib


_RT_ICON = 3
"""The resource type of one icon image."""

_RT_GROUP_ICON = 14
"""The resource type of an icon's image directory."""

_RT_VERSION = 16
"""The resource type of the version information."""

_LANGUAGE = 0x0409
"""English (United States), the language of the version strings."""

_CODE_PAGE = 0x04B0
"""Unicode, the code page of the version strings."""

_MOVEABLE_DISCARDABLE = 0x1010
"""The memory flags resource compilers give icon images."""

_GROUP_FLAGS = 0x1030
"""The memory flags resource compilers give icon groups and versions."""

_PRODUCT = "PyMOL-Open-Source"
"""The product and executable name."""

_COPYRIGHT = "Hannah Kullik, Schrodinger LLC"
"""The copyright the installer names (AppCopyright in setup.iss)."""


def _align(data: bytes) -> bytes:
  """Pads data with zero bytes to a multiple of 4.

  Args:
    data: The bytes.

  Returns:
    The padded bytes.
  """
  return data + b"\0" * (-len(data) % 4)


def _entry(resource_type: int, name: int, flags: int, data: bytes) -> bytes:
  """Builds one .res entry with a numeric type and id.

  Args:
    resource_type: The resource type, such as RT_ICON.
    name: The resource id.
    flags: The memory flags.
    data: The resource's data.

  Returns:
    The header, the data and the padding to the next entry.
  """
  tmp_header = struct.pack(
    "<IIHHHHIHHII",
    len(data),
    32,
    0xFFFF,
    resource_type,
    0xFFFF,
    name,
    0,
    flags,
    _LANGUAGE if resource_type else 0,
    0,
    0,
  )
  return _align(tmp_header + data)


def _icon_entries(icon: bytes) -> bytes:
  """Turns an .ico file into one RT_ICON per image and an RT_GROUP_ICON.

  Args:
    icon: The .ico file's bytes.

  Returns:
    The entries; the group has id 1, the images ids 1, 2, ...
  """
  tmp_reserved, tmp_kind, tmp_count = struct.unpack_from("<HHH", icon, 0)
  if tmp_reserved != 0 or tmp_kind != 1 or tmp_count == 0:
    raise ValueError("not an .ico file")
  tmp_entries = b""
  tmp_group = struct.pack("<HHH", 0, 1, tmp_count)
  for tmp_index in range(tmp_count):
    tmp_fields = struct.unpack_from("<BBBBHHII", icon, 6 + 16 * tmp_index)
    tmp_size, tmp_offset = tmp_fields[6], tmp_fields[7]
    tmp_entries += _entry(
      _RT_ICON,
      tmp_index + 1,
      _MOVEABLE_DISCARDABLE,
      icon[tmp_offset : tmp_offset + tmp_size],
    )
    tmp_group += struct.pack("<BBBBHHIH", *tmp_fields[:7], tmp_index + 1)
  return tmp_entries + _entry(_RT_GROUP_ICON, 1, _GROUP_FLAGS, tmp_group)


def _node(
  key: str, value: bytes, text: bool, value_length: int, children: bytes = b""
) -> bytes:
  """Builds one block of the version information tree.

  Args:
    key: The block's key, such as "StringFileInfo".
    value: Its value's bytes.
    text: Whether the value is text (wType 1) rather than binary (0).
    value_length: wValueLength: characters for text, bytes for binary.
    children: The child blocks, each already aligned.

  Returns:
    The block, aligned to 4 bytes.
  """
  tmp_body = _align(b"\0" * 6 + (key + "\0").encode("utf-16-le")) + value
  tmp_block = (_align(tmp_body) + children) if children else tmp_body
  tmp_header = struct.pack("<HHH", len(tmp_block), value_length, int(text))
  return _align(tmp_header + tmp_block[6:])


def _string(key: str, value: str) -> bytes:
  """Builds one string of a StringTable.

  Args:
    key: The string's name, such as "ProductName".
    value: Its text.

  Returns:
    The block.
  """
  tmp_value = (value + "\0").encode("utf-16-le")
  return _node(key, tmp_value, True, len(value) + 1)


def _numeric_version(version: str) -> tuple[int, int]:
  """Packs the first four numbers of a version into two DWORDs.

  Args:
    version: Such as "3.2.0.3+1"; the local part after "+" is left out.

  Returns:
    The most and the least significant DWORD of the fixed file version.
  """
  tmp_numbers = [
    int(tmp_part) for tmp_part in re.findall(r"\d+", version.split("+")[0])
  ]
  tmp_numbers = (tmp_numbers + [0, 0, 0, 0])[:4]
  return (tmp_numbers[0] << 16) | tmp_numbers[1], (
    tmp_numbers[2] << 16
  ) | tmp_numbers[3]


def _version_entry(version: str) -> bytes:
  """Builds the RT_VERSION entry.

  Args:
    version: The app's version.

  Returns:
    The entry.
  """
  tmp_ms, tmp_ls = _numeric_version(version)
  tmp_fixed = struct.pack(
    "<13I",
    0xFEEF04BD,
    0x00010000,
    tmp_ms,
    tmp_ls,
    tmp_ms,
    tmp_ls,
    0x3F,
    0,
    0x00040004,
    1,
    0,
    0,
    0,
  )
  tmp_strings = b"".join(
    _string(tmp_key, tmp_value)
    for tmp_key, tmp_value in (
      ("CompanyName", _COPYRIGHT),
      ("FileDescription", _PRODUCT),
      ("FileVersion", version),
      ("InternalName", _PRODUCT),
      ("LegalCopyright", _COPYRIGHT),
      ("OriginalFilename", f"{_PRODUCT}.exe"),
      ("ProductName", _PRODUCT),
      ("ProductVersion", version),
    )
  )
  tmp_table = _node(
    f"{_LANGUAGE:04X}{_CODE_PAGE:04X}", b"", True, 0, tmp_strings
  )
  tmp_string_info = _node("StringFileInfo", b"", True, 0, tmp_table)
  tmp_translation = struct.pack("<HH", _LANGUAGE, _CODE_PAGE)
  tmp_var = _node("Translation", tmp_translation, False, len(tmp_translation))
  tmp_var_info = _node("VarFileInfo", b"", True, 0, tmp_var)
  tmp_version_info = _node(
    "VS_VERSION_INFO",
    tmp_fixed,
    False,
    len(tmp_fixed),
    tmp_string_info + tmp_var_info,
  )
  return _entry(_RT_VERSION, 1, _GROUP_FLAGS, tmp_version_info)


def main(argv: list[str]) -> int:
  """Writes the .res file.

  Args:
    argv: --icon <.ico>, --pyproject <pyproject.toml> with the app's version,
      --out <.res>.

  Returns:
    0.
  """
  tmp_parser = argparse.ArgumentParser()
  tmp_parser.add_argument("--icon", required=True)
  tmp_parser.add_argument("--pyproject", required=True)
  tmp_parser.add_argument("--out", required=True)
  tmp_arguments = tmp_parser.parse_args(argv)
  with open(tmp_arguments.pyproject, "rb") as tmp_handle:
    tmp_version = tomllib.load(tmp_handle)["project"]["version"]
  pathlib.Path(tmp_arguments.out).write_bytes(
    _entry(0, 0, 0, b"")
    + _icon_entries(pathlib.Path(tmp_arguments.icon).read_bytes())
    + _version_entry(tmp_version)
  )
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
