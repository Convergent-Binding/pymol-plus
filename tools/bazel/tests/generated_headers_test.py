"""The shader text and build info //tools/bazel:pymol_generated_headers writes.

ShaderText.cpp is the only way shaders reach PyMOL at run time: CShaderMgr
reads `_shader_cache_raw` and resolves each shader's `#include` lines against
the same cache (layer0/ShaderMgr.cpp). A shader file missing from the cache,
or an include naming a file that is not in it, fails only when that shader is
compiled on a user's GPU.
"""

import pathlib
import re
import sys
import unittest

_SHADER_SUFFIXES = (".vs", ".fs", ".gs", ".tsc", ".tse", ".shared")


def _by_name(paths: list[str], name: str) -> pathlib.Path:
  matches = [pathlib.Path(p) for p in paths if pathlib.Path(p).name == name]
  if len(matches) != 1:
    raise AssertionError(f"expected one {name} among {paths}")
  return matches[0]


_GENERATED = sys.argv[1].split()
_SHADER_SRCS = [pathlib.Path(p) for p in sys.argv[2].split()]


class GeneratedHeadersTest(unittest.TestCase):
  """Every shader is in the cache; every include resolves; build info is set."""

  @classmethod
  def setUpClass(cls) -> None:
    cls.shader_text = _by_name(_GENERATED, "ShaderText.cpp").read_text()
    cls.build_info = _by_name(_GENERATED, "PyMOLBuildInfo.h").read_text()
    cls.cached = set(re.findall(r'^"([^"\\]+)", ""$', cls.shader_text, re.M))

  def test_every_shader_file_is_cached(self) -> None:
    shaders = {p.name for p in _SHADER_SRCS if p.suffix in _SHADER_SUFFIXES}
    self.assertTrue(shaders)
    self.assertEqual(shaders - self.cached, set())

  def test_every_file_include_names_a_cached_shader(self) -> None:
    included = set(re.findall(r'^"#include (\S+)\\n"$', self.shader_text, re.M))
    files = {name for name in included if name.endswith(_SHADER_SUFFIXES)}
    self.assertTrue(files)
    self.assertEqual(files - self.cached, set())

  def test_build_info_has_sha_and_date(self) -> None:
    sha = re.search(r'_PYMOL_BUILD_GIT_SHA "([^"]*)"', self.build_info)
    date = re.search(r"_PyMOL_BUILD_DATE (\d+)", self.build_info)
    self.assertRegex(sha.group(1), r"^([0-9a-f]{40}|unknown)$")
    self.assertGreater(int(date.group(1)), 0)


if __name__ == "__main__":
  unittest.main(argv=sys.argv[:1])
