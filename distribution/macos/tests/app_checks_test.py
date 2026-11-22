"""Every binary in PyMOL-Open-Source.app suits the DMG's Macs.

Each DMG is for one architecture and macOS 12 or later: a universal binary
left in the app doubles its size, and a binary from a wheel built for macOS
13 or 14 stops the app on older Macs.
"""

import pathlib
import sys
import unittest

import macho


_APP = pathlib.Path(sys.argv[1]).resolve()
"""The built PyMOL-Open-Source.app."""

_ARCH = sys.argv[2]
"""The DMG's architecture, "arm64" or "x86_64"."""

_MINIMUM = (12, 0)
"""The app's minimum macOS, LSMinimumSystemVersion in Info.plist."""


def _binaries() -> list[pathlib.Path]:
  """Lists the app's Mach-O files.

  Returns:
    Their paths, sorted.
  """
  return sorted(
    tmp_path
    for tmp_path in _APP.rglob("*")
    if tmp_path.is_file() and macho.is_macho(tmp_path)
  )


class AppChecksTest(unittest.TestCase):
  """Reads every Mach-O file of the app."""

  def test_the_app_has_binaries(self) -> None:
    """The launcher and the runtime are among them."""
    tmp_names = {tmp_path.name for tmp_path in _binaries()}

    self.assertIn("PyMOL-Open-Source", tmp_names)
    self.assertIn("libpython3.13.dylib", tmp_names)

  def test_every_macho_targets_one_architecture(self) -> None:
    """Every binary holds only the DMG's architecture."""
    tmp_wrong = [
      f"{tmp_path.relative_to(_APP)}: {macho.architectures(tmp_path)}"
      for tmp_path in _binaries()
      if macho.architectures(tmp_path) != [_ARCH]
    ]

    self.assertEqual(tmp_wrong, [])

  def test_minimum_macos_at_most_12(self) -> None:
    """No binary needs a newer macOS than the app's minimum."""
    tmp_newer = [
      f"{tmp_path.relative_to(_APP)}: {tmp_minimum}"
      for tmp_path in _binaries()
      if (tmp_minimum := macho.minimum_macos(tmp_path)) is not None
      and tmp_minimum > _MINIMUM
    ]

    self.assertEqual(tmp_newer, [])


if __name__ == "__main__":
  unittest.main(argv=sys.argv[:1])
