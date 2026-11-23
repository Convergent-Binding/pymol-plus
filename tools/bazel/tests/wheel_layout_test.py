"""The wheel //tools/bazel/wheel:wheel builds for the host platform.

Its tags and extension names must be the ones the interpreter running this
test -- the toolchain the extensions were compiled against -- accepts: a wheel
whose `_cmd` suffix that interpreter does not import installs cleanly and then
fails at `import pymol._cmd`. Its members must be the packages, the extensions
and the data tree at their installed paths, and nothing at a source path.
"""

import email.parser
import importlib.machinery
import pathlib
import platform
import sys
import unittest
import zipfile

_WHEEL = next(
    pathlib.Path(p) for p in sys.argv[1].split() if p.endswith(".whl")
)
_VERSION = sys.argv[2]
_PYTHON_TAG = f"cp{sys.version_info.major}{sys.version_info.minor}"
_EXTENSION_SUFFIX = importlib.machinery.EXTENSION_SUFFIXES[0]


def _expected_platform_tag() -> str:
  machine = platform.machine().lower()
  if sys.platform == "win32":
    return "win_amd64"
  if sys.platform == "darwin":
    return "macosx_12_0_" + ("arm64" if machine == "arm64" else "x86_64")
  return "linux_" + machine


class WheelLayoutTest(unittest.TestCase):
  """Name, members and metadata of the built wheel."""

  @classmethod
  def setUpClass(cls) -> None:
    with zipfile.ZipFile(_WHEEL) as wheel:
      cls.members = set(wheel.namelist())
      metadata_name = next(
          m for m in cls.members if m.endswith(".dist-info/METADATA")
      )
      cls.metadata = email.parser.Parser().parsestr(
          wheel.read(metadata_name).decode("utf-8")
      )

  def test_file_name_carries_the_interpreter_and_platform_tags(self) -> None:
    self.assertEqual(
        _WHEEL.name,
        f"pymol_open_source_whl-{_VERSION}-{_PYTHON_TAG}-{_PYTHON_TAG}"
        f"-{_expected_platform_tag()}.whl",
    )

  def test_extensions_are_named_for_this_interpreter(self) -> None:
    self.assertIn(f"pymol/_cmd{_EXTENSION_SUFFIX}", self.members)
    self.assertIn(f"chempy/champ/_champ{_EXTENSION_SUFFIX}", self.members)

  def test_packages_and_data_are_at_installed_paths(self) -> None:
    """Every package, pymol3 included, and PyMOL's data install in place."""
    for member in (
        "pymol/__init__.py",
        "pymol2/__init__.py",
        "pymol3/__init__.py",
        "chempy/__init__.py",
        "pmg_tk/__init__.py",
        "pmg_qt/forms/colors.ui",
        "pymol/data/shaders/default.vs",
    ):
      with self.subTest(member=member):
        self.assertIn(member, self.members)

  def test_nothing_is_at_a_source_path(self) -> None:
    for prefix in ("modules/", "tools/", "data/", "contrib/", "bazel-out/"):
      with self.subTest(prefix=prefix):
        self.assertEqual(
            [m for m in self.members if m.startswith(prefix)], []
        )

  def test_metadata_matches_pyproject(self) -> None:
    self.assertEqual(self.metadata["Name"], "pymol-open-source-whl")
    self.assertEqual(self.metadata["Version"], _VERSION)
    self.assertEqual(self.metadata["Requires-Python"], ">=3.10")
    self.assertEqual(self.metadata.get_all("Requires-Dist"), ["numpy>=2.2"])


if __name__ == "__main__":
  unittest.main(argv=sys.argv[:1])
