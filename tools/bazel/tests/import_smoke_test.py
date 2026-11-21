"""PyMOL imports and runs from Bazel's build of _cmd, _champ and the data tree.

The packages come from modules/ with the extensions and data staged beside
them (//modules/pymol:cmd_extension_for_run and friends), as in an installed
wheel. A link error, a missing data file PyMOL reads at start-up, or a build
info header without its git SHA fails here.
"""

import unittest

from pymol2 import PyMOL


class ImportSmokeTest(unittest.TestCase):
  """A headless session builds a molecule; _champ imports; version has a SHA."""

  def test_session_builds_alanine(self) -> None:
    with PyMOL() as session:
      session.cmd.fragment("ala")
      self.assertEqual(session.cmd.count_atoms(), 10)

  def test_champ_imports(self) -> None:
    from chempy.champ import _champ  # pylint: disable=import-outside-toplevel

    self.assertTrue(callable(_champ.new))

  def test_version_carries_git_sha(self) -> None:
    with PyMOL() as session:
      sha = session.cmd.get_version()[4]
    self.assertRegex(sha, r"^[0-9a-f]{40}$")


if __name__ == "__main__":
  unittest.main()
