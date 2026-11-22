"""make_resources writes the launcher's icon and version as a .res file.

The tests read the .res back: a sequence of entries, each a header with the
resource type, name and size, then its data, every entry DWORD-aligned.
"""

import pathlib
import struct
import tempfile
import unittest

import make_resources


_RT_ICON = 3
"""The resource type of one icon image."""

_RT_GROUP_ICON = 14
"""The resource type of an icon's image directory."""

_RT_VERSION = 16
"""The resource type of the version information."""


def _ico(sizes: tuple[int, ...]) -> bytes:
  """Builds an .ico file with one fake PNG image per size.

  Args:
    sizes: The images' widths and heights in pixels.

  Returns:
    The file's bytes.
  """
  tmp_images = [bytes([tmp_size]) * (10 + tmp_size) for tmp_size in sizes]
  tmp_header = struct.pack("<HHH", 0, 1, len(sizes))
  tmp_offset = 6 + 16 * len(sizes)
  tmp_entries = b""
  for tmp_size, tmp_image in zip(sizes, tmp_images, strict=True):
    tmp_entries += struct.pack(
      "<BBBBHHII", tmp_size, tmp_size, 0, 0, 1, 32, len(tmp_image), tmp_offset
    )
    tmp_offset += len(tmp_image)
  return tmp_header + tmp_entries + b"".join(tmp_images)


def _entries(data: bytes) -> list[tuple[int, int, int, bytes]]:
  """Splits a .res file into its entries.

  Args:
    data: The file's bytes.

  Returns:
    Each entry's offset, type id, name id and data.
  """
  tmp_entries = []
  tmp_offset = 0
  while tmp_offset < len(data):
    tmp_size, tmp_header_size = struct.unpack_from("<II", data, tmp_offset)
    tmp_type = struct.unpack_from("<HH", data, tmp_offset + 8)[1]
    tmp_name = struct.unpack_from("<HH", data, tmp_offset + 12)[1]
    tmp_start = tmp_offset + tmp_header_size
    tmp_entries.append(
      (tmp_offset, tmp_type, tmp_name, data[tmp_start : tmp_start + tmp_size])
    )
    tmp_offset = (tmp_start + tmp_size + 3) & ~3
  return tmp_entries


class MakeResourcesTest(unittest.TestCase):
  """Runs make_resources.main on a fake icon and version."""

  def setUp(self) -> None:
    """Writes a two-image icon and a pyproject.toml."""
    self._dir = tempfile.TemporaryDirectory()
    self.root = pathlib.Path(self._dir.name)
    self.icon = self.root / "logo.ico"
    self.icon.write_bytes(_ico((16, 32)))
    self.pyproject = self.root / "pyproject.toml"
    self.pyproject.write_text(
      '[project]\nversion = "3.2.0.3+1"\n', encoding="utf-8"
    )
    self.out = self.root / "launcher.res"

  def tearDown(self) -> None:
    """Removes the temporary folder."""
    self._dir.cleanup()

  def _make(self) -> list[tuple[int, int, int, bytes]]:
    """Writes the .res and reads it back.

    Returns:
      Its entries, as _entries gives them.
    """
    tmp_status = make_resources.main(
      [
        "--icon",
        str(self.icon),
        "--pyproject",
        str(self.pyproject),
        "--out",
        str(self.out),
      ]
    )
    self.assertEqual(tmp_status, 0)
    return _entries(self.out.read_bytes())

  def test_icon_group_lists_every_image(self) -> None:
    """One RT_ICON per image, and an RT_GROUP_ICON naming them by id."""
    tmp_entries = self._make()

    tmp_icons = {
      tmp_name: tmp_data
      for _, tmp_type, tmp_name, tmp_data in tmp_entries
      if tmp_type == _RT_ICON
    }
    self.assertEqual(sorted(tmp_icons), [1, 2])
    self.assertEqual(tmp_icons[1], bytes([16]) * 26)
    tmp_group = [
      tmp_data
      for _, tmp_type, _, tmp_data in tmp_entries
      if tmp_type == _RT_GROUP_ICON
    ]
    self.assertEqual(len(tmp_group), 1)
    tmp_count = struct.unpack_from("<H", tmp_group[0], 4)[0]
    tmp_ids = [
      struct.unpack_from("<H", tmp_group[0], 6 + 14 * tmp_index + 12)[0]
      for tmp_index in range(tmp_count)
    ]
    self.assertEqual(tmp_ids, [1, 2])

  def test_version_strings(self) -> None:
    """RT_VERSION names the product and the app's full version."""
    tmp_version = [
      tmp_data
      for _, tmp_type, _, tmp_data in self._make()
      if tmp_type == _RT_VERSION
    ]
    self.assertEqual(len(tmp_version), 1)
    for tmp_text in ("ProductName", "PyMOL-Open-Source", "3.2.0.3+1"):
      self.assertIn(tmp_text.encode("utf-16-le"), tmp_version[0])
    tmp_signature = struct.pack("<I", 0xFEEF04BD)
    tmp_fixed = tmp_version[0].index(tmp_signature)
    tmp_ms, tmp_ls = struct.unpack_from("<II", tmp_version[0], tmp_fixed + 8)
    self.assertEqual((tmp_ms, tmp_ls), ((3 << 16) | 2, (0 << 16) | 3))

  def test_resources_are_dword_aligned(self) -> None:
    """Every entry starts on a DWORD boundary, the first one empty."""
    tmp_entries = self._make()

    self.assertEqual(tmp_entries[0][1:], (0, 0, b""))
    for tmp_offset, _, _, _ in tmp_entries:
      self.assertEqual(tmp_offset % 4, 0)


if __name__ == "__main__":
  unittest.main()
