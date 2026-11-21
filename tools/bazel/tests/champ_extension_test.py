"""The built _champ extension loads into the interpreter it was built for.

Loads the shared library straight from Bazel's output, without the chempy
package around it, so a broken link (a missing Python import library on
Windows, an unresolved symbol on macOS) fails here rather than at
`import chempy.champ` in an installed wheel.
"""

import importlib.machinery
import importlib.util
import sys
import unittest

_CHAMP_PATH = sys.argv[1]


class ChampExtensionTest(unittest.TestCase):
  """_champ exposes the functions chempy.champ calls."""

  def test_loads_and_exposes_its_functions(self) -> None:
    loader = importlib.machinery.ExtensionFileLoader("_champ", _CHAMP_PATH)
    spec = importlib.util.spec_from_file_location(
        "_champ", _CHAMP_PATH, loader=loader
    )
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    self.assertTrue(callable(module.new))
    self.assertTrue(callable(module.insert_model))


if __name__ == "__main__":
  unittest.main(argv=sys.argv[:1])
