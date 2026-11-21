"""Holds the wheel metadata Bazel reads from pyproject.toml to tomllib's reading.

//tools/bazel:pyproject.bzl parses a subset of TOML in Starlark, so the build
can load the [project] fields at loading time. This test parses the same file
with CPython's real TOML parser and fails when the two disagree, which keeps
the hand-written reader honest.
"""

import json
import sys
import tomllib
import unittest

_METADATA_JSON, _PYPROJECT = sys.argv[1:3]


class PyprojectMetadataTest(unittest.TestCase):
  """The constants @pymol_project_metadata exports match pyproject.toml."""

  @classmethod
  def setUpClass(cls) -> None:
    with open(_METADATA_JSON, encoding="utf-8") as handle:
      cls.metadata = json.load(handle)
    with open(_PYPROJECT, "rb") as handle:
      cls.project = tomllib.load(handle)["project"]

  def test_name(self) -> None:
    self.assertEqual(self.metadata["NAME"], self.project["name"])

  def test_version(self) -> None:
    self.assertEqual(self.metadata["VERSION"], self.project["version"])

  def test_requires_python(self) -> None:
    self.assertEqual(self.metadata["REQUIRES_PYTHON"], ">=3.10")
    self.assertEqual(
        self.metadata["REQUIRES_PYTHON"], self.project["requires-python"]
    )

  def test_dependencies(self) -> None:
    self.assertEqual(self.metadata["DEPENDENCIES"], ["numpy>=2.2"])
    self.assertEqual(
        self.metadata["DEPENDENCIES"], self.project["dependencies"]
    )


if __name__ == "__main__":
  unittest.main(argv=sys.argv[:1])
